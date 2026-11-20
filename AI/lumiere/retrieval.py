"""Fusion, verification and grounding use catalog facts, never LLM facts."""

from collections import defaultdict
from decimal import Decimal
import logging
import math
import re
from typing import Sequence

from .domain import Candidate, Product, ProductRepository, QueryContext, Retriever
from .understanding import QueryUnderstandingService, contains, normalize
from .matching import eligible
from .ranking import ProductReranker
from .recommendation import RecommendationService, path_supported
from dataclasses import replace

logger = logging.getLogger(__name__)


class LexicalRetriever:
    name = "lexical"

    def __init__(self, repository: ProductRepository):
        self.repository = repository

    def retrieve(self, context: QueryContext, limit: int) -> list[Candidate]:
        tokens = set(re.findall(r"\w+", normalize(context.query)))
        constrained = bool(context.entities or context.min_price is not None or context.max_price is not None or context.product_id_filter is not None)
        rows = []
        for product in self.repository.all():
            if not eligible(product, context):
                continue
            score = len(tokens & set(re.findall(r"\w+", normalize(product.text))))
            if score or constrained or contains(normalize(context.query), "trang suc"):
                rows.append(Candidate(product.id, score, "Khớp từ khóa hoặc bộ lọc trong danh mục"))
        return sorted(rows, key=lambda c: (-c.score, c.product_id))[:limit]


class RankFusionService:
    def fuse(self, lists: Sequence[Sequence[Candidate]], weights: Sequence[float] | None = None) -> dict[int, float]:
        scores = defaultdict(float)
        for source_index, candidates in enumerate(lists):
            seen = set()
            rank = 0
            for item in sorted((c for c in candidates if math.isfinite(c.score)), key=lambda c: (-c.score, c.product_id)):
                if item.product_id not in seen:
                    rank += 1
                    scores[item.product_id] += (weights[source_index] if weights else 1.0) / (60 + rank)
                    seen.add(item.product_id)
        return dict(scores)


class HybridRetrievalService:
    def __init__(self, repository: ProductRepository, retrievers: Sequence[Retriever],
                 understanding: QueryUnderstandingService, fusion: RankFusionService,
                 verifier: ProductRepository | None = None, reranker: ProductReranker | None = None):
        self.repository, self.retrievers = repository, retrievers
        self.understanding, self.fusion = understanding, fusion
        self.verifier, self.reranker = verifier, reranker or ProductReranker()

    def search(self, query: str, top_k: int) -> tuple[list[dict], list[str]]:
        context = self.understanding.understand(query, top_k)
        # A complete authoritative snapshot ensures post-filtering cannot starve Top-K.
        products = {p.id: p for p in self.repository.all()}
        context = RecommendationService().plan(context, products)
        if context.ambiguities:
            return [], ["entity_linking_ambiguity"]
        seed = products.get(context.seed_product_id)
        if seed:
            entities = dict(context.entities)
            for relationship, kind in (("HAS_GEMSTONE", "gemstone"), ("MADE_OF", "material"), ("HAS_STYLE", "style")):
                if relationship in context.required_relationships:
                    values = (tuple(f.canonical_id for f in seed.facts if f.kind == kind) if kind == "style"
                              else (normalize(getattr(seed, kind)),))
                    if not values:
                        return [], ["missing_seed_evidence"]
                    entities[kind] = values
            context = replace(context, entities=entities)
        elif context.seed_product_id is not None:
            return [], ["seed_not_found"]
        limit = context.candidate_k
        lists, weights, degraded, explanations, paths = [], [], [], defaultdict(list), defaultdict(list)
        for retriever in self.retrievers:
            try:
                candidates = retriever.retrieve(context, limit)
                lists.append(candidates)
                weights.append(2.0 if retriever.name == "dense" else 1.0)
                for candidate in candidates:
                    if candidate.reason and candidate.reason not in explanations[candidate.product_id]:
                        explanations[candidate.product_id].append(candidate.reason)
                    paths[candidate.product_id].extend(candidate.paths)
            except Exception:
                degraded.append(retriever.name)
                logger.warning("retrieval_source_unavailable source=%s", retriever.name, exc_info=False)
        scores = self.fusion.fuse(lists, weights)
        if self.verifier is not None:
            products = {p.id: p for p in self.verifier.all()}
            if seed is not None:
                current_seed = products.get(seed.id)
                if current_seed is None or any(
                    (getattr(seed, kind) != getattr(current_seed, kind) if kind != "facts" else seed.facts != current_seed.facts)
                    for kind in ("material", "gemstone", "facts")
                ):
                    return [], [*degraded, "seed_changed_during_search"]
        valid = [p for p in products.values() if p.id != context.seed_product_id and eligible(p, context)]
        if not any(p.id in scores for p in valid):
            return [], degraded
        # Deterministic reranking: rank fusion, then stable catalog identity.
        ranked = self.reranker.rank(valid, scores, context)
        result = []
        for product, final_score in ranked[:top_k]:
            row = product.public()
            row["score"] = final_score
            row["rank"] = len(result) + 1
            row["explanation"] = explanations[product.id] or ["Đáp ứng bộ lọc giá, thuộc tính và tồn kho"]
            if paths[product.id]:
                row["matched_relationships"] = [path for path in paths[product.id] if path_supported(path, products)]
                # Never repeat stale graph names as verified business explanations.
                row["explanation"] = (["Đường dẫn đồ thị đã đối soát: " + ", ".join(sorted({p["entity_name"] for p in row["matched_relationships"]}))]
                                       if row["matched_relationships"] else ["Đáp ứng các thuộc tính đã xác minh trong catalog"])
            row["matched_entities"] = context.entities
            result.append(row)
        return result, degraded


class GroundedAnswerService:
    def __init__(self, retrieval: HybridRetrievalService):
        self.retrieval = retrieval

    def answer(self, query: str, top_k: int = 3) -> dict:
        if not query.strip():
            return {"success": False, "answer": "Vui lòng nhập câu hỏi.", "products": []}
        products, degraded = self.retrieval.search(query, top_k)
        if "entity_linking_ambiguity" in degraded:
            return {"success": True, "answer": "Yêu cầu còn nhập nhằng về đối tượng hoặc phong cách. Vui lòng mô tả rõ hơn.",
                    "products": [], "degraded_sources": degraded}
        lines = ["Đây là các sản phẩm phù hợp với yêu cầu của bạn:" if products else "Không tìm thấy sản phẩm phù hợp."]
        if products and len(products) < top_k:
            lines.append(f"Chỉ tìm thấy {len(products)} sản phẩm phù hợp trên {top_k} yêu cầu.")
        for p in products:
            exact = Decimal(p["PriceVND"])
            price = (f"{exact:,.0f}".replace(",", ".") if exact == exact.to_integral_value()
                     else f"{exact:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))
            lines.append(f"• {p['ProductName']} — Mã sản phẩm: {p['ProductID']} — Giá bán: {price} VNĐ")
        return {"success": True, "answer": "\n".join(lines), "products": products,
                "degraded_sources": degraded}
