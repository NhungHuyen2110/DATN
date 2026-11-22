import unittest
from unittest.mock import patch


class InternalDiagnosticsTests(unittest.TestCase):
    def test_internal_endpoint_is_disabled_without_token_and_rejects_wrong_token(self):
        import api
        from fastapi.testclient import TestClient
        client = TestClient(api.app)
        payload = {'query': 'nhẫn', 'top_k': 1}
        with patch.dict('os.environ', {'LUMIERE_AI_DIAGNOSTICS_TOKEN': ''}):
            self.assertEqual(client.post('/internal/retrieval-diagnostics', json=payload).status_code, 404)
        with patch.dict('os.environ', {'LUMIERE_AI_DIAGNOSTICS_TOKEN': 'synthetic-token'}):
            self.assertEqual(client.post('/internal/retrieval-diagnostics', json=payload,
                                         headers={'Authorization': 'Bearer wrong'}).status_code, 404)

    def test_authorized_diagnostics_returns_actual_rank_evidence(self):
        import api
        from fastapi.testclient import TestClient
        from jewelry_agents import retrieval
        import jewelry_agents.business_catalog as catalog
        product = {'ProductID': 1, 'ProductName': 'Synthetic ring', 'SKU': 'SYNTHETIC',
                   'Category': 'Nhẫn', 'CategoryID': 1, 'Material': 'Bạc 925', 'Gemstone': 'CZ',
                   'GemstoneID': 6, 'Price': '100', 'Stock': 1}
        with patch.dict('os.environ', {'LUMIERE_AI_DIAGNOSTICS_TOKEN': 'synthetic-token'}), \
                patch.object(catalog, 'fetch_catalog', return_value={1: product}), \
                patch.object(retrieval, 'search_qdrant', return_value=[{'ProductID': 1}]), \
                patch.object(retrieval, 'graph_search_candidates', return_value=[]), \
                patch.object(retrieval, 'graph_expand_candidates', return_value=[]):
            response = TestClient(api.app).post('/internal/retrieval-diagnostics', json={'query': 'nhẫn'},
                                               headers={'Authorization': 'Bearer synthetic-token'})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'ok')
        self.assertEqual(body['products'][0]['score_type'], 'rrf')
        self.assertGreater(body['products'][0]['score'], 0)
        self.assertEqual(body['diagnostics']['source_ranks']['dense'], [1])
