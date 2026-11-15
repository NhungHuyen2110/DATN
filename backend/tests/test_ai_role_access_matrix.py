
from types import SimpleNamespace
import importlib

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.auth import get_current_user
from app.core.database import get_db


admin_router = importlib.import_module(
    "app.routers.ai_admin"
)
staff_router = importlib.import_module(
    "app.routers.ai_staff"
)


def fake_user(role):
    return SimpleNamespace(
        id=1,
        role=SimpleNamespace(name=role),
    )


def fake_chat_response(*args, **kwargs):
    return {
        "intent": "multi_intent",
        "answer": "Kết quả kiểm thử AI.",
        "tools_used": ["inventory"],
        "data": {},
    }


@pytest.mark.parametrize(
    "role,endpoint,expected",
    [
        (None, "/staff/ai/chat", 401),
        (None, "/admin/ai/chat", 401),
        ("customer", "/staff/ai/chat", 403),
        ("customer", "/admin/ai/chat", 403),
        ("staff", "/staff/ai/chat", 200),
        ("staff", "/admin/ai/chat", 403),
        ("admin", "/staff/ai/chat", 200),
        ("admin", "/admin/ai/chat", 200),
    ],
)
def test_ai_role_access(
    monkeypatch,
    role,
    endpoint,
    expected,
):
    # Không dùng PostgreSQL thật trong bài test.
    app.dependency_overrides.clear()

    app.dependency_overrides[get_db] = (
        lambda: object()
    )

    # Giả lập kết quả AI, nhưng giữ nguyên
    # dependency admin/staff_or_admin thật.
    monkeypatch.setattr(
        admin_router,
        "answer_admin_multi_intent",
        fake_chat_response,
    )

    monkeypatch.setattr(
        staff_router,
        "answer_staff_multi_intent",
        fake_chat_response,
    )

    if role is not None:
        app.dependency_overrides[get_current_user] = (
            lambda: fake_user(role)
        )

    try:
        with TestClient(app) as client:
            response = client.post(
                endpoint,
                json={
                    "message": (
                        "Có bao nhiêu đơn hàng chờ xử lý "
                        "và sản phẩm nào sắp hết hàng?"
                    )
                },
            )

        assert response.status_code == expected, (
            f"Role={role}, endpoint={endpoint}: "
            f"expected={expected}, "
            f"actual={response.status_code}, "
            f"body={response.text}"
        )

        if expected == 200:
            assert (
                response.json()["intent"]
                == "multi_intent"
            )

    finally:
        app.dependency_overrides.clear()
