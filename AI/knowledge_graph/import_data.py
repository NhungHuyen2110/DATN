"""Product-only CSV -> Neo4j CLI; dry-run default, explicit isolated-dev apply.

Never imports customers/orders, reads .env, deletes a graph, or connects on import.
The previous importer is preserved in the local source checkpoint.
"""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

if __package__:
    from .csv_validation import ROOT, validate_csv, summary
else:
    from csv_validation import ROOT, validate_csv, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--lookup-dir", type=Path, default=ROOT / "data")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--delimiter", default=",")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--environment", choices=["dev", "test"])
    parser.add_argument("--confirm-isolated", action="store_true")
    parser.add_argument("--backup-reference", type=Path, help="Existing local source/data recovery manifest")
    parser.add_argument("--uri", help="Explicit Neo4j target; never inferred from .env")
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args(argv)
    if not 1 <= args.batch_size <= 10000:
        parser.error("batch-size must be 1..10000")
    if args.report and args.report.exists():
        parser.error("report exists; refusing to overwrite")
    if args.apply:
        uri = urlsplit(args.uri or "")
        if (not args.environment or not args.confirm_isolated or not args.backup_reference
                or not args.backup_reference.is_file() or uri.scheme not in {"bolt", "neo4j"}
                or uri.hostname not in {"localhost", "127.0.0.1", "::1"}
                or uri.username or uri.password or uri.query or uri.fragment):
            parser.error("apply requires dev/test, confirm-isolated, existing backup-reference and explicit loopback Neo4j URI")
    report = None
    started = time.perf_counter()
    try:
        before = hashlib.sha256(args.file.read_bytes()).hexdigest()
        result = validate_csv(args.file, args.lookup_dir, args.delimiter, args.limit)
        report = summary(result, args.file)
        if report["source_sha256"] != before:
            raise ValueError("source_changed_during_validation")
        code = 1 if result["errors"] else 0
        if args.apply and code == 0:
            password = os.environ.get("LUMIERE_GRAPH_PASSWORD")
            if not password:
                raise ValueError("missing_explicit_dev_credential")
            if __package__:
                from .graph_writer import import_projection
            else:
                from graph_writer import import_projection
            from neo4j import GraphDatabase
            report["mode"] = "apply"
            report["verification"] = None
            report["committed_records"] = 0
            report["write_attempted"] = True
            def progress(count):
                report["committed_records"] = count
            with GraphDatabase.driver(args.uri, auth=(os.getenv("LUMIERE_GRAPH_USER", "neo4j"), password),
                                      connection_timeout=5, max_transaction_retry_time=10) as driver:
                report["verification"] = import_projection(
                    driver, args.database, result["records"], args.file.name, before, args.batch_size, progress=progress)
            report["write_allowed"] = True
            report["completed"] = bool(report["verification"]["pass"])
            code = 0 if report["verification"]["pass"] else 1
    except Exception as exc:
        report = report or {"mode": "apply" if args.apply else "dry-run"}
        report.update(error_type=type(exc).__name__, completed=False)
        report["partial_write_possible"] = bool(report.get("write_attempted"))
        code = 2
    report['elapsed_seconds'] = round(time.perf_counter() - started, 6)
    if args.report:
        with args.report.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
