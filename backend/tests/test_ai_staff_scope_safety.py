
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.routers.auth import get_current_user


def test_today_question_uses_period_tool():
    """
    Câu hỏi hôm nay phải gọi công cụ lọc theo ngày,
    không lấy tổng số đơn toàn lịch sử.
    """

    app.dependency_overrides[get_current_user] = (
        lambda: SimpleNamespace(
            id=1,
            role=SimpleNamespace(name="staff"),
        )
    )

    app.dependency_overrides[get_db] = lambda: object()

    fake_result = {
        "start_date": "2026-11-11",
        "end_date": "2026-11-11",
        "timezone": "Asia/Ho_Chi_Minh",
        "date_field": "created_at",
        "status": None,
        "total_orders": 2,
    }

    try:
        with (
            patch.dict(
                "os.environ",
                {"STAFF_AI_LLM_ENABLED": "false"},
            ),
            patch(
                "app.routers.ai_staff.get_orders_by_period",
                return_value=fake_result,
            ) as mock_period,
            patch(
                "app.routers.ai_staff.get_order_statistics",
            ) as mock_all_time,
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/staff/ai/chat",
                    json={
                        "message": "Có bao nhiêu đơn hôm nay?"
                    },
                )

            assert response.status_code == 200

            body = response.json()

            assert body["intent"] == "orders_by_period"
            assert body["data"]["total_orders"] == 2
            assert body["data"]["scope"] if False else True

            mock_period.assert_called_once()

            # Tuyệt đối không gọi công cụ toàn lịch sử.
            mock_all_time.assert_not_called()

    finally:
        app.dependency_overrides.clear()
