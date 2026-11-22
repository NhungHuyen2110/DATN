"""Add optional product projection outbox; never modify existing business rows."""
from alembic import op
import sqlalchemy as sa

revision = '20261118_0008'
down_revision = '20261106_0007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('product_index_jobs',
        sa.Column('product_id', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('generation', sa.BigInteger(), nullable=False),
        sa.Column('delivered_generation', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(12), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('dirty_since', sa.DateTime(timezone=True)),
        sa.Column('lease_until', sa.DateTime(timezone=True)),
        sa.Column('lease_token', sa.String(32)),
        sa.Column('last_error_type', sa.String(100)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint('product_id > 0 AND generation > 0 AND delivered_generation >= 0 AND delivered_generation <= generation', name='ck_index_job_generation'),
        sa.CheckConstraint("status IN ('pending','processing','done','dead') AND attempts >= 0", name='ck_index_job_status'),
        sa.CheckConstraint("(status = 'processing' AND lease_token IS NOT NULL AND lease_until IS NOT NULL) OR (status <> 'processing' AND lease_token IS NULL AND lease_until IS NULL)", name='ck_index_job_lease'))
    op.create_index('ix_product_index_jobs_next_attempt_at', 'product_index_jobs', ['next_attempt_at'])
    op.create_index('ix_product_index_jobs_lease_until', 'product_index_jobs', ['lease_until'])


def downgrade():
    raise RuntimeError('Outbox downgrade disabled: preserve pending delivery/recovery records; disable feature flag instead')
