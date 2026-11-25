
import unittest

from jewelry_agents.ontology_reasoner import (
    reason_categories,
    rank_with_knowledge,
)


class OntologyReasonerTests(unittest.TestCase):

    def test_finger(self):
        result = reason_categories(
            "Tôi muốn mua món trang sức đeo quanh ngón tay"
        )
        self.assertEqual(result["eligible"], ["ring"])

    def test_neck(self):
        result = reason_categories(
            "Tôi muốn mua món trang sức đeo quanh cổ"
        )
        self.assertEqual(result["eligible"], ["necklace"])

    def test_wrist(self):
        result = reason_categories(
            "Tôi muốn mua món trang sức đeo quanh cổ tay"
        )
        self.assertEqual(
            set(result["eligible"]),
            {"bracelet", "chain_bracelet"},
        )

    def test_ear(self):
        result = reason_categories(
            "Tôi muốn mua món trang sức đeo ở tai"
        )
        self.assertEqual(result["eligible"], ["earring"])

    def test_attachment(self):
        result = reason_categories(
            "Tôi muốn mua phụ kiện nhỏ gắn vào vòng tay"
        )
        self.assertEqual(result["eligible"], ["charm"])

    def test_generic_request(self):
        result = reason_categories(
            "Tôi muốn mua một món trang sức đẹp"
        )
        self.assertEqual(result["status"], "no_evidence")

    def test_negation(self):
        result = reason_categories(
            "Tôi không muốn đeo trang sức ở ngón tay"
        )
        self.assertEqual(result["eligible"], [])

    def test_indirect_finger(self):
        result = reason_categories(
            "Có món nào ôm lấy ngón áp út không"
        )
        self.assertEqual(result["eligible"], ["ring"])

    def test_multiple_locations(self):
        result = reason_categories(
            "Tôi muốn đeo ở cổ hoặc cổ tay"
        )
        self.assertEqual(result["status"], "no_evidence")

    def test_flexible_chain(self):
        result = reason_categories(
            "Tôi muốn đeo sợi mềm quanh cổ tay"
        )
        self.assertEqual(
            result["eligible"],
            ["chain_bracelet"],
        )

    def test_knowledge_filter(self):
        scores = {
            "charm": 0.6233,
            "necklace": 0.6169,
            "ring": 0.5620,
            "chain_bracelet": 0.5586,
            "bracelet": 0.5355,
        }

        result = rank_with_knowledge(
            "Trang sức đeo quanh cổ tay",
            scores,
        )

        self.assertEqual(
            [key for key, score in result["ranked"]],
            ["chain_bracelet", "bracelet"],
        )


if __name__ == "__main__":
    unittest.main()
