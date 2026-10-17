"""Create orders and immutable product snapshots.

Revision ID: 20261016_0003
Revises: 20261016_0002
"""

from alembic import op
import sqlalchemy as sa

revision = "20261016_0003"
down_revision = "20261016_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipient_name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(10), nullable=False),
        sa.Column("address", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payment_status", sa.String(20), nullable=False),
        sa.Column("stock_restored", sa.Boolean(), nullable=False),
        sa.Column("subtotal_vnd", sa.Numeric(38, 2), nullable=False),
        sa.Column("shipping_vnd", sa.Numeric(38, 2), nullable=False),
        sa.Column("discount_vnd", sa.Numeric(38, 2), nullable=False),
        sa.Column("total_vnd", sa.Numeric(38, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code"),
        sa.CheckConstraint("status IN ('pending','confirmed','packing','shipping','delivered','cancelled')", name="ck_orders_status"),
        sa.CheckConstraint("payment_status IN ('unpaid','paid','refunded')", name="ck_orders_payment_status"),
        sa.CheckConstraint("subtotal_vnd >= 0 AND shipping_vnd >= 0 AND discount_vnd >= 0 AND discount_vnd <= subtotal_vnd", name="ck_orders_amounts"),
        sa.CheckConstraint("total_vnd = subtotal_vnd + shipping_vnd - discount_vnd", name="ck_orders_total"),
        sa.CheckConstraint("(status = 'cancelled' AND stock_restored) OR (status <> 'cancelled' AND NOT stock_restored)", name="ck_orders_stock_restored"),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sku", sa.String(50), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_vnd", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_total_vnd", sa.Numeric(38, 2), nullable=False),
        sa.UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product"),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity"),
        sa.CheckConstraint("unit_price_vnd >= 0 AND line_total_vnd = unit_price_vnd * quantity", name="ck_order_items_amounts"),
    )
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])


def downgrade():
    raise RuntimeError("Order downgrade is disabled to preserve order history and stock accounting.")
