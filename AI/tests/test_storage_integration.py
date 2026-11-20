"""Opt-in storage checks. These are separate from semantic model evaluation."""

from dataclasses import replace
from contextlib import closing
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lumiere.catalog import SnapshotProductRepository
from lumiere.adapters import DenseRetriever, QdrantProductIndex
from lumiere.ingestion import Neo4jProductWriter
from lumiere.understanding import EntityLinkingService, QueryUnderstandingService
from test_modular_pipeline import product


class StorageAdapterTests(unittest.TestCase):
    def test_incompatible_cosine_collection_is_preserved(self):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
        class Encoder:
            def encode(self, texts):
                return [[1.0,0.0] for _ in texts]
        with closing(QdrantClient(":memory:")) as client:
            client.create_collection("wrong_metric", vectors_config=VectorParams(size=2,distance=Distance.DOT))
            with self.assertRaises(ValueError):
                QdrantProductIndex(client,Encoder(),"wrong_metric","test").upsert([product(1)])
            self.assertTrue(client.collection_exists("wrong_metric"))
            self.assertEqual(client.count("wrong_metric").count,0)

    def test_stale_representation_cannot_be_reported_as_current_dense_hit(self):
        from qdrant_client import QdrantClient
        class Encoder:
            def encode(self, texts):
                return [[1.0,0.0] for _ in texts]
        with closing(QdrantClient(":memory:")) as client:
            QdrantProductIndex(client,Encoder(),"stale","test").upsert([product(1)])
            current = SnapshotProductRepository([replace(product(1),name="Changed product representation")])
            context = QueryUnderstandingService(EntityLinkingService()).understand("nhẫn",1)
            self.assertEqual(DenseRetriever(client,Encoder(),"stale",current,"test").retrieve(context,10),[])

    def test_qdrant_real_local_storage_upsert_and_filter(self):
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            self.skipTest(f"Qdrant SDK cannot load on this host: {type(exc).__name__}")
        # Fixed vectors isolate adapter behavior; this does NOT test semantic quality.
        class TestEmbedder:
            def encode(self, texts):
                return [[1.0, 0.0] for _ in texts]

        rows = [product(1), product(2, stock=0)]
        with closing(QdrantClient(":memory:")) as client:
            index = QdrantProductIndex(client, TestEmbedder(), "adapter_test", "test-model")
            self.assertEqual(index.upsert(rows), 2)
            self.assertEqual(index.upsert(rows), 2)
            self.assertEqual(client.count("adapter_test").count, 2)
            context = QueryUnderstandingService(EntityLinkingService()).understand("nhẫn", 2)
            found = DenseRetriever(client, TestEmbedder(), "adapter_test", SnapshotProductRepository(rows), "test-model").retrieve(context, 10)
            self.assertEqual([c.product_id for c in found], [1])


@unittest.skipUnless(os.getenv("LUMIERE_EMPTY_GRAPH_TEST") == "1", "Dedicated empty Neo4j test instance is not enabled")
class Neo4jIntegrationTests(unittest.TestCase):
    def test_import_replay_and_relationship_replacement(self):
        from neo4j import GraphDatabase
        uri = os.environ["NEO4J_TEST_URI"]
        password = os.environ["NEO4J_TEST_PASSWORD"]
        with GraphDatabase.driver(uri, auth=("neo4j", password)) as driver:
            with driver.session() as session:
                if session.run("MATCH (n) RETURN count(n) AS n").single()["n"]:
                    self.fail("Refusing to run: test Neo4j must contain no nodes")
            rows = [product(1), product(2)]
            writer = Neo4jProductWriter(driver)
            try:
                self.assertEqual(writer.upsert(rows), 2)
                self.assertEqual(writer.upsert(rows), 2)
                with driver.session() as session:
                    self.assertEqual(session.run("MATCH (:Product)-[r]->() RETURN count(r) AS n").single()["n"], 10)
                changed = [replace(rows[0], material="Vàng 18K", entity_ids=(1, 1, 2, 1, 1)), rows[1]]
                self.assertEqual(writer.upsert(changed), 2)
                with driver.session() as session:
                    values = list(session.run("MATCH (:Product {product_id:1})-[:MADE_OF]->(m) RETURN m.material_id AS id"))
                    self.assertEqual([r["id"] for r in values], [2])
            finally:
                # The initial emptiness check and opt-in flag scope all writes to a test graph.
                with driver.session() as session:
                    session.run("MATCH (p:Product) WHERE p.product_id IN [1,2] DETACH DELETE p").consume()
                    for label, key in (("Category", "category_id"), ("Brand", "brand_id"), ("Material", "material_id"),
                                       ("Gemstone", "gemstone_id"), ("Collection", "collection_id")):
                        session.run(f"MATCH (n:{label}) WHERE n.{key} IN [1,2] AND NOT (n)--() DELETE n").consume()


if __name__ == "__main__":
    unittest.main()
