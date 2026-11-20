"""Public catalog facts and retrieval contracts, independent of vendor SDKs."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol, Sequence


@dataclass(frozen=True)
class EntityFact:
    kind: str
    canonical_id: str
    name: str
    evidence: str
    source_field: str

    def __post_init__(self):
        if self.kind not in {"audience", "style", "occasion"} or not all(
                value.strip() for value in (self.canonical_id, self.name, self.evidence, self.source_field)):
            raise ValueError("Optional entity facts require identity and source evidence")


@dataclass(frozen=True)
class SourceLineage:
    source: str
    row: int
    sha256: str
    method: str = "structured"


@dataclass(frozen=True)
class Product:
    id: int
    sku: str
    name: str
    price: Decimal
    stock: int
    category: str
    brand: str
    material: str
    gemstone: str
    collection: str
    entity_ids: tuple[int, int, int, int, int]
    facts: tuple[EntityFact, ...] = ()
    lineage: SourceLineage | None = None
    published: bool = True

    def __post_init__(self):
        if type(self.id) is not int or not 0 < self.id <= 2147483647 or not self.name.strip() or not self.sku.strip():
            raise ValueError("Product identity, name and SKU are required")
        if (not self.price.is_finite() or not 0 <= self.price < Decimal("10000000000000000")
                or self.price != self.price.quantize(Decimal("0.01"))
                or type(self.stock) is not int or not 0 <= self.stock <= 2147483647):
            raise ValueError("Invalid price or stock")
        if len(self.entity_ids) != 5 or any(type(i) is not int or not 0 < i <= 2147483647 for i in self.entity_ids):
            raise ValueError("Five positive taxonomy IDs are required")
        if any(not value.strip() for value in (self.category, self.brand, self.material, self.gemstone, self.collection)):
            raise ValueError("Taxonomy names are required")

    @property
    def text(self) -> str:
        return ". ".join((str(self.id), self.sku, self.name, self.category, self.brand, self.material, self.gemstone,
                          self.collection, *(fact.name for fact in self.facts)))

    def public(self) -> dict:
        return {"ProductID": self.id, "SKU": self.sku, "ProductName": self.name,
                "Price": float(self.price), "PriceVND": format(self.price, "f"), "Stock": self.stock, "Category": self.category,
                "Brand": self.brand, "Material": self.material, "Gemstone": self.gemstone,
                "Collection": self.collection, **{f.kind.title(): f.name for f in self.facts}}


@dataclass(frozen=True)
class QueryContext:
    query: str
    top_k: int
    entities: dict[str, tuple[str, ...]] = field(default_factory=dict)
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    intent: str = "product_search"
    excluded_entities: dict[str, tuple[str, ...]] = field(default_factory=dict)
    linking_evidence: tuple[dict, ...] = ()
    ambiguities: tuple[str, ...] = ()
    seed_product_id: int | None = None
    candidate_k: int = 100
    required_relationships: tuple[str, ...] = ()
    product_id_filter: int | None = None


@dataclass(frozen=True)
class Candidate:
    product_id: int
    score: float
    reason: str = ""
    paths: tuple[dict, ...] = ()


class ProductRepository(Protocol):
    def all(self) -> Sequence[Product]: ...


class Retriever(Protocol):
    name: str
    def retrieve(self, context: QueryContext, limit: int) -> Sequence[Candidate]: ...


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> list[list[float]]: ...


class ProductWriter(Protocol):
    def upsert(self, products: Sequence[Product]) -> int: ...
