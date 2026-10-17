"""Add session-owned carts; no changes to account or product data.

Revision ID: 20261016_0002
Revises: 20261015_0001
"""

from alembic import op
import sqlalchemy as sa

revision = "20261016_0002"
down_revision = "20261015_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "carts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "cart_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cart_id", sa.Integer(), sa.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.UniqueConstraint("cart_id", "product_id", name="uq_cart_items_cart_product"),
        sa.CheckConstraint("quantity > 0", name="ck_cart_items_quantity_positive"),
    )
    op.create_index("ix_cart_items_product_id", "cart_items", ["product_id"])


def downgrade():
    raise RuntimeError("Cart downgrade is disabled to prevent deleting customer cart data.")
