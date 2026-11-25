
"""Optional local LLM for semantic price preference extraction."""

import json
import os
import urllib.request
from urllib.parse import urlparse

from shared.local_dialogue import NoRedirect
from shared.retrieval_limits import SourceGate
from .semantic_intent_validator import validate_price_intent


_GATE = SourceGate(
    "semantic_price_intent",
    timeout=35,
    cooldown=15
)

SYSTEM_PROMPT = """
Bạn là bộ phân tích ý định mua trang sức.
Không tư vấn sản phẩm. Chỉ phân loại sở thích giá
dựa trên điều khách hàng thực sự nói.

Trả về JSON:
{
  "price_preference": "neutral",
  "evidence": ""
}

Các nhãn:

affordable:
Khách muốn tiết kiệm tiền, giảm chi tiêu hoặc
có khó khăn về khả năng chi trả.

lowest_price:
Khách yêu cầu sản phẩm có giá thấp nhất.

highest_price:
Khách yêu cầu sản phẩm có giá cao nhất.

neutral:
Không thể hiện sở thích về giá, không quan tâm giá,
phủ định việc mua đồ rẻ, hoặc chỉ đưa ngân sách cụ thể.

Quy tắc bắt buộc:
1. Không suy ra sở thích giá từ chất liệu, danh mục,
   nghề nghiệp, giới tính hoặc mục đích tặng quà.
2. Ngân sách bằng con số không đồng nghĩa với affordable.
3. Xét toàn bộ ý nghĩa câu và phạm vi phủ định.
4. Không muốn đồ rẻ không có nghĩa là muốn đồ rẻ nhất.
5. Evidence phải là cụm từ nguyên văn trong câu hỏi.
6. Nếu không có căn cứ rõ ràng, chọn neutral.
7. Với neutral, evidence là chuỗi rỗng.
8. Chỉ trả JSON, không giải thích.

Ví dụ:
"Cho xem vòng bạc"
{"price_preference":"neutral","evidence":""}

"Muốn mua món không quá tốn kém"
{"price_preference":"affordable","evidence":"không quá tốn kém"}

"Không thích các mẫu giá thấp"
{"price_preference":"neutral","evidence":""}

"Chọn bông tai trong khoảng 2 triệu"
{"price_preference":"neutral","evidence":""}

"Cho xem mẫu có giá thấp nhất"
{"price_preference":"lowest_price","evidence":"giá thấp nhất"}
"""


def infer_price_preference(query, *, enabled=None, time_budget=None):

    if enabled is None:
        enabled = os.getenv(
            "LUMIERE_SEMANTIC_PRICE_ENABLED", "false"
        ).lower() == "true"

    if not enabled:
        return "neutral"

    if time_budget is not None and not 2 <= time_budget <= 24:
        return "neutral"

    if not isinstance(query, str):
        return "neutral"

    query = query.strip()

    if not query or len(query) > 1000:
        return "neutral"

    endpoint = os.getenv(
        "LUMIERE_SEMANTIC_PRICE_URL",
        "http://host.docker.internal:11434/api/chat"
    )

    address = urlparse(endpoint)

    if (
        address.scheme != "http"
        or address.hostname not in {
            "127.0.0.1",
            "localhost",
            "ollama",
            "host.docker.internal"
        }
        or address.username
        or address.password
        or address.path != "/api/chat"
        or address.query
        or address.fragment
    ):
        return "neutral"

    payload = {
        "model": os.getenv(
            "LUMIERE_SEMANTIC_PRICE_MODEL",
            "qwen2.5:3b"
        ),
        "stream": False,
        "format": "json",
        "keep_alive": os.getenv(
            "LUMIERE_SEMANTIC_PRICE_KEEP_ALIVE",
            "5m"
        ),
        "options": {
            "temperature": 0,
            "num_ctx": 2048,
            "num_predict": 128
        },
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": query
            }
        ]
    }

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    def generate():

        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            NoRedirect()
        )

        with opener.open(
            request, timeout=35 if time_budget is None else time_budget + 1
        ) as response:

            result = json.loads(
                response.read(65536)
            )

        content = result["message"]["content"]
        proposal = json.loads(content)

        validated = validate_price_intent(
            query, proposal
        )

        if os.getenv(
            "LUMIERE_SEMANTIC_PRICE_DEBUG", "false"
        ).lower() == "true":
            print("RAW PROPOSAL:", repr(proposal))
            print("VALIDATED:", validated)

        return validated

    try:
        if time_budget is not None:
            return _GATE.call_with_timeout(time_budget, generate)

        return _GATE.call(generate)

    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError
    ) as exc:
        if os.getenv(
            "LUMIERE_SEMANTIC_PRICE_DEBUG", "false"
        ).lower() == "true":
            print("FALLBACK ERROR:", type(exc).__name__)

        return "neutral"
