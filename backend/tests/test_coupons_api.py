"""Coupon API/checkout regression on memory fixtures, never real payments/PG."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_payments_api as payment_tests


class CouponTests(payment_tests.PaymentTests):
    def setUp(self):
        super().setUp()
        from app.models import Coupon, CouponUsage
        self.Coupon, self.Usage = Coupon, CouponUsage

    def payload(self, **changes):
        body = dict(code=" SAVE10 ", discount_type="percent", discount_value="10",
                    max_discount_vnd="80000", min_order_vnd="0", usage_limit=10,
                    starts_at="2026-01-01T00:00:00Z", ends_at="2099-01-01T00:00:00Z",
                    is_active=True, description="Coupon example")
        body.update(changes)
        return body

    def create_coupon(self, **changes):
        status, body, _ = self.admin_call("POST", "/admin/coupons", self.payload(**changes))
        self.assertEqual(status, 201, body)
        return body

    def coupon_cart(self, *, other=False, price="1000000"):
        with Session(self.engine) as db, db.begin():
            db.get(self.Product, 1).sale_price = Decimal(price)
        self.assertEqual(self.add(other=other)[0], 200)

    def coupon_order(self, code="SAVE10", *, other=False, online=False):
        body = dict(self.shipping(), coupon_code=code)
        if online:
            body["payment_method"] = "vnpay"
        return self.checkout(body, other=other)

    def coupon_state(self, ident=1):
        with Session(self.engine) as db:
            return (db.get(self.Coupon, ident).used_count,
                    [(u.status, u.returned_at) for u in db.scalars(sa.select(self.Usage).order_by(self.Usage.id))])

    def validate_coupon(self, code="SAVE10", **kwargs):
        return self.cart_call("POST", "/checkout/coupon/validate", {"coupon_code": code}, **kwargs)

    def test_coupon_admin_crud_and_snapshot(self):
        c = self.create_coupon()
        self.assertEqual(c["code"], "SAVE10")
        self.assertEqual(c["used_count"], 0)
        self.assertEqual(self.admin_call(path="/admin/coupons")[1]["total"], 1)
        self.assertEqual(self.admin_call(path="/admin/coupons/1")[1], c)
        self.coupon_cart()
        status, order, _ = self.coupon_order()
        self.assertEqual(status, 201)
        self.assertEqual(tuple(Decimal(order[k]) for k in ("subtotal_vnd", "discount_vnd", "total_vnd")),
                         (Decimal(1000000), Decimal(80000), Decimal(920000)))
        self.assertEqual((order["coupon_id"], order["coupon_code"]), (c["id"], "SAVE10"))
        self.assertEqual(self.admin_call("PATCH", "/admin/coupons/1", {"code": "RENAMED", "discount_value": "5"})[0], 200)
        old = self.cart_call(path=f"/orders/{order['id']}")[1]
        self.assertEqual((old["coupon_code"], old["discount_vnd"], old["total_vnd"]),
                         ("SAVE10", order["discount_vnd"], order["total_vnd"]))
        self.assertEqual(self.admin_call("PATCH", "/admin/coupons/1/status", {"is_active": False})[1]["is_active"], False)
        self.assertEqual(self.admin_call(path="/admin/coupons/999")[0], 404)

    def test_coupon_permissions(self):
        self.create_coupon()
        cases = (("GET", "/admin/coupons", None), ("GET", "/admin/coupons/1", None),
                 ("POST", "/admin/coupons", self.payload(code="OTHER")),
                 ("PATCH", "/admin/coupons/1", {"description": "Changed"}),
                 ("PATCH", "/admin/coupons/1/status", {"is_active": False}))
        for method, path, body in cases:
            with self.subTest(method=method, path=path):
                self.assertEqual(self.cart_call(method, path, body)[0], 403)
                self.assertEqual(self.admin_call(method, path, body, staff=True)[0], 403)
                self.assertEqual(self.cart_call(method, path, body, anonymous=True)[0], 401)
        self.assertEqual(self.admin_call("POST", "/checkout/coupon/validate", {"coupon_code": "SAVE10"})[0], 403)
        self.assertEqual(self.admin_call("POST", "/checkout/coupon/validate", {"coupon_code": "SAVE10"}, staff=True)[0], 403)
        self.assertEqual(self.validate_coupon(anonymous=True)[0], 401)
        with Session(self.engine) as db, db.begin():
            db.get(self.User, 1).is_active = False
        self.assertEqual(self.validate_coupon()[0], 401)

    def test_coupon_invalid_create_and_patch(self):
        invalid = ({"code": "a"}, {"code": "bad space"}, {"discount_type": "other"},
                   {"discount_value": "NaN"}, {"discount_value": "Infinity"}, {"discount_value": "-1"},
                   {"discount_value": "101"}, {"discount_value": "1.001"}, {"min_order_vnd": "-1"},
                   {"max_discount_vnd": "0"}, {"usage_limit": 0}, {"usage_limit": True},
                   {"starts_at": "2026-01-01T00:00:00"}, {"ends_at": "2025-01-01T00:00:00Z"},
                   {"is_active": "true"}, {"description": "bad\x00"}, {"used_count": 100})
        for changes in invalid:
            with self.subTest(changes=changes):
                self.assertEqual(self.admin_call("POST", "/admin/coupons", self.payload(**changes))[0], 422)
        self.create_coupon()
        for body in ({}, {"used_count": 0}, {"discount_value": None}, {"discount_value": "101"},
                     {"ends_at": "2020-01-01T00:00:00Z"}, {"starts_at": "2026-01-01"}, {"description": "bad\x00"}):
            self.assertEqual(self.admin_call("PATCH", "/admin/coupons/1", body)[0], 422)
        self.assertEqual(self.admin_call("POST", "/admin/coupons", self.payload(code="save10"))[0], 409)
        self.create_coupon(code="SECOND")
        self.assertEqual(self.admin_call("PATCH", "/admin/coupons/2", {"code": "save10"})[0], 409)
        self.assertEqual(self.admin_call("PATCH", "/admin/coupons/1/status", {"is_active": 0})[0], 422)

    def test_coupon_search_filters_pagination(self):
        self.create_coupon()
        self.create_coupon(code="OTHER", is_active=False, description="Special offer")
        async_request = payment_tests.orders_tests.cart_tests.profile.request
        import asyncio
        for query, expected in ((b"search=special", [2]), (b"is_active=false", [2]),
                                (b"page=2&page_size=1", [2]), (b"page=3&page_size=1", []), (b"search=%25", [])):
            async def wrapped(scope, receive, send):
                scope["query_string"] = query
                await self.app(scope, receive, send)
            status, body, _ = asyncio.run(async_request(wrapped, "GET", "/admin/coupons", cookie="lumiere_session=admin-token"))
            self.assertEqual(status, 200)
            self.assertEqual([c["id"] for c in body["items"]], expected)

    def test_coupon_validation_does_not_reserve(self):
        self.create_coupon()
        self.coupon_cart()
        for _ in range(2):
            status, body, _ = self.validate_coupon(" save10 ")
            self.assertEqual(status, 200)
            self.assertTrue(body["valid"])
            self.assertEqual(Decimal(body["total_vnd"]), Decimal(920000))
        self.assertEqual(self.coupon_state(), (0, []))
        self.assertEqual(self.stock(), 5)
        self.assertEqual(self.order_count(), 0)
        self.assertFalse(self.validate_coupon("UNKNOWN")[1]["valid"])
        self.assertEqual(self.cart_call("POST", "/checkout/coupon/validate", {"coupon_code": "SAVE10", "subtotal": 1})[0], 422)

    def test_coupon_responses_do_not_expose_account_or_payment_secrets(self):
        created = self.create_coupon()
        self.coupon_cart()
        responses = [created, self.admin_call(path="/admin/coupons")[1],
                     self.admin_call(path="/admin/coupons/1")[1], self.validate_coupon()[1],
                     self.coupon_order()[1]]
        text = json.dumps(responses)
        for secret in (self.password_hash, self.password, "admin-token", "test-token",
                       self.provider.secret, "token_hash", "password_hash"):
            self.assertNotIn(secret, text)

    def test_coupon_conditions_and_time_boundaries(self):
        c = self.create_coupon()
        self.coupon_cart()
        now = datetime.now(timezone.utc)
        cases = (({"is_active": False}, "inactive"),
                 ({"starts_at": now + timedelta(days=1)}, "not_started"),
                 ({"ends_at": now - timedelta(seconds=1)}, "expired"),
                 ({"min_order_vnd": Decimal(2000000)}, "min_order"),
                 ({"usage_limit": 1, "used_count": 1}, "exhausted"))
        for changes, reason in cases:
            with Session(self.engine) as db, db.begin():
                coupon = db.get(self.Coupon, c["id"])
                before = {key: getattr(coupon, key) for key in changes}
                for key, value in changes.items():
                    setattr(coupon, key, value)
            self.assertEqual(self.validate_coupon()[1]["reason"], reason)
            self.assertEqual(self.coupon_order()[0], 409)
            with Session(self.engine) as db, db.begin():
                for key, value in before.items():
                    setattr(db.get(self.Coupon, c["id"]), key, value)
        from app.services.coupons import failure_reason
        with Session(self.engine) as db:
            coupon = db.get(self.Coupon, c["id"])
            coupon.starts_at, coupon.ends_at = now, now + timedelta(seconds=1)
            self.assertIsNone(failure_reason(db, coupon, 1, Decimal(1000000), now))
            self.assertEqual(failure_reason(db, coupon, 1, Decimal(1000000), now + timedelta(seconds=1)), "expired")

    def test_coupon_fixed_percent_rounding_and_zero_total(self):
        self.create_coupon(discount_type="fixed", discount_value="1000.50", max_discount_vnd=None)
        self.coupon_cart(price="10000")
        self.assertEqual(Decimal(self.validate_coupon()[1]["discount_vnd"]), Decimal(1001))
        self.assertEqual(self.admin_call("PATCH", "/admin/coupons/1", {"discount_value": "10000"})[0], 200)
        self.assertEqual(self.validate_coupon()[1]["reason"], "invalid_discount")
        self.assertEqual(self.coupon_order()[0], 409)
        self.assertEqual(self.admin_call("PATCH", "/admin/coupons/1", {"discount_type": "percent", "discount_value": "100"})[0], 200)
        self.assertFalse(self.validate_coupon()[1]["valid"])
        self.assertEqual(self.admin_call("PATCH", "/admin/coupons/1", {"discount_value": "10", "max_discount_vnd": "800"})[0], 200)
        self.assertEqual(Decimal(self.validate_coupon()[1]["discount_vnd"]), Decimal(800))

    def test_coupon_once_per_customer_and_return_after_cancellation(self):
        self.create_coupon(usage_limit=None)
        self.coupon_cart()
        status, order, _ = self.coupon_order()
        self.assertEqual(status, 201)
        self.coupon_cart()
        self.assertEqual(self.validate_coupon()[1]["reason"], "already_used")
        self.assertEqual(self.coupon_order()[0], 409)
        self.assertEqual(self.status(order["id"], "cancelled")[0], 200)
        self.assertEqual(self.status(order["id"], "cancelled")[0], 200)
        self.assertEqual(self.coupon_state()[0], 0)
        self.assertEqual(self.coupon_state()[1][0][0], "returned")
        self.assertIsNotNone(self.coupon_state()[1][0][1])
        self.assertEqual(self.coupon_order()[0], 201)
        self.assertEqual(self.coupon_state()[0], 1)
        self.assertEqual(len(self.coupon_state()[1]), 2)

    def test_coupon_last_use_rechecked_at_checkout(self):
        # Serialized competition outcome; actual PostgreSQL races are separate.
        self.create_coupon(usage_limit=1)
        self.coupon_cart()
        self.coupon_cart(other=True)
        self.assertTrue(self.validate_coupon()[1]["valid"])
        self.assertTrue(self.validate_coupon(other=True)[1]["valid"])
        self.assertEqual(self.coupon_order()[0], 201)
        self.assertEqual(self.coupon_order(other=True)[0], 409)
        self.assertEqual(self.coupon_state()[0], 1)
        self.assertEqual(self.stock(), 4)
        self.assertEqual(len(self.cart_call(other=True)[1]["items"]), 1)

    def test_coupon_transaction_rollback(self):
        self.create_coupon()
        self.coupon_cart()
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("private-error")):
            status, body, _ = self.coupon_order()
        self.assertEqual(status, 500)
        self.assertNotIn("private-error", json.dumps(body))
        self.assertEqual(self.coupon_state(), (0, []))
        self.assertEqual(self.order_count(), 0)
        self.assertEqual(self.stock(), 5)
        self.assertEqual(len(self.cart_call()[1]["items"]), 1)
        order = self.coupon_order()[1]
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("private-error")):
            self.assertEqual(self.status(order["id"], "cancelled")[0], 500)
        self.assertEqual(self.coupon_state()[0], 1)
        self.assertEqual(self.coupon_state()[1][0][0], "active")
        self.assertEqual(self.stock(), 4)

    def test_coupon_usage_limit_cannot_be_reduced_below_used(self):
        self.create_coupon()
        self.coupon_cart()
        self.coupon_cart(other=True)
        self.assertEqual(self.coupon_order()[0], 201)
        self.assertEqual(self.coupon_order(other=True)[0], 201)
        self.assertEqual(self.admin_call("PATCH", "/admin/coupons/1", {"usage_limit": 1})[0], 409)
        self.assertEqual(self.coupon_state()[0], 2)

    def test_coupon_cod_after_discount_and_paid_cancel_blocked(self):
        self.create_coupon()
        self.coupon_cart()
        order = self.coupon_order()[1]
        for status in ("confirmed", "packing", "shipping", "delivered"):
            self.assertEqual(self.status(order["id"], status)[0], 200)
        status, payment, _ = self.admin_call("POST", f"/admin/orders/{order['id']}/cod/confirm", {"collection_reference": "COUPON-COD"})
        self.assertEqual(status, 200, payment)
        self.assertEqual(Decimal(payment["amount_vnd"]), Decimal(920000))
        self.assertEqual(self.status(order["id"], "cancelled")[0], 409)
        self.assertEqual(self.coupon_state()[0], 1)

    def test_coupon_vnpay_amount_and_pending_cancel_blocked(self):
        self.create_coupon()
        self.coupon_cart()
        status, order, _ = self.coupon_order(online=True)
        self.assertEqual(status, 201)
        status, result, _ = self.cart_call("POST", f"/orders/{order['id']}/payments/vnpay")
        self.assertEqual(status, 200)
        from urllib.parse import parse_qs, urlsplit
        self.assertEqual(parse_qs(urlsplit(result["payment_url"]).query)["vnp_Amount"], ["92000000"])
        self.assertEqual(self.status(order["id"], "cancelled")[0], 409)
        self.assertEqual(self.coupon_state()[0], 1)
        params = self.callback_params(result)
        self.assertEqual(self.callback(params)[1]["RspCode"], "00")
        self.assertEqual(self.callback(params)[1]["RspCode"], "02")
        self.assertEqual(self.cart_call(path=f"/orders/{order['id']}")[1]["payment_status"], "paid")

    def test_coupon_vnpay_error_does_not_consume(self):
        self.create_coupon()
        self.coupon_cart()
        from fastapi import HTTPException
        with patch("app.services.payment_providers.get_provider", side_effect=HTTPException(503, "Unavailable")):
            self.assertEqual(self.coupon_order(online=True)[0], 503)
        self.assertEqual(self.coupon_state(), (0, []))
        self.assertEqual(self.stock(), 5)
        self.assertEqual(self.order_count(), 0)

    def test_coupon_postgres_lock_order(self):
        from sqlalchemy.dialects import postgresql
        statements = []
        original_scalar, original_scalars = Session.scalar, Session.scalars
        def scalar(db, statement, *args, **kwargs):
            statements.append(str(statement.compile(dialect=postgresql.dialect())))
            return original_scalar(db, statement, *args, **kwargs)
        def scalars(db, statement, *args, **kwargs):
            statements.append(str(statement.compile(dialect=postgresql.dialect())))
            return original_scalars(db, statement, *args, **kwargs)
        self.create_coupon()
        self.coupon_cart()
        with patch.object(Session, "scalar", scalar), patch.object(Session, "scalars", scalars):
            order = self.coupon_order()[1]
        locks = [sql for sql in statements if "FOR UPDATE" in sql]
        for sql, table in zip(locks, ("users", "cart_items", "products", "coupons")):
            self.assertIn("FROM " + table, sql)
        self.assertEqual(len(locks), 4)
        statements.clear()
        with patch.object(Session, "scalar", scalar), patch.object(Session, "scalars", scalars):
            self.assertEqual(self.status(order["id"], "cancelled")[0], 200)
        locks = [sql for sql in statements if "FOR UPDATE" in sql]
        for sql, table in zip(locks, ("users", "orders", "products", "coupons", "coupon_usages")):
            self.assertIn("FROM " + table, sql)

    def test_coupon_database_usage_constraints(self):
        self.create_coupon()
        self.coupon_cart()
        first = self.coupon_order()[1]
        self.coupon_cart()
        second = self.checkout()[1]
        for order_id in (first["id"], second["id"]):
            with Session(self.engine) as db:
                db.add(self.Usage(coupon_id=1, user_id=1, order_id=order_id, status="active"))
                with self.assertRaises(IntegrityError):
                    db.commit()
        with Session(self.engine) as db:
            db.get(self.Coupon, 1).used_count = 11
            with self.assertRaises(IntegrityError):
                db.commit()

    def test_coupon_migration_preserves_old_order(self):
        from alembic import op
        from alembic.config import Config
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from alembic.script import ScriptDirectory
        scripts = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")))
        revision = scripts.get_revision("20261023_0006").module
        engine = sa.create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
                conn.exec_driver_sql("CREATE TABLE orders (id INTEGER PRIMARY KEY, total_vnd NUMERIC(38,2) NOT NULL)")
                conn.exec_driver_sql("INSERT INTO orders (id, total_vnd) VALUES (1, 123.45)")
                with Operations.context(MigrationContext.configure(conn)):
                    revision.upgrade()
                row = conn.exec_driver_sql("SELECT id,total_vnd,coupon_id,coupon_code FROM orders").one()
                self.assertEqual(tuple(row), (1, 123.45, None, None))
            output = io.StringIO()
            with Operations.context(MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})):
                revision.upgrade()
            sql = output.getvalue()
            self.assertIn("WHERE status = 'active'", sql)
            self.assertNotIn("DROP TABLE", sql)
            self.assertNotIn("UPDATE orders", sql)
        finally:
            engine.dispose()


if __name__ == "__main__":
    original_connect = sa.engine.Engine.connect
    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("Only isolated in-memory SQLite connections are allowed")
        return original_connect(engine, *args, **kwargs)
    with patch.object(sa.engine.Engine, "connect", memory_only), patch("dotenv.load_dotenv"):
        unittest.main()
