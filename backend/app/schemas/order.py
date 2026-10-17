from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.auth import RegisterRequest


OrderStatus = Literal["pending", "confirmed", "packing", "shipping", "delivered", "cancelled"]


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_name: str = Field(min_length=2, max_length=150)
    phone: str = Field(min_length=10, max_length=20)
    address: str = Field(min_length=5, max_length=1000)
    payment_method: Literal["cod", "vnpay"] = "cod"

    @field_validator("recipient_name", "address")
    @classmethod
    def validate_text(cls, value, info):
        value = " ".join(value.split())
        minimum = 2 if info.field_name == "recipient_name" else 5
        if "\x00" in value or len(value) < minimum:
            raise ValueError("Thông tin giao hàng không hợp lệ")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        result = RegisterRequest.validate_phone(value)
        if result is None:
            raise ValueError("Cần số điện thoại người nhận")
        return result


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    sku: str
    product_name: str
    quantity: int
    unit_price_vnd: Decimal
    line_total_vnd: Decimal


class OrderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    user_id: int
    status: OrderStatus
    payment_status: Literal["unpaid", "paid", "refunded"]
    payment_method: Literal["cod", "vnpay"]
    subtotal_vnd: Decimal
    shipping_vnd: Decimal
    discount_vnd: Decimal
    total_vnd: Decimal
    created_at: datetime
    updated_at: datetime


class OrderResponse(OrderSummary):
    recipient_name: str
    phone: str
    address: str
    items: list[OrderItemResponse]


class OrderPage(BaseModel):
    items: list[OrderSummary]
    page: int
    page_size: int
    total: int


class StaffOrderSummary(OrderSummary):
    # Operational order data only; do not expose the customer's account identifier.
    user_id: int = Field(exclude=True)


class StaffOrderResponse(StaffOrderSummary):
    recipient_name: str
    phone: str
    address: str
    items: list[OrderItemResponse]


class StaffOrderPage(BaseModel):
    items: list[StaffOrderSummary]
    page: int
    page_size: int
    total: int
