"""Read-only readiness checks. Liveness never imports or warms the model."""
import os
from pathlib import Path


def readiness(model_provider):
    from .bootstrap import catalog_repository
    checks = {}

    def probe(name, operation):
        try:
            checks[name] = bool(operation())
        except Exception:
            checks[name] = False

    if os.getenv("AI_PIPELINE", "legacy") != "modular":
        return {"status": "not_ready", "checks": {"legacy_runtime_verified": False}}
    probe("catalog", lambda: catalog_repository().all())
    if os.getenv("AI_DENSE_ENABLED", "true").lower() == "true":
        # Initial startup is not ready until a controlled warm-up/request loads it.
        checks["embedding_model_loaded"] = model_provider.model is not None
        def vector_probe():
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance
            local = os.getenv("AI_QDRANT_PATH")
            if local and not Path(local).is_dir():
                return False
            client = (QdrantClient(path=local) if local else QdrantClient(
                url=os.getenv("QDRANT_URL", "http://127.0.0.1:6333"), timeout=3, check_compatibility=False))
            try:
                info = client.get_collection(os.getenv("QDRANT_COLLECTION", "lumiere_products_v2"))
                config = info.config.params.vectors
                dimension = (getattr(model_provider.model, "get_embedding_dimension", None) or
                             getattr(model_provider.model, "get_sentence_embedding_dimension", None))
                size = dimension() if dimension else None
                return getattr(config, "distance", None) == Distance.COSINE and getattr(config, "size", None) == size and info.points_count > 0
            finally:
                client.close()
        probe("vector_collection", vector_probe)
    if os.getenv("AI_GRAPH_ENABLED", "true").lower() == "true":
        def graph_probe():
            from neo4j import GraphDatabase
            with GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
                auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "")),
                connection_timeout=3, max_transaction_retry_time=0) as driver:
                with driver.session() as session:
                    return session.run("MATCH (p:Product) RETURN p.product_id AS id LIMIT 1").single() is not None
        probe("graph_catalog", graph_probe)
    return {"status": "ready" if all(checks.values()) else "not_ready", "checks": checks}
