"""Review gate shared by the evaluator and CSV review workflow."""
import csv
import json
from pathlib import Path

RANKING_INTENTS = {"product_search", "product_recommendation", "recommendation"}


def load_reviewed_cases(path: Path):
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
    else:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    cases, seen, pending, rejected = [], set(), 0, 0
    for row in rows:
        ident = row.get("query_id", row.get("id"))
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            raise ValueError("Unique query_id is required")
        seen.add(ident)
        if not isinstance(row.get("query"), str) or not row["query"].strip():
            raise ValueError("Query is required")
        status = row.get("review_status", "PENDING_REVIEW")
        if status not in {"PENDING_REVIEW", "APPROVED", "REJECTED"}:
            raise ValueError("Unknown review_status")
        if status != "APPROVED":
            pending += status == "PENDING_REVIEW"
            rejected += status == "REJECTED"
            continue
        if not str(row.get("reviewer", "")).strip():
            raise ValueError("APPROVED requires a human reviewer")

        def structured(key, default=None):
            value = row.get(key, default)
            return json.loads(value) if isinstance(value, str) else value

        entities = structured("expected_entities")
        if not isinstance(entities, dict) or any(not isinstance(v, list) or any(not isinstance(i,str) for i in v) for v in entities.values()):
            raise ValueError("expected_entities must be an object of lists")
        constraints = structured("hard_constraints", {})
        if not isinstance(constraints, dict) or not row.get("expected_intent"):
            raise ValueError("Intent and hard_constraints object are required")
        allowed = constraints.get("allowed_product_ids")
        if allowed is not None and (not isinstance(allowed,list) or any(type(i) is not int or i < 1 for i in allowed) or len(allowed) != len(set(allowed))):
            raise ValueError("allowed_product_ids must be unique positive IDs")
        ranking = row["expected_intent"] in RANKING_INTENTS
        ids = structured("expected_product_ids", row.get("relevant_ids")) if ranking else None
        if ranking and (not isinstance(ids, list) or any(type(i) is not int or i < 1 for i in ids) or len(ids) != len(set(ids))):
            raise ValueError("Approved ranking needs explicit unique expected_product_ids, including [] for reviewed no-result")
        k = int(row.get("top_k", 3))
        if not 1 <= k <= 20:
            raise ValueError("top_k must be 1..20")
        cases.append({**row, "id": ident, "top_k": k, "expected_entities": entities,
                      "hard_constraints": constraints, "relevant_ids": ids, "ranking_task": ranking})
    return cases, {"total": len(rows), "approved": len(cases), "pending_review": pending, "rejected": rejected}


def entity_metrics(actual: dict, expected: dict) -> dict:
    def pairs(values):
        if any(not isinstance(items,(list,tuple)) or any(not isinstance(i,str) for i in items) for items in values.values()):
            raise ValueError("Entity predictions must be canonical string lists")
        return {(kind, str(value)) for kind, items in values.items() for value in items}
    observed, gold = pairs(actual), pairs(expected)
    true_positive = len(observed & gold)
    precision = true_positive / len(observed) if observed else float(not gold)
    recall = true_positive / len(gold) if gold else float(not observed)
    return {"entity_linking_accuracy": float(observed == gold),
            "entity_precision": precision, "entity_recall": recall,
            "entity_f1": 2*precision*recall/(precision+recall) if precision+recall else 0.0}
