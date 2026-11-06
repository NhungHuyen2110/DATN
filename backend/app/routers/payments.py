from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.routers.orders import OrderID, admin, customer, staff_or_admin
from app.schemas.payment import CODConfirmation, PaymentResponse, PaymentURLResponse
from app.services import payments as service
from app.services.payment_providers import VNPaySandbox
from app.services.shipping import public_shipping_policy
from fastapi import HTTPException


router = APIRouter(tags=["Payments"])
Database = Annotated[Session, Depends(get_db)]

@router.get("/checkout/payment-methods")
def payment_methods():
    """Public capabilities only; never expose merchant credentials."""
    try:
        VNPaySandbox.from_environment()
        enabled = True
    except HTTPException:
        enabled = False
    return {"shipping": public_shipping_policy(),
            "cod": {"enabled": True, "label": "Thanh toán khi nhận hàng"},
            "vnpay": {"enabled": enabled, "label": "VNPay Sandbox",
                      "message": "Thanh toán VNPay Sandbox đã cấu hình" if enabled
                                 else "VNPay Sandbox chưa cấu hình merchant và URL HTTPS."}}



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
