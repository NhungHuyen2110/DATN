"""Session-owned carts. Mutations lock users first, then the affected product."""

from contextlib import contextmanager
from decimal import Decimal, localcontext
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, load_only

from app.core.database import get_db
from app.models import Cart, CartItem, Product, User
from app.routers.auth import get_current_user
from app.schemas.cart import AddCartItem, CartResponse, UpdateCartItem


router = APIRouter(prefix="/cart", tags=["Cart"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
ItemID = Annotated[int, Path(ge=1, le=2147483647)]


def find_cart(db, user_id):
    return db.scalar(select(Cart).where(Cart.user_id == user_id))


def cart_response(db, cart):
    if cart is None:
        return {"id": None, "items": [], "total_quantity": 0, "subtotal_vnd": Decimal("0.00")}
    items = db.scalars(select(CartItem).where(CartItem.cart_id == cart.id).options(
        joinedload(CartItem.product).load_only(
            Product.id, Product.sku, Product.name, Product.stock, Product.sale_price
        )
    ).order_by(CartItem.id)).all()
    result = []
    # Numeric(18,2) * Integer can exceed the default Decimal precision when summed.
    with localcontext() as context:
        context.prec = 50
        subtotal = Decimal("0.00")
        for item in items:
            product = item.product
            line_total = product.sale_price * item.quantity
            subtotal += line_total
            result.append({
                "id": item.id,
                "product": {"id": product.id, "sku": product.sku, "name": product.name, "stock": product.stock},
                "quantity": item.quantity, "unit_price_vnd": product.sale_price,
                "line_total_vnd": line_total, "in_stock": item.quantity <= product.stock,
            })
    return {"id": cart.id, "items": result, "total_quantity": sum(i.quantity for i in items), "subtotal_vnd": subtotal}


@contextmanager
def mutation(db, user_id):
    try:
        # Auth has already begun a transaction on this same dependency Session.
        # A user row exists even when their cart does not, avoiding first-add races.
        owner = db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
        if owner is None or not owner.is_active:
            raise HTTPException(status_code=401, detail="Tài khoản không khả dụng")
        yield
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Giỏ hàng đã thay đổi; vui lòng thử lại") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Không thể cập nhật giỏ hàng") from None
    except Exception:
        db.rollback()
        raise


def locked_product(db, product_id):
    product = db.scalar(select(Product).where(Product.id == product_id).options(
        load_only(Product.id, Product.sku, Product.name, Product.stock, Product.sale_price)
    ).with_for_update().execution_options(populate_existing=True))
    if product is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    return product


def check_stock(product, quantity):
    if quantity > min(product.stock, 2147483647):
        raise HTTPException(status_code=409, detail="Số lượng vượt tồn kho")


def owned_item(db, cart, item_id):
    item = None if cart is None else db.scalar(select(CartItem).where(
        CartItem.id == item_id, CartItem.cart_id == cart.id
    ))
    if item is None:
        # Same response for missing items and another user's items.
        raise HTTPException(status_code=404, detail="Không tìm thấy mục trong giỏ hàng")
    return item


@router.get("", response_model=CartResponse)
def get_cart(user: CurrentUser, db: Database):
    return cart_response(db, find_cart(db, user.id))


@router.post("/items", response_model=CartResponse)
def add_item(request: AddCartItem, user: CurrentUser, db: Database):
    with mutation(db, user.id):
        cart = find_cart(db, user.id)
        item = None if cart is None else db.scalar(select(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.product_id == request.product_id
        ))
        quantity = request.quantity + (item.quantity if item is not None else 0)
        product = locked_product(db, request.product_id)
        check_stock(product, quantity)
        if cart is None:
            cart = Cart(user_id=user.id)
            db.add(cart)
            db.flush()
        if item is None:
            db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=quantity))
        else:
            item.quantity = quantity
        db.flush()
        result = cart_response(db, cart)
    return result


@router.patch("/items/{id}", response_model=CartResponse)
def update_item(id: ItemID, request: UpdateCartItem, user: CurrentUser, db: Database):
    with mutation(db, user.id):
        cart = find_cart(db, user.id)
        item = owned_item(db, cart, id)
        check_stock(locked_product(db, item.product_id), request.quantity)
        item.quantity = request.quantity
        db.flush()
        result = cart_response(db, cart)
    return result


@router.delete("/items/{id}", response_model=CartResponse)
def delete_item(id: ItemID, user: CurrentUser, db: Database):
    with mutation(db, user.id):
        cart = find_cart(db, user.id)
        db.delete(owned_item(db, cart, id))
        db.flush()
        result = cart_response(db, cart)
    return result
