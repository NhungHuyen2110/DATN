
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
    "white_gold_18k": "vàng trắng 18K",
    "white_gold_14k": "vàng trắng 14K",
    "white_gold_10k": "vàng trắng 10K",
    "gold_24k": "vàng 24K",
    "gold_14k": "vàng 14K",
    "gold_10k": "vàng 10K",
    "gold": "vàng",
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

    from .entity_linking import load_entities
    for field, label in (("gemstone", "Gemstone"), ("audience", "Audience"), ("style", "Style")):
        value = getattr(state, field)
        if value is not None:
            entity = next((e for e in load_entities()['entities']
                           if e['label'] == label and e['canonical_id'] == value), None)
            if entity is None:
                raise ValueError("Unknown " + field)
            parts.append(entity['aliases'][0])

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
