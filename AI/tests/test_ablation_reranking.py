import unittest
from unittest.mock import Mock

from jewelry_agents.search_service import search
from jewelry_agents.reranking import GraphFeatureReranker


def product(pid):
    return {'ProductID': pid, 'ProductName': 'Nhẫn ' + str(pid), 'CategoryID': 1, 'Category': 'Nhẫn',
            'GemstoneID': 6, 'Gemstone': 'CZ', 'SKU': 'SYNTHETIC' + str(pid), 'Material': 'Bạc 925',
            'Price': '100', 'Stock': 2}


class AblationRerankingTests(unittest.TestCase):
    def search(self, **kwargs):
        return search('nhẫn', 3, catalog=lambda: {i: product(i) for i in range(1, 5)},
                      parse_price=lambda q: {}, **kwargs)

    def test_disabled_sources_are_never_called_and_candidate_pool_is_bounded(self):
        dense, graph = Mock(side_effect=AssertionError('Must not call')), Mock(side_effect=AssertionError('Must not call'))
        result = self.search(dense=dense, graph=graph, sources={'lexical'}, candidate_k=3, diagnostics=True)
        dense.assert_not_called()
        graph.assert_not_called()
        self.assertEqual(result['diagnostics']['source_ranks'], {'lexical': [1, 2, 3]})
        result = self.search(dense=lambda *a, **k: [{'ProductID': 4}], sources={'dense'})
        self.assertEqual([item['ProductID'] for item in result['products']], [4])

    def test_stale_or_unrelated_graph_paths_never_count_as_graph_evidence(self):
        result = self.search(dense=lambda *a, **k: [], graph=lambda *a: [{'ProductID': 1, 'paths': [
            {'relationship': 'HAS_GEMSTONE', 'target_id': 999, 'target_name': 'stale'},
            {'relationship': 'UNKNOWN', 'target_id': 1, 'target_name': 'unknown'}]}])
        item = result['products'][0]
        self.assertEqual(item['graph_paths'], [])
        self.assertEqual(item['retrieval_sources'], ['lexical'])

    def test_experimental_reranker_preserves_ids_and_uses_real_bounded_features(self):
        candidates = [{'ProductID': 1, 'score': .02, 'graph_paths': []},
                      {'ProductID': 2, 'score': .02, 'graph_paths': [{'relationship': 'BELONGS_TO'}]}]
        result = GraphFeatureReranker()(None, candidates)
        self.assertEqual([item['ProductID'] for item in result], [2, 1])
        self.assertEqual(result[0]['rrf_score'], .02)
        self.assertEqual(result[0]['rerank_features']['verified_graph'], .5)
        self.assertTrue(all(0 <= item['score'] <= 1 for item in result))

    def test_reranker_cannot_insert_drop_duplicate_or_nan_product_ids(self):
        for reranker in (lambda q, rows: [], lambda q, rows: [{**rows[0], 'ProductID': 999}],
                         lambda q, rows: [{**item, 'score': float('nan')} for item in rows]):
            with self.subTest(reranker=reranker), self.assertRaises(ValueError):
                self.search(dense=lambda *a, **k: [], reranker=reranker)

    def test_latest_catalog_still_wins_over_reranker_price_fields(self):
        def reranker(query, candidates):
            return [{**item, 'Price': '-1', 'Stock': 999, 'score': 1} for item in candidates]
        result = self.search(dense=lambda *a, **k: [], reranker=reranker)
        self.assertEqual(result['products'][0]['Price'], '100')
        self.assertEqual(result['products'][0]['Stock'], 2)
