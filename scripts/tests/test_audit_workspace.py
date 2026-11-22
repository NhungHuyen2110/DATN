import importlib.util
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("audit_workspace", Path(__file__).resolve().parents[1] / "audit_workspace.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class AuditInventoryTests(unittest.TestCase):
    def test_inventory_never_executes_sources_or_reads_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AI").mkdir()
            (root / "AI/module.py").write_text("raise RuntimeError('must never execute')\n", encoding="utf-8")
            (root / "AI/.env").write_text("SECRET=sentinel", encoding="utf-8")
            (root / "AI/customer.csv").write_text("private", encoding="utf-8")
            (root / "AI/module.py.bak").write_text("private", encoding="utf-8")
            (root / "AI/.venv").mkdir()
            (root / "AI/.venv/ignored.py").write_text("invalid syntax !", encoding="utf-8")
            result = AUDIT.inventory(root)
            self.assertEqual([f["path"] for f in result["files"]], ["AI/module.py"])
            self.assertEqual(result["summary"]["syntax_failures"], 0)
            self.assertEqual(result["files"][0]["review_status"], "inventory-only")

    def test_syntax_failure_does_not_echo_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "backend").mkdir()
            (root / "backend/broken.py").write_text("sentinel_secret = !", encoding="utf-8")
            result = AUDIT.inventory(root)
            self.assertEqual(result["summary"]["syntax_failures"], 1)
            self.assertNotIn("sentinel_secret", str(result))


if __name__ == "__main__":
    unittest.main()
