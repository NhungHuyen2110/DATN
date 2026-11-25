
"""Coordinate deterministic and optional semantic price intent."""

import re
from .entity_linking import normalize
from .price_preference import detect_price_preference
from .semantic_price_intent import infer_price_preference


def resolve_price_preference(
    query,
    constraints=None,
    allow_semantic=False,
    semantic_infer=None
):
    constraints = constraints or {}


    # Check negation before accepting explicit price preferences.
    text = normalize(query)

    if re.search(
        r"\b(?:khong|chang|dung)\s+"
        r"(?:(?:can|muon|thich|mua|tim|chon|lay|"
        r"cac|nhung|san|pham|trang|suc|mon|do|"
        r"loai|mau|qua)\s+){0,12}"
        r"(?:gia re|gia mem|gia thap|re nhat|"
        r"binh dan|tiet kiem|vua tui tien)\b",
        text
    ):
        return "neutral"

    explicit = detect_price_preference(query)

    if explicit != "neutral":
        return explicit

    if not allow_semantic:
        return "neutral"

    if (
        constraints.get("min_price") is not None
        or constraints.get("max_price") is not None
    ):
        return "neutral"

    text = normalize(query)

    # Do not override explicit rejection of cheap products
    # or explicit indifference to price.
    if re.search(
        r"\b(?:khong|chang)\s+"
        r"(?:can|muon|thich|quan tam|quan trong)\b"
        r".{0,60}\b(?:gia|re|binh dan|tiet kiem)\b",
        text
    ):
        return "neutral"

    if re.search(
        r"\b(?:gia nao cung duoc|"
        r"tien bac khong thanh van de|"
        r"gia tinh sau)\b",
        text
    ):
        return "neutral"

    proposed = (
        semantic_infer or infer_price_preference
    )(query)

    # Semantic inference may only introduce a soft preference.
    if proposed == "affordable":
        return "affordable"

    return "neutral"
