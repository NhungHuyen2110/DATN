from datetime import datetime, timedelta, timezone
import io
from pathlib import Path
import unittest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
import sqlalchemy as sa
from app.core.database import Base
from app.models import Role, User
from app.routers.password_reset import PasswordResetToken


class PasswordResetMigrationTests(unittest.TestCase):
    def revision(self):
        backend = Path(__file__).resolve().parents[1]
        return ScriptDirectory.from_config(Config(str(backend / 'alembic.ini'))).get_revision('20261121_0009').module

    def test_offline_sql_is_additive_and_existing_rows_are_preserved(self):
        revision = self.revision()
        output = io.StringIO()
        with Operations.context(MigrationContext.configure(dialect_name='postgresql', opts={'as_sql': True, 'output_buffer': output})):
            revision.upgrade()
        self.assertIn('CREATE TABLE password_reset_tokens', output.getvalue())
        for forbidden in ('DROP ', 'DELETE FROM ', 'UPDATE ', 'ALTER TABLE users'):
            self.assertNotIn(forbidden, output.getvalue())
        engine = sa.create_engine('sqlite:///:memory:')
        try:
            Base.metadata.create_all(engine, tables=[Role.__table__, User.__table__])
            with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
                revision.upgrade()
                connection.execute(Role.__table__.insert().values(id=1, name='customer'))
                connection.execute(User.__table__.insert().values(id=1, role_id=1, full_name='Synthetic',
                    email='synthetic@example.com', password_hash='synthetic', is_active=True))
                connection.execute(PasswordResetToken.__table__.insert().values(id=1, user_id=1, token_hash='a' * 64,
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)))
                revision.upgrade()
                self.assertEqual(connection.scalar(sa.select(sa.func.count()).select_from(PasswordResetToken)), 1)
        finally:
            engine.dispose()

    def test_incompatible_existing_table_is_rejected_without_replacement(self):
        engine = sa.create_engine('sqlite:///:memory:')
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql('CREATE TABLE password_reset_tokens (id INTEGER PRIMARY KEY, secret TEXT)')
                with Operations.context(MigrationContext.configure(connection)), self.assertRaises(RuntimeError):
                    self.revision().upgrade()
                self.assertIn('secret', {col['name'] for col in sa.inspect(connection).get_columns('password_reset_tokens')})
        finally:
            engine.dispose()
