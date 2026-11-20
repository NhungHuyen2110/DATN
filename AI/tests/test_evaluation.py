import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lumiere.evaluation import evaluate_ranking


class EvaluationTests(unittest.TestCase):
    def test_known_ranking_metrics(self):
        result = evaluate_ranking([9, 1, 2], {1, 2}, 3, {1, 2, 3})
        self.assertEqual(result["precision_at_k"], 2 / 3)
        self.assertEqual(result["recall_at_k"], 1)
        self.assertEqual(result["mrr"], .5)
        self.assertAlmostEqual(result["ndcg_at_k"], (1 / math.log2(3) + .5) / (1 + 1 / math.log2(3)))
        self.assertEqual(result["hard_filter_violations"], 1)

    def test_short_result_is_penalized_and_no_relevance_is_zero(self):
        result = evaluate_ranking([1], {1, 2, 3}, 3)
        self.assertEqual(result["precision_at_k"], 1 / 3)
        self.assertFalse(result["top_k_fulfilled"])
        self.assertIsNone(result["hard_filter_violations"])
        self.assertEqual(evaluate_ranking([], set(), 3)["ndcg_at_k"], 0)

    def test_duplicate_candidates_cannot_inflate_metrics(self):
        with self.assertRaises(ValueError):
            evaluate_ranking([1, 1], {1}, 3)
        self.assertEqual(evaluate_ranking([1,2,3], {1}, 1)["top_k_overflow"],2)
