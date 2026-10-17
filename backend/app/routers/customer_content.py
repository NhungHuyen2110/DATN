"""Wishlist and product reviews only; reuse existing customer session auth."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.routers.orders import OrderID, Page, PageSize, customer
from app.schemas.customer_content import (
    DeleteMessageResponse,
    ReviewCreate, ReviewPage, ReviewResponse, ReviewUpdate, WishlistAdd, WishlistPage, WishlistResponse,
)
from app.services import customer_content as service


router = APIRouter(tags=["Wishlist & Reviews"])
Database = Annotated[Session, Depends(get_db)]
Customer = Annotated[User, Depends(customer)]


@router.get("/wishlist", response_model=WishlistPage)
def wishlist(user: Customer, db: Database, page: Page = 1, page_size: PageSize = 20):
    return service.list_wishlist(db, user.id, page, page_size)


@router.post("/wishlist/items", response_model=WishlistResponse)
def add_wishlist(request: WishlistAdd, user: Customer, db: Database):
    return service.add_wishlist(db, user.id, request.product_id)


@router.delete("/wishlist/items/{product_id}", status_code=200, response_model=DeleteMessageResponse,
    responses={200: {"description": "Đã xóa sản phẩm khỏi danh sách yêu thích",
        "content": {"application/json": {"example": {"message": "Đã xóa sản phẩm khỏi danh sách yêu thích"}}}}})
def delete_wishlist(product_id: OrderID, user: Customer, db: Database):
    service.delete_wishlist(db, user.id, product_id)
    return {"message": "Đã xóa sản phẩm khỏi danh sách yêu thích"}


@router.get("/products/{product_id}/reviews", response_model=ReviewPage)
def product_reviews(product_id: OrderID, db: Database, page: Page = 1, page_size: PageSize = 20):
    return service.list_reviews(db, page, page_size, product_id=product_id)


@router.get("/reviews/my", response_model=ReviewPage)
def my_reviews(user: Customer, db: Database, page: Page = 1, page_size: PageSize = 20):
    return service.list_reviews(db, page, page_size, user_id=user.id)


@router.post("/products/{product_id}/reviews", response_model=ReviewResponse, status_code=201)
def create_review(product_id: OrderID, request: ReviewCreate, user: Customer, db: Database):
    return service.create_review(db, user.id, product_id, request)


@router.patch("/reviews/{id}", response_model=ReviewResponse)
def update_review(id: OrderID, request: ReviewUpdate, user: Customer, db: Database):
    return service.update_review(db, user.id, id, request)


@router.delete("/reviews/{id}", status_code=200, response_model=DeleteMessageResponse,
    responses={200: {"description": "Đã xóa đánh giá thành công",
        "content": {"application/json": {"example": {"message": "Đã xóa đánh giá thành công"}}}}})
def delete_review(id: OrderID, user: Customer, db: Database):
    service.delete_review(db, user.id, id)
    return {"message": "Đã xóa đánh giá thành công"}
