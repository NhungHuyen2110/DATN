import importlib.util
from pathlib import Path
import unittest
import json
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('fault_script', Path(__file__).resolve().parents[2] / 'scripts/fault_injection.py')
fault = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fault)


class FaultInjectionGuardTests(unittest.TestCase):
    def test_stop_timeout_still_attempts_recovery_and_records_recovery_failure(self):
        details = {'Config': {'Labels': {'com.docker.compose.project': fault.PROJECT,
                                         'com.docker.compose.service': 'ai-api'}}, 'State': {'Running': True}}
        called = []
        def command(*arguments):
            called.append(arguments)
            if arguments[0] == 'ps':
                return 'synthetic-container'
            if arguments[0] == 'inspect':
                return json.dumps([details])
            raise RuntimeError('synthetic-secret-error')
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'report.json'
            with patch('sys.argv', ['fault', '--service', 'ai-api', '--apply', '--confirm-isolated', '--report', str(report)]), \
                    patch.object(fault, 'docker', side_effect=command), patch.object(fault, 'probe', return_value=200):
                self.assertEqual(fault.main(), 1)
            evidence = json.loads(report.read_text())
            self.assertFalse(evidence['recovered'])
            self.assertEqual(evidence['recovery_error_type'], 'RuntimeError')
            self.assertNotIn('synthetic-secret', report.read_text())
            self.assertIn(('start', 'synthetic-container'), called)

    def test_external_or_other_local_ports_are_rejected(self):
        fault.validate_base('http://127.0.0.1:18080')
        for value in ('https://example.com', 'http://127.0.0.1:8001', 'http://localhost:18080/production',
                      'http://user:password@localhost:18080', 'http://localhost:18080?target=prod'):
            with self.assertRaises(ValueError):
                fault.validate_base(value)

    def test_existing_production_or_initially_stopped_containers_are_rejected(self):
        correct = {'Config': {'Labels': {'com.docker.compose.project': fault.PROJECT,
                                         'com.docker.compose.service': 'ai-api'}}, 'State': {'Running': True}}
        fault.verify_identity(correct, 'ai-api')
        with self.assertRaises(ValueError):
            fault.verify_identity(correct, 'postgres')
        correct['Config']['Labels']['com.docker.compose.project'] = 'existing-site'
        with self.assertRaises(ValueError):
            fault.verify_identity(correct, 'ai-api')
