from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from .order_item import OrderItem
    from .user import User


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("status IN ('pending','confirmed','packing','shipping','delivered','cancelled')", name="ck_orders_status"),
        CheckConstraint("payment_status IN ('unpaid','paid','refunded')", name="ck_orders_payment_status"),
        CheckConstraint("payment_method IN ('cod','vnpay')", name="ck_orders_payment_method"),
        CheckConstraint("subtotal_vnd >= 0 AND shipping_vnd >= 0 AND discount_vnd >= 0 AND discount_vnd <= subtotal_vnd", name="ck_orders_amounts"),
        CheckConstraint("total_vnd = subtotal_vnd + shipping_vnd - discount_vnd", name="ck_orders_total"),
        CheckConstraint("(status = 'cancelled' AND stock_restored) OR (status <> 'cancelled' AND NOT stock_restored)", name="ck_orders_stock_restored"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    recipient_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(10), nullable=False)
    address: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), server_default="cod", nullable=False)
    stock_restored: Mapped[bool] = mapped_column(Boolean, nullable=False)
    subtotal_vnd: Mapped[Decimal] = mapped_column(Numeric(38, 2), nullable=False)
    shipping_vnd: Mapped[Decimal] = mapped_column(Numeric(38, 2), nullable=False)
    discount_vnd: Mapped[Decimal] = mapped_column(Numeric(38, 2), nullable=False)
    total_vnd: Mapped[Decimal] = mapped_column(Numeric(38, 2), nullable=False)
    coupon_id: Mapped[int | None] = mapped_column(ForeignKey("coupons.id", ondelete="RESTRICT"), nullable=True)
    coupon_code: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User")
    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order", order_by="OrderItem.id")
