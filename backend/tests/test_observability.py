"""Real ASGI calls and Prometheus parser; no network/DB calls."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.observability import install, measure, correlation_headers
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families


class ObservabilityTests(unittest.TestCase):
    def app(self, enabled=True, token='test-only-token'):
        app = FastAPI()
        with patch.dict('os.environ', {'LUMIERE_METRICS_ENABLED': str(enabled).lower(),
                                      'LUMIERE_METRICS_TOKEN': token}):
            install(app, 'test-service')

        @app.get('/products/{product_id}')
        def product(product_id: int):
            with measure('dense'):
                headers = correlation_headers()
            return {'headers': headers}

        @app.get('/failure')
        def failure():
            with measure('graph'):
                raise ConnectionError('private-secret')
        return TestClient(app, raise_server_exceptions=False)

    def test_metrics_are_protected_and_no_dynamic_paths_or_queries_are_exported(self):
        client = self.app()
        self.assertEqual(client.get('/internal/metrics').status_code, 404)
        self.assertEqual(client.get('/internal/metrics', headers={'Authorization': 'Bearer wrong'}).status_code, 404)
        response = client.get('/products/487?reset_token=private-secret', headers={'X-Request-ID': 'unsafe-value'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['headers']['X-Request-ID'], response.headers['x-request-id'])
        text = client.get('/internal/metrics', headers={'Authorization': 'Bearer test-only-token'}).text
        self.assertIn('route="/products/{product_id}"', text)
        self.assertNotIn('487', text.split('route=')[1].split('}')[0])
        self.assertNotIn('private-secret', text)
        self.assertNotIn('unsafe-value', text)
        samples = [sample for family in text_string_to_metric_families(text) for sample in family.samples]
        count = next(sample for sample in samples if sample.name == 'lumiere_http_requests_total')
        self.assertEqual(count.value, 1)

    def test_error_is_counted_without_swallowing_exception_or_exposing_details(self):
        client = self.app()
        response = client.get('/failure')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('private-secret', response.text)
        text = client.get('/internal/metrics', headers={'Authorization': 'Bearer test-only-token'}).text
        self.assertIn('status="500"', text)
        self.assertIn('outcome="error",service="test-service",stage="graph"', text)

    def test_disabled_feature_and_missing_scrape_token_do_not_expose_metrics(self):
        self.assertEqual(self.app(enabled=False).get('/internal/metrics').status_code, 404)
        self.assertEqual(self.app(token='').get('/internal/metrics').status_code, 404)

    def test_unmatched_paths_have_one_metric_label_and_correlation_is_reset(self):
        client = self.app()
        client.get('/unknown-sensitive-path')
        client.get('/another-sensitive-path')
        text = client.get('/internal/metrics', headers={'Authorization': 'Bearer test-only-token'}).text
        self.assertIn('route="unmatched"', text)
        self.assertNotIn('sensitive-path', text)
        self.assertEqual(correlation_headers(), {})
