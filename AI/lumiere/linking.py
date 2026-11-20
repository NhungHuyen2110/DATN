"""Versioned alias -> semantic candidates -> context/schema verification."""

from dataclasses import dataclass, field
import math
import re

from .configuration import load_aliases
from .domain import Embedder
from .text import contains, nfc, normalize


def folded_aliases(config: dict | None = None) -> dict:
    config = config or load_aliases()
    return {kind: {canonical: tuple(dict.fromkeys(normalize(a) for a in definition["aliases"]))
                   for canonical, definition in concepts.items()} for kind, concepts in config["entities"].items()}


@dataclass(frozen=True)
class LinkingResult:
    entities: dict[str, tuple[str, ...]] = field(default_factory=dict)
    excluded: dict[str, tuple[str, ...]] = field(default_factory=dict)
    evidence: tuple[dict, ...] = ()
    ambiguities: tuple[str, ...] = ()


class SemanticEntityResolver:
    def __init__(self, embedder: Embedder, config: dict):
        self.embedder, self.config = embedder, config
        self.cache = {}

    def resolve(self, kind: str, mention: str) -> tuple[str | None, float, float]:
        definitions = self.config["entities"][kind]
        ids = list(definitions)
        if kind not in self.cache:
            self.cache[kind] = self.embedder.encode([definitions[i].get("description", definitions[i]["name"]) for i in ids])
        vector = self.embedder.encode([mention])[0]
        if not vector or not any(vector) or not all(math.isfinite(v) for v in vector):
            raise ValueError("Invalid entity embedding")

        def cosine(other):
            if len(vector) != len(other):
                raise ValueError("Entity embedding dimensions mismatch")
            if not all(math.isfinite(v) for v in other) or not any(other):
                raise ValueError("Invalid entity concept embedding")
            denominator = math.sqrt(sum(v*v for v in vector) * sum(v*v for v in other))
            return sum(a*b for a, b in zip(vector, other)) / denominator if denominator else 0.0

        ranked = sorted(((cosine(v), ident) for ident, v in zip(ids, self.cache[kind])), key=lambda x: (-x[0], x[1]))
        best, ident = ranked[0]
        gap = best - ranked[1][0] if len(ranked) > 1 else best
        if best < self.config["semantic_threshold"] or gap < self.config["ambiguity_margin"]:
            return None, best, gap
        return ident, best, gap


class EntityLinkingService:
    def __init__(self, config: dict | None = None, semantic: SemanticEntityResolver | None = None):
        self.config = config or load_aliases()
        self.aliases = folded_aliases(self.config)
        self.semantic = semantic

    def link(self, query: str) -> dict[str, tuple[str, ...]]:
        return self.resolve(query).entities

    def resolve(self, query: str) -> LinkingResult:
        text, original = normalize(query), nfc(query).casefold()
        positive, negative, evidence, ambiguous = {}, {}, [], []
        for kind, concepts in self.aliases.items():
            matches, excluded = [], []
            for canonical, aliases in concepts.items():
                for alias in aliases:
                    for match in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text):
                        prefix = text[max(0, match.start()-30):match.start()]
                        # 'bác' as recipient must not become a silver constraint.
                        if kind == "material" and canonical == "bac" and (
                            (contains(original, "bác") and not contains(original, "bạc"))
                            or re.search(r"(?:cho|tang)\s+$", prefix)
                        ):
                            continue
                        negated = bool(re.search(r"(?:khong(?:\s+(?:co|gan|dinh|dung))?|tranh|ngoai tru)\s+$", prefix))
                        (excluded if negated else matches).append(canonical)
                        evidence.append({"kind": kind, "canonical_id": canonical, "alias": alias,
                                         "method": "exact_alias", "confidence": 1.0,
                                         "negated": negated, "alias_version": self.config["version"]})
            if kind == "material" and matches:
                # Longest specific gold concept dominates broad gold, regardless of order.
                specific = max(matches, key=len)
                if specific.startswith("vang "):
                    matches = [i for i in matches if not (i == "vang" or specific.startswith(i + " "))]
            if matches:
                positive[kind] = tuple(dict.fromkeys(matches))
            if excluded:
                negative[kind] = tuple(dict.fromkeys(excluded))
        age = re.search(r"\b(\d{1,2})\s*tuoi\b", text)
        if age and int(age.group(1)) < 18 and ("female" in positive.get("audience", ()) or contains(text, "be gai")):
            positive["audience"] = ("female_child",)
            evidence.append({"kind": "audience", "canonical_id": "female_child", "method": "age_context",
                             "age": int(age.group(1)), "confidence": 1.0, "alias_version": self.config["version"]})
        # Semantic candidates are restricted to explicit field contexts. Similarity
        # cannot silently manufacture a mandatory facet from a general sentence.
        contexts = {"style": r"(?:phong cach|kieu dang|thiet ke)\s+(.+?)(?=\s+(?:duoi|tren|gia|cho|voi|khong)\b|$)",
                    "audience": r"(?:danh cho)\s+(.+?)(?=\s+(?:duoi|gia|phong cach)\b|$)"}
        for kind, pattern in contexts.items():
            mention = re.search(pattern, text)
            if not mention or kind in positive or kind in negative:
                continue
            if kind == "style" and mention.group(1).startswith(("voi ", "giong san pham", "tuong tu san pham")):
                continue  # A relative graph constraint is resolved from the verified seed.
            if self.semantic is None:
                ambiguous.append(f"Chưa xác định được {kind}: {mention.group(1)}")
                continue
            try:
                canonical, confidence, gap = self.semantic.resolve(kind, mention.group(1))
            except Exception:
                ambiguous.append(f"Chưa thể xác minh ngữ nghĩa {kind}; vui lòng mô tả rõ hơn.")
                continue
            evidence.append({"kind": kind, "canonical_id": canonical, "method": "embedding_cosine",
                             "confidence": confidence, "margin": gap, "alias_version": self.config["version"]})
            if canonical is None:
                ambiguous.append(f"Ngữ nghĩa {kind} còn nhập nhằng; vui lòng mô tả rõ hơn.")
            else:
                positive[kind] = (canonical,)
        return LinkingResult(positive, negative, tuple(evidence), tuple(ambiguous))
