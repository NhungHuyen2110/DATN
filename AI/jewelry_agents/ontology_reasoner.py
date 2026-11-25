
"""Conservative domain evidence for jewelry category resolution."""

import re

from .entity_linking import normalize


CATEGORY_KNOWLEDGE = {
    "ring": {
        "location": "finger",
        "usage": "direct_wear",
    },
    "necklace": {
        "location": "neck",
        "usage": "direct_wear",
    },
    "earring": {
        "location": "ear",
        "usage": "direct_wear",
    },
    "bracelet": {
        "location": "wrist",
        "usage": "direct_wear",
        "form": "bangle",
    },
    "chain_bracelet": {
        "location": "wrist",
        "usage": "direct_wear",
        "form": "flexible_chain",
    },
    "charm": {
        "location": "jewelry",
        "usage": "attachment",
    },
}


LOCATION_PATTERNS = {
    "finger": r"\b(?:ngon tay|ngon ap ut|ngon tro|ngon cai|ngon ut|ngon giua)\b",
    "wrist": r"\bco tay\b",
    "neck": r"\b(?:quanh|tren|o|vung|vong) co\b(?!\s+tay\b)",
    "ear": r"\b(?:o tai|tren tai|dai tai|vanh tai|hai ben tai)\b",
}


def extract_features(query):
    text = normalize(query)

    # Do not infer a category from negative requirements.
    if re.search(
        r"\b(?:khong|chang|dung|khong muon)\s+"
        r"(?:muon\s+)?(?:mua|deo|gan|treo|chon|lay)\b",
        text,
    ):
        return {}

    # Distinguish the attachment from the item it attaches to.
    if (
        re.search(r"\b(?:phu kien|mat treo|hat|chi tiet)\b", text)
        and re.search(
            r"\b(?:gan|treo|moc|lap)\s+(?:them\s+)?"
            r"(?:vao|len|tren)\b",
            text,
        )
        and re.search(
            r"\b(?:vong tay|lac tay|day chuyen|trang suc)\b",
            text,
        )
    ):
        return {"usage": "attachment"}

    if not re.search(
        r"\b(?:deo|om|quanh|trang tri|gan)\b", text
    ):
        return {}

    locations = {
        location
        for location, pattern in LOCATION_PATTERNS.items()
        if re.search(pattern, text)
    }

    if len(locations) != 1:
        return {}

    location = next(iter(locations))

    features = {
        "location": location,
        "usage": "direct_wear",
    }

    if location == "wrist":
        if re.search(
            r"\b(?:day mem|soi mem|chuoi mem|mat xich)\b",
            text,
        ):
            features["form"] = "flexible_chain"

        elif re.search(
            r"\b(?:vong cung|dang cung)\b", text
        ):
            features["form"] = "bangle"

    return features


def reason_categories(query):
    features = extract_features(query)

    if not features:
        return {
            "status": "no_evidence",
            "features": {},
            "eligible": [],
        }

    eligible = [
        category
        for category, knowledge in CATEGORY_KNOWLEDGE.items()
        if all(
            knowledge.get(key) == value
            for key, value in features.items()
        )
    ]

    if len(eligible) == 1:
        status = "resolved"
    elif len(eligible) > 1:
        status = "ambiguous"
    else:
        status = "no_match"

    return {
        "status": status,
        "features": features,
        "eligible": eligible,
    }


def rank_with_knowledge(query, semantic_scores):
    evidence = reason_categories(query)

    if evidence["status"] in {"resolved", "ambiguous"}:
        allowed = set(evidence["eligible"])
        candidates = {
            key: score
            for key, score in semantic_scores.items()
            if key in allowed
        }
    else:
        candidates = dict(semantic_scores)

    ranked = sorted(
        candidates.items(),
        key=lambda item: (-item[1], item[0]),
    )

    return {
        "ranked": ranked,
        "evidence": evidence,
        "method": "ontology_guided_semantic_linking",
    }
