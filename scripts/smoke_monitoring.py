"""Export real metrics from synthetic ASGI traffic; no DB/network/model calls."""
import argparse
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from prometheus_client.parser import text_string_to_metric_families
    from shared.observability import install, measure
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--metrics', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.metrics.exists():
        parser.error('Evidence output already exists')
    app = FastAPI()
    with patch.dict(os.environ, {'LUMIERE_METRICS_ENABLED': 'true', 'LUMIERE_METRICS_TOKEN': 'synthetic-test-token'}):
        install(app, 'synthetic-asgi-smoke')
    @app.get('/probe/{identity}')
    def probe(identity: int):
        with measure('parse'):
            pass
        return {'ok': True}
    @app.get('/failure')
    def fail():
        with measure('dense'):
            raise ConnectionError('synthetic-private-value')
    client = TestClient(app, raise_server_exceptions=False)
    for index in range(20):
        assert client.get(f'/probe/{index}?query=synthetic-private-value').status_code == 200
    assert client.get('/failure').status_code == 500
    metrics = client.get('/internal/metrics', headers={'Authorization': 'Bearer synthetic-test-token'})
    assert metrics.status_code == 200 and 'synthetic-private-value' not in metrics.text
    families = list(text_string_to_metric_families(metrics.text))
    samples = [sample for family in families for sample in family.samples]
    counts = [sample for sample in samples if sample.name == 'lumiere_http_requests_total']
    assert sum(sample.value for sample in counts) == 21
    with args.metrics.open('x', encoding='utf-8') as handle:
        handle.write(metrics.text)
    report = {'successful': True, 'requests': 21, 'http_200': 20, 'http_500': 1,
              'traffic': 'synthetic actual ASGI requests', 'exporter': 'actual prometheus-client exposition',
              'scraped_by_prometheus_server': False, 'grafana_screenshot': False,
              'private_query_or_exception_in_export': False}
    with args.report.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
