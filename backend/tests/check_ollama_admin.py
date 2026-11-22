
import json
import urllib.request
import urllib.error


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:3b"


def main():
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Bạn là trợ lý AI quản trị hệ thống "
                    "thương mại điện tử trang sức LUMIÈRE. "
                    "Trả lời bằng tiếng Việt. "
                    "Không tự bịa số liệu kinh doanh. "
                    "Nếu chưa có dữ liệu, hãy nói rõ "
                    "cần truy vấn hệ thống."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Hãy giải thích ngắn gọn bạn sẽ "
                    "làm gì khi Admin hỏi: "
                    "'Sản phẩm nào bán chạy nhất tháng này?'"
                ),
            },
        ],
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 180,
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=90
        ) as response:
            result = json.load(response)

        print("\n=== OLLAMA ADMIN TEST ===")
        print("Model:", MODEL)
        print(
            "Answer:",
            result.get("message", {}).get("content", ""),
        )
        print("\nOLLAMA TEST COMPLETED")

    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
    ) as error:
        print("OLLAMA TEST FAILED:", error)


if __name__ == "__main__":
    main()
