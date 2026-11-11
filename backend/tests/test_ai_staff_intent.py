
import pytest

from app.services.ai_staff_intent import (
    understand_staff_question,
)


@pytest.mark.parametrize(
    "question, expected_field",
    [
        ("Có bao nhiêu đơn hàng?", "total_orders"),
        ("Có bao nhiêu đơn chờ xử lý?", "pending_orders"),
        ("Đơn nào đã xác nhận?", "confirmed_orders"),
        ("Có bao nhiêu đơn đã giao?", "delivered_orders"),
        ("Bao nhiêu đơn chưa thanh toán?", "unpaid_orders"),
        ("Bao nhiêu đơn đã thanh toán?", "paid_orders"),
    ],
)
def test_staff_intent(question, expected_field):
    result = understand_staff_question(question)

    assert result["intent"] == "order_statistics"
    assert result["field"] == expected_field


def test_unsupported_question():
    result = understand_staff_question(
        "Sản phẩm nào bán chạy nhất?"
    )

    assert result["intent"] == "unsupported"


def test_empty_question():
    result = understand_staff_question("")

    assert result["intent"] == "invalid"
