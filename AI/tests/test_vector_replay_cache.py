from contextlib import closing
import unittest
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from knowledge_graph.csv_validation import validate_csv, ROOT
from vector_index import index_products
import hashlib


class VectorReplayCacheTests(unittest.TestCase):
    def test_approved_fact_revision_and_revocation_invalidate_cached_metadata_and_text(self):
        class Encoder:
            def __init__(self): self.texts=[]
            def get_sentence_embedding_dimension(self): return 3
            def encode(self,texts):
                self.texts.extend(texts)
                return [[1.,0.,0.] for _ in texts]
        row=validate_csv(ROOT/'AI/tests/fixtures/products_graph.csv',ROOT/'data')['records'][0]
        approved={'label':'Style','canonical_id':'elegant','name':'Thanh lịch',
                  'source_reference_sha256':hashlib.sha256(b'synthetic fixture').hexdigest(),
                  'review_id':1,'review_version':1,'reviewed_at':'2026-11-22T00:00:00+00:00'}
        encoder=Encoder()
        with closing(QdrantClient(location=':memory:')) as client:
            first=index_products(client,encoder,[{**row,'verified_attributes':[approved]}],
                                 'synthetic','revision-1','snapshot',reuse_existing=True)
            self.assertIn('Thanh lịch',encoder.texts[-1])
            changed={**approved,'review_version':2}
            second=index_products(client,encoder,[{**row,'verified_attributes':[changed]}],
                                  'synthetic','revision-1','snapshot',reuse_existing=True)
            self.assertEqual(second['encoded_products'],0)
            self.assertEqual(second['refreshed_payload_products'],1)
            third=index_products(client,encoder,[{**row,'verified_attributes':[]}],
                                 'synthetic','revision-1','snapshot',reuse_existing=True)
            self.assertEqual(third['encoded_products'],1)
            point=client.retrieve(first['collection'],ids=[row['ProductID']],with_payload=True)[0]
            self.assertEqual(point.payload['verified_attributes'],[])
            self.assertNotIn('Thanh lịch',encoder.texts[-1])

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
            self.assertEqual(encoder.calls, 1)
            index({**row, 'ProductName': 'Changed name'}, 'new-snapshot')
            self.assertEqual(encoder.calls, 2)
            client.set_payload(first['collection'], {'embedding_fingerprint': 'untrusted'}, points=[row['ProductID']])
            index()
            self.assertEqual(encoder.calls, 3)
            # Corrupt/missing vector cannot count as an encoded product.
            point = client.retrieve(first['collection'], ids=[row['ProductID']], with_payload=True)[0]
            client.upsert(first['collection'], points=[PointStruct(id=row['ProductID'], vector=[0., 0., 0.], payload=point.payload)])
            index()
            self.assertEqual(encoder.calls, 4)
            self.assertEqual(client.count(first['collection'], exact=True).count, 1)

    def test_stock_price_and_lineage_refresh_preserves_embedding_but_brand_change_encodes(self):
        class Encoder:
            calls = 0
            def get_sentence_embedding_dimension(self): return 3
            def encode(self, texts):
                self.calls += len(texts)
                return [[1., 0., 0.] for _ in texts]
        row = validate_csv(ROOT/'AI/tests/fixtures/products_graph.csv', ROOT/'data')['records'][0]
        encoder = Encoder()
        with closing(QdrantClient(location=':memory:')) as client:
            def index(data, digest):
                return index_products(client, encoder, [data], 'synthetic', 'revision-1', digest, reuse_existing=True)
            first = index(row, 'old')
            changed = {**row, 'Stock': 0, 'SalePrice': '1.00', 'Barcode': 'changed'}
            second = index(changed, 'new')
            self.assertEqual(encoder.calls, 1)
            self.assertEqual(second['encoded_products'], 0)
            point = client.retrieve(first['collection'], ids=[row['ProductID']], with_payload=True)[0]
            self.assertEqual(point.payload['source_sha256'], 'new')
            self.assertNotIn('Stock', point.payload)
            self.assertNotIn('Price', point.payload)
            index({**changed, 'BrandName': 'New brand'}, 'brand')
            self.assertEqual(encoder.calls, 2)

    def test_legacy_vector_without_document_digest_is_reencoded_once(self):
        class Encoder:
            calls = 0
            def get_sentence_embedding_dimension(self): return 3
            def encode(self, texts):
                self.calls += 1
                return [[1., 0., 0.] for _ in texts]
        row = validate_csv(ROOT/'AI/tests/fixtures/products_graph.csv', ROOT/'data')['records'][0]
        with closing(QdrantClient(location=':memory:')) as client:
            encoder = Encoder()
            first = index_products(client, encoder, [row], 'synthetic', 'revision-1', 'same', reuse_existing=True)
            client.delete_payload(first['collection'], keys=['embedding_document_sha256'], points=[row['ProductID']])
            index_products(client, encoder, [row], 'synthetic', 'revision-1', 'same', reuse_existing=True)
            index_products(client, encoder, [row], 'synthetic', 'revision-1', 'new-stock', reuse_existing=True)
            self.assertEqual(encoder.calls, 2)
