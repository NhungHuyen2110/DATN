from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jewelry_agents.entity_linking import link_query, cosine


class EntityLinkingTests(unittest.TestCase):
    def test_female_paraphrases_and_unaccented_category(self):
        for query in ("Nhẫn cho phái nữ", "Nhẫn cho phụ nữ", "Nhẫn cho nữ giới", "nhẫn cho con gái", "nhan cho phai nu"):
            with self.subTest(query=query):
                result = link_query(query)
                ids = {item["canonical_id"] for item in result["entities"]}
                self.assertTrue({"ring", "female"}.issubset(ids))
                self.assertFalse(result["needs_clarification"])

    def test_child_context_never_maps_to_adult(self):
        for query in ("mua nhẫn tặng con gái 8 tuổi", "nhan cho con gai 12 tuoi", "nhẫn cho bé gái"):
            result = link_query(query)
            ids = {item["canonical_id"] for item in result["entities"]}
            self.assertIn("child_female", ids)
            self.assertNotIn("female", ids)
            self.assertTrue(result["needs_clarification"])

    def test_word_boundary_does_not_match_cz_inside_word(self):
        self.assertNotIn("cz", {e["canonical_id"] for e in link_query("abcxyz")['entities']})
        self.assertIn("cz", {e["canonical_id"] for e in link_query("nhẫn CZ")['entities']})

    def test_refined_is_not_minimalist(self):
        self.assertIn("refined", {e['canonical_id'] for e in link_query("nhẫn tinh tế")['entities']})
        self.assertNotIn("minimalist", {e['canonical_id'] for e in link_query("nhẫn tinh tế")['entities']})

    def test_multiple_categories_require_resolution(self):
        self.assertTrue(link_query("nhẫn hoặc dây chuyền")['needs_clarification'])

    def test_cosine_is_normalized_and_dimensions_checked(self):
        self.assertAlmostEqual(cosine([2, 0], [20, 0]), 1.0)
        self.assertEqual(cosine([0, 0], [20, 0]), 0.0)
        with self.assertRaises(ValueError):
            cosine([1], [1, 2])

    def test_cosine_accepts_actual_numpy_encoder_output(self):
        import numpy as np
        self.assertAlmostEqual(cosine(np.array([2.0, 0]), np.array([20.0, 0])), 1.0)

    def test_semantic_path_uses_measured_scores_and_does_not_override_alias(self):
        class Encoder:
            def encode(self, texts):
                # Synthetic vectors test the decision rule, not real model accuracy.
                return [[1.0, 0.0]] + [[1.0, 0.0] if t == 'thanh lịch' else [0.0, 1.0] for t in texts[1:]]
        result = link_query("nhẫn sang trọng", encoder=Encoder())
        matched = next(e for e in result['entities'] if e['canonical_id'] == 'elegant')
        self.assertEqual(matched['method'], 'embedding_candidate')
        self.assertAlmostEqual(matched['similarity'], 1.0)
        self.assertIn('ring', {e['canonical_id'] for e in result['entities']})


if __name__ == '__main__':
    unittest.main()
