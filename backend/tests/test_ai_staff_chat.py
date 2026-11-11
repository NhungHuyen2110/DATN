
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.routers.auth import get_current_user


FAKE_RESULT = {
    "total_orders": 9,
    "order_status": {
        "pending": 3,
        "confirmed": 2,
        "delivered": 4,
    },
    "payment_status": {
        "unpaid": 5,
        "paid": 4,
    },
    "pending_orders": 3,
    "confirmed_orders": 2,
    "delivered_orders": 4,
    "scope": "all_time",
}


@pytest.mark.parametrize(
    "role, expected_status",
    [
        ("customer", 403),
        ("staff", 200),
        ("admin", 200),
    ],
)
def test_staff_chat_permissions(role, expected_status):
    app.dependency_overrides[get_current_user] = (
        lambda: SimpleNamespace(
            id=1,
            role=SimpleNamespace(name=role),
        )
    )
    app.dependency_overrides[get_db] = lambda: object()

    try:
        with patch(
            "app.routers.ai_staff.get_order_statistics",
            return_value=FAKE_RESULT,
        ) as mock_service:
            with TestClient(app) as client:
                response = client.post(
                    "/staff/ai/chat",
                    json={
                        "message": (
                            "Có bao nhiêu đơn chờ xử lý?"
                        )
                    },
                )

            assert response.status_code == expected_status

            if role in {"staff", "admin"}:
                body = response.json()

                assert body["intent"] == "order_statistics"
                assert body["field"] == "pending_orders"
                assert "3 đơn" in body["answer"]

                mock_service.assert_called_once()
            else:
                mock_service.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "message,field,value",
    [
        ("Có bao nhiêu đơn hàng?", "total_orders", 9),
        ("Có bao nhiêu đơn đã giao?", "delivered_orders", 4),
        ("Bao nhiêu đơn chưa thanh toán?", "unpaid_orders", 5),
        ("Bao nhiêu đơn đã thanh toán?", "paid_orders", 4),
    ],
)
def test_staff_chat_statistics(message, field, value):
    app.dependency_overrides[get_current_user] = (
        lambda: SimpleNamespace(
            id=1,
            role=SimpleNamespace(name="staff"),
        )
    )
    app.dependency_overrides[get_db] = lambda: object()

    try:
        with patch(
            "app.routers.ai_staff.get_order_statistics",
            return_value=FAKE_RESULT,
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/staff/ai/chat",
                    json={"message": message},
                )

        assert response.status_code == 200
        assert response.json()["field"] == field
        assert response.json()["data"]["value"] == value
    finally:
        app.dependency_overrides.clear()
