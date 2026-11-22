"""Make the existing password-reset feature reproducible without replacing old token rows."""
from alembic import op
import sqlalchemy as sa

revision = '20261121_0009'
down_revision = '20261118_0008'
branch_labels = None
depends_on = None


def validate_existing(inspector):
    columns = {item['name']: item for item in inspector.get_columns('password_reset_tokens')}
    expected = {'id': sa.Integer, 'user_id': sa.Integer, 'token_hash': sa.String,
                'expires_at': sa.DateTime, 'used_at': sa.DateTime}
    if set(columns) != set(expected) or any(not isinstance(columns[key]['type'], kind) for key, kind in expected.items()):
        raise RuntimeError('Existing reset token schema needs review; refusing replacement')
    if columns['token_hash']['type'].length != 64 or any(columns[key]['nullable'] for key in ('id', 'user_id', 'token_hash', 'expires_at')):
        raise RuntimeError('Existing reset token identity constraints differ')
    if not columns['used_at']['nullable']:
        raise RuntimeError('Reset used_at must allow unused records')
    if inspector.get_pk_constraint('password_reset_tokens')['constrained_columns'] != ['id']:
        raise RuntimeError('Existing reset token primary key differs')
    unique = [item['column_names'] for item in inspector.get_unique_constraints('password_reset_tokens')]
    unique += [item['column_names'] for item in inspector.get_indexes('password_reset_tokens') if item['unique']]
    if ['token_hash'] not in unique:
        raise RuntimeError('Existing reset token hashes are not unique')
    foreign = inspector.get_foreign_keys('password_reset_tokens')
    if not any(item['constrained_columns'] == ['user_id'] and item['referred_table'] == 'users'
               and item['referred_columns'] == ['id'] and item.get('options', {}).get('ondelete', '').upper() == 'CASCADE'
               for item in foreign):
        raise RuntimeError('Existing reset ownership FK needs review')


def upgrade():
    if not op.get_context().as_sql:
        inspector = sa.inspect(op.get_bind())
        if 'password_reset_tokens' in inspector.get_table_names():
            validate_existing(inspector)
            return  # Preserve manually initialized tables and all outstanding tokens.
    op.create_table('password_reset_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True)))
    op.create_index('ix_password_reset_tokens_user_id', 'password_reset_tokens', ['user_id'])
    op.create_index('ix_password_reset_tokens_token_hash', 'password_reset_tokens', ['token_hash'], unique=True)


def downgrade():
    raise RuntimeError('Preserve password-reset security records; no automatic destructive downgrade')
