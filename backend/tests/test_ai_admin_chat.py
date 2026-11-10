
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
def test_admin_chat_permissions(role, expected_status):
    fake_user = SimpleNamespace(
        id=1,
        role=SimpleNamespace(name=role),
    )

    app.dependency_overrides[get_current_user] = (
        lambda: fake_user
    )
    app.dependency_overrides[get_db] = (
        lambda: object()
    )

    fake_result = {
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
        "metric": "confirmed_payment_sales",
        "items": [
            {
                "product_id": 1,
                "product_name": "Bông tai Angel",
                "quantity_sold": 2,
                "gross_item_value_vnd": "11194652.00",
            }
        ],
    }

    try:
        with patch(
            "app.routers.ai_admin.get_top_selling_products",
            return_value=fake_result,
        ) as mock_service:
            with TestClient(app) as client:
                response = client.post(
                    "/admin/ai/chat",
                    json={
                        "message": (
                            "Top 5 sản phẩm bán chạy "
                            "tháng 10/2026"
                        )
                    },
                )

            assert response.status_code == expected_status

            if role == "admin":
                body = response.json()
                assert "Bông tai Angel" in body["answer"]
                assert body["intent"] == "top_selling_products"
                mock_service.assert_called_once()
            else:
                mock_service.assert_not_called()

    finally:
        app.dependency_overrides.clear()
