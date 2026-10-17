"""Order business rules on in-memory fixtures; all PostgreSQL access is blocked."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_cart_api as cart_tests


class OrderTests(cart_tests.CartTests):
    def setUp(self):
        super().setUp()
        from app.models import Order, OrderItem
        self.Order, self.OrderItem = Order, OrderItem
        with Session(self.engine) as db, db.begin():
            for ident, name in ((3, "admin"), (4, "staff")):
                db.add(self.Role(id=ident, name=name))
                db.flush()
                db.add(self.User(id=ident, role_id=ident, full_name=name.title(), email=name + "@example.com", password_hash=self.password_hash, is_active=True))
                db.flush()
                db.add(self.UserSession(user_id=ident, token_hash=self.hash_token(name + "-token"), expires_at=datetime.now(timezone.utc) + timedelta(days=1)))

    def shipping(self):
        return {"recipient_name": "Nguyễn Văn An", "phone": "0912345678", "address": "123 Đường Nguyễn Huệ, TP HCM"}

    def checkout(self, body=None, **kwargs):
        return self.cart_call("POST", "/orders", self.shipping() if body is None else body, **kwargs)

    def admin_call(self, method="GET", path="/admin/orders", body=None, staff=False):
        return self.call(method=method, path=path, body=body, cookie="lumiere_session=" + ("staff-token" if staff else "admin-token"))

    def status(self, ident, value):
        return self.admin_call("PATCH", f"/admin/orders/{ident}/status", {"status": value})

    def order_count(self):
        with Session(self.engine) as db:
            return db.scalar(sa.select(sa.func.count()).select_from(self.Order))

    def stock(self, product_id=1):
        with Session(self.engine) as db:
            return db.get(self.Product, product_id).stock

    def test_checkout_snapshots_stock_and_cart_atomic(self):
        self.add(2)
        self.add(1, product_id=2)
        with Session(self.engine) as db:
            original = db.get(self.Product, 1)
            price, name, sku = original.sale_price, original.name, original.sku
        status, body, _ = self.checkout()
        self.assertEqual(status, 201)
        self.assertEqual((body["status"], body["payment_status"]), ("pending", "unpaid"))
        self.assertEqual(body["user_id"], 1)
        self.assertEqual(self.stock(), 3)
        self.assertEqual(self.stock(2), 2)
        self.assertEqual(self.cart_call()[1]["items"], [])
        item = next(i for i in body["items"] if i["product_id"] == 1)
        self.assertEqual((item["sku"], item["product_name"]), (sku, name))
        self.assertEqual(Decimal(item["unit_price_vnd"]), price)
        self.assertEqual(Decimal(item["line_total_vnd"]), price * 2)
        self.assertEqual(Decimal(body["total_vnd"]), sum(Decimal(i["line_total_vnd"]) for i in body["items"]))
        self.assertNotIn("cost_price", json.dumps(body))
        with Session(self.engine) as db, db.begin():
            product = db.get(self.Product, 1)
            product.name = "Changed Product"
            product.sale_price = Decimal("100.00")
        detail = self.cart_call(path=f"/orders/{body['id']}")[1]
        self.assertEqual(detail["items"], body["items"])

    def test_empty_cart_and_duplicate_submit(self):
        self.assertEqual(self.checkout()[0], 409)
        self.add()
        self.assertEqual(self.checkout()[0], 201)
        self.assertEqual(self.checkout()[0], 409)
        self.assertEqual(self.order_count(), 1)

    def test_out_of_stock_retains_cart_without_order(self):
        self.add(3)
        with Session(self.engine) as db, db.begin():
            db.get(self.Product, 1).stock = 1
        self.assertEqual(self.checkout()[0], 409)
        self.assertEqual(self.order_count(), 0)
        self.assertEqual(self.cart_call()[1]["total_quantity"], 3)
        self.assertEqual(self.stock(), 1)

    def test_another_customer_cannot_spend_last_stock(self):
        self.add(4)
        self.add(4, other=True)
        self.assertEqual(self.checkout()[0], 201)
        self.assertEqual(self.checkout(other=True)[0], 409)
        self.assertEqual(self.stock(), 1)
        self.assertEqual(self.cart_call(other=True)[1]["total_quantity"], 4)

    def test_missing_product_detected_without_partial_order(self):
        self.add()
        # Deliberately simulate corrupt legacy data in memory only.
        with self.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys = OFF")
            conn.execute(sa.update(self.CartItem).values(product_id=999))
            conn.commit()
            conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        self.assertEqual(self.checkout()[0], 409)
        self.assertEqual(self.order_count(), 0)
        self.assertEqual(self.stock(), 5)

    def test_checkout_failure_after_flush_rolls_back_everything(self):
        self.add(2)
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("private driver information")):
            status, body, _ = self.checkout()
        self.assertEqual(status, 500)
        self.assertNotIn("private driver", json.dumps(body))
        self.assertEqual(self.stock(), 5)
        self.assertEqual(self.order_count(), 0)
        self.assertEqual(self.cart_call()[1]["total_quantity"], 2)

    def test_authorization_owner_admin_and_staff(self):
        self.add()
        ident = self.checkout()[1]["id"]
        self.assertEqual(self.cart_call(path=f"/orders/{ident}", other=True)[0], 404)
        self.assertEqual(self.admin_call(path=f"/orders/{ident}")[0], 200)
        self.assertEqual(self.admin_call(path=f"/orders/{ident}", staff=True)[0], 404)
        self.assertEqual(self.cart_call(path="/admin/orders")[0], 403)
        self.assertEqual(self.admin_call(staff=True)[0], 403)
        self.assertEqual(self.cart_call("PATCH", f"/admin/orders/{ident}/status", {"status": "confirmed"})[0], 403)
        self.assertEqual(self.admin_call("POST", "/orders", self.shipping())[0], 403)
        self.assertEqual(self.admin_call("POST", "/orders", self.shipping(), staff=True)[0], 403)
        self.assertEqual(self.cart_call(path="/orders/999")[0], 404)

    def test_all_endpoints_require_auth(self):
        for method, path, body in (("POST", "/orders", self.shipping()), ("GET", "/orders/my", None), ("GET", "/orders/1", None), ("GET", "/admin/orders", None), ("PATCH", "/admin/orders/1/status", {"status": "confirmed"})):
            with self.subTest(path=path):
                self.assertEqual(self.cart_call(method, path, body, anonymous=True)[0], 401)

    def test_list_ownership_my_route_and_pagination(self):
        self.add()
        first = self.checkout()[1]["id"]
        self.add(other=True)
        second = self.checkout(other=True)[1]["id"]
        self.assertEqual([o["id"] for o in self.cart_call(path="/orders/my")[1]["items"]], [first])
        self.assertEqual([o["id"] for o in self.cart_call(path="/orders/my", other=True)[1]["items"]], [second])
        # Generic test ASGI helper accepts query_string only through its scope.
        import asyncio
        # Use a small authenticated ASGI wrapper rather than changing production helpers.
        async def wrapped(scope, receive, send):
            scope["query_string"] = b"page=1&page_size=1"
            await self.app(scope, receive, send)
        status, body, _ = asyncio.run(cart_tests.profile.request(wrapped, "GET", "/admin/orders", cookie="lumiere_session=admin-token"))
        self.assertEqual(status, 200)
        self.assertEqual((body["total"], len(body["items"])), (2, 1))
        self.assertEqual(body["items"][0]["id"], second)

        for query in (b"page=0", b"page_size=101", b"page_size=abc"):
            async def invalid_query(scope, receive, send):
                scope["query_string"] = query
                await self.app(scope, receive, send)
            self.assertEqual(asyncio.run(cart_tests.profile.request(invalid_query, "GET", "/admin/orders", cookie="lumiere_session=admin-token"))[0], 422)

    def test_cancel_restores_stock_exactly_once(self):
        self.add(2)
        body = self.checkout()[1]
        ident = body["id"]
        self.assertEqual(self.stock(), 3)
        self.assertEqual(self.status(ident, "cancelled")[0], 200)
        self.assertEqual(self.stock(), 5)
        self.assertEqual(self.status(ident, "cancelled")[0], 200)
        self.assertEqual(self.stock(), 5)
        self.assertEqual(self.status(ident, "confirmed")[0], 409)
        self.assertEqual(self.cart_call()[1]["items"], [])
        with Session(self.engine) as db:
            self.assertTrue(db.get(self.Order, ident).stock_restored)

    def test_status_machine_and_terminal_states(self):
        self.add()
        ident = self.checkout()[1]["id"]
        self.assertEqual(self.status(ident, "shipping")[0], 409)
        for state in ("confirmed", "packing", "shipping", "delivered"):
            self.assertEqual(self.status(ident, state)[0], 200)
        self.assertEqual(self.status(ident, "cancelled")[0], 409)
        self.assertEqual(self.status(ident, "pending")[0], 409)
        self.assertEqual(self.stock(), 4)
        self.assertEqual(self.status(999, "confirmed")[0], 404)

    def test_confirmed_cancel_and_paid_cancel_blocked(self):
        self.add()
        ident = self.checkout()[1]["id"]
        self.status(ident, "confirmed")
        with Session(self.engine) as db, db.begin():
            db.get(self.Order, ident).payment_status = "paid"
        self.assertEqual(self.status(ident, "cancelled")[0], 409)
        self.assertEqual(self.stock(), 4)
        with Session(self.engine) as db, db.begin():
            db.get(self.Order, ident).payment_status = "unpaid"
        self.assertEqual(self.status(ident, "cancelled")[0], 200)
        self.assertEqual(self.stock(), 5)

    def test_cancel_failure_rolls_back_stock_and_status(self):
        self.add(2)
        ident = self.checkout()[1]["id"]
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("failure")):
            self.assertEqual(self.status(ident, "cancelled")[0], 500)
        self.assertEqual(self.stock(), 3)
        with Session(self.engine) as db:
            order = db.get(self.Order, ident)
            self.assertEqual(order.status, "pending")
            self.assertFalse(order.stock_restored)

    def test_restoration_overflow_rolls_back_all_products(self):
        self.add()
        self.add(product_id=2)
        ident = self.checkout()[1]["id"]
        with Session(self.engine) as db, db.begin():
            db.get(self.Product, 2).stock = 2147483647
        self.assertEqual(self.status(ident, "cancelled")[0], 409)
        self.assertEqual(self.stock(), 4)
        self.assertEqual(self.stock(2), 2147483647)
        self.assertEqual(self.cart_call(path=f"/orders/{ident}")[1]["status"], "pending")

    def test_shipping_and_mass_assignment_validation(self):
        for field, value in (("recipient_name", " "), ("phone", "123"), ("phone", None), ("address", "a\x00b"), ("address", "a"), ("recipient_name", "a" * 151)):
            body = self.shipping()
            body[field] = value
            with self.subTest(field=field):
                self.assertEqual(self.checkout(body)[0], 422)
        for field in ("user_id", "role", "status", "payment_status", "price", "total_vnd", "items", "shipping_vnd"):
            body = self.shipping()
            body[field] = 1
            self.assertEqual(self.checkout(body)[0], 422)
        self.assertEqual(self.admin_call("PATCH", "/admin/orders/1/status", {"status": "invalid"})[0], 422)
        self.assertEqual(self.admin_call("PATCH", "/admin/orders/1/status", {"status": "confirmed", "payment_status": "paid"})[0], 422)

    def test_order_lock_sequence_and_migration_offline(self):
        from sqlalchemy.dialects import postgresql
        statements = []
        original_execute = Session._execute_internal

        def record(db, statement, *args, **kwargs):
            if hasattr(statement, "compile"):
                statements.append(str(statement.compile(dialect=postgresql.dialect())))
            return original_execute(db, statement, *args, **kwargs)

        self.add()
        with patch.object(Session, "_execute_internal", record):
            self.assertEqual(self.checkout()[0], 201)
        locks = [sql for sql in statements if "FOR UPDATE" in sql]
        self.assertIn("FROM users", locks[0])
        self.assertIn("FROM cart_items", locks[1])
        self.assertIn("FROM products", locks[2])
        self.assertIn("ORDER BY products.id", locks[2])
        from alembic import command
        from alembic.config import Config
        output = io.StringIO()
        command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output), "20261016_0002:20261016_0003", sql=True)
        sql = output.getvalue()
        self.assertLess(sql.index("CREATE TABLE orders"), sql.index("CREATE TABLE order_items"))
        self.assertNotIn("DROP TABLE", sql)
        self.assertNotIn("DELETE FROM", sql)
        self.assertNotIn("ALTER TABLE products", sql)

    def test_staff_routes_permissions_and_minimal_customer_data(self):
        self.add()
        ident = self.checkout()[1]["id"]
        for method, path, payload in (
            ("GET", "/staff/orders", None),
            ("GET", f"/staff/orders/{ident}", None),
            ("PATCH", f"/staff/orders/{ident}/status", {"status": "confirmed"}),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.cart_call(method, path, payload, anonymous=True)[0], 401)
                self.assertEqual(self.cart_call(method, path, payload)[0], 403)
                self.assertEqual(self.admin_call(method, path, payload, staff=True)[0], 200)
                self.assertEqual(self.admin_call(method, path, payload)[0], 200)
        detail = self.admin_call(path=f"/staff/orders/{ident}", staff=True)[1]
        self.assertEqual((detail["recipient_name"], detail["phone"], detail["address"]),
                         (self.shipping()["recipient_name"], self.shipping()["phone"], self.shipping()["address"]))
        for private in ("user_id", "email", "password_hash", "is_active", "role", "cost_price", "wholesale_price"):
            self.assertNotIn(private, json.dumps(detail))
        self.assertNotIn("user_id", self.admin_call(path="/staff/orders", staff=True)[1]["items"][0])
        self.assertIn("user_id", self.admin_call(path=f"/orders/{ident}")[1])

    def test_staff_status_flow_does_not_grant_cod_or_admin_permissions(self):
        self.add()
        ident = self.checkout()[1]["id"]
        path = f"/staff/orders/{ident}/status"
        self.assertEqual(self.admin_call("PATCH", path, {"status": "shipping"}, staff=True)[0], 409)
        for state in ("confirmed", "packing", "shipping", "delivered"):
            self.assertEqual(self.admin_call("PATCH", path, {"status": state}, staff=True)[0], 200)
        self.assertEqual(self.admin_call("PATCH", path, {"status": "pending"}, staff=True)[0], 409)
        self.assertEqual(self.admin_call("PATCH", path, {"status": "cancelled"}, staff=True)[0], 409)
        self.assertEqual(self.admin_call("PATCH", f"/admin/orders/{ident}/status", {"status": "delivered"}, staff=True)[0], 403)
        self.assertEqual(self.admin_call("POST", f"/admin/orders/{ident}/cod/confirm", {"collection_reference": "TEST-RECEIPT"}, staff=True)[0], 403)
        self.assertEqual(self.admin_call(path=f"/staff/orders/{ident}", staff=True)[1]["payment_status"], "unpaid")
        self.assertEqual(self.stock(), 4)

    def test_staff_cancellation_reuses_single_stock_restoration(self):
        self.add(2)
        ident = self.checkout()[1]["id"]
        path = f"/staff/orders/{ident}/status"
        self.assertEqual(self.admin_call("PATCH", path, {"status": "cancelled"}, staff=True)[0], 200)
        self.assertEqual(self.stock(), 5)
        self.assertEqual(self.admin_call("PATCH", path, {"status": "cancelled"}, staff=True)[0], 200)
        self.assertEqual(self.stock(), 5)
        self.assertEqual(self.admin_call("PATCH", path, {"status": "confirmed"}, staff=True)[0], 409)

    def test_staff_cannot_bypass_payment_or_pending_transaction_guards(self):
        self.add()
        ident = self.checkout()[1]["id"]
        from app.models import PaymentTransaction
        with Session(self.engine) as db, db.begin():
            order = db.get(self.Order, ident)
            order.payment_method = "vnpay"
            db.add(PaymentTransaction(order_id=ident, provider="vnpay", reference="staff-test-pending",
                                      amount_vnd=order.total_vnd, status="pending", review_required=False))
        path = f"/staff/orders/{ident}/status"
        self.assertEqual(self.admin_call("PATCH", path, {"status": "confirmed"}, staff=True)[0], 200)
        self.assertEqual(self.admin_call("PATCH", path, {"status": "packing"}, staff=True)[0], 409)
        self.assertEqual(self.admin_call("PATCH", path, {"status": "cancelled"}, staff=True)[0], 409)
        self.assertEqual(self.stock(), 4)
        self.assertEqual(self.admin_call("PATCH", path, {"status": "confirmed", "payment_status": "paid"}, staff=True)[0], 422)

    def test_staff_status_failure_rolls_back_and_service_checks_roles(self):
        self.add()
        ident = self.checkout()[1]["id"]
        path = f"/staff/orders/{ident}/status"
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("private-driver-error")):
            status, body, _ = self.admin_call("PATCH", path, {"status": "cancelled"}, staff=True)
        self.assertEqual(status, 500)
        self.assertNotIn("private-driver-error", json.dumps(body))
        self.assertEqual(self.stock(), 4)
        self.assertEqual(self.admin_call(path=f"/staff/orders/{ident}", staff=True)[1]["status"], "pending")
        from fastapi import HTTPException
        from app.services.orders import change_status
        for actor, allow_staff in ((1, True), (4, False)):
            with Session(self.engine) as db, self.assertRaises(HTTPException) as error:
                change_status(db, actor, ident, "confirmed", allow_staff=allow_staff)
            self.assertEqual(error.exception.status_code, 403)

    def test_staff_pagination_not_found_and_validation(self):
        self.add()
        first = self.checkout()[1]["id"]
        self.add(other=True)
        second = self.checkout(other=True)[1]["id"]
        import asyncio
        for query, expected_status in ((b"page=1&page_size=1", 200), (b"page=0", 422), (b"page_size=101", 422)):
            async def wrapped(scope, receive, send):
                scope["query_string"] = query
                await self.app(scope, receive, send)
            status, body, _ = asyncio.run(cart_tests.profile.request(wrapped, "GET", "/staff/orders", cookie="lumiere_session=staff-token"))
            self.assertEqual(status, expected_status)
            if status == 200:
                self.assertEqual(body["total"], 2)
                self.assertEqual([item["id"] for item in body["items"]], [second])
        self.assertEqual(self.admin_call(path="/staff/orders/999", staff=True)[0], 404)
        self.assertEqual(self.admin_call("PATCH", "/staff/orders/999/status", {"status": "confirmed"}, staff=True)[0], 404)
        self.assertEqual(self.admin_call(path="/staff/orders/abc", staff=True)[0], 422)
        self.assertEqual(self.admin_call("PATCH", f"/staff/orders/{first}/status", {"status": "unknown"}, staff=True)[0], 422)

    def product_snapshot(self):
        with Session(self.engine) as db:
            table = self.Product.__table__
            return dict(db.execute(sa.select(table).where(table.c.id == 1)).mappings().one())

    def test_staff_and_admin_stock_update_preserves_product_fields(self):
        before = self.product_snapshot()
        for staff, expected, new in ((True, 5, 15), (False, 15, 12), (True, 12, 12)):
            status, body, _ = self.admin_call("PATCH", "/staff/products/1/stock", {"expected_stock": expected, "stock": new}, staff=staff)
            self.assertEqual(status, 200)
            self.assertEqual(body, {"id": 1, "sku": before["sku"], "stock": new})
            after = self.product_snapshot()
            self.assertEqual({k: v for k, v in after.items() if k != "stock"},
                             {k: v for k, v in before.items() if k != "stock"})

    def test_stock_update_auth_and_missing_product(self):
        payload = {"expected_stock": 5, "stock": 10}
        self.assertEqual(self.cart_call("PATCH", "/staff/products/1/stock", payload, anonymous=True)[0], 401)
        self.assertEqual(self.cart_call("PATCH", "/staff/products/1/stock", payload)[0], 403)
        self.assertEqual(self.admin_call("PATCH", "/staff/products/999/stock", payload, staff=True)[0], 404)
        self.assertEqual(self.stock(), 5)

    def test_stock_update_strict_validation_and_integer_boundaries(self):
        path = "/staff/products/1/stock"
        for field in ("expected_stock", "stock"):
            for value in (-1, 2147483648, True, False, 1.0, 1.5, "5", None):
                payload = {"expected_stock": 5, "stock": 10, field: value}
                with self.subTest(payload=payload):
                    self.assertEqual(self.admin_call("PATCH", path, payload, staff=True)[0], 422)
        for payload in ({}, {"stock": 10}, {"expected_stock": 5},
                        {"expected_stock": 5, "stock": 10, "sku": "CHANGED"},
                        {"expected_stock": 5, "stock": 10, "sale_price": "1"}):
            self.assertEqual(self.admin_call("PATCH", path, payload, staff=True)[0], 422)
        self.assertEqual(self.stock(), 5)
        self.assertEqual(self.admin_call("PATCH", path, {"expected_stock": 5, "stock": 0}, staff=True)[1]["stock"], 0)
        self.assertEqual(self.admin_call("PATCH", path, {"expected_stock": 0, "stock": 2147483647})[1]["stock"], 2147483647)

    def test_stock_update_detects_stale_staff_and_checkout_values(self):
        path = "/staff/products/1/stock"
        self.assertEqual(self.admin_call("PATCH", path, {"expected_stock": 5, "stock": 8}, staff=True)[0], 200)
        before = self.product_snapshot()
        self.assertEqual(self.admin_call("PATCH", path, {"expected_stock": 5, "stock": 20})[0], 409)
        self.assertEqual(self.product_snapshot(), before)
        self.add(2)
        self.assertEqual(self.checkout()[0], 201)
        self.assertEqual(self.stock(), 6)
        self.assertEqual(self.admin_call("PATCH", path, {"expected_stock": 8, "stock": 20}, staff=True)[0], 409)
        self.assertEqual(self.stock(), 6)

    def test_stock_update_commit_failure_rolls_back(self):
        before = self.product_snapshot()
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("private-driver-error")):
            status, body, _ = self.admin_call("PATCH", "/staff/products/1/stock", {"expected_stock": 5, "stock": 10}, staff=True)
        self.assertEqual(status, 500)
        self.assertNotIn("private-driver-error", json.dumps(body))
        self.assertEqual(self.product_snapshot(), before)

    def test_stock_update_postgresql_lock_order(self):
        from sqlalchemy.dialects import postgresql
        statements = []
        original_scalar = Session.scalar

        def record(db, statement, *args, **kwargs):
            statements.append(str(statement.compile(dialect=postgresql.dialect())))
            return original_scalar(db, statement, *args, **kwargs)

        with patch.object(Session, "scalar", record):
            self.assertEqual(self.admin_call("PATCH", "/staff/products/1/stock", {"expected_stock": 5, "stock": 10}, staff=True)[0], 200)
        locks = [sql for sql in statements if "FOR UPDATE" in sql]
        self.assertEqual(len(locks), 2)
        self.assertIn("FROM users", locks[0])
        self.assertIn("FROM products", locks[1])


if __name__ == "__main__":
    original_connect = sa.engine.Engine.connect

    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("Only isolated in-memory SQLite connections are allowed")
        return original_connect(engine, *args, **kwargs)

    with patch.object(sa.engine.Engine, "connect", memory_only):
        unittest.main()
