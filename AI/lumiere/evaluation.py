"""Binary relevance metrics for externally labeled query/ID datasets."""

import math


def evaluate_ranking(returned: list[int], relevant: set[int], top_k: int,
                     allowed: set[int] | None = None) -> dict:
    if top_k < 1 or len(returned) != len(set(returned)) or any(type(i) is not int or i < 1 for i in returned):
        raise ValueError("Positive top_k and unique returned IDs are required")
    ranked = returned[:top_k]
    hits = [int(ident in relevant) for ident in ranked]
    dcg = sum(hit / math.log2(rank + 2) for rank, hit in enumerate(hits))
    ideal = sum(1 / math.log2(rank + 2) for rank in range(min(len(relevant), top_k)))
    return {
        "precision_at_k": sum(hits) / top_k,
        "recall_at_k": sum(hits) / len(relevant) if relevant else 0.0,
        "mrr": next((1 / (rank + 1) for rank, hit in enumerate(hits) if hit), 0.0),
        "ndcg_at_k": dcg / ideal if ideal else 0.0,
        "returned": len(ranked),
        "returned_total": len(returned),
        "top_k_overflow": max(0, len(returned)-top_k),
        "hard_filter_violations": sum(ident not in allowed for ident in ranked) if allowed is not None else None,
        "top_k_fulfilled": len(ranked) == top_k,
        "enough_eligible": len(allowed) >= top_k if allowed is not None else None,
    }
