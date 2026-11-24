import unittest
from test_search_service import product, parse_price
from jewelry_agents.search_service import search


class DenseAnchorExpansionTests(unittest.TestCase):
    def test_dense_anchors_use_one_traversal_not_an_extra_taxonomy_lookup(self):
        live={i:product(i) for i in range(1,5)}
        def unexpected_lookup(*args):self.fail('Dense anchors must go straight to expansion')
        result=search('jewelry',3,dense=lambda *a,**k:[{'ProductID':2}],catalog=lambda:live,
                      parse_price=parse_price,graph=unexpected_lookup,
                      graph_expander=lambda *a,**k:[{'ProductID':3,'paths':[self.path()]}],diagnostics=True)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['diagnostics']['source_ranks']['graph'],[3])

    def run_search(self, expander, catalog=None, dense=None):
        live = {i: product(i) for i in range(1, 5)}
        return search('jewelry', 3, dense=dense or (lambda *a, **k: [{'ProductID': 2}]),
                      catalog=catalog or (lambda: live), parse_price=parse_price,
                      graph=lambda *a: [], graph_expander=expander, diagnostics=True)

    def path(self, source=2, target=3, entity=6):
        return {'relationship': 'HAS_GEMSTONE', 'target_id': entity,
                'source_product_id': source, 'candidate_product_id': target}

    def test_dense_ids_anchor_expansion_and_real_paths_survive(self):
        calls = []
        def expand(ids, top_k,eligible_ids):
            self.assertEqual(set(eligible_ids),{1,2,3,4})
            calls.append((ids, top_k))
            return [{'ProductID': 3, 'paths': [self.path()]}]
        result = self.run_search(expand)
        self.assertEqual(calls, [([2], 35)])
        self.assertEqual(result['diagnostics']['source_ranks']['graph'], [3])
        candidate = next(p for p in result['products'] if p['ProductID'] == 3)
        self.assertEqual(candidate['graph_paths'][0]['source_product_id'], 2)
        self.assertEqual(candidate['graph_paths'][0]['target_name'], 'CZ')

    def test_unknown_anchor_wrong_edge_and_duplicate_candidates_are_rejected(self):
        result = self.run_search(lambda *a, **k: [
            {'ProductID': 1, 'paths': [self.path(source=999, target=1)]},
            {'ProductID': 3, 'paths': [self.path(entity=5)]},
            {'ProductID': 4, 'paths': [self.path(target=4)]},
            {'ProductID': 4, 'paths': [self.path(target=4)]}])
        self.assertEqual(result['diagnostics']['source_ranks']['graph'], [4])
        self.assertEqual(len([p for p in result['products'] if p['ProductID'] == 4]), 1)

    def test_dense_outage_never_fabricates_anchors(self):
        def dense(*a, **k):
            raise ConnectionError('synthetic outage')
        def expand(*a, **k):
            self.fail('No graph expansion without dense anchors')
        self.assertEqual(self.run_search(expand, dense=dense)['status'], 'degraded')

    def test_graph_outage_preserves_dense_results(self):
        def expand(*a, **k):
            raise ConnectionError('private synthetic detail')
        result = self.run_search(expand)
        self.assertEqual(result['products'][0]['ProductID'], 2)
        self.assertEqual(result['status'], 'degraded')
        self.assertNotIn('private synthetic detail', str(result))

    def test_anchor_attribute_changed_before_response_cannot_be_explained_as_shared(self):
        before = {i: product(i) for i in range(1, 5)}
        after = {i: dict(p) for i, p in before.items()}
        after[2]['GemstoneID'] = 5
        states = iter([before, after])
        result = self.run_search(lambda *a, **k: [{'ProductID': 3, 'paths': [self.path()]}],
                                 catalog=lambda: next(states))
        self.assertEqual(next(p for p in result['products'] if p['ProductID'] == 3)['graph_paths'], [])
