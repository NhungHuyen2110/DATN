"""Deterministic rank fusion and final verification; no service/model side effects."""
from decimal import Decimal, InvalidOperation
import math
from shared.verified_attributes import PublicAttribute


def approved_facts(product):
    result = {}
    values = product.get('verified_attributes', [])
    if not isinstance(values, list):
        return result
    for value in values:
        try:
            fact = PublicAttribute.model_validate(value).model_dump()
        except (ValueError, TypeError):
            continue
        result[(fact['label'], fact['canonical_id'])] = fact
    return result


def reviewed_constraints_valid(product, constraints):
    facts = approved_facts(product)
    for label, canonical in constraints.get('advisory_preferences', {}).items():
        known = {key[1] for key in facts if key[0] == label}
        if known and canonical not in known:
            return False
    if any((label, canonical) not in facts for label, canonical in constraints.get('reviewed_attributes', {}).items()):
        return False
    shared_styles = constraints.get('shared_reference_styles')
    return not shared_styles or any(('Style', style) in facts for style in shared_styles)


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
        if not reviewed_constraints_valid(live, constraints):
            continue
        seen.add(pid)
        ordered.append({**candidate, **live, "score": score, "rank": len(ordered) + 1})
        if len(ordered) == top_k:
            break
    return ordered

def rerank_price_preference(
    candidates,
    live_products,
    preference='neutral',
    weight=0.35
):
    """Combine relevance with a soft price preference."""

    if preference not in {
        'neutral', 'affordable', 'higher_price'
    }:
        raise ValueError('Unknown price preference')

    if not 0 <= weight <= 1:
        raise ValueError('Invalid preference weight')

    if preference == 'neutral' or not candidates:
        return candidates

    prices = {}

    for pid, product in live_products.items():
        try:
            price = Decimal(str(product.get('Price')))

            if price.is_finite() and price >= 0:
                prices[pid] = price

        except (InvalidOperation, ValueError, TypeError):
            continue

    valid = [
        item for item in candidates
        if item.get('ProductID') in prices
        and math.isfinite(float(item.get('score', 0)))
    ]

    if not valid:
        return candidates

    min_price = min(prices.values())
    max_price = max(prices.values())

    scores = [
        float(item.get('score', 0))
        for item in valid
    ]

    min_score = min(scores)
    max_score = max(scores)

    ranked = []

    for item in valid:
        pid = item['ProductID']
        original_score = float(item.get('score', 0))

        if min_score >= 0:
            relevance = (
                original_score / max_score
                if max_score > 0
                else 1.0
            )
        else:
            relevance = (
                (original_score - min_score)
                / (max_score - min_score)
                if max_score > min_score
                else 1.0
            )

        price_score = (
            float(
                (max_price - prices[pid])
                / (max_price - min_price)
            )
            if max_price > min_price
            else 1.0
        )

        if preference == 'higher_price':
            if max_price > min_price:
                price_score = 1.0 - price_score

        final_score = (
            (1.0 - weight) * relevance
            + weight * price_score
        )

        ranked.append({
            **item,
            'base_relevance_score': original_score,
            'normalized_relevance': relevance,
            'price_preference_score': price_score,
            'price_preference': preference,
            'score': final_score,
        })

    return sorted(
        ranked,
        key=lambda item: (
            -item['score'],
            str(item['ProductID'])
        )
    )


def exact_price_ranking(live_products, constraints, preference):
    """Rank the complete eligible catalog by authoritative price."""

    if preference not in {"lowest_price", "highest_price"}:
        raise ValueError("Unknown exact price preference")

    eligible = [
        (pid, product)
        for pid, product in live_products.items()
        if price_and_stock_valid(product, constraints)
        and reviewed_constraints_valid(product, constraints)
        and all(
            product.get(field) == value
            for field, value in constraints.get("attributes", {}).items()
        )
    ]

    direction = 1 if preference == "lowest_price" else -1

    eligible.sort(
        key=lambda item: (
            direction * Decimal(str(item[1]["Price"])),
            item[0]
        )
    )

    return [
        {
            "ProductID": pid,
            "score": 1.0 / (rank + 1),
            "score_type": "exact_price_rank",
            "price_preference": preference,
            "retrieval_sources": ["catalog"],
            "graph_paths": [],
        }
        for rank, (pid, product) in enumerate(eligible)
    ]
