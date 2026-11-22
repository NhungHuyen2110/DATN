"""ASGI compatibility tests with model/database constructors forbidden."""
import importlib
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ChatPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sentence = ModuleType('sentence_transformers')
        sentence.SentenceTransformer = MagicMock(side_effect=AssertionError('No model construction allowed'))
        qdrant = ModuleType('qdrant_client')
        qdrant.QdrantClient = MagicMock(side_effect=AssertionError('No Qdrant construction allowed'))
        neo4j = ModuleType('neo4j')
        neo4j.GraphDatabase = MagicMock()
        neo4j.GraphDatabase.driver.side_effect = AssertionError('No Neo4j construction allowed')
        with patch.dict(sys.modules, {'sentence_transformers': sentence, 'qdrant_client': qdrant, 'neo4j': neo4j}), \
                patch('dotenv.load_dotenv', return_value=False):
            cls.api = importlib.import_module('api')
            cls.rag = importlib.import_module('rag.rag_service')

    def call(self, query, **patches):
        from fastapi.testclient import TestClient
        live = {1: {'ProductID': 1, 'ProductName': 'Nhẫn mẫu', 'SKU': 'TEST1', 'Category': 'Nhẫn', 'CategoryID': 1,
                    'Material': 'Bạc 925', 'Gemstone': 'CZ', 'GemstoneID': 6, 'Collection': 'Minimal',
                    'Price': '7000000.01', 'Stock': 1}}
        with patch.object(self.rag, 'fetch_catalog', patches.get('catalog', lambda: live)), \
                patch.object(self.rag, 'search_qdrant', patches.get('dense', lambda *a, **k: [{'ProductID': 1}])), \
                patch.object(self.rag, 'graph_search_candidates', patches.get('graph', lambda *a: [])), \
                patch.dict('os.environ', {'LUMIERE_RETRIEVAL_V2_ENABLED': 'true'}):
            return TestClient(self.api.app).post('/chat', json={'query': query, 'top_k': 3})

    def test_existing_chat_contract_and_exact_price_no_llm(self):
        response = self.call('Top 1 nhẫn dưới 8 triệu')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['success'])
        self.assertEqual(len(body['products']), 1)
        self.assertEqual(body['products'][0]['Price'], '7000000.01')
        self.assertIn('7.000.000,01 VNĐ', body['answer'])
        self.assertNotIn('score', body['products'][0])
        self.assertEqual(body['requested_k'], 1)

    def test_dense_and_graph_failure_still_returns_verified_cards(self):
        def failed(*a, **k):
            raise ConnectionError('synthetic')
        body = self.call('nhẫn', dense=failed, graph=failed).json()
        self.assertTrue(body['success'])
        self.assertEqual(body['status'], 'degraded')
        self.assertEqual(len(body['products']), 1)

    def test_catalog_failure_does_not_serve_stale_prices(self):
        def failed():
            raise ConnectionError('synthetic')
        body = self.call('nhẫn', catalog=failed).json()
        self.assertFalse(body['success'])
        self.assertEqual(body['products'], [])

    def test_child_request_returns_clarification(self):
        body = self.call('mua nhẫn tặng con gái 8 tuổi').json()
        self.assertEqual(body['status'], 'clarification_required')
        self.assertEqual(body['products'], [])

    def test_liveness_does_not_call_optional_services(self):
        from fastapi.testclient import TestClient
        response = TestClient(self.api.app).get('/health/live')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'alive')


if __name__ == '__main__':
    unittest.main()
