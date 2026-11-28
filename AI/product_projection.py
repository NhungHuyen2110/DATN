"""Idempotent graph/vector adapters for the durable business outbox worker."""
import hashlib
import json

from knowledge_graph.graph_writer import import_projection, mark_deleted
from vector_index import index_products, index_identity


class ProductProjection:
    def __init__(self, graph_driver, graph_database, qdrant, encoder, model_name, model_revision):
        self.graph_driver, self.graph_database = graph_driver, graph_database
        self.qdrant, self.encoder = qdrant, encoder
        self.model_name, self.model_revision = model_name, model_revision

    def __call__(self, product_id, snapshot, generation):
        if not isinstance(generation, int) or generation < 1:
            raise ValueError('Positive outbox generation required')
        if snapshot is not None and snapshot.get('ProductID') != product_id:
            raise ValueError('Snapshot identity differs from claimed product')
        # Incremental delivery must not create/switch collections or schema.
        from qdrant_client.models import Distance
        dimension = self.encoder.get_sentence_embedding_dimension()
        collection, _ = index_identity(self.model_name, self.model_revision, dimension)
        if not self.qdrant.collection_exists(collection):
            raise ValueError('Expected existing vector collection; approval required')
        config = self.qdrant.get_collection(collection).config.params.vectors
        if isinstance(config, dict) or config.size != dimension or config.distance != Distance.COSINE:
            raise ValueError('Existing collection schema differs')
        if snapshot is None:
            mark_deleted(self.graph_driver, self.graph_database, product_id)
            if self.qdrant.collection_exists(collection):
                from qdrant_client.models import PointIdsList
                self.qdrant.delete(collection, points_selector=PointIdsList(points=[product_id]), wait=True)
                if self.qdrant.retrieve(collection, ids=[product_id]):
                    raise RuntimeError('VectorDeletionVerificationFailed')
            return
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        result = import_projection(self.graph_driver, self.graph_database, [snapshot], 'business-db.products', digest,
                                   allow_schema_changes=False)
        if not result['pass']:
            raise RuntimeError('GraphVerificationFailed')
        result = index_products(self.qdrant, self.encoder, [snapshot], self.model_name,
                                self.model_revision, digest, reuse_existing=True)
        if not result['pass']:
            raise RuntimeError('VectorVerificationFailed')

    def known_product_ids(self):
        from knowledge_graph.graph_writer import OWNER
        with self.graph_driver.session(database=self.graph_database) as session:
            ids = {row['id'] for row in session.run('MATCH (p:Product {projection_owner:$owner}) RETURN p.product_id AS id', owner=OWNER)}
        collection, fingerprint = index_identity(self.model_name, self.model_revision,
                                                 self.encoder.get_sentence_embedding_dimension())
        if self.qdrant.collection_exists(collection):
            offset = None
            for _ in range(100):
                points, offset = self.qdrant.scroll(collection, limit=100, offset=offset,
                                                     with_payload=True, with_vectors=False)
                for point in points:
                    if point.payload.get('embedding_fingerprint') != fingerprint:
                        raise ValueError('Unmanaged vector payload in projection collection')
                    ids.add(int(point.id))
                if offset is None:
                    break
            else:
                raise ValueError('Projection scan exceeds bounded reconciliation limit')
        return ids
