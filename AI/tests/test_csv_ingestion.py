import csv
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lumiere.catalog import CatalogValidationError, CsvProductRepository
from lumiere.domain import Candidate
from lumiere.matching import eligible
from lumiere.understanding import EntityLinkingService, QueryUnderstandingService
from lumiere.retrieval import GroundedAnswerService, HybridRetrievalService, LexicalRetriever, RankFusionService
from lumiere.catalog import SnapshotProductRepository
from lumiere.recommendation import path_supported
import sync_catalog

FIXTURE = Path(__file__).parent / "fixtures/catalog_semantic.csv"


class CsvIngestionTests(unittest.TestCase):
    def test_facts_lineage_and_optional_metadata_are_not_guessed(self):
        rows = CsvProductRepository(FIXTURE).all()
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0].lineage.source, FIXTURE.name)
        self.assertEqual(rows[0].lineage.sha256, hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
        self.assertEqual(rows[0].facts[0].canonical_id, "female")
        real = CsvProductRepository(FIXTURE.parents[3] / "output/products_ai.csv").all()
        self.assertTrue(all(not p.facts for p in real))

    def test_quoted_decimal_bom_and_invalid_rows_have_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.csv"
            with FIXTURE.open(encoding="utf-8") as fixture_file:
                original = list(csv.DictReader(fixture_file))
            original[0]["SalePrice"] = "2.500.000,50"
            with source.open("w", encoding="utf-8-sig", newline="") as out:
                writer = csv.DictWriter(out, original[0].keys())
                writer.writeheader()
                writer.writerows(original)
            self.assertEqual(CsvProductRepository(source).all()[0].price, Decimal("2500000.50"))
            original[0]["Stock"] = "-1"
            with source.open("w", encoding="utf-8", newline="") as out:
                writer = csv.DictWriter(out, original[0].keys())
                writer.writeheader()
                writer.writerows(original)
            with self.assertRaises(CatalogValidationError) as error:
                CsvProductRepository(source).all()
            self.assertEqual(error.exception.report["errors"][0]["row"], 2)
            report = Path(tmp) / "report.json"
            self.assertEqual(sync_catalog.main(["--file", str(source), "--dry-run", "--report", str(report)]), 1)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"], "invalid_input")

    def test_duplicate_headers_and_missing_evidence_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.csv"
            raw = FIXTURE.read_text(encoding="utf-8")
            path.write_text(raw.replace("ProductID,SKU", "ProductID,ProductID", 1), encoding="utf-8")
            with self.assertRaises(CatalogValidationError):
                CsvProductRepository(path).all()
            path.write_text(raw.replace("Fixture được gán nhãn phái nữ", "", 1), encoding="utf-8")
            with self.assertRaises(CatalogValidationError):
                CsvProductRepository(path).all()

    def test_filters_published_age_and_no_unrelated_backfill(self):
        repository = SnapshotProductRepository(CsvProductRepository(FIXTURE).all())
        understanding = QueryUnderstandingService(EntityLinkingService())
        service = GroundedAnswerService(HybridRetrievalService(repository, [LexicalRetriever(repository)], understanding, RankFusionService()))
        found = service.answer("nhẫn thanh lịch cho phái nữ dưới 8 triệu", 3)
        self.assertEqual({p["ProductID"] for p in found["products"]}, {900101, 900102})
        child = service.answer("nhẫn cho con gái 8 tuổi", 3)
        self.assertEqual([p["ProductID"] for p in child["products"]], [900104])
        self.assertIn("Chỉ tìm thấy 1", child["answer"])

    def test_live_revalidation_excludes_newly_hidden_or_expensive_stock(self):
        original = CsvProductRepository(FIXTURE).all()
        before = SnapshotProductRepository(original)
        after = SnapshotProductRepository([replace(p, stock=0) if p.id == 900101 else p for p in original])
        service = HybridRetrievalService(before, [LexicalRetriever(before)], QueryUnderstandingService(EntityLinkingService()), RankFusionService(), verifier=after)
        rows, _ = service.search("nhẫn dưới 8 triệu", 5)
        self.assertNotIn(900101, [p["ProductID"] for p in rows])

    def test_stale_graph_paths_cannot_be_claimed_as_verified(self):
        rows = {p.id: p for p in CsvProductRepository(FIXTURE).all()}
        valid = {"source_product_id": 900101, "target_product_id": 900102, "relationship": "HAS_GEMSTONE", "entity_id": 1, "entity_name": "Diamond"}
        self.assertTrue(path_supported(valid, rows))
        self.assertFalse(path_supported({**valid, "entity_name": "Ruby"}, rows))
        self.assertFalse(path_supported({**valid, "target_product_id": 900104}, rows))

    def test_direct_sku_lookup_is_not_a_recommendation_seed(self):
        repository = SnapshotProductRepository(CsvProductRepository(FIXTURE).all())
        service = GroundedAnswerService(HybridRetrievalService(repository, [LexicalRetriever(repository)],
            QueryUnderstandingService(EntityLinkingService()), RankFusionService()))
        for query in ("Tìm mã TEST-N001", "Cho tôi sản phẩm #900101"):
            self.assertEqual([p["ProductID"] for p in service.answer(query)["products"]], [900101])
        self.assertEqual(service.answer("Tìm sản phẩm #999999")["products"], [])

    def test_seed_is_revalidated_after_retrieval(self):
        rows = CsvProductRepository(FIXTURE).all()
        before = SnapshotProductRepository(rows)
        after = SnapshotProductRepository([replace(p, gemstone="Ruby", entity_ids=(*p.entity_ids[:3],2,p.entity_ids[4])) if p.id == 900101 else p for p in rows])
        service = HybridRetrievalService(before, [LexicalRetriever(before)], QueryUnderstandingService(EntityLinkingService()), RankFusionService(), verifier=after)
        found, degraded = service.search("cùng đá với sản phẩm #900101", 3)
        self.assertEqual(found, [])
        self.assertIn("seed_changed_during_search", degraded)
