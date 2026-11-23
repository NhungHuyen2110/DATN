from contextlib import closing
import unittest
from unittest.mock import patch
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from jewelry_agents.advice_planner import plan_advice, RequestEmbedding, PROTOTYPES
from jewelry_agents.retrieval import _search_qdrant
from vector_index import index_identity


class Vector(list):
    def tolist(self):
        return list(self)


class Encoder:
    def __init__(self):
        self.calls = []

    def get_sentence_embedding_dimension(self):
        return 2

    def encode(self, texts,**kwargs):
        self.calls.append(texts)
        if isinstance(texts, str):
            return Vector([0., 1.])
        other = PROTOTYPES['product_search'] + PROTOTYPES['other']
        return [[0., 1.] if text in other else [1., 0.] for text in texts]


class RequestEmbeddingTests(unittest.TestCase):
    def query(self, client, encoder, text, context):
        collection, _ = index_identity('synthetic', 'test-revision', 2)
        if not client.collection_exists(collection):
            client.create_collection(collection, vectors_config=VectorParams(size=2, distance=Distance.COSINE))
            client.upsert(collection, [PointStruct(id=pid, vector=vector, payload={'ProductID':pid})
                           for pid, vector in ((1, [1., 0.]), (2, [0., 1.]))])
        with patch.dict('os.environ', {'EMBEDDING_REVISION':'test-revision'}), \
                patch('jewelry_agents.retrieval.QDRANT_COLLECTION', collection), \
                patch('jewelry_agents.retrieval.EMBEDDING_MODEL', 'synthetic'):
            return _search_qdrant(text, top_k=1, eligible_ids=[1, 2], services=(client, encoder), request_embedding=context)

    def test_advice_and_dense_share_only_the_exact_request_vector(self):
        model = Encoder()
        query = 'Synthetic private birthday request'
        advice = plan_advice(query, model, include_embedding=True)
        context = advice['_request_embedding']
        with closing(QdrantClient(location=':memory:')) as client:
            result = self.query(client, model, query, context)
        self.assertEqual(result[0]['ProductID'], 1)
        self.assertEqual([len(call) for call in model.calls], [8, 1,6])
        self.assertNotIn(query, repr(context))

    def test_rewritten_query_or_replaced_model_must_encode_again(self):
        first = Encoder()
        context = plan_advice('original private question', first, include_embedding=True)['_request_embedding']
        with closing(QdrantClient(location=':memory:')) as client:
            self.assertEqual(self.query(client, first, 'rewritten query', context)[0]['ProductID'], 2)
            second = Encoder()
            self.assertEqual(self.query(client, second, 'original private question', context)[0]['ProductID'], 2)
        self.assertEqual(first.calls[-1], 'rewritten query')
        self.assertEqual(second.calls, ['original private question'])

    def test_dimension_nonfinite_and_zero_vectors_are_rejected(self):
        model = Encoder()
        with closing(QdrantClient(location=':memory:')) as client:
            for vector in ((1.,), (float('nan'), 1.), (0., 0.)):
                with self.subTest(vector=vector), self.assertRaises(ValueError):
                    self.query(client, model, 'query', RequestEmbedding('query', model, vector))
