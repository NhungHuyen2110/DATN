from contextlib import redirect_stderr
from io import StringIO
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
from scripts import fault_injection


class FaultRetrievalProbeTests(unittest.TestCase):
    def test_unhealthy_baseline_is_recorded_without_stopping_any_container(self):
        def docker(*args):
            if args[0] == 'ps':
                return 'ai-id' if any('service=ai-api' in arg for arg in args) else 'qdrant-id'
            if args[0] == 'inspect':
                service = 'ai-api' if args[1] == 'ai-id' else 'qdrant'
                return json.dumps([{'Config': {'Labels': {'com.docker.compose.project': fault_injection.PROJECT,
                    'com.docker.compose.service': service}}, 'State': {'Running': True}}])
            self.fail('No stop/start is allowed with unhealthy retrieval')
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'baseline.json'
            arguments = ['fault_injection', '--service', 'qdrant', '--apply', '--confirm-isolated',
                         '--retrieval-probe', '--baseline-timeout', '1', '--report', str(report)]
            with patch('sys.argv', arguments), patch.object(fault_injection, 'docker', side_effect=docker), \
                    patch.object(fault_injection, 'probe', return_value=200), \
                    patch.object(fault_injection, 'retrieval_snapshot', return_value={'status': 'degraded'}), \
                    patch.object(fault_injection.time, 'perf_counter', side_effect=[0, 0, 2]), \
                    patch.object(fault_injection.time, 'sleep'), patch('builtins.print'):
                self.assertEqual(fault_injection.main(), 1)
            saved = json.loads(report.read_text())
            self.assertFalse(saved['applied'])
            self.assertEqual(saved['fault_not_started'], 'retrieval_baseline_unavailable')

    def test_recovery_requires_both_sources_live_filters_and_all_three_products(self):
        healthy = {'http': 200, 'status': 'ok', 'dense_candidates': 19,
                   'graph_candidates': 19, 'products': 3, 'live_filters_valid': True}
        self.assertTrue(fault_injection.retrieval_healthy(healthy))
        for change in ({'http': 503}, {'status': 'degraded'}, {'dense_candidates': 0},
                       {'graph_candidates': 0}, {'products': 0}, {'live_filters_valid': False}):
            self.assertFalse(fault_injection.retrieval_healthy({**healthy, **change}))

    def test_probe_errors_do_not_echo_private_subprocess_output(self):
        with patch.object(fault_injection.subprocess, 'run', return_value=Mock(
                returncode=1, stdout='synthetic-private-canary', stderr='synthetic-private-canary')):
            with self.assertRaises(RuntimeError) as caught:
                fault_injection.retrieval_snapshot('synthetic-container-id')
        self.assertNotIn('synthetic-private-canary', str(caught.exception))

    def test_incompatible_fault_targets_and_unbounded_recovery_are_refused_before_docker(self):
        for arguments in (['--service', 'ai-api', '--apply', '--retrieval-probe'],
                          ['--service', 'neo4j', '--retrieval-probe'],
                          ['--service', 'neo4j', '--recovery-timeout', '301']):
            with patch('sys.argv', ['fault_injection', *arguments]), \
                    patch.object(fault_injection, 'docker') as docker, redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    fault_injection.main()
                self.assertEqual(caught.exception.code, 2)
                docker.assert_not_called()
