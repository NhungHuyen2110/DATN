from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.routers.orders import OrderID, admin, customer, staff_or_admin
from app.schemas.payment import CODConfirmation, PaymentResponse, PaymentURLResponse
from app.services import payments as service


router = APIRouter(tags=["Payments"])
Database = Annotated[Session, Depends(get_db)]


@router.post("/orders/{id}/payments/vnpay", response_model=PaymentURLResponse)
def create_url(id: OrderID, request: Request, user: Annotated[User, Depends(customer)], db: Database):
    # Do not trust arbitrary X-Forwarded-For supplied by browsers.
    return service.create_vnpay_url(db, user.id, id, request.client.host)


@router.post("/admin/orders/{id}/cod/confirm", response_model=PaymentResponse)
def confirm_cod(id: OrderID, request: CODConfirmation, user: Annotated[User, Depends(admin)], db: Database):
    return service.confirm_cod(db, user.id, id, request.collection_reference)


@router.post("/staff/orders/{id}/cod/confirm", response_model=PaymentResponse)
def staff_confirm_cod(id: OrderID, request: CODConfirmation, user: Annotated[User, Depends(staff_or_admin)], db: Database):
    return service.confirm_cod(db, user.id, id, request.collection_reference, allow_staff=True)


@router.get("/payments/vnpay/ipn")
def vnpay_ipn(request: Request, db: Database):
    return service.ipn(db, request.query_params.multi_items())


@router.get("/payments/vnpay/return")
def vnpay_return(request: Request, db: Database):
    return service.return_result(db, request.query_params.multi_items())
