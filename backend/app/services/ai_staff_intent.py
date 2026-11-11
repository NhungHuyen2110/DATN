
import unicodedata


def normalize_text(text: str) -> str:
    """
    Chuẩn hóa tiếng Việt để nhận diện câu hỏi.
    """
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)

    text = "".join(
        char for char in text
        if unicodedata.category(char) != "Mn"
    )

    return text.replace("đ", "d")


def understand_staff_question(question: str):
    """
    Nhận diện câu hỏi về thống kê đơn hàng.

    Không truy cập database.
    Không thay đổi dữ liệu.
    """

    text = normalize_text(question)

    if not text:
        return {
            "intent": "invalid",
            "message": "Vui lòng nhập câu hỏi."
        }

    order_keywords = (
        "don hang",
        "don",
    )

    if not any(word in text for word in order_keywords):
        return {
            "intent": "unsupported",
            "message": (
                "Hiện tại tôi hỗ trợ thống kê "
                "đơn hàng và trạng thái xử lý."
            ),
        }

    if "chua thanh toan" in text:
        return {
            "intent": "order_statistics",
            "field": "unpaid_orders",
        }

    if "da thanh toan" in text:
        return {
            "intent": "order_statistics",
            "field": "paid_orders",
        }

    if any(
        word in text
        for word in ("cho xu ly", "dang cho", "pending")
    ):
        return {
            "intent": "order_statistics",
            "field": "pending_orders",
        }

    if any(
        word in text
        for word in ("da xac nhan", "confirmed")
    ):
        return {
            "intent": "order_statistics",
            "field": "confirmed_orders",
        }

    if any(
        word in text
        for word in ("da giao", "delivered")
    ):
        return {
            "intent": "order_statistics",
            "field": "delivered_orders",
        }

    return {
        "intent": "order_statistics",
        "field": "total_orders",
    }
