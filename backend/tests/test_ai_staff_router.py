
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.routers.ai_staff import router


@pytest.mark.parametrize(
    "role, expected_status",
    [
        ("customer", 403),
        ("staff", 200),
        ("admin", 200),
    ],
)
def test_staff_ai_permissions(role, expected_status):
    app = FastAPI()
    app.include_router(router)

    fake_user = SimpleNamespace(
        id=1,
        role=SimpleNamespace(name=role),
    )

    app.dependency_overrides[get_current_user] = (
        lambda: fake_user
    )
    app.dependency_overrides[get_db] = lambda: object()

    fake_result = {
        "total_orders": 9,
        "order_status": {
            "delivered": 4,
            "pending": 3,
            "confirmed": 2,
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

    try:
        with patch(
            "app.routers.ai_staff.get_order_statistics",
            return_value=fake_result,
        ) as mock_service:
            with TestClient(app) as client:
                response = client.get(
                    "/staff/ai/order-statistics"
                )

            assert response.status_code == expected_status

            if role in {"staff", "admin"}:
                assert response.json()["total_orders"] == 9
                mock_service.assert_called_once()
            else:
                mock_service.assert_not_called()

    finally:
        app.dependency_overrides.clear()


def test_staff_ai_requires_login():
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.get(
            "/staff/ai/order-statistics"
        )

    assert response.status_code in (401, 403)
