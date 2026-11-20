"""Resolve seed identities and verify graph evidence against live catalog facts."""

from dataclasses import replace
from .domain import Product, QueryContext
from .text import contains, normalize

RELATIONSHIP_FIELDS = {"BELONGS_TO": ("category", 0), "MADE_OF": ("material", 2), "HAS_GEMSTONE": ("gemstone", 3)}
FACT_RELATIONSHIPS = {"HAS_STYLE": "style", "SUITABLE_FOR": "audience", "FOR_OCCASION": "occasion"}


class RecommendationService:
    def plan(self, context: QueryContext, products: dict[int, Product]) -> QueryContext:
        if context.seed_product_id is not None:
            return context
        query = normalize(context.query)
        if not any(contains(query, phrase) for phrase in ("giong", "cung", "tuong tu")):
            exact_skus = [p for p in products.values() if contains(query, normalize(p.sku))]
            if len(exact_skus) == 1:
                return replace(context, product_id_filter=exact_skus[0].id)
            return context
        matched = [p for p in products.values() if contains(query, normalize(p.sku)) or contains(query, normalize(p.name))]
        sku_matches = [p for p in matched if contains(query, normalize(p.sku))]
        if sku_matches:
            matched = sku_matches
        if len(matched) == 1:
            return replace(context, seed_product_id=matched[0].id, intent="recommendation")
        if len(matched) > 1:
            return replace(context, ambiguities=(*context.ambiguities, "Tên sản phẩm trùng; vui lòng cung cấp SKU hoặc ProductID."))
        return context


def path_supported(path: dict, products: dict[int, Product]) -> bool:
    target = products.get(path.get("target_product_id"))
    source_id = path.get("source_product_id")
    source = products.get(source_id) if source_id is not None else None
    if target is None or (source_id is not None and source is None):
        return False
    relationship, ident = path.get("relationship"), path.get("entity_id")
    if relationship in RELATIONSHIP_FIELDS:
        kind, index = RELATIONSHIP_FIELDS[relationship]
        return all(p.entity_ids[index] == ident and getattr(p, kind) == path.get("entity_name") for p in (target, source) if p is not None)
    kind = FACT_RELATIONSHIPS.get(relationship)
    if kind is None:
        return False
    return all(any(f.kind == kind and f.canonical_id == ident and f.name == path.get("entity_name") for f in p.facts)
               for p in (target, source) if p is not None)
