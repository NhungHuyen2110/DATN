
import json
import os
import urllib.request

from app.services.ai_admin_intent import (
    understand_admin_question,
)


OLLAMA_URL = os.getenv(
    "ADMIN_OLLAMA_URL",
    "http://127.0.0.1:11434/api/chat",
)

ADMIN_MODEL = os.getenv(
    "ADMIN_OLLAMA_MODEL",
    "qwen2.5:3b",
)


def classify_with_ollama(question: str) -> str:
    """
    LLM chỉ phân loại ý định.
    Không được truy cập database hoặc thực thi SQL.
    """

    payload = {
        "model": ADMIN_MODEL,
        "stream": False,
        "format": "json",
        "keep_alive": "10m",
        "options": {
            "temperature": 0,
            "num_predict": 100,
        },
        "messages": [
            {
                "role": "system",
                "content": (
                    "Bạn phân loại câu hỏi của Admin "
                    "trong hệ thống bán trang sức LUMIÈRE. "
                    "Chỉ trả về JSON hợp lệ.\n"
                    "Các intent được phép:\n"
                    "- top_selling_products: câu hỏi về "
                    "sản phẩm bán chạy, bán nhiều nhất, "
                    "tiêu thụ nhiều nhất.\n"
                    "- unsupported: các câu hỏi khác.\n"
                    "Chỉ trả về dạng "
                    '{"intent":"top_selling_products"} '
                    'hoặc {"intent":"unsupported"}. '
                    "Không trả lời câu hỏi, không tạo SQL."
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
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=60,
    ) as response:
        result = json.load(response)

    content = result["message"]["content"]
    parsed = json.loads(content)

    intent = parsed.get("intent")

    if intent not in {
        "top_selling_products",
        "unsupported",
    }:
        return "unsupported"

    return intent


def understand_admin_question_with_llm(
    question: str,
):
    """
    Ưu tiên bộ nhận diện cũ đang hoạt động.
    Chỉ gọi LLM khi câu hỏi chưa được nhận diện.
    """

    existing = understand_admin_question(question)

    if existing["intent"] != "unsupported":
        return existing

    # Nếu LLM lỗi hoặc không hoạt động,
    # giữ nguyên kết quả an toàn của hệ thống cũ.
    try:
        llm_intent = classify_with_ollama(question)
    except (
        OSError,
        TimeoutError,
        ValueError,
        KeyError,
        TypeError,
    ):
        return existing

    if llm_intent != "top_selling_products":
        return existing

    # Giữ nguyên câu hỏi gốc để không mất thông tin
    # ngày, tháng, năm và số lượng sản phẩm.
    normalized_question = question + " bán chạy"

    return understand_admin_question(normalized_question)
