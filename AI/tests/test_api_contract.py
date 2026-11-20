"""HTTP regression tests do not invoke legacy models or external databases."""

import os
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import api


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)

    def test_public_catalog_contract_and_missing_product_legacy_200(self):
        response = self.client.get("/products")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["number"], 500)
        self.assertEqual(set(response.json()["data"][0]), {"ProductID", "ProductName", "CategoryName", "BrandName",
                         "MaterialName", "GemstoneName", "CollectionName", "SalePrice", "Stock"})
        missing = self.client.get("/products/999999")
        self.assertEqual(missing.status_code, 200)
        self.assertFalse(missing.json()["success"])

    def test_openapi_matches_checkpoint_schema(self):
        baseline = Path(__file__).resolve().parents[2] / "docs/baseline/ai-openapi.json"
        self.assertEqual(api.app.openapi(), json.loads(baseline.read_text(encoding="utf-8")))

    def test_chat_input_bounds_remain_compatible(self):
        for body in ({"query": ""}, {"query": "nhẫn", "top_k": 0}, {"query": "nhẫn", "top_k": 11}):
            self.assertEqual(self.client.post("/chat", json=body).status_code, 422)

    def test_modular_chat_real_catalog_lexical_mode(self):
        with patch.dict(os.environ, {"AI_PIPELINE": "modular", "AI_DENSE_ENABLED": "false", "AI_GRAPH_ENABLED": "false"}):
            response = self.client.post("/chat", json={"query": "nhẫn dưới 50 triệu", "top_k": 10})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["products"]), 10)
        self.assertEqual(set(("success", "answer", "products")) - body.keys(), set())
        self.assertTrue(all(p["Stock"] > 0 and p["Price"] <= 50000000 for p in body["products"]))

    def test_composed_pipeline_degrades_without_leaking_source_errors(self):
        with patch.dict(os.environ, {"AI_PIPELINE": "modular", "AI_DENSE_ENABLED": "true", "AI_GRAPH_ENABLED": "true"}), \
             patch("lumiere.bootstrap.LazyDenseRetriever.retrieve", side_effect=ConnectionError("secret-dsn")), \
             patch("lumiere.bootstrap.LazyGraphRetriever.retrieve", side_effect=ConnectionError("secret-dsn")):
            response = self.client.post("/chat", json={"query": "nhẫn", "top_k": 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["degraded_sources"], ["dense", "graph"])
        self.assertEqual(len(response.json()["products"]), 3)
        self.assertNotIn("secret-dsn", response.text)

    def test_catalog_failure_returns_unavailable_without_disclosing_details(self):
        with patch.dict(os.environ, {"AI_PIPELINE": "modular"}), \
             patch("lumiere.bootstrap.catalog_repository", side_effect=ValueError("secret-dsn")):
            response = self.client.post("/chat", json={"query": "nhẫn"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret-dsn", response.text)

    def test_liveness_does_not_load_the_model(self):
        with patch.object(api.app.state.embedding_provider, "get") as model:
            self.assertEqual(self.client.get("/health").status_code, 200)
            self.assertEqual(self.client.get("/health/live").status_code, 200)
            model.assert_not_called()

    def test_readiness_distinguishes_dependencies_and_redacts_failures(self):
        with patch.dict(os.environ, {"AI_PIPELINE": "modular", "AI_DENSE_ENABLED": "false", "AI_GRAPH_ENABLED": "false"}):
            self.assertEqual(self.client.get("/health/ready").status_code, 200)
            with patch("lumiere.bootstrap.catalog_repository", side_effect=RuntimeError("secret-dsn")):
                response = self.client.get("/health/ready")
                self.assertEqual(response.status_code, 503)
                self.assertFalse(response.json()["checks"]["catalog"])
                self.assertNotIn("secret-dsn", response.text)

    def test_legacy_chat_function_remains_default(self):
        expected = {"success": True, "answer": "grounded", "products": []}
        with patch.object(api, "answer_jewelry_question", return_value=expected) as answer:
            self.assertEqual(self.client.post("/chat", json={"query": "nhẫn"}).json(), expected)
            answer.assert_called_once_with(query="nhẫn", top_k=3)

    def test_modular_query_top_k_and_explicit_body_precedence(self):
        with patch.dict(os.environ, {"AI_PIPELINE": "modular"}), \
             patch.object(api, "answer_jewelry_question", return_value={"success": True}) as answer:
            self.assertEqual(self.client.post("/chat", json={"query": "top 5 nhẫn"}).status_code, 200)
            answer.assert_called_with(query="top 5 nhẫn", top_k=5)
            self.client.post("/chat", json={"query": "top 5 nhẫn", "top_k": 2})
            answer.assert_called_with(query="top 5 nhẫn", top_k=2)
            self.assertEqual(self.client.post("/chat", json={"query": "top 99 nhẫn"}).status_code, 422)

    def test_v2_validation_and_response_shape(self):
        self.assertEqual(self.client.get("/recommendations/v2?customer_id=A&product_id=9999").status_code, 404)
        self.assertEqual(self.client.get("/recommendations/v2?customer_id=A&product_id=1&number=21").status_code, 422)
        with patch.object(api, "recommend_v2", return_value=[{"ProductID": 2}]):
            body = self.client.get("/recommendations/v2?customer_id=A&product_id=1&number=1").json()
        self.assertEqual(body, {"success": True, "customer_id": "A", "product_id": 1, "number": 1, "data": [{"ProductID": 2}]})


if __name__ == "__main__":
    unittest.main()
