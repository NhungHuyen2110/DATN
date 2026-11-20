"""Vendor adapters accept clients through constructors. SDKs load only on use."""

import math
import hashlib

from .domain import Candidate, Embedder, ProductRepository, QueryContext
from .retrieval import eligible
from .configuration import load_graph_schema

REPRESENTATION_VERSION = "2026-11-19.3"


class SentenceTransformerEmbedder:
    def __init__(self, model):
        self.model = model

    def encode(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()


class DenseRetriever:
    name = "dense"

    def __init__(self, client, embedder: Embedder, collection: str, repository: ProductRepository, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.client, self.embedder, self.collection, self.repository = client, embedder, collection, repository
        self.model_name = model_name

    def retrieve(self, context: QueryContext, limit: int) -> list[Candidate]:
        from qdrant_client.models import FieldCondition, Filter, HasIdCondition, MatchValue
        catalog = {p.id: p for p in self.repository.all() if eligible(p, context)}
        allowed = list(catalog)
        if not allowed:
            return []
        vector = self.embedder.encode([context.query])[0]
        if not vector or not any(vector) or not all(math.isfinite(v) for v in vector):
            raise ValueError("Invalid query embedding")
        points = self.client.query_points(collection_name=self.collection, query=vector,
                                         query_filter=Filter(must=[HasIdCondition(has_id=allowed),
                                             FieldCondition(key="embedding_model", match=MatchValue(value=self.model_name)),
                                             FieldCondition(key="representation_version", match=MatchValue(value=REPRESENTATION_VERSION))]),
                                         limit=limit, with_payload=True).points
        return [Candidate(int(point.id), float(point.score), "Tương đồng ngữ nghĩa đa ngôn ngữ") for point in points
                if int(point.id) in catalog and (point.payload or {}).get("content_sha256") == hashlib.sha256(catalog[int(point.id)].text.encode("utf-8")).hexdigest()]


class Neo4jGraphRetriever:
    name = "graph"

    def __init__(self, driver, repository: ProductRepository):
        self.driver, self.repository = driver, repository

    def retrieve(self, context: QueryContext, limit: int) -> list[Candidate]:
        if not context.entities and context.seed_product_id is None:
            return []
        allowed = [p.id for p in self.repository.all() if eligible(p, context)]
        schema = load_graph_schema()
        kinds = {"category": "BELONGS_TO", "material": "MADE_OF", "gemstone": "HAS_GEMSTONE",
                 **{item["kind"]: item["relationship"] for item in schema["evidence_facets"]}}
        relationships = list(context.required_relationships or (tuple(kinds.values()) if context.seed_product_id else
                              tuple(kinds[k] for k in context.entities if k in kinds)))
        with self.driver.session() as session:
            if context.seed_product_id is not None:
                rows = session.run('''
                    MATCH (source:Product {product_id:$seed})-[a]->(e)<-[b]-(p:Product)
                    WHERE p.product_id IN $allowed AND p <> source
                      AND type(a) IN $relationships AND type(b)=type(a)
                    WITH p, collect(DISTINCT {relationship:type(a), entity_name:e.name,
                        entity_id:coalesce(e.category_id,e.material_id,e.gemstone_id,e.canonical_id),
                        source_product_id:$seed, target_product_id:p.product_id}) AS paths
                    WHERE all(required IN $required WHERE any(path IN paths WHERE path.relationship=required))
                    RETURN p.product_id AS id, size(paths) AS score, paths
                    ORDER BY score DESC, id ASC LIMIT $limit
                ''', seed=context.seed_product_id, allowed=allowed, relationships=relationships,
                    required=list(context.required_relationships), limit=limit)
            else:
                rows = session.run('''
                    MATCH (p:Product)-[r]->(e)
                    WHERE p.product_id IN $allowed AND type(r) IN $relationships
                    WITH p, collect(DISTINCT {relationship:type(r), entity_name:e.name,
                        entity_id:coalesce(e.category_id,e.material_id,e.gemstone_id,e.canonical_id),
                        target_product_id:p.product_id}) AS paths
                    RETURN p.product_id AS id, size(paths) AS score, paths
                    ORDER BY score DESC, id ASC LIMIT $limit
                ''', allowed=allowed, relationships=relationships, limit=limit)
            return [Candidate(row["id"], float(row["score"]),
                              "Đường dẫn đồ thị đã truy vấn: " + ", ".join(sorted({p["entity_name"] for p in row["paths"]})),
                              tuple(row["paths"])) for row in rows]


class QdrantProductIndex:
    def __init__(self, client, embedder: Embedder, collection: str, model_name: str, batch_size: int = 100):
        self.client, self.embedder, self.collection, self.model_name = client, embedder, collection, model_name
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.batch_size = batch_size

    def _payload(self, product):
        return {**product.public(), "embedding_model": self.model_name, "representation_version": REPRESENTATION_VERSION,
                "content_sha256": hashlib.sha256(product.text.encode("utf-8")).hexdigest()}

    def upsert(self, products) -> int:
        from .catalog import validate_catalog
        products = validate_catalog(products)
        for offset in range(0, len(products), self.batch_size):
            self._upsert_batch(products[offset:offset+self.batch_size])
        return self.verify(products)

    def _upsert_batch(self, products) -> int:
        from qdrant_client.models import Distance, PointStruct, VectorParams
        vectors = self.embedder.encode([p.text for p in products])
        if len(vectors) != len(products) or not vectors or not vectors[0]:
            raise ValueError("Embedding batch shape mismatch")
        size = len(vectors[0])
        if any(len(v) != size or not all(math.isfinite(x) for x in v) or not any(v) for v in vectors):
            raise ValueError("Invalid embedding dimensions or values")
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(collection_name=self.collection,
                                          vectors_config=VectorParams(size=size, distance=Distance.COSINE))
        config = self.client.get_collection(self.collection).config.params.vectors
        if getattr(config, "size", None) != size or getattr(config, "distance", None) != Distance.COSINE:
            raise ValueError("Existing collection dimension/distance mismatch; use a new collection")
        # Stable IDs overwrite the same public payload; existing collections are never deleted.
        self.client.upsert(collection_name=self.collection, wait=True,
                           points=[PointStruct(id=p.id, vector=v, payload=self._payload(p))
                                   for p, v in zip(products, vectors)])
        return self.verify(products)

    def verify(self, products) -> int:
        stored = self.client.retrieve(collection_name=self.collection, ids=[p.id for p in products], with_payload=True)
        expected = {p.id: self._payload(p) for p in products}
        if len(stored) != len(products) or any(row.payload != expected.get(row.id) for row in stored):
            raise RuntimeError("Qdrant verification failed")
        return len(stored)
