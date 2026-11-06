"""Configurable, deterministic shipping policy. Default keeps existing free-shipping behavior."""

from decimal import Decimal
import os


def shipping_policy():
    raw_fee = os.getenv("SHIPPING_FLAT_VND", "0")
    raw_free_from = os.getenv("SHIPPING_FREE_FROM_VND", "2000000")
    try:
        fee = Decimal(raw_fee)
        free_from = Decimal(raw_free_from)
        if not fee.is_finite() or not free_from.is_finite() or fee < 0 or free_from < 0:
            raise ValueError("Invalid shipping policy")
        if fee != fee.to_integral_value() or free_from != free_from.to_integral_value():
            raise ValueError("VND fee must be an integer")
        if fee > 1000000 or free_from > 1000000000000:
            raise ValueError("Shipping policy exceeds allowed limits")
    except (ValueError, ArithmeticError):
        raise ValueError("Invalid SHIPPING_FLAT_VND or SHIPPING_FREE_FROM_VND") from None
    return fee, free_from


def calculate_shipping(subtotal):
    fee, free_from = shipping_policy()
    return Decimal("0.00") if subtotal >= free_from else fee


def public_shipping_policy():
    fee, free_from = shipping_policy()
    return {"flat_fee_vnd": str(fee), "free_from_vnd": str(free_from)}
