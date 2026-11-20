"""Operational metrics must not turn URLs/query strings into high-cardinality labels."""

import json
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.observability import install_observability


class ObservabilityTests(unittest.TestCase):
    def test_failed_endpoint_does_not_break_next_request(self):
        app = FastAPI()
        install_observability(app)

        @app.get("/fail")
        def fail():
            raise RuntimeError("private-error")

        @app.get("/ok")
        def ok():
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)
        failed = client.get("/fail")
        self.assertEqual(failed.status_code, 500)
        self.assertNotIn("private-error", failed.text)
        self.assertEqual(client.get("/ok").json(), {"ok": True})
        self.assertIn('route="/fail",method="GET",status="500"', client.get("/metrics").text)

    def test_route_labels_and_logs_exclude_query_and_cookie(self):
        app = FastAPI()
        install_observability(app)

        @app.get("/items/{item_id}")
        def item(item_id: int):
            return {"id": item_id}

        client = TestClient(app)
        with self.assertLogs("uvicorn.error", level="INFO") as logs:
            self.assertEqual(client.get("/items/7?private=secret-query", headers={"Cookie": "session=secret-cookie"}).status_code, 200)
        text = client.get("/metrics").text
        self.assertIn('route="/items/{item_id}"', text)
        self.assertNotIn("/items/7", text)
        self.assertNotIn("secret", " ".join(logs.output) + text)
        self.assertEqual(json.loads(logs.records[0].getMessage())["status"], 200)
