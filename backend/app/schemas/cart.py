from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


PositiveInteger = Annotated[int, Field(strict=True, ge=1, le=2147483647)]


class AddCartItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: PositiveInteger
    quantity: PositiveInteger


class UpdateCartItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: PositiveInteger


class CartProduct(BaseModel):
    id: int
    sku: str
    name: str
    stock: int


class CartItemResponse(BaseModel):
    id: int
    product: CartProduct
    quantity: int
    unit_price_vnd: Decimal
    line_total_vnd: Decimal
    in_stock: bool


class CartResponse(BaseModel):
    id: int | None
    items: list[CartItemResponse]
    total_quantity: int
    subtotal_vnd: Decimal
