"""Real cookie authentication with an overridden, isolated in-memory database."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, attributes
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def request(app, method, path, body=None, cookie=None):
    messages = []
    sent = False
    raw = json.dumps(body).encode() if body is not None else b""

    async def receive():
        nonlocal sent
        if sent:
            await asyncio.Future()
        sent = True
        return {"type": "http.request", "body": raw, "more_body": False}

    async def send(message):
        messages.append(message)

    headers = [(b"content-type", b"application/json")]
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    await app({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path,
        "raw_path": path.encode(), "root_path": "", "query_string": b"",
        "headers": headers, "client": ("127.0.0.1", 12345), "server": ("test", 80),
    }, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    data = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start["status"], json.loads(data), start["headers"]


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {"POSTGRES_PASSWORD": "test-placeholder"}), patch("dotenv.load_dotenv"):
            from app.main import app
            from app.core.database import Base, get_db
            from app.core.security import hash_password
            from app.models import Role, User, UserSession
            from app.routers.auth import hash_session_token
        cls.app, cls.base = app, Base
        cls.get_db = staticmethod(get_db)
        cls.Role, cls.User, cls.UserSession = Role, User, UserSession
        cls.hash_token = staticmethod(hash_session_token)
        cls.password = "Test-password-123!"
        cls.password_hash = hash_password(cls.password)

        # SQLite drops timezone info. Restore UTC on test loads only; PostgreSQL
        # TIMESTAMP WITH TIME ZONE already returns aware datetime values.
        def restore_utc(target, context):
            if target.expires_at.tzinfo is None:
                attributes.set_committed_value(target, "expires_at", target.expires_at.replace(tzinfo=timezone.utc))

        cls.restore_utc = staticmethod(restore_utc)
        sa.event.listen(UserSession, "load", restore_utc)

    @classmethod
    def tearDownClass(cls):
        sa.event.remove(cls.UserSession, "load", cls.restore_utc)

    def setUp(self):
        self.engine = sa.create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.base.metadata.create_all(self.engine)
        with Session(self.engine) as db, db.begin():
            db.add(self.Role(id=1, name="customer"))
            db.flush()
            for ident, email in ((1, "alice@example.com"), (2, "bob@example.com")):
                db.add(self.User(id=ident, role_id=1, full_name=f"Customer {ident}", email=email,
                                 phone="0901234567", password_hash=self.password_hash, is_active=True))
            db.flush()
            db.add(self.UserSession(user_id=1, token_hash=self.hash_token("test-token"), expires_at=datetime.now(timezone.utc) + timedelta(days=1)))

        def override_db():
            with Session(self.engine) as db:
                yield db

        self.app.dependency_overrides[self.get_db] = override_db
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.app.dependency_overrides.pop, self.get_db)

    def call(self, method="PATCH", path="/auth/me", body=None, cookie="lumiere_session=test-token"):
        return asyncio.run(request(self.app, method, path, body, cookie))

    def snapshot(self, ident=1):
        with Session(self.engine) as db:
            table = self.User.__table__
            return dict(db.execute(sa.select(table).where(table.c.id == ident)).mappings().one())

    def test_update_own_profile_and_get(self):
        other = self.snapshot(2)
        before = self.snapshot()
        status, body, _ = self.call(body={"full_name": "  Nguyễn   Văn An  ", "phone": " 0912345678 "})
        self.assertEqual(status, 200)
        self.assertEqual(body, {"id": 1, "full_name": "Nguyễn Văn An", "phone": "0912345678", "email": "alice@example.com", "role": "customer"})
        self.assertEqual(self.call(method="GET")[1], body)
        self.assertEqual(self.snapshot(2), other)
        after = self.snapshot()
        for key in before:
            if key not in ("full_name", "phone"):
                self.assertEqual(before[key], after[key])
        self.assertNotIn(self.password_hash, json.dumps(body))
        self.assertNotIn("test-token", json.dumps(body))

    def test_partial_update_and_clear_phone(self):
        self.assertEqual(self.call(body={"full_name": "New Name"})[1]["phone"], "0901234567")
        self.assertEqual(self.call(body={"phone": "0987654321"})[1]["full_name"], "New Name")
        for value in (None, "", "   "):
            self.assertIsNone(self.call(body={"phone": value})[1]["phone"])

    def test_missing_invalid_and_expired_cookie(self):
        before = self.snapshot()
        for cookie in (None, "lumiere_session=wrong"):
            self.assertEqual(self.call(body={"full_name": "New Name"}, cookie=cookie)[0], 401)
        with Session(self.engine) as db, db.begin():
            session = db.scalar(sa.select(self.UserSession))
            session.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        self.assertEqual(self.call(body={"full_name": "New Name"})[0], 401)
        self.assertEqual(before, self.snapshot())

    def test_inactive_or_deleted_user(self):
        with Session(self.engine) as db, db.begin():
            db.get(self.User, 1).is_active = False
        self.assertEqual(self.call(body={"phone": None})[0], 401)
        with Session(self.engine) as db, db.begin():
            db.execute(sa.delete(self.User).where(self.User.id == 1))
        self.assertEqual(self.call(body={"phone": None})[0], 401)

    def test_invalid_input_does_not_write(self):
        before = self.snapshot()
        invalid = [{}, {"full_name": None}, {"full_name": " "}, {"full_name": "A"},
                   {"full_name": "A" * 151}, {"full_name": "a\x00b"}, {"full_name": 123},
                   {"phone": "123"}, {"phone": "1901234567"}, {"phone": "０９１２３４５６７８"},
                   {"phone": 912345678}, {"full_name": "New Name", "phone": "bad"}]
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertEqual(self.call(body=payload)[0], 422)
                self.assertEqual(before, self.snapshot())

    def test_forbidden_fields_reject_entire_request(self):
        before = self.snapshot()
        for field, value in {"role": "admin", "role_id": 2, "email": "changed@example.com", "password_hash": "bad", "password": "new", "is_active": False, "user_id": 2, "id": 2, "created_at": "2026-01-01", "unknown": 1}.items():
            with self.subTest(field=field):
                self.assertEqual(self.call(body={"full_name": "New Name", field: value})[0], 422)
                self.assertEqual(before, self.snapshot())

    def test_commit_failure_rolls_back_and_hides_driver_error(self):
        before = self.snapshot()
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("private-driver-details")):
            status, body, _ = self.call(body={"full_name": "New Name"})
        self.assertEqual(status, 500)
        self.assertNotIn("private-driver-details", json.dumps(body))
        self.assertEqual(before, self.snapshot())

    def test_register_login_patch_logout_existing_flow(self):
        status, _, _ = self.call(method="POST", path="/auth/register", cookie=None,
                                 body={"full_name": "New Customer", "email": "new@example.com", "password": self.password})
        self.assertEqual(status, 201)
        status, _, headers = self.call(method="POST", path="/auth/login", cookie=None,
                                       body={"email": "new@example.com", "password": self.password})
        self.assertEqual(status, 200)
        set_cookie = next(v.decode() for k, v in headers if k.lower() == b"set-cookie")
        self.assertIn("HttpOnly", set_cookie)
        cookie = set_cookie.split(";", 1)[0]
        status, body, _ = self.call(body={"phone": "0912345678"}, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(body["email"], "new@example.com")
        self.assertEqual(body["role"], "customer")
        self.assertEqual(self.call(method="POST", path="/auth/logout", cookie=cookie)[0], 200)
        self.assertEqual(self.call(body={"phone": None}, cookie=cookie)[0], 401)


if __name__ == "__main__":
    original_connect = sa.engine.Engine.connect

    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("Only isolated in-memory SQLite connections are allowed")
        return original_connect(engine, *args, **kwargs)

    with patch.object(sa.engine.Engine, "connect", memory_only):
        unittest.main()
