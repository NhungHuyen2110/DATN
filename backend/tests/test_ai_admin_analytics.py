
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.ai_admin_analytics import get_top_selling_products


def test_top_selling_products():
    db = MagicMock()

    payments = [
        {
            "id": 1,
            "payment_status": "paid",
            "status": "delivered",
            "candidate_count": 1,
            "succeeded_count": 1,
            "review_count": 0,
            "amount_mismatch": 0,
            "provider_mismatch": 0,
            "missing_verified": 0,
        },
        {
            "id": 2,
            "payment_status": "paid",
            "status": "cancelled",
            "candidate_count": 1,
            "succeeded_count": 1,
            "review_count": 0,
            "amount_mismatch": 0,
            "provider_mismatch": 0,
            "missing_verified": 0,
        },
    ]

    items = [
        SimpleNamespace(
            product_id=10,
            product_name="Nhẫn bạc",
            quantity=3,
            line_total_vnd=Decimal("900000"),
        ),
        SimpleNamespace(
            product_id=20,
            product_name="Dây chuyền",
            quantity=2,
            line_total_vnd=Decimal("1200000"),
        ),
    ]

    db.execute.return_value.mappings.return_value.all.return_value = payments
    db.scalars.return_value.all.return_value = items

    result = get_top_selling_products(
        db,
        date(2026, 10, 1),
        date(2026, 10, 31),
        limit=5,
    )

    assert len(result["items"]) == 2
    assert result["items"][0]["product_name"] == "Nhẫn bạc"
    assert result["items"][0]["quantity_sold"] == 3
    assert result["items"][1]["product_name"] == "Dây chuyền"


def test_invalid_date_range():
    with pytest.raises(HTTPException) as error:
        get_top_selling_products(
            MagicMock(),
            date(2026, 11, 1),
            date(2026, 10, 1),
        )

    assert error.value.status_code == 422


def test_invalid_limit():
    with pytest.raises(HTTPException) as error:
        get_top_selling_products(
            MagicMock(),
            date(2026, 10, 1),
            date(2026, 10, 31),
            limit=100,
        )

    assert error.value.status_code == 422


def test_cancelled_orders_are_excluded():
    from app.services.dashboard import classify

    valid_payment = {
        "id": 1,
        "payment_status": "paid",
        "status": "delivered",
        "candidate_count": 1,
        "succeeded_count": 1,
        "review_count": 0,
        "amount_mismatch": 0,
        "provider_mismatch": 0,
        "missing_verified": 0,
    }

    cancelled_payment = {
        **valid_payment,
        "id": 2,
        "status": "cancelled",
    }

    valid, valid_reasons = classify(valid_payment)
    cancelled, cancelled_reasons = classify(cancelled_payment)

    assert valid is True
    assert valid_reasons == []

    assert cancelled is False
    assert (
        "cancelled_order_with_successful_transaction"
        in cancelled_reasons
    )


def test_cancelled_order_items_not_counted():
    db = MagicMock()

    payments = [
        {
            "id": 1,
            "payment_status": "paid",
            "status": "delivered",
            "candidate_count": 1,
            "succeeded_count": 1,
            "review_count": 0,
            "amount_mismatch": 0,
            "provider_mismatch": 0,
            "missing_verified": 0,
        },
        {
            "id": 2,
            "payment_status": "paid",
            "status": "cancelled",
            "candidate_count": 1,
            "succeeded_count": 1,
            "review_count": 0,
            "amount_mismatch": 0,
            "provider_mismatch": 0,
            "missing_verified": 0,
        },
    ]

    valid_item = SimpleNamespace(
        order_id=1,
        product_id=10,
        product_name="Nhẫn bạc",
        quantity=3,
        line_total_vnd=Decimal("900000"),
    )

    cancelled_item = SimpleNamespace(
        order_id=2,
        product_id=20,
        product_name="Dây chuyền",
        quantity=100,
        line_total_vnd=Decimal("50000000"),
    )

    db.execute.return_value.mappings.return_value.all.return_value = payments

    # Giả lập DB chỉ trả sản phẩm thuộc đơn hợp lệ.
    db.scalars.return_value.all.return_value = [valid_item]

    result = get_top_selling_products(
        db,
        date(2026, 10, 1),
        date(2026, 10, 31),
    )

    assert len(result["items"]) == 1
    assert result["items"][0]["product_name"] == "Nhẫn bạc"
    assert result["items"][0]["quantity_sold"] == 3

    # Xác nhận truy vấn lọc order_id, không lấy toàn bộ sản phẩm.
    query = db.scalars.call_args.args[0]
    compiled = query.compile()
    assert "order_items.order_id IN" in str(compiled)
    assert compiled.params["order_id_1"] == [1]
