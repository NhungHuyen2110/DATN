"""Managed product projection; no connection or writes on import.

Only use on explicitly identified development databases. IDs, labels and edge
types follow the existing application contract. Input values are parameters.
"""
from decimal import Decimal
from pathlib import Path

try:
    from .csv_validation import LOOKUPS
except ImportError:
    from csv_validation import LOOKUPS


OWNER = "lumiere-products-v1"


class ProjectionConflict(ValueError):
    pass


def prepare_rows(records, source_file, source_sha256):
    rows = []
    for record in records:
        row = dict(record)
        price = Decimal(record["SalePrice"])
        snapshot = float(price)
        if Decimal(str(snapshot)) != price:
            raise ValueError("Price cannot be represented as legacy graph numeric snapshot without loss")
        row["properties"] = {
            "name": record["ProductName"], "sku": record["SKU"], "barcode": record["Barcode"],
            "weight": float(record["Weight"]), "sale_price": snapshot,
            "sale_price_decimal": str(price), "sale_price_minor": int(price * 100),
            "stock": record["Stock"], "projection_owner": OWNER, "is_deleted": False,
            "source_file": source_file, "source_row": record["source_row"],
            "source_sha256": source_sha256, "extraction_method": "structured",
        }
        rows.append(row)
    return rows


def write_batch(tx, rows):
    # Never silently take over legacy/unmanaged product projections.
    conflicts = tx.run("""
        UNWIND $rows AS row
        MATCH (p:Product {product_id: row.ProductID})
        WHERE p.projection_owner IS NULL OR p.projection_owner <> $owner
        RETURN count(p) AS conflicts
    """, rows=rows, owner=OWNER).single()["conflicts"]
    if conflicts:
        raise ProjectionConflict("Unmanaged product IDs exist; use a separate dev graph or reviewed migration")
    tx.run("""
        UNWIND $rows AS row
        MERGE (p:Product {product_id: row.ProductID})
        SET p += row.properties, p.indexed_at = datetime()
    """, rows=rows).consume()
    # Identifiers below come exclusively from this source-controlled whitelist.
    for label, (_, relationship) in LOOKUPS.items():
        key = label.lower() + "_id"
        unmanaged = tx.run(f"""
            UNWIND $rows AS row
            MATCH (p:Product {{product_id: row.ProductID}})-[edge:{relationship}]->()
            WHERE edge.projection_owner IS NULL OR edge.projection_owner <> $owner
            RETURN count(edge) AS conflicts
        """, rows=rows, owner=OWNER).single()["conflicts"]
        if unmanaged:
            raise ProjectionConflict("Unmanaged taxonomy relationships require reviewed migration")
        tx.run(f"""
            UNWIND $rows AS row
            MERGE (entity:{label} {{{key}: row.{label}ID}})
            SET entity.name = row.{label}Name
            WITH entity, row
            MATCH (p:Product {{product_id: row.ProductID}})
            OPTIONAL MATCH (p)-[old:{relationship}]->(previous)
            WHERE old.projection_owner = $owner AND previous <> entity
            DELETE old
            WITH DISTINCT p, entity, row
            MERGE (p)-[edge:{relationship}]->(entity)
            SET edge.projection_owner = $owner, edge.source_row = row.source_row,
                edge.source_sha256 = row.properties.source_sha256,
                edge.extraction_method = 'structured'
        """, rows=rows, owner=OWNER).consume()


def mark_deleted(driver, database, product_id):
    def tombstone(tx):
        conflict = tx.run('MATCH (p:Product {product_id:$id}) WHERE coalesce(p.projection_owner, "") <> $owner RETURN count(p) AS count',
                          id=product_id, owner=OWNER).single()['count']
        if conflict:
            raise ProjectionConflict('Cannot tombstone unmanaged product')
        tx.run('MATCH (p:Product {product_id:$id, projection_owner:$owner}) SET p.is_deleted=true, p.stock=0, p.indexed_at=datetime()',
               id=product_id, owner=OWNER).consume()
    with driver.session(database=database) as session:
        session.execute_write(tombstone)


def verify_projection(session, rows):
    """Verify requested IDs and exact single-value taxonomy endpoints, not global counts."""
    ids = [row["ProductID"] for row in rows]
    products = session.run("""
        MATCH (p:Product) WHERE p.product_id IN $ids
        RETURN count(p) AS count, count(DISTINCT p.product_id) AS distinct_count,
               sum(CASE WHEN p.projection_owner = $owner THEN 0 ELSE 1 END) AS unmanaged
    """, ids=ids, owner=OWNER).single()
    report = {"requested_products": len(ids), "products": products["count"],
              "duplicate_products": products["count"] - products["distinct_count"],
              "unmanaged_products": products["unmanaged"], "relationships": {}}
    for label, (_, relationship) in LOOKUPS.items():
        key = label.lower() + "_id"
        result = session.run(f"""
            UNWIND $rows AS row
            OPTIONAL MATCH (p:Product {{product_id: row.ProductID}})-[r:{relationship}]->(n)
            WITH row, count(r) AS total,
                 sum(CASE WHEN n:{label} AND n.{key} = row.{label}ID
                           AND r.projection_owner = $owner THEN 1 ELSE 0 END) AS correct
            RETURN sum(total) AS count,
                   sum(CASE WHEN total = 1 AND correct = 1 THEN 0 ELSE 1 END) AS violations
        """, rows=rows, owner=OWNER).single()
        report["relationships"][relationship] = dict(result)
    report["pass"] = (report["products"] == len(ids) and report["duplicate_products"] == 0
                      and report["unmanaged_products"] == 0
                      and all(item["violations"] == 0 for item in report["relationships"].values()))
    return report


def import_projection(driver, database, records, source_file, source_sha256, batch_size=100, progress=None):
    if not records or not 1 <= batch_size <= 10000:
        raise ValueError("Nonempty validated records and batch-size 1..10000 required")
    # Prepare ALL rows before any constraints or data writes.
    rows = prepare_rows(records, source_file, source_sha256)
    schema = Path(__file__).with_name("schema.cypher").read_text(encoding="utf-8-sig")
    statements = "\n".join(line for line in schema.splitlines() if not line.strip().startswith("//"))
    with driver.session(database=database) as session:
        conflicts = session.run("""
            MATCH (n)
            WHERE NOT any(label IN labels(n) WHERE label IN $allowed_labels)
               OR (n:Product AND coalesce(n.projection_owner, '') <> $owner)
            RETURN count(n) AS conflicts
        """, allowed_labels=['Product', *LOOKUPS], owner=OWNER).single()['conflicts']
        if conflicts:
            raise ProjectionConflict("Target contains unmanaged products or non-catalog data; refusing all writes")
        for statement in statements.split(";"):
            if statement.strip():
                session.run(statement).consume()
        for start in range(0, len(rows), batch_size):
            # Neo4j execute_write retries retryable failures within driver retry budget.
            session.execute_write(write_batch, rows[start:start + batch_size])
            if progress:
                progress(min(start + batch_size, len(rows)))
        return verify_projection(session, rows)
