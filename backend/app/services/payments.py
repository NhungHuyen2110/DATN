"""Payment persistence. Only validated IPN or authorized COD collection can pay."""

from datetime import datetime, timedelta, timezone
import hashlib
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models import Order, PaymentTransaction
from app.schemas.payment import PaymentResponse
from app.services.orders import lock_user, transaction
from app.services.payment_providers import VNP_TIMEZONE, aware, canonical, get_provider


def order_lock(db, order_id):
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update().execution_options(populate_existing=True))
    if order is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    return order


def cancellation_allowed(db, order):
    payments = db.scalars(select(PaymentTransaction).where(PaymentTransaction.order_id == order.id)).all()
    if any(p.status != "failed" or p.review_required for p in payments):
        raise HTTPException(status_code=409, detail="Giao dịch chưa rõ hoặc đã thanh toán; cần đối soát trước khi hủy")


def create_vnpay_url(db, user_id, order_id, client_ip):
    with transaction(db):
        lock_user(db, user_id, "customer")
        order = order_lock(db, order_id)
        if order.user_id != user_id:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
        if order.payment_method != "vnpay" or order.payment_status != "unpaid" or order.status != "pending":
            raise HTTPException(status_code=409, detail="Đơn hàng không thể tạo thanh toán VNPay")
        provider = get_provider()
        provider.amount_units(order.total_vnd)
        payment = db.scalar(select(PaymentTransaction).where(PaymentTransaction.order_id == order.id))
        now = datetime.now(timezone.utc).replace(microsecond=0)
        if payment is not None:
            if (payment.status != "pending" or payment.review_required or aware(payment.expires_at) <= now
                    or payment.merchant_code != provider.merchant or payment.return_url != provider.return_url):
                raise HTTPException(status_code=409, detail="Giao dịch đã kết thúc hoặc cần đối soát; không tự tạo lại")
        else:
            payment = PaymentTransaction(
                order_id=order.id, provider="vnpay", reference=uuid4().hex,
                amount_vnd=order.total_vnd, status="pending", review_required=False,
                merchant_code=provider.merchant, return_url=provider.return_url, client_ip=client_ip,
                created_at=now, expires_at=now + timedelta(minutes=15),
            )
            db.add(payment)
        db.flush()
        url = provider.payment_url(payment)
        result = {"transaction": PaymentResponse.model_validate(payment).model_dump(), "payment_url": url}
    return result


def confirm_cod(db, admin_id, order_id, reference, *, allow_staff=False):
    with transaction(db):
        lock_user(db, admin_id, {"staff", "admin"} if allow_staff else "admin")
        order = order_lock(db, order_id)
        if order.payment_method != "cod" or order.status != "delivered":
            raise HTTPException(status_code=409, detail="Chỉ xác nhận COD sau khi đơn đã giao")
        previous = db.scalar(select(PaymentTransaction).where(PaymentTransaction.order_id == order.id))
        if previous is not None:
            if (previous.status != "succeeded" or previous.provider_transaction_id != reference
                    or order.payment_status != "paid" or previous.amount_vnd != order.total_vnd):
                raise HTTPException(status_code=409, detail="Chứng từ thu tiền không khớp giao dịch đã ghi nhận")
            result = PaymentResponse.model_validate(previous).model_dump()
        else:
            if order.payment_status != "unpaid" or order.total_vnd <= 0:
                raise HTTPException(status_code=409, detail="Trạng thái hoặc số tiền COD không hợp lệ")
            payment = PaymentTransaction(
                order_id=order.id, provider="cod", reference=uuid4().hex,
                amount_vnd=order.total_vnd, status="succeeded", review_required=False,
                provider_transaction_id=reference, confirmed_by=admin_id, verified_at=datetime.now(timezone.utc),
            )
            db.add(payment)
            order.payment_status = "paid"
            db.flush()
            result = PaymentResponse.model_validate(payment).model_dump()
    return result


def checked_callback(pairs):
    provider = get_provider()
    try:
        params = provider.verify(pairs)
    except ValueError:
        raise HTTPException(status_code=400, detail="Callback VNPay không hợp lệ") from None
    return provider, params


def validate_payment_order(provider, params, payment, order):
    if (payment.provider != "vnpay" or order.payment_method != "vnpay"
            or payment.merchant_code != params["vnp_TmnCode"]
            or params["vnp_OrderInfo"] != "Thanh toan don hang " + str(order.id)):
        return "01"
    expected = provider.amount_units(payment.amount_vnd)
    if int(params["vnp_Amount"]) != int(expected) or payment.amount_vnd != order.total_vnd:
        return "04"
    return None


def ipn(db, pairs):
    try:
        provider, params = checked_callback(pairs)
    except HTTPException as exc:
        if exc.status_code == 503:
            return {"RspCode": "99", "Message": "Merchant configuration unavailable"}
        return {"RspCode": "97", "Message": "Invalid signature or parameters"}
    try:
        with transaction(db):
            payment = db.scalar(select(PaymentTransaction).where(PaymentTransaction.reference == params["vnp_TxnRef"]))
            if payment is None:
                return {"RspCode": "01", "Message": "Order not found"}
            order = order_lock(db, payment.order_id)
            payment = db.scalar(select(PaymentTransaction).where(PaymentTransaction.id == payment.id).with_for_update().execution_options(populate_existing=True))
            error = validate_payment_order(provider, params, payment, order)
            if error:
                return {"RspCode": error, "Message": "Order or amount mismatch"}
            digest = hashlib.sha256(canonical(params).encode()).hexdigest()
            success = params["vnp_ResponseCode"] == "00" and params["vnp_TransactionStatus"] == "00"
            terminal_failure = params["vnp_ResponseCode"] != "00" and params["vnp_TransactionStatus"] == "02"
            desired_status = "succeeded" if success else "failed" if terminal_failure else "pending"
            gateway_id = str(int(params["vnp_TransactionNo"]))
            if payment.status != "pending":
                if (payment.status != desired_status or
                        (success and payment.provider_transaction_id != gateway_id)):
                    payment.review_required = True
                return {"RspCode": "02", "Message": "Transaction already confirmed"}
            if payment.callback_digest == digest:
                return {"RspCode": "02", "Message": "Notification already recorded"}
            payment.callback_digest = digest
            payment.response_code = params["vnp_ResponseCode"]
            payment.provider_status = params["vnp_TransactionStatus"]
            payment.verified_at = datetime.now(timezone.utc)
            if int(params["vnp_TransactionNo"]) > 0:
                payment.provider_transaction_id = gateway_id
            if success:
                try:
                    pay_date = datetime.strptime(params.get("vnp_PayDate", ""), "%Y%m%d%H%M%S").replace(tzinfo=VNP_TIMEZONE)
                    raw_date = params.get("vnp_PayDate", "")
                    bank = params.get("vnp_BankCode", "")
                    date_valid = (len(raw_date) == 14 and raw_date.isascii() and raw_date.isdigit()
                                  and 3 <= len(bank) <= 20 and bank.isascii() and bank.isalnum()
                                  and aware(payment.created_at) <= pay_date <= aware(payment.expires_at)
                                  and pay_date <= datetime.now(timezone.utc) + timedelta(minutes=5))
                except ValueError:
                    date_valid = False
                if (not date_valid or int(params["vnp_TransactionNo"]) <= 0
                        or order.status == "cancelled" or order.stock_restored
                        or order.payment_status != "unpaid"):
                    payment.review_required = True
                else:
                    payment.provider_transaction_id = gateway_id
                    payment.status = "succeeded"
                    order.payment_status = "paid"
            elif terminal_failure:
                payment.status = "failed"
            else:
                # Unknown/in-flight/suspected result cannot release inventory.
                payment.review_required = True
            db.flush()
        return {"RspCode": "00", "Message": "Confirm Success"}
    except (HTTPException, SQLAlchemyError):
        db.rollback()
        return {"RspCode": "99", "Message": "Unable to confirm transaction"}


def return_result(db, pairs):
    provider, params = checked_callback(pairs)
    payment = db.scalar(select(PaymentTransaction).where(PaymentTransaction.reference == params["vnp_TxnRef"]))
    order = None if payment is None else db.get(Order, payment.order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")
    if validate_payment_order(provider, params, payment, order):
        raise HTTPException(status_code=400, detail="Thông tin thanh toán không khớp")
    # Deliberately read-only even for a correctly signed browser return.
    return {"reference": payment.reference, "payment_status": order.payment_status,
            "transaction_status": payment.status, "message": "Trạng thái lấy từ server; return URL không xác nhận thanh toán"}
