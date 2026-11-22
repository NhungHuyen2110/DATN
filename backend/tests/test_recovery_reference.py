import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.recovery import validate_backup_reference


class RecoveryReferenceTests(unittest.TestCase):
    def test_wrong_target_modified_backup_and_path_escape_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = b'PGDMPsynthetic-unit-test-only'
            (root / 'fixture.dump').write_bytes(payload)
            record = {'version': 1, 'environment': 'test', 'database_host': '127.0.0.1', 'database_port': 15439,
                      'database_name': 'lumiere_test_fixture', 'format': 'pg_dump_custom',
                      'backup_file': 'fixture.dump', 'backup_sha256': hashlib.sha256(payload).hexdigest()}
            reference = root / 'reference.json'
            reference.write_text(json.dumps(record))
            self.assertTrue(validate_backup_reference(reference, 'test', 'localhost', 15439, 'lumiere_test_fixture')['verified'])
            with self.assertRaises(ValueError):
                validate_backup_reference(reference, 'test', 'localhost', 15439, 'lumiere_test_other')
            (root / 'fixture.dump').write_bytes(payload + b'modified')
            with self.assertRaises(ValueError):
                validate_backup_reference(reference, 'test', 'localhost', 15439, 'lumiere_test_fixture')
            reference.write_text(json.dumps({**record, 'backup_file': '../elsewhere.dump'}))
            with self.assertRaises(ValueError):
                validate_backup_reference(reference, 'test', 'localhost', 15439, 'lumiere_test_fixture')
