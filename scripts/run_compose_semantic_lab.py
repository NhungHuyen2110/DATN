"""Enable graph/vector/worker for the verified five-product synthetic Compose demo after backup.

Leaves the demo running. Preserves prior rows/volumes and never touches legacy databases.
Requires the pinned cached model and independently built worker image.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ['docker', 'compose', '--env-file', '.env.example', '-f', 'compose.yaml', '-f', 'compose.demo.yaml']
VERIFY = r'''
import json, os, sys, time, requests
sys.path.insert(0, '/srv')
from decimal import Decimal
from jewelry_agents import retrieval
with requests.Session() as client:
    client.trust_env = False
    headers = {'Authorization': 'Bearer ' + os.environ['LUMIERE_AI_DIAGNOSTICS_TOKEN']}
    for attempt in range(12):
        try:
            response = client.post('http://127.0.0.1:8000/internal/retrieval-diagnostics', headers=headers,
                                   json={'query':'Top 3 nhẫn dưới 8 triệu'}, timeout=15)
            result = response.json()
            products = result.get('products', [])
            if response.status_code == 200 and len(products) == 3 and all(
                    {'lexical','dense','graph'} <= set(item.get('retrieval_sources', [])) for item in products):
                break
        except (requests.RequestException, ValueError):
            pass  # Readiness may be transient while the cached model warms; facts below never bypass validation.
        time.sleep(3)
    else:
        raise RuntimeError('Three-source retrieval not ready')
    for item in products:
        live = client.get(os.environ['BUSINESS_API_URL'] + '/products/' + str(item['ProductID']), timeout=5)
        live.raise_for_status()
        live = live.json()
        assert item['ProductName'] == live['name'] and item['Stock'] == live['stock'] > 0
        assert Decimal(str(item['Price'])) == Decimal(str(live['price_vnd']))
        assert item['graph_paths']
    collection = client.get(os.environ['QDRANT_URL'] + '/collections/' + os.environ['QDRANT_COLLECTION'], timeout=5)
    collection.raise_for_status()
    info = collection.json()['result']
    assert info['points_count'] == 5 and info['config']['params']['vectors']['size'] == 384
    driver = retrieval.get_graph_driver()
    try:
        with driver.session() as session:
            nodes = session.run('MATCH (p:Product {projection_owner:$owner}) RETURN count(p) AS n', owner='lumiere-products-v1').single()['n']
            edges = session.run('MATCH (:Product {projection_owner:$owner})-[r]->() RETURN count(r) AS n', owner='lumiere-products-v1').single()['n']
        assert nodes == 5 and edges == 25
    finally:
        driver.close()
    print(json.dumps({'successful':True, 'sources':['lexical','dense','graph'], 'returned_ids':[p['ProductID'] for p in products],
        'live_price_stock_verified':True, 'verified_graph_paths':True, 'graph_products':nodes, 'graph_edges':edges,
        'qdrant_points':info['points_count'], 'vector_dimension':384,
        'model_revision':os.environ['EMBEDDING_REVISION'], 'readiness_attempts':attempt+1, 'quality_benchmark':False}))
'''
STATUS = '''import json
from app.core.database import SessionLocal
from app.services.product_index_jobs import sync_status
with SessionLocal() as db:
    print(json.dumps(sync_status(db)))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Choose a new report')
    folder = ROOT / '.local-tmp' / args.report.stem
    folder.mkdir(exist_ok=False)
    recovery = ROOT / '.local-tmp/recovery/compose-demo-20261122'
    if recovery.exists():
        parser.error('Preserve the existing recovery directory; no automatic overwrite')
    result = {'successful': False, 'project':'lumiere-rebuild-test', 'production_accessed':False,
              'scope':'5 synthetic products in actual Compose; real pinned model; not quality benchmark',
              'artifacts':str(folder.relative_to(ROOT))}
    number = 0
    def run(command, timeout=60, content=None):
        nonlocal number
        number += 1
        completed = subprocess.run(command, cwd=ROOT, input=content, capture_output=True, timeout=timeout)
        (folder / (str(number) + '.log')).write_bytes(completed.stdout + completed.stderr)
        if completed.returncode:
            raise RuntimeError('Lab command failed; see artifact ' + str(number))
        return completed.stdout
    try:
        baseline = json.loads((ROOT / 'docs/compose-demo-full-browser-r2-20261122.json').read_text())
        built = json.loads((ROOT / 'docs/docker-worker-cached-image-20261122.json').read_text())
        if not baseline['successful'] or not built['successful']:
            raise ValueError('Passing core browser and actual worker build required')
        user = None
        for service in ('postgres', 'business-api'):
            cid = run(COMPOSE + ['ps', '-q', service]).decode().strip()
            target = json.loads(run(['docker', 'inspect', cid]))[0]
            labels = target['Config']['Labels']
            env = dict(item.split('=', 1) for item in target['Config']['Env'] if '=' in item)
            if (labels.get('com.docker.compose.project') != 'lumiere-rebuild-test' or
                labels.get('com.docker.compose.service') != service or env.get('POSTGRES_DB') != 'lumiere_test_rebuild'):
                raise ValueError('Wrong project/database')
            if service == 'postgres':
                user = env['POSTGRES_USER']
        catalog = json.loads(run(COMPOSE + ['exec', '-T', 'ai-api', 'python', '-B', '-c',
            "import requests,json; r=requests.get('http://business-api:8001/products?page_size=100',timeout=5); r.raise_for_status(); print(json.dumps(r.json()))"]))
        if catalog['total'] != 5 or {p['sku'] for p in catalog['items']} != {'SYNTHETIC'+str(i) for i in range(1,6)}:
            raise ValueError('Five-product synthetic catalog required')
        backup = run(COMPOSE + ['exec', '-T', 'postgres', 'pg_dump', '-U', user, '-d', 'lumiere_test_rebuild', '-Fc'])
        if not backup.startswith(b'PGDMP'):
            raise ValueError('Invalid custom backup')
        recovery.mkdir(parents=True, exist_ok=False)
        (recovery / 'before-semantic.dump').write_bytes(backup)
        record = {'version':1, 'environment':'test', 'database_name':'lumiere_test_rebuild', 'database_host':'postgres',
            'database_port':5432, 'format':'pg_dump_custom', 'backup_file':'before-semantic.dump',
            'backup_sha256':hashlib.sha256(backup).hexdigest()}
        (recovery / 'backup-reference.json').write_text(json.dumps(record), encoding='utf-8')
        result['backup_sha256'] = record['backup_sha256']
        run(COMPOSE + ['up', '-d', '--no-deps', 'neo4j', 'qdrant'], timeout=180)
        for _ in range(60):
            cid = run(COMPOSE + ['ps', '-q', 'neo4j']).decode().strip()
            state = json.loads(run(['docker', 'inspect', '--format', '{{json .State}}', cid]))
            if state.get('Health', {}).get('Status') == 'healthy':
                break
            time.sleep(2)
        else:
            raise RuntimeError('Neo4j did not become healthy')
        run(COMPOSE + ['--profile', 'sync', 'up', '-d', '--no-deps', 'business-api', 'index-worker'], timeout=180)
        for _ in range(80):
            status = json.loads(run(COMPOSE + ['exec', '-T', 'business-api', 'python', '-B', '-c', STATUS]))
            if status.get('enabled') and status.get('states') == {'done':5}:
                result['sync_status'] = status
                break
            time.sleep(3)
        else:
            raise RuntimeError('Five projection jobs were not delivered')
        result['retrieval'] = json.loads(run(COMPOSE + ['exec', '-T', 'ai-api', 'python', '-B', '-c', VERIFY], timeout=300))
        result['successful'] = result['retrieval']['successful']
        result['test_services_left_running'] = True
    except Exception as error:
        result['error_type'] = type(error).__name__
        result['error_summary'] = str(error) if isinstance(error, (ValueError, RuntimeError)) else 'See ignored artifacts'
    result['completed_utc'] = datetime.now(timezone.utc).isoformat()
    with args.report.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
    print(json.dumps(result))
    return 0 if result['successful'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
