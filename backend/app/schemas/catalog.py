"""Public catalog responses. Decimal is serialized as a JSON string by Pydantic."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LookupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    barcode: str
    name: str
    category: LookupResponse
    brand: LookupResponse
    material: LookupResponse
    gemstone: LookupResponse
    collection: LookupResponse
    weight: Decimal
    price_vnd: Decimal = Field(validation_alias="sale_price")
    stock: int


class ProductPage(BaseModel):
    items: list[ProductResponse]
    page: int
    page_size: int
    total: int


class StockUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_stock: int = Field(strict=True, ge=0, le=2147483647)
    stock: int = Field(strict=True, ge=0, le=2147483647)


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    stock: int


CatalogID = Annotated[int, Field(strict=True, ge=1, le=2147483647)]
CatalogMoney = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)]


class ProductUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    weight: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2, allow_inf_nan=False)
    category_id: CatalogID | None = None
    brand_id: CatalogID | None = None
    material_id: CatalogID | None = None
    gemstone_id: CatalogID | None = None
    collection_id: CatalogID | None = None
    sale_price: CatalogMoney | None = None
    expected_sale_price: CatalogMoney | None = None

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_patch(self):
        fields = self.model_fields_set
        if not fields or fields == {"expected_sale_price"}:
            raise ValueError("Provide at least one editable field")
        if any(getattr(self, field) is None for field in fields):
            raise ValueError("Explicit null values are not allowed")
        if ("sale_price" in fields) != ("expected_sale_price" in fields):
            raise ValueError("sale_price and expected_sale_price must be supplied together")
        return self
