import ast
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jewelry_agents.search_service import search, RetrievalUnavailable

# Existing money functions without importing model/driver initialization.
tree = ast.parse((ROOT / 'jewelry_agents/retrieval.py').read_text(encoding='utf-8-sig'))
namespace = {'re': re}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
                             and n.name in {'parse_money', 'extract_price_filter'}], type_ignores=[]), '<price-parser>', 'exec'), namespace)
parse_price = namespace['extract_price_filter']


def product(pid, price=7_000_000, stock=1, category=1):
    return {'ProductID': pid, 'ProductName': 'Nhẫn mẫu ' + str(pid), 'SKU': 'TEST' + str(pid),
            'Category': 'Nhẫn', 'CategoryID': category, 'Material': 'Bạc 925', 'Gemstone': 'CZ',
            'GemstoneID': 6, 'Collection': 'Minimal', 'Price': price, 'Stock': stock}


class SearchServiceTests(unittest.TestCase):
    def run_search(self, query, live=None, dense=None, graph=None):
        return search(query, 3, dense=dense or (lambda *a, **k: [{'ProductID': 3}, {'ProductID': 2}, {'ProductID': 1}]),
                      catalog=lambda: live if live is not None else {i: product(i) for i in range(1, 6)},
                      parse_price=parse_price, graph=graph)

    def test_requested_top1_overrides_api_default(self):
        result = self.run_search('Top 1 nhẫn dưới 8 triệu')
        self.assertEqual(len(result['products']), 1)
        self.assertEqual(result['requested_k'], 1)

    def test_all_hard_filters_use_live_data(self):
        live = {1: product(1, price=None), 2: product(2, stock=0), 3: product(3, price=8_000_000),
                4: product(4, category=2), 5: product(5)}
        result = self.run_search('Top 3 nhẫn dưới 8 triệu', live)
        self.assertEqual([p['ProductID'] for p in result['products']], [5])

    def test_dense_outage_falls_back_to_lexical_without_fake_semantic_score(self):
        def failed(*args, **kwargs):
            raise ConnectionError('synthetic')
        result = self.run_search('nhẫn dưới 8 triệu', dense=failed)
        self.assertEqual(result['status'], 'degraded')
        self.assertTrue(result['products'])
        self.assertTrue(all(p['retrieval_sources'] == ['lexical'] for p in result['products']))

    def test_business_outage_fails_closed(self):
        def failed():
            raise ConnectionError('synthetic')
        with self.assertRaises(RetrievalUnavailable):
            search('nhẫn', 3, dense=lambda *a, **k: [], catalog=failed, parse_price=parse_price)

    def test_children_and_missing_audience_facts_not_invented(self):
        self.assertEqual(self.run_search('nhẫn cho con gái 8 tuổi')['status'], 'clarification_required')
        self.assertEqual(self.run_search('nhẫn cho phái nữ')['status'], 'missing_verified_attributes')

    def test_graph_evidence_is_propagated_and_not_fabricated(self):
        paths = [{'relationship': 'BELONGS_TO', 'target_id': 1, 'target_name': 'Nhẫn'}]
        result = self.run_search('nhẫn', graph=lambda *a: [{'ProductID': 2, 'paths': paths}])
        item = next(p for p in result['products'] if p['ProductID'] == 2)
        self.assertEqual(item['graph_paths'], paths)
        self.assertIn('graph', item['retrieval_sources'])

    def test_unaccented_budget_and_decimal_budget(self):
        for query in ('nhan duoi 8 trieu', 'nhan duoi 8,5 trieu'):
            result = self.run_search(query, {1: product(1, price=9_000_000), 2: product(2)})
            self.assertEqual([p['ProductID'] for p in result['products']], [2])

    def test_dense_receives_live_eligible_ids_before_search(self):
        received = []
        def dense(query, top_k, eligible_ids):
            received.extend(eligible_ids)
            return [{'ProductID': 2}]
        self.run_search('nhẫn dưới 8 triệu', {1: product(1, price=9_000_000), 2: product(2)}, dense=dense)
        self.assertEqual(received, [2])

    def test_live_catalog_is_rechecked_after_ranking(self):
        states = iter([{1: product(1), 2: product(2)},
                       {1: product(1, price=9_000_000), 2: product(2)}])
        result = search('nhẫn dưới 8 triệu', 3, dense=lambda *a, **k: [{'ProductID': 1}, {'ProductID': 2}],
                        catalog=lambda: next(states), parse_price=parse_price)
        self.assertEqual([p['ProductID'] for p in result['products']], [2])

    def test_silver_constraint_does_not_match_platinum_prefix(self):
        live = {1: product(1), 2: {**product(2), 'Material': 'Bạch kim'}}
        result = self.run_search('Top 3 nhẫn bạc', live)
        self.assertEqual([p['ProductID'] for p in result['products']], [1])

    def test_reference_can_have_different_material_from_requested_candidates(self):
        live = {1: {**product(1), 'ProductName': 'Nhẫn mẫu gốc', 'Material': 'Vàng 18K', 'MaterialID': 1},
                2: {**product(2), 'MaterialID': 2}}
        result = self.run_search('Top 3 nhẫn bạc cùng loại đá với sản phẩm 1', live)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual([p['ProductID'] for p in result['products']], [2])

    def test_reference_material_in_its_name_is_not_a_candidate_constraint(self):
        live = {1: {**product(1), 'ProductName': 'Nhẫn Vàng 18K mẫu gốc', 'Material': 'Vàng 18K', 'MaterialID': 1},
                2: {**product(2), 'MaterialID': 2}}
        result = self.run_search('Top 3 cùng loại đá với Nhẫn Vàng 18K mẫu gốc', live)
        self.assertEqual([p['ProductID'] for p in result['products']], [2])

    def test_explicit_sku_beats_unrelated_dense_ranks(self):
        live = {1: {**product(1), 'SKU': 'SP000079'}, 2: product(2)}
        result = self.run_search('Top 1 SP000079', live, dense=lambda *a, **k: [{'ProductID': 2}])
        self.assertEqual([item['ProductID'] for item in result['products']], [1])

    def test_explicit_sku_does_not_bypass_stock_filter(self):
        live = {1: {**product(1, stock=0), 'SKU': 'SP000079'}, 2: product(2)}
        self.assertEqual(self.run_search('SP000079', live)['products'], [])

    def test_sku_changed_during_search_does_not_return_different_identity(self):
        first = {1: {**product(1), 'SKU': 'SP000079'}}
        latest = {1: {**product(1), 'SKU': 'RENAMED'}}
        states = iter([first, latest])
        result = search('SP000079', 1, dense=lambda *a, **k: [{'ProductID': 1}],
                        catalog=lambda: next(states), parse_price=parse_price)
        self.assertEqual(result['products'], [])

    def test_alphabetic_sku_does_not_capture_ordinary_category_word_without_marker(self):
        live = {1: {**product(1), 'SKU': 'NHAN'}, 2: product(2)}
        self.assertEqual({item['ProductID'] for item in self.run_search('Top 3 nhẫn', live)['products']}, {1, 2})
        self.assertEqual([item['ProductID'] for item in self.run_search('SKU NHAN', live)['products']], [1])

    def test_result_count_is_not_a_product_name_ranking_token(self):
        live = {pid: product(pid) for pid in (1, 2, 3, 4)}
        result = self.run_search('Top 3 nhẫn', live, dense=lambda *a, **k: [])
        self.assertEqual([item['ProductID'] for item in result['products']], [1, 2, 3])

    def test_numeric_sku_does_not_capture_requested_count_or_budget(self):
        live = {1: {**product(1), 'SKU': '3'}, 2: {**product(2), 'SKU': '8'}, 3: product(3)}
        result = self.run_search('Top 3 nhẫn dưới 8 triệu', live, dense=lambda *a, **k: [])
        self.assertEqual({item['ProductID'] for item in result['products']}, {1, 2, 3})


if __name__ == '__main__':
    unittest.main()
