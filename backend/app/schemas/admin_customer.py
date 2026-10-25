"""Explicit public fields for Admin Customers; never serialize account secrets."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import StaffAccountResponse


class CustomerResponse(StaffAccountResponse):
    order_count: int = Field(ge=0)
    total_spent_vnd: Decimal = Field(ge=0)


class CustomerPage(BaseModel):
    items: list[CustomerResponse]
    page: int
    page_size: int
    total: int


class CustomerStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool = Field(strict=True)
