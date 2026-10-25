"""Real API/session tests on memory fixtures; PostgreSQL connections forbidden."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_auth_profile as profile
import test_dashboard_api as dashboard_tests


class CustomerTests(profile.ProfileTests):
    def setUp(self):
        super().setUp()
        from app.models import Order, PaymentTransaction
        self.Order, self.Payment = Order, PaymentTransaction
        with Session(self.engine) as db, db.begin():
            for ident, role in ((3, "admin"), (4, "staff")):
                db.add(self.Role(id=ident, name=role))
                db.flush()
                db.add(self.User(id=ident, role_id=ident, full_name=role.title(),
                                 email=role + "@example.com", password_hash=self.password_hash, is_active=True))
                db.flush()
                db.add(self.UserSession(user_id=ident, token_hash=self.hash_token(role + "-token"),
                                       expires_at=datetime.now(timezone.utc) + timedelta(days=1)))

    seed_order = dashboard_tests.DashboardTests.seed_order

    def customers(self, method="GET", path="/admin/customers", body=None, cookie="admin-token", **params):
        async def wrapped(scope, receive, send):
            scope["query_string"] = urlencode(params).encode()
            await self.app(scope, receive, send)
        return asyncio.run(profile.request(wrapped, method, path, body,
            None if cookie is None else "lumiere_session=" + cookie))

    def toggle(self, active):
        return self.customers("PATCH", "/admin/customers/1/status", {"is_active": active})

    def test_customer_permissions_all_routes(self):
        for method, path, body in (("GET", "/admin/customers", None),
                ("GET", "/admin/customers/1", None),
                ("PATCH", "/admin/customers/1/status", {"is_active": False})):
            for cookie, expected in ((None, 401), ("wrong", 401), ("test-token", 403), ("staff-token", 403)):
                with self.subTest(method=method, cookie=cookie):
                    self.assertEqual(self.customers(method, path, body, cookie)[0], expected)
        with Session(self.engine) as db, db.begin():
            db.get(self.User, 3).is_active = False
        self.assertEqual(self.customers()[0], 401)

    def test_customer_fields_zero_stats_and_sensitive_data(self):
        status, page, _ = self.customers()
        self.assertEqual(status, 200)
        self.assertEqual((page["total"], [u["id"] for u in page["items"]]), (2, [1, 2]))
        item = page["items"][0]
        self.assertEqual(set(item), {"id", "full_name", "email", "phone", "created_at", "is_active", "order_count", "total_spent_vnd"})
        self.assertEqual((item["order_count"], Decimal(item["total_spent_vnd"])), (0, Decimal(0)))
        self.assertEqual(self.customers(path="/admin/customers/1")[1], item)
        text = json.dumps(page)
        for secret in (self.password_hash, "test-token", "token_hash", "password_hash", self.hash_token("test-token")):
            self.assertNotIn(secret, text)

    def test_customer_noncustomer_or_missing_404(self):
        for ident in (3, 4, 999):
            for method, suffix, payload in (("GET", "", None), ("PATCH", "/status", {"is_active": False})):
                self.assertEqual(self.customers(method, f"/admin/customers/{ident}{suffix}", payload)[0], 404)
        self.assertTrue(self.snapshot(3)["is_active"])
        self.assertTrue(self.snapshot(4)["is_active"])

    def test_customer_search_status_and_stable_pagination(self):
        with Session(self.engine) as db, db.begin():
            db.get(self.User, 2).is_active = False
            db.get(self.User, 2).phone = None
            db.get(self.User, 2).full_name = "Literal%_Name"
        for text in ("customer 1", " ALICE@EXAMPLE.COM ", "090123", "Customer"):
            page = self.customers(search=text)[1]
            self.assertEqual([u["id"] for u in page["items"]], [1])
        self.assertEqual(self.customers(search="%_")[1]["total"], 1)
        self.assertEqual(self.customers(search="absent")[1]["items"], [])
        self.assertEqual(self.customers(is_active="false")[1]["items"][0]["id"], 2)
        self.assertEqual(self.customers(is_active="true")[1]["total"], 1)
        for page, ids in ((1, [1]), (2, [2]), (3, [])):
            result = self.customers(page=page, page_size=1)[1]
            self.assertEqual(result["total"], 2)
            self.assertEqual([u["id"] for u in result["items"]], ids)
        self.assertIsNone(self.customers(path="/admin/customers/2")[1]["phone"])

    def test_customer_validation(self):
        for params in ({"page": 0}, {"page_size": 101}, {"page_size": 0}, {"page": "x"},
                       {"search": "x" * 256}, {"search": "bad\x00term"}, {"is_active": "bad"}):
            self.assertEqual(self.customers(**params)[0], 422)
        for ident in ("0", "-1", "2147483648", "abc"):
            self.assertEqual(self.customers(path=f"/admin/customers/{ident}")[0], 422)
        for body in ({}, {"is_active": "false"}, {"is_active": 0}, {"is_active": None},
                     {"is_active": False, "role": "admin"}, {"password_hash": "secret"}):
            status, result, _ = self.customers("PATCH", "/admin/customers/1/status", body)
            self.assertEqual(status, 422)
            self.assertTrue(all("input" not in error for error in result["detail"]))

    def test_customer_spending_matches_dashboard_exclusions(self):
        self.seed_order(amount="10.10")
        self.seed_order(amount="10.10")  # Equal-valued orders must both count.
        for params in ({"payment": False}, {"status": "cancelled"}, {"payment_status": "refunded"},
                       {"payment_status": "unpaid"}, {"tx_status": "pending"}, {"tx_status": "failed"},
                       {"review": True}, {"verified": None}, {"tx_amount": "99"}, {"provider": "vnpay"}):
            self.seed_order(**params)
        customer = self.customers(path="/admin/customers/1")[1]
        self.assertEqual(customer["order_count"], 12)
        self.assertEqual(Decimal(customer["total_spent_vnd"]), Decimal("20.20"))
        report = self.customers(path="/admin/dashboard")[1]
        self.assertEqual(customer["total_spent_vnd"], report["confirmed_payment_amount_vnd"])

    def test_customer_multiple_transactions_and_user_isolation(self):
        ident = self.seed_order()
        with Session(self.engine) as db, db.begin():
            db.add(self.Payment(order_id=ident, provider="vnpay", reference="duplicate",
                amount_vnd=Decimal("12.34"), status="succeeded", review_required=False,
                verified_at=datetime.now(timezone.utc)))
        other = self.seed_order(amount="100.00")
        with Session(self.engine) as db, db.begin():
            db.get(self.Order, other).user_id = 2
        page = self.customers()[1]["items"]
        self.assertEqual([(x["order_count"], Decimal(x["total_spent_vnd"])) for x in page],
                         [(1, Decimal(0)), (1, Decimal(100))])

    def test_customer_lock_revokes_all_sessions_and_unlock_does_not_restore(self):
        with Session(self.engine) as db, db.begin():
            db.add(self.UserSession(user_id=1, token_hash=self.hash_token("extra"),
                                   expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        self.assertEqual(self.toggle(False)[0], 200)
        self.assertEqual(self.toggle(False)[0], 200)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(sa.select(sa.func.count()).select_from(self.UserSession).where(self.UserSession.user_id == 1)), 0)
        self.assertEqual(self.call(method="GET")[0], 401)
        login = {"email": "alice@example.com", "password": self.password}
        self.assertEqual(self.call("POST", "/auth/login", login, cookie=None)[0], 401)
        self.assertEqual(self.toggle(True)[0], 200)
        self.assertEqual(self.call(method="GET")[0], 401)
        self.assertEqual(self.call("POST", "/auth/login", login, cookie=None)[0], 200)

    def test_customer_status_rollback(self):
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("private-driver")):
            status, body, _ = self.toggle(False)
        self.assertEqual(status, 500)
        self.assertNotIn("private-driver", json.dumps(body))
        self.assertTrue(self.snapshot()["is_active"])
        self.assertEqual(self.call(method="GET")[0], 200)

    def test_customer_login_and_lock_serialization_contract(self):
        # Both operations serialize on the same User row. SQLite cannot exercise
        # PostgreSQL wait semantics; verify emitted locks and both serial outcomes.
        from sqlalchemy.dialects import postgresql
        statements = []
        original = Session.scalar
        def record(db, statement, *args, **kwargs):
            statements.append(str(statement.compile(dialect=postgresql.dialect())))
            return original(db, statement, *args, **kwargs)
        login = {"email": "alice@example.com", "password": self.password}
        with patch.object(Session, "scalar", record):
            self.assertEqual(self.call("POST", "/auth/login", login, cookie=None)[0], 200)
            self.assertEqual(self.toggle(False)[0], 200)
        locks = [sql for sql in statements if "FOR UPDATE" in sql]
        self.assertTrue(any("users.email" in sql for sql in locks))
        self.assertTrue(any("FOR UPDATE OF users" in sql and "roles.name" in sql for sql in locks))
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(sa.select(sa.func.count()).select_from(self.UserSession).where(self.UserSession.user_id == 1)), 0)
        self.assertEqual(self.call("POST", "/auth/login", login, cookie=None)[0], 401)


if __name__ == "__main__":
    original_connect = sa.engine.Engine.connect
    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("Only isolated in-memory SQLite connections are allowed")
        return original_connect(engine, *args, **kwargs)
    with patch.object(sa.engine.Engine, "connect", memory_only):
        unittest.main()
