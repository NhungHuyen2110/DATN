"""Admin-only read endpoints for system-confirmed payments (not net revenue)."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.routers.orders import admin
from app.schemas.dashboard import DashboardResponse, RevenueResponse
from app.services import dashboard as service


router = APIRouter(tags=["Admin Dashboard"])
Database = Annotated[Session, Depends(get_db)]
ActiveAdmin = Annotated[User, Depends(admin)]


@router.get("/admin/dashboard", response_model=DashboardResponse,
    summary="All-time orders, current stock and system-confirmed payments")
def dashboard(user: ActiveAdmin, db: Database):
    return service.dashboard(db)


@router.get("/admin/reports/revenue", response_model=RevenueResponse,
    summary="System-confirmed payments by verification date; not profit or net revenue")
def revenue(user: ActiveAdmin, db: Database, start_date: date, end_date: date,
            group_by: Literal["day", "month"] = "day"):
    return service.revenue(db, start_date, end_date, group_by)
