import os
import sys
import requests

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from neo4j import GraphDatabase


# ============================================================
# CONFIG
# ============================================================

QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "jewelry_products"

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "12345678"


# ============================================================
# CONNECT QDRANT
# ============================================================

print("Đang kết nối Qdrant...")

qdrant_client = QdrantClient(
    url=QDRANT_URL
)

embedding_model = SentenceTransformer(
    EMBEDDING_MODEL
)

print("Qdrant + Embedding sẵn sàng.")


# ============================================================
# CONNECT NEO4J
# ============================================================

print("Đang kết nối Neo4j...")

neo4j_driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(
        NEO4J_USERNAME,
        NEO4J_PASSWORD
    )
)

print("Neo4j sẵn sàng.")


# ============================================================
# QDRANT SEARCH
# ============================================================

def search_qdrant(query, top_k=5):

    vector = embedding_model.encode(
        query
    ).tolist()

    results = qdrant_client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=vector,
        limit=top_k,
        with_payload=True
    ).points

    products = []

    for result in results:

        payload = result.payload or {}

        product = {
            "ProductID": payload.get("ProductID"),
            "ProductName": payload.get("ProductName"),
            "score": result.score
        }

        products.append(product)

    return products


# ============================================================
# NEO4J ENRICHMENT
# ============================================================

def get_product_from_neo4j(product_id):

    query = """
    MATCH (p:Product {product_id: $product_id})

    OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:Category)
    OPTIONAL MATCH (p)-[:HAS_BRAND]->(b:Brand)
    OPTIONAL MATCH (p)-[:MADE_OF]->(m:Material)
    OPTIONAL MATCH (p)-[:HAS_GEMSTONE]->(g:Gemstone)
    OPTIONAL MATCH (p)-[:IN_COLLECTION]->(co:Collection)

    RETURN
        p.product_id AS ProductID,
        p.name AS ProductName,
        c.name AS Category,
        b.name AS Brand,
        m.name AS Material,
        g.name AS Gemstone,
        co.name AS Collection,
        p.sale_price AS Price,
        p.stock AS Stock,
        p.sku AS SKU
    """

    with neo4j_driver.session() as session:

        result = session.run(
            query,
            product_id=int(product_id)
        )

        record = result.single()

        if record is None:
            return None

        return dict(record)


# ============================================================
# FORMAT PRICE
# ============================================================

def format_price(price):

    if price is None:
        return "Không có thông tin"

    try:

        price = int(float(price))

        return (
            f"{price:,}"
            .replace(",", ".")
            + " VNĐ"
        )

    except (
        ValueError,
        TypeError
    ):

        return str(price)


# ============================================================
# HYBRID FILTERING
# ============================================================

def hybrid_search(query, top_k=5):

    qdrant_results = search_qdrant(
        query,
        top_k
    )

    enriched_products = []

    for item in qdrant_results:

        product_id = item["ProductID"]

        product = get_product_from_neo4j(
            product_id
        )

        if product is None:
            continue

        product["score"] = item["score"]

        enriched_products.append(
            product
        )


    # --------------------------------------------------------
    # PARSE QUERY
    # --------------------------------------------------------

    query_lower = query.lower()


    # --------------------------------------------------------
    # MATERIAL
    # --------------------------------------------------------

    material = None

    if "vàng" in query_lower:
        material = "vàng"

    elif "bạc" in query_lower:
        material = "bạc"

    elif "bạch kim" in query_lower:
        material = "bạch kim"

    elif "platinum" in query_lower:
        material = "platinum"


    # --------------------------------------------------------
    # CATEGORY
    # --------------------------------------------------------

    category_keywords = None

    if "vòng tay" in query_lower:

        category_keywords = [
            "vòng tay",
            "lắc tay"
        ]

    elif "lắc tay" in query_lower:

        category_keywords = [
            "vòng tay",
            "lắc tay"
        ]

    elif "nhẫn" in query_lower:

        category_keywords = [
            "nhẫn"
        ]

    elif "dây chuyền" in query_lower:

        category_keywords = [
            "dây chuyền"
        ]

    elif "bông tai" in query_lower:

        category_keywords = [
            "bông tai",
            "hoa tai"
        ]

    elif "charm" in query_lower:

        category_keywords = [
            "charm"
        ]


    # --------------------------------------------------------
    # FILTER
    # --------------------------------------------------------

    filtered = []

    for product in enriched_products:

        material_ok = True
        category_ok = True


        # MATERIAL FILTER

        if material:

            product_material = (
                product.get("Material") or ""
            ).lower()

            material_ok = (
                material in product_material
            )


        # CATEGORY FILTER

        if category_keywords:

            product_category = (
                product.get("Category") or ""
            ).lower()

            category_ok = any(
                keyword in product_category
                for keyword in category_keywords
            )


        if material_ok and category_ok:

            filtered.append(product)


    # --------------------------------------------------------
    # SORT BY QDRANT SCORE
    # --------------------------------------------------------

    filtered.sort(
        key=lambda x: x["score"],
        reverse=True
    )


    return filtered


# ============================================================
# BUILD RAG CONTEXT
# ============================================================

def build_rag_context(products):

    context_parts = []

    for product in products:

        context_parts.append(
            f"""
Sản phẩm:
- ProductID: {product.get("ProductID")}
- Tên: {product.get("ProductName")}
- Danh mục: {product.get("Category")}
- Thương hiệu: {product.get("Brand")}
- Chất liệu: {product.get("Material")}
- Đá quý: {product.get("Gemstone")}
- Bộ sưu tập: {product.get("Collection")}
- Giá bán chính xác: {format_price(product.get("Price"))}
- Tồn kho: {product.get("Stock")}
- SKU: {product.get("SKU")}
- Điểm tương đồng Qdrant: {product.get("score")}
"""
        )

    return "\n".join(
        context_parts
    )