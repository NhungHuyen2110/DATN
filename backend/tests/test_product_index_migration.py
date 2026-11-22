"""Validate additive DDL without connecting to PostgreSQL or applying real migrations."""
import io
from pathlib import Path
import unittest

import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from app.models import ProductIndexJob


class ProductIndexMigrationTests(unittest.TestCase):
    def test_additive_postgres_sql_and_sqlite_model_agreement(self):
        backend = Path(__file__).resolve().parents[1]
        scripts = ScriptDirectory.from_config(Config(str(backend / 'alembic.ini')))
        revision = scripts.get_revision('20261118_0008').module
        self.assertEqual(revision.down_revision, '20261106_0007')
        output = io.StringIO()
        context = MigrationContext.configure(dialect_name='postgresql', opts={'as_sql': True, 'output_buffer': output})
        with Operations.context(context):
            revision.upgrade()
        sql = output.getvalue().upper()
        self.assertIn('CREATE TABLE PRODUCT_INDEX_JOBS', sql)
        for forbidden in ('DROP ', 'DELETE FROM ', 'UPDATE ', 'ALTER TABLE ', 'INSERT INTO '):
            self.assertNotIn(forbidden, sql)
        engine = sa.create_engine('sqlite:///:memory:')
        try:
            with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
                revision.upgrade()
            inspector = sa.inspect(engine)
            self.assertEqual({col['name'] for col in inspector.get_columns('product_index_jobs')},
                             set(ProductIndexJob.__table__.c.keys()))
            self.assertEqual(inspector.get_foreign_keys('product_index_jobs'), [])
            self.assertEqual({item['name'] for item in inspector.get_check_constraints('product_index_jobs')},
                             {item.name for item in ProductIndexJob.__table__.constraints if isinstance(item, sa.CheckConstraint)})
        finally:
            engine.dispose()
