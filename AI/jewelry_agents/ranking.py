"""Deterministic rank fusion and final verification; no service/model side effects."""
from decimal import Decimal, InvalidOperation
import math


def reciprocal_rank_fusion(rankings, constant=60):
    if constant < 1:
        raise ValueError("RRF constant must be positive")
    scores, sources = {}, {}
    for source, ids in rankings.items():
        seen = set()
        for rank, pid in enumerate(dict.fromkeys(ids), 1):
            if pid in seen:
                continue
            seen.add(pid)
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (constant + rank)
            sources.setdefault(pid, []).append(source)
    return [(pid, scores[pid], sources[pid]) for pid in sorted(scores, key=lambda pid: (-scores[pid], str(pid)))]


def price_and_stock_valid(product, constraints):
    try:
        price = Decimal(str(product.get("Price")))
        stock = product.get("Stock")
        if not price.is_finite() or price < 0 or type(stock) is not int or stock <= 0:
            return False
        minimum, maximum = constraints.get("min_price"), constraints.get("max_price")
        if minimum is not None and (price < Decimal(str(minimum)) or
                (constraints.get("min_exclusive") and price == Decimal(str(minimum)))):
            return False
        if maximum is not None and (price > Decimal(str(maximum)) or
                (constraints.get("max_exclusive") and price == Decimal(str(maximum)))):
            return False
        return True
    except (InvalidOperation, ValueError, TypeError):
        return False


def finalize_topk(candidates, top_k, constraints, live_products):
    """Only authoritative catalog products survive; stale snapshots cannot win."""
    if type(top_k) is not int or not 1 <= top_k <= 10:
        raise ValueError("top_k must be 1..10")
    ordered, seen = [], set()
    for candidate in sorted(candidates, key=lambda p: (-float(p.get("score", 0)), str(p.get("ProductID")))):
        pid = candidate.get("ProductID")
        score = float(candidate.get("score", 0))
        if pid in seen or pid not in live_products or not math.isfinite(score):
            continue
        live = live_products[pid]
        if not price_and_stock_valid(live, constraints):
            continue
        if any(live.get(field) != expected for field, expected in constraints.get("attributes", {}).items()):
            continue
        seen.add(pid)
        ordered.append({**candidate, **live, "score": score, "rank": len(ordered) + 1})
        if len(ordered) == top_k:
            break
    return ordered
