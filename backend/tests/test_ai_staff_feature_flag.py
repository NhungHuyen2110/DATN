
from types import SimpleNamespace
from unittest.mock import patch
from urllib import response

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
    "enabled,expected_field",
    [
        (False, None),
        (True, "pending_orders"),
    ],
)

def test_staff_llm_feature_flag(enabled, expected_field):
    app.dependency_overrides[get_current_user] = (
        lambda: SimpleNamespace(
            id=1,
            role=SimpleNamespace(name="staff"),
        )
    )
    app.dependency_overrides[get_db] = lambda: object()

    try:
        with (
            patch.dict(
                "os.environ",
                {
                    "STAFF_AI_LLM_ENABLED": (
                        "true" if enabled else "false"
                    )
                },
            ),
            patch(
                "app.routers.ai_staff."
                "understand_staff_question_with_llm",
                return_value={
                    "intent": "order_statistics",
                    "field": "pending_orders",
                },
            ) as mock_llm,
            patch(
                "app.routers.ai_staff.get_order_statistics",
                return_value=FAKE_RESULT,
            ) as mock_data,
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/staff/ai/chat",
                    json={
                        "message": "Tình hình công việc thế nào?"
                    },
                )

        assert response.status_code == 200

        body = response.json()

        if enabled:
            # Khi bật LLM, câu hỏi được nhận diện
            # là thống kê đơn đang chờ xử lý.
            assert body["intent"] == "order_statistics"
            assert body["field"] == "pending_orders"

            mock_llm.assert_called_once()
            mock_data.assert_called_once()

        else:
            # Khi tắt LLM, hệ thống dùng bộ nhận diện cũ.
            # Câu hỏi này chưa được hỗ trợ.
            assert body["intent"] == "unsupported"
            assert body["data"] is None

            mock_llm.assert_not_called()
            mock_data.assert_not_called()
    finally:
        app.dependency_overrides.clear()
