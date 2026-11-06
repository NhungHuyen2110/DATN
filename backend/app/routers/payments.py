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
from fastapi.responses import HTMLResponse
from html import escape


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
    result = service.return_result(db, request.query_params.multi_items())
    # Browser users receive a readable summary. Never mark a payment paid here:
    # the validated IPN endpoint alone updates the transaction.
    if "text/html" not in request.headers.get("accept", "").lower():
        return result
    reference = escape(str(result["reference"]))
    payment_status = escape(str(result["payment_status"]))
    state = escape(str(result["transaction_status"]))
    return HTMLResponse("""<!doctype html><html lang="vi"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Trạng thái thanh toán | LUMIÈRE</title>
    <style>body{margin:0;background:#f8f5f1;color:#292824;font:15px/1.8 Arial,sans-serif}
    main{max-width:620px;margin:9vh auto;padding:40px;background:white;border:1px solid #e3d9ca}
    h1{font:400 37px Georgia,serif}small{color:#8b704d;letter-spacing:.15em}
    a{display:inline-block;background:#292824;color:white;text-decoration:none;padding:12px 20px;margin-top:18px}
    .note{padding:14px;background:#f4eadd;border-left:3px solid #ac8a5c}</style></head><body>
    <main><small>LUMIÈRE FINE JEWELRY</small><h1>Kết quả chuyển về từ VNPay</h1>
    <p>Mã giao dịch: <strong>""" + reference + """</strong></p>
    <p>Trạng thái thanh toán trong hệ thống: <strong>""" + payment_status + """</strong></p>
    <p>Trạng thái giao dịch: <strong>""" + state + """</strong></p>
    <p class="note">Trang chuyển về chỉ hiển thị thông tin. Hệ thống chỉ xác nhận đã thanh toán sau khi nhận và kiểm tra IPN từ VNPay. Nếu chưa cập nhật, hãy kiểm tra lại đơn hàng.</p>
    <a href="/pages/orders.html">Xem đơn hàng của tôi</a></main></body></html>""")
