"""Replayable, non-destructive graph/vector synchronization."""

from .catalog import TAXONOMY, validate_catalog
from .domain import ProductRepository, ProductWriter
from .configuration import load_graph_schema
from time import perf_counter

RELATIONSHIPS = ("BELONGS_TO", "HAS_BRAND", "MADE_OF", "HAS_GEMSTONE", "IN_COLLECTION")


class Neo4jProductWriter:
    def __init__(self, driver, batch_size: int = 100, progress=None, resume_ids=()):
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.driver = driver
        self.batch_size, self.progress, self.resume_ids = batch_size, progress, set(resume_ids)
        self.last_report = {}

    def upsert(self, products) -> int:
        products = validate_catalog(products)
        started, completed = perf_counter(), []
        schema = load_graph_schema()
        with self.driver.session() as session:
            definitions = [{"label": "Product", "key": "product_id"}, *schema["taxonomy"], *schema["evidence_facets"]]
            for definition in definitions:
                label, key = definition["label"], definition["key"]
                session.run(f"CREATE CONSTRAINT lumiere_{label.lower()}_{key}_unique IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE").consume()
            for offset in range(0, len(products), self.batch_size):
                batch = products[offset:offset+self.batch_size]
                if all(p.id in self.resume_ids for p in batch):
                    session.execute_read(self._verify, self._rows(batch))
                    session.execute_read(self._verify_facts, batch)
                else:
                    session.execute_write(self._write, batch)
                completed.extend(p.id for p in batch)
                self.last_report = {"verified_products": len(completed), "completed_ids": list(completed),
                                    "batch_size": self.batch_size, "schema_version": schema["version"],
                                    "elapsed_seconds": perf_counter()-started}
                if self.progress:
                    self.progress(self.last_report)
        return len(completed)

    @staticmethod
    def _rows(products):
        rows = []
        for p in products:
            row = {"id": p.id, "sku": p.sku, "name": p.name, "price": float(p.price), "price_exact": format(p.price, "f"),
                   "stock": p.stock, "published": p.published, "source": p.lineage.source if p.lineage else "catalog",
                   "source_row": p.lineage.row if p.lineage else p.id,
                   "source_sha256": p.lineage.sha256 if p.lineage else None}
            for kind, ident, name in zip(TAXONOMY, p.entity_ids, (p.category, p.brand, p.material, p.gemstone, p.collection)):
                row[kind.lower() + "_id"], row[kind.lower() + "_name"] = ident, name
            rows.append(row)
        return rows

    @staticmethod
    def _write(tx, products):
        rows = Neo4jProductWriter._rows(products)
        tx.run('''UNWIND $rows AS row
                  MERGE (p:Product {product_id: row.id})
                  SET p.sku=row.sku, p.name=row.name, p.sale_price=row.price, p.price_exact=row.price_exact,
                      p.stock=row.stock, p.published=row.published, p.source_file=row.source,
                      p.source_row=row.source_row, p.source_sha256=row.source_sha256,
                      p.extraction_method='structured' ''', rows=rows).consume()
        for kind, relationship in zip(TAXONOMY, RELATIONSHIPS):
            key = kind.lower()
            # All label/type identifiers come from constants, values are parameters.
            tx.run(f'''UNWIND $rows AS row
                MATCH (p:Product {{product_id: row.id}})
                MERGE (e:{kind} {{{key}_id: row.{key}_id}})
                SET e.name = row.{key}_name
                WITH p, e
                OPTIONAL MATCH (p)-[stale:{relationship}]->(old:{kind}) WHERE old <> e
                DELETE stale
                MERGE (p)-[:{relationship}]->(e)''', rows=rows).consume()
        for spec in load_graph_schema()["evidence_facets"]:
            facts = [{"product_id": p.id, "id": f.canonical_id, "name": f.name,
                      "evidence": f.evidence, "source_field": f.source_field}
                     for p in products for f in p.facts if f.kind == spec["kind"]]
            if not facts:
                continue
            label, relationship = spec["label"], spec["relationship"]
            tx.run(f'''UNWIND $facts AS row
                MATCH (p:Product {{product_id:row.product_id}})
                MERGE (e:{label} {{canonical_id:row.id}}) SET e.name=row.name
                WITH p,e,row
                OPTIONAL MATCH (p)-[stale:{relationship}]->(old:{label}) WHERE old <> e
                DELETE stale
                MERGE (p)-[fact:{relationship}]->(e)
                SET fact.evidence=row.evidence, fact.source_field=row.source_field,
                    fact.extraction_method='structured', fact.source_record_id=row.product_id
            ''', facts=facts).consume()
            count = tx.run(f'''UNWIND $facts AS row
                MATCH (p:Product {{product_id:row.product_id}})-[r:{relationship}]->(e:{label} {{canonical_id:row.id}})
                WHERE r.evidence=row.evidence AND r.source_field=row.source_field
                RETURN count(p) AS count''', facts=facts).single()["count"]
            if count != len(facts):
                raise RuntimeError("Neo4j optional fact/evidence verification failed")
        return Neo4jProductWriter._verify(tx, rows)

    @staticmethod
    def _verify_facts(tx, products):
        for spec in load_graph_schema()["evidence_facets"]:
            facts = [{"id": p.id, "canonical": f.canonical_id, "name": f.name,
                      "evidence": f.evidence, "source_field": f.source_field}
                     for p in products for f in p.facts if f.kind == spec["kind"]]
            if not facts:
                continue
            count = tx.run(f'''UNWIND $facts AS row
                MATCH (p:Product {{product_id:row.id}})-[r:{spec['relationship']}]->(e:{spec['label']})
                WHERE e.canonical_id=row.canonical AND e.name=row.name
                    AND r.evidence=row.evidence AND r.source_field=row.source_field
                RETURN count(p) AS count''', facts=facts).single()["count"]
            if count != len(facts):
                raise RuntimeError("Neo4j optional fact verification failed")

    @staticmethod
    def _verify(tx, rows):
        verified = tx.run('''UNWIND $rows AS row
            MATCH (p:Product {product_id: row.id})
            WHERE p.sku=row.sku AND p.name=row.name AND p.price_exact=row.price_exact AND p.stock=row.stock
                AND p.published=row.published AND coalesce(p.source_sha256,'')=coalesce(row.source_sha256,'')
            RETURN count(p) AS count''', rows=rows).single()["count"]
        if verified != len(rows):
            raise RuntimeError("Neo4j product verification failed")
        for kind, relationship in zip(TAXONOMY, RELATIONSHIPS):
            key = kind.lower()
            count = tx.run(f'''UNWIND $rows AS row
                MATCH (p:Product {{product_id:row.id}})-[:{relationship}]->(e:{kind})
                WHERE e.{key}_id=row.{key}_id AND e.name=row.{key}_name
                RETURN count(p) AS count''', rows=rows).single()["count"]
            if count != len(rows):
                raise RuntimeError("Neo4j relationship verification failed")
        return verified

    def verify(self, products) -> dict:
        products = validate_catalog(products)
        with self.driver.session() as session:
            verified = session.execute_read(self._verify, self._rows(products))
            session.execute_read(self._verify_facts, products)
            ids = [p.id for p in products]
            node_counts = {}
            schema = load_graph_schema()
            for label in ["Product", *(r["label"] for r in schema["taxonomy"] + schema["evidence_facets"])]:
                node_counts[label] = session.run(f"MATCH (n:{label}) RETURN count(n) AS count").single()["count"]
            relationships = {r["relationship"]: session.run(
                f"MATCH (p:Product)-[r:{r['relationship']}]->() WHERE p.product_id IN $ids RETURN count(r) AS count", ids=ids
            ).single()["count"] for r in schema["taxonomy"] + schema["evidence_facets"]}
            orphan_ids = [r["id"] for r in session.run('''MATCH (p:Product)
                WHERE p.product_id IN $ids AND NOT (p)-[:BELONGS_TO]->(:Category)
                RETURN p.product_id AS id''', ids=ids)]
        if orphan_ids:
            raise RuntimeError("Imported product orphan invariant failed")
        return {"verified_products": verified, "node_counts": node_counts, "relationship_counts": relationships,
                "orphan_ids": orphan_ids, "schema_version": schema["version"]}


class ProductSyncService:
    def __init__(self, repository: ProductRepository, graph_writer: ProductWriter, vector_index: ProductWriter):
        self.repository, self.graph_writer, self.vector_index = repository, graph_writer, vector_index

    def synchronize(self) -> dict:
        products = validate_catalog(self.repository.all())
        # Each target verifies completion. Cross-store atomicity is not claimed;
        # replay on failure converges using stable IDs and upserts.
        graph = self.graph_writer.upsert(products)
        vectors = self.vector_index.upsert(products)
        return {"products": len(products), "graph_verified": graph, "vectors_verified": vectors}
