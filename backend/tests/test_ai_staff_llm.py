
from unittest.mock import patch


def test_ollama_socket_wait_is_bounded():
    with patch("app.services.ai_staff_llm.urllib.request.urlopen", side_effect=TimeoutError()) as call:
        result = understand_staff_question_with_llm("Có bao nhiêu đơn chờ xử lý?")
    assert result["field"] == "pending_orders"
    assert 0 < call.call_args.kwargs["timeout"] <= 5

from app.services.ai_staff_llm import (
    understand_staff_question_with_llm,
)


def test_llm_pending_orders():
    with patch(
        "app.services.ai_staff_llm.classify_staff_with_ollama",
        return_value={
            "intent": "order_statistics",
            "field": "pending_orders",
        },
    ):
        result = understand_staff_question_with_llm(
            "Hiện còn mấy đơn chưa xử lý?"
        )

    assert result["intent"] == "order_statistics"
    assert result["field"] == "pending_orders"


def test_llm_delivered_orders():
    with patch(
        "app.services.ai_staff_llm.classify_staff_with_ollama",
        return_value={
            "intent": "order_statistics",
            "field": "delivered_orders",
        },
    ):
        result = understand_staff_question_with_llm(
            "Đã giao thành công bao nhiêu đơn rồi?"
        )

    assert result["field"] == "delivered_orders"


def test_llm_unsupported_question():
    with patch(
        "app.services.ai_staff_llm.classify_staff_with_ollama",
        return_value={
            "intent": "unsupported",
            "message": "Chưa hỗ trợ câu hỏi này.",
        },
    ):
        result = understand_staff_question_with_llm(
            "Doanh thu tháng 10 là bao nhiêu?"
        )

    assert result["intent"] == "unsupported"


def test_ollama_timeout_fallback():
    with patch(
        "app.services.ai_staff_llm.classify_staff_with_ollama",
        side_effect=TimeoutError(),
    ):
        result = understand_staff_question_with_llm(
            "Có bao nhiêu đơn chờ xử lý?"
        )

    assert result["intent"] == "order_statistics"
    assert result["field"] == "pending_orders"


def test_empty_question():
    result = understand_staff_question_with_llm("")

    assert result["intent"] == "invalid"


def test_time_filter_not_supported():
    with patch(
        "app.services.ai_staff_llm.classify_staff_with_ollama"
    ) as mock_llm:
        result = understand_staff_question_with_llm(
            "Có bao nhiêu đơn hôm nay?"
        )

    assert result["intent"] == "unsupported"
    mock_llm.assert_not_called()


def test_order_list_not_supported():
    result = understand_staff_question_with_llm(
        "Liệt kê các đơn đang chờ xử lý"
    )

    assert result["intent"] == "unsupported"
