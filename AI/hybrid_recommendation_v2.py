
from hybrid_recommendation import (
    products,
    get_content_scores,
    get_qdrant_scores,
    get_collaborative_scores,
    normalize_scores
)
from knowledge_graph.graph_recommendation import GraphRecommender
from jewelry_agents.business_catalog import fetch_catalog
from jewelry_agents.ranking import price_and_stock_valid
from config import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD
)

def recommend_v2(customer_id, product_id, top_k=5):
    if type(top_k) is not int or not 1 <= top_k <= 20:
        raise ValueError("top_k must be 1..20")
    live_products = fetch_catalog()
    if int(product_id) not in live_products:
        raise ValueError("Source product is no longer in the authoritative catalog")
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
    graph_service = None
    try:
        graph_service = GraphRecommender(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
        graph_results = graph_service.recommend(
            product_id, limit=30
        )
    except Exception:
        graph_results = []
    finally:
        if graph_service is not None:
            graph_service.close()

    # Verify graph explanations against BOTH live endpoints, not only live price.
    verified_graph = []
    attributes = {'BELONGS_TO': ('CategoryID', 0.4), 'MADE_OF': ('MaterialID', 0.3),
                  'HAS_GEMSTONE': ('GemstoneID', 0.3)}
    for item in graph_results:
        candidate = live_products.get(int(item['ProductID']))
        if candidate is None:
            continue
        paths = []
        for path in item.get('paths', []):
            field_weight = attributes.get(path.get('relationship'))
            if field_weight:
                field, _ = field_weight
                attribute_id = path.get('attribute_id')
                if (attribute_id is not None and path.get('source_product_id') == int(product_id)
                        and path.get('candidate_product_id') == int(item['ProductID'])
                        and live_products[int(product_id)].get(field) == attribute_id
                        and candidate.get(field) == attribute_id):
                    paths.append(path)
        types = {path['relationship'] for path in paths}
        if paths:
            verified_graph.append({**item, 'paths': paths,
                                   'GraphScore': sum(attributes[relation][1] for relation in types)})
    graph_results = verified_graph

    graph = normalize_scores({
        int(item["ProductID"]): item["GraphScore"]
        for item in graph_results
    })
    graph_evidence = {int(item['ProductID']): item.get('paths', []) for item in graph_results}

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
            "ContentScore": float(round(content.get(pid, 0), 4)),
            "QdrantScore": float(round(qdrant.get(pid, 0), 4)),
            "CollaborativeScore": float(round(collaborative.get(pid, 0), 4)),
            "GraphScore": float(round(graph.get(pid, 0), 4)),
            "HybridScore": float(score)
        })

    recommendations.sort(
        key=lambda item: (-item["HybridScore"], item["ProductID"])
    )

    final_results = []

    for item in recommendations:
        pid = item["ProductID"]

        if pid not in live_products:
            continue
        product = live_products[pid]
        if not price_and_stock_valid(product, {}):
            continue

        final_results.append({
            **item,
            "ProductName": product["ProductName"],
            "CategoryName": product["Category"],
            "MaterialName": product["Material"],
            "GemstoneName": product["Gemstone"],
            "SalePrice": str(product["Price"]),
            "Stock": int(product["Stock"]),
            "GraphEvidence": graph_evidence.get(pid, []),
            "verified_source": "business_api"
        })

        if len(final_results) >= top_k:
            break

    return final_results
