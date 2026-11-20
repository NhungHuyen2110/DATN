"""Accent tolerant Vietnamese aliases and explicit price constraints."""

from decimal import Decimal
import re

from .domain import QueryContext


class QueryError(ValueError):
    pass


from .text import normalize, contains
from .linking import EntityLinkingService, folded_aliases

ALIASES = folded_aliases()  # Backwards-compatible read-only alias view.


MONEY = r"(\d+(?:[.,]\d+)?)\s*(trieu|tr|nghin|ngan|k|tram)?\b"


def money(value: str, unit: str | None) -> Decimal:
    scale = {"trieu": 1_000_000, "tr": 1_000_000, "nghin": 1000, "ngan": 1000, "k": 1000, "tram": 100}
    return Decimal(value.replace(",", ".")) * scale.get(unit, 1)


def price_bounds(query: str) -> tuple[Decimal | None, Decimal | None]:
    text = normalize(query)
    interval = re.search(r"tu\s*" + MONEY + r"\s*(?:den|toi|-)\s*" + MONEY, text)
    if interval:
        a, ua, b, ub = interval.groups()
        low, high = money(a, ua or ub), money(b, ub or ua)
        if low > high:
            raise QueryError("Khoảng giá không hợp lệ")
        return low, high
    lower = re.search(r"(?:tren|>=|tu)\s*" + MONEY, text)
    upper = re.search(r"(?:duoi|<=|khong qua|toi da|ngan sach|budget|tam gia|gia khoang|tam|khoang)\s*(?:khoang|tam|la)?\s*" + MONEY, text)
    return (money(*lower.groups()) if lower else None,
            money(*upper.groups()) if upper else None)


class QueryUnderstandingService:
    def __init__(self, linker: EntityLinkingService, candidate_k: int = 100):
        self.linker = linker
        self.candidate_k = candidate_k

    def understand(self, query: str, top_k: int) -> QueryContext:
        if not query.strip() or not 1 <= top_k <= 20:
            raise QueryError("Query and top_k (1..20) are required")
        low, high = price_bounds(query)
        linked = self.linker.resolve(query)
        seed = re.search(r"\b(?:san pham\s*#?\s*|sp0*)(\d+)\b", normalize(query))
        relative = any(contains(normalize(query), phrase) for phrase in ("giong", "cung", "tuong tu"))
        relationships = []
        for phrase, relationship in (("cung da", "HAS_GEMSTONE"), ("cung loai da", "HAS_GEMSTONE"),
                                      ("cung chat lieu", "MADE_OF"), ("phong cach", "HAS_STYLE")):
            if relative and contains(normalize(query), phrase):
                relationships.append(relationship)
        return QueryContext(query.strip(), top_k, linked.entities, low, high,
                            "recommendation" if relative or contains(normalize(query), "goi y") else "product_search",
                            linked.excluded, linked.evidence, linked.ambiguities,
                            int(seed.group(1)) if seed and relative else None, max(top_k * 5, self.candidate_k),
                            tuple(dict.fromkeys(relationships)), int(seed.group(1)) if seed and not relative else None)


def requested_top_k(query: str) -> int | None:
    match = re.search(r"\btop\s*(\d+)\b", normalize(query))
    return int(match.group(1)) if match else None
