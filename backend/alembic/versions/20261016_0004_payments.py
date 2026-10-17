"""Payment method and provider transaction ledger; no gateway requests.

Revision ID: 20261016_0004
Revises: 20261016_0003
"""

from alembic import op
import sqlalchemy as sa

revision = "20261016_0004"
down_revision = "20261016_0003"
branch_labels = None
depends_on = None


def upgrade():
    # Legacy orders are treated as COD. Review this assumption before applying.
    op.add_column("orders", sa.Column("payment_method", sa.String(20), server_default="cod", nullable=False))
    op.create_check_constraint("ck_orders_payment_method", "orders", "payment_method IN ('cod','vnpay')")
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("amount_vnd", sa.Numeric(38, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("provider_transaction_id", sa.String(100), nullable=True),
        sa.Column("response_code", sa.String(2), nullable=True),
        sa.Column("provider_status", sa.String(2), nullable=True),
        sa.Column("callback_digest", sa.String(64), nullable=True),
        sa.Column("merchant_code", sa.String(8), nullable=True),
        sa.Column("return_url", sa.String(255), nullable=True),
        sa.Column("client_ip", sa.String(45), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("reference"),
        sa.UniqueConstraint("order_id", "provider", name="uq_payment_order_provider"),
        sa.UniqueConstraint("provider", "provider_transaction_id", name="uq_payment_provider_transaction"),
        sa.CheckConstraint("status IN ('pending','succeeded','failed')", name="ck_payment_status"),
        sa.CheckConstraint("amount_vnd > 0", name="ck_payment_amount"),
    )


def downgrade():
    raise RuntimeError("Payment downgrade disabled to preserve financial transaction history.")
