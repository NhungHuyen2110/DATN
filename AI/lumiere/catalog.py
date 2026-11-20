"""Validated catalog adapters. No private customer or purchase-cost fields."""

import csv
import hashlib
import re
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from .domain import EntityFact, Product, SourceLineage
from .configuration import load_aliases
from .text import normalize, nfc

TAXONOMY = ("Category", "Brand", "Material", "Gemstone", "Collection")


def validate_catalog(products: Iterable[Product]) -> tuple[Product, ...]:
    result = tuple(products)
    ids, skus, names = set(), set(), {}
    for product in result:
        if product.id in ids or product.sku in skus:
            raise ValueError(f"Duplicate product ID or SKU: {product.id}")
        ids.add(product.id)
        skus.add(product.sku)
        for kind, ident, name in zip(TAXONOMY, product.entity_ids,
                                     (product.category, product.brand, product.material, product.gemstone, product.collection)):
            key = kind, ident
            if key in names and names[key] != name:
                raise ValueError(f"Conflicting taxonomy identity: {key}")
            names[key] = name
    if not result:
        raise ValueError("Catalog is empty; refusing to synchronize")
    return result


class CatalogValidationError(ValueError):
    def __init__(self, report: dict):
        self.report = report
        super().__init__(f"Catalog validation failed: {len(report['errors'])} errors; no records written")


def required_text(row: dict, key: str) -> str:
    value = row.get(key)
    if value is None or not str(value).strip() or str(value).strip().lower() in {"null", "none", "nan"}:
        raise ValueError(f"Missing required field: {key}")
    value = nfc(str(value).strip())
    if "\x00" in value:
        raise ValueError(f"NUL character in {key}")
    return value


def numeric_price(raw: str) -> Decimal:
    # Explicit locale grouping; no unit conversion or guess at product prices.
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", raw):
        raw = raw.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?", raw):
        raw = raw.replace(",", "")
    elif re.fullmatch(r"\d+,\d{1,2}", raw):
        raw = raw.replace(",", ".")
    return Decimal(raw)


def from_row(row: dict) -> Product:
    facts, definitions = [], load_aliases()["entities"]
    for kind, column in (("audience", "Audience"), ("style", "Style"), ("occasion", "Occasion")):
        fields = [row.get(column + suffix, "") or "" for suffix in ("ID", "Name", "Evidence")]
        if not any(str(v).strip() for v in fields):
            continue
        if not all(str(v).strip() for v in fields):
            raise ValueError(f"{column} requires ID, Name and Evidence together")
        canonical, name, evidence = (nfc(str(v).strip()) for v in fields)
        concept = definitions[kind].get(canonical)
        if concept is None or normalize(name) not in {normalize(v) for v in [concept["name"], *concept["aliases"]]}:
            raise ValueError(f"Unknown/conflicting canonical {column}")
        facts.append(EntityFact(kind, canonical, concept["name"], evidence, column + "Evidence"))
    published = row.get("Published", "true")
    if str(published).lower() not in {"true", "false", "1", "0"}:
        raise ValueError("Published must be true/false or 1/0")
    return Product(int(required_text(row, "ProductID")), required_text(row, "SKU"), required_text(row, "ProductName"),
                   numeric_price(required_text(row, "SalePrice")), int(required_text(row, "Stock")),
                   *(required_text(row, f"{kind}Name") for kind in TAXONOMY),
                   tuple(int(required_text(row, f"{kind}ID")) for kind in TAXONOMY),
                   tuple(facts), published=str(published).lower() in {"true", "1"})


class CsvProductRepository:
    def __init__(self, path: Path, delimiter: str = ",", limit: int | None = None):
        self.path, self.delimiter, self.limit = path, delimiter, limit
        self.last_report = {}

    def all(self) -> tuple[Product, ...]:
        from dataclasses import replace
        if len(self.delimiter) != 1 or (self.limit is not None and self.limit < 1):
            raise ValueError("Invalid delimiter or limit")
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        report = {"source": self.path.name, "sha256": digest, "rows_read": 0, "valid_records": 0, "errors": []}
        self.last_report = report
        products = []
        required = {"ProductID", "SKU", "ProductName", "SalePrice", "Stock"} | {kind + suffix for kind in TAXONOMY for suffix in ("ID", "Name")}
        with self.path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, delimiter=self.delimiter)
            header = reader.fieldnames or []
            if len(header) != len(set(header)) or required - set(header):
                report["errors"].append({"row": 1, "code": "invalid_header", "missing": sorted(required-set(header))})
                raise CatalogValidationError(report)
            for row in reader:
                if self.limit is not None and report["rows_read"] >= self.limit:
                    break
                report["rows_read"] += 1
                try:
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError("CSV row width differs from header")
                    product = from_row(row)
                    products.append(replace(product, lineage=SourceLineage(self.path.name, reader.line_num, digest)))
                except (ValueError, ArithmeticError) as exc:
                    report["errors"].append({"row": reader.line_num, "code": "invalid_record", "message": str(exc)})
        report["valid_records"] = len(products)
        try:
            result = validate_catalog(products)
        except ValueError as exc:
            report["errors"].append({"row": None, "code": "catalog_invariant", "message": str(exc)})
        if report["errors"]:
            raise CatalogValidationError(report)
        return result


class SnapshotProductRepository:
    def __init__(self, products: Iterable[Product]):
        self.products = validate_catalog(products)

    def all(self) -> tuple[Product, ...]:
        return self.products


class PostgresProductRepository:
    """Connection factory owns credentials; one query gives a consistent catalog view."""

    def __init__(self, connect):
        self.connect = connect

    def all(self) -> tuple[Product, ...]:
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute('''
                SELECT p.id, p.sku, p.name, p.sale_price, p.stock,
                       c.name, b.name, m.name, g.name, co.name,
                       p.category_id, p.brand_id, p.material_id, p.gemstone_id, p.collection_id
                FROM products p
                JOIN categories c ON c.id = p.category_id
                JOIN brands b ON b.id = p.brand_id
                JOIN materials m ON m.id = p.material_id
                JOIN gemstones g ON g.id = p.gemstone_id
                JOIN collections co ON co.id = p.collection_id
                ORDER BY p.id
            ''')
            return validate_catalog(Product(*row[:10], tuple(row[10:])) for row in cursor.fetchall())
