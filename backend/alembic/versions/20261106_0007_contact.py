"""Persist contact form inquiries.

Revision ID: 20261106_0007
Revises: 20261023_0006
"""

from alembic import op
import sqlalchemy as sa

revision = "20261106_0007"
down_revision = "20261023_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("message", sa.String(1500), nullable=False),
        sa.Column("status", sa.String(20), server_default="new", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('new','in_progress','closed')", name="ck_contact_status"),
        sa.CheckConstraint("length(trim(message)) BETWEEN 10 AND 1500", name="ck_contact_message_length"),
    )


def downgrade():
    raise RuntimeError("Contact messages downgrade disabled to preserve inquiries.")
