from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jewelry_agents.business_catalog import fetch_catalog, CatalogUnavailable


class BusinessCatalogTests(unittest.TestCase):
    def test_runtime_catalog_deadline_never_returns_partial_data(self):
        with patch.dict('os.environ',{'LUMIERE_RETRIEVAL_LIMITS_ENABLED':'true'}), \
             patch('jewelry_agents.business_catalog._catalog_gate.call',side_effect=TimeoutError) as gate:
            with self.assertRaises(CatalogUnavailable):fetch_catalog()
        self.assertEqual(gate.call_count,1)
    def test_maps_only_authoritative_public_fields(self):
        item = {'id': 1, 'name': 'Live product', 'sku': 'TEST1', 'price_vnd': '123.45', 'stock': 2,
                'category': {'id': 1, 'name': 'Nhẫn'}, 'brand': {'id': 1, 'name': 'Brand'},
                'material': {'id': 1, 'name': 'Bạc 925'}, 'gemstone': {'id': 6, 'name': 'CZ'},
                'collection': {'id': 4, 'name': 'Minimal'}}
        client = MagicMock()
        client.get.return_value.json.return_value = {'items': [item], 'total': 1}
        with patch('jewelry_agents.business_catalog.requests.Session') as factory:
            factory.return_value.__enter__.return_value = client
            result = fetch_catalog()
        self.assertEqual(result[1]['Price'], '123.45')
        self.assertEqual(result[1]['verified_source'], 'business_api')
        self.assertEqual(client.get.call_args.kwargs['timeout'], 3)

    def test_failed_page_does_not_return_partial_or_stale_catalog(self):
        client = MagicMock()
        client.get.return_value.json.return_value = {'items': [], 'total': 500}
        with patch('jewelry_agents.business_catalog.requests.Session') as factory:
            factory.return_value.__enter__.return_value = client
            with self.assertRaises(CatalogUnavailable):
                fetch_catalog()


if __name__ == '__main__':
    unittest.main()
