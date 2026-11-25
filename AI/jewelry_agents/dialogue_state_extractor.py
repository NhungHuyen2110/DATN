
"""Extract supported shopping-state changes from Vietnamese messages."""

import re

from .entity_linking import link_query, normalize
from .shopping_advice import budget_text
from .price_preference import detect_price_preference
from .dialogue_state import ShoppingState, update_state


ENTITY_FIELDS = {
    "Category": "category",
    "Gemstone": "gemstone",
    "Audience": "audience",
    "Style": "style",
}


MATERIALS = {
    "vang trang": "white_gold",
    "vang hong": "rose_gold",
    "vang 18k": "gold_18k",
    "bac 925": "silver",
    "bach kim": "platinum",
    "platinum": "platinum",
    "bac": "silver",
}


def extract_state_changes(message, parse_price):

    if not isinstance(message, str):
        raise TypeError("Expected text message")

    text = normalize(message)
    updates = {}
    clear = set()

    clear_material = bool(re.search(
        r"\b(?:khong can|khong bat buoc|bo yeu cau)"
        r"\s+(?:bang |chat lieu )?"
        r"(?:bac(?: 925)?|vang(?: trang| hong| 18k)?|"
        r"bach kim|platinum|chat lieu)"
        r"(?: nua)?\b",
        text
    ))

    if clear_material:
        clear.add("material")
    else:
        for alias, canonical in MATERIALS.items():
            if re.search(
                r"(?<!\w)" + re.escape(alias) + r"(?!\w)",
                text
            ):
                updates["material"] = canonical
                break

    understanding = link_query(message)

    if not understanding.get("needs_clarification"):
        grouped = {}

        for entity in understanding.get("entities", []):
            field = ENTITY_FIELDS.get(entity["label"])

            if field:
                grouped.setdefault(field, set()).add(
                    entity["canonical_id"]
                )

        for field, values in grouped.items():
            if len(values) == 1:
                updates[field] = next(iter(values))

    price_query = budget_text(message)

    price_query = re.sub(
        r"\b(?:tăng|giảm)\s+(?:ngân sách\s+)?"
        r"(?:lên|xuống)\s+",
        "ngân sách ",
        price_query,
        flags=re.I
    )

    price_aliases = {
        "duoi": "dưới",
        "tren": "trên",
        "tu": "từ",
        "den": "đến",
        "tam": "tầm",
        "khoang": "khoảng",
        "trieu": "triệu",
        "nghin": "nghìn",
        "ngan": "ngàn",
        "dong": "đồng",
        "khong qua": "không quá",
        "ngan sach": "ngân sách",
        "toi da": "tối đa",
    }

    price_query = re.sub(
        r"(?<!\w)(?:"
        + "|".join(
            re.escape(alias)
            for alias in sorted(
                price_aliases, key=len, reverse=True
            )
        )
        + r")(?!\w)",
        lambda match: price_aliases[match.group(0).lower()],
        price_query,
        flags=re.I
    )

    prices = parse_price(price_query) or {}

    for field in ("min_price", "max_price"):
        value = prices.get(field)

        if value is not None:
            if int(value) != value:
                raise ValueError("Non-integer budget")

            updates[field] = int(value)

            exclusive = field.replace(
                "_price", "_exclusive"
            )

            normalized_price = normalize(price_query)

            if exclusive in prices:
                updates[exclusive] = bool(prices[exclusive])

            elif field == "max_price":
                updates[exclusive] = bool(re.search(
                    r"\b(?:duoi|nho hon|thap hon)\s+\d",
                    normalized_price
                ))

            else:
                updates[exclusive] = bool(re.search(
                    r"\b(?:tren|lon hon|cao hon)\s+\d",
                    normalized_price
                ))

    preference = detect_price_preference(message)

    if preference != "neutral":
        updates["price_preference"] = preference

    elif re.search(
        r"\b(?:khong quan tam gia|"
        r"gia nao cung duoc|"
        r"khong quan trong gia|"
        r"tien bac khong thanh van de)\b",
        text
    ):
        clear.add("price_preference")

    count = re.search(
        r"\b(?:top\s*|"
        r"(?:cho xem|goi y|chon|lay)\s+)"
        r"(\d{1,2})\b",
        text
    )

    if count:
        updates["top_k"] = int(count.group(1))

    return updates, clear


def apply_shopping_message(
    state, message, parse_price
):
    """Apply changes to an already-established shopping task."""

    if not isinstance(state, ShoppingState):
        raise TypeError("Expected ShoppingState")

    updates, clear = extract_state_changes(
        message, parse_price
    )

    return update_state(
        state,
        updates=updates,
        clear=clear
    )
