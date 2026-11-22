from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from knowledge_graph.csv_validation import validate_csv, ROOT
from knowledge_graph.graph_writer import import_projection, prepare_rows, write_batch, ProjectionConflict


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


if __name__ == '__main__':
    unittest.main()
