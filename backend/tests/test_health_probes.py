"""Process liveness must remain independent of database readiness."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app


class HealthProbeTests(unittest.TestCase):
    def test_exhausted_pool_keeps_liveness_and_recovers(self):
        from concurrent.futures import ThreadPoolExecutor
        import sqlalchemy as sa
        from sqlalchemy.pool import QueuePool

        engine = sa.create_engine("sqlite:///:memory:", poolclass=QueuePool, pool_size=1,
                                  max_overflow=0, pool_timeout=0.05,
                                  connect_args={"check_same_thread": False})
        self.addCleanup(engine.dispose)
        client = TestClient(app)
        with patch("app.core.database.engine", engine):
            with engine.connect(), ThreadPoolExecutor(max_workers=2) as workers:
                ready = workers.submit(client.get, "/health/ready")
                live = workers.submit(client.get, "/health/live")
                self.assertEqual(ready.result().status_code, 503)
                self.assertEqual(live.result().status_code, 200)
            self.assertEqual(client.get("/health/ready").status_code, 200)

    def test_database_wait_limits_without_connecting(self):
        import os
        from pathlib import Path
        import runpy

        source = Path(__file__).resolve().parents[1] / "app/core/database.py"
        with patch.dict(os.environ, {"POSTGRES_DB": "test_only", "POSTGRES_PASSWORD": "test_only"}, clear=True), \
                patch("dotenv.load_dotenv"), patch("sqlalchemy.create_engine") as create:
            runpy.run_path(str(source))
        options = create.call_args.kwargs
        self.assertLessEqual(options["pool_timeout"], 5)
        self.assertEqual(options["connect_args"]["connect_timeout"], 5)
        self.assertIn("statement_timeout=15000", options["connect_args"]["options"])
        self.assertIn("lock_timeout=5000", options["connect_args"]["options"])
        create.return_value.connect.assert_not_called()

    def test_liveness_never_checks_database(self):
        with patch("app.main.check_database", side_effect=AssertionError("must not connect")) as database:
            response = TestClient(app).get("/health/live")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),{"status":"alive"})
        database.assert_not_called()

    def test_readiness_reports_failure_without_leaking_details(self):
        client = TestClient(app)
        with patch("app.main.check_database", side_effect=RuntimeError("secret-dsn")):
            response = client.get("/health/ready")
        self.assertEqual(response.status_code,503)
        self.assertNotIn("secret-dsn",response.text)
        with patch("app.main.check_database",return_value=True):
            self.assertEqual(client.get("/health/ready").json(),client.get("/health").json())
