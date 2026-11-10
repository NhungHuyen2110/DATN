
from unittest.mock import patch

from app.services.ai_admin_llm import (
    understand_admin_question_with_llm,
)


def test_existing_question_still_works():
    with patch(
        "app.services.ai_admin_llm.classify_with_ollama"
    ) as mock_llm:
        result = understand_admin_question_with_llm(
            "Top 5 sản phẩm bán chạy tháng 10/2026"
        )

    assert result["intent"] == "top_selling_products"
    assert result["limit"] == 5
    assert result["start_date"].month == 10

    # Câu hỏi cũ không cần gọi LLM.
    mock_llm.assert_not_called()


def test_llm_understands_new_phrase():
    with patch(
        "app.services.ai_admin_llm.classify_with_ollama",
        return_value="top_selling_products",
    ):
        result = understand_admin_question_with_llm(
            "Mặt hàng nào được mua nhiều nhất "
            "tháng 10/2026?"
        )

    assert result["intent"] == "top_selling_products"
    assert result["start_date"].year == 2026
    assert result["start_date"].month == 10


def test_unsupported_question():
    with patch(
        "app.services.ai_admin_llm.classify_with_ollama",
        return_value="unsupported",
    ):
        result = understand_admin_question_with_llm(
            "Doanh thu hôm nay là bao nhiêu?"
        )

    assert result["intent"] == "unsupported"


def test_ollama_failure_keeps_fallback():
    with patch(
        "app.services.ai_admin_llm.classify_with_ollama",
        side_effect=TimeoutError(),
    ):
        result = understand_admin_question_with_llm(
            "Mặt hàng nào được mua nhiều nhất?"
        )

    assert result["intent"] == "unsupported"
