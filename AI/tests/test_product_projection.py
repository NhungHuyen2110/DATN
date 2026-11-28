"""Projection replay/deletion with actual Qdrant memory and a stubbed graph."""
from contextlib import closing
import unittest
from unittest.mock import patch

from qdrant_client import QdrantClient
from knowledge_graph.csv_validation import validate_csv, ROOT
from product_projection import ProductProjection
from vector_index import index_identity
from qdrant_client.models import Distance, VectorParams


class Encoder:
    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


class ProductProjectionTests(unittest.TestCase):
    def collection(self, client):
        name, _ = index_identity('synthetic', 'revision-1', 3)
        client.create_collection(name, vectors_config=VectorParams(size=3, distance=Distance.COSINE))

    def test_update_delete_and_recreate_keep_stable_identity(self):
        row = validate_csv(ROOT / 'AI/tests/fixtures/products_graph.csv', ROOT / 'data')['records'][0]
        pid = row['ProductID']
        with closing(QdrantClient(location=':memory:')) as client, \
                patch('product_projection.import_projection', return_value={'pass': True}) as graph, \
                patch('product_projection.mark_deleted') as tombstone:
            projection = ProductProjection(object(), 'neo4j', client, Encoder(), 'synthetic', 'revision-1')
            self.collection(client)
            collection, _ = index_identity('synthetic', 'revision-1', 3)
            projection(pid, row, 1)
            projection(pid, {**row, 'Stock': 2}, 2)
            self.assertEqual(client.count(collection, exact=True).count, 1)
            projection(pid, None, 3)
            tombstone.assert_called_once_with(projection.graph_driver, 'neo4j', pid)
            self.assertTrue(client.collection_exists(collection))
            self.assertEqual(client.count(collection, exact=True).count, 0)
            projection(pid, row, 4)
            self.assertEqual([point.id for point in client.retrieve(collection, ids=[pid])], [pid])
            self.assertEqual(graph.call_count, 3)

    def test_graph_failure_leaves_vectors_untouched_for_retry(self):
        row = validate_csv(ROOT / 'AI/tests/fixtures/products_graph.csv', ROOT / 'data')['records'][0]
        with closing(QdrantClient(location=':memory:')) as client, \
                patch('product_projection.import_projection', return_value={'pass': False}):
            projection = ProductProjection(object(), 'neo4j', client, Encoder(), 'synthetic', 'revision-1')
            self.collection(client)
            with self.assertRaisesRegex(RuntimeError, 'GraphVerificationFailed'):
                projection(row['ProductID'], row, 1)
            self.assertEqual(client.count(index_identity('synthetic', 'revision-1', 3)[0]).count, 0)

    def test_missing_collection_and_identity_mismatch_fail_before_graph_write(self):
        row = validate_csv(ROOT / 'AI/tests/fixtures/products_graph.csv', ROOT / 'data')['records'][0]
        with closing(QdrantClient(location=':memory:')) as client, patch('product_projection.import_projection') as graph:
            projection = ProductProjection(object(), 'neo4j', client, Encoder(), 'synthetic', 'revision-1')
            with self.assertRaisesRegex(ValueError, 'existing vector collection'):
                projection(row['ProductID'], row, 1)
            with self.assertRaisesRegex(ValueError, 'identity differs'):
                projection(row['ProductID'] + 1, row, 1)
            graph.assert_not_called()

    def test_vector_failure_after_graph_success_is_replayed_with_stable_identity(self):
        row = validate_csv(ROOT / 'AI/tests/fixtures/products_graph.csv', ROOT / 'data')['records'][0]
        with closing(QdrantClient(location=':memory:')) as client, \
                patch('product_projection.import_projection', return_value={'pass': True}) as graph:
            self.collection(client)
            encoder = Encoder()
            projection = ProductProjection(object(), 'neo4j', client, encoder, 'synthetic', 'revision-1')
            with patch.object(encoder, 'encode', side_effect=TimeoutError):
                with self.assertRaises(TimeoutError):
                    projection(row['ProductID'], row, 1)
            projection(row['ProductID'], row, 1)
            self.assertEqual(graph.call_count, 2)
            self.assertEqual(client.count(index_identity('synthetic', 'revision-1', 3)[0]).count, 1)
