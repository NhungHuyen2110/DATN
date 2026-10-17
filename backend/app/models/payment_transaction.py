from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        UniqueConstraint("order_id", "provider", name="uq_payment_order_provider"),
        UniqueConstraint("provider", "provider_transaction_id", name="uq_payment_provider_transaction"),
        CheckConstraint("status IN ('pending','succeeded','failed')", name="ck_payment_status"),
        CheckConstraint("amount_vnd > 0", name="ck_payment_amount"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    reference: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    amount_vnd: Mapped[Decimal] = mapped_column(Numeric(38, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    response_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    provider_status: Mapped[str | None] = mapped_column(String(2), nullable=True)
    callback_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    merchant_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    return_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
