from datetime import datetime, timezone
from decimal import Decimal
import re
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator


def normalize_code(value):
    if not isinstance(value, str):
        raise ValueError("Coupon code must be a string")
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{3,24}", value, flags=re.ASCII):
        raise ValueError("Coupon code must contain 3-24 ASCII letters, digits, _ or -")
    return value


CouponCode = Annotated[str, BeforeValidator(normalize_code)]
Money = Annotated[Decimal, Field(ge=0, max_digits=38, decimal_places=2, allow_inf_nan=False)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=38, decimal_places=2, allow_inf_nan=False)]
Limit = Annotated[int, Field(strict=True, ge=1, le=2147483647)]


class CouponCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: CouponCode
    discount_type: Literal["fixed", "percent"]
    discount_value: PositiveMoney
    max_discount_vnd: PositiveMoney | None = None
    min_order_vnd: Money = Decimal("0.00")
    usage_limit: Limit | None = None
    starts_at: datetime
    ends_at: datetime
    is_active: bool = Field(default=True, strict=True)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone is required")
        return value.astimezone(timezone.utc)

    @field_validator("description")
    @classmethod
    def description_valid(cls, value):
        if value is not None and "\x00" in value:
            raise ValueError("NUL is not allowed")
        return value

    @model_validator(mode="after")
    def coherent(self):
        if self.discount_type == "percent" and self.discount_value > 100:
            raise ValueError("Percent must not exceed 100")
        if self.discount_type == "fixed" and self.max_discount_vnd is not None:
            raise ValueError("max_discount_vnd is only supported for percent coupons")
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at must precede ends_at")
        return self


class CouponPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: CouponCode | None = None
    discount_type: Literal["fixed", "percent"] | None = None
    discount_value: PositiveMoney | None = None
    max_discount_vnd: PositiveMoney | None = None
    min_order_vnd: Money | None = None
    usage_limit: Limit | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = Field(default=None, strict=True)
    description: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def meaningful_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        nullable = {"max_discount_vnd", "usage_limit", "description"}
        for key in self.model_fields_set - nullable:
            if getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null")
        return self


class CouponStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool = Field(strict=True)


class CouponResponse(CouponCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    used_count: int
    created_at: datetime
    updated_at: datetime

    @field_validator("starts_at", "ends_at", "created_at", "updated_at")
    @classmethod
    def timezone_required(cls, value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class CouponPage(BaseModel):
    items: list[CouponResponse]
    page: int
    page_size: int
    total: int


class CouponValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    coupon_code: CouponCode


class CouponValidation(BaseModel):
    valid: bool
    reason: str | None = None
    coupon_code: str
    subtotal_vnd: Decimal
    discount_vnd: Decimal
    total_vnd: Decimal
