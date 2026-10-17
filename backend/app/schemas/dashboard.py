"""Amounts are confirmed payments, not profit or net revenue after refunds."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ReconciliationReason(BaseModel):
    reason: str
    order_count: int


class DashboardResponse(BaseModel):
    total_orders: int
    orders_by_status: dict[str, int]
    orders_by_payment_status: dict[str, int]
    confirmed_payment_amount_vnd: Decimal = Field(description="Tiền thanh toán hợp lệ được hệ thống xác nhận; không phải lợi nhuận/doanh thu thuần sau hoàn tiền")
    reconciliation_order_count: int
    reconciliation_order_value_vnd: Decimal = Field(description="Tổng giá trị các đơn cần đối soát, mỗi đơn một lần; không phải số tiền thực thu sai lệch")
    reconciliation_reasons: list[ReconciliationReason]
    total_products: int
    out_of_stock_products: int


class RevenueBucket(BaseModel):
    period_start: date
    confirmed_payment_amount_vnd: Decimal
    confirmed_payment_order_count: int


class RevenueResponse(BaseModel):
    start_date: date
    end_date: date
    group_by: Literal["day", "month"]
    timezone: str = "Asia/Ho_Chi_Minh"
    time_basis: str = "payment_transaction.verified_at"
    confirmed_payment_amount_vnd: Decimal
    confirmed_payment_order_count: int
    items: list[RevenueBucket]
