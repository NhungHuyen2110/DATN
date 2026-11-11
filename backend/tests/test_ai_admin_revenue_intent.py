
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.ai_admin_revenue_intent import (
    understand_revenue_question,
)


def test_revenue_specific_month():
    result = understand_revenue_question(
        "Doanh thu tháng 10/2026 là bao nhiêu?"
    )

    assert result["intent"] == "revenue_statistics"
    assert result["start_date"] == date(2026, 10, 1)
    assert result["end_date"] == date(2026, 10, 31)
    assert result["group_by"] == "month"


def test_revenue_today():
    today = datetime.now(
        ZoneInfo("Asia/Ho_Chi_Minh")
    ).date()

    result = understand_revenue_question(
        "Doanh thu hôm nay bao nhiêu?"
    )

    assert result["intent"] == "revenue_statistics"
    assert result["start_date"] == today
    assert result["end_date"] == today
    assert result["group_by"] == "day"


def test_invalid_month():
    result = understand_revenue_question(
        "Doanh thu tháng 15/2026"
    )

    assert result["intent"] == "invalid"


def test_unrelated_question():
    result = understand_revenue_question(
        "Top 5 sản phẩm bán chạy tháng 10/2026"
    )

    assert result["intent"] == "unsupported"


def test_revenue_previous_month():
    today = datetime.now(
        ZoneInfo("Asia/Ho_Chi_Minh")
    ).date()
    previous = today.replace(day=1) - timedelta(days=1)

    result = understand_revenue_question(
        "Doanh thu tháng trước"
    )

    assert result["intent"] == "revenue_statistics"
    assert result["start_date"] == previous.replace(day=1)
    assert result["end_date"] == previous


def test_combined_question_not_silently_answered():
    result = understand_revenue_question(
        "Doanh thu và sản phẩm bán chạy tháng 10/2026?"
    )

    assert result["intent"] == "unsupported"
