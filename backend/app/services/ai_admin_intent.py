
import re


def understand_admin_question(question: str):
    """
    Nhận diện ý định truy vấn thống kê.
    Đây là bộ phân tích quy tắc ban đầu,
    chưa phải mô hình LLM.
    """
    from .ai_staff_intent import normalize_text
    text = normalize_text(question)

    if not text:
        return {
            "intent": "invalid",
            "message": "Vui lòng nhập câu hỏi."
        }

    selling_keywords = [
        'ban chay', 'ban nhieu nhat', 'ban tot nhat', 'top san pham',
        'san pham ban nhieu', 'mua nhieu nhat',
    ]

    if not any(word in text for word in selling_keywords) and not re.search(r'\btop\s*\d+\s+san pham\b', text):
        return {
            "intent": "unsupported",
            "message": (
                "Hiện tại tôi hỗ trợ thống kê "
                "sản phẩm bán chạy. Các chức năng "
                "AI khác đang được bổ sung."
            )
        }

    from .ai_reporting_period import parse_reporting_period, reporting_scope_supported
    period = parse_reporting_period(question)
    if period['intent'] != 'period':
        return period
    if re.search(r'\b(?:theo|moi|tung)\s+(?:ngay|thang)\b', text):
        return {'intent': 'unsupported', 'message': 'Báo cáo bán chạy chưa hỗ trợ chia nhóm theo ngày hoặc tháng.'}
    if not reporting_scope_supported(period.pop('_remaining'), selling=True):
        return {'intent': 'unsupported', 'message': 'Chưa hỗ trợ đầy đủ bộ lọc trong yêu cầu bán chạy.'}

    # Nhận diện top 3, top 5, top 10...
    top_match = re.search(r"\btop\s+(\d+)", text)
    limit = int(top_match.group(1)) if top_match else 5

    if not 1 <= limit <= 20:
        return {
            "intent": "invalid",
            "message": "Số lượng top phải từ 1 đến 20."
        }

    return {
        'intent': 'top_selling_products',
        'start_date': period['start_date'],
        'end_date': period['end_date'],
        'limit': limit,
    }
