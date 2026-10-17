"""Exercise the actual FastAPI app via ASGI; no server or PostgreSQL access."""

import asyncio
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def asgi_get(app, path, params):
    messages = []
    sent_request = False

    async def receive():
        nonlocal sent_request
        if not sent_request:
            sent_request = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.Future()

    async def send(message):
        messages.append(message)

    await app({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": path,
        "raw_path": path.encode(), "root_path": "",
        "query_string": urlencode(params or {}).encode(),
        "headers": [], "client": ("127.0.0.1", 12345), "server": ("test", 80),
    }, receive, send)
    status = next(m["status"] for m in messages if m["type"] == "http.response.start")
    raw = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return status, json.loads(raw)


class CatalogAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the real source solely as isolated test fixtures, not production import.
        with patch.dict(os.environ, {"POSTGRES_PASSWORD": "isolated-test-placeholder"}), patch("dotenv.load_dotenv"):
            from app.main import app
            from app.core.database import Base, get_db
            from app.import_catalog import load_sources, load_models, insert_plan
        cls.app = app
        cls.engine = sa.create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(cls.engine)
        cls.sources = load_sources()
        with Session(cls.engine) as db, db.begin():
            insert_plan(db, {n: (rows, 0) for n, rows in cls.sources.items()}, load_models())

        def override_db():
            with Session(cls.engine) as db:
                yield db

        cls.get_db = get_db
        app.dependency_overrides[get_db] = override_db

    @classmethod
    def tearDownClass(cls):
        cls.app.dependency_overrides.pop(cls.get_db, None)
        cls.engine.dispose()

    def get(self, path, **params):
        return asyncio.run(asgi_get(self.app, path, params))

    def test_lookup_json_and_order(self):
        for name, count in (("categories", 6), ("brands", 4)):
            with self.subTest(name=name):
                status, body = self.get("/" + name)
                self.assertEqual(status, 200)
                self.assertEqual(len(body), count)
                self.assertEqual(body, sorted(self.sources[name], key=lambda r: r["id"]))

    def test_default_pagination_and_public_json(self):
        status, body = self.get("/products")
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {"items", "page", "page_size", "total"})
        self.assertEqual((body["page"], body["page_size"], body["total"]), (1, 20, 500))
        self.assertEqual([p["id"] for p in body["items"]], list(range(1, 21)))
        item = body["items"][0]
        self.assertEqual(set(item), {"id", "sku", "barcode", "name", "category", "brand", "material", "gemstone", "collection", "weight", "price_vnd", "stock"})
        self.assertIsInstance(item["price_vnd"], str)
        self.assertEqual(Decimal(item["price_vnd"]), self.sources["products"][0]["sale_price"])

    def test_pagination_boundaries_and_no_overlap(self):
        _, one = self.get("/products", page_size=100)
        _, two = self.get("/products", page=2, page_size=100)
        self.assertEqual(len(one["items"]), 100)
        self.assertEqual(two["items"][0]["id"], 101)
        self.assertFalse({p["id"] for p in one["items"]} & {p["id"] for p in two["items"]})
        _, empty = self.get("/products", page=26)
        self.assertEqual(empty["items"], [])
        self.assertEqual(empty["total"], 500)

    def test_search_name_sku_and_literal_wildcards(self):
        for term in ("Angel", "sp000001", "%", "_", "' OR 1=1 --"):
            with self.subTest(term=term):
                status, body = self.get("/products", q=term, page_size=100)
                expected = [p for p in self.sources["products"] if term.lower() in p["name"].lower() or term.lower() in p["sku"].lower()]
                self.assertEqual(status, 200)
                self.assertEqual(body["total"], len(expected))
                self.assertEqual([p["id"] for p in body["items"]], [p["id"] for p in expected[:100]])

    def test_all_five_filters_and_combination(self):
        sample = self.sources["products"][0]
        keys = ("category_id", "brand_id", "material_id", "gemstone_id", "collection_id")
        cases = [{key: sample[key]} for key in keys] + [{key: sample[key] for key in keys}]
        for filters in cases:
            with self.subTest(filters=filters):
                status, body = self.get("/products", page_size=100, **filters)
                expected = [p for p in self.sources["products"] if all(p[k] == v for k, v in filters.items())]
                self.assertEqual(status, 200)
                self.assertEqual(body["total"], len(expected))
                self.assertEqual([p["id"] for p in body["items"]], [p["id"] for p in expected[:100]])

    def test_price_bounds_and_combined_search(self):
        sample = self.sources["products"][0]
        price = sample["sale_price"]
        status, body = self.get("/products", min_price=str(price), max_price=str(price), q=sample["sku"])
        self.assertEqual(status, 200)
        self.assertEqual([p["id"] for p in body["items"]], [sample["id"]])
        _, body = self.get("/products", max_price="0")
        self.assertEqual(body["total"], 0)

    def test_invalid_queries_return_422(self):
        cases = [{key: value} for key in ("page", "page_size", "category_id", "brand_id", "material_id", "gemstone_id", "collection_id") for value in ("0", "-1", "1.5", "abc")]
        cases += [{"page_size": "101"}, {"category_id": "2147483648"}, {"min_price": "-1"}, {"min_price": "NaN"}, {"max_price": "Infinity"}, {"min_price": "1.001"}, {"max_price": "10000000000000000"}, {"min_price": "10", "max_price": "9"}, {"q": "a" * 256}]
        for params in cases:
            with self.subTest(params=params):
                status, body = self.get("/products", **params)
                self.assertEqual(status, 422)
                self.assertIn("detail", body)

    def test_detail_original_id_related_objects_and_404(self):
        status, body = self.get("/products/1")
        self.assertEqual(status, 200)
        self.assertEqual(body["id"], 1)
        for key in ("category", "brand", "material", "gemstone", "collection"):
            self.assertEqual(set(body[key]), {"id", "name"})
            self.assertEqual(body[key]["id"], self.sources["products"][0][key + "_id"])
        self.assertEqual(self.get("/products/501")[0], 404)
        self.assertEqual(self.get("/products/0")[0], 422)
        self.assertEqual(self.get("/products/abc")[0], 422)
        self.assertEqual(self.get("/products", category_id=9999)[1]["total"], 0)

    def test_decimal_serialization_does_not_use_float(self):
        from app.schemas.catalog import ProductResponse
        _, item = self.get("/products/1")
        item["sale_price"] = Decimal("1234567890123456.78")
        body = json.loads(ProductResponse.model_validate(item).model_dump_json())
        self.assertEqual(body["price_vnd"], "1234567890123456.78")

    def test_read_only_queries_and_postgresql_compilation(self):
        from app.models import Product
        from app.routers.catalog import public_product_query
        from sqlalchemy.dialects import postgresql
        statements = []

        def record(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        sa.event.listen(self.engine, "before_cursor_execute", record)
        try:
            self.assertEqual(self.get("/products", page_size=100)[0], 200)
        finally:
            sa.event.remove(self.engine, "before_cursor_execute", record)
        self.assertEqual(len(statements), 2)  # Count + rows with all five related objects.
        self.assertTrue(all(sql.lstrip().upper().startswith("SELECT") for sql in statements))
        compiled = str(public_product_query().where(
            Product.name.icontains("Angel", autoescape=True)
        ).compile(dialect=postgresql.dialect()))
        self.assertIn("ILIKE", compiled)
        self.assertNotIn("cost_price", compiled)
        self.assertNotIn("wholesale_price", compiled)

    def test_auth_routes_and_openapi_have_no_conflicts(self):
        status, schema = self.get("/openapi.json")
        self.assertEqual(status, 200)
        paths = schema["paths"]
        for path in ("/categories", "/brands", "/products", "/products/{id}"):
            self.assertIn("get", paths[path])
        for path in ("/auth/register", "/auth/login", "/auth/logout"):
            self.assertIn("post", paths[path])
        self.assertEqual(self.get("/auth/me")[0], 401)
        pairs = [(route.path, method) for route in self.app.routes if hasattr(route, "methods") for method in route.methods]
        self.assertEqual(len(pairs), len(set(pairs)))


if __name__ == "__main__":
    original_connect = sa.engine.Engine.connect

    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("PostgreSQL and disk databases are forbidden in these tests")
        return original_connect(engine, *args, **kwargs)

    with patch.object(sa.engine.Engine, "connect", memory_only):
        unittest.main()
