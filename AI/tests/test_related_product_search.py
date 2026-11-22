import unittest
from jewelry_agents.search_service import search


def product(pid, category=1, gemstone=5, material=2, name=None):
    return {'ProductID': pid, 'ProductName': name or 'Synthetic ' + str(pid), 'SKU': 'SYNTHETIC' + str(pid),
            'CategoryID': category, 'Category': 'Nhẫn' if category == 1 else 'Bông tai',
            'GemstoneID': gemstone, 'Gemstone': 'Moissanite' if gemstone == 5 else 'Ruby',
            'MaterialID': material, 'Material': 'Bạc 925', 'Price': '100', 'Stock': 2}


class RelatedProductSearchTests(unittest.TestCase):
    def run_search(self, query, catalog=None, graph=None):
        live = catalog or {1: product(1, category=3, name='Bông tai Angel'), 2: product(2),
                           3: product(3, gemstone=2), 4: product(4, material=3)}
        self.seen = []
        def dense(query, top_k, eligible_ids):
            self.seen.append((query, eligible_ids))
            return [{'ProductID': pid} for pid in eligible_ids]
        return search(query, 3, dense=dense, catalog=lambda: live, parse_price=lambda q: {}, graph=graph)

    def test_same_gemstone_uses_live_reference_id_and_never_returns_source_itself(self):
        result = self.run_search('Top 3 nhẫn cùng loại đá với sản phẩm 1')
        self.assertEqual({item['ProductID'] for item in result['products']}, {2, 4})
        self.assertTrue(all(item['GemstoneID'] == 5 for item in result['products']))
        self.assertIn('Bông tai Angel', self.seen[0][0])
        self.assertNotIn(1, self.seen[0][1])

    def test_same_material_and_gemstone_constraints_both_hold(self):
        result = self.run_search('nhẫn cùng đá và cùng chất liệu với sản phẩm 1')
        self.assertEqual([item['ProductID'] for item in result['products']], [2])

    def test_unique_reference_name_does_not_add_an_unwanted_category_constraint(self):
        result = self.run_search('nhẫn cùng đá với Bông tai Angel')
        self.assertEqual({item['ProductID'] for item in result['products']}, {2, 4})

    def test_missing_reference_conflicting_stone_and_unsupported_style_abstain(self):
        for query, status in (('nhẫn cùng đá với sản phẩm 999', 'reference_unavailable'),
                              ('nhẫn cùng đá', 'clarification_required'),
                              ('nhẫn ruby cùng đá với sản phẩm 1', 'clarification_required'),
                              ('cùng đá và cùng phong cách với sản phẩm 1', 'missing_verified_attributes')):
            with self.subTest(query=query):
                result = self.run_search(query)
                self.assertEqual(result['status'], status)
                self.assertEqual(result['products'], [])
        self.assertEqual(self.run_search('Tìm sản phẩm cùng loại đá và phong cách với sản phẩm 1')['status'],
                         'missing_verified_attributes')

    def test_reference_taxonomy_change_during_search_does_not_return_stale_equality(self):
        first = {1: product(1), 2: product(2)}
        latest = {**first, 1: product(1, gemstone=2)}
        versions = iter([first, latest])
        result = search('nhẫn cùng đá với sản phẩm 1', 3,
                        dense=lambda *a, **k: [{'ProductID': 2}], catalog=lambda: next(versions), parse_price=lambda q: {})
        self.assertEqual(result['status'], 'reference_changed')
        self.assertEqual(result['products'], [])
