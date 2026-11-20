from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.core.dependencies import CurrentUser, customer, admin, staff_or_admin
from app.core.api_parameters import OrderID, Page, PageSize
from app.schemas.order import (
    CheckoutRequest, OrderPage, OrderResponse, StatusUpdate,
    StaffOrderPage, StaffOrderResponse,
)
from app.services import orders as service


router = APIRouter(tags=["Orders"])
Database = Annotated[Session, Depends(get_db)]


@router.post("/orders", response_model=OrderResponse, status_code=201)
def create_order(request: CheckoutRequest, user: Annotated[User, Depends(customer)], db: Database):
    return service.checkout(db, user.id, request)


def list_orders(db, page, page_size, user_id=None):
    return service.list_orders(db, page, page_size, user_id)


# Static /my must be registered before the integer detail route.
@router.get("/orders/my", response_model=OrderPage)
def my_orders(user: Annotated[User, Depends(customer)], db: Database, page: Page = 1, page_size: PageSize = 20):
    return list_orders(db, page, page_size, user.id)


@router.get("/orders/{id}", response_model=OrderResponse)
def get_order(id: OrderID, user: CurrentUser, db: Database):
    return service.get_order(db, id, None if user.role.name == "admin" else user.id)


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
    return service.get_order(db, id)


@router.patch("/staff/orders/{id}/status", response_model=StaffOrderResponse)
def staff_order_status(id: OrderID, request: StatusUpdate, user: Annotated[User, Depends(staff_or_admin)], db: Database):
    return service.change_status(db, user.id, id, request.status, allow_staff=True)
