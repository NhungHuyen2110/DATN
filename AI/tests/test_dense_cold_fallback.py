import unittest
from unittest.mock import patch


class DenseColdFallbackTests(unittest.TestCase):
    def test_vector_outage_does_not_load_a_cold_embedding_model(self):
        from jewelry_agents import retrieval
        class MissingVectorSource:
            def get_collection(self, name):
                raise ConnectionError('Synthetic isolated vector outage')
        with patch.dict('os.environ', {'LUMIERE_DENSE_ENABLED': 'true'}), \
             patch.object(retrieval, 'qdrant_client', MissingVectorSource()), \
             patch.object(retrieval, 'embedding_model', None), \
             patch('sentence_transformers.SentenceTransformer', side_effect=AssertionError('Cold model must not load')) as model:
            with self.assertRaises(ConnectionError):
                retrieval.get_dense_services()
            model.assert_not_called()
