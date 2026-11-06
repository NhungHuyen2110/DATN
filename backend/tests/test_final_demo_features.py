"""Tests for final-demo enhancements with isolated in-memory SQLite only."""

import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


class FinalDemoFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {"POSTGRES_DB": "test_only", "POSTGRES_PASSWORD": "test_placeholder"}), patch("dotenv.load_dotenv"):
            from app.core.database import Base
            import app.models
            cls.Base = Base

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.Base.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)

    def test_contact_is_persisted_and_admin_can_update_status(self):
        from app.routers.contact import ContactCreate, ContactStatus, submit, inbox, change_status
        with Session(self.engine) as db:
            response = submit(ContactCreate(full_name="Customer Example", email="customer@example.com",
                topic="Tư vấn", message="Tôi muốn được tư vấn về nhẫn cưới."), db)
            self.assertEqual(response["status"], "new")
            rows = inbox(None, db, page=1, page_size=20)
            self.assertEqual(rows["total"], 1)
            self.assertEqual(rows["items"][0]["email"], "customer@example.com")
            edited = change_status(response["id"], ContactStatus(status="in_progress"), None, db)
            self.assertEqual(edited["status"], "in_progress")

    def test_admin_taxonomy_create_rename_delete_unused(self):
        from app.routers.taxonomy import LookupWrite, add, change, remove, rows
        with Session(self.engine) as db:
            brand = add(db, "brands", LookupWrite(name="Test Brand"))
            self.assertEqual(brand["product_count"], 0)
            renamed = change(db, "brands", brand["id"], LookupWrite(name="New Brand"))
            self.assertEqual(renamed["name"], "New Brand")
            self.assertEqual(len(rows(db, "brands")), 1)
            remove(db, "brands", brand["id"])
            self.assertEqual(len(rows(db, "brands")), 0)

    def test_shipping_opt_in_and_free_threshold(self):
        from app.services.shipping import calculate_shipping
        with patch.dict(os.environ, {"SHIPPING_FLAT_VND":"30000", "SHIPPING_FREE_FROM_VND":"2000000"}):
            self.assertEqual(calculate_shipping(Decimal("1000000")), Decimal("30000"))
            self.assertEqual(calculate_shipping(Decimal("2500000")), Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
