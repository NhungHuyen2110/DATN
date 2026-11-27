
"""Prepare structured shopping refinements without mutating sessions."""

import re
import os
from functools import lru_cache

from .dialogue_state import ShoppingState, StatePatch, update_state
from .dialogue_state_extractor import apply_shopping_message, extract_state_changes
from .dialogue_state_query import render_shopping_query
from .entity_linking import normalize, link_query
from .price_intent_router import resolve_price_preference
from .semantic_price_intent import infer_price_preference


def prepare_state(query, parse_price, top_k=3):
    """Build a state for a supported shopping request."""

    if identity_request(query):
        return None
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

    if enabled:
        semantic_state = semantic_entity_refinement(message, previous_state)
        if semantic_state is not None:
            return semantic_state

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


@lru_cache(maxsize=1)
def _semantic_slot_vectors(encoder):
    from .entity_linking import load_entities
    from .dialogue_state_extractor import MATERIALS
    candidates = [(e['label'].lower(), e['canonical_id'], e.get('definition', e['aliases'][0]))
                  for e in load_entities()['entities'] if e['label'] in {'Category', 'Gemstone'}]
    candidates += [('material', canonical, alias) for alias, canonical in MATERIALS.items()]
    return candidates, encoder.encode([item[2] for item in candidates])


def semantic_entity_refinement(message, previous_state):
    """Use the already loaded MiniLM and ontology; never load another model.

    Explicit extraction always wins. Low confidence and negation abstain.
    Inferred audience/style remain strict verified-attribute filters in search.
    """
    from . import retrieval
    from .entity_linking import cosine
    text = normalize(message)
    encoder = retrieval.embedding_model
    if encoder is None or retrieval._model_warming.is_set():
        return None
    if re.search(r'\b(?:khong|dung|bo|chang|gia|tien|ngan sach|re|dat)\b', text):
        return None
    def encode():
        candidates, vectors = _semantic_slot_vectors(encoder)
        return candidates, vectors, encoder.encode([message])[0]
    candidates, vectors, query_vector = retrieval._dense_gate.call_with_timeout(4, encode)
    scores = {}
    for index, (field, canonical, _) in enumerate(candidates):
        key = (field, canonical)
        scores[key] = max(scores.get(key, -1), cosine(query_vector, vectors[index]))
    ranked = sorted(scores.items(), key=lambda item: -item[1])
    if len(ranked) < 2 or ranked[0][1] < .82 or ranked[0][1] - ranked[1][1] < .12:
        return None
    (field, value), _ = ranked[0]
    updated = StatePatch({field: value}).apply(previous_state)
    return updated, render_shopping_query(updated)


def cheaper_request(message):
    return bool(re.search(r"\b(?:re hon|gia (?:thap|mem) hon|it tien hon)\b", normalize(message)))


def identity_request(message):
    text = normalize(message)
    return bool(re.search(r'\b(?:sku|ma san pham|ma hang|ma sp)\b|\bsan pham\s+\d+\b|#\d+', text)
                or re.search(r'\b(?!top\d)[a-z]{2,}\d+[a-z0-9]*\b', text))


def missing_refinement_field(message):
    text = normalize(message)
    for field, phrase in (("material", "chất liệu"), ("gemstone", "loại đá")):
        normalized_phrase = normalize(phrase)
        if (normalized_phrase in text and
                re.search(r"\b(?:doi|thay|thu|khac)\b", text) and
                not extract_state_changes(message, lambda _: {})[0].get(field)):
            return field, f"Bạn muốn đổi sang {phrase} nào?"
    return None


def prepare_refinement(message, previous_state, parse_price, previous_products=()):

    if not isinstance(previous_state, ShoppingState):
        return None

    try:
        from shared.conversation import knowledge_request, followup_kind
        from .intent_router import classify_query
        from .query_reference import reference_request
        if (knowledge_request(message) or followup_kind(message) or
                identity_request(message) or
                normalize(message).startswith(('so sanh ', 'tai sao ', 'vi sao ', 'cach ')) or
                classify_query(message) not in {'general_question', 'product_search'} or
                reference_request(message).get('active')):
            return None
        text = normalize(message)
        understanding = link_query(re.split(r'\b(?:thay vi|chu khong phai)\b', text)[0])
        if understanding.get('needs_clarification'):
            return None
        updates, clear = extract_state_changes(message, parse_price)
        if cheaper_request(message):
            from decimal import Decimal
            prices = [Decimal(str(p['Price'])) for p in previous_products if p.get('Price') is not None]
            prices = [p for p in prices if p.is_finite() and p >= 0]
            if not prices:
                return None  # No grounded comparison anchor.
            anchor = min(prices)
            ceiling = int(anchor) if anchor == int(anchor) else format(anchor, 'f')
            old_max = previous_state.max_price
            if old_max is None or anchor <= Decimal(str(old_max)):
                updates.update(max_price=ceiling, max_exclusive=True)
            updates['price_preference'] = 'affordable'
        if not updates and not clear:
            if missing_refinement_field(message):
                return None
            return prepare_semantic_refinement(message, previous_state)
        # Reject negated entity selection unless an explicit CLEAR/replacement exists.
        if re.search(r'\b(?:khong|dung) (?:muon |thich )?(?:mua|chon|lay|tim)\b', text):
            return None
        reset = bool(re.search(r'\b(?:bat dau lai|nhu cau moi|tim moi|bo het dieu kien)\b', text))
        updated = StatePatch(updates, frozenset(clear), reset).apply(previous_state)
        query = render_shopping_query(updated)
        return updated, query

    except (TypeError, ValueError, OSError, RuntimeError):
        return None
