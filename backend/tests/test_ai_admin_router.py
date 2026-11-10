
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.ai_admin import router


def test_admin_ai_endpoint_requires_authentication():
    app = FastAPI()
    app.include_router(router)

    client = TestClient(app)

    response = client.get(
        "/admin/ai/top-selling-products",
        params={
            "start_date": "2026-10-01",
            "end_date": "2026-10-31",
            "limit": 5,
        },
    )

    assert response.status_code in (401, 403)


from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.services.ai_admin_analytics import get_top_selling_products


@pytest.mark.parametrize(
    "role, expected_status",
    [
        ("customer", 403),
        ("staff", 403),
        ("admin", 200),
    ],
)
def test_admin_ai_role_permissions(role, expected_status):
    app = FastAPI()
    app.include_router(router)

    fake_user = SimpleNamespace(
        id=1,
        role=SimpleNamespace(name=role),
    )

    fake_db = MagicMock()

    app.dependency_overrides[get_current_user] = (
        lambda: fake_user
    )
    app.dependency_overrides[get_db] = (
        lambda: fake_db
    )

    # Chỉ giả lập dữ liệu thống kê, không truy vấn PostgreSQL.
    from app.routers import ai_admin

    original_service = ai_admin.get_top_selling_products

    def fake_service(**kwargs):
        return {
            "start_date": "2026-10-01",
            "end_date": "2026-10-31",
            "metric": "confirmed_payment_sales",
            "items": [],
        }

    ai_admin.get_top_selling_products = fake_service

    try:
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
            assert response.json()["items"] == []
    finally:
        ai_admin.get_top_selling_products = original_service
        app.dependency_overrides.clear()
