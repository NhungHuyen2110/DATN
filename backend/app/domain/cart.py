from contextlib import AbstractContextManager
from decimal import Decimal
from typing import Protocol, Sequence


class CartError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ProductRecord(Protocol):
    id: int
    sku: str
    name: str
    stock: int
    sale_price: Decimal


class CartRecord(Protocol):
    id: int


class ItemRecord(Protocol):
    id: int
    product_id: int
    quantity: int
    product: ProductRecord


class CartRepository(Protocol):
    def mutation(self, user_id: int) -> AbstractContextManager[None]: ...
    def find(self, user_id: int) -> CartRecord | None: ...
    def items(self, cart_id: int) -> Sequence[ItemRecord]: ...
    def find_product_item(self, cart_id: int, product_id: int) -> ItemRecord | None: ...
    def owned_item(self, cart: CartRecord | None, item_id: int) -> ItemRecord: ...
    def lock_product(self, product_id: int) -> ProductRecord: ...
    def create(self, user_id: int) -> CartRecord: ...
    def add(self, cart_id: int, product_id: int, quantity: int) -> None: ...
    def delete(self, item: ItemRecord) -> None: ...
    def flush(self) -> None: ...


def check_stock(product: ProductRecord, quantity: int) -> None:
    if quantity > min(product.stock, 2147483647):
        raise CartError("conflict", "Số lượng vượt tồn kho")
