
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.routers.auth import get_current_user


@pytest.mark.parametrize(
    "role,expected_status",
    [
        ("customer", 403),
        ("staff", 403),
        ("admin", 200),
    ],
)
def test_ai_admin_in_main_app(role, expected_status):
    fake_user = SimpleNamespace(
        id=1,
        role=SimpleNamespace(name=role),
    )

    def fake_db():
        yield object()

    def fake_analytics(**kwargs):
        return {
            "start_date": "2026-10-01",
            "end_date": "2026-10-31",
            "metric": "confirmed_payment_sales",
            "items": [],
        }

    app.dependency_overrides[get_current_user] = (
        lambda: fake_user
    )
    app.dependency_overrides[get_db] = fake_db

    try:
        with patch(
            "app.routers.ai_admin.get_top_selling_products",
            side_effect=fake_analytics,
        ):
            with TestClient(app) as client:
                response = client.get(
                    "/admin/ai/top-selling-products",
                    params={
                        "start_date": "2026-10-01",
                        "end_date": "2026-10-31",
                        "limit": 5,
                    },
                )

        assert response.status_code == expected_status

        if role == "admin":
            assert response.json()["metric"] == (
                "confirmed_payment_sales"
            )
    finally:
        app.dependency_overrides.clear()
