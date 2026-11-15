
import json
import os
import urllib.error
import urllib.request

from app.services.ai_staff_intent import (
    normalize_text,
    understand_staff_question,
)


OLLAMA_URL = os.getenv(
    "STAFF_OLLAMA_URL",
    "http://127.0.0.1:11434/api/chat",
)

STAFF_MODEL = os.getenv(
    "STAFF_OLLAMA_MODEL",
    "qwen2.5:3b",
)

ALLOWED_FIELDS = {
    "total_orders",
    "pending_orders",
    "confirmed_orders",
    "delivered_orders",
    "unpaid_orders",
    "paid_orders",
}


def unsupported(message=None):
    return {
        "intent": "unsupported",
        "message": message or (
            "Hiện tại tôi hỗ trợ thống kê số lượng "
            "đơn hàng theo trạng thái."
        ),
    }


def classify_staff_with_ollama(question: str):
    """
    Ollama chỉ phân loại câu hỏi.
    Không truy cập PostgreSQL và không tạo SQL.
    """

    payload = {
        "model": STAFF_MODEL,
        "stream": False,
        "format": "json",
        "keep_alive": "5m",
        "options": {
            "temperature": 0,
            "num_predict": 120,
        },
        "messages": [
            {
                "role": "system",
                "content": (
                    "Bạn là bộ phân loại câu hỏi cho "
                    "nhân viên LUMIÈRE.\n"
                    "Chỉ trả JSON, không giải thích.\n"
                    "Intent hợp lệ: order_statistics, "
                    "unsupported.\n"
                    "Nếu intent là order_statistics, "
                    "chọn đúng một field:\n"
                    "- total_orders: tổng số đơn\n"
                    "- pending_orders: đơn chờ xử lý\n"
                    "- confirmed_orders: đơn đã xác nhận\n"
                    "- delivered_orders: đơn đã giao\n"
                    "- unpaid_orders: đơn chưa thanh toán\n"
                    "- paid_orders: đơn đã thanh toán\n"
                    "Nếu câu hỏi không liên quan đến "
                    "số lượng đơn theo trạng thái, "
                    "trả unsupported.\n"
                    "Không trả lời số liệu thực tế.\n"
                    "Không tạo SQL.\n"
                    "Ví dụ JSON:\n"
                    '{"intent":"order_statistics",'
                    '"field":"pending_orders"}\n'
                    '{"intent":"unsupported"}'
                ),
            },
            {
                "role": "user",
                "content": question,
            },
        ],
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=20,
    ) as response:
        result = json.load(response)

    content = result["message"]["content"]
    parsed = json.loads(content)

    if not isinstance(parsed, dict):
        return unsupported()

    intent = parsed.get("intent")
    field = parsed.get("field")

    if intent != "order_statistics":
        return unsupported()

    if field not in ALLOWED_FIELDS:
        return unsupported()

    return {
        "intent": "order_statistics",
        "field": field,
    }


def understand_staff_question_with_llm(question: str):
    """
    Nhận diện bằng Ollama, có fallback.

    Nếu Ollama gặp lỗi, dùng bộ nhận diện cũ.
    Không tự thực hiện truy vấn database.
    """

    if not question or not question.strip():
        return {
            "intent": "invalid",
            "message": "Vui lòng nhập câu hỏi.",
        }

    text = normalize_text(question)

    # Chưa hỗ trợ lọc theo thời gian hoặc liệt kê
    # đơn cụ thể. Không trả số liệu all_time thay
    # cho câu hỏi hôm nay/tháng này.
    unsupported_patterns = (
        "hom nay",
        "hom qua",
        "thang nay",
        "thang truoc",
        "tuan nay",
        "ngay ",
        "liet ke",
        "danh sach",
        "ma don",
        "don nao",
    )

    if any(
        pattern in text
        for pattern in unsupported_patterns
    ):
        return unsupported(
            "Hiện tại tôi chỉ thống kê số lượng "
            "đơn trong toàn bộ lịch sử. "
            "Chức năng lọc thời gian và liệt kê "
            "đơn cụ thể chưa được hỗ trợ."
        )

    try:
        return classify_staff_with_ollama(question)

    except (
        OSError,
        TimeoutError,
        ValueError,
        KeyError,
        TypeError,
    ):
        # Giữ chức năng cũ khi Ollama không sẵn sàng.
        return understand_staff_question(question)
