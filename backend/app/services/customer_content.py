"""Transactions for customer content; never mutate products, orders or payments."""

from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.models import Order, OrderItem, Product, ProductReview, WishlistItem
from app.schemas.customer_content import ReviewResponse, WishlistResponse
from app.services.orders import lock_user


@contextmanager
def customer_write(db, user_id):
    try:
        # Same first lock as Cart/Orders. Serializes same-customer duplicate adds.
        lock_user(db, user_id, "customer")
        yield
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dữ liệu yêu thích/đánh giá bị trùng hoặc đã thay đổi") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Không thể cập nhật yêu thích/đánh giá") from None
    except Exception:
        db.rollback()
        raise


def require_product(db, product_id):
    if db.scalar(select(Product.id).where(Product.id == product_id)) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")


def wishlist_query():
    product = joinedload(WishlistItem.product)
    return select(WishlistItem).options(
        product.defer(Product.cost_price), product.defer(Product.wholesale_price),
        *[product.joinedload(relation) for relation in (
            Product.category, Product.brand, Product.material, Product.gemstone, Product.collection)],
    )


def list_wishlist(db, user_id, page, page_size):
    condition = WishlistItem.user_id == user_id
    total = db.scalar(select(func.count()).select_from(WishlistItem).where(condition))
    items = db.scalars(wishlist_query().where(condition).order_by(WishlistItem.id.desc())
        .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": items, "page": page, "page_size": page_size, "total": total}


def add_wishlist(db, user_id, product_id):
    with customer_write(db, user_id):
        require_product(db, product_id)
        item = db.scalar(select(WishlistItem).where(
            WishlistItem.user_id == user_id, WishlistItem.product_id == product_id))
        if item is None:
            item = WishlistItem(user_id=user_id, product_id=product_id)
            db.add(item)
            db.flush()
        item = db.scalar(wishlist_query().where(WishlistItem.id == item.id))
        result = WishlistResponse.model_validate(item)
    return result


def delete_wishlist(db, user_id, product_id):
    with customer_write(db, user_id):
        require_product(db, product_id)
        item = db.scalar(select(WishlistItem).where(
            WishlistItem.user_id == user_id, WishlistItem.product_id == product_id).with_for_update())
        if item is None:
            raise HTTPException(status_code=404, detail="Sản phẩm không có trong danh sách yêu thích của bạn")
        db.delete(item)


def review_query():
    # Load only the author's name, never account credentials or contact details.
    from app.models import User
    return select(ProductReview).options(joinedload(ProductReview.user).load_only(User.full_name))


def review_response(review):
    name = review.user.full_name.strip()
    return ReviewResponse(id=review.id, product_id=review.product_id, rating=review.rating,
        comment=review.comment, author_display_name=(name[:1] + "***") if name else "Khách hàng",
        created_at=review.created_at, updated_at=review.updated_at)


def list_reviews(db, page, page_size, *, product_id=None, user_id=None):
    filters = []
    if product_id is not None:
        require_product(db, product_id)
        filters.append(ProductReview.product_id == product_id)
    if user_id is not None:
        filters.append(ProductReview.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(ProductReview).where(*filters))
    items = db.scalars(review_query().where(*filters).order_by(ProductReview.id.desc())
        .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [review_response(item) for item in items], "total": total,
            "page": page, "page_size": page_size}


def create_review(db, user_id, product_id, request):
    with customer_write(db, user_id):
        require_product(db, product_id)
        if db.scalar(select(ProductReview.id).where(ProductReview.user_id == user_id,
                ProductReview.product_id == product_id)) is not None:
            raise HTTPException(status_code=409, detail="Bạn đã đánh giá sản phẩm này")
        # Lock qualifying order after user, matching the existing order workflow.
        eligible = db.scalar(select(Order).where(
            Order.user_id == user_id, Order.status == "delivered", Order.payment_status == "paid",
            select(OrderItem.id).where(OrderItem.order_id == Order.id,
                OrderItem.product_id == product_id).exists(),
        ).order_by(Order.id).limit(1).with_for_update().execution_options(populate_existing=True))
        if eligible is None:
            raise HTTPException(status_code=403,
                detail="Chỉ được đánh giá sản phẩm trong đơn của bạn đã giao và đã thanh toán (delivered + paid)")
        item = ProductReview(user_id=user_id, product_id=product_id, **request.model_dump())
        db.add(item)
        db.flush()
        item = db.scalar(review_query().where(ProductReview.id == item.id))
        result = review_response(item)
    return result


def owned_review(db, user_id, review_id):
    # Lock only the owned review, not joined author rows.
    review = db.scalar(select(ProductReview).where(ProductReview.id == review_id,
        ProductReview.user_id == user_id).with_for_update().execution_options(populate_existing=True))
    if review is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đánh giá của bạn")
    return review


def update_review(db, user_id, review_id, request):
    with customer_write(db, user_id):
        item = owned_review(db, user_id, review_id)
        for field, value in request.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        db.flush()
        result = review_response(db.scalar(review_query().where(ProductReview.id == item.id)))
    return result


def delete_review(db, user_id, review_id):
    with customer_write(db, user_id):
        db.delete(owned_review(db, user_id, review_id))
