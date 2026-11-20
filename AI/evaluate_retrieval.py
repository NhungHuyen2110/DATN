"""Real retrieval evaluation; only human-approved CSV/JSONL cases can be scored."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from time import perf_counter

from lumiere.review_data import load_reviewed_cases, entity_metrics
from lumiere.evaluation import evaluate_ranking


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("lexical", "dense", "dense_lexical", "dense_graph", "hybrid"), default="hybrid")
    parser.add_argument("--predictions", type=Path, help="Captured real predictions JSONL for backend/intent tasks")
    parser.add_argument("--inspect-only", action="store_true")
    args = parser.parse_args(argv)
    cases, review = load_reviewed_cases(args.dataset)
    report = {"dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(), "review": review,
        "status": "PENDING_REVIEW" if not cases else "REVIEWED_CASES_AVAILABLE",
        "sufficient_100_reviewed": len(cases) >= 100, "mode": args.mode, "summary": None, "results": []}

    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if not cases or args.inspect_only:
        save()
        print(json.dumps({"status": report["status"], **review}))
        return 0 if args.inspect_only else 2
    predictions = {}
    if args.predictions:
        for line in args.predictions.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            ident = row["query_id"]
            if ident in predictions or not isinstance(row.get("entities"), dict) or not isinstance(row.get("intent"), str):
                raise ValueError("Predictions require unique query_id, entities and intent")
            predictions[ident] = row
        report["prediction_sha256"] = hashlib.sha256(args.predictions.read_bytes()).hexdigest()
    else:
        from lumiere.bootstrap import catalog_repository, SemanticModelProvider, LazyDenseRetriever, LazyGraphRetriever, DEFAULT_MODEL
        from lumiere.catalog import SnapshotProductRepository
        from lumiere.configuration import load_aliases
        from lumiere.linking import EntityLinkingService, SemanticEntityResolver
        from lumiere.understanding import QueryUnderstandingService
        from lumiere.retrieval import HybridRetrievalService, LexicalRetriever, RankFusionService
        from lumiere.adapters import REPRESENTATION_VERSION
        source = catalog_repository()
        repository = SnapshotProductRepository(source.all())
        provider, config = SemanticModelProvider(), load_aliases()
        linker = EntityLinkingService(config, SemanticEntityResolver(provider, config) if args.mode != "lexical" else None)
        understanding = QueryUnderstandingService(linker)
        retrievers = []
        if args.mode in {"dense", "dense_lexical", "dense_graph", "hybrid"}:
            retrievers.append(LazyDenseRetriever(repository, provider))
        if args.mode in {"lexical", "dense_lexical", "hybrid"}:
            retrievers.append(LexicalRetriever(repository))
        if args.mode in {"dense_graph", "hybrid"}:
            retrievers.append(LazyGraphRetriever(repository))
        service = HybridRetrievalService(repository, retrievers, understanding, RankFusionService(), verifier=source)
        report.update({"model": os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL), "representation_version": REPRESENTATION_VERSION,
            "catalog_sha256": hashlib.sha256(json.dumps([p.public() for p in repository.all()], sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            "sources_enabled": [r.name for r in retrievers], "collection": os.getenv("QDRANT_COLLECTION", "lumiere_products_v2")})
    durations = []
    for case in cases:
        if not args.predictions and not case["ranking_task"]:
            report["results"].append({"id": case["id"], "status": "UNSUPPORTED_TASK",
                "reason": "Capture real backend/intent predictions for authorization, policies and non-product tasks"})
            continue
        if args.predictions and case["id"] not in predictions:
            report["results"].append({"id": case["id"], "status": "MISSING_PREDICTION"})
            continue
        started = perf_counter()
        if args.predictions:
            prediction = predictions[case["id"]]
            actual_ids = prediction.get("product_ids", [])
            actual_entities, actual_intent = prediction["entities"], prediction["intent"]
            degraded = prediction.get("degraded_sources", [])
        else:
            context = understanding.understand(case["query"], case["top_k"])
            actual_entities, actual_intent = context.entities, context.intent
            products, degraded = service.search(case["query"], case["top_k"])
            actual_ids = [p["ProductID"] for p in products]
        elapsed = perf_counter()-started
        durations.append(elapsed)
        measured = {"id": case["id"], "status": "EVALUATED", "returned_ids": actual_ids,
            "actual_entities": actual_entities, "actual_intent": actual_intent,
            "intent_correct": actual_intent == case["expected_intent"],
            **entity_metrics(actual_entities, case["expected_entities"]), "degraded_sources": degraded}
        if not args.predictions:
            measured["latency_seconds"] = elapsed
        if case["ranking_task"]:
            # Allowed IDs are human-supplied constraints, independent of the linker's own output.
            hard = case["hard_constraints"]
            allowed = set(hard["allowed_product_ids"]) if "allowed_product_ids" in hard else None
            measured.update(evaluate_ranking(actual_ids, set(case["relevant_ids"]), case["top_k"], allowed))
        report["results"].append(measured)
    evaluated = [r for r in report["results"] if r["status"] == "EVALUATED"]
    ranked = [r for r in evaluated if "precision_at_k" in r]
    summary = {"evaluated_cases": len(evaluated), "ranking_cases": len(ranked), "unsupported_or_missing": len(cases)-len(evaluated)}
    for metric in ("precision_at_k", "recall_at_k", "mrr", "ndcg_at_k"):
        summary[metric] = sum(r[metric] for r in ranked)/len(ranked) if ranked else None
    for metric in ("entity_linking_accuracy", "entity_precision", "entity_recall", "entity_f1", "intent_correct"):
        summary[metric] = sum(r[metric] for r in evaluated)/len(evaluated) if evaluated else None
    summary["latency_p95_seconds"] = sorted(durations)[math.ceil(.95*len(durations))-1] if durations and not args.predictions else None
    summary["degraded_case_count"] = sum(bool(r["degraded_sources"]) for r in evaluated)
    summary["top_k_overflow"] = sum(r["top_k_overflow"] for r in ranked)
    scored = [r for r in ranked if r["hard_filter_violations"] is not None]
    summary["hard_filter_violations"] = sum(r["hard_filter_violations"] for r in scored) if scored else None
    report["summary"], report["status"] = summary, "EVALUATED_APPROVED_ONLY"
    save()
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
