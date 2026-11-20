"""Validate without services by default; --apply explicitly writes graph and vectors."""

import argparse
import json
import os
from pathlib import Path
from time import perf_counter

from lumiere.bootstrap import DEFAULT_MODEL, catalog_repository
from lumiere.catalog import CatalogValidationError, CsvProductRepository, validate_catalog
from lumiere.configuration import load_aliases, load_graph_schema


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--delimiter", default=",")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--target", choices=("graph", "vectors", "both"), default="both")
    parser.add_argument("--environment", choices=("test", "staging"))
    parser.add_argument("--neo4j-uri")
    parser.add_argument("--qdrant-url")
    parser.add_argument("--qdrant-local", type=Path)
    args = parser.parse_args(argv)
    if args.batch_size < 1 or (args.limit is not None and args.limit < 1):
        parser.error("batch-size/limit must be positive")
    if args.apply and (args.dry_run or args.verify_only):
        parser.error("--apply cannot be combined with --dry-run/--verify-only")
    if (args.apply or args.verify_only) and not args.environment:
        parser.error("Set --environment test|staging explicitly; production writes are not supported")
    report = {"status": "started", "alias_version": load_aliases()["version"], "schema_version": load_graph_schema()["version"]}
    started = perf_counter()

    def save():
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.report.with_suffix(args.report.suffix + ".tmp")
            temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(args.report)

    def progress(graph):
        report["graph_progress"] = graph
        save()

    try:
        repository = (CsvProductRepository(args.file, args.delimiter, args.limit) if args.file else catalog_repository())
        products = validate_catalog(repository.all())
        report["input"] = getattr(repository, "last_report", {"source": "postgres"})
        report["products"] = len(products)
        resume_ids = []
        if args.resume:
            previous = json.loads(args.resume.read_text(encoding="utf-8"))
            if any(previous.get(key) != report.get(key) for key in ("input", "alias_version", "schema_version")):
                raise ValueError("Resume source/schema/alias version differs")
            resume_ids = previous.get("graph_progress", {}).get("completed_ids", [])
        if not args.apply and not args.verify_only:
            report["status"] = "validated_only"
            save()
            print(json.dumps({"status": report["status"], "products": len(products)}))
            return 0
        from contextlib import ExitStack
        from lumiere.ingestion import Neo4jProductWriter
        from lumiere.adapters import QdrantProductIndex
        with ExitStack() as stack:
            if args.target in ("graph", "both"):
                if not args.neo4j_uri:
                    raise ValueError("--neo4j-uri must explicitly identify the isolated target")
                from neo4j import GraphDatabase
                secret = os.environ["NEO4J_TEST_PASSWORD" if args.environment == "test" else "NEO4J_PASSWORD"]
                driver = GraphDatabase.driver(args.neo4j_uri, auth=(os.getenv("NEO4J_USERNAME", "neo4j"), secret),
                                              connection_timeout=5, max_transaction_retry_time=5)
                stack.callback(driver.close)
                driver.verify_connectivity()
                writer = Neo4jProductWriter(driver, args.batch_size, progress, resume_ids)
                if args.apply:
                    writer.upsert(products)
                report["graph"] = writer.verify(products)
                save()
            if args.target in ("vectors", "both"):
                if not args.qdrant_url and not args.qdrant_local:
                    raise ValueError("Set explicit --qdrant-url or --qdrant-local target")
                from qdrant_client import QdrantClient
                from lumiere.bootstrap import SemanticModelProvider
                client = (QdrantClient(path=str(args.qdrant_local)) if args.qdrant_local else
                          QdrantClient(url=args.qdrant_url, timeout=30, check_compatibility=False))
                stack.callback(client.close)
                index = QdrantProductIndex(client, SemanticModelProvider(), os.getenv("QDRANT_COLLECTION", "lumiere_products_v2"),
                                          os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL), args.batch_size)
                count = index.upsert(products) if args.apply else index.verify(products)
                report["vectors"] = {"verified_products": count, "model": index.model_name, "collection": index.collection}
        report["status"] = "verified"
        return 0
    except CatalogValidationError as exc:
        report["status"], report["input"] = "invalid_input", exc.report
        return 1
    except Exception as exc:
        # Driver/model errors can include credentials or private paths. Keep only type.
        report["status"], report["error_type"] = "failed", type(exc).__name__
        return 1
    finally:
        report["elapsed_seconds"] = perf_counter()-started
        save()
        if report["status"] != "validated_only":
            print(json.dumps({"status": report["status"], "products": report.get("products", 0),
                              "error_type": report.get("error_type")}))


if __name__ == "__main__":
    raise SystemExit(main())
