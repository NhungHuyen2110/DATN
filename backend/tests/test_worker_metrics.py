from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from prometheus_client import generate_latest
from prometheus_client.parser import text_string_to_metric_families
from shared.worker_metrics import WorkerMetrics


class WorkerMetricsTests(unittest.TestCase):
    def test_event_latency_counts_only_completed_generations(self):
        metrics = WorkerMetrics('synthetic')
        for completed, lag in [(False, None), (False, 12), (True, 5)]:
            metrics.record({'claimed': True, 'delivered': True, 'acknowledged': True,
                            'completed': completed, 'event_to_index_seconds': lag}, .1)
        text = generate_latest(metrics.registry).decode()
        self.assertIn('lumiere_sync_event_to_index_seconds_count 1.0', text)
        self.assertIn('lumiere_sync_event_to_index_seconds_sum 5.0', text)

    def test_queue_snapshot_and_acknowledged_outcomes_use_real_numbers_without_ids(self):
        metrics = WorkerMetrics('synthetic')
        metrics.update({'enabled': True, 'states': {'pending': 3, 'dead': 1},
                        'oldest_pending_seconds': 27, 'last_success': '2026-11-21T13:00:00+00:00'})
        metrics.record({'claimed': True, 'delivered': False, 'acknowledged': False}, .25)
        text = generate_latest(metrics.registry).decode()
        samples = [sample for family in text_string_to_metric_families(text) for sample in family.samples]
        pending = next(sample for sample in samples if sample.name == 'lumiere_sync_jobs' and sample.labels['state'] == 'pending')
        self.assertEqual(pending.value, 3)
        self.assertIn('lumiere_sync_oldest_pending_seconds 27.0', text)
        self.assertIn('lumiere_sync_lease_lost_total 1.0', text)
        self.assertNotIn('product_id', text)

    def test_disabled_sync_does_not_open_database_and_invalid_token_is_rejected(self):
        metrics = WorkerMetrics('synthetic')
        factory = Mock()
        with patch.dict('os.environ', {'PRODUCT_INDEX_SYNC_ENABLED': 'false'}):
            metrics.refresh(factory)
        factory.assert_not_called()
        self.assertFalse(metrics.authorized('Bearer wrong'))
        self.assertTrue(metrics.authorized('Bearer synthetic'))
        with self.assertRaises(ValueError):
            WorkerMetrics('')
