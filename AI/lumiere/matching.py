"""Hard constraints operate only on catalog facts with source evidence."""

from .configuration import load_aliases
from .domain import Product, QueryContext
from .text import contains, normalize


def matches_entity(product: Product, kind: str, canonical: str, aliases: dict) -> bool:
    if kind in {"audience", "style", "occasion"}:
        ids = {fact.canonical_id for fact in product.facts if fact.kind == kind}
        return canonical in ids or (kind == "audience" and canonical in {"female", "child"} and "female_child" in ids)
    value = normalize(getattr(product, kind, ""))
    terms = aliases.get(kind, {}).get(canonical, {}).get("aliases", [canonical])
    return any(contains(value, normalize(term)) for term in terms)


def eligible(product: Product, context: QueryContext) -> bool:
    if context.product_id_filter is not None and product.id != context.product_id_filter:
        return False
    if not product.published or product.stock <= 0:
        return False
    if context.min_price is not None and product.price < context.min_price:
        return False
    if context.max_price is not None and product.price > context.max_price:
        return False
    aliases = load_aliases()["entities"]
    if any(not any(matches_entity(product, kind, c, aliases) for c in concepts)
           for kind, concepts in context.entities.items()):
        return False
    return not any(any(matches_entity(product, kind, c, aliases) for c in concepts)
                   for kind, concepts in context.excluded_entities.items())
