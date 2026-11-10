
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.routers.auth import get_current_user


def test_admin_llm_feature_flag():
    fake_admin = SimpleNamespace(
        id=1,
        role=SimpleNamespace(name="admin"),
    )

    app.dependency_overrides[get_current_user] = (
        lambda: fake_admin
    )
    app.dependency_overrides[get_db] = (
        lambda: object()
    )

    try:
        with (
            patch.dict(
                "os.environ",
                {"ADMIN_AI_LLM_ENABLED": "true"},
            ),
            patch(
                "app.routers.ai_admin.understand_admin_question_with_llm",
                return_value={
                    "intent": "top_selling_products",
                    "start_date": date(2026, 10, 1),
                    "end_date": date(2026, 10, 31),
                    "limit": 5,
                },
            ) as mock_llm,
            patch(
                "app.routers.ai_admin.get_top_selling_products",
                return_value={
                    "start_date": "2026-10-01",
                    "end_date": "2026-10-31",
                    "metric": "confirmed_payment_sales",
                    "items": [],
                },
            ) as mock_data,
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/admin/ai/chat",
                    json={
                        "message": (
                            "Mặt hàng nào được mua nhiều nhất "
                            "tháng 10/2026?"
                        )
                    },
                )

            assert response.status_code == 200
            assert (
                response.json()["intent"]
                == "top_selling_products"
            )
            mock_llm.assert_called_once()
            mock_data.assert_called_once()

    finally:
        app.dependency_overrides.clear()
