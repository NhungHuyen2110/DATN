"""Experimental graph-feature reranking; disabled unless explicitly injected.

Scores are deterministic heuristic features, not probabilities or measured
relevance. Tune/compare on validation labels before enabling for customers.
"""
import math


class GraphFeatureReranker:
    name = 'normalized_rrf_verified_graph_v1'

    def __init__(self, rrf_weight=.9):
        if not 0 <= rrf_weight <= 1:
            raise ValueError('RRF weight must be in 0..1')
        self.rrf_weight = rrf_weight

    def __call__(self, query, candidates):
        maximum = max((float(item['score']) for item in candidates), default=0)
        if maximum < 0 or not math.isfinite(maximum):
            raise ValueError('Finite nonnegative RRF scores required')
        ranked = []
        for item in candidates:
            score = float(item['score'])
            if score < 0 or not math.isfinite(score):
                raise ValueError('Finite nonnegative RRF scores required')
            # Search supplies only paths revalidated against the latest catalog.
            types = {path['relationship'] for path in item.get('graph_paths', [])}
            graph_feature = len(types & {'BELONGS_TO', 'HAS_GEMSTONE'}) / 2
            rrf_feature = score / maximum if maximum else 0
            final = self.rrf_weight * rrf_feature + (1 - self.rrf_weight) * graph_feature
            ranked.append({**item, 'rrf_score': score, 'score': final,
                           'score_type': self.name, 'rerank_features': {
                               'normalized_rrf': rrf_feature, 'verified_graph': graph_feature}})
        return sorted(ranked, key=lambda item: (-item['score'], str(item['ProductID'])))
