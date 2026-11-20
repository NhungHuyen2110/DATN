"""Rank-based, deterministic reranking; never add raw cosine and lexical scores."""

from .domain import Product, QueryContext
from .text import contains, normalize


class ProductReranker:
    def rank(self, products: list[Product], fusion_scores: dict[int, float], context: QueryContext) -> list[tuple[Product, float]]:
        query = normalize(context.query)
        ranked = [(p, fusion_scores.get(p.id, 0.0) + (1.0 if contains(query, normalize(p.sku)) else 0.0)) for p in products]
        return sorted(ranked, key=lambda row: (-row[1], row[0].id))
