
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.routers.auth import get_current_user


@pytest.mark.parametrize(
    "role, expected_status",
    [
        ("customer", 403),
        ("staff", 403),
        ("admin", 200),
    ],
)
def test_revenue_chat_permissions(role, expected_status):
    app.dependency_overrides[get_current_user] = (
        lambda: SimpleNamespace(
            id=1,
            role=SimpleNamespace(name=role),
        )
    )
    app.dependency_overrides[get_db] = lambda: object()

    fake_result = {
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
        "group_by": "month",
        "confirmed_payment_amount_vnd": "13814291.00",
        "confirmed_payment_order_count": 3,
        "items": [],
    }

    try:
        with patch(
            "app.routers.ai_admin.get_revenue_statistics",
            return_value=fake_result,
        ) as mock_revenue:
            with TestClient(app) as client:
                response = client.post(
                    "/admin/ai/chat",
                    json={
                        "message": (
                            "Doanh thu tháng 10/2026 là bao nhiêu?"
                        )
                    },
                )

            assert response.status_code == expected_status

            if role == "admin":
                body = response.json()
                assert body["intent"] == "revenue_statistics"
                assert "13.814.291" in body["answer"]
                assert "3 đơn hàng" in body["answer"]
                mock_revenue.assert_called_once()
            else:
                mock_revenue.assert_not_called()
    finally:
        app.dependency_overrides.clear()
