"""Offline preflight for the existing products_ai.csv -> Neo4j importer.

Uses the actual CSV contract and authoritative lookup JSON. No driver, pandas,
model, .env, customer data, or database connection is imported by this module.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import unicodedata


ROOT = Path(__file__).resolve().parents[2]
LOOKUPS = {
    "Category": ("categories", "BELONGS_TO"),
    "Brand": ("brands", "HAS_BRAND"),
    "Material": ("materials", "MADE_OF"),
    "Gemstone": ("gemstones", "HAS_GEMSTONE"),
    "Collection": ("collections", "IN_COLLECTION"),
}
BASE_FIELDS = {"ProductID", "SKU", "Barcode", "ProductName", "Weight", "SalePrice",
               "WholesalePrice", "CostPrice", "Stock"}
FIELDS = BASE_FIELDS | {prefix + suffix for prefix in LOOKUPS for suffix in ("ID", "Name")}


def integer(value: str, minimum: int = 1) -> int:
    if not re.fullmatch(r"[0-9]+", value or ""):
        raise ValueError("invalid_integer")
    number = int(value)
    if not minimum <= number <= 2147483647:
        raise ValueError("integer_out_of_range")
    return number


def decimal(value: str, precision: int = 18, positive: bool = False) -> Decimal:
    try:
        number = Decimal(value)
        if (not number.is_finite() or number < 0 or (positive and number == 0)
                or number >= Decimal(10) ** (precision - 2)
                or number.as_tuple().exponent < -2):
            raise ValueError("invalid_decimal")
        return number
    except (InvalidOperation, TypeError):
        raise ValueError("invalid_decimal") from None


def text(value: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value or len(value) > maximum:
        raise ValueError("invalid_text")
    return unicodedata.normalize("NFC", value)


def load_lookups(directory: Path) -> dict:
    result = {}
    for prefix, (filename, _) in LOOKUPS.items():
        entries = json.loads((directory / (filename + ".json")).read_text(encoding="utf-8-sig"))
        if not isinstance(entries, list) or not entries:
            raise ValueError("invalid_lookup_list")
        by_id = {}
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"id", "name"} or type(entry["id"]) is not int:
                raise ValueError("invalid_lookup_record")
            key = integer(str(entry["id"]))
            if key in by_id:
                raise ValueError("duplicate_lookup_id")
            by_id[key] = text(entry["name"], 150)
        result[prefix] = by_id
    return result


def validate_csv(path: Path, lookup_directory: Path, delimiter: str = ",", limit: int | None = None) -> dict:
    if len(delimiter) != 1:
        raise ValueError("delimiter_must_be_one_character")
    if limit is not None and limit < 1:
        raise ValueError("limit_must_be_positive")
    lookups = load_lookups(lookup_directory)
    errors, records = [], []
    seen = {field: set() for field in ("ProductID", "SKU", "Barcode")}
    rows_seen = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames or len(reader.fieldnames) != len(FIELDS) or set(reader.fieldnames) != FIELDS:
            return {"records": [], "errors": [{"row": 1, "field": "header", "code": "schema_mismatch"}],
                    "rows_seen": 0, "scope": "invalid_header"}
        for row_number, raw in enumerate(reader, 2):
            if limit is not None and rows_seen >= limit:
                break
            rows_seen += 1
            if None in raw or any(value is None for value in raw.values()):
                errors.append({"row": row_number, "field": "row", "code": "wrong_column_count"})
                continue
            record = {"source_row": row_number}
            row_errors = []
            for field, value in raw.items():
                try:
                    if field == "Stock" or field.endswith("ID"):
                        converted = integer(value, minimum=0 if field == "Stock" else 1)
                    elif field in {"Weight", "SalePrice", "WholesalePrice", "CostPrice"}:
                        converted = str(decimal(value, precision=10 if field == "Weight" else 18,
                                                positive=field == "Weight"))
                    elif field in {"SKU", "Barcode"}:
                        text(value, 50)
                        converted = value  # Preserve original SKU/barcode, including leading zeroes.
                    else:
                        converted = text(value, 255 if field == "ProductName" else 150)
                    record[field] = converted
                    if field in seen:
                        if converted in seen[field]:
                            raise ValueError("duplicate_identity")
                        seen[field].add(converted)
                except ValueError as exc:
                    row_errors.append({"row": row_number, "field": field, "code": str(exc)})
            for prefix, lookup in lookups.items():
                key = record.get(prefix + "ID")
                if key is not None and key not in lookup:
                    row_errors.append({"row": row_number, "field": prefix + "ID", "code": "unknown_foreign_key"})
                elif key is not None and record.get(prefix + "Name") != lookup[key]:
                    row_errors.append({"row": row_number, "field": prefix + "Name", "code": "lookup_name_mismatch"})
            errors.extend(row_errors)
            if not row_errors:
                records.append(record)
    if not rows_seen:
        errors.append({"row": 1, "field": "row", "code": "empty_dataset"})
    return {"records": records, "errors": errors, "rows_seen": rows_seen,
            "scope": "prefix_only" if limit is not None else "whole_file"}


def summary(result: dict, path: Path) -> dict:
    counts = {prefix: len({row[prefix + "ID"] for row in result["records"]}) for prefix in LOOKUPS}
    counts["Product"] = len(result["records"])
    return {"mode": "dry-run", "source_file": path.name,
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "scope": result["scope"], "rows_seen": result["rows_seen"],
            "valid_records": len(result["records"]), "errors": result["errors"],
            "planned_nodes": counts,
            "planned_relationships": {rel: len(result["records"]) for _, rel in LOOKUPS.values()},
            "write_allowed": False,
            "notes": ["Counts are a plan, not live graph measurements.",
                      "Any error must block the entire import, including valid rows.",
                      "No Audience/Style facts inferred from product names.",
                      "CSV prices/stock must never overwrite PostgreSQL business data."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--lookup-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--delimiter", default=",")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true", help="Always dry-run; provided for explicit operation")
    parser.add_argument("--report", type=Path, help="Create a new report, never overwrite")
    args = parser.parse_args()
    try:
        result = validate_csv(args.file, args.lookup_dir, args.delimiter, args.limit)
        report = summary(result, args.file)
    except (OSError, ValueError, csv.Error) as exc:
        # Input errors must not print record contents or credentials.
        print(json.dumps({"mode": "dry-run", "error_type": type(exc).__name__, "write_allowed": False}))
        return 2
    if args.report:
        with args.report.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
