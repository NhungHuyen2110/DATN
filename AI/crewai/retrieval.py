import os
import sys
import requests
import re

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

def extract_category(query):
    """
    Xác định loại trang sức từ câu hỏi.
    """

    query_lower = query.lower()

    if "vòng tay" in query_lower:
        return ["vòng tay", "lắc tay"]

    if "lắc tay" in query_lower:
        return ["vòng tay", "lắc tay"]

    if "nhẫn" in query_lower:
        return ["nhẫn"]

    if "dây chuyền" in query_lower:
        return ["dây chuyền"]

    if "bông tai" in query_lower:
        return ["bông tai", "hoa tai"]

    if "hoa tai" in query_lower:
        return ["bông tai", "hoa tai"]

    if "charm" in query_lower:
        return ["charm"]

    return None


def extract_material(query):
    """
    Xác định chất liệu chung.
    """

    query_lower = query.lower()

    if "bạch kim" in query_lower:
        return "bạch kim"

    if "platinum" in query_lower:
        return "platinum"

    if "bạc" in query_lower:
        return "bạc"

    if "vàng" in query_lower:
        return "vàng"

    return None


def extract_gold_type(query):
    query_lower = query.lower()

    gold_types = [
        "vàng trắng 18k",
        "vàng trắng 14k",
        "vàng trắng 10k",
        "vàng 24k",
        "vàng 18k",
        "vàng 14k",
        "vàng 10k"
    ]

    for gold_type in gold_types:

        if gold_type in query_lower:
            return gold_type

    return None

def extract_gemstone(query):
    """
    Xác định loại đá quý.
    """

    query_lower = query.lower()

    gemstone_mapping = {
        "kim cương": "diamond",
        "diamond": "diamond",
        "ruby": "ruby",
        "sapphire": "sapphire",
        "emerald": "emerald",
        "moissanite": "moissanite"
    }

    for keyword, gemstone in gemstone_mapping.items():
        if keyword in query_lower:
            return gemstone

    return None

def hybrid_search(query, top_k=5):
    print()
    print("Đang phân tích yêu cầu tìm kiếm...")

    # ==========================================================
    # 1. PHÂN TÍCH QUERY
    # ==========================================================

    category_keywords = extract_category(query)
    material = extract_material(query)
    gold_type = extract_gold_type(query)
    gemstone = extract_gemstone(query)
    price_filter = extract_price_filter(query)

    print(f"Loại sản phẩm: {category_keywords}")
    print(f"Chất liệu: {material}")
    print(f"Loại vàng: {gold_type}")
    print(f"Đá quý: {gemstone}")
    print(f"Khoảng giá: {price_filter}")

    # ==========================================================
    # 2. QDRANT LẤY NHIỀU ỨNG VIÊN
    # ==========================================================
    # Không chỉ lấy 3 hoặc 5 sản phẩm.
    # Lấy 20 sản phẩm để tránh trường hợp sản phẩm phù hợp
    # bị xếp hạng thấp bởi semantic search.

    candidate_k = max(top_k * 7, 20)

    qdrant_results = search_qdrant(
        query,
        top_k=candidate_k
    )

    print()
    print(f"Qdrant trả về {len(qdrant_results)} ứng viên.")

    # ==========================================================
    # 3. LẤY THÔNG TIN CHI TIẾT TỪ NEO4J
    # ==========================================================

    enriched_products = []

    for item in qdrant_results:

        product_id = item.get("ProductID")

        if product_id is None:
            continue

        product = get_product_from_neo4j(product_id)

        if product is None:
            continue

        product["score"] = item.get("score", 0)

        enriched_products.append(product)

    print(
        f"Neo4j lấy được thông tin "
        f"{len(enriched_products)} sản phẩm."
    )

    # ==========================================================
    # 4. LỌC THEO THUỘC TÍNH
    # ==========================================================

    filtered = []

    for product in enriched_products:

        product_category = (
            product.get("Category") or ""
        ).lower().strip()

        product_material = (
            product.get("Material") or ""
        ).lower().strip()

        product_gemstone = (
            product.get("Gemstone") or ""
        ).lower().strip()

        product_price = product.get("Price")

        # ------------------------------------------------------
        # CATEGORY
        # ------------------------------------------------------

        category_ok = True

        if category_keywords:

            category_ok = any(
                keyword.lower() in product_category
                for keyword in category_keywords
            )

        # ------------------------------------------------------
        # MATERIAL
        # ------------------------------------------------------

        material_ok = True

        if material:
            material_ok = material.lower() in product_material

        # ------------------------------------------------------
        # GOLD TYPE
        # ------------------------------------------------------

        gold_ok = True

        if gold_type:
            gold_ok = (
                gold_type.lower()
                in product_material
            )

        # ------------------------------------------------------
        # GEMSTONE
        # ------------------------------------------------------

        gemstone_ok = True

        if gemstone:
            gemstone_ok = (
                gemstone.lower()
                in product_gemstone
            )

        # ------------------------------------------------------
        # PRICE
        # ------------------------------------------------------

        price_ok = True

        if product_price is not None:

            try:

                product_price = float(product_price)

                min_price = price_filter.get(
                    "min_price"
                )

                max_price = price_filter.get(
                    "max_price"
                )

                if min_price is not None:
                    price_ok = (
                        product_price >= min_price
                    )

                if max_price is not None:
                    price_ok = (
                        price_ok
                        and product_price <= max_price
                    )

            except (ValueError, TypeError):

                price_ok = False

        # ------------------------------------------------------
        # TỔNG HỢP ĐIỀU KIỆN
        # ------------------------------------------------------

        if (
            category_ok
            and material_ok
            and gold_ok
            and gemstone_ok
            and price_ok
        ):

            filtered.append(product)

    # ==========================================================
    # 5. SẮP XẾP THEO ĐIỂM QDRANT
    # ==========================================================

    filtered.sort(
        key=lambda x: x.get("score", 0),
        reverse=True
    )

    # ==========================================================
    # 6. CHỈ TRẢ VỀ TOP K
    # ==========================================================

    filtered = filtered[:top_k]

    print()
    print(
        f"Sau khi lọc còn "
        f"{len(filtered)} sản phẩm phù hợp."
    )

    return filtered

def parse_money(value, unit):
    """
    Chuyển số tiền về VNĐ.
    """

    value = float(value)

    if unit == "triệu":
        return value * 1_000_000

    if unit == "trăm":
        return value * 100

    if unit == "nghìn":
        return value * 1_000

    return value


def extract_price_filter(query):
    """
    Trích xuất khoảng giá từ câu hỏi.

    Trả về:
    {
        "min_price": ...,
        "max_price": ...
    }
    """

    query_lower = query.lower()

    min_price = None
    max_price = None

    # -----------------------------------------
    # Ví dụ:
    # dưới 10 triệu
    # dưới 20 triệu
    # -----------------------------------------

    match = re.search(
        r"(?:dưới|<=|không quá|tối đa)\s*(\d+(?:[.,]\d+)?)\s*(triệu|trăm|nghìn)?",
        query_lower
    )

    if match:
        value = match.group(1).replace(",", ".")
        unit = match.group(2)

        max_price = parse_money(
            value,
            unit
        )

    # -----------------------------------------
    # Ví dụ:
    # trên 5 triệu
    # từ 5 triệu trở lên
    # -----------------------------------------

    match = re.search(
        r"(?:trên|>=|từ)\s*(\d+(?:[.,]\d+)?)\s*(triệu|trăm|nghìn)?",
        query_lower
    )

    if match:
        value = match.group(1).replace(",", ".")
        unit = match.group(2)

        min_price = parse_money(
            value,
            unit
        )

    # -----------------------------------------
    # Ví dụ:
    # từ 5 triệu đến 15 triệu
    # -----------------------------------------

    match = re.search(
        r"từ\s*(\d+(?:[.,]\d+)?)\s*(triệu|trăm|nghìn)?\s*đến\s*(\d+(?:[.,]\d+)?)\s*(triệu|trăm|nghìn)?",
        query_lower
    )

    if match:
        value1 = match.group(1).replace(",", ".")
        unit1 = match.group(2)

        value2 = match.group(3).replace(",", ".")
        unit2 = match.group(4)

        min_price = parse_money(
            value1,
            unit1
        )

        max_price = parse_money(
            value2,
            unit2
        )

    return {
        "min_price": min_price,
        "max_price": max_price
    }

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