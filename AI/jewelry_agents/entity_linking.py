"""Versioned Vietnamese query entities with explicit evidence and ambiguity.

Entities express query intent, never inferred product facts. Optional semantic
matching accepts an existing encoder; this module never downloads a model.
"""
from functools import lru_cache
import json
import math
from pathlib import Path
import re
import unicodedata


CONFIG = Path(__file__).resolve().parents[1] / "config/aliases_vi.json"


def normalize(text):
    text = unicodedata.normalize("NFC", text).casefold()
    folded = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^\w]+", " ", folded.replace("đ", "d")).split())


@lru_cache(maxsize=1)
def load_entities():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    allowed = {"Category", "Audience", "Style", "Gemstone"}
    keys = set()
    for entity in config["entities"]:
        key = (entity["label"], entity["canonical_id"])
        if entity["label"] not in allowed or key in keys or not entity["aliases"]:
            raise ValueError("Invalid canonical entity configuration")
        keys.add(key)
    return config


def cosine(left, right):
    if len(left) != len(right) or len(left) == 0:
        raise ValueError("Embedding dimensions must match and be nonempty")
    if not all(math.isfinite(float(x)) for x in [*left, *right]):
        raise ValueError("Nonfinite embedding")
    denominator = math.sqrt(sum(float(x) ** 2 for x in left) * sum(float(x) ** 2 for x in right))
    return sum(float(a) * float(b) for a, b in zip(left, right)) / denominator if denominator else 0.0


def link_query(query, encoder=None, threshold=0.80, margin=0.08):
    config = load_entities()
    text = normalize(query)
    padded = " " + text + " "
    matches, ambiguous = [], []
    for entity in config["entities"]:
        hits = [alias for alias in entity["aliases"] if " " + normalize(alias) + " " in padded]
        if hits:
            alias = max(hits, key=lambda value: len(normalize(value)))
            matches.append({"label": entity["label"], "canonical_id": entity["canonical_id"],
                            "graph_id": entity.get("graph_id"), "method": "normalized_alias",
                            "alias": alias, "similarity": None})
    # A leading subject “nữ …” is different from the generic “nữ trang”
    # or product names such as “Nữ hoàng”. This resolves query intent only.
    if (re.match(r'^(?:cho )?nu(?:\s|$)', text)
            and not re.match(r'^(?:cho )?nu (?:trang|hoang|than)\b', text)
            and not any(item['label'] == 'Audience' for item in matches)):
        matches.append({'label': 'Audience', 'canonical_id': 'female', 'graph_id': None,
                        'method': 'subject_context', 'alias': 'nữ', 'similarity': None})
    age = re.search(r"\b(\d{1,2})\s*tuoi\b", text)
    female = any(item["label"] == "Audience" and item["canonical_id"] in {"female", "child_female"} for item in matches)
    child = " be gai " in padded or (female and age is not None and int(age.group(1)) < 18)
    if child:
        matches = [item for item in matches if item["label"] != "Audience"]
        matches.append({"label": "Audience", "canonical_id": "child_female", "graph_id": None,
                        "method": "age_context", "alias": age.group(0) if age else "bé gái", "similarity": None})
        ambiguous.append("child_catalog_not_verified")
    # Multiple explicit values are kept as unresolved constraints, not silently collapsed.
    for label in {item["label"] for item in matches}:
        if len({item["canonical_id"] for item in matches if item["label"] == label}) > 1:
            ambiguous.append("multiple_" + label.lower())
    attempted = False
    if encoder is not None and text:
        # Only unresolved labels, no automatic merging or overriding explicit aliases.
        candidates = [item for item in config["entities"]
                      if item["label"] not in {match["label"] for match in matches}
                      and not (item["label"] == "Audience" and age and int(age.group(1)) < 18)]
        if candidates:
            attempted = True
            vectors = encoder.encode([query] + [item["aliases"][0] for item in candidates])
            for label in {item["label"] for item in candidates}:
                ranked = sorted([(cosine(vectors[0], vectors[index + 1]), item)
                                 for index, item in enumerate(candidates) if item["label"] == label],
                                key=lambda pair: (-pair[0], pair[1]["canonical_id"]))
                score, item = ranked[0]
                second = ranked[1][0] if len(ranked) > 1 else -1.0
                if score >= threshold and score - second >= margin:
                    matches.append({"label": label, "canonical_id": item["canonical_id"],
                                    "graph_id": item.get("graph_id"), "method": "embedding_candidate",
                                    "alias": None, "similarity": score})
    return {"normalized": text, "entities": matches, "ambiguities": sorted(set(ambiguous)),
            "needs_clarification": bool(ambiguous), "semantic_attempted": attempted,
            "alias_version": config["version"]}
