"""Coupons and reversible per-customer usage; preserve all existing orders.

Revision ID: 20261023_0006
Revises: 20261017_0005
"""

from alembic import op
import sqlalchemy as sa

revision = "20261023_0006"
down_revision = "20261017_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "coupons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(24), unique=True, nullable=False),
        sa.Column("discount_type", sa.String(10), nullable=False),
        sa.Column("discount_value", sa.Numeric(38, 2), nullable=False),
        sa.Column("max_discount_vnd", sa.Numeric(38, 2), nullable=True),
        sa.Column("min_order_vnd", sa.Numeric(38, 2), nullable=False),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("code = upper(trim(code)) AND length(code) BETWEEN 3 AND 24", name="ck_coupons_code"),
        sa.CheckConstraint("discount_type IN ('fixed','percent')", name="ck_coupons_type"),
        sa.CheckConstraint("discount_value > 0 AND (discount_type <> 'percent' OR discount_value <= 100)", name="ck_coupons_value"),
        sa.CheckConstraint("min_order_vnd >= 0 AND (max_discount_vnd IS NULL OR max_discount_vnd > 0)", name="ck_coupons_amounts"),
        sa.CheckConstraint("used_count >= 0 AND (usage_limit IS NULL OR (usage_limit > 0 AND used_count <= usage_limit))", name="ck_coupons_usage"),
        sa.CheckConstraint("starts_at < ends_at", name="ck_coupons_dates"),
    )
    op.add_column("orders", sa.Column("coupon_id", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("coupon_code", sa.String(24), nullable=True))
    # batch mode also allows the migration's compatibility test on SQLite memory.
    with op.batch_alter_table("orders") as batch:
        batch.create_foreign_key("fk_orders_coupon_id", "coupons", ["coupon_id"], ["id"], ondelete="RESTRICT")
    op.create_table(
        "coupon_usages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("coupon_id", sa.Integer(), sa.ForeignKey("coupons.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="RESTRICT"), unique=True, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active','returned')", name="ck_coupon_usages_status"),
        sa.CheckConstraint("(status = 'active' AND returned_at IS NULL) OR (status = 'returned' AND returned_at IS NOT NULL)", name="ck_coupon_usages_return"),
    )
    op.create_index("uq_coupon_usages_active_customer", "coupon_usages", ["coupon_id", "user_id"], unique=True,
                    postgresql_where=sa.text("status = 'active'"), sqlite_where=sa.text("status = 'active'"))


def downgrade():
    raise RuntimeError("Downgrade disabled to preserve coupon and order history.")
