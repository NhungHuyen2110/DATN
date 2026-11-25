
"""Prepare structured shopping refinements without mutating sessions."""

import re

from .dialogue_state import ShoppingState
from .dialogue_state_extractor import apply_shopping_message
from .dialogue_state_query import render_shopping_query
from .entity_linking import normalize


def prepare_state(query, parse_price, top_k=3):
    """Build a state for a supported shopping request."""

    state = apply_shopping_message(
        ShoppingState(top_k=top_k),
        query,
        parse_price
    )

    if state.category is None:
        return None

    # Verify that all extracted fields can be rendered.
    render_shopping_query(state)

    return state


def is_supported_refinement(message):

    text = normalize(message)

    patterns = (
        r"^(?:thoi )?(?:doi|chuyen) sang "
        r"(?:nhan|day chuyen|bong tai|lac tay|vong tay|charm)"
        r"(?: di| nhe| thoi)?$",

        r"^(?:tang|giam) ngan sach (?:len|xuong) "
        r"\d+(?:[.,]\d+)?\s*(?:trieu|tr|nghin|ngan|dong|k)$",

        r"^(?:toi |tui |minh |em )?"
        r"muon tiet kiem(?: mot chut)?$",

        r"^khong can bang "
        r"(?:bac(?: 925)?|vang 18k|vang trang|vang hong|bach kim)"
        r" nua$",

        r"^(?:cho xem|goi y) "
        r"(?:10|[1-9]) (?:mon|mau|san pham)(?: thoi)?$",

        r"^(?:khong quan tam gia|gia nao cung duoc)$",
    )

    return any(
        re.fullmatch(pattern, text)
        for pattern in patterns
    )


def prepare_refinement(message, previous_state, parse_price):

    if not isinstance(previous_state, ShoppingState):
        return None

    if not is_supported_refinement(message):
        return None

    try:

        updated = apply_shopping_message(
            previous_state,
            message,
            parse_price
        )

        text = normalize(message)

        # Do not accept failed budget updates silently.
        if re.match(r"^(?:tang|giam) ngan sach", text):
            if updated.max_price == previous_state.max_price:
                return None

        query = render_shopping_query(updated)

        return updated, query

    except (TypeError, ValueError):
        return None
