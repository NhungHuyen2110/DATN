"""Admin Staff management with locally sanitized request validation errors."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.routers.orders import OrderID, Page, PageSize, admin
from app.schemas.auth import (
    ProfileUpdateRequest, StaffAccountPage, StaffAccountResponse,
    StaffCreateRequest, StaffStatusUpdate,
)
from app.services import staff as service


class SafeValidationRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                errors = [{key: error[key] for key in ("type", "loc", "msg")} for error in exc.errors()]
                return JSONResponse(status_code=422, content={"detail": errors})

        return safe_handler


router = APIRouter(prefix="/admin/staff", tags=["Admin Staff"], route_class=SafeValidationRoute)
Database = Annotated[Session, Depends(get_db)]
ActiveAdmin = Annotated[User, Depends(admin)]


@router.get("", response_model=StaffAccountPage)
def list_accounts(actor: ActiveAdmin, db: Database, page: Page = 1, page_size: PageSize = 20):
    return service.list_staff(db, page, page_size)


@router.get("/{id}", response_model=StaffAccountResponse)
def get_account(id: OrderID, actor: ActiveAdmin, db: Database):
    return service.get_staff(db, id)


@router.post("", response_model=StaffAccountResponse, status_code=201)
def create_account(request: StaffCreateRequest, actor: ActiveAdmin, db: Database):
    return service.create_staff(db, actor.id, request)


@router.patch("/{id}", response_model=StaffAccountResponse)
def update_account(id: OrderID, request: ProfileUpdateRequest, actor: ActiveAdmin, db: Database):
    return service.update_staff(db, actor.id, id, request)


@router.patch("/{id}/status", response_model=StaffAccountResponse)
def set_account_status(id: OrderID, request: StaffStatusUpdate, actor: ActiveAdmin, db: Database):
    return service.set_staff_status(db, actor.id, id, request.is_active)
