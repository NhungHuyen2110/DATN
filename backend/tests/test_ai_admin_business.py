
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.ai_admin_business import (
    get_revenue_statistics,
)


def test_revenue_statistics():
    db = MagicMock()

    fake_revenue = SimpleNamespace(
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 31),
        group_by="month",
        confirmed_payment_amount_vnd=Decimal(
            "13814291.00"
        ),
        confirmed_payment_order_count=3,
        items=[
            SimpleNamespace(
                period_start=date(2026, 10, 1),
                confirmed_payment_amount_vnd=Decimal(
                    "13814291.00"
                ),
                confirmed_payment_order_count=3,
            )
        ],
    )

    with patch(
        "app.services.ai_admin_business.revenue",
        return_value=fake_revenue,
    ) as mock_revenue:
        result = get_revenue_statistics(
            db=db,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            group_by="month",
        )

    assert (
        result["confirmed_payment_amount_vnd"]
        == "13814291.00"
    )
    assert result["confirmed_payment_order_count"] == 3
    assert len(result["items"]) == 1

    mock_revenue.assert_called_once_with(
        db=db,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 31),
        group_by="month",
    )


def test_invalid_group_by():
    with pytest.raises(HTTPException) as error:
        get_revenue_statistics(
            db=MagicMock(),
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            group_by="year",
        )

    assert error.value.status_code == 422


def test_invalid_date_range():
    with pytest.raises(HTTPException) as error:
        get_revenue_statistics(
            db=MagicMock(),
            start_date=date(2026, 11, 1),
            end_date=date(2026, 10, 1),
        )

    assert error.value.status_code == 422


def test_no_confirmed_payments():
    fake_revenue = SimpleNamespace(
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 31),
        group_by="month",
        confirmed_payment_amount_vnd=Decimal("0"),
        confirmed_payment_order_count=0,
        items=[],
    )

    with patch(
        "app.services.ai_admin_business.revenue",
        return_value=fake_revenue,
    ):
        result = get_revenue_statistics(
            db=MagicMock(),
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
        )

    assert result["confirmed_payment_amount_vnd"] == "0"
    assert result["confirmed_payment_order_count"] == 0
    assert result["items"] == []
