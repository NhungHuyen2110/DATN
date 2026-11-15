
import re
from calendar import monthrange
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.ai_staff_intent import normalize_text


VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")


def understand_time_order_question(question: str):
    """
    Trả None nếu không phải câu hỏi thời gian.
    Không truy vấn database.
    """
    text = normalize_text(question)

    # Chỉ nhận diện câu hỏi có yếu tố thời gian.
    time_words = (
        "hom nay",
        "hom qua",
        "thang nay",
        "thang truoc",
        "tuan nay",
        "tuan truoc",
    )

    month_match = re.search(
        r"\bthang\s+(\d{1,2})(?:\s*/\s*(\d{4}))?\b",
        text,
    )

    has_time = (
        month_match is not None
        or any(word in text for word in time_words)
    )

    if not has_time:
        return None

    unsupported = {
        "intent": "unsupported",
        "message": (
            "Hiện tại tôi hỗ trợ đếm đơn theo "
            "ngày hoặc tháng. Chưa hỗ trợ yêu cầu này."
        ),
    }

    if not re.search(r"\bdon(?:\s+hang)?\b", text):
        return unsupported

    # Không tự diễn giải câu hỏi liệt kê,
    # thanh toán, doanh thu hoặc nhiều yêu cầu.
    forbidden = (
        "liet ke",
        "danh sach",
        "don nao",
        "ma don",
        "chua thanh toan",
        "da thanh toan",
        "doanh thu",
        "tuan nay",
        "tuan truoc",
    )

    if any(word in text for word in forbidden):
        return unsupported

    today = datetime.now(VIETNAM).date()

    if "hom nay" in text:
        start_date = end_date = today

    elif "hom qua" in text:
        start_date = end_date = today - timedelta(days=1)

    else:
        month = today.month
        year = today.year

        if "thang truoc" in text:
            previous = today.replace(day=1) - timedelta(days=1)
            month, year = previous.month, previous.year

        elif month_match:
            month = int(month_match.group(1))
            year = int(month_match.group(2) or today.year)

        elif "thang nay" not in text:
            return unsupported

        if not 1 <= month <= 12 or not 2000 <= year <= 2100:
            return {
                "intent": "invalid",
                "message": "Tháng hoặc năm không hợp lệ.",
            }

        start_date = date(year, month, 1)
        end_date = date(
            year, month, monthrange(year, month)[1]
        )

    status = None

    if any(
        word in text
        for word in ("cho xu ly", "chua xu ly", "pending")
    ):
        status = "pending"

    elif any(
        word in text
        for word in ("da xac nhan", "confirmed")
    ):
        status = "confirmed"

    elif any(
        word in text
        for word in ("da giao", "delivered")
    ):
        status = "delivered"

    return {
        "intent": "orders_by_period",
        "start_date": start_date,
        "end_date": end_date,
        "status": status,
    }
