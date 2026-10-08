from pathlib import Path

from sentence_transformers import SentenceTransformer

from qdrant_client import QdrantClient

from neo4j import GraphDatabase


# =========================================================
# 1. QDRANT
# =========================================================

QDRANT_URL = "http://localhost:6333"

COLLECTION_NAME = "jewelry_products"


qdrant = QdrantClient(
    url=QDRANT_URL
)


# =========================================================
# 2. EMBEDDING MODEL
# =========================================================

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

model = SentenceTransformer(
    MODEL_NAME
)


# =========================================================
# 3. NEO4J
# =========================================================

NEO4J_URI = "neo4j://127.0.0.1:7687"

NEO4J_USERNAME = "neo4j"

NEO4J_PASSWORD = "12345678"


neo4j_driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(
        NEO4J_USERNAME,
        NEO4J_PASSWORD
    )
)


# =========================================================
# 4. QDRANT SEARCH
# =========================================================

def search_qdrant(
    query,
    top_k=5
):

    # -----------------------------------------------------
    # Tạo embedding
    # -----------------------------------------------------

    vector = model.encode(
        query
    ).tolist()

    # -----------------------------------------------------
    # Search
    # -----------------------------------------------------

    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        limit=top_k,
        with_payload=True
    ).points

    products = []

    for result in results:

        payload = result.payload or {}

        products.append({
            "product_id": payload.get(
                "ProductID",
                payload.get("product_id")
            ),

            "score": result.score,

            "payload": payload
        })

    return products


# =========================================================
# 5. NEO4J ENRICHMENT
# =========================================================

def enrich_with_neo4j(
    product_ids
):

    query = """
    MATCH (p:Product)

    WHERE p.product_id IN $product_ids

    OPTIONAL MATCH
        (p)-[:BELONGS_TO]->(category:Category)

    OPTIONAL MATCH
        (p)-[:HAS_BRAND]->(brand:Brand)

    OPTIONAL MATCH
        (p)-[:MADE_OF]->(material:Material)

    OPTIONAL MATCH
        (p)-[:HAS_GEMSTONE]->(gemstone:Gemstone)

    OPTIONAL MATCH
        (p)-[:IN_COLLECTION]->(collection:Collection)

    RETURN
        p.product_id AS product_id,
        p.name AS product_name,
        p.sale_price AS sale_price,
        p.stock AS stock,
        p.weight AS weight,

        category.name AS category,

        brand.name AS brand,

        material.name AS material,

        gemstone.name AS gemstone,

        collection.name AS collection
    """

    with neo4j_driver.session() as session:

        result = session.run(
            query,
            product_ids=[
                int(x)
                for x in product_ids
            ]
        )

        return [
            record.data()
            for record in result
        ]


# =========================================================
# 6. HYBRID SEARCH
# =========================================================

def hybrid_search(
    query,
    top_k=5
):

    print("\n")
    print("=" * 70)
    print("HYBRID SEARCH")
    print("=" * 70)

    print("\nQuery:")
    print(query)


    # -----------------------------------------------------
    # STEP 1 - QDRANT
    # -----------------------------------------------------

    qdrant_results = search_qdrant(
        query,
        top_k
    )


    print("\nQDRANT RESULTS")

    for item in qdrant_results:

        print(
            "ProductID:",
            item["product_id"],
            "| Score:",
            item["score"]
        )


    # -----------------------------------------------------
    # STEP 2 - LẤY PRODUCT IDS
    # -----------------------------------------------------

    product_ids = [
        item["product_id"]
        for item in qdrant_results
        if item["product_id"] is not None
    ]


    if not product_ids:

        return []


    # -----------------------------------------------------
    # STEP 3 - NEO4J
    # -----------------------------------------------------

    graph_results = enrich_with_neo4j(
        product_ids
    )


    # -----------------------------------------------------
    # STEP 4 - GHÉP SCORE
    # -----------------------------------------------------

    score_map = {
        item["product_id"]: item["score"]
        for item in qdrant_results
    }


    for item in graph_results:

        item["qdrant_score"] = score_map.get(
            item["product_id"],
            0
        )


    return graph_results


# =========================================================
# 7. MAIN TEST
# =========================================================

if __name__ == "__main__":

    query = (
        "Tôi muốn tìm bông tai "
        "Moissanite phong cách Minimal"
    )

    results = hybrid_search(
        query,
        top_k=5
    )


    print("\n")
    print("=" * 70)
    print("KET QUA HYBRID")
    print("=" * 70)


    for item in results:

        print("\n")

        print(
            "ProductID:",
            item["product_id"]
        )

        print(
            "Tên:",
            item["product_name"]
        )

        print(
            "Category:",
            item["category"]
        )

        print(
            "Brand:",
            item["brand"]
        )

        print(
            "Material:",
            item["material"]
        )

        print(
            "Gemstone:",
            item["gemstone"]
        )

        print(
            "Collection:",
            item["collection"]
        )

        print(
            "Price:",
            item["sale_price"]
        )

        print(
            "Stock:",
            item["stock"]
        )

        print(
            "Qdrant score:",
            item["qdrant_score"]
        )


    neo4j_driver.close()