
import re
from datetime import date, timedelta
from calendar import monthrange
from zoneinfo import ZoneInfo
from datetime import datetime


VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")


def understand_admin_question(question: str):
    """
    Nhận diện ý định truy vấn thống kê.
    Đây là bộ phân tích quy tắc ban đầu,
    chưa phải mô hình LLM.
    """
    text = question.strip().lower()

    if not text:
        return {
            "intent": "invalid",
            "message": "Vui lòng nhập câu hỏi."
        }

    selling_keywords = [
        "bán chạy",
        "bán nhiều nhất",
        "bán tốt nhất",
        "top sản phẩm",
        "sản phẩm bán nhiều",
    ]

    if not any(word in text for word in selling_keywords):
        return {
            "intent": "unsupported",
            "message": (
                "Hiện tại tôi hỗ trợ thống kê "
                "sản phẩm bán chạy. Các chức năng "
                "AI khác đang được bổ sung."
            )
        }

    today = datetime.now(VIETNAM).date()
    year = today.year
    month = today.month

    # Nhận diện tháng cụ thể: tháng 10/2026
    match = re.search(
        r"tháng\s+(\d{1,2})(?:\s*/\s*(\d{4}))?",
        text
    )

    if match:
        month = int(match.group(1))
        year = int(match.group(2) or today.year)

        if not 1 <= month <= 12:
            return {
                "intent": "invalid",
                "message": "Tháng phải từ 1 đến 12."
            }

        if year < 2000 or year > 2100:
            return {
                "intent": "invalid",
                "message": "Năm không hợp lệ."
            }

    elif "tháng trước" in text:
        previous = today.replace(day=1) - timedelta(days=1)
        month = previous.month
        year = previous.year

    # Nhận diện top 3, top 5, top 10...
    top_match = re.search(r"\btop\s+(\d+)", text)
    limit = int(top_match.group(1)) if top_match else 5

    if not 1 <= limit <= 20:
        return {
            "intent": "invalid",
            "message": "Số lượng top phải từ 1 đến 20."
        }

    last_day = monthrange(year, month)[1]

    return {
        "intent": "top_selling_products",
        "start_date": date(year, month, 1),
        "end_date": date(year, month, last_day),
        "limit": limit,
    }
