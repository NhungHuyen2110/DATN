"""Explicit opt-in test against an EMPTY, isolated Neo4j; never deletes data."""
import hashlib
import json
import csv
import os
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from knowledge_graph.csv_validation import validate_csv, FIELDS
from knowledge_graph.graph_writer import import_projection, prepare_rows, write_batch, ProjectionConflict, OWNER


@unittest.skipUnless(os.getenv('LUMIERE_ALLOW_ISOLATED_GRAPH_TEST') == '1', 'Requires explicitly isolated empty Neo4j')
class GraphIntegrationTests(unittest.TestCase):
    def test_replay_and_changed_taxonomy(self):
        from neo4j import GraphDatabase
        uri = os.environ['LUMIERE_NEO4J_INTEGRATION_URI']
        if urlsplit(uri).hostname not in {'127.0.0.1', 'localhost', '::1'}:
            self.fail('Only an explicit loopback test database is permitted')
        file = ROOT / 'tests/fixtures/products_graph.csv'
        records = validate_csv(file, ROOT.parent / 'data')['records']
        sha = hashlib.sha256(file.read_bytes()).hexdigest()
        with GraphDatabase.driver(uri, auth=('neo4j', os.environ['LUMIERE_GRAPH_PASSWORD']),
                                  connection_timeout=5, max_transaction_retry_time=5) as driver:
            with driver.session(database='neo4j') as session:
                self.assertEqual(session.run('MATCH (n) RETURN count(n) AS count').single()['count'], 0,
                                 'Refusing to touch a nonempty graph; no cleanup performed')
            first = import_projection(driver, 'neo4j', records, file.name, sha, batch_size=2)
            second = import_projection(driver, 'neo4j', records, file.name, sha, batch_size=2)
            self.assertTrue(first['pass'])
            self.assertEqual(first, second)
            records[0]['CategoryID'], records[0]['CategoryName'] = 2, 'Dây chuyền'
            records[0]['ProductName'] = 'Đổi tên fixture'
            with tempfile.TemporaryDirectory() as directory:
                changed_file = Path(directory) / 'changed-fixture.csv'
                with changed_file.open('w', encoding='utf-8-sig', newline='') as handle:
                    writer = csv.DictWriter(handle, fieldnames=sorted(FIELDS))
                    writer.writeheader()
                    writer.writerows({key: row[key] for key in FIELDS} for row in records)
                changed_sha = hashlib.sha256(changed_file.read_bytes()).hexdigest()
                validated_changes = validate_csv(changed_file, ROOT.parent / 'data')
                self.assertFalse(validated_changes['errors'])
                changed = import_projection(driver, 'neo4j', validated_changes['records'], changed_file.name,
                                            changed_sha, batch_size=2)
            self.assertTrue(changed['pass'])
            self.assertEqual(changed['products'], 3)
            from knowledge_graph.graph_recommendation import GraphRecommender
            recommender = GraphRecommender(uri, 'neo4j', os.environ['LUMIERE_GRAPH_PASSWORD'])
            try:
                recommendations = recommender.recommend(900001, limit=3)
            finally:
                recommender.close()
            self.assertEqual([item['ProductID'] for item in recommendations], [900002])
            self.assertTrue(recommendations[0]['paths'])
            self.assertTrue(all(path['source_product_id'] == 900001 for path in recommendations[0]['paths']))
            # Force an owned-fixture batch to fail after Product SET, then prove rollback.
            with driver.session(database='neo4j') as session:
                session.run("MATCH (p:Product {product_id:900002})-[r:HAS_BRAND]->() SET r.projection_owner='test-conflict'").consume()
                modified = dict(records[1], ProductName='MUST_ROLL_BACK')
                with self.assertRaises(ProjectionConflict):
                    session.execute_write(write_batch, prepare_rows([modified], file.name, sha))
                actual = session.run('MATCH (p:Product {product_id:900002}) RETURN p.name AS name').single()['name']
                self.assertEqual(actual, records[1]['ProductName'])
                session.run('MATCH (p:Product {product_id:900002})-[r:HAS_BRAND]->() SET r.projection_owner=$owner', owner=OWNER).consume()
            if os.getenv('LUMIERE_GRAPH_TEST_REPORT'):
                report = {'first_import': first, 'second_import': second, 'changed_taxonomy': changed,
                          'idempotency_pass': first == second, 'batch_rollback_pass': True,
                          'recommendation_ids': [item['ProductID'] for item in recommendations],
                          'recommendation_paths_verified': True, 'data_kind': 'synthetic_fixture_only'}
                with Path(os.environ['LUMIERE_GRAPH_TEST_REPORT']).open('x', encoding='utf-8') as handle:
                    json.dump(report, handle, indent=2)
                    handle.write('\n')
            # Graph deliberately remains for inspection. No DELETE-all or volume removal.


if __name__ == '__main__':
    unittest.main()
