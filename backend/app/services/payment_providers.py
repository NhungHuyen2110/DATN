"""Provider interface and VNPay 2.1.0 Sandbox adapter. No outbound requests."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import hashlib
import hmac
import ipaddress
import os
import re
from typing import Protocol
from urllib.parse import urlencode, urlsplit

from fastapi import HTTPException


SANDBOX_URL = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
VNP_TIMEZONE = timezone(timedelta(hours=7))


def canonical(params):
    return urlencode(sorted((key, str(value)) for key, value in params.items() if value != ""))


class PaymentProvider(Protocol):
    merchant: str
    return_url: str
    def amount_units(self, amount: Decimal) -> str: ...
    def payment_url(self, transaction) -> str: ...
    def verify(self, pairs) -> dict[str, str]: ...


@dataclass(frozen=True)
class VNPaySandbox:
    merchant: str
    secret: str = field(repr=False)
    return_url: str

    @classmethod
    def from_environment(cls):
        merchant = os.getenv("VNPAY_TMN_CODE", "")
        secret = os.getenv("VNPAY_HASH_SECRET", "")
        return_url = os.getenv("VNPAY_RETURN_URL", "")
        try:
            parsed = urlsplit(return_url)
        except ValueError:
            raise HTTPException(status_code=503, detail="VNPay Sandbox chưa được cấu hình hợp lệ") from None
        if (os.getenv("VNPAY_ENABLED", "false").lower() != "true"
                or not re.fullmatch(r"[A-Za-z0-9]{8}", merchant) or not secret
                or parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment or len(return_url) > 255
                or parsed.path != "/payments/vnpay/return"):
            raise HTTPException(status_code=503, detail="VNPay Sandbox chưa được cấu hình hợp lệ")
        return cls(merchant, secret, return_url)

    def sign(self, params):
        return hmac.new(self.secret.encode(), canonical(params).encode(), hashlib.sha512).hexdigest()

    @staticmethod
    def amount_units(amount):
        with localcontext() as context:
            context.prec = 50
            units = amount * 100
            if (not units.is_finite() or units <= 0 or units != units.to_integral_value()
                    or units >= Decimal(10) ** 12):
                raise HTTPException(status_code=422, detail="Số tiền vượt giới hạn VNPay Sandbox")
            return str(int(units))

    def payment_url(self, transaction):
        ipaddress.ip_address(transaction.client_ip)
        params = {
            "vnp_Version": "2.1.0", "vnp_Command": "pay", "vnp_TmnCode": transaction.merchant_code,
            "vnp_Amount": self.amount_units(transaction.amount_vnd), "vnp_CurrCode": "VND",
            "vnp_TxnRef": transaction.reference, "vnp_OrderInfo": "Thanh toan don hang " + str(transaction.order_id),
            "vnp_OrderType": "other", "vnp_Locale": "vn", "vnp_ReturnUrl": transaction.return_url,
            "vnp_IpAddr": transaction.client_ip,
            "vnp_CreateDate": aware(transaction.created_at).astimezone(VNP_TIMEZONE).strftime("%Y%m%d%H%M%S"),
            "vnp_ExpireDate": aware(transaction.expires_at).astimezone(VNP_TIMEZONE).strftime("%Y%m%d%H%M%S"),
        }
        return SANDBOX_URL + "?" + canonical(params) + "&vnp_SecureHash=" + self.sign(params)

    def verify(self, pairs):
        if len(pairs) > 40:
            raise ValueError("Too many callback parameters")
        params = {}
        for key, value in pairs:
            if not key.startswith("vnp_") or key in params or len(key) > 64 or len(value) > 2048:
                raise ValueError("Invalid or duplicate callback parameters")
            params[key] = value
        supplied = params.pop("vnp_SecureHash", "")
        params.pop("vnp_SecureHashType", None)
        if (not re.fullmatch(r"[a-fA-F0-9]{128}", supplied)
                or not hmac.compare_digest(supplied.lower(), self.sign(params))):
            raise ValueError("Invalid signature")
        required = ("vnp_TxnRef", "vnp_TmnCode", "vnp_Amount", "vnp_ResponseCode", "vnp_TransactionStatus", "vnp_TransactionNo", "vnp_OrderInfo")
        if any(not params.get(key) for key in required) or params["vnp_TmnCode"] != self.merchant:
            raise ValueError("Invalid callback fields")
        for key, pattern in (
            ("vnp_Amount", r"[0-9]{1,12}"), ("vnp_TxnRef", r"[A-Za-z0-9]{1,100}"),
            ("vnp_ResponseCode", r"[0-9]{2}"), ("vnp_TransactionStatus", r"[0-9]{2}"),
            ("vnp_TransactionNo", r"[0-9]{1,15}"),
        ):
            if not re.fullmatch(pattern, params[key]):
                raise ValueError("Invalid callback format")
        return params


def aware(value):
    # PostgreSQL returns aware timestamps; this fallback supports in-memory tests.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def get_provider(name="vnpay") -> PaymentProvider:
    # Add a MoMo adapter here only after its own protocol and credentials are ready.
    if name != "vnpay":
        raise HTTPException(status_code=503, detail="Phương thức thanh toán chưa được tích hợp")
    return VNPaySandbox.from_environment()
