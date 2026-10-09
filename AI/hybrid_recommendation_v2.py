
from hybrid_recommendation import (
    get_content_scores,
    get_qdrant_scores,
    get_collaborative_scores,
    normalize_scores
)
from knowledge_graph.graph_recommendation import GraphRecommender
from config import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD
)

def recommend_v2(customer_id, product_id, top_k=5):
    # Điểm từ hệ thống cũ
    content = normalize_scores(
        get_content_scores(product_id)
    )

    qdrant = normalize_scores(
        get_qdrant_scores(product_id)
    )

    collaborative = normalize_scores(
        get_collaborative_scores(customer_id)
    )

    # Điểm Knowledge Graph
    graph_service = GraphRecommender(
        NEO4J_URI,
        NEO4J_USERNAME,
        NEO4J_PASSWORD
    )

    try:
        graph_results = graph_service.recommend(
            product_id, limit=30
        )
    finally:
        graph_service.close()

    graph = normalize_scores({
        int(item["ProductID"]): item["GraphScore"]
        for item in graph_results
    })

    product_ids = (
        set(content) |
        set(qdrant) |
        set(collaborative) |
        set(graph)
    )

    recommendations = []

    for pid in product_ids:
        pid = int(pid)

        if pid == int(product_id):
            continue

        score = (
            0.20 * content.get(pid, 0) +
            0.30 * qdrant.get(pid, 0) +
            0.25 * collaborative.get(pid, 0) +
            0.25 * graph.get(pid, 0)
        )

        recommendations.append({
            "ProductID": pid,
            "HybridScore": round(score, 4),
            "GraphScore": graph.get(pid, 0)
        })

    recommendations.sort(
        key=lambda item: item["HybridScore"],
        reverse=True
    )

    return recommendations[:top_k]
