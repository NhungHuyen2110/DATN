"""Coupon pricing, row-locked redemption and reversible usage accounting."""

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models import Cart, CartItem, Coupon, CouponUsage
from app.schemas.coupon import CouponCreate, CouponResponse
from app.services.orders import lock_products, lock_user, transaction


def aware(value):
    # SQLite test fixtures drop timezone; PostgreSQL returns aware timestamptz.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def get_coupon(db, ident, *, lock=False):
    query = select(Coupon).where(Coupon.id == ident)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    result = db.scalar(query)
    if result is None:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return result


def serialize(db, coupon):
    db.flush()
    db.refresh(coupon)
    return CouponResponse.model_validate(coupon).model_dump()


@contextmanager
def admin_write(db, actor_id):
    try:
        lock_user(db, actor_id, "admin")
        yield
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate coupon code or conflicting coupon data") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Cannot update coupon") from None
    except Exception:
        db.rollback()
        raise


def list_coupons(db, page, page_size, search=None, is_active=None):
    query = select(Coupon)
    if search:
        text = search.strip().replace("/", "//").replace("%", "/%").replace("_", "/_")
        query = query.where(or_(Coupon.code.ilike("%" + text + "%", escape="/"),
                                Coupon.description.ilike("%" + text + "%", escape="/")))
    if is_active is not None:
        query = query.where(Coupon.is_active == is_active)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(Coupon.id).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [CouponResponse.model_validate(c).model_dump() for c in items],
            "page": page, "page_size": page_size, "total": total}


def create_coupon(db, actor_id, request):
    with admin_write(db, actor_id):
        coupon = Coupon(**request.model_dump(), used_count=0)
        db.add(coupon)
        result = serialize(db, coupon)
    return result


def update_coupon(db, actor_id, ident, changes):
    with admin_write(db, actor_id):
        coupon = get_coupon(db, ident, lock=True)
        data = {key: getattr(coupon, key) for key in CouponCreate.model_fields}
        data["starts_at"], data["ends_at"] = aware(data["starts_at"]), aware(data["ends_at"])
        data.update(changes)
        try:
            validated = CouponCreate.model_validate(data)
        except ValidationError:
            raise HTTPException(status_code=422, detail="Invalid coupon fields or date/value combination") from None
        if validated.usage_limit is not None and validated.usage_limit < coupon.used_count:
            raise HTTPException(status_code=409, detail="usage_limit cannot be below used_count")
        for key, value in validated.model_dump().items():
            setattr(coupon, key, value)
        result = serialize(db, coupon)
    return result


def failure_reason(db, coupon, user_id, subtotal, now):
    if coupon is None:
        return "not_found"
    if not coupon.is_active:
        return "inactive"
    if now < aware(coupon.starts_at):
        return "not_started"
    if now >= aware(coupon.ends_at):
        return "expired"
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        return "exhausted"
    if coupon.used_count >= 2147483647:
        return "counter_capacity"
    if subtotal < coupon.min_order_vnd:
        return "min_order"
    if db.scalar(select(CouponUsage.id).where(CouponUsage.coupon_id == coupon.id,
            CouponUsage.user_id == user_id, CouponUsage.status == "active")) is not None:
        return "already_used"
    return None


def price(coupon, subtotal):
    with localcontext() as context:
        context.prec = 80
        amount = coupon.discount_value
        if coupon.discount_type == "percent":
            amount = subtotal * amount / Decimal(100)
            if coupon.max_discount_vnd is not None:
                amount = min(amount, coupon.max_discount_vnd)
        # Coupon reductions are rounded to whole VND, half up. Existing product
        # prices/subtotal retain their current 2-decimal representation.
        amount = min(subtotal, amount).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        total = subtotal - amount
        if amount <= 0 or amount > subtotal or total <= 0:
            return None
        return amount.quantize(Decimal("0.01")), total


def evaluate(db, code, user_id, subtotal, *, lock=False):
    query = select(Coupon).where(Coupon.code == code)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    coupon = db.scalar(query)
    reason = failure_reason(db, coupon, user_id, subtotal, datetime.now(timezone.utc))
    amounts = None if reason else price(coupon, subtotal)
    if reason is None and amounts is None:
        reason = "invalid_discount"
    return coupon, amounts, reason


def redeem(db, code, user_id, subtotal):
    coupon, amounts, reason = evaluate(db, code, user_id, subtotal, lock=True)
    if reason:
        raise HTTPException(status_code=409, detail="Coupon invalid: " + reason)
    return coupon, amounts


def record_usage(db, coupon, order, user_id):
    # Caller owns the coupon row lock until the enclosing checkout commits.
    coupon.used_count += 1
    db.add(CouponUsage(coupon_id=coupon.id, user_id=user_id, order_id=order.id, status="active"))


def return_usage(db, order):
    if order.coupon_id is None:
        return
    coupon = get_coupon(db, order.coupon_id, lock=True)
    usage = db.scalar(select(CouponUsage).where(CouponUsage.order_id == order.id).with_for_update())
    if usage is None or usage.coupon_id != coupon.id or usage.user_id != order.user_id:
        raise HTTPException(status_code=409, detail="Coupon usage requires reconciliation")
    if usage.status == "active":
        if coupon.used_count <= 0:
            raise HTTPException(status_code=409, detail="Coupon counter requires reconciliation")
        coupon.used_count -= 1
        usage.status = "returned"
        usage.returned_at = datetime.now(timezone.utc)


def validate_cart(db, user_id, code):
    # Serialize with same-user cart writes; validation does not lock/reserve coupon.
    with transaction(db):
        lock_user(db, user_id, "customer")
        cart = db.scalar(select(Cart).where(Cart.user_id == user_id))
        items = [] if cart is None else db.scalars(select(CartItem).where(
            CartItem.cart_id == cart.id).order_by(CartItem.product_id).with_for_update()).all()
        if not items:
            raise HTTPException(status_code=409, detail="Cart is empty")
        products = lock_products(db, [item.product_id for item in items])
        with localcontext() as context:
            context.prec = 50
            subtotal = Decimal("0.00")
            for item in items:
                product = products[item.product_id]
                if item.quantity <= 0 or item.quantity > product.stock:
                    raise HTTPException(status_code=409, detail="Insufficient stock")
                subtotal += product.sale_price * item.quantity
            if subtotal >= Decimal(10) ** 36:
                raise HTTPException(status_code=409, detail="Order amount exceeds limit")
        coupon, amounts, reason = evaluate(db, code, user_id, subtotal)
        result = {"valid": reason is None, "reason": reason, "coupon_code": code,
                  "subtotal_vnd": subtotal, "discount_vnd": Decimal("0.00") if reason else amounts[0],
                  "total_vnd": subtotal if reason else amounts[1]}
    return result
