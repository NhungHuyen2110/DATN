"""Real Qdrant local engine, synthetic vectors; no server/model downloads."""
from pathlib import Path
from contextlib import closing
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from knowledge_graph.csv_validation import validate_csv, ROOT
from vector_index import index_products, index_identity


class Encoder:
    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, texts):
        return [[1.0, float(i) * 0.1, 0.0] for i, _ in enumerate(texts)]


class QdrantVersionedTests(unittest.TestCase):
    def test_actual_local_upsert_replay_cosine_and_version_separation(self):
        from qdrant_client import QdrantClient
        from jewelry_agents import retrieval
        rows = validate_csv(ROOT / 'AI/tests/fixtures/products_graph.csv', ROOT / 'data')['records']
        with closing(QdrantClient(location=':memory:')) as client:
            first = index_products(client, Encoder(), rows, 'synthetic-test-encoder', 'revision-one', 'fixture-sha')
            second = index_products(client, Encoder(), rows, 'synthetic-test-encoder', 'revision-one', 'fixture-sha')
            self.assertEqual(first, second)
            self.assertTrue(first['pass'])
            self.assertEqual(client.count(first['collection'], exact=True).count, 3)
            hits = client.query_points(first['collection'], query=[10.0, 0.0, 0.0], limit=1).points
            self.assertEqual(hits[0].id, 900001)
            self.assertAlmostEqual(hits[0].score, 1.0, places=5)
            newer = index_products(client, Encoder(), rows, 'synthetic-test-encoder', 'revision-two', 'fixture-sha')
            self.assertNotEqual(first['collection'], newer['collection'])
            self.assertTrue(client.collection_exists(first['collection']))

    def test_dimension_and_revision_are_in_identity(self):
        self.assertNotEqual(index_identity('model', 'revision', 3), index_identity('model', 'revision', 4))
        with self.assertRaises(ValueError):
            index_identity('model', '', 384)

    def test_actual_search_checks_version_and_collection_contract(self):
        import numpy as np
        from qdrant_client import QdrantClient
        class QueryEncoder(Encoder):
            def encode(self, texts):
                return np.array([1.0, 0.0, 0.0]) if isinstance(texts, str) else super().encode(texts)
        rows = validate_csv(ROOT / 'AI/tests/fixtures/products_graph.csv', ROOT / 'data')['records']
        with closing(QdrantClient(location=':memory:')) as client:
            model = QueryEncoder()
            report = index_products(client, model, rows, 'synthetic-model', 'pinned-revision', 'fixture-sha')
            from jewelry_agents import retrieval
            with patch.object(retrieval, 'get_dense_services', return_value=(client, model)), \
                 patch.object(retrieval, 'QDRANT_COLLECTION', report['collection']), \
                 patch.object(retrieval, 'EMBEDDING_MODEL', 'synthetic-model'), \
                 patch.dict(os.environ, {'EMBEDDING_REVISION': 'pinned-revision', 'LUMIERE_RETRIEVAL_LIMITS_ENABLED': 'false'}):
                result = retrieval.search_qdrant('synthetic query', top_k=1)
                self.assertEqual(result[0]['ProductID'], 900001)
                filtered = retrieval.search_qdrant('synthetic query', top_k=3, eligible_ids=[900002])
                self.assertEqual([p['ProductID'] for p in filtered], [900002])
                retrieval.EMBEDDING_MODEL = 'wrong-model'
                with self.assertRaises(ValueError):
                    retrieval.search_qdrant('synthetic query')


if __name__ == '__main__':
    unittest.main()
