"""Actual chat endpoint and search stages with injected services, no live I/O."""
import unittest
from unittest.mock import patch


class ObservedChatTests(unittest.TestCase):
    def test_degraded_chat_emits_stage_error_and_verified_products_without_query_labels(self):
        import api
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from shared.observability import install
        import rag.rag_service as rag
        app = FastAPI()
        app.include_router(api.app.router)
        with patch.dict('os.environ', {'LUMIERE_METRICS_ENABLED': 'true', 'LUMIERE_METRICS_TOKEN': 'synthetic'}):
            install(app, 'ai-api')
        product = {'ProductID': 1, 'ProductName': 'Synthetic ring', 'Category': 'Nhẫn', 'CategoryID': 1,
                   'Material': 'Bạc 925', 'Gemstone': 'CZ', 'GemstoneID': 6, 'Collection': 'Synthetic',
                   'SKU': 'SYNTHETIC1', 'Price': '100', 'Stock': 1}
        with patch.object(rag, 'fetch_catalog', return_value={1: product}), \
                patch.object(rag, 'search_qdrant', side_effect=ConnectionError('synthetic-private-value')), \
                patch.object(rag, 'graph_search_candidates', return_value=[]):
            client = TestClient(app)
            response = client.post('/chat', json={'query': 'nhẫn', 'top_k': 1})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], 'degraded')
            self.assertEqual(response.json()['products'][0]['ProductID'], 1)
            metrics = client.get('/internal/metrics', headers={'Authorization': 'Bearer synthetic'}).text
        self.assertIn('outcome="error",service="ai-api",stage="dense"', metrics)
        self.assertIn('route="/chat"', metrics)
        self.assertNotIn('synthetic-private-value', metrics)
        self.assertNotIn('Synthetic ring', metrics)
