from pathlib import Path
from unittest.mock import MagicMock
import unittest
from knowledge_graph.graph_writer import ensure_constraints, LOOKUPS, ProjectionConflict


class GraphConstraintsReplayTests(unittest.TestCase):
    def statements(self):
        from knowledge_graph import graph_writer
        source = Path(graph_writer.__file__).with_name('schema.cypher').read_text(encoding='utf-8-sig')
        return '\n'.join(line for line in source.splitlines() if not line.strip().startswith('//'))

    def constraints(self):
        return [{'name': 'lumiere_' + label.lower() + '_id', 'type': 'UNIQUENESS',
                 'labelsOrTypes': [label], 'properties': [label.lower() + '_id']}
                for label in ['Product', *LOOKUPS]] + [
                    {'name': 'lumiere_review_' + label.lower() + '_canonical_id', 'type': 'UNIQUENESS',
                     'labelsOrTypes': [label], 'properties': ['canonical_id']} for label in ['Audience', 'Style']]

    def test_replay_checks_existing_schema_without_six_ddl_transactions(self):
        session = MagicMock()
        session.run.return_value = self.constraints()
        ensure_constraints(session, self.statements())
        self.assertEqual(session.run.call_count, 1)

    def test_only_missing_constraint_is_created(self):
        session = MagicMock()
        session.run.side_effect = [self.constraints()[1:], MagicMock()]
        ensure_constraints(session, self.statements())
        self.assertEqual(session.run.call_count, 2)
        self.assertIn('lumiere_product_id', session.run.call_args.args[0])

    def test_wrong_uniqueness_schema_is_rejected_before_any_writes(self):
        session = MagicMock()
        rows = self.constraints()
        rows[-1]['properties'] = ['wrong_id']
        session.run.return_value = rows[1:]
        with self.assertRaises(ProjectionConflict):
            ensure_constraints(session, self.statements())
        self.assertEqual(session.run.call_count, 1)

    def test_incremental_mode_requires_existing_constraints_and_never_emits_ddl(self):
        session = MagicMock()
        session.run.return_value = self.constraints()[1:]
        with self.assertRaisesRegex(ProjectionConflict, 'schema approval'):
            ensure_constraints(session, self.statements(), allow_create=False)
        self.assertEqual(session.run.call_count, 1)
