"""Core acceptance tests run without SDKs, servers or model downloads."""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lumiere.catalog import CsvProductRepository, SnapshotProductRepository, validate_catalog
from lumiere.domain import Candidate, Product
from lumiere.ingestion import ProductSyncService
from lumiere.retrieval import GroundedAnswerService, HybridRetrievalService, LexicalRetriever, RankFusionService
from lumiere.understanding import EntityLinkingService, QueryUnderstandingService, price_bounds


def product(ident, **kwargs):
    base = Product(ident, f"SP{ident}", f"Nhẫn {ident}", Decimal("2000000"), 5,
                   "Nhẫn", "PNJ", "Bạc 925", "Diamond", "Office", (1, 1, 1, 1, 1))
    return replace(base, **kwargs)


class ModularPipelineTests(unittest.TestCase):
    def setUp(self):
        self.understanding = QueryUnderstandingService(EntityLinkingService())

    def service(self, products, extra=()):
        repository = SnapshotProductRepository(products)
        return GroundedAnswerService(HybridRetrievalService(repository,
            [*extra, LexicalRetriever(repository)], self.understanding, RankFusionService()))

    def test_aliases_accents_and_specific_material(self):
        cases = [("hoa tai kim cương", "category", ("bong tai",)),
                 ("lắc tay platinum", "material", ("bach kim",)),
                 ("NHẪN VÀNG TRẮNG 18K", "material", ("vang trang 18k",)),
                 ("nhẫn đá CZ", "gemstone", ("cz",))]
        for query, field, expected in cases:
            with self.subTest(query=query):
                self.assertEqual(self.understanding.understand(query, 3).entities[field], expected)
        self.assertNotIn("gemstone", EntityLinkingService().link("czarina"))

    def test_price_ranges_and_shared_units(self):
        for query, expected in [("từ 3 đến 5 triệu", (3000000, 5000000)),
                                ("từ 3 triệu đến 5 triệu", (3000000, 5000000)),
                                ("ngân sách khoảng 2,5 triệu", (None, 2500000)),
                                ("dưới 500 nghìn", (None, 500000)),
                                ("tầm giá 7 triệu", (None, 7000000))]:
            with self.subTest(query=query):
                self.assertEqual(price_bounds(query), expected)
        with self.assertRaises(ValueError):
            price_bounds("từ 5 đến 3 triệu")

    def test_exact_top_k_after_hard_filters_and_duplicate_source_ids(self):
        rows = [product(i) for i in range(1, 15)] + [product(15, stock=0), product(16, price=Decimal("9000000"))]
        dense = Mock(name="dense", **{"retrieve.return_value": [Candidate(15, 1), Candidate(16, .9), Candidate(1, .8), Candidate(1, .7)]})
        result = self.service(rows, [dense]).answer("nhẫn bạc kim cương dưới 3 triệu", 10)
        self.assertEqual(len(result["products"]), 10)
        ids = [p["ProductID"] for p in result["products"]]
        self.assertEqual(len(set(ids)), 10)
        self.assertNotIn(15, ids)
        self.assertNotIn(16, ids)

    def test_source_faults_cannot_relax_filters_or_invent_products(self):
        failed = Mock(**{"retrieve.side_effect": ConnectionError("private server details")})
        failed.name = "graph"
        result = self.service([product(1), product(2, price=Decimal("8000000"))], [failed]).answer("nhẫn dưới 3 triệu", 5)
        self.assertEqual([p["ProductID"] for p in result["products"]], [1])
        self.assertEqual(result["degraded_sources"], ["graph"])
        self.assertNotIn("private server", str(result))
        self.assertTrue(result["products"][0]["explanation"])

    def test_material_and_gemstone_never_fallback_to_unrelated_stock(self):
        result = self.service([product(1), product(2, material="Vàng 18K", gemstone="CZ", entity_ids=(1, 1, 2, 2, 1))]).answer("nhẫn bạc CZ", 5)
        self.assertEqual(result["products"], [])

    def test_ties_stable_and_grounded_answer_ignores_injected_name_in_query(self):
        service = self.service([product(3), product(2), product(1)])
        a = service.answer("nhẫn bịa giá 1 đồng cho Unicorn", 3)
        b = service.answer("nhẫn bịa giá 1 đồng cho Unicorn", 3)
        self.assertEqual(a, b)
        self.assertEqual([p["ProductID"] for p in a["products"]], [1, 2, 3])
        self.assertNotIn("Unicorn", a["answer"])
        self.assertIn("2.000.000 VNĐ", a["answer"])
        self.assertNotIn("CostPrice", str(a))

    def test_unknown_query_does_not_return_arbitrary_catalog_rows(self):
        self.assertEqual(self.service([product(1)]).answer("abcdefghijk", 3)["products"], [])

    def test_grounded_price_does_not_round_fractional_or_large_decimal_facts(self):
        result = self.service([product(1, price=Decimal("9999999999999999.99"))]).answer("nhẫn", 1)
        self.assertEqual(result["products"][0]["PriceVND"], "9999999999999999.99")
        self.assertIn("9.999.999.999.999.999,99 VNĐ", result["answer"])

    def test_validation_before_sync_and_replay_uses_same_identities(self):
        repo = SnapshotProductRepository([product(1), product(2)])
        graph, vectors = Mock(), Mock()
        graph.upsert.return_value = vectors.upsert.return_value = 2
        sync = ProductSyncService(repo, graph, vectors)
        self.assertEqual(sync.synchronize(), sync.synchronize())
        self.assertEqual(graph.upsert.call_args_list[0], graph.upsert.call_args_list[1])
        # This verifies replay orchestration, not server-side idempotency.
        broken = Mock(**{"all.return_value": [product(1), product(1)]})
        with self.assertRaises(ValueError):
            ProductSyncService(broken, graph, vectors).synchronize()
        self.assertEqual(graph.upsert.call_count, 2)

    def test_source_catalog_validates_all_500_records_and_stable_ids(self):
        rows = CsvProductRepository(Path(__file__).resolve().parents[2] / "output/products_ai.csv").all()
        self.assertEqual(len(rows), 500)
        self.assertEqual({p.id for p in rows}, set(range(1, 501)))
        self.assertTrue(all("CostPrice" not in p.public() for p in rows))

    def test_invalid_values_and_conflicting_taxonomy_rejected(self):
        for kwargs in ({"price": Decimal("NaN")}, {"price": Decimal("1e1000")}, {"price": Decimal("1.001")},
                       {"stock": -1}, {"entity_ids": (0, 1, 1, 1, 1)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                product(1, **kwargs)
        with self.assertRaises(ValueError):
            validate_catalog([product(1), product(2, material="Vàng")])

    def test_fusion_deduplicates_each_source(self):
        result = RankFusionService().fuse([[Candidate(1, 1), Candidate(1, .5)], [Candidate(1, 1)]])
        self.assertAlmostEqual(result[1], 2 / 61)


if __name__ == "__main__":
    unittest.main()
