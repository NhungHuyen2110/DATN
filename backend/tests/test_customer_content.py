"""Wishlist/review API tests: synthetic fixtures, real cookies, SQLite memory only."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_auth_profile as profile


async def request(app, method, path, body, cookie, params):
    messages = []
    sent = False
    async def receive():
        nonlocal sent
        if sent:
            await asyncio.Future()
        sent = True
        return {"type": "http.request", "body": json.dumps(body).encode() if body is not None else b"", "more_body": False}
    async def send(message):
        messages.append(message)
    headers = [(b"content-type", b"application/json")]
    if cookie:
        headers.append((b"cookie", ("lumiere_session=" + cookie).encode()))
    await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "path": path, "raw_path": path.encode(), "root_path": "",
        "scheme": "http", "query_string": urlencode(params).encode(), "headers": headers,
        "client": ("127.0.0.1", 1234), "server": ("test", 80)}, receive, send)
    status = next(m["status"] for m in messages if m["type"] == "http.response.start")
    raw = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return status, json.loads(raw) if raw else None


class CustomerContentTests(profile.ProfileTests):
    @classmethod
    def setUpClass(cls):
        original = sa.engine.Engine.connect
        def memory_only(engine, *args, **kwargs):
            if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
                raise AssertionError("Only SQLite memory allowed")
            return original(engine, *args, **kwargs)
        for guard in (patch.object(sa.engine.Engine, "connect", memory_only), patch("dotenv.load_dotenv")):
            guard.start()
            cls.addClassCleanup(guard.stop)
        super().setUpClass()

    def setUp(self):
        super().setUp()
        from app import models
        self.models = models
        with self.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        with Session(self.engine) as db, db.begin():
            for model in (models.Category, models.Brand, models.Material, models.Gemstone, models.Collection):
                db.add(model(id=1, name="Test lookup"))
            for ident, role in ((3, "staff"), (4, "admin")):
                db.add(self.Role(id=ident, name=role))
                db.flush()
                db.add(self.User(id=ident, role_id=ident, full_name=role, email=role + "@example.com",
                    password_hash=self.password_hash, is_active=True))
            db.flush()
            for ident, token in ((2, "other"), (3, "staff"), (4, "admin")):
                db.add(self.UserSession(user_id=ident, token_hash=self.hash_token(token),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
            for ident in (1, 2):
                db.add(models.Product(id=ident, sku=f"TEST-{ident}", barcode=f"BAR-{ident}",
                    name=f"Test product {ident}", category_id=1, brand_id=1, material_id=1,
                    gemstone_id=1, collection_id=1, weight=Decimal("1.00"), sale_price=Decimal("12.34"),
                    wholesale_price=Decimal("10.00"), cost_price=Decimal("8.00"), stock=5))

    def api(self, method="GET", path="/wishlist", body=None, token="test-token", **params):
        return asyncio.run(request(self.app, method, path, body, token, params))

    def buy(self, *, user_id=1, product_id=1, status="delivered", payment_status="paid"):
        with Session(self.engine) as db, db.begin():
            order = self.models.Order(code="TEST-" + str(db.scalar(sa.select(sa.func.count()).select_from(self.models.Order))),
                user_id=user_id, recipient_name="Test", phone="0912345678", address="Test address",
                status=status, payment_status=payment_status, payment_method="cod", stock_restored=status == "cancelled",
                subtotal_vnd=Decimal("12.34"), shipping_vnd=Decimal("0.00"), discount_vnd=Decimal("0.00"), total_vnd=Decimal("12.34"))
            db.add(order)
            db.flush()
            db.add(self.models.OrderItem(order_id=order.id, product_id=product_id, sku=f"TEST-{product_id}",
                product_name="Test product", quantity=1, unit_price_vnd=Decimal("12.34"), line_total_vnd=Decimal("12.34")))
            if payment_status == "paid":
                db.add(self.models.PaymentTransaction(order_id=order.id, provider="cod", reference=f"TEST-PAY-{order.id}",
                    amount_vnd=Decimal("12.34"), status="succeeded", review_required=False,
                    verified_at=datetime.now(timezone.utc)))
            return order.id

    def add_favorite(self, product_id=1, **kwargs):
        return self.api("POST", "/wishlist/items", {"product_id": product_id}, **kwargs)

    def review(self, product_id=1, body=None, **kwargs):
        return self.api("POST", f"/products/{product_id}/reviews",
            {"rating": 5, "comment": "  Sản phẩm đẹp  "} if body is None else body, **kwargs)

    def count(self, model):
        with Session(self.engine) as db:
            return db.scalar(sa.select(sa.func.count()).select_from(model))

    def business_snapshot(self):
        with Session(self.engine) as db:
            return {model.__tablename__: list(db.execute(sa.select(model.__table__).order_by(model.id)).mappings())
                for model in (self.models.Product, self.models.Order, self.models.OrderItem, self.models.PaymentTransaction)}

    def test_wishlist_add_repeat_list_current_product_and_remove(self):
        self.assertEqual(self.api()[1]["items"], [])
        status, first = self.add_favorite()
        self.assertEqual(status, 200)
        self.assertEqual(self.add_favorite()[1]["id"], first["id"])
        self.assertEqual(self.count(self.models.WishlistItem), 1)
        self.add_favorite(2)
        self.assertEqual(self.api(page_size=1)[1]["total"], 2)
        one = self.api(page_size=1)[1]["items"][0]["product"]["id"]
        two = self.api(page_size=1, page=2)[1]["items"][0]["product"]["id"]
        self.assertNotEqual(one, two)
        with Session(self.engine) as db, db.begin():
            product = db.get(self.models.Product, 1)
            product.sale_price = Decimal("23.45")
            product.stock = 3
        item = self.add_favorite()[1]
        self.assertEqual(item["product"]["price_vnd"], "23.45")
        self.assertEqual(item["product"]["stock"], 3)
        self.assertNotIn("cost_price", json.dumps(item))
        self.assertNotIn("wholesale_price", json.dumps(item))
        self.assertEqual(self.api("DELETE", "/wishlist/items/1"),
            (200, {"message": "Đã xóa sản phẩm khỏi danh sách yêu thích"}))
        self.assertEqual(self.api("DELETE", "/wishlist/items/1")[0], 404)

    def test_wishlist_owner_missing_and_validation(self):
        self.add_favorite()
        self.assertEqual(self.api(token="other")[1]["total"], 0)
        self.assertEqual(self.api("DELETE", "/wishlist/items/1", token="other")[0], 404)
        self.assertEqual(self.api()[1]["total"], 1)
        self.assertEqual(self.add_favorite(999)[0], 404)
        self.assertEqual(self.api("DELETE", "/wishlist/items/999")[0], 404)
        for value in (True, 1.0, "1", 0, -1, None, 2147483648):
            self.assertEqual(self.add_favorite(value)[0], 422)
        for field in ("user_id", "stock", "price", "id"):
            self.assertEqual(self.api("POST", "/wishlist/items", {"product_id": 1, field: 2})[0], 422)

    def test_customer_content_all_private_routes_permissions(self):
        routes = (("GET", "/wishlist", None), ("POST", "/wishlist/items", {"product_id": 1}),
            ("DELETE", "/wishlist/items/1", None), ("GET", "/reviews/my", None),
            ("POST", "/products/1/reviews", {"rating": 5, "comment": "Test"}),
            ("PATCH", "/reviews/1", {"rating": 4}), ("DELETE", "/reviews/1", None))
        for token, expected in ((None, 401), ("wrong", 401), ("staff", 403), ("admin", 403)):
            for method, path, body in routes:
                self.assertEqual(self.api(method, path, body, token=token)[0], expected, (token, path))
        for token in (None, "test-token", "staff", "admin"):
            self.assertEqual(self.api(path="/products/1/reviews", token=token)[0], 200)

    def test_customer_content_expired_session_and_locked_account(self):
        with Session(self.engine) as db, db.begin():
            session = db.scalar(sa.select(self.UserSession).where(self.UserSession.user_id == 1))
            session.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        self.assertEqual(self.add_favorite()[0], 401)
        self.assertEqual(self.review()[0], 401)
        with Session(self.engine) as db, db.begin():
            db.get(self.User, 2).is_active = False
        self.assertEqual(self.api(token="other")[0], 401)
        self.assertEqual(self.review(token="other")[0], 401)

    def test_reviews_create_public_edit_delete_and_private_data(self):
        self.buy()
        status, review = self.review()
        self.assertEqual(status, 201)
        self.assertEqual(review["comment"], "Sản phẩm đẹp")
        self.assertEqual(set(review), {"id", "product_id", "rating", "comment", "author_display_name", "created_at", "updated_at"})
        self.assertEqual(self.api(path="/products/1/reviews", token=None)[1]["items"], [review])
        self.assertEqual(self.api(path="/reviews/my")[1]["items"], [review])
        self.assertEqual(self.api(path="/reviews/my", token="other")[1]["items"], [])
        path = f"/reviews/{review['id']}"
        self.assertEqual(self.api("PATCH", path, {"rating": 3})[1]["rating"], 3)
        self.assertEqual(self.api("PATCH", path, {"comment": " <b>plain text</b> "})[1]["comment"], "<b>plain text</b>")
        self.assertEqual(self.api("DELETE", path), (200, {"message": "Đã xóa đánh giá thành công"}))
        self.assertEqual(self.api("DELETE", path)[0], 404)

    def test_reviews_purchase_requirement_all_states(self):
        self.assertEqual(self.review()[0], 403)
        self.buy(user_id=2)
        self.buy(product_id=2)
        self.assertEqual(self.review()[0], 403)
        ident = self.buy(status="pending", payment_status="unpaid")
        for status in ("pending", "confirmed", "packing", "shipping", "cancelled", "delivered"):
            for payment_status in ("unpaid", "paid", "refunded"):
                if (status, payment_status) == ("delivered", "paid"):
                    continue
                with Session(self.engine) as db, db.begin():
                    order = db.get(self.models.Order, ident)
                    order.status, order.payment_status = status, payment_status
                    order.stock_restored = status == "cancelled"
                result = self.review()
                self.assertEqual(result[0], 403, (status, payment_status))
                self.assertIn("delivered + paid", result[1]["detail"])
        self.buy()
        self.assertEqual(self.review()[0], 201)

    def test_reviews_duplicate_ownership_and_refunded_after_creation(self):
        ident = self.buy()
        self.buy()
        review = self.review()[1]
        self.assertEqual(self.review()[0], 409)
        path = f"/reviews/{review['id']}"
        self.assertEqual(self.api("PATCH", path, {"rating": 1}, token="other")[0], 404)
        self.assertEqual(self.api("DELETE", path, token="other")[0], 404)
        with Session(self.engine) as db, db.begin():
            db.execute(sa.update(self.models.Order).where(self.models.Order.user_id == 1).values(payment_status="refunded"))
        self.assertEqual(self.api(path="/products/1/reviews")[1]["total"], 1)
        self.assertEqual(self.api("PATCH", path, {"comment": "Still editable"})[0], 200)
        self.assertEqual(self.api("DELETE", path)[0], 200)

    def test_reviews_validation_unknown_products_and_pagination(self):
        self.buy()
        for value in (True, False, 1.0, "5", None, 0, 6):
            self.assertEqual(self.review(body={"rating": value, "comment": "OK"})[0], 422)
        for value in ("", "   ", "a" * 2001, None, 5, "bad\x00comment"):
            self.assertEqual(self.review(body={"rating": 5, "comment": value})[0], 422)
        for field in ("user_id", "product_id", "order_id", "verified_purchase", "id"):
            self.assertEqual(self.review(body={"rating": 5, "comment": "OK", field: 1})[0], 422)
        self.assertEqual(self.review(999)[0], 404)
        self.assertEqual(self.api(path="/products/999/reviews")[0], 404)
        ident = self.review(body={"rating": 1, "comment": "  " + "a" * 2000 + "  "})[1]["id"]
        for payload in ({}, {"rating": None}, {"comment": None}, {"rating": "1"}, {"rating": True}, {"comment": " "}, {"user_id": 2}):
            self.assertEqual(self.api("PATCH", f"/reviews/{ident}", payload)[0], 422)
        self.buy(user_id=2)
        self.assertEqual(self.review(token="other")[0], 201)
        one = self.api(path="/products/1/reviews", page_size=1)[1]
        two = self.api(path="/products/1/reviews", page=2, page_size=1)[1]
        self.assertEqual(one["total"], 2)
        self.assertNotEqual(one["items"][0]["id"], two["items"][0]["id"])
        for path in ("/wishlist", "/products/1/reviews", "/reviews/my"):
            for params in ({"page": 0}, {"page_size": 101}, {"page": "bad"}):
                self.assertEqual(self.api(path=path, **params)[0], 422)

    def test_customer_content_rollback_and_business_data_unchanged(self):
        self.buy()
        before = self.business_snapshot()
        for operation in (self.add_favorite, self.review):
            with patch.object(Session, "commit", side_effect=SQLAlchemyError("private database details")):
                code, body = operation()
            self.assertEqual(code, 500)
            self.assertNotIn("private database", json.dumps(body))
        self.assertEqual(self.count(self.models.WishlistItem), 0)
        self.assertEqual(self.count(self.models.ProductReview), 0)
        self.add_favorite()
        review = self.review()[1]
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("hidden")):
            self.assertEqual(self.api("PATCH", f"/reviews/{review['id']}", {"rating": 1})[0], 500)
            self.assertEqual(self.api("DELETE", f"/reviews/{review['id']}")[0], 500)
            self.assertEqual(self.api("DELETE", "/wishlist/items/1")[0], 500)
        self.assertEqual(self.api(path="/reviews/my")[1]["items"][0]["rating"], 5)
        self.assertEqual(self.api()[1]["total"], 1)
        self.assertEqual(self.api("DELETE", "/wishlist/items/1")[0], 200)
        self.assertEqual(self.api("DELETE", f"/reviews/{review['id']}")[0], 200)
        self.assertEqual(self.business_snapshot(), before)

    def test_customer_content_unique_constraints_and_lock_order(self):
        self.buy()
        statements = []
        def record(state):
            if state.is_select and getattr(state.statement, "_for_update_arg", None) is not None:
                from sqlalchemy.dialects import postgresql
                statements.append(str(state.statement.compile(dialect=postgresql.dialect())))
        sa.event.listen(Session, "do_orm_execute", record)
        try:
            self.add_favorite()
            self.review()
        finally:
            sa.event.remove(Session, "do_orm_execute", record)
        self.assertIn("FROM users", statements[0])
        self.assertIn("FROM users", statements[1])
        self.assertIn("FROM orders", statements[2])
        for model, kwargs in ((self.models.WishlistItem, {}), (self.models.ProductReview, {"rating": 5, "comment": "dup"})):
            with self.assertRaises(IntegrityError), Session(self.engine) as db, db.begin():
                db.add(model(user_id=1, product_id=1, **kwargs))
        with patch.object(Session, "commit", side_effect=IntegrityError("private", {}, Exception())):
            self.assertEqual(self.add_favorite(2)[0], 409)

    def test_delete_success_openapi_documents_json_200(self):
        schema = self.api(path="/openapi.json", token=None)[1]
        for path, message in (
            ("/wishlist/items/{product_id}", "Đã xóa sản phẩm khỏi danh sách yêu thích"),
            ("/reviews/{id}", "Đã xóa đánh giá thành công"),
        ):
            responses = schema["paths"][path]["delete"]["responses"]
            self.assertNotIn("204", responses)
            content = responses["200"]["content"]["application/json"]
            self.assertEqual(content["example"], {"message": message})
            self.assertEqual(content["schema"]["$ref"], "#/components/schemas/DeleteMessageResponse")
        response = schema["components"]["schemas"]["DeleteMessageResponse"]
        self.assertEqual(response["required"], ["message"])

    def test_customer_content_migration_offline_and_sqlite(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        backend = Path(__file__).resolve().parents[1]
        scripts = ScriptDirectory.from_config(Config(str(backend / "alembic.ini")))
        self.assertEqual(scripts.get_heads(), ["20261017_0005"])
        revision = scripts.get_revision("20261017_0005").module
        self.assertEqual(revision.down_revision, "20261016_0004")
        output = io.StringIO()
        context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
        with Operations.context(context):
            revision.upgrade()
        sql = output.getvalue()
        for name in ("wishlist_items", "product_reviews", "uq_wishlist_user_product", "ck_reviews_rating"):
            self.assertIn(name, sql)
        for forbidden in ("DROP ", "DELETE FROM ", "UPDATE ", "ALTER TABLE products", "INSERT INTO "):
            self.assertNotIn(forbidden, sql)
        engine = sa.create_engine("sqlite:///:memory:")
        self.addCleanup(engine.dispose)
        self.base.metadata.create_all(engine, tables=[table for table in self.base.metadata.sorted_tables
            if table.name not in {"wishlist_items", "product_reviews"}])
        with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            revision.upgrade()
        inspector = sa.inspect(engine)
        for name in ("wishlist_items", "product_reviews"):
            self.assertEqual({fk["referred_table"] for fk in inspector.get_foreign_keys(name)}, {"users", "products"})
            self.assertTrue(any(item["column_names"] == ["user_id", "product_id"] for item in inspector.get_unique_constraints(name)))


if __name__ == "__main__":
    unittest.main()
