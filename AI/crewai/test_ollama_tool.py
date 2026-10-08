import requests
import json


url = "http://localhost:11434/api/chat"


payload = {
    "model": "qwen2.5:3b",
    "messages": [
        {
            "role": "user",
            "content": "Tìm cho tôi một chiếc vòng tay bằng vàng"
        }
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "qdrant_product_search",
                "description": "Tìm kiếm sản phẩm trang sức bằng Qdrant",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Câu truy vấn tìm kiếm sản phẩm"
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Số lượng sản phẩm cần tìm"
                        }
                    },
                    "required": ["query", "top_k"]
                }
            }
        }
    ],
    "stream": False
}


print("=" * 70)
print("TEST OLLAMA + QWEN 3B + TOOL CALLING")
print("=" * 70)

try:
    response = requests.post(
        url,
        json=payload,
        timeout=60
    )

    print("\nHTTP STATUS:")
    print(response.status_code)

    print("\nRAW RESPONSE:")
    print(response.text)

    if response.status_code == 200:
        data = response.json()

        print("\n" + "=" * 70)
        print("MESSAGE")
        print("=" * 70)

        message = data.get("message", {})

        print(json.dumps(
            message,
            ensure_ascii=False,
            indent=2
        ))

        if message.get("tool_calls"):
            print("\n" + "=" * 70)
            print("TOOL CALL ĐÃ ĐƯỢC TẠO")
            print("=" * 70)

            for tool_call in message["tool_calls"]:
                print(json.dumps(
                    tool_call,
                    ensure_ascii=False,
                    indent=2
                ))

        else:
            print("\nKHÔNG CÓ TOOL CALL")

except Exception as e:
    print("\nLỖI:")
    print(type(e).__name__)
    print(str(e))