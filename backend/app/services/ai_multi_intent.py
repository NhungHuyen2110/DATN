
import re
import unicodedata
from shared.conversation import normalize_utterance

INVENTORY_REQUEST = r'ton kho|hang ton|(?:hang )?sap het(?: hang)?|het hang|con hang|stock'
PURCHASE_REQUEST = r'hanh vi mua(?: hang)?|chi so mua hang|thong ke khach hang'


def normalize_question(message: str) -> str:
    """Chuẩn hóa tiếng Việt để nhận diện từ khóa."""
    text = unicodedata.normalize("NFD", normalize_utterance(message))

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
        if re.search(r'\b(?:' + PURCHASE_REQUEST + r')\b', text):
            tools.append('purchase_behavior')
        if contains_phrase(text, (
            "doanh thu",
            "tong doanh thu",
            "tien ban hang",
        )):
            tools.append("revenue")

        if re.search(r'\btop\s*\d+\s+san pham\b', text) or contains_phrase(text, (
            "ban chay",
            "ban chay nhat",
            "san pham nao ban chay",
            "san pham ban nhieu",
            "mua nhieu nhat",
            "mat hang nao duoc mua nhieu",
        )):
            tools.append("top_selling_products")

    if role in ("staff", "admin"):
        if re.search(r'\b(?:' + INVENTORY_REQUEST + r')\b', text):
            tools.append("inventory")

    if role in ("staff", "admin"):
        # The order parser validates status/filter coverage later. Tool routing
        # must retain requests with unknown statuses instead of answering only
        # the other business clause and silently discarding the order clause.
        if re.search(r"\bdon\b", text):
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
