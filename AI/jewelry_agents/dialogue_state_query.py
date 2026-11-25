
"""Convert validated shopping state into a retrieval query."""

from .dialogue_state import ShoppingState


CATEGORY_NAMES = {
    "ring": "nhẫn",
    "necklace": "dây chuyền",
    "earring": "bông tai",
    "chain_bracelet": "lắc tay",
    "bracelet": "vòng tay",
    "charm": "charm",
}


MATERIAL_NAMES = {
    "silver": "bạc",
    "white_gold": "vàng trắng",
    "rose_gold": "vàng hồng",
    "gold_18k": "vàng 18K",
    "platinum": "bạch kim",
}


PRICE_PREFERENCE_NAMES = {
    "neutral": "",
    "affordable": "giá mềm",
    "lowest_price": "rẻ nhất",
    "highest_price": "đắt nhất",
}


def render_shopping_query(state):
    """Render supported state without carrying obsolete descriptions."""

    if not isinstance(state, ShoppingState):
        raise TypeError("Expected ShoppingState")

    # Do not silently discard unsupported constraints.
    if any((state.gemstone, state.audience, state.style)):
        raise ValueError("Unsupported state fields for query rendering")

    parts = [f"Top {state.top_k}"]

    if state.category is not None:
        if state.category not in CATEGORY_NAMES:
            raise ValueError("Unknown category")

        parts.append(CATEGORY_NAMES[state.category])

    else:
        parts.append("trang sức")

    if state.material is not None:
        if state.material not in MATERIAL_NAMES:
            raise ValueError("Unknown material")

        parts.append(MATERIAL_NAMES[state.material])

    preference = PRICE_PREFERENCE_NAMES[state.price_preference]

    if preference:
        parts.append(preference)

    if state.min_price is not None:
        operator = (
            "trên" if state.min_exclusive
            else "từ"
        )

        parts.append(
            f"{operator} {state.min_price} đồng"
        )

    if state.max_price is not None:
        operator = (
            "dưới" if state.max_exclusive
            else "không quá"
        )

        parts.append(
            f"{operator} {state.max_price} đồng"
        )

    return " ".join(parts)
