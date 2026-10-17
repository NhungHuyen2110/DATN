"""Validate/import the original catalog. No writes without explicit --apply."""

import argparse
import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import sys

from sqlalchemy import Integer, Numeric, String, select, text
from sqlalchemy.exc import SQLAlchemyError


ROOT = Path(__file__).resolve().parents[2]
LOOKUPS = ("categories", "brands", "materials", "gemstones", "collections")
TABLES = (*LOOKUPS, "products")
EXPECTED_PRODUCTS = 500
PRODUCT_FIELDS = {
    "ProductID": "id", "SKU": "sku", "Barcode": "barcode",
    "ProductName": "name", "CategoryID": "category_id", "BrandID": "brand_id",
    "MaterialID": "material_id", "GemstoneID": "gemstone_id",
    "CollectionID": "collection_id", "Weight": "weight", "SalePrice": "sale_price",
    "WholesalePrice": "wholesale_price", "CostPrice": "cost_price", "Stock": "stock",
}
FOREIGN_KEYS = dict(zip(
    ("category_id", "brand_id", "material_id", "gemstone_id", "collection_id"), LOOKUPS
))
UNIQUE_FIELDS = {name: ("name",) for name in LOOKUPS}
UNIQUE_FIELDS["products"] = ("sku", "barcode")


class CatalogError(ValueError):
    """Input or existing catalog conflicts; stop without overwriting anything."""


def integer(value, label, minimum=1):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise CatalogError(f"{label}: phải là số nguyên.")
    if not re.fullmatch(r"[0-9]+", str(value)):
        raise CatalogError(f"{label}: phải là số nguyên không âm.")
    number = int(value)
    if not minimum <= number <= 2147483647:
        raise CatalogError(f"{label}: ngoài giới hạn Integer hoặc nhỏ hơn {minimum}.")
    return number


def string(value, label, limit):
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise CatalogError(f"{label}: chuỗi bắt buộc, không được rỗng hoặc chứa NUL.")
    if len(value) > limit:
        raise CatalogError(f"{label}: dài hơn {limit} ký tự.")
    return value  # Preserve the original text, including SKU/barcode leading zeros.


def decimal_value(value, label, precision=18, positive=False):
    try:
        number = Decimal(value)
        if not number.is_finite() or number < 0 or (positive and number == 0):
            raise CatalogError(f"{label}: giá trị phải hữu hạn và hợp lệ.")
        if number >= Decimal(10) ** (precision - 2):
            raise CatalogError(f"{label}: vượt giới hạn Numeric({precision}, 2).")
        if number != number.quantize(Decimal("0.01")):
            raise CatalogError(f"{label}: quá 2 chữ số thập phân; không tự làm tròn.")
        return number
    except (InvalidOperation, TypeError, ValueError) as exc:
        if isinstance(exc, CatalogError):
            raise
        raise CatalogError(f"{label}: số thập phân không hợp lệ.") from None


def json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError(f"JSON có khóa lặp: {key}.")
        result[key] = value
    return result


def check_unique(rows, table):
    for field in ("id", *UNIQUE_FIELDS[table]):
        seen = set()
        for row in rows:
            if row[field] in seen:
                raise CatalogError(f"{table}: trùng {field} trong dữ liệu nguồn.")
            seen.add(row[field])


def parse_products(handle):
    reader = csv.DictReader(handle)
    if (reader.fieldnames is None or len(reader.fieldnames) != len(PRODUCT_FIELDS)
            or set(reader.fieldnames) != set(PRODUCT_FIELDS)):
        raise CatalogError("products.csv: cột thiếu, thừa hoặc trùng so với định dạng gốc.")
    rows = []
    for line, raw in enumerate(reader, 2):
        if None in raw or any(value is None for value in raw.values()):
            raise CatalogError(f"products.csv dòng {line}: sai số lượng cột.")
        row = {}
        for source, target in PRODUCT_FIELDS.items():
            label = f"products.csv dòng {line}, {source}"
            value = raw[source]
            if target == "stock" or target == "id" or target.endswith("_id"):
                row[target] = integer(value, label, minimum=0 if target == "stock" else 1)
            elif target in ("sku", "barcode", "name"):
                row[target] = string(value, label, 255 if target == "name" else 50)
            else:
                row[target] = decimal_value(
                    value, label, precision=10 if target == "weight" else 18,
                    positive=target == "weight",
                )
        rows.append(row)
    if len(rows) != EXPECTED_PRODUCTS:
        raise CatalogError(f"Cần đúng {EXPECTED_PRODUCTS} sản phẩm; nhận được {len(rows)}.")
    check_unique(rows, "products")
    return rows


def load_sources(root=ROOT):
    sources = {}
    for table in LOOKUPS:
        path = root / "data" / (table + ".json")
        raw = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=json_pairs)
        if not isinstance(raw, list) or not raw:
            raise CatalogError(f"{table}: cần một danh sách không rỗng.")
        rows = []
        for index, item in enumerate(raw, 1):
            if not isinstance(item, dict) or set(item) != {"id", "name"}:
                raise CatalogError(f"{table} mục {index}: cần đúng hai trường id, name.")
            rows.append({
                "id": integer(item["id"], f"{table} mục {index}, id"),
                "name": string(item["name"], f"{table} mục {index}, name", 150),
            })
        check_unique(rows, table)
        sources[table] = rows
    with (root / "output/products.csv").open(encoding="utf-8-sig", newline="") as handle:
        sources["products"] = parse_products(handle)
    lookup_ids = {name: {row["id"] for row in sources[name]} for name in LOOKUPS}
    for row in sources["products"]:
        for field, table in FOREIGN_KEYS.items():
            if row[field] not in lookup_ids[table]:
                raise CatalogError(f"ProductID {row['id']}: {field} không có trong nguồn {table}.")
    return sources


def load_models():
    # Lazy import: parsing files and --help never open a DB connection.
    from app.models import Brand, Category, Collection, Gemstone, Material, Product
    return dict(zip(TABLES, (Category, Brand, Material, Gemstone, Collection, Product)))


def check_models(sources, models):
    """Reject drift rather than adapting the database or silently losing fields."""
    for name in TABLES:
        table = models[name].__table__
        if set(table.c.keys()) != set(sources[name][0]):
            raise CatalogError(f"{name}: cột model đã thay đổi; cần kiểm tra lại chương trình.")
        if not table.c.id.primary_key or table.c.id.autoincrement is not False:
            raise CatalogError(f"{name}: model phải nhận ID nguồn tường minh.")
        for column in table.c:
            for row in sources[name]:
                value = row[column.name]
                if value is None and not column.nullable:
                    raise CatalogError(f"{name}.{column.name}: không được NULL.")
                if isinstance(column.type, String):
                    string(value, f"{name}.{column.name}", column.type.length)
                elif isinstance(column.type, Numeric):
                    if column.type.scale != 2:
                        raise CatalogError(f"{name}.{column.name}: scale của model đã thay đổi.")
                    decimal_value(value, f"{name}.{column.name}", column.type.precision,
                                  positive=column.name == "weight")
                elif not isinstance(column.type, Integer):
                    raise CatalogError(f"{name}.{column.name}: kiểu model chưa được hỗ trợ.")
        if name == "products":
            actual = {fk.parent.name: fk.target_fullname for fk in table.foreign_keys}
            expected = {field: target + ".id" for field, target in FOREIGN_KEYS.items()}
            if actual != expected:
                raise CatalogError("products: khóa ngoại model không khớp dữ liệu nguồn.")


def plan_table(table, incoming, existing):
    by_id = {row["id"]: row for row in existing}
    owners = {
        field: {row[field]: row["id"] for row in existing}
        for field in UNIQUE_FIELDS[table]
    }
    missing = []
    skipped = 0
    for row in incoming:
        current = by_id.get(row["id"])
        if current is not None:
            changed = [field for field in row if current[field] != row[field]]
            if changed:
                raise CatalogError(
                    f"{table} ID {row['id']}: dữ liệu khác ở {', '.join(changed)}; dừng, không ghi đè."
                )
            skipped += 1
        else:
            for field, index in owners.items():
                if row[field] in index:
                    raise CatalogError(
                        f"{table} ID {row['id']}: {field} đã thuộc ID {index[row[field]]}; dừng."
                    )
            missing.append(row)
    return missing, skipped


def build_plan(db, sources, models):
    plan = {}
    for name in TABLES:
        table = models[name].__table__
        existing = db.execute(select(table)).mappings().all()
        plan[name] = plan_table(name, sources[name], existing)
    return plan


def insert_plan(db, plan, models):
    for name in TABLES:
        missing, _ = plan[name]
        db.add_all(models[name](**row) for row in missing)
        # Flush parents before products. Commit only after ALL tables succeed.
        db.flush()


def database_run(sources, models, apply=False):
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        with db.begin():
            if not apply:
                db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            else:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                # Fixed identifiers only. Block concurrent catalog writes until commit.
                db.execute(text(
                    "LOCK TABLE brands, categories, collections, gemstones, materials, products "
                    "IN SHARE ROW EXCLUSIVE MODE"
                ))
            plan = build_plan(db, sources, models)
            if apply:
                insert_plan(db, plan, models)
    return plan


def main(argv=None):
    # Windows redirected consoles may default to an encoding without Vietnamese.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true", help="Kiểm tra file và model, không kết nối DB")
    mode.add_argument("--dry-run", action="store_true", help="Kiểm tra file và đối chiếu DB bằng transaction chỉ đọc")
    mode.add_argument("--apply", action="store_true", help="Import thật trong một transaction")
    args = parser.parse_args(argv)
    try:
        sources = load_sources()
        models = load_models()
        check_models(sources, models)
        for name in TABLES:
            print(f"Nguồn {name}: {len(sources[name])}")
        if args.validate_only:
            print("HỢP LỆ: dữ liệu nguồn khớp model; không kết nối database.")
            return 0
        plan = database_run(sources, models, apply=args.apply)
        for name, (missing, skipped) in plan.items():
            print(f"{name}: {'đã thêm' if args.apply else 'sẽ thêm'} {len(missing)}, giống hệt/bỏ qua {skipped}")
        print("ĐÃ COMMIT toàn bộ catalog." if args.apply else "DRY-RUN: không ghi dữ liệu; kết quả có thể đổi trước lần import thật.")
        return 0
    except CatalogError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error):
        print("LỖI: không đọc được dữ liệu nguồn hoặc định dạng không hợp lệ.", file=sys.stderr)
    except SQLAlchemyError as exc:
        # Driver exception strings may include SQL parameters; do not print them.
        print(f"LỖI database ({type(exc).__name__}); transaction đã bị hủy. Kiểm tra kết nối, migration, quyền hoặc xung đột.", file=sys.stderr)
    except (KeyError, ImportError):
        print("LỖI: thiếu cấu hình môi trường hoặc dependency Backend.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
