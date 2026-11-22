import importlib
import unittest
from unittest.mock import patch


class PublicRecommendationTests(unittest.TestCase):
    def fixtures(self):
        return {pid: {'ProductID': pid, 'ProductName': 'Synthetic ' + str(pid), 'CategoryID': 1,
                     'Category': 'Nhẫn', 'MaterialID': 2, 'Material': 'Bạc 925', 'GemstoneID': 6,
                     'Gemstone': 'CZ', 'Price': '100', 'Stock': 1} for pid in range(1, 24)}

    def test_public_can_return_twenty_and_never_source_without_private_history(self):
        from jewelry_agents import public_recommendation as service
        with patch.object(service, 'fetch_catalog', side_effect=lambda: self.fixtures()), \
             patch.object(service.retrieval, 'search_qdrant', side_effect=ConnectionError), \
             patch.object(service.retrieval, 'graph_search_candidates', side_effect=ConnectionError):
            result, degraded = service.recommend_public(1, 20)
        self.assertEqual(len(result), 20)
        self.assertNotIn(1, [item['ProductID'] for item in result])
        self.assertEqual(len(degraded), 2)
        self.assertTrue(all(item['GraphEvidence'] == [] for item in result))

    def test_final_catalog_change_removes_stock_and_invalid_graph_paths(self):
        from jewelry_agents import public_recommendation as service
        initial, latest = self.fixtures(), self.fixtures()
        latest[2]['Stock'] = 0
        latest[3]['MaterialID'] = 99
        graph = [{'ProductID': 3, 'paths': [{'relationship': 'MADE_OF', 'target_id': 2,
                  'source_product_id': 1, 'candidate_product_id': 3}]}]
        with patch.object(service, 'fetch_catalog', side_effect=[initial, latest]), \
             patch.object(service.retrieval, 'search_qdrant', return_value=[]), \
             patch.object(service.retrieval, 'graph_search_candidates', return_value=graph):
            result, _ = service.recommend_public(1, 3)
        self.assertNotIn(2, [item['ProductID'] for item in result])
        self.assertEqual(next(item for item in result if item['ProductID'] == 3)['GraphEvidence'], [])

    def test_both_api_paths_ignore_caller_customer_identity_and_skip_legacy_imports(self):
        from fastapi.testclient import TestClient
        api = importlib.import_module('api')
        fake = [{'ProductID': 2, 'ProductName': 'Synthetic', 'SalePrice': '100', 'Stock': 1}]
        with patch.dict('os.environ', {'LUMIERE_PUBLIC_RECOMMENDATIONS_V2_ENABLED': 'true'}), \
             patch('jewelry_agents.public_recommendation.recommend_public', return_value=(fake, [])) as call, \
             patch.dict('sys.modules', {'hybrid_recommendation': None, 'hybrid_recommendation_v2': None}):
            for path in ('/recommendations', '/recommendations/v2'):
                response = TestClient(api.app).get(path, params={'customer_id': 'OTHER_CUSTOMER', 'product_id': 1, 'number': 4})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()['personalized'])
                self.assertEqual(response.json()['data'], fake)
            self.assertEqual(call.call_args.args, (1, 4))
