from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.routers.admin_customers import Search
from app.routers.admin_staff import SafeValidationRoute
from app.routers.orders import OrderID, Page, PageSize, admin, customer
from app.schemas.coupon import (CouponCreate, CouponPage, CouponPatch, CouponResponse,
                               CouponStatus, CouponValidateRequest, CouponValidation)
from app.services import coupons as service

router = APIRouter(tags=["Coupons"], route_class=SafeValidationRoute)
Database = Annotated[Session, Depends(get_db)]
Admin = Annotated[User, Depends(admin)]
Customer = Annotated[User, Depends(customer)]


@router.get("/admin/coupons", response_model=CouponPage)
def list_coupons(actor: Admin, db: Database, page: Page = 1, page_size: PageSize = 20,
                 search: Search = None, is_active: bool | None = None):
    return service.list_coupons(db, page, page_size, search, is_active)


@router.get("/admin/coupons/{id}", response_model=CouponResponse)
def detail(id: OrderID, actor: Admin, db: Database):
    return CouponResponse.model_validate(service.get_coupon(db, id))


@router.post("/admin/coupons", response_model=CouponResponse, status_code=201)
def create(request: CouponCreate, actor: Admin, db: Database):
    return service.create_coupon(db, actor.id, request)


@router.patch("/admin/coupons/{id}", response_model=CouponResponse)
def update(id: OrderID, request: CouponPatch, actor: Admin, db: Database):
    return service.update_coupon(db, actor.id, id, request.model_dump(exclude_unset=True))


@router.patch("/admin/coupons/{id}/status", response_model=CouponResponse)
def status(id: OrderID, request: CouponStatus, actor: Admin, db: Database):
    return service.update_coupon(db, actor.id, id, {"is_active": request.is_active})


@router.post("/checkout/coupon/validate", response_model=CouponValidation)
def validate(request: CouponValidateRequest, actor: Customer, db: Database):
    return service.validate_cart(db, actor.id, request.coupon_code)
