from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jewelry_agents.business_catalog import fetch_catalog, CatalogUnavailable


class BusinessCatalogTests(unittest.TestCase):
    def test_pages_overlap_with_two_reader_limit_and_no_partial_catalog(self):
        from jewelry_agents.business_catalog import _fetch_catalog
        active=peak=0
        lock=threading.Lock()
        calls=[]
        item={'name':'Public','sku':'SKU','price_vnd':'100','stock':2,
              **{name:{'id':1,'name':'Value'} for name in ('category','brand','material','gemstone','collection')}}
        def get(url,params,**kwargs):
            nonlocal active,peak
            number=params['page']
            with lock:active+=1;peak=max(peak,active);calls.append(number)
            try:
                if number>1:time.sleep(.03)
                response=MagicMock()
                response.json.return_value={'total':500,'items':[{**item,'id':i} for i in range((number-1)*100+1,number*100+1)]}
                return response
            finally:
                with lock:active-=1
        client=MagicMock();client.get.side_effect=get
        with patch('jewelry_agents.business_catalog.requests.Session') as factory:
            factory.return_value.__enter__.return_value=client
            result=_fetch_catalog()
        self.assertEqual(set(result),set(range(1,501)))
        self.assertEqual(sorted(calls),[1,2,3,4,5])
        self.assertEqual(peak,2)

    def test_changed_total_and_duplicate_ids_are_rejected(self):
        from jewelry_agents.business_catalog import _fetch_catalog
        item={'name':'Public','sku':'SKU','price_vnd':'100','stock':2,
              **{name:{'id':1,'name':'Value'} for name in ('category','brand','material','gemstone','collection')}}
        for duplicate in (True,False):
            def get(url,params,**kwargs):
                number=params['page']
                total=200 if duplicate or number==1 else 201
                response=MagicMock()
                response.json.return_value={'total':total,'items':[{**item,'id':i+(0 if duplicate or number==1 else 100)} for i in range(1,101)]}
                return response
            client=MagicMock();client.get.side_effect=get
            with self.subTest(duplicate=duplicate),patch('jewelry_agents.business_catalog.requests.Session') as factory:
                factory.return_value.__enter__.return_value=client
                with self.assertRaises(CatalogUnavailable):_fetch_catalog()

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
