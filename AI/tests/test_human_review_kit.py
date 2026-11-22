import csv
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.prepare_human_review_kit import FIELDS, write_review_kit, load_original_public_catalog


class HumanReviewKitTests(unittest.TestCase):
    def test_only_public_fields_export_and_no_labels_are_fabricated(self):
        product = dict.fromkeys(FIELDS, 'Synthetic public value')
        product.update(ProductID=1, ProductName='=spreadsheet-formula', CostPrice='private-cost-canary',
                       customer_email='private-customer-canary')
        questions = [{'query_id': 'Q1', 'query': '=untrusted-query', 'group': 'test', 'reviewed': False}]
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'review'
            report = write_review_kit(folder, [product], questions, 'synthetic-hash', 'synthetic fixture')
            snapshot = (folder / 'catalog-public-snapshot.json').read_text(encoding='utf-8')
            self.assertNotIn('private-cost-canary', snapshot)
            self.assertNotIn('private-customer-canary', snapshot)
            with (folder / 'catalog-for-human-review.csv').open(encoding='utf-8-sig', newline='') as stream:
                row = list(csv.DictReader(stream))[0]
            self.assertEqual(row['ProductName'], "'=spreadsheet-formula")
            for field in ('audience_proposal', 'style_proposal', 'evidence_source', 'reviewer', 'reviewed_at'):
                self.assertEqual(row[field], '')
            self.assertEqual(row['approved'], 'false')
            self.assertEqual(report['human_reviewed_products'], 0)
            self.assertEqual(report['human_reviewed_queries'], 0)
            self.assertFalse(report['database_writes'])
            self.assertEqual(json.loads(snapshot)[0]['ProductID'], 1)

    def test_existing_human_work_and_reviewed_queries_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'review'
            folder.mkdir()
            marker = folder / 'human-work.csv'
            marker.write_text('human work', encoding='utf-8')
            with self.assertRaises(ValueError):
                write_review_kit(folder, [], [], 'sha', 'fixture')
            self.assertEqual(marker.read_text(), 'human work')
            target = Path(temporary) / 'other'
            with self.assertRaises(ValueError):
                write_review_kit(target, [dict.fromkeys(FIELDS, '1')], [{'reviewed': True}], 'sha', 'fixture')
            self.assertFalse(target.exists())

    def test_original_adapter_forces_local_endpoint_and_restores_process_configuration(self):
        item = {'ProductID': 1, 'SKU': 'TEST', 'ProductName': 'Synthetic ring', 'CategoryID': 1,
                'Category': 'Ring', 'Brand': 'Brand', 'MaterialID': 1, 'Material': 'Silver',
                'GemstoneID': 1, 'Gemstone': 'CZ', 'Collection': 'Fixture', 'Price': '100', 'Stock': 1}
        def fetch():
            self.assertEqual(os.environ['BUSINESS_API_URL'], 'http://127.0.0.1:18080/api')
            return {1: item}
        with patch.dict(os.environ, {'BUSINESS_API_URL': 'synthetic-original-config'}), \
                patch('jewelry_agents.business_catalog.fetch_catalog', side_effect=fetch):
            rows = load_original_public_catalog()
            self.assertEqual(os.environ['BUSINESS_API_URL'], 'synthetic-original-config')
        self.assertEqual(rows[0]['SalePrice'], '100')
        self.assertEqual(set(rows[0]), set(FIELDS))
