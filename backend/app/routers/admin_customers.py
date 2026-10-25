"""Admin-only customer listing, detail and account status."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AfterValidator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.routers.admin_staff import SafeValidationRoute
from app.routers.orders import OrderID, Page, PageSize, admin
from app.schemas.admin_customer import CustomerPage, CustomerResponse, CustomerStatusUpdate
from app.services import admin_customers as service


def clean_search(value):
    if value is not None:
        if "\x00" in value:
            raise ValueError("Từ khóa không được chứa ký tự NUL")
        return value.strip()
    return value


Search = Annotated[str | None, Query(max_length=255), AfterValidator(clean_search)]
Database = Annotated[Session, Depends(get_db)]
ActiveAdmin = Annotated[User, Depends(admin)]
router = APIRouter(prefix="/admin/customers", tags=["Admin Customers"], route_class=SafeValidationRoute)


@router.get("", response_model=CustomerPage)
def list_accounts(actor: ActiveAdmin, db: Database, page: Page = 1, page_size: PageSize = 20,
                  search: Search = None, is_active: bool | None = None):
    return service.list_customers(db, page, page_size, search, is_active)


@router.get("/{id}", response_model=CustomerResponse)
def get_account(id: OrderID, actor: ActiveAdmin, db: Database):
    return service.customer_detail(db, id)


@router.patch("/{id}/status", response_model=CustomerResponse)
def set_account_status(id: OrderID, request: CustomerStatusUpdate, actor: ActiveAdmin, db: Database):
    return service.set_customer_status(db, actor.id, id, request.is_active)
