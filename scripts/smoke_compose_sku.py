"""Recreate only the isolated AI service after the SKU fix; independently verify returned business facts."""
import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--ai-build-report', type=Path, default=ROOT / 'docs/docker-ai-sku-image-20261122.json')
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists')
    core = json.loads((ROOT / 'docs/compose-core-runtime-20261122.json').read_text())
    built = json.loads(args.ai_build_report.read_text())
    if core.get('project') != 'lumiere-rebuild-test' or core.get('production_accessed') is not False or not built.get('successful'):
        parser.error('Verified isolated fixture and new AI image required')
    log = ROOT / '.local-tmp' / (args.report.stem + '-recreate.log')
    with log.open('xb') as output:
        command = subprocess.run(['docker', 'compose', '--env-file', '.env.example', '-f', 'compose.yaml',
            'up', '-d', '--no-deps', 'ai-api'], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if command.returncode:
        raise RuntimeError('AI test recreate failed; see ignored log')
    import requests
    samples = []
    with requests.Session() as client:
        client.trust_env = False
        base = 'http://127.0.0.1:18080'
        for attempt in range(30):
            try:
                if client.get(base + '/ai/health/live', timeout=3).status_code == 200:
                    break
            except requests.RequestException:
                pass
            if attempt == 29:
                raise RuntimeError('New AI container not live')
            time.sleep(1)
        for query, count, identity in [('Top 1 SYNTHETIC5', 1, 5), ('Top 3 nhẫn dưới 8 triệu', 3, None),
                                      ('Top 3 nhan duoi 8 trieu', 3, None)]:
            response = client.post(base + '/ai/chat', json={'query': query}, timeout=60)
            assert response.status_code == 200
            result = response.json()
            assert result['returned_k'] == count and len(result['products']) == count
            if identity is not None:
                assert result['products'][0]['ProductID'] == identity
            for item in result['products']:
                current = client.get(base + '/api/products/' + str(item['ProductID']), timeout=5)
                assert current.status_code == 200
                current = current.json()
                assert item['ProductName'] == current['name'] and item['Stock'] == current['stock'] > 0
                assert Decimal(str(item['Price'])) == Decimal(str(current['price_vnd']))
            samples.append({'query': query, 'product_ids': [item['ProductID'] for item in result['products']],
                            'status': result['status'], 'live_fields_independently_verified': True})
    report = {'successful': True, 'ai_image_id': built['image_id'], 'samples': samples,
              'scope': 'real Docker proxy/AI/Business/PostgreSQL, 5 synthetic fixture products; not quality benchmark',
              'production_accessed': False}
    with args.report.open('x', encoding='utf-8') as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
    print(json.dumps({'successful': True, 'queries_verified': len(samples), 'ai_image_id': built['image_id']}))


if __name__ == '__main__':
    main()
