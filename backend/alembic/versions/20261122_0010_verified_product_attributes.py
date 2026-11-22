"""Add human-reviewed product facts without modifying old product/customer/order rows."""
from alembic import op
import sqlalchemy as sa

revision='20261122_0010'
down_revision='20261121_0009'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('product_attribute_reviews',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('product_id',sa.Integer(),sa.ForeignKey('products.id',ondelete='CASCADE'),nullable=False),
        sa.Column('label',sa.String(16),nullable=False),
        sa.Column('canonical_id',sa.String(32),nullable=False),
        sa.Column('source_reference',sa.String(200),nullable=False),
        sa.Column('reviewed_by',sa.Integer(),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('reviewed_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('active',sa.Boolean(),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('review_log',sa.JSON(),nullable=False),
        sa.UniqueConstraint('product_id','label','canonical_id',name='uq_product_review_attribute'),
        sa.CheckConstraint("(label='Audience' AND canonical_id IN ('female','male','child_female')) OR "
                           "(label='Style' AND canonical_id IN ('elegant','minimalist','refined'))",name='ck_reviewed_attribute_canonical'),
        sa.CheckConstraint('version > 0',name='ck_attribute_review_version'),
        sa.CheckConstraint('length(trim(source_reference)) > 0',name='ck_attribute_review_source'))
    op.create_index('ix_product_attribute_reviews_product_id','product_attribute_reviews',['product_id'])


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError('Review rollback requires checking existing evidence rows first')
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM product_attribute_reviews')):
        raise RuntimeError('Preserve human review evidence; export/checkpoint before a reviewed rollback')
    op.drop_table('product_attribute_reviews')
