"""OPT-IN races on a dedicated PostgreSQL test database, never lumiere_db.

Not part of discovery. Set COUPON_TEST_DATABASE_URL to a database whose name
ends in _test, then run this file explicitly. Creates/removes only a unique
fixture schema; no migrations, real payments or existing application data.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
import sys
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@unittest.skipUnless(os.environ.get("COUPON_TEST_DATABASE_URL"), "Dedicated PostgreSQL test URL not supplied")
class PostgreSQLCouponRaces(unittest.TestCase):
    def setUp(self):
        url = sa.engine.make_url(os.environ["COUPON_TEST_DATABASE_URL"])
        if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
            raise RuntimeError("Only a dedicated PostgreSQL database ending in _test is allowed")
        with patch("dotenv.load_dotenv"), patch.dict(os.environ, {"POSTGRES_PASSWORD": "test-placeholder"}):
            from app.core.database import Base
            from app.models import Cart, CartItem, Coupon, CouponUsage, Order, Product, Role, User
            from app.import_catalog import insert_plan, load_models, load_sources
        self.Cart, self.CartItem, self.Coupon = Cart, CartItem, Coupon
        self.Usage, self.Order, self.Product = CouponUsage, Order, Product
        raw = sa.create_engine(url, connect_args={"options": "-c statement_timeout=10000 -c lock_timeout=5000"})
        self.addCleanup(raw.dispose)
        schema = "coupon_race_" + uuid4().hex
        with raw.begin() as conn:
            conn.execute(sa.schema.CreateSchema(schema))
        def cleanup():
            with raw.begin() as conn:
                conn.execute(sa.schema.DropSchema(schema, cascade=True))
        self.addCleanup(cleanup)
        self.engine = raw.execution_options(schema_translate_map={None: schema})
        Base.metadata.create_all(self.engine)
        sources = load_sources()
        sources["products"] = sources["products"][:2]
        for product in sources["products"]:
            product["stock"] = 5
        with Session(self.engine) as db, db.begin():
            insert_plan(db, {key: (rows, 0) for key, rows in sources.items()}, load_models())
            db.add(Role(id=1, name="customer"))
            db.flush()
            for ident in (1, 2):
                db.add(User(id=ident, role_id=1, full_name="Race Customer", email=f"race{ident}@example.com",
                            password_hash="unused-test-only", is_active=True))
                db.flush()
                cart = Cart(user_id=ident)
                db.add(cart)
                db.flush()
                db.add(CartItem(cart_id=cart.id, product_id=ident, quantity=1))
                db.get(Product, ident).sale_price = Decimal("10000.00")
            db.add(Coupon(code="RACE10", discount_type="percent", discount_value=Decimal(10),
                          min_order_vnd=Decimal(0), used_count=0, usage_limit=1,
                          starts_at=datetime.now(timezone.utc) - timedelta(days=1),
                          ends_at=datetime.now(timezone.utc) + timedelta(days=1), is_active=True))

    def race(self, users):
        from app.services.orders import checkout
        from app.schemas.order import CheckoutRequest
        from fastapi import HTTPException
        barrier = Barrier(2)
        def worker(user_id):
            with Session(self.engine, autoflush=False) as db:
                # Acquire distinct physical connections before both workers start.
                pid = db.scalar(sa.text("SELECT pg_backend_pid()"))
                barrier.wait(timeout=10)
                try:
                    order = checkout(db, user_id, CheckoutRequest(recipient_name="Race Customer",
                        phone="0912345678", address="Test address", coupon_code="RACE10"))
                    return pid, 201, order
                except HTTPException as exc:
                    return pid, exc.status_code, None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, users))
        self.assertNotEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(row[1] for row in results), [201, 409])
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(sa.select(sa.func.count()).select_from(self.Order)), 1)
            self.assertEqual(db.scalar(sa.select(sa.func.count()).select_from(self.Usage)), 1)
            self.assertEqual(db.get(self.Coupon, 1).used_count, 1)
            self.assertEqual(sum(db.scalars(sa.select(self.Product.stock))), 9)

    def test_two_customers_last_use(self):
        self.race((1, 2))

    def test_same_customer_two_checkouts(self):
        with Session(self.engine) as db, db.begin():
            db.get(self.Coupon, 1).usage_limit = None
        self.race((1, 1))


if __name__ == "__main__":
    unittest.main()
