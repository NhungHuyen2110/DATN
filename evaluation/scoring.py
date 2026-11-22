"""Ranking metric definitions kept independent of retrieval/model code."""
import math


def ranking_metrics(ids, relevance, k=3):
    if type(k) is not int or k < 1 or len(ids) != len(set(ids)):
        raise ValueError('Positive K and unique predicted IDs required')
    if any(type(pid) is not int or pid <= 0 for pid in ids):
        raise ValueError('Positive integer product identities required')
    if any(type(pid) is not int or pid <= 0 or type(grade) is not int or not 0 <= grade <= 3
           for pid, grade in relevance.items()):
        raise ValueError('Relevance grades must be integers 0..3 for positive IDs')
    relevant = {pid for pid, grade in relevance.items() if grade > 0}
    if not relevant:
        raise ValueError('Ranking quality is undefined without positive judgments')
    selected = ids[:k]
    hits = sum(pid in relevant for pid in selected)
    dcg = sum((2 ** relevance.get(pid, 0) - 1) / math.log2(rank + 2)
              for rank, pid in enumerate(selected))
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum((2 ** grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(ideal))
    mrr = next((1 / rank for rank, pid in enumerate(ids, 1) if pid in relevant), 0)
    return {'precision_at_k': hits / k, 'recall_at_k': hits / len(relevant),
            'mrr': mrr, 'ndcg_at_k': dcg / idcg}


def evaluate(labels, predictions, k=3):
    truth, results = {}, {}
    for label in labels:
        key = label['query_id']
        if key in truth:
            raise ValueError('Duplicate label query_id')
        if label.get('reviewed') is not True or not str(label.get('reviewer') or '').strip():
            raise ValueError('Human review is required; draft records cannot be scored')
        if not label.get('dataset_sha256') or label.get('split') not in {'validation', 'test'}:
            raise ValueError('Dataset fingerprint and explicit evaluation split required')
        truth[key] = label
    if not truth:
        raise ValueError('No reviewed labels')
    for prediction in predictions:
        key = prediction['query_id']
        if key in results:
            raise ValueError('Duplicate prediction query_id')
        results[key] = prediction
    if set(truth) != set(results):
        raise ValueError('Prediction coverage differs from labels; do not omit failed queries')
    rows = []
    for key, label in truth.items():
        prediction = results[key]
        if prediction.get('dataset_sha256') != label['dataset_sha256']:
            raise ValueError('Prediction and label dataset differ')
        relevance = {int(pid): grade for pid, grade in label['relevance'].items()}
        metrics = ranking_metrics(prediction['product_ids'], relevance, k)
        latency = prediction.get('latency_seconds')
        if type(latency) not in {float, int} or not math.isfinite(latency) or latency < 0:
            raise ValueError('Measured finite nonnegative latency required')
        rows.append({'query_id': key, **metrics, 'latency_seconds': latency})
    aggregate = {name: sum(row[name] for row in rows) / len(rows)
                 for name in ('precision_at_k', 'recall_at_k', 'mrr', 'ndcg_at_k')}
    latencies = sorted(row['latency_seconds'] for row in rows)
    aggregate['latency_p50_seconds'] = latencies[math.ceil(.5 * len(latencies)) - 1]
    aggregate['latency_p95_seconds'] = latencies[math.ceil(.95 * len(latencies)) - 1]
    return {'queries': len(rows), 'k': k, 'metrics': aggregate, 'per_query': rows,
            'limitations': 'Ranking on reviewed positive judgments only; not an automatic grounding or graph-quality evaluation'}
