"""Exercise the local provisioning CLI against memory-only fixtures."""

from contextlib import redirect_stderr, redirect_stdout
import getpass
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import warnings

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import create_admin


class AccountCLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {"POSTGRES_PASSWORD": "isolated-test-placeholder"}), patch("dotenv.load_dotenv"):
            from app.core.database import Base
            from app.models import Role, User
            from app.core.security import verify_password
        cls.base, cls.Role, cls.User = Base, Role, User
        cls.verify_password = staticmethod(verify_password)

    def setUp(self):
        self.engine = sa.create_engine("sqlite:///:memory:")
        self.base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, autoflush=False)
        self.addCleanup(self.engine.dispose)
        with self.factory() as db, db.begin():
            # Deliberately nonstandard IDs: CLI must look up role names.
            db.add_all([self.Role(id=7, name="admin"), self.Role(id=19, name="staff")])
        self.password = "unit-test-password-only"

    def run_cli(self, args=None, email="staff@example.com", name="  New   Staff  ", passwords=None):
        output = io.StringIO()
        with patch("app.core.database.SessionLocal", self.factory), patch("builtins.input", side_effect=[email, name]), patch("getpass.getpass", side_effect=passwords or [self.password, self.password]), redirect_stdout(output), redirect_stderr(output):
            result = create_admin.main([] if args is None else args)
        self.assertNotIn(self.password, output.getvalue())
        return result, output.getvalue()

    def users(self):
        with self.factory() as db:
            return [dict(row) for row in db.execute(sa.select(self.User.__table__)).mappings()]

    def test_default_role_is_staff_and_password_is_hashed(self):
        result, output = self.run_cli(email=" STAFF@EXAMPLE.COM ")
        self.assertEqual(result, 0)
        user, = self.users()
        self.assertEqual((user["email"], user["full_name"], user["role_id"]), ("staff@example.com", "New Staff", 19))
        self.assertTrue(user["is_active"])
        self.assertIsNone(user["phone"])
        self.assertNotEqual(user["password_hash"], self.password)
        self.assertTrue(self.verify_password(self.password, user["password_hash"]))
        self.assertNotIn(user["password_hash"], output)

    def test_explicit_admin_is_still_supported(self):
        self.assertEqual(self.run_cli(["--role", "admin"])[0], 0)
        self.assertEqual(self.users()[0]["role_id"], 7)

    def test_explicit_staff(self):
        self.assertEqual(self.run_cli(["--role", "staff"])[0], 0)
        self.assertEqual(self.users()[0]["role_id"], 19)

    def test_duplicate_email_never_promotes_or_changes_password(self):
        self.run_cli()
        before = self.users()
        result, _ = self.run_cli(["--role", "admin"], email="STAFF@example.com", name="Other Name")
        self.assertEqual(result, 1)
        self.assertEqual(before, self.users())

    def test_missing_role_does_not_seed(self):
        with self.factory() as db, db.begin():
            db.execute(sa.delete(self.Role).where(self.Role.name == "staff"))
        result, output = self.run_cli()
        self.assertEqual(result, 1)
        self.assertIn("Chưa có role staff", output)
        self.assertEqual(self.users(), [])
        with self.factory() as db:
            self.assertEqual(db.scalars(sa.select(self.Role.name)).all(), ["admin"])

    def test_invalid_input_is_rejected_without_disclosing_password(self):
        for kwargs in ({"email": "bad-email"}, {"name": "A"}, {"name": "a\x00b"}, {"passwords": ["short", "short"]}, {"passwords": [self.password, "different"]}):
            with self.subTest(kwargs=list(kwargs)):
                result, output = self.run_cli(**kwargs)
                self.assertEqual(result, 1)
                self.assertNotIn("short", output)
                self.assertEqual(self.users(), [])

    def test_invalid_role_rejected_before_prompt_or_database(self):
        with patch("builtins.input") as prompt, patch("app.core.database.SessionLocal") as factory, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                create_admin.main(["--role", "customer"])
        self.assertEqual(error.exception.code, 2)
        prompt.assert_not_called()
        factory.assert_not_called()

    def test_getpass_fallback_is_blocked(self):
        def unsupported_terminal(*args, **kwargs):
            warnings.warn("Hidden input unavailable", getpass.GetPassWarning)

        with patch("getpass.getpass", side_effect=unsupported_terminal), patch("builtins.input", side_effect=["new@example.com", "New User"]), patch("app.core.database.SessionLocal") as factory, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(create_admin.main([]), 1)
        factory.assert_not_called()

    def test_failure_after_insert_rolls_back_and_hides_error_details(self):
        original_flush = Session.flush

        def fail_after_flush(db, *args, **kwargs):
            original_flush(db, *args, **kwargs)
            raise RuntimeError("private-driver-connection-details")

        with patch.object(Session, "flush", fail_after_flush):
            result, output = self.run_cli()
        self.assertEqual(result, 1)
        self.assertNotIn("private-driver-connection-details", output)
        self.assertEqual(self.users(), [])

    def test_integrity_error_rolls_back_and_is_sanitized(self):
        with patch.object(Session, "flush", side_effect=IntegrityError("private-sql", {}, Exception("private-driver"))):
            result, output = self.run_cli()
        self.assertEqual(result, 1)
        self.assertNotIn("private-sql", output)
        self.assertNotIn("private-driver", output)
        self.assertEqual(self.users(), [])


if __name__ == "__main__":
    original_connect = sa.engine.Engine.connect

    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("Only isolated in-memory SQLite connections are allowed")
        return original_connect(engine, *args, **kwargs)

    with patch.object(sa.engine.Engine, "connect", memory_only):
        unittest.main()
