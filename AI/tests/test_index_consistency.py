"""Projection drift contracts using catalog fixtures, with no model or live I/O."""
import unittest
from copy import deepcopy

from knowledge_graph.csv_validation import validate_csv, ROOT, LOOKUPS
from knowledge_graph.graph_writer import prepare_rows, OWNER
from vector_index import product_payload, index_identity
from shared.product_index_contract import compare_indexes


class IndexConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.rows = validate_csv(ROOT/'AI/tests/fixtures/products_graph.csv', ROOT/'data')['records']
        self.fingerprint = index_identity('fixture', 'revision', 384)[1]
        self.graph = [{'properties': {**p['properties'], 'product_id': p['ProductID']}}
                      for p in prepare_rows(self.rows, 'fixture', 'sha')]
        self.edges = [{'product_id': row['ProductID'], 'type': relation, 'labels': [label],
                       'properties': {'projection_owner': OWNER},
                       'target': {label.lower() + '_id': row[label+'ID'], 'name': row[label+'Name']}}
                      for row in self.rows for label, (_, relation) in LOOKUPS.items()]
        self.vector = [{'id': row['ProductID'], 'payload': product_payload(row, self.fingerprint, 'fixture', 'revision', 'sha'),
                        'vector_dimension': 384, 'finite_nonzero': True} for row in self.rows]

    def compare(self):
        return compare_indexes(self.rows, self.graph, self.edges, self.vector, self.fingerprint)

    def test_exact_contract_ignores_price_stock_brand_not_stored_in_vector_payload(self):
        self.assertNotIn('Stock', self.vector[0]['payload'])
        self.assertNotIn('Price', self.vector[0]['payload'])
        self.assertNotIn('Brand', self.vector[0]['payload'])
        self.assertTrue(self.compare()['pass'])

    def test_missing_zero_stock_product_remains_index_eligible(self):
        row = deepcopy(self.rows[0])
        row.update(ProductID=501, SKU='new-501', ProductName='aaaa', Stock=0)
        self.rows.append(row)
        result = self.compare()
        self.assertEqual(result['affected_product_ids'], [501])
        self.assertEqual({i['store'] for i in result['issues']}, {'graph', 'vector'})

    def test_attribute_drift_and_duplicate_taxonomy_edges_are_detected(self):
        self.graph[0]['properties']['stock'] += 1
        self.edges.append(deepcopy(self.edges[0]))
        self.vector[0]['payload']['SKU'] = 'stale'
        result = self.compare()
        self.assertFalse(result['pass'])
        self.assertTrue({'stock', 'BELONGS_TO', 'SKU'} <= {i['field'] for i in result['issues']})

    def test_duplicate_nodes_and_foreign_embedding_revision_block_acceptance(self):
        self.graph.append(deepcopy(self.graph[0]))
        self.vector[0]['payload']['embedding_revision'] = 'foreign'
        result = self.compare()
        self.assertTrue({'duplicate_identity', 'embedding_identity'} <= {i['field'] for i in result['issues']})

    def test_absent_product_tombstone_is_retained_but_extra_vector_is_drift(self):
        pid = self.rows.pop()['ProductID']
        self.graph[-1]['properties']['is_deleted'] = True
        result = self.compare()
        self.assertEqual(result['affected_product_ids'], [pid])
        self.assertEqual([(i['store'], i['field']) for i in result['issues']], [('vector', 'extra_active')])
