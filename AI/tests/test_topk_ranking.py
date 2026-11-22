from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jewelry_agents.ranking import reciprocal_rank_fusion, finalize_topk


class RankingTests(unittest.TestCase):
    def test_rrf_deduplicates_each_source_and_reinforces_multiple_sources(self):
        result = reciprocal_rank_fusion({'dense': [2, 2, 1], 'lexical': [1, 3]})
        self.assertEqual(result[0][0], 1)
        self.assertAlmostEqual(next(r[1] for r in result if r[0] == 2), 1 / 61)

    def test_live_price_stock_override_stale_snapshot(self):
        candidates = [{'ProductID': 1, 'score': 0.9, 'Price': 1, 'Stock': 99},
                      {'ProductID': 2, 'score': 0.8}, {'ProductID': 3, 'score': 0.7}]
        live = {1: {'ProductID': 1, 'Price': 9_000_000, 'Stock': 1},
                2: {'ProductID': 2, 'Price': 7_000_000, 'Stock': 0},
                3: {'ProductID': 3, 'Price': 6_000_000, 'Stock': 1}}
        result = finalize_topk(candidates, 3, {'max_price': 8_000_000}, live)
        self.assertEqual([p['ProductID'] for p in result], [3])
        self.assertEqual(result[0]['Price'], 6_000_000)

    def test_unknown_price_and_missing_live_product_fail_closed(self):
        result = finalize_topk([{'ProductID': 1, 'score': 1}, {'ProductID': 2, 'score': 0.9}], 3, {},
                               {1: {'Price': None, 'Stock': 1}})
        self.assertEqual(result, [])

    def test_exclusive_budget_and_deterministic_topk(self):
        candidates = [{'ProductID': i, 'score': 0.8} for i in (3, 1, 2, 1)]
        live = {i: {'ProductID': i, 'Price': 8_000_000 if i == 1 else 7_000_000, 'Stock': 1} for i in (1, 2, 3)}
        self.assertEqual([r['ProductID'] for r in finalize_topk(candidates, 1,
                         {'max_price': 8_000_000, 'max_exclusive': True}, live)], [2])


if __name__ == '__main__':
    unittest.main()
