import threading
import time
import unittest
from shared.retrieval_limits import SourceGate, SourceUnavailable


class RetrievalLimitTests(unittest.TestCase):
    def test_startup_budget_does_not_change_request_budget_or_allow_queueing(self):
        release, entered = threading.Event(), threading.Event()
        gate = SourceGate('test-startup', timeout=.01, cooldown=0)
        results = []
        def startup():
            entered.set()
            release.wait(1)
            return 'ready'
        worker = threading.Thread(target=lambda: results.append(gate.call_with_timeout(1, startup)))
        try:
            worker.start()
            self.assertTrue(entered.wait(1))
            with self.assertRaises(SourceUnavailable):
                gate.call(lambda: 'must not queue')
            time.sleep(.03)  # startup may exceed the ordinary request budget
            release.set()
            worker.join(1)
            self.assertEqual(results, ['ready'])
            self.assertEqual(gate.timeout, .01)
            self.assertEqual(gate.call(lambda: 'fresh'), 'fresh')
        finally:
            release.set()
            worker.join(1)
            gate.close()

    def test_failed_source_is_not_retried_until_cooldown_then_can_recover(self):
        now, calls = [100], []
        gate = SourceGate('test-cooldown', clock=lambda: now[0], cooldown=10)
        def operation():
            calls.append(1)
            raise ConnectionError('Synthetic source failure')
        try:
            with self.assertRaises(ConnectionError):
                gate.call(operation)
            with self.assertRaises(SourceUnavailable):
                gate.call(operation)
            self.assertEqual(len(calls), 1)
            now[0] = 111
            self.assertEqual(gate.call(lambda: 'recovered'), 'recovered')
        finally:
            gate.close()

    def test_timeout_does_not_enqueue_unbounded_work_or_reuse_late_results(self):
        release, finished = threading.Event(), threading.Event()
        now, calls = [100], []
        gate = SourceGate('test-timeout', timeout=.03, cooldown=1, clock=lambda: now[0])
        def slow():
            calls.append(1)
            release.wait(2)
            finished.set()
            return 'stale previous-query result'
        try:
            with self.assertRaises(SourceUnavailable):
                gate.call(slow)
            now[0] = 102
            with self.assertRaises(SourceUnavailable):
                gate.call(slow)
            self.assertEqual(len(calls), 1)
            release.set()
            self.assertTrue(finished.wait(1))
            deadline = time.monotonic() + 1
            while True:
                try:
                    result = gate.call(lambda: 'fresh current-query result')
                    break
                except SourceUnavailable:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(.001)
            self.assertEqual(result, 'fresh current-query result')
        finally:
            release.set()
            gate.close()

    def test_closed_gate_cannot_start_new_tasks(self):
        gate = SourceGate('test-shutdown')
        gate.close()
        with self.assertRaises(SourceUnavailable):
            gate.call(lambda: 'not called')
