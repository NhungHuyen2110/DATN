from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lumiere.configuration import load_aliases
from lumiere.linking import EntityLinkingService, SemanticEntityResolver
from lumiere.understanding import QueryUnderstandingService, requested_top_k
from lumiere.text import nfc


class EntityLinkingTests(unittest.TestCase):
    def test_female_paraphrases_link_without_assuming_adult_age(self):
        linker = EntityLinkingService()
        for recipient in ("phái nữ", "nữ giới", "phụ nữ", "con gái", "phai nu"):
            with self.subTest(recipient=recipient):
                result = linker.resolve("nhẫn cho " + recipient)
                self.assertEqual(result.entities["audience"], ("female",))
                self.assertEqual(result.entities["category"], ("nhan",))
                self.assertTrue(result.evidence)
                self.assertTrue(all(e["alias_version"] for e in result.evidence))

    def test_child_context_does_not_link_to_generic_adult_products(self):
        self.assertEqual(EntityLinkingService().link("nhẫn tặng con gái 8 tuổi")["audience"], ("female_child",))

    def test_negation_and_homograph_recipient(self):
        result = EntityLinkingService().resolve("nhẫn bạc không kim cương")
        self.assertEqual(result.excluded["gemstone"], ("diamond",))
        self.assertNotIn("gemstone", result.entities)
        self.assertNotIn("material", EntityLinkingService().link("nhẫn tặng bác gái"))

    def test_unknown_mandatory_style_requires_clarification(self):
        self.assertTrue(EntityLinkingService().resolve("nhẫn phong cách abcxyz").ambiguities)

    def test_semantic_linking_uses_cosine_threshold_and_margin(self):
        # Vector fixtures test decisions only; real-model evidence is separate.
        class Encoder:
            def encode(self, texts):
                if len(texts) == 1:
                    return [[1, 0, 0]]
                return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

        config = load_aliases()
        linked = EntityLinkingService(config, SemanticEntityResolver(Encoder(), config)).resolve("nhẫn thiết kế gọn nhẹ")
        self.assertEqual(linked.entities["style"], ("minimalist",))
        evidence = next(e for e in linked.evidence if e["method"] == "embedding_cosine")
        self.assertEqual(evidence["confidence"], 1)
        self.assertEqual(evidence["margin"], 1)

    def test_top_k_seed_and_nfc(self):
        context = QueryUnderstandingService(EntityLinkingService()).understand("Top 3 cùng đá và phong cách với sản phẩm 900101", 3)
        self.assertEqual(context.seed_product_id, 900101)
        self.assertIn("HAS_GEMSTONE", context.required_relationships)
        self.assertIn("HAS_STYLE", context.required_relationships)
        self.assertEqual(requested_top_k("Top 5 nhẫn"), 5)
        self.assertEqual(nfc("nu\u031b\u0303"), "nữ")
