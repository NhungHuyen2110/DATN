"""Cart API tests with real Auth cookies and isolated, memory-only fixtures."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_auth_profile as profile


class CartTests(profile.ProfileTests):
    # Inherit the Auth regression cases and its real-cookie, memory-only setup.
    def setUp(self):
        super().setUp()
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        from app.import_catalog import load_sources, load_models, insert_plan
        from app.models import Cart, CartItem, Product
        self.Cart, self.CartItem, self.Product = Cart, CartItem, Product
        sources = load_sources()
        sources["products"] = sources["products"][:2]
        sources["products"][0]["stock"] = 5
        sources["products"][1]["stock"] = 3
        with Session(self.engine) as db, db.begin():
            insert_plan(db, {n: (rows, 0) for n, rows in sources.items()}, load_models())
            db.add(self.UserSession(user_id=2, token_hash=self.hash_token("second-token"), expires_at=datetime.now(timezone.utc) + timedelta(days=1)))

    def cart_call(self, method="GET", path="/cart", body=None, other=False, anonymous=False):
        cookie = None if anonymous else "lumiere_session=" + ("second-token" if other else "test-token")
        return self.call(method=method, path=path, body=body, cookie=cookie)

    def add(self, quantity=1, product_id=1, **kwargs):
        return self.cart_call("POST", "/cart/items", {"product_id": product_id, "quantity": quantity}, **kwargs)

    def test_empty_get_does_not_create_cart(self):
        status, body, _ = self.cart_call()
        self.assertEqual(status, 200)
        self.assertEqual(body, {"id": None, "items": [], "total_quantity": 0, "subtotal_vnd": "0.00"})
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(sa.select(sa.func.count()).select_from(self.Cart)), 0)

    def test_every_cart_route_requires_login(self):
        for method, path, payload in (("GET", "/cart", None), ("POST", "/cart/items", {"product_id": 1, "quantity": 1}), ("PATCH", "/cart/items/1", {"quantity": 1}), ("DELETE", "/cart/items/1", None)):
            with self.subTest(method=method):
                self.assertEqual(self.cart_call(method, path, payload, anonymous=True)[0], 401)

    def test_duplicate_add_accumulates_and_uses_db_prices(self):
        self.assertEqual(self.add(2)[0], 200)
        status, body, _ = self.add(3)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["items"]), 1)
        item = body["items"][0]
        self.assertEqual(item["quantity"], 5)
        self.assertEqual(Decimal(item["line_total_vnd"]), Decimal(item["unit_price_vnd"]) * 5)
        self.assertEqual(body["subtotal_vnd"], item["line_total_vnd"])
        self.assertTrue(item["in_stock"])
        self.assertNotIn("cost_price", json.dumps(body))
        self.assertNotIn("password_hash", json.dumps(body))
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(sa.select(sa.func.count()).select_from(self.CartItem)), 1)
            self.assertEqual(db.get(self.Product, 1).stock, 5)

    def test_stock_conflict_rolls_back_and_no_cart_on_failed_first_add(self):
        self.assertEqual(self.add(6)[0], 409)
        self.assertIsNone(self.cart_call()[1]["id"])
        self.add(4)
        self.assertEqual(self.add(2)[0], 409)
        self.assertEqual(self.cart_call()[1]["items"][0]["quantity"], 4)
        with Session(self.engine) as db, db.begin():
            db.get(self.Product, 2).stock = 0
        self.assertEqual(self.add(product_id=2)[0], 409)

    def test_patch_replaces_quantity_and_delete_returns_cart(self):
        _, body, _ = self.add(3)
        item_id = body["items"][0]["id"]
        path = f"/cart/items/{item_id}"
        self.assertEqual(self.cart_call("PATCH", path, {"quantity": 2})[1]["total_quantity"], 2)
        self.assertEqual(self.cart_call("PATCH", path, {"quantity": 6})[0], 409)
        status, body, _ = self.cart_call("DELETE", path)
        self.assertEqual(status, 200)
        self.assertEqual(body["items"], [])
        self.assertEqual(body["subtotal_vnd"], "0.00")
        self.assertEqual(self.cart_call("DELETE", path)[0], 404)

    def test_other_user_cannot_access_or_change_items(self):
        _, body, _ = self.add(2)
        path = f"/cart/items/{body['items'][0]['id']}"
        self.assertEqual(self.cart_call(other=True)[1]["items"], [])
        self.add(product_id=2, other=True)
        self.assertEqual(self.cart_call("PATCH", path, {"quantity": 1}, other=True)[0], 404)
        self.assertEqual(self.cart_call("DELETE", path, other=True)[0], 404)
        self.assertEqual(self.cart_call()[1]["total_quantity"], 2)

    def test_invalid_inputs_and_forged_prices_rejected(self):
        for field in ("product_id", "quantity"):
            for value in (0, -1, True, 1.5, "1", None, 2147483648):
                payload = {"product_id": 1, "quantity": 1, field: value}
                with self.subTest(payload=payload):
                    self.assertEqual(self.cart_call("POST", "/cart/items", payload)[0], 422)
        for field in ("price", "unit_price_vnd", "user_id", "cart_id"):
            self.assertEqual(self.cart_call("POST", "/cart/items", {"product_id": 1, "quantity": 1, field: 1})[0], 422)
        self.assertEqual(self.cart_call("POST", "/cart/items", {})[0], 422)
        self.assertEqual(self.cart_call("PATCH", "/cart/items/1", {"quantity": 0})[0], 422)
        self.assertEqual(self.cart_call("PATCH", "/cart/items/1", {"quantity": 1, "product_id": 2})[0], 422)
        self.assertEqual(self.cart_call("DELETE", "/cart/items/abc")[0], 422)
        self.assertEqual(self.cart_call("DELETE", "/cart/items/0")[0], 422)

    def test_missing_products_and_items(self):
        self.assertEqual(self.add(product_id=999)[0], 404)
        self.assertEqual(self.cart_call("PATCH", "/cart/items/999", {"quantity": 1})[0], 404)
        self.assertEqual(self.cart_call("DELETE", "/cart/items/999")[0], 404)

    def test_current_price_and_reduced_stock_are_visible_without_reserving(self):
        self.add(3)
        with Session(self.engine) as db, db.begin():
            product = db.get(self.Product, 1)
            product.sale_price = Decimal("123.45")
            product.stock = 1
        body = self.cart_call()[1]
        self.assertEqual(body["subtotal_vnd"], "370.35")
        self.assertFalse(body["items"][0]["in_stock"])
        self.assertEqual(self.add()[0], 409)
        item_id = body["items"][0]["id"]
        self.assertEqual(self.cart_call("PATCH", f"/cart/items/{item_id}", {"quantity": 1})[0], 200)

    def test_commit_failure_rolls_back_cart_and_item(self):
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("hidden details")):
            status, body, _ = self.add()
        self.assertEqual(status, 500)
        self.assertNotIn("hidden details", json.dumps(body))
        self.assertIsNone(self.cart_call()[1]["id"])

    def test_integrity_conflict_rolls_back(self):
        with patch.object(Session, "commit", side_effect=IntegrityError("hidden", {}, Exception())):
            self.assertEqual(self.add()[0], 409)
        self.assertIsNone(self.cart_call()[1]["id"])

    def test_db_unique_and_quantity_constraints(self):
        self.add()
        with self.assertRaises(IntegrityError):
            with Session(self.engine) as db, db.begin():
                cart = db.scalar(sa.select(self.Cart))
                db.add(self.CartItem(cart_id=cart.id, product_id=1, quantity=1))
        with self.assertRaises(IntegrityError):
            with Session(self.engine) as db, db.begin():
                cart = db.scalar(sa.select(self.Cart))
                db.add(self.CartItem(cart_id=cart.id, product_id=2, quantity=0))
        with self.assertRaises(IntegrityError):
            with Session(self.engine) as db, db.begin():
                db.add(self.Cart(user_id=1))
        with self.assertRaises(IntegrityError):
            with Session(self.engine) as db, db.begin():
                db.execute(sa.delete(self.Product).where(self.Product.id == 1))

    def test_postgresql_lock_order_and_new_migration_offline(self):
        from sqlalchemy.dialects import postgresql
        statements = []
        original_scalar = Session.scalar

        def record(db, statement, *args, **kwargs):
            statements.append(str(statement.compile(dialect=postgresql.dialect())))
            return original_scalar(db, statement, *args, **kwargs)

        with patch.object(Session, "scalar", record):
            self.assertEqual(self.add()[0], 200)
        locks = [sql for sql in statements if "FOR UPDATE" in sql]
        self.assertEqual(len(locks), 2)
        self.assertIn("FROM users", locks[0])
        self.assertIn("FROM products", locks[1])

        from alembic import command
        from alembic.config import Config
        output = io.StringIO()
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output)
        command.upgrade(config, "20261015_0001:20261016_0002", sql=True)
        sql = output.getvalue()
        self.assertLess(sql.index("CREATE TABLE carts"), sql.index("CREATE TABLE cart_items"))
        self.assertIn("UNIQUE (cart_id, product_id)", sql)
        self.assertIn("quantity > 0", sql)
        self.assertNotIn("DROP TABLE", sql)
        self.assertNotIn("DELETE FROM", sql)


if __name__ == "__main__":
    original_connect = sa.engine.Engine.connect

    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("Only isolated in-memory SQLite connections are allowed")
        return original_connect(engine, *args, **kwargs)

    with patch.object(sa.engine.Engine, "connect", memory_only):
        unittest.main()
