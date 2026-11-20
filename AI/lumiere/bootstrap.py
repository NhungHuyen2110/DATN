"""Composition root: one request owns and closes its external clients."""

from contextlib import contextmanager
import os
from pathlib import Path
from threading import Lock

from .adapters import DenseRetriever, Neo4jGraphRetriever, SentenceTransformerEmbedder
from .catalog import CsvProductRepository, PostgresProductRepository, SnapshotProductRepository
from .retrieval import GroundedAnswerService, HybridRetrievalService, LexicalRetriever, RankFusionService
from .understanding import EntityLinkingService, QueryUnderstandingService
from .linking import SemanticEntityResolver
from .configuration import load_aliases

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def catalog_repository():
    source = os.getenv("AI_CATALOG_SOURCE", "csv")
    if source == "csv":
        return CsvProductRepository(Path(os.getenv("AI_CATALOG_PATH", str(ROOT / "output/products_ai.csv"))))
    if source == "postgres":
        import psycopg
        return PostgresProductRepository(lambda: psycopg.connect(os.environ["AI_DATABASE_URL"],
            connect_timeout=5, options="-c default_transaction_read_only=on -c statement_timeout=10000"))
    raise ValueError("AI_CATALOG_SOURCE must be csv or postgres")


class SemanticModelProvider:
    """Application-owned lazy model; no model download during API import."""

    def __init__(self):
        self.model = None
        self.lock = Lock()

    def get(self):
        with self.lock:
            if self.model is None:
                from sentence_transformers import SentenceTransformer
                workspace_cache = ROOT / ".cache/hf/models"
                cache = os.getenv("AI_MODEL_CACHE") or (str(workspace_cache) if workspace_cache.is_dir() else None)
                allow_download = os.getenv("AI_ALLOW_MODEL_DOWNLOAD", "false").lower() == "true"
                self.model = SentenceTransformer(os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL),
                    cache_folder=cache, trust_remote_code=False, local_files_only=not allow_download)
        return self.model

    def encode(self, texts):
        return SentenceTransformerEmbedder(self.get()).encode(texts)


class LazyDenseRetriever:
    name = "dense"

    def __init__(self, repository, model_provider):
        self.repository, self.model_provider = repository, model_provider

    def retrieve(self, context, limit):
        from qdrant_client import QdrantClient
        client = (QdrantClient(path=os.environ["AI_QDRANT_PATH"]) if os.getenv("AI_QDRANT_PATH") else
                  QdrantClient(url=os.getenv("QDRANT_URL", "http://127.0.0.1:6333"), timeout=5, check_compatibility=False))
        try:
            return DenseRetriever(client, SentenceTransformerEmbedder(self.model_provider.get()),
                                  os.getenv("QDRANT_COLLECTION", "lumiere_products_v2"), self.repository,
                                  os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL)).retrieve(context, limit)
        finally:
            client.close()


class LazyGraphRetriever:
    name = "graph"

    def __init__(self, repository):
        self.repository = repository

    def retrieve(self, context, limit):
        from neo4j import GraphDatabase
        with GraphDatabase.driver(os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687"),
                                  auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "")),
                                  connection_timeout=5, max_transaction_retry_time=5) as driver:
            return Neo4jGraphRetriever(driver, self.repository).retrieve(context, limit)


@contextmanager
def answer_service(model_provider=None, repository_override=None):
    # Snapshot once so all sources verify against the same catalog facts.
    source = repository_override or catalog_repository()
    repository = SnapshotProductRepository(source.all())
    model_provider = model_provider or SemanticModelProvider()
    retrievers = [LexicalRetriever(repository)]
    if os.getenv("AI_DENSE_ENABLED", "true").lower() == "true":
        retrievers.append(LazyDenseRetriever(repository, model_provider))
    if os.getenv("AI_GRAPH_ENABLED", "true").lower() == "true":
        retrievers.append(LazyGraphRetriever(repository))
    config = load_aliases()
    semantic = SemanticEntityResolver(model_provider, config) if os.getenv("AI_SEMANTIC_LINKING", "true").lower() == "true" else None
    yield GroundedAnswerService(HybridRetrievalService(repository, retrievers,
        QueryUnderstandingService(EntityLinkingService(config, semantic), int(os.getenv("AI_CANDIDATE_K", "100"))),
        RankFusionService(), verifier=source))
