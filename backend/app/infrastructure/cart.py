"""Preserves user -> product lock order and the shared auth Session transaction."""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, load_only

from app.domain.cart import CartError
from app.models import Cart, CartItem, Product, User


class SqlAlchemyCartRepository:
    def __init__(self, db: Session):
        self.db = db

    @contextmanager
    def mutation(self, user_id: int) -> Iterator[None]:
        try:
            owner = self.db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
            if owner is None or not owner.is_active:
                raise CartError("unauthorized", "Tài khoản không khả dụng")
            yield
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise CartError("conflict", "Giỏ hàng đã thay đổi; vui lòng thử lại") from None
        except SQLAlchemyError:
            self.db.rollback()
            raise CartError("persistence", "Không thể cập nhật giỏ hàng") from None
        except Exception:
            self.db.rollback()
            raise

    def find(self, user_id: int) -> Cart | None:
        return self.db.scalar(select(Cart).where(Cart.user_id == user_id))

    def items(self, cart_id: int):
        return self.db.scalars(select(CartItem).where(CartItem.cart_id == cart_id).options(
            joinedload(CartItem.product).load_only(Product.id, Product.sku, Product.name, Product.stock, Product.sale_price)
        ).order_by(CartItem.id)).all()

    def find_product_item(self, cart_id: int, product_id: int) -> CartItem | None:
        return self.db.scalar(select(CartItem).where(CartItem.cart_id == cart_id, CartItem.product_id == product_id))

    def owned_item(self, cart, item_id: int) -> CartItem:
        item = None if cart is None else self.db.scalar(select(CartItem).where(
            CartItem.id == item_id, CartItem.cart_id == cart.id))
        if item is None:
            raise CartError("missing", "Không tìm thấy mục trong giỏ hàng")
        return item

    def lock_product(self, product_id: int) -> Product:
        product = self.db.scalar(select(Product).where(Product.id == product_id).options(
            load_only(Product.id, Product.sku, Product.name, Product.stock, Product.sale_price)
        ).with_for_update().execution_options(populate_existing=True))
        if product is None:
            raise CartError("missing", "Không tìm thấy sản phẩm")
        return product

    def create(self, user_id: int) -> Cart:
        cart = Cart(user_id=user_id)
        self.db.add(cart)
        self.db.flush()
        return cart

    def add(self, cart_id: int, product_id: int, quantity: int) -> None:
        self.db.add(CartItem(cart_id=cart_id, product_id=product_id, quantity=quantity))

    def delete(self, item) -> None:
        self.db.delete(item)

    def flush(self) -> None:
        self.db.flush()
