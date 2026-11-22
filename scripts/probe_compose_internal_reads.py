"""Read-only timing probe inside the verified synthetic AI container, without browser/host forwarding."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = r'''
import json, time, requests
samples = []
with requests.Session() as client:
    client.trust_env = False
    for turn in range(3):
        for name, method, url, payload in (
            ('business_catalog', 'GET', 'http://business-api:8001/products?page=1&page_size=100', None),
            ('ai_sku', 'POST', 'http://127.0.0.1:8000/chat', {'query': 'Top 1 SYNTHETIC5'}),
            ('ai_public_recommendations', 'GET', 'http://127.0.0.1:8000/recommendations/v2?customer_id=GUEST&product_id=1&number=4', None)):
            start = time.monotonic()
            entry = {'turn': turn + 1, 'source': name}
            try:
                response = client.request(method, url, json=payload, timeout=(3, 20))
                data = response.json()
                entry['http_status'] = response.status_code
                entry['contract_verified'] = response.status_code == 200 and (
                    (name == 'business_catalog' and data.get('total') == 5) or
                    (name == 'ai_sku' and data.get('returned_k') == 1 and
                     data.get('products', [{}])[0].get('ProductID') == 5) or
                    (name == 'ai_public_recommendations' and data.get('number') == 4 and data.get('personalized') is False))
            except Exception as error:
                entry.update(contract_verified=False, error_type=type(error).__name__)
            entry['seconds'] = round(time.monotonic() - start, 4)
            samples.append(entry)
print(json.dumps({'successful': all(item['contract_verified'] for item in samples), 'samples': samples,
                  'scope': 'read-only inside AI container; single lab, not SLA or quality benchmark',
                  'production_accessed': False}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Choose a new report')
    baseline = json.loads((ROOT / 'docs/compose-core-runtime-20261122.json').read_text())
    if baseline.get('project') != 'lumiere-rebuild-test' or not baseline.get('successful') or baseline.get('production_accessed') is not False:
        parser.error('Verified synthetic core required')
    def execute(command, timeout):
        try:
            return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True, timeout=timeout)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
            failure = {'successful': False, 'error_type': type(error).__name__,
                       'phase': 'Docker CLI/control plane; API probe not completed',
                       'timeout_seconds': timeout, 'production_accessed': False}
            with args.report.open('x', encoding='utf-8') as output:
                json.dump(failure, output, indent=2)
            print(json.dumps(failure))
            raise SystemExit(1) from None
    prefix = ['docker', 'compose', '--env-file', '.env.example', '-f', 'compose.yaml']
    cid = execute(prefix + ['ps', '-q', 'ai-api'], 20).stdout.strip()
    container = json.loads(execute(['docker', 'inspect', cid], 20).stdout)[0]
    labels = container['Config']['Labels']
    if labels.get('com.docker.compose.project') != 'lumiere-rebuild-test' or labels.get('com.docker.compose.service') != 'ai-api':
        parser.error('Wrong target')
    result = execute(prefix + ['exec', '-T', 'ai-api', 'python', '-B', '-c', PAYLOAD], 240)
    report = json.loads(result.stdout)
    report['ai_image_id'] = container['Image']
    with args.report.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
    print(json.dumps(report))
    return 0 if report['successful'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
