import ast
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jewelry_agents.ranking import price_and_stock_valid


class RecommendationContractTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((ROOT / 'hybrid_recommendation_v2.py').read_text(encoding='utf-8-sig'))
        self.namespace = {'price_and_stock_valid': price_and_stock_valid,
                          'normalize_scores': lambda value: value,
                          'get_content_scores': lambda pid: {2: 0.5, 3: 0.5, 4: 0.8},
                          'get_qdrant_scores': lambda pid: {}, 'get_collaborative_scores': lambda pid: {},
                          'NEO4J_URI': 'fake', 'NEO4J_USERNAME': 'fake', 'NEO4J_PASSWORD': 'fake'}
        class Graph:
            def __init__(self, *args):
                pass
            def recommend(self, *args, **kwargs):
                return [{'ProductID': 2, 'GraphScore': 0.5, 'paths': [{'relationship': 'MADE_OF', 'attribute_id': 1,
                        'source_product_id': 1, 'candidate_product_id': 2}]}]
            def close(self):
                pass
        self.namespace['GraphRecommender'] = Graph
        self.namespace['fetch_catalog'] = lambda: {
            pid: {'ProductID': pid, 'ProductName': 'Live name', 'Category': 'Nhẫn', 'Material': 'Bạc 925',
                  'Gemstone': 'CZ', 'CategoryID': 1, 'MaterialID': 1, 'GemstoneID': 6,
                  'Price': '7000000.01', 'Stock': 0 if pid == 4 else 1}
            for pid in (1, 2, 3, 4)}
        exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'recommend_v2'],
                                type_ignores=[]), '<recommendation>', 'exec'), self.namespace)

    def test_live_fields_stock_and_actual_graph_evidence(self):
        result = self.namespace['recommend_v2']('GUEST', 1, top_k=3)
        self.assertEqual([p['ProductID'] for p in result], [2, 3])
        self.assertEqual(result[0]['SalePrice'], '7000000.01')
        self.assertEqual(result[0]['ProductName'], 'Live name')
        self.assertEqual(result[0]['GraphEvidence'], [{'relationship': 'MADE_OF', 'attribute_id': 1,
                         'source_product_id': 1, 'candidate_product_id': 2}])
        self.assertEqual(result[1]['GraphEvidence'], [])

    def test_requested_topk_is_enforced(self):
        self.assertEqual(len(self.namespace['recommend_v2']('GUEST', 1, top_k=1)), 1)
        with self.assertRaises(ValueError):
            self.namespace['recommend_v2']('GUEST', 1, top_k=0)

    def test_stale_graph_fact_is_not_returned_as_explanation(self):
        original = self.namespace['fetch_catalog']
        def changed_catalog():
            products = original()
            products[2]['MaterialID'] = 2
            return products
        self.namespace['fetch_catalog'] = changed_catalog
        result = self.namespace['recommend_v2']('GUEST', 1, top_k=3)
        self.assertEqual(next(p for p in result if p['ProductID'] == 2)['GraphEvidence'], [])


if __name__ == '__main__':
    unittest.main()
