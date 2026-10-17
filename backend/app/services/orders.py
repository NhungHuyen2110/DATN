"""Atomic checkout and order transitions; no payment gateway operations."""

from contextlib import contextmanager
from decimal import Decimal, localcontext
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import load_only, selectinload

from app.models import Cart, CartItem, Order, OrderItem, Product, User
from app.schemas.order import OrderResponse


TRANSITIONS = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"packing", "cancelled"},
    "packing": {"shipping"},
    "shipping": {"delivered"},
    "delivered": set(), "cancelled": set(),
}


@contextmanager
def transaction(db):
    try:
        yield
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dữ liệu đơn hàng đã thay đổi; vui lòng kiểm tra lại") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Không thể xử lý đơn hàng") from None
    except Exception:
        db.rollback()
        raise


def lock_user(db, user_id, required_role=None):
    user = db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Tài khoản không khả dụng")
    allowed_roles = {required_role} if isinstance(required_role, str) else required_role
    if allowed_roles and user.role.name not in allowed_roles:
        raise HTTPException(status_code=403, detail="Bạn không có quyền thực hiện thao tác này")
    return user


def lock_products(db, ids):
    # One canonical order across checkout and cancellation prevents product-lock cycles.
    products = db.scalars(select(Product).where(Product.id.in_(ids)).order_by(Product.id).options(
        load_only(Product.id, Product.sku, Product.name, Product.sale_price, Product.stock)
    ).with_for_update().execution_options(populate_existing=True)).all()
    if len(products) != len(set(ids)):
        raise HTTPException(status_code=409, detail="Sản phẩm trong giỏ hoặc đơn không còn tồn tại")
    return {product.id: product for product in products}


def serialize_order(db, order):
    db.flush()
    return OrderResponse.model_validate(order).model_dump()


def checkout(db, user_id, request):
    with transaction(db):
        lock_user(db, user_id, "customer")  # Same first lock as cart mutations.
        cart = db.scalar(select(Cart).where(Cart.user_id == user_id))
        items = [] if cart is None else db.scalars(select(CartItem).where(
            CartItem.cart_id == cart.id
        ).order_by(CartItem.product_id).with_for_update()).all()
        if not items:
            raise HTTPException(status_code=409, detail="Không thể đặt giỏ hàng rỗng")
        products = lock_products(db, [item.product_id for item in items])
        snapshots = []
        with localcontext() as context:
            context.prec = 50
            subtotal = Decimal("0.00")
            for item in items:
                product = products[item.product_id]
                if item.quantity <= 0 or item.quantity > product.stock:
                    raise HTTPException(status_code=409, detail="Số lượng sản phẩm vượt tồn kho")
                amount = product.sale_price * item.quantity
                subtotal += amount
                snapshots.append(OrderItem(
                    product_id=product.id, sku=product.sku, product_name=product.name,
                    quantity=item.quantity, unit_price_vnd=product.sale_price, line_total_vnd=amount,
                ))
            if subtotal >= Decimal(10) ** 36:
                raise HTTPException(status_code=409, detail="Tổng tiền vượt giới hạn đơn hàng")
        order = Order(
            code="LM" + uuid4().hex.upper(), user_id=user_id,
            recipient_name=request.recipient_name, phone=request.phone, address=request.address,
            status="pending", payment_status="unpaid", payment_method=request.payment_method, stock_restored=False,
            subtotal_vnd=subtotal, shipping_vnd=Decimal("0.00"), discount_vnd=Decimal("0.00"),
            total_vnd=subtotal, items=snapshots,
        )
        if request.payment_method == "vnpay":
            from app.services.payment_providers import get_provider
            get_provider().amount_units(subtotal)
        db.add(order)
        for item in items:
            products[item.product_id].stock -= item.quantity
            db.delete(item)
        result = serialize_order(db, order)
    return result


def change_status(db, admin_id, order_id, new_status, *, allow_staff=False):
    with transaction(db):
        lock_user(db, admin_id, {"staff", "admin"} if allow_staff else "admin")
        order = db.scalar(select(Order).where(Order.id == order_id).with_for_update().execution_options(populate_existing=True))
        if order is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
        if new_status != order.status:
            if new_status not in TRANSITIONS[order.status]:
                raise HTTPException(status_code=409, detail="Chuyển trạng thái đơn hàng không hợp lệ")
            if new_status == "cancelled":
                if order.payment_status != "unpaid" or order.stock_restored:
                    raise HTTPException(status_code=409, detail="Không thể tự động hủy hoặc hoàn kho đơn này")
                from app.services.payments import cancellation_allowed
                cancellation_allowed(db, order)
                items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.product_id)).all()
                products = lock_products(db, [item.product_id for item in items])
                for item in items:
                    product = products[item.product_id]
                    if product.stock + item.quantity > 2147483647:
                        raise HTTPException(status_code=409, detail="Hoàn kho vượt giới hạn số lượng")
                    product.stock += item.quantity
                order.stock_restored = True
            if new_status in {"packing", "shipping", "delivered"} and order.payment_method == "vnpay" and order.payment_status != "paid":
                raise HTTPException(status_code=409, detail="Đơn VNPay chưa được xác nhận thanh toán")
            order.status = new_status
        result = serialize_order(db, order)
    return result


def order_query():
    return select(Order).options(selectinload(Order.items))
