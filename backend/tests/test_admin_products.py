"""Admin product APIs: real cookies, SQLite fixtures, no production connections."""

import asyncio
from decimal import Decimal
import json
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from test_orders_api import OrderTests
from test_auth_profile import request


class AdminProductTests(OrderTests):
    def product_call(self, method="GET", ident=1, body=None, cookie="admin-token", params=None):
        path = "/admin/products" + ("" if ident is None else f"/{ident}")

        async def app(scope, receive, send):
            scope["query_string"] = urlencode(params or {}).encode()
            await self.app(scope, receive, send)

        return asyncio.run(request(app, method, path, body,
            None if cookie is None else "lumiere_session=" + cookie))

    def product_snapshot(self):
        with Session(self.engine) as db:
            return dict(db.execute(sa.select(self.Product.__table__).where(self.Product.id == 1)).mappings().one())

    def test_product_permissions(self):
        for cookie, expected in ((None, 401), ("test-token", 403), ("staff-token", 403)):
            for method, ident, body in (("GET", None, None), ("GET", 1, None), ("PATCH", 1, {"name": "New"})):
                self.assertEqual(self.product_call(method, ident, body, cookie)[0], expected)
        with Session(self.engine) as db, db.begin():
            db.get(self.User, 3).is_active = False
        self.assertEqual(self.product_call()[0], 401)

    def test_product_reads_search_pagination_and_missing(self):
        status, body, _ = self.product_call(ident=None, params={"page_size": 1})
        self.assertEqual(status, 200)
        self.assertEqual((body["total"], body["page"], body["page_size"]), (2, 1, 1))
        self.assertEqual(body["items"][0]["id"], 1)
        self.assertEqual(self.product_call(ident=None, params={"page": 2, "page_size": 1})[1]["items"][0]["id"], 2)
        detail = self.product_call()[1]
        for term in (detail["sku"].lower(), detail["name"], "%", "_", "' OR 1=1 --"):
            result = self.product_call(ident=None, params={"q": term})
            self.assertEqual(result[0], 200)
            expected = []
            with Session(self.engine) as db:
                expected = [p.id for p in db.scalars(sa.select(self.Product).order_by(self.Product.id))
                    if term.lower() in p.name.lower() or term.lower() in p.sku.lower()]
            self.assertEqual([p["id"] for p in result[1]["items"]], expected)
        for params in ({"page": 0}, {"page_size": 101}, {"q": "x" * 256}):
            self.assertEqual(self.product_call(ident=None, params=params)[0], 422)
        self.assertEqual(self.product_call(ident=999)[0], 404)
        self.assertEqual(self.product_call("PATCH", 999, {"name": "New"})[0], 404)
        self.assertNotIn("cost_price", json.dumps(detail))
        self.assertNotIn("wholesale_price", json.dumps(detail))

    def test_product_updates_each_allowed_field_and_preserves_rest(self):
        from app.models import Category, Brand, Material, Gemstone, Collection
        before = self.product_snapshot()
        values = {"name": "  Updated name  ", "weight": "12.34"}
        for field, model in (("category_id", Category), ("brand_id", Brand),
            ("material_id", Material), ("gemstone_id", Gemstone), ("collection_id", Collection)):
            with Session(self.engine) as db:
                values[field] = db.scalar(sa.select(model.id).where(model.id != before[field]).limit(1))
        for field, value in values.items():
            previous = self.product_snapshot()
            status, body, _ = self.product_call("PATCH", body={field: value})
            self.assertEqual(status, 200, body)
            after = self.product_snapshot()
            self.assertEqual(after[field], "Updated name" if field == "name" else Decimal(value) if field == "weight" else value)
            for unchanged in previous.keys() - {field}:
                self.assertEqual(after[unchanged], previous[unchanged])
            if field.endswith("_id"):
                self.assertEqual(body[field[:-3]]["id"], value)
        after = self.product_snapshot()
        for field in ("id", "sku", "barcode", "stock", "cost_price", "wholesale_price", "sale_price"):
            self.assertEqual(before[field], after[field])

    def test_product_validation_and_foreign_keys(self):
        before = self.product_snapshot()
        cases = [{}, {"name": "   "}, {"name": "x" * 256}, {"name": None},
            {"weight": "0"}, {"weight": "1.001"}, {"weight": "100000000"},
            {"weight": "NaN"}, {"sale_price": "1"}, {"expected_sale_price": "1"},
            {"sale_price": "-1", "expected_sale_price": "0"},
            {"sale_price": "NaN", "expected_sale_price": "0"},
            {"sale_price": "10000000000000000", "expected_sale_price": "0"},
            {"sale_price": "1.001", "expected_sale_price": "0"}]
        cases += [{field: 1} for field in ("id", "sku", "barcode", "stock", "cost_price", "wholesale_price", "unknown")]
        for field in ("category_id", "brand_id", "material_id", "gemstone_id", "collection_id"):
            cases += [{field: value} for value in (999999, 0, True, "1", 1.5, None)]
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertEqual(self.product_call("PATCH", body=payload)[0], 422)
                self.assertEqual(self.product_snapshot(), before)

    def test_product_price_compare_and_snapshot(self):
        self.add()
        order = self.checkout()[1]
        old = str(self.product_snapshot()["sale_price"])
        payload = {"name": "Changed", "sale_price": "123456789.12", "expected_sale_price": old}
        status, body, _ = self.product_call("PATCH", body=payload)
        self.assertEqual(status, 200)
        self.assertEqual(body["price_vnd"], "123456789.12")
        public = self.cart_call(path="/products/1")[1]
        self.assertEqual(public["price_vnd"], "123456789.12")
        self.assertNotIn("cost_price", public)
        self.assertNotIn("wholesale_price", public)
        self.assertEqual(self.stock(), 4)
        self.assertEqual(self.cart_call(path=f"/orders/{order['id']}")[1]["items"], order["items"])
        before = self.product_snapshot()
        self.assertEqual(self.product_call("PATCH", body=payload)[0], 409)
        self.assertEqual(self.product_snapshot(), before)

    def test_product_rollback_and_lock_order(self):
        before = self.product_snapshot()
        statements = []
        def record(state):
            if state.is_select and getattr(state.statement, "_for_update_arg", None) is not None:
                statements.append(str(state.statement))
        sa.event.listen(Session, "do_orm_execute", record)
        try:
            with patch.object(Session, "commit", side_effect=SQLAlchemyError("private detail")):
                status, body, _ = self.product_call("PATCH", body={"name": "Rollback"})
        finally:
            sa.event.remove(Session, "do_orm_execute", record)
        self.assertEqual(status, 500)
        self.assertNotIn("private detail", json.dumps(body))
        self.assertEqual(self.product_snapshot(), before)
        self.assertIn("FROM users", statements[0])
        self.assertIn("FROM products", statements[1])


if __name__ == "__main__":
    original_connect = sa.engine.Engine.connect
    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("Only in-memory SQLite is allowed")
        return original_connect(engine, *args, **kwargs)
    with patch.object(sa.engine.Engine, "connect", memory_only), patch("dotenv.load_dotenv"):
        unittest.main()
