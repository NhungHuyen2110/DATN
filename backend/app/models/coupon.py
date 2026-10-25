from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Coupon(Base):
    __tablename__ = "coupons"
    __table_args__ = (
        CheckConstraint("code = upper(trim(code)) AND length(code) BETWEEN 3 AND 24", name="ck_coupons_code"),
        CheckConstraint("discount_type IN ('fixed','percent')", name="ck_coupons_type"),
        CheckConstraint("discount_value > 0 AND (discount_type <> 'percent' OR discount_value <= 100)", name="ck_coupons_value"),
        CheckConstraint("min_order_vnd >= 0 AND (max_discount_vnd IS NULL OR max_discount_vnd > 0)", name="ck_coupons_amounts"),
        CheckConstraint("used_count >= 0 AND (usage_limit IS NULL OR (usage_limit > 0 AND used_count <= usage_limit))", name="ck_coupons_usage"),
        CheckConstraint("starts_at < ends_at", name="ck_coupons_dates"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    discount_type: Mapped[str] = mapped_column(String(10), nullable=False)
    discount_value: Mapped[Decimal] = mapped_column(Numeric(38, 2), nullable=False)
    max_discount_vnd: Mapped[Decimal | None] = mapped_column(Numeric(38, 2))
    min_order_vnd: Mapped[Decimal] = mapped_column(Numeric(38, 2), nullable=False)
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CouponUsage(Base):
    __tablename__ = "coupon_usages"
    __table_args__ = (
        CheckConstraint("status IN ('active','returned')", name="ck_coupon_usages_status"),
        CheckConstraint("(status = 'active' AND returned_at IS NULL) OR (status = 'returned' AND returned_at IS NOT NULL)", name="ck_coupon_usages_return"),
        Index("uq_coupon_usages_active_customer", "coupon_id", "user_id", unique=True,
              postgresql_where=text("status = 'active'"), sqlite_where=text("status = 'active'")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
