
import re
import unicodedata


def normalize_question(message: str) -> str:
    """Chuẩn hóa tiếng Việt để nhận diện từ khóa."""
    text = unicodedata.normalize("NFD", message.casefold())

    text = "".join(
        char for char in text
        if unicodedata.category(char) != "Mn"
    )

    text = text.replace("đ", "d")

    # Chuẩn hóa khoảng trắng và dấu câu
    text = re.sub(r"[^a-z0-9]+", " ", text)

    return " ".join(text.split())


def contains_phrase(text: str, phrases) -> bool:
    """Tìm cụm từ trên ranh giới từ."""
    padded = f" {text} "

    return any(
        f" {phrase} " in padded
        for phrase in phrases
    )


def detect_requested_tools(message: str, role: str):
    text = normalize_question(message)
    tools = []

    if role == "admin":
        if contains_phrase(text, (
            "doanh thu",
            "tong doanh thu",
            "tien ban hang",
        )):
            tools.append("revenue")

        if contains_phrase(text, (
            "ban chay",
            "ban chay nhat",
            "san pham nao ban chay",
            "san pham ban nhieu",
            "mua nhieu nhat",
            "mat hang nao duoc mua nhieu",
        )):
            tools.append("top_selling_products")

    if role in ("staff", "admin"):
        if contains_phrase(text, (
            "ton kho",
            "sap het hang",
            "het hang",
            "con hang",
            "san pham nao sap het",
        )):
            tools.append("inventory")

    if role in ("staff", "admin"):
        if contains_phrase(text, (
            "don hang",
            "don hang cho xu ly",
            "don cho xu ly",
            "don dang cho",
            "don da giao",
            "don da xac nhan",
            "bao nhieu don",
        )):
            tools.append("order_statistics")

    return tools


def analyze_multi_intent(message: str, role: str):
    if not isinstance(message, str):
        return {
            "is_multi_intent": False,
            "tools": [],
            "tool_count": 0,
        }

    if not isinstance(role, str) or role not in (
        "admin", "staff"
    ):
        return {
            "is_multi_intent": False,
            "tools": [],
            "tool_count": 0,
        }

    if not message.strip() or len(message) > 1000:
        return {
            "is_multi_intent": False,
            "tools": [],
            "tool_count": 0,
        }

    tools = detect_requested_tools(message, role)

    return {
        "is_multi_intent": len(tools) >= 2,
        "tools": tools,
        "tool_count": len(tools),
    }
