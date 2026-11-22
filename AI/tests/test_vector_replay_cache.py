from contextlib import closing
import unittest
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from knowledge_graph.csv_validation import validate_csv, ROOT
from vector_index import index_products


class VectorReplayCacheTests(unittest.TestCase):
    def test_replay_skips_encoding_only_for_matching_source_contract_and_payload(self):
        class Encoder:
            calls = 0
            def get_sentence_embedding_dimension(self): return 3
            def encode(self, texts):
                self.calls += len(texts)
                return [[1., 0., 0.] for _ in texts]
        row = validate_csv(ROOT / 'AI/tests/fixtures/products_graph.csv', ROOT / 'data')['records'][0]
        encoder = Encoder()
        with closing(QdrantClient(location=':memory:')) as client:
            def index(data=row, digest='snapshot-1'):
                return index_products(client, encoder, [data], 'synthetic', 'revision-1', digest,
                                      reuse_existing=True)
            first = index()
            second = index()
            self.assertEqual(encoder.calls, 1)
            self.assertEqual(second['reused_products'], 1)
            self.assertTrue(second['pass'])
            index(digest='new-snapshot')
            self.assertEqual(encoder.calls, 2)
            index({**row, 'ProductName': 'Changed name'}, 'new-snapshot')
            self.assertEqual(encoder.calls, 3)
            client.set_payload(first['collection'], {'embedding_fingerprint': 'untrusted'}, points=[row['ProductID']])
            index()
            self.assertEqual(encoder.calls, 4)
            # Corrupt/missing vector cannot count as an encoded product.
            point = client.retrieve(first['collection'], ids=[row['ProductID']], with_payload=True)[0]
            client.upsert(first['collection'], points=[PointStruct(id=row['ProductID'], vector=[0., 0., 0.], payload=point.payload)])
            index()
            self.assertEqual(encoder.calls, 5)
            self.assertEqual(client.count(first['collection'], exact=True).count, 1)
