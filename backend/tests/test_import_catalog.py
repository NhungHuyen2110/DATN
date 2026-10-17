"""Isolated tests: PostgreSQL connections are forbidden; DB writes use memory only."""

import copy
from decimal import Decimal
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import import_catalog as catalog


class ImportCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load actual models without reading .env or permitting PostgreSQL access.
        with patch.dict(os.environ, {"POSTGRES_PASSWORD": "isolated-test-placeholder"}), patch("dotenv.load_dotenv"):
            cls.models = catalog.load_models()
        from app.core.database import Base
        cls.base = Base
        cls.sources = catalog.load_sources()

    def setUp(self):
        self.engine = sa.create_engine("sqlite:///:memory:")
        self.base.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)

    def test_real_source_and_model_compatibility(self):
        catalog.check_models(self.sources, self.models)
        self.assertEqual([len(self.sources[n]) for n in catalog.TABLES], [6, 4, 5, 6, 5, 500])
        self.assertEqual({r["id"] for r in self.sources["products"]}, set(range(1, 501)))
        self.assertIsInstance(self.sources["products"][0]["sale_price"], Decimal)

    def test_decimal_validation_preserves_exact_value(self):
        self.assertEqual(catalog.decimal_value("1234567890123456.78", "price"), Decimal("1234567890123456.78"))
        for value in ("NaN", "Infinity", "-1", "1.001", "10000000000000000", "invalid"):
            with self.subTest(value=value), self.assertRaises(catalog.CatalogError):
                catalog.decimal_value(value, "price")
        self.assertEqual(catalog.string("000123", "barcode", 50), "000123")

    def test_integer_and_required_values(self):
        for value in (True, "", "1.0", "-1", 2147483648):
            with self.subTest(value=value), self.assertRaises(catalog.CatalogError):
                catalog.integer(value, "ID")
        for value in (None, " ", "a\x00b", "x" * 51):
            with self.subTest(value=value), self.assertRaises(catalog.CatalogError):
                catalog.string(value, "sku", 50)

    def test_csv_rejects_count_duplicate_and_malformed_header(self):
        raw = (catalog.ROOT / "output/products.csv").read_text(encoding="utf-8-sig")
        lines = raw.splitlines()
        invalid = [
            "\n".join(lines[:-1]),
            "\n".join([lines[0], lines[1], lines[1], *lines[3:]]),
            raw.replace("ProductID,SKU", "ProductID,ProductID", 1),
            raw.replace("ProductID,SKU", "ProductID,Unknown", 1),
        ]
        for value in invalid:
            with self.subTest(), self.assertRaises(catalog.CatalogError):
                catalog.parse_products(io.StringIO(value))

    def test_duplicate_json_keys_and_unique_fields(self):
        with self.assertRaises(catalog.CatalogError):
            catalog.json_pairs([("id", 1), ("id", 2)])
        for key in ("id", "sku", "barcode"):
            rows = copy.deepcopy(self.sources["products"])
            rows[1][key] = rows[0][key]
            with self.subTest(key=key), self.assertRaises(catalog.CatalogError):
                catalog.check_unique(rows, "products")

    def test_missing_source_foreign_key(self):
        rows = copy.deepcopy(self.sources["products"])
        rows[0]["category_id"] = 9999
        with patch.object(catalog, "parse_products", return_value=rows), self.assertRaises(catalog.CatalogError):
            catalog.load_sources()

    def test_same_id_changed_field_and_unique_owner_conflicts(self):
        incoming = self.sources["products"][:1]
        for field in incoming[0]:
            old = copy.deepcopy(incoming)
            value = old[0][field]
            old[0][field] = value + " changed" if isinstance(value, str) else value + 1
            with self.subTest(field=field), self.assertRaises(catalog.CatalogError):
                catalog.plan_table("products", incoming, old)
        for field in ("sku", "barcode"):
            old = copy.deepcopy(incoming)
            old[0]["id"] = 9999
            old[0]["barcode" if field == "sku" else "sku"] = "different"
            with self.subTest(field=field), self.assertRaises(catalog.CatalogError):
                catalog.plan_table("products", incoming, old)

    def test_import_and_rerun_in_memory_preserve_all_fields(self):
        with Session(self.engine) as db, db.begin():
            plan = catalog.build_plan(db, self.sources, self.models)
            catalog.insert_plan(db, plan, self.models)
        with Session(self.engine) as db, db.begin():
            plan = catalog.build_plan(db, self.sources, self.models)
            self.assertTrue(all(not missing for missing, _ in plan.values()))
            self.assertEqual(plan["products"][1], 500)
            catalog.insert_plan(db, plan, self.models)
            table = self.models["products"].__table__
            actual = {r["id"]: dict(r) for r in db.execute(sa.select(table)).mappings()}
            self.assertEqual(actual, {r["id"]: r for r in self.sources["products"]})

    def test_product_error_rolls_back_lookup_inserts_in_memory(self):
        plan = {n: (copy.deepcopy(rows), 0) for n, rows in self.sources.items()}
        plan["products"][0][0]["stock"] = -1  # DB failure after lookup flushes.
        with self.assertRaises(IntegrityError):
            with Session(self.engine) as db, db.begin():
                catalog.insert_plan(db, plan, self.models)
        with Session(self.engine) as db:
            for name in catalog.TABLES:
                count = db.scalar(sa.select(sa.func.count()).select_from(self.models[name]))
                self.assertEqual(count, 0)

    def test_dry_run_is_read_only_and_never_calls_insert(self):
        db = MagicMock()
        factory = MagicMock()
        factory.return_value.__enter__.return_value = db
        with patch("app.core.database.SessionLocal", factory), patch.object(catalog, "build_plan", return_value={}), patch.object(catalog, "insert_plan") as insert:
            catalog.database_run(self.sources, self.models, apply=False)
        self.assertEqual(str(db.execute.call_args.args[0]), "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        insert.assert_not_called()


if __name__ == "__main__":
    # Enforce the PostgreSQL boundary for the entire test run.
    original_connect = sa.engine.Engine.connect

    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("Only an isolated in-memory database is allowed")
        return original_connect(engine, *args, **kwargs)

    with patch.object(sa.engine.Engine, "connect", memory_only):
        unittest.main()
