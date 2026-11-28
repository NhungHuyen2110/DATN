from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from knowledge_graph.csv_validation import validate_csv, ROOT
from knowledge_graph.graph_writer import import_projection, prepare_rows, write_batch, ProjectionConflict
from knowledge_graph.graph_writer import verify_projection, LOOKUPS
from knowledge_graph.graph_writer import mark_deleted


class GraphWriterTests(unittest.TestCase):
    def setUp(self):
        self.records = validate_csv(ROOT / 'output/products_ai.csv', ROOT / 'data', limit=2)['records']

    def test_lineage_exact_price_and_no_cost_in_public_projection(self):
        rows = prepare_rows(self.records, 'synthetic.csv', 'abc')
        properties = rows[0]['properties']
        self.assertEqual(properties['source_sha256'], 'abc')
        self.assertEqual(properties['source_row'], 2)
        self.assertNotIn('cost_price', properties)
        self.assertIn('sale_price_decimal', properties)

    def test_unmanaged_products_block_transaction(self):
        tx = MagicMock()
        tx.run.return_value.single.return_value = {'conflicts': 1}
        with self.assertRaises(ProjectionConflict):
            write_batch(tx, prepare_rows(self.records, 'synthetic.csv', 'abc'))
        self.assertEqual(tx.run.call_count, 1)

    def test_data_values_are_never_interpolated_into_cypher(self):
        self.records[0]['ProductName'] = "x') DETACH DELETE n //"
        tx = MagicMock()
        tx.run.return_value.single.return_value = {'conflicts': 0}
        write_batch(tx, prepare_rows(self.records, 'synthetic.csv', 'abc'))
        for call in tx.run.call_args_list:
            self.assertNotIn('DETACH DELETE', call.args[0])
            self.assertIn('rows', call.kwargs)

    def test_no_write_before_entire_projection_can_be_represented(self):
        self.records[1]['SalePrice'] = '9999999999999999.99'
        driver = MagicMock()
        with self.assertRaises(ValueError):
            import_projection(driver, 'neo4j', self.records, 'synthetic.csv', 'abc')
        driver.session.assert_not_called()

    def test_wrong_product_properties_fail_even_when_ids_and_relationships_match(self):
        session = MagicMock()
        results = [{'count': 2, 'distinct_count': 2, 'unmanaged': 0}, {'violations': 1}]
        results += [{'count': 2, 'violations': 0} for _ in LOOKUPS]
        session.run.return_value.single.side_effect = results
        report = verify_projection(session, prepare_rows(self.records, 'fixture', 'sha'))
        self.assertEqual(report['property_violations'], 1)
        self.assertFalse(report['pass'])

    def test_tombstone_requires_readback_before_transaction_success(self):
        driver = MagicMock()
        tx = MagicMock()
        tx.run.return_value.single.side_effect = [{'count': 0}, {'violations': 1}]
        session = driver.session.return_value.__enter__.return_value
        session.execute_write.side_effect = lambda callback: callback(tx)
        with self.assertRaisesRegex(ProjectionConflict, 'Tombstone verification failed'):
            mark_deleted(driver, 'neo4j', 1)


if __name__ == '__main__':
    unittest.main()
