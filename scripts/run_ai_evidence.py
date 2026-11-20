"""Real model + local Qdrant + owned test Neo4j engineering acceptance.

Synthetic labels are engineering fixtures, never human-reviewed benchmark truth.
No production target options, deletion, or collection recreation are provided.
"""
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "AI"))


def main():
    from neo4j import GraphDatabase
    from qdrant_client import QdrantClient
    from lumiere.adapters import DenseRetriever, Neo4jGraphRetriever, QdrantProductIndex, REPRESENTATION_VERSION
    from lumiere.bootstrap import DEFAULT_MODEL, SemanticModelProvider
    from lumiere.catalog import CsvProductRepository, SnapshotProductRepository, validate_catalog
    from lumiere.configuration import load_aliases
    from lumiere.ingestion import Neo4jProductWriter
    from lumiere.linking import EntityLinkingService, SemanticEntityResolver
    from lumiere.retrieval import GroundedAnswerService, HybridRetrievalService, LexicalRetriever, RankFusionService
    from lumiere.understanding import QueryUnderstandingService

    started = perf_counter()
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.environ.setdefault("AI_MODEL_CACHE", str(ROOT / ".cache/hf/models"))
    os.environ.setdefault("HF_HOME", str(ROOT / ".cache/hf"))
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    real_path, fixture_path = ROOT / "output/products_ai.csv", ROOT / "AI/tests/fixtures/catalog_semantic.csv"
    real, fixtures = CsvProductRepository(real_path).all(), CsvProductRepository(fixture_path).all()
    products = validate_catalog([*real, *fixtures])
    report = {"run_utc": run, "scope": "engineering acceptance, NOT human-reviewed relevance benchmark",
              "representation_version": REPRESENTATION_VERSION,
              "sources": [{"file": str(p.relative_to(ROOT)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                          for p in (real_path, fixture_path)],
              "real_products": len(real), "synthetic_products": len(fixtures),
              "real_products_with_optional_evidence": sum(bool(p.facts) for p in real), "checks": []}

    def check(name, condition, **evidence):
        report["checks"].append({"name": name, "passed": bool(condition), **evidence})
        print(name, "PASS" if condition else "FAIL", flush=True)
        if not condition:
            raise AssertionError(name)

    try:
        password = os.environ["NEO4J_TEST_PASSWORD"]
        with GraphDatabase.driver("bolt://127.0.0.1:17687", auth=("neo4j", password)) as driver:
            with driver.session() as session:
                directory = session.run("SHOW SETTINGS YIELD name,value WHERE name='server.directories.data' RETURN value").single()["value"]
                if Path(directory).resolve() != (ROOT / ".cache/neo4j-test/data").resolve():
                    raise RuntimeError("Refusing a graph outside the owned test directory")
            report["graph_data_directory"] = directory
            writer = Neo4jProductWriter(driver, batch_size=100)
            writer.upsert(products)
            first = writer.verify(products)
            writer.upsert(products)
            second = writer.verify(products)
            check("csv_graph_508_idempotent", first == second and second["verified_products"] == 508,
                  verification=second)
            # Mutate one synthetic record, verify removal of its stale edge, restore it.
            changed = replace(fixtures[0], material=fixtures[5].material,
                              entity_ids=(*fixtures[0].entity_ids[:2], fixtures[5].entity_ids[2], *fixtures[0].entity_ids[3:]))
            writer.upsert([changed])
            writer.verify([changed])
            with driver.session() as session:
                edges = session.run("MATCH (:Product {product_id:900101})-[:MADE_OF]->(m) RETURN collect(m.material_id) AS ids").single()["ids"]
            check("synthetic_material_update", edges == [changed.entity_ids[2]], ids=edges)
            writer.upsert([fixtures[0]])
            resume = Neo4jProductWriter(driver, resume_ids=[p.id for p in products])
            check("resume_verifies_existing_facts", resume.upsert(products) == 508)

            provider = SemanticModelProvider()
            vectors = provider.encode(["nhẫn cho phái nữ", "nhẫn dành cho phụ nữ"])
            cosine = sum(a*b for a,b in zip(*vectors))
            check("actual_multilingual_model", len(vectors[0]) == 384 and cosine > .8,
                  model=DEFAULT_MODEL, dimension=len(vectors[0]), paraphrase_cosine=cosine)
            storage = ROOT / ".cache" / ("qdrant-evidence-" + run)
            with closing(QdrantClient(path=str(storage))) as client:
                collection = "lumiere_evidence_v2"
                index = QdrantProductIndex(client, provider, collection, DEFAULT_MODEL)
                check("actual_vectors_508_readback", index.upsert(products) == 508)
                index.upsert(products)
                check("vector_replay_no_duplicates", client.count(collection).count == 508)
                repository = SnapshotProductRepository(fixtures)
                understanding = QueryUnderstandingService(EntityLinkingService(load_aliases(), SemanticEntityResolver(provider, load_aliases())))
                dense = DenseRetriever(client, provider, collection, repository, DEFAULT_MODEL)
                graph = Neo4jGraphRetriever(driver, repository)
                lexical = LexicalRetriever(repository)

                def service(retrievers, verifier=None):
                    return GroundedAnswerService(HybridRetrievalService(repository, retrievers, understanding, RankFusionService(), verifier=verifier))

                smoke = [
                    ("top3_enough", "nhẫn cho phái nữ dưới 8 triệu", 3, {900101,900102,900103,900104}, 3),
                    ("female_paraphrase", "nhẫn thanh lịch cho phụ nữ dưới 8 triệu", 3, {900101,900102}, 2),
                    ("child_context", "nhẫn cho con gái 8 tuổi", 3, {900104}, 1),
                    ("negative_material", "nhẫn không vàng dưới 8 triệu", 3, {900101,900102,900103,900104}, 3),
                    ("graph_same_gem_style", "cùng đá và phong cách với sản phẩm #900101", 3, {900102,900107}, 2),
                ]
                report["retrieval_cases"] = []
                for name, query, k, allowed, expected_count in smoke:
                    t = perf_counter()
                    answer = service([dense, lexical, graph]).answer(query, k)
                    ids = [p["ProductID"] for p in answer["products"]]
                    evidence = {"query": query, "ids": ids, "seconds": perf_counter()-t,
                                "degraded_sources": answer["degraded_sources"],
                                "paths": [p.get("matched_relationships", []) for p in answer["products"]]}
                    context = understanding.understand(query, k)
                    evidence["entity_linking_evidence"] = list(context.linking_evidence)
                    evidence["entities"] = context.entities
                    report["retrieval_cases"].append(evidence)
                    check(name, len(ids) == expected_count and len(set(ids)) == len(ids) and set(ids) <= allowed
                          and not answer["degraded_sources"], **evidence)
                    if name.startswith("graph"):
                        check("actual_graph_paths", all({p["relationship"] for p in paths} >= {"HAS_GEMSTONE","HAS_STYLE"} for paths in evidence["paths"]))

                report["ablation_smoke"] = {}
                for name, retrievers in (("lexical", [lexical]), ("dense", [dense]), ("graph", [graph]), ("hybrid", [dense,lexical,graph])):
                    answer = service(retrievers).answer("nhẫn cho phái nữ dưới 8 triệu", 3)
                    report["ablation_smoke"][name] = [p["ProductID"] for p in answer["products"]]
                class Unavailable:
                    name = "graph"
                    def retrieve(self, context, limit):
                        raise ConnectionError("injected engineering fault")
                degraded = service([dense, lexical, Unavailable()]).answer("nhẫn dưới 8 triệu", 3)
                check("graph_fault_degrades", len(degraded["products"]) == 3 and degraded["degraded_sources"] == ["graph"])
                updated = SnapshotProductRepository([replace(p, stock=0, published=False) if p.id == 900101 else p for p in fixtures])
                answer = service([dense,lexical,graph], updated).answer("nhẫn dưới 8 triệu", 3)
                check("live_catalog_revalidation", len(answer["products"]) == 3 and all(p["ProductID"] != 900101 for p in answer["products"]))
                # Search real catalog separately: no synthetic labels influence this request.
                real_repo = SnapshotProductRepository(real)
                real_dense = DenseRetriever(client, provider, collection, real_repo, DEFAULT_MODEL)
                real_answer = GroundedAnswerService(HybridRetrievalService(real_repo, [real_dense,LexicalRetriever(real_repo),Neo4jGraphRetriever(driver,real_repo)], understanding, RankFusionService())).answer("nhẫn bạc dưới 8 triệu", 3)
                check("real_catalog_hybrid", len(real_answer["products"]) == 3 and not real_answer["degraded_sources"],
                      ids=[p["ProductID"] for p in real_answer["products"]])
                direct = GroundedAnswerService(HybridRetrievalService(real_repo, [real_dense,LexicalRetriever(real_repo)], understanding, RankFusionService())).answer("Tìm sản phẩm SP000001", 1)
                check("real_sku_identity", [p["ProductID"] for p in direct["products"]] == [1])
                report["qdrant_directory"] = str(storage.relative_to(ROOT))
            # Close the local Qdrant owner before the real HTTP composition opens it.
            from fastapi.testclient import TestClient
            import api
            api.app.state.embedding_provider = provider
            os.environ.update({"AI_PIPELINE": "modular", "AI_CATALOG_SOURCE": "csv",
                "AI_CATALOG_PATH": str(fixture_path), "AI_QDRANT_PATH": str(storage),
                "QDRANT_COLLECTION": collection, "AI_DENSE_ENABLED": "true", "AI_GRAPH_ENABLED": "true",
                "NEO4J_URI": "bolt://127.0.0.1:17687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": password})
            with TestClient(api.app) as http:
                check("http_readiness_real_dependencies", http.get("/health/ready").status_code == 200)
                response = http.post("/chat", json={"query": "top 3 nhẫn cho phái nữ dưới 8 triệu"})
                body = response.json()
                check("http_modular_real_dependencies", response.status_code == 200 and len(body["products"]) == 3
                      and not body["degraded_sources"], ids=[p["ProductID"] for p in body["products"]])
                body = http.post("/chat", json={"query": "cùng đá và phong cách với sản phẩm #900101"}).json()
                check("http_graph_recommendation", {p["ProductID"] for p in body["products"]} == {900102,900107}
                      and not body["degraded_sources"])
        report["status"] = "PASS"
    except Exception as exc:
        report["status"], report["error_type"] = "FAIL", type(exc).__name__
        raise
    finally:
        report["elapsed_seconds"] = perf_counter()-started
        target = ROOT / "docs/evidence/ai-live-acceptance.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
