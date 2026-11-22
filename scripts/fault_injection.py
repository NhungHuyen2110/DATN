"""Default dry-run. Stop/start ONE verified container belonging to isolated test project."""
import argparse
import json
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

PROJECT = 'lumiere-rebuild-test'
SERVICES = {'ai-api', 'neo4j', 'qdrant', 'ollama', 'prometheus', 'grafana', 'frontend', 'business-api', 'postgres'}
ROOT = Path(__file__).resolve().parents[1]


def business_transaction_probe(base):
    """Only the synthetic Compose fixture; credentials/results never printed."""
    import requests
    core = json.loads((ROOT / 'docs/compose-core-runtime-20261122.json').read_text())
    fixture = json.loads((ROOT / '.local-tmp/compose-core-20261122/fixture.json').read_text())
    if (core.get('project') != PROJECT or core.get('production_accessed') is not False
            or fixture.get('synthetic_only') is not True):
        raise ValueError('Verified synthetic Compose fixture required for write probes')
    env = fixture['fixture_env']
    with requests.Session() as client:
        client.trust_env = False
        login = client.post(base + '/api/auth/login', json={'email': env['LUMIERE_E2E_CUSTOMER_EMAIL'],
            'password': env['LUMIERE_E2E_CUSTOMER_PASSWORD']}, timeout=5)
        if login.status_code != 200 or client.get(base + '/api/auth/me', timeout=5).json().get('role') != 'customer':
            raise AssertionError('Synthetic customer login failed during AI outage')
        assert client.post(base + '/api/cart/items', json={'product_id': 1, 'quantity': 1}, timeout=5).status_code == 200
        order = client.post(base + '/api/orders', json={'recipient_name': 'Synthetic container outage customer',
            'phone': '0901234567', 'address': 'Synthetic isolated address', 'payment_method': 'cod'}, timeout=5)
        assert order.status_code == 201
        identity = order.json()['id']
        own = client.get(base + '/api/orders/' + str(identity), timeout=5)
        assert own.status_code == 200 and own.json()['payment_method'] == 'cod'
        assert client.get(base + '/api/admin/orders', timeout=5).status_code == 403
    return {'passed': True, 'customer_login': 200, 'cod_checkout': 201, 'own_order_read': 200,
            'customer_admin_access': 403, 'order_id': identity, 'production_accessed': False}


def docker(*arguments):
    process = subprocess.run(['docker', *arguments], text=True, capture_output=True, timeout=25)
    if process.returncode:
        raise RuntimeError('Docker command failed (raw output intentionally suppressed)')
    return process.stdout.strip()


def verify_identity(details, service):
    labels = details.get('Config', {}).get('Labels', {})
    if labels.get('com.docker.compose.project') != PROJECT or labels.get('com.docker.compose.service') != service:
        raise ValueError('Container is outside the isolated test project/service')
    if not details.get('State', {}).get('Running'):
        raise ValueError('Target must already be running; do not change initially stopped containers')


def validate_base(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost'}
            or parsed.port != 18080 or parsed.path not in {'', '/'} or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise ValueError('Only isolated loopback proxy port 18080 is allowed')


def probe(base, path):
    try:
        # The DB connect budget is 3 s; allow the API to return its controlled
        # 503 instead of recording a caller timeout before that budget expires.
        with urlopen(Request(base.rstrip('/') + path), timeout=5) as response:
            return response.status
    except HTTPError as exc:
        return exc.code
    except OSError:
        return 0


def retrieval_snapshot(ai_container):
    """Fixed public-catalog query; internal credentials never leave the container."""
    code = r'''
import json,os,urllib.request,urllib.error
from decimal import Decimal
request=urllib.request.Request('http://127.0.0.1:8000/internal/retrieval-diagnostics',
 data=json.dumps({'query':'Top 3 nh\u1eabn d\u01b0\u1edbi 8 tri\u1ec7u','top_k':3}).encode(),
 headers={'Content-Type':'application/json','Authorization':'Bearer '+os.environ['LUMIERE_AI_DIAGNOSTICS_TOKEN']})
try:
 with urllib.request.urlopen(request,timeout=25) as response: data=json.load(response)
 d=data.get('diagnostics',{})
 print(json.dumps({'http':200,'status':data.get('status'),
  'products':len(data.get('products',[])),
  'dense_candidates':len(d.get('source_ranks',{}).get('dense',[])),
  'graph_candidates':len(d.get('source_ranks',{}).get('graph',[])),
  'source_errors':d.get('source_errors',{}),
  'live_filters_valid':all(p['CategoryID']==1 and p['Stock']>0 and Decimal(str(p['Price']))<8000000 and p.get('verified_source')=='business_api' for p in data.get('products',[]))}))
except urllib.error.HTTPError as exc: print(json.dumps({'http':exc.code}))
'''
    process = subprocess.run(['docker', 'exec', '-i', ai_container, 'python', '-B', '-'],
                             input=code, capture_output=True, text=True, timeout=35)
    if process.returncode:
        raise RuntimeError('Internal retrieval probe failed; raw output suppressed')
    return json.loads(process.stdout)


def retrieval_healthy(snapshot):
    return (snapshot.get('http') == 200 and snapshot.get('status') == 'ok'
            and snapshot.get('dense_candidates', 0) > 0 and snapshot.get('graph_candidates', 0) > 0
            and snapshot.get('products') == 3 and snapshot.get('live_filters_valid') is True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service', choices=sorted(SERVICES), required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:18080')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-isolated', action='store_true')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--business-transaction-probe', action='store_true',
                        help='AI outage only: login/COD/ownership probes against the synthetic Compose fixture')
    parser.add_argument('--retrieval-probe', action='store_true',
                        help='Read-only dense/graph failure and semantic recovery checks')
    parser.add_argument('--recovery-timeout', type=int, default=60,
                        help='Explicit recovery observation budget, 30..300 seconds')
    parser.add_argument('--baseline-timeout', type=int, default=60,
                        help='Wait for healthy retrieval before stopping anything, 1..180 seconds')
    args = parser.parse_args()
    if not 30 <= args.recovery_timeout <= 300:
        parser.error('Recovery timeout must be 30..300 seconds')
    if not 1 <= args.baseline_timeout <= 180:
        parser.error('Baseline timeout must be 1..180 seconds')
    if args.business_transaction_probe and (args.service != 'ai-api' or not args.apply):
        parser.error('Synthetic business write probes require an applied isolated AI fault')
    if args.retrieval_probe and (args.service not in {'qdrant', 'neo4j', 'postgres'} or not args.apply):
        parser.error('Retrieval probes require an applied isolated Qdrant/Neo4j/PostgreSQL fault')
    validate_base(args.base_url)
    plan = {'project': PROJECT, 'service': args.service, 'applied': False,
            'recovery_budget_seconds': args.recovery_timeout,
            'limitation': 'HTTP isolation smoke only; not login/checkout or semantic fallback quality verification'}
    if not args.apply:
        print(json.dumps(plan))
        return 0
    if not args.confirm_isolated or not args.report or args.report.exists():
        parser.error('Apply requires isolated confirmation and a new report path')
    ids = docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT,
                 '--filter', 'label=com.docker.compose.service=' + args.service).splitlines()
    if len(ids) != 1:
        raise ValueError('Expected exactly one running test container')
    container = ids[0]
    verify_identity(json.loads(docker('inspect', container))[0], args.service)
    paths = ['/', '/api/health/live', '/api/health/ready', '/api/products?page_size=1', '/ai/health/live']
    baseline = {path: probe(args.base_url, path) for path in paths}
    if any(code != 200 for code in baseline.values()):
        raise ValueError('Healthy seeded baseline required before stopping anything')
    plan['baseline'] = baseline
    ai_container = None
    if args.retrieval_probe:
        ai_ids = docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT,
                        '--filter', 'label=com.docker.compose.service=ai-api').splitlines()
        if len(ai_ids) != 1:
            raise ValueError('Exactly one isolated AI container required')
        ai_container = ai_ids[0]
        verify_identity(json.loads(docker('inspect', ai_container))[0], 'ai-api')
        probes = plan['retrieval_baseline_probes'] = []
        deadline = time.perf_counter() + args.baseline_timeout
        while time.perf_counter() < deadline:
            try:
                snapshot = retrieval_snapshot(ai_container)
            except Exception as error:
                snapshot = {'error_type': type(error).__name__}
            probes.append(snapshot)
            if retrieval_healthy(snapshot):
                break
            time.sleep(3)
        plan['retrieval_baseline'] = probes[-1] if probes else {'error_type': 'BaselineBudgetElapsed'}
        if not retrieval_healthy(plan['retrieval_baseline']):
            plan.update({'isolation_passed': False, 'fault_not_started': 'retrieval_baseline_unavailable'})
            with args.report.open('x', encoding='utf-8') as handle:
                json.dump(plan, handle, indent=2)
            print(json.dumps(plan))
            return 1
    stopped = False
    try:
        # Mark before calling: even a CLI timeout may have stopped the container.
        stopped = True
        docker('stop', '--time', '10', container)
        plan['applied'] = True
        plan['during_failure'] = {path: probe(args.base_url, path) for path in paths}
        during = plan['during_failure']
        if args.service == 'frontend':
            passed = during['/'] != 200 and during['/api/health/ready'] == 200 and during['/ai/health/live'] == 200
        elif args.service == 'business-api':
            passed = during['/'] == 200 and during['/api/health/ready'] != 200 and during['/ai/health/live'] == 200
        elif args.service == 'postgres':
            passed = during['/'] == 200 and during['/api/health/live'] == 200 and during['/api/health/ready'] == 503
        elif args.service == 'ai-api':
            passed = during['/ai/health/live'] != 200 and all(during[path] == 200 for path in paths[:-1])
        else:
            passed = all(code == 200 for code in during.values())
        plan['isolation_passed'] = passed
        if args.retrieval_probe:
            snapshot = plan['retrieval_during_failure'] = retrieval_snapshot(ai_container)
            if args.service == 'postgres':
                semantic_passed = snapshot.get('http') == 503
            else:
                failed_source, fallback = ('dense', 'graph') if args.service == 'qdrant' else ('graph', 'dense')
                semantic_passed = (snapshot.get('status') == 'degraded'
                    and failed_source in snapshot.get('source_errors', {})
                    and snapshot.get(fallback + '_candidates', 0) > 0
                    and snapshot.get('products') == 3 and snapshot.get('live_filters_valid') is True)
            plan['retrieval_fault_passed'] = semantic_passed
            plan['isolation_passed'] = passed and semantic_passed
            plan['limitation'] = 'Actual isolated dependency fault with read-only dense/graph fallback and live filters; no checkout or Qwen quality claim'
        if args.business_transaction_probe:
            plan['business_transaction_probe'] = business_transaction_probe(args.base_url)
            plan['limitation'] = 'Actual container AI outage with synthetic login/COD/role guard; not all dependency faults or quality evaluation'
    except Exception as exc:
        plan['failure_error_type'] = type(exc).__name__
        plan['isolation_passed'] = False
    finally:
        if stopped:
            start = time.perf_counter()
            recovered = False
            try:
                docker('start', container)
                deadline = start + args.recovery_timeout
                while time.perf_counter() < deadline:
                    current = {path: probe(args.base_url, path) for path in paths}
                    if current == baseline:
                        recovered = True
                        break
                    time.sleep(1)
                if recovered and args.business_transaction_probe:
                    import requests
                    from decimal import Decimal
                    with requests.Session() as client:
                        client.trust_env = False
                        response = client.post(args.base_url.rstrip('/') + '/ai/chat',
                            json={'query': 'Top 1 nhẫn dưới 8 triệu', 'top_k': 1}, timeout=45)
                        body = response.json()
                        products = body.get('products', [])
                        recovered = (response.status_code == 200 and body.get('returned_k') == 1 and len(products) == 1
                            and products[0].get('verified_source') == 'business_api')
                        if recovered:
                            product = products[0]
                            current = client.get(args.base_url.rstrip('/') + '/api/products/' + str(product['ProductID']), timeout=5)
                            live = current.json()
                            recovered = (current.status_code == 200 and live['name'] == product['ProductName']
                                and Decimal(str(live['price_vnd'])) == Decimal(str(product['Price']))
                                and live['stock'] == product['Stock'] and live['stock'] > 0)
                            plan['recovered_product_live_price_stock_verified'] = recovered
                    plan['ai_recovered_with_verified_product'] = recovered
                if recovered and args.retrieval_probe:
                    probes = []
                    while time.perf_counter() < deadline:
                        snapshot = retrieval_snapshot(ai_container)
                        probes.append(snapshot)
                        if retrieval_healthy(snapshot):
                            break
                        time.sleep(3)
                    plan['retrieval_recovery_probes'] = probes
                    recovered = bool(probes) and retrieval_healthy(probes[-1])
            except Exception as exc:
                recovered = False
                plan['recovery_error_type'] = type(exc).__name__
            plan.update({'recovered': recovered, 'recovery_seconds': time.perf_counter() - start})
            with args.report.open('x', encoding='utf-8') as handle:
                json.dump(plan, handle, indent=2)
    print(json.dumps(plan))
    return 0 if plan.get('isolation_passed') and plan.get('recovered') else 1


if __name__ == '__main__':
    raise SystemExit(main())
