from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CODConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    collection_reference: str = Field(min_length=3, max_length=100)

    @field_validator("collection_reference")
    @classmethod
    def reference_not_blank(cls, value):
        value = value.strip()
        if len(value) < 3 or "\x00" in value:
            raise ValueError("Cần mã chứng từ thu tiền hợp lệ")
        return value


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    provider: str
    reference: str
    amount_vnd: Decimal
    status: str
    review_required: bool
    expires_at: datetime | None

    @field_validator("expires_at")
    @classmethod
    def utc_expiry(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class PaymentURLResponse(BaseModel):
    transaction: PaymentResponse
    payment_url: str
