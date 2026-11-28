
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

    from .ai_order_scope import has_order_request, parse_order_scope
    if not has_order_request(question):
        return {'intent': 'unsupported', 'message': 'Hiện tại tôi hỗ trợ thống kê đơn hàng và trạng thái xử lý.'}
    return parse_order_scope(question)
