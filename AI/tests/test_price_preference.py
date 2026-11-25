import unittest

from jewelry_agents.ranking import (
    rerank_price_preference,
    finalize_topk
)


class PricePreferenceTests(unittest.TestCase):

    def setUp(self):
        self.live = {
            1: {'ProductID': 1, 'Price': 1000000, 'Stock': 5},
            2: {'ProductID': 2, 'Price': 5000000, 'Stock': 5},
            3: {'ProductID': 3, 'Price': 10000000, 'Stock': 5},
        }

        self.candidates = [
            {'ProductID': 3, 'score': 0.9},
            {'ProductID': 2, 'score': 0.8},
            {'ProductID': 1, 'score': 0.7},
        ]

    def test_neutral_preserves_original_ranking(self):
        result = rerank_price_preference(
            self.candidates,
            self.live,
            'neutral'
        )

        self.assertEqual(result, self.candidates)

    def test_affordable_prefers_lower_price(self):
        result = rerank_price_preference(
            self.candidates,
            self.live,
            'affordable',
            weight=1.0
        )

        self.assertEqual(
            [p['ProductID'] for p in result],
            [1, 2, 3]
        )

    def test_higher_price_preference(self):
        result = rerank_price_preference(
            self.candidates,
            self.live,
            'higher_price',
            weight=1.0
        )

        self.assertEqual(
            [p['ProductID'] for p in result],
            [3, 2, 1]
        )

    def test_relevance_is_preserved(self):
        result = rerank_price_preference(
            self.candidates,
            self.live,
            'affordable',
            weight=0.0
        )

        self.assertEqual(
            [p['ProductID'] for p in result],
            [3, 2, 1]
        )

    def test_no_fabricated_products(self):
        result = rerank_price_preference(
            self.candidates,
            self.live,
            'affordable'
        )

        self.assertEqual(
            {p['ProductID'] for p in result},
            {1, 2, 3}
        )

    def test_equal_prices_do_not_crash(self):
        for product in self.live.values():
            product['Price'] = 2000000

        result = rerank_price_preference(
            self.candidates,
            self.live,
            'affordable'
        )

        self.assertEqual(len(result), 3)

    def test_empty_candidates(self):
        self.assertEqual(
            rerank_price_preference(
                [], self.live, 'affordable'
            ),
            []
        )

    def test_invalid_weight(self):
        with self.assertRaises(ValueError):
            rerank_price_preference(
                self.candidates,
                self.live,
                'affordable',
                weight=1.5
            )

    def test_stock_and_budget_still_enforced(self):
        self.live[1]['Stock'] = 0

        ranked = rerank_price_preference(
            self.candidates,
            self.live,
            'affordable'
        )

        result = finalize_topk(
            ranked,
            3,
            {'max_price': 6000000},
            self.live
        )

        self.assertEqual(
            [p['ProductID'] for p in result],
            [2]
        )


if __name__ == '__main__':
    unittest.main()