
import re
from calendar import monthrange
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")


def understand_revenue_question(question: str):
    """
    Nhận diện câu hỏi doanh thu của Admin.

    Chỉ phân tích ý định và khoảng thời gian.
    Không truy cập PostgreSQL.
    """

    text = question.strip().lower()

    keywords = (
        "doanh thu",
        "tổng tiền bán hàng",
        "tiền bán hàng",
    )

    if not any(keyword in text for keyword in keywords):
        return {"intent": "unsupported"}

    # Chưa hỗ trợ câu hỏi kết hợp nhiều nghiệp vụ.
    if any(
        keyword in text
        for keyword in (
            "sản phẩm bán chạy",
            "sản phẩm nào",
            "mặt hàng nào",
            "tồn kho",
            "đơn chờ",
        )
    ):
        return {
            "intent": "unsupported",
            "message": (
                "Hiện tại vui lòng hỏi doanh thu và "
                "các thống kê khác thành từng câu riêng."
            ),
        }

    today = datetime.now(VIETNAM).date()

    if "hôm nay" in text:
        start_date = today
        end_date = today
        group_by = "day"

    elif "hôm qua" in text:
        yesterday = today - timedelta(days=1)
        start_date = yesterday
        end_date = yesterday
        group_by = "day"

    else:
        month = today.month
        year = today.year

        if "tháng trước" in text:
            previous = today.replace(day=1) - timedelta(days=1)
            month = previous.month
            year = previous.year

        else:
            match = re.search(
                r"tháng\s+(\d{1,2})"
                r"(?:\s*/\s*(\d{4}))?",
                text,
            )

            if match:
                month = int(match.group(1))
                year = int(match.group(2) or today.year)

                if not 1 <= month <= 12:
                    return {
                        "intent": "invalid",
                        "message": "Tháng phải từ 1 đến 12.",
                    }

                if not 2000 <= year <= 2100:
                    return {
                        "intent": "invalid",
                        "message": "Năm không hợp lệ.",
                    }

        start_date = date(year, month, 1)
        last_day = monthrange(year, month)[1]
        end_date = date(year, month, last_day)
        group_by = "month"

    return {
        "intent": "revenue_statistics",
        "start_date": start_date,
        "end_date": end_date,
        "group_by": group_by,
    }
