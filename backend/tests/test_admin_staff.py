"""Admin account management on isolated fixtures, never production PostgreSQL."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_orders_api as orders_tests


class StaffManagementTests(orders_tests.OrderTests):
    def creation(self, **changes):
        body = {"full_name": "  New   Staff  ", "email": " NEW.STAFF@EXAMPLE.COM ", "phone": "0912345678", "password": self.password}
        body.update(changes)
        return body

    def test_admin_success_all_five_endpoints(self):
        status, created, _ = self.admin_call("POST", "/admin/staff", self.creation())
        self.assertEqual(status, 201)
        ident = created["id"]
        self.assertEqual(set(created), {"id", "full_name", "email", "phone", "is_active", "created_at"})
        self.assertEqual((created["full_name"], created["email"]), ("New Staff", "new.staff@example.com"))
        from app.core.security import verify_password
        with Session(self.engine) as db:
            user = db.get(self.User, ident)
            self.assertEqual(user.role.name, "staff")
            self.assertTrue(verify_password(self.password, user.password_hash))
            self.assertNotIn(user.password_hash, json.dumps(created))
        self.assertNotIn(self.password, json.dumps(created))
        page = self.admin_call(path="/admin/staff")[1]
        self.assertEqual(page["total"], 2)
        self.assertEqual([item["id"] for item in page["items"]], [4, ident])
        self.assertEqual(self.admin_call(path=f"/admin/staff/{ident}")[1], created)
        status, updated, _ = self.admin_call("PATCH", f"/admin/staff/{ident}", {"full_name": "New Name", "phone": None})
        self.assertEqual(status, 200)
        self.assertEqual((updated["full_name"], updated["phone"]), ("New Name", None))
        self.assertEqual(updated["email"], created["email"])
        for active in (False, True):
            self.assertEqual(self.admin_call("PATCH", f"/admin/staff/{ident}/status", {"is_active": active})[1]["is_active"], active)

    def test_permissions_and_inactive_admin(self):
        cases = (("GET", "/admin/staff", None), ("GET", "/admin/staff/4", None),
                 ("POST", "/admin/staff", self.creation()), ("PATCH", "/admin/staff/4", {"phone": None}),
                 ("PATCH", "/admin/staff/4/status", {"is_active": False}))
        for method, path, payload in cases:
            with self.subTest(path=path, method=method):
                self.assertEqual(self.cart_call(method, path, payload, anonymous=True)[0], 401)
                self.assertEqual(self.cart_call(method, path, payload)[0], 403)
                self.assertEqual(self.admin_call(method, path, payload, staff=True)[0], 403)
        with Session(self.engine) as db, db.begin():
            db.get(self.User, 3).is_active = False
        self.assertEqual(self.admin_call(path="/admin/staff")[0], 401)
        self.assertEqual(self.admin_call("POST", "/admin/staff", self.creation())[0], 401)

    def test_non_staff_targets_cannot_be_read_or_changed(self):
        for ident in (1, 2, 3, 999):
            for method, suffix, payload in (("GET", "", None), ("PATCH", "", {"full_name": "Changed"}), ("PATCH", "/status", {"is_active": False})):
                with self.subTest(ident=ident, method=method):
                    self.assertEqual(self.admin_call(method, f"/admin/staff/{ident}{suffix}", payload)[0], 404)
        self.assertTrue(self.snapshot(3)["is_active"])
        self.assertEqual(self.snapshot(1)["full_name"], "Customer 1")

    def test_duplicate_email_conflict_and_no_overwrite(self):
        before = self.snapshot(1)
        self.assertEqual(self.admin_call("POST", "/admin/staff", self.creation(email=" ALICE@EXAMPLE.COM "))[0], 409)
        self.assertEqual(self.snapshot(1), before)
        self.assertEqual(self.admin_call("POST", "/admin/staff", self.creation())[0], 201)
        self.assertEqual(self.admin_call("POST", "/admin/staff", self.creation())[0], 409)
        # Simulate the database unique constraint winning a concurrent insert.
        original_flush = Session.flush

        def fail_new_user(db, *args, **kwargs):
            has_user = any(isinstance(obj, self.User) for obj in db.new)
            original_flush(db, *args, **kwargs)
            if has_user:
                raise IntegrityError("private-sql", {}, Exception("private-driver"))

        with patch.object(Session, "flush", fail_new_user):
            status, body, _ = self.admin_call("POST", "/admin/staff", self.creation(email="other@example.com"))
        self.assertEqual(status, 409)
        self.assertNotIn("private-sql", json.dumps(body))
        with Session(self.engine) as db:
            self.assertIsNone(db.scalar(sa.select(self.User).where(self.User.email == "other@example.com")))

    def test_creation_validation_mass_assignment_and_no_password_echo(self):
        invalid = [{"email": "bad"}, {"phone": "123"}, {"full_name": " "}, {"full_name": "a\x00b"},
                   {"password": "pwd123"}, {"password": "x" * 129}]
        invalid += [{field: value} for field, value in {"role": "admin", "role_id": 3, "id": 99, "user_id": 99, "is_active": False, "password_hash": "attack"}.items()]
        for changes in invalid:
            payload = self.creation(**changes)
            with self.subTest(fields=list(changes)):
                status, body, _ = self.admin_call("POST", "/admin/staff", payload)
                self.assertEqual(status, 422)
                text = json.dumps(body)
                self.assertNotIn(payload["password"], text)
                self.assertTrue(all("input" not in error and "ctx" not in error for error in body["detail"]))

    def test_update_allowlist_and_strict_status(self):
        before = self.snapshot(4)
        for payload in ({}, {"full_name": None}, {"full_name": "A"}, {"phone": "bad"},
                        {"email": "new@example.com"}, {"role": "admin"}, {"role_id": 3},
                        {"password": "newpassword"}, {"password_hash": "attack"}, {"is_active": False}):
            self.assertEqual(self.admin_call("PATCH", "/admin/staff/4", payload)[0], 422)
            self.assertEqual(before, self.snapshot(4))
        for value in (0, 1, "false", None):
            self.assertEqual(self.admin_call("PATCH", "/admin/staff/4/status", {"is_active": value})[0], 422)
        self.assertEqual(self.admin_call("PATCH", "/admin/staff/4/status", {"is_active": False, "role": "admin"})[0], 422)

    def test_disable_revokes_all_sessions_and_reenable_does_not_restore(self):
        with Session(self.engine) as db, db.begin():
            db.add(self.UserSession(user_id=4, token_hash=self.hash_token("second-staff-token"), expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        self.assertEqual(self.admin_call(path="/staff/orders", staff=True)[0], 200)
        self.assertEqual(self.admin_call("PATCH", "/admin/staff/4/status", {"is_active": False})[0], 200)
        self.assertEqual(self.admin_call(path="/staff/orders", staff=True)[0], 401)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(sa.select(sa.func.count()).select_from(self.UserSession).where(self.UserSession.user_id == 4)), 0)
            self.assertGreater(db.scalar(sa.select(sa.func.count()).select_from(self.UserSession).where(self.UserSession.user_id == 1)), 0)
        self.assertEqual(self.call(method="POST", path="/auth/login", cookie=None, body={"email": "staff@example.com", "password": self.password})[0], 401)
        self.admin_call("PATCH", "/admin/staff/4/status", {"is_active": True})
        for token in ("staff-token", "second-staff-token"):
            self.assertEqual(self.call(method="GET", path="/staff/orders", cookie="lumiere_session=" + token)[0], 401)
        status, _, headers = self.call(method="POST", path="/auth/login", cookie=None, body={"email": "staff@example.com", "password": self.password})
        self.assertEqual(status, 200)
        cookie = next(value.decode().split(";", 1)[0] for key, value in headers if key.lower() == b"set-cookie")
        self.assertEqual(self.call(method="GET", path="/staff/orders", cookie=cookie)[0], 200)

    def test_status_error_rolls_back_both_user_and_session_deletion(self):
        before = self.snapshot(4)
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("private-driver")):
            status, body, _ = self.admin_call("PATCH", "/admin/staff/4/status", {"is_active": False})
        self.assertEqual(status, 500)
        self.assertNotIn("private-driver", json.dumps(body))
        self.assertEqual(self.snapshot(4), before)
        self.assertEqual(self.admin_call(path="/staff/orders", staff=True)[0], 200)

    def test_missing_role_is_not_created(self):
        # Empty the role in an isolated fixture while leaving Admin intact.
        with Session(self.engine) as db, db.begin():
            db.execute(sa.delete(self.UserSession).where(self.UserSession.user_id == 4))
            db.delete(db.get(self.User, 4))
            db.delete(db.get(self.Role, 4))
        self.assertEqual(self.admin_call("POST", "/admin/staff", self.creation())[0], 409)
        with Session(self.engine) as db:
            self.assertIsNone(db.scalar(sa.select(self.Role).where(self.Role.name == "staff")))

    def test_pagination_and_login_user_lock(self):
        self.admin_call("POST", "/admin/staff", self.creation())
        for query, expected_status in ((b"page=1&page_size=1", 200), (b"page=0", 422), (b"page_size=101", 422)):
            async def wrapped(scope, receive, send):
                scope["query_string"] = query
                await self.app(scope, receive, send)
            status, body, _ = asyncio.run(orders_tests.cart_tests.profile.request(wrapped, "GET", "/admin/staff", cookie="lumiere_session=admin-token"))
            self.assertEqual(status, expected_status)
            if status == 200:
                self.assertEqual((body["total"], len(body["items"])), (2, 1))
        from sqlalchemy.dialects import postgresql
        statements = []
        original_scalar = Session.scalar

        def record(db, statement, *args, **kwargs):
            statements.append(str(statement.compile(dialect=postgresql.dialect())))
            return original_scalar(db, statement, *args, **kwargs)

        with patch.object(Session, "scalar", record):
            self.assertEqual(self.call(method="POST", path="/auth/login", cookie=None, body={"email": "staff@example.com", "password": self.password})[0], 200)
        self.assertTrue(any("FROM users" in sql and "FOR UPDATE" in sql for sql in statements))


if __name__ == "__main__":
    original_connect = sa.engine.Engine.connect

    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("Only isolated in-memory SQLite connections are allowed")
        return original_connect(engine, *args, **kwargs)

    with patch.object(sa.engine.Engine, "connect", memory_only):
        unittest.main()
