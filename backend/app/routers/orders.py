from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Order, User
from app.routers.auth import get_current_user
from app.schemas.order import (
    CheckoutRequest, OrderPage, OrderResponse, StatusUpdate,
    StaffOrderPage, StaffOrderResponse,
)
from app.services import orders as service


router = APIRouter(tags=["Orders"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OrderID = Annotated[int, Path(ge=1, le=2147483647)]
Page = Annotated[int, Query(ge=1, le=2147483647)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def customer(user: CurrentUser):
    if user.role.name != "customer":
        raise HTTPException(status_code=403, detail="Chỉ khách hàng được đặt hàng và xem danh sách cá nhân")
    return user


def admin(user: CurrentUser):
    if user.role.name != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin được quản lý đơn hàng")
    return user


def staff_or_admin(user: CurrentUser):
    if user.role.name not in {"staff", "admin"}:
        raise HTTPException(status_code=403, detail="Chỉ Staff hoặc Admin được xử lý đơn hàng")
    return user


@router.post("/orders", response_model=OrderResponse, status_code=201)
def create_order(request: CheckoutRequest, user: Annotated[User, Depends(customer)], db: Database):
    return service.checkout(db, user.id, request)


def list_orders(db, page, page_size, user_id=None):
    filters = [] if user_id is None else [Order.user_id == user_id]
    total = db.scalar(select(func.count()).select_from(Order).where(*filters))
    items = db.scalars(select(Order).where(*filters).order_by(Order.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# Static /my must be registered before the integer detail route.
@router.get("/orders/my", response_model=OrderPage)
def my_orders(user: Annotated[User, Depends(customer)], db: Database, page: Page = 1, page_size: PageSize = 20):
    return list_orders(db, page, page_size, user.id)


@router.get("/orders/{id}", response_model=OrderResponse)
def get_order(id: OrderID, user: CurrentUser, db: Database):
    query = service.order_query().where(Order.id == id)
    if user.role.name != "admin":
        query = query.where(Order.user_id == user.id)
    order = db.scalar(query)
    if order is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    return order


@router.get("/admin/orders", response_model=OrderPage)
def admin_orders(user: Annotated[User, Depends(admin)], db: Database, page: Page = 1, page_size: PageSize = 20):
    return list_orders(db, page, page_size)


@router.patch("/admin/orders/{id}/status", response_model=OrderResponse)
def update_status(id: OrderID, request: StatusUpdate, user: Annotated[User, Depends(admin)], db: Database):
    return service.change_status(db, user.id, id, request.status)


@router.get("/staff/orders", response_model=StaffOrderPage)
def staff_orders(user: Annotated[User, Depends(staff_or_admin)], db: Database, page: Page = 1, page_size: PageSize = 20):
    return list_orders(db, page, page_size)


@router.get("/staff/orders/{id}", response_model=StaffOrderResponse)
def staff_order_detail(id: OrderID, user: Annotated[User, Depends(staff_or_admin)], db: Database):
    order = db.scalar(service.order_query().where(Order.id == id))
    if order is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    return order


@router.patch("/staff/orders/{id}/status", response_model=StaffOrderResponse)
def staff_order_status(id: OrderID, request: StatusUpdate, user: Annotated[User, Depends(staff_or_admin)], db: Database):
    return service.change_status(db, user.id, id, request.status, allow_staff=True)
