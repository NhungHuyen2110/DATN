
"""Prepare structured shopping refinements without mutating sessions."""

import re
import os

from .dialogue_state import ShoppingState, update_state
from .dialogue_state_extractor import apply_shopping_message
from .dialogue_state_query import render_shopping_query
from .entity_linking import normalize, link_query
from .price_intent_router import resolve_price_preference
from .semantic_price_intent import infer_price_preference


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



def prepare_semantic_refinement(message, previous_state):
    """Allow only a supported soft price preference."""

    from shared.conversation import knowledge_request, followup_kind
    from .intent_router import classify_query
    from .query_reference import reference_request

    if previous_state.category is None:
        return None

    if not isinstance(message, str) or not 1 <= len(message) <= 250:
        return None

    if knowledge_request(message) or followup_kind(message):
        return None

    if classify_query(message) not in {
        "general_question", "product_search"
    }:
        return None

    if reference_request(message).get("active"):
        return None

    if link_query(message).get("entities"):
        return None

    if re.search(r"\d", message):
        return None

    enabled = os.getenv(
        "LUMIERE_SEMANTIC_DST_ENABLED", "false"
    ).lower() == "true"

    def semantic_infer(query):

        from .retrieval import _model_warming

        if _model_warming.is_set():
            return "neutral"

        return infer_price_preference(
            query,
            enabled=True,
            time_budget=18
        )

    preference = resolve_price_preference(
        message,
        constraints={},
        allow_semantic=enabled,
        semantic_infer=semantic_infer
    )

    if preference != "affordable":
        return None

    state = update_state(
        previous_state,
        updates={"price_preference": "affordable"}
    )

    return state, render_shopping_query(state)


def prepare_refinement(message, previous_state, parse_price):

    if not isinstance(previous_state, ShoppingState):
        return None

    if not is_supported_refinement(message):
        try:
            return prepare_semantic_refinement(
                message, previous_state
            )
        except (TypeError, ValueError):
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
