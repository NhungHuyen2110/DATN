from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation.scoring import ranking_metrics, evaluate


class EvaluationScoringTests(unittest.TestCase):
    def test_hand_calculated_precision_recall_mrr_and_ideal_ndcg(self):
        metrics = ranking_metrics([9, 2, 1], {1: 1, 2: 1, 3: 1}, 3)
        self.assertAlmostEqual(metrics['precision_at_k'], 2 / 3)
        self.assertAlmostEqual(metrics['recall_at_k'], 2 / 3)
        self.assertEqual(metrics['mrr'], .5)
        self.assertEqual(ranking_metrics([1, 2, 3], {1: 3, 2: 2, 3: 1})['ndcg_at_k'], 1)

    def test_short_result_uses_requested_k_denominator(self):
        self.assertEqual(ranking_metrics([1], {1: 1}, 3)['precision_at_k'], 1 / 3)
        with self.assertRaises(ValueError):
            ranking_metrics([1, 1], {1: 1})

    def test_unreviewed_labels_and_missing_predictions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Human review'):
            evaluate([{'query_id': 'one', 'reviewed': False}], [])
        label = {'query_id': 'one', 'reviewed': True, 'reviewer': 'synthetic-test-reviewer',
                 'dataset_sha256': 'synthetic-fixture', 'split': 'test', 'relevance': {'1': 1}}
        with self.assertRaisesRegex(ValueError, 'coverage'):
            evaluate([label], [])
        with self.assertRaisesRegex(ValueError, 'dataset differ'):
            evaluate([label], [{'query_id': 'one', 'dataset_sha256': 'other'}])
