
import unittest
from jewelry_agents.retrieval import extract_price_filter


class PriceIntentTests(unittest.TestCase):

    def test_budget_phrases(self):
        cases = [
            ("Tôi có ngân sách 7 triệu", 7_000_000),
            ("Tìm nhẫn dưới 5 triệu", 5_000_000),
            ("Gợi ý quà sinh nhật tầm 3 triệu", 3_000_000),
            ("Trang sức khoảng 5 triệu", 5_000_000),
            ("Vòng tay tầm giá 7 triệu", 7_000_000),
        ]

        for question, expected in cases:
            with self.subTest(question=question):
                result = extract_price_filter(question)
                self.assertEqual(result["max_price"], expected)


if __name__ == "__main__":
    unittest.main()
