from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
import os
import sys
import requests
import re
from decimal import Decimal, InvalidOperation

from qdrant_client import QdrantClient

from neo4j import GraphDatabase
from shared.retrieval_limits import SourceGate

_dense_gate = SourceGate('dense')
_graph_gate = SourceGate('graph')


def _bounded_source(gate, function, *args, **kwargs):
    if os.getenv('LUMIERE_RETRIEVAL_LIMITS_ENABLED', 'false').lower() == 'true':
        return gate.call(function, *args, **kwargs)
    return function(*args, **kwargs)


def close_retrieval_limits():
    _dense_gate.close()
    _graph_gate.close()


# ============================================================
# CONFIG
# ============================================================

QDRANT_URL = os.getenv(
    "QDRANT_URL", "http://127.0.0.1:6333"
)
QDRANT_COLLECTION = os.getenv(
    "QDRANT_COLLECTION", "jewelry_products"
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "paraphrase-multilingual-MiniLM-L12-v2"
)

NEO4J_URI = os.getenv(
    "NEO4J_URI", "neo4j://127.0.0.1:7687"
)
NEO4J_USERNAME = os.getenv(
    "NEO4J_USERNAME", "neo4j"
)
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


# ============================================================
# CONNECT QDRANT
# ============================================================

qdrant_client = None
embedding_model = None


def get_dense_services():
    global qdrant_client, embedding_model
    if os.getenv('LUMIERE_DENSE_ENABLED', 'true').lower() != 'true':
        raise RuntimeError('Dense retrieval disabled by runtime policy')
    if qdrant_client is None:
        qdrant_client = QdrantClient(url=QDRANT_URL, timeout=3)
    if embedding_model is None:
        # A cold model is expensive. If its vector source/index is unavailable,
        # fail before loading weights so lexical/graph fallback stays bounded.
        qdrant_client.get_collection(QDRANT_COLLECTION)
        from sentence_transformers import SentenceTransformer
        # A request must not trigger an unapproved model download.
        embedding_model = SentenceTransformer(EMBEDDING_MODEL, revision=os.getenv("EMBEDDING_REVISION") or None,
                                              local_files_only=True)
    return qdrant_client, embedding_model


# ============================================================
# CONNECT NEO4J
# ============================================================

neo4j_driver = None


def get_graph_driver():
    global neo4j_driver
    if os.getenv('LUMIERE_GRAPH_ENABLED', 'true').lower() != 'true':
        raise RuntimeError('Graph retrieval disabled by runtime policy')
    if neo4j_driver is None:
        if not NEO4J_PASSWORD:
            raise RuntimeError("Neo4j credential not configured")
        neo4j_driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
            connection_timeout=3, max_transaction_retry_time=5)
    return neo4j_driver


def plan_shopping_advice(query):
    # Shares the bounded dense worker: a cold/unavailable model cannot queue
    # unlimited intent work or delay ordinary lexical/graph fallback.
    def operation():
        from .advice_planner import plan_advice
        return plan_advice(query,get_dense_services()[1])
    return _bounded_source(_dense_gate,operation)


def graph_search_candidates(query, understanding):
    return _bounded_source(_graph_gate, _graph_search_candidates, query, understanding)


def _graph_search_candidates(query, understanding):
    reference = understanding.get('reference_product')
    if reference:
        cypher = """
            MATCH (source:Product {product_id:$source_id})-[left]->(entity)<-[right]-(p:Product)
            WHERE p.product_id <> source.product_id AND type(left)=type(right)
              AND ((type(left)='BELONGS_TO' AND entity:Category AND entity.category_id=$category)
                OR (type(left)='MADE_OF' AND entity:Material AND entity.material_id=$material)
                OR (type(left)='HAS_GEMSTONE' AND entity:Gemstone AND entity.gemstone_id=$gemstone))
              AND (size($required)=0 OR type(left) IN $required)
            WITH p, collect(DISTINCT type(left)) AS types,
                 collect(DISTINCT {relationship:type(left),
                    target_id:coalesce(entity.category_id,entity.material_id,entity.gemstone_id),
                    target_name:entity.name, source_product_id:source.product_id,
                    candidate_product_id:p.product_id}) AS paths
            WHERE all(relation IN $required WHERE relation IN types)
            RETURN p.product_id AS ProductID, paths
            ORDER BY size(paths) DESC, ProductID ASC LIMIT 100
        """
        with get_graph_driver().session() as session:
            return [record.data() for record in session.run(cypher, source_id=reference['ProductID'],
                category=reference.get('CategoryID'), material=reference.get('MaterialID'),
                gemstone=reference.get('GemstoneID'), required=understanding.get('required_relationships', []))]
    categories = [e["graph_id"] for e in understanding["entities"] if e["label"] == "Category"]
    gemstones = [e["graph_id"] for e in understanding["entities"] if e["label"] == "Gemstone"]
    if not categories and not gemstones:
        return []
    cypher = """
        MATCH (p:Product)-[rel]->(entity)
        WHERE (type(rel) = 'BELONGS_TO' AND entity:Category AND entity.category_id IN $categories)
           OR (type(rel) = 'HAS_GEMSTONE' AND entity:Gemstone AND entity.gemstone_id IN $gemstones)
        WITH p, collect(DISTINCT {relationship: type(rel),
             target_id: coalesce(entity.category_id, entity.gemstone_id), target_name: entity.name}) AS paths
        RETURN p.product_id AS ProductID, paths
        ORDER BY size(paths) DESC, ProductID ASC LIMIT 100
    """
    with get_graph_driver().session() as session:
        return [record.data() for record in session.run(cypher, categories=categories, gemstones=gemstones)]


# ============================================================
# QDRANT SEARCH
# ============================================================

def search_qdrant(query, top_k=5, eligible_ids=None):
    return _bounded_source(_dense_gate, _search_qdrant, query, top_k=top_k, eligible_ids=eligible_ids)


def _search_qdrant(query, top_k=5, eligible_ids=None):
    if eligible_ids is not None and not eligible_ids:
        return []
    client, model = get_dense_services()
    dimension = model.get_sentence_embedding_dimension()
    if QDRANT_COLLECTION.startswith("jewelry_products_v_"):
        from vector_index import index_identity
        expected, _ = index_identity(EMBEDDING_MODEL, os.getenv("EMBEDDING_REVISION"),
                                     dimension)
        if expected != QDRANT_COLLECTION:
            raise ValueError("Embedding version does not match Qdrant collection")
    elif (QDRANT_COLLECTION != "jewelry_products"
          or EMBEDDING_MODEL != "paraphrase-multilingual-MiniLM-L12-v2"
          or os.getenv("EMBEDDING_REVISION") or dimension != 384):
        raise ValueError("Unversioned collection is only supported for the known legacy embedding contract")
    configuration = client.get_collection(QDRANT_COLLECTION).config.params.vectors
    if (isinstance(configuration, dict) or configuration.size != dimension
            or str(configuration.distance.value).lower() != "cosine"):
        raise ValueError("Qdrant dimension/distance differs from embedding contract")
    vector = model.encode(
        query
    ).tolist()

    query_filter = None
    if eligible_ids is not None:
        from qdrant_client.models import Filter, HasIdCondition
        query_filter = Filter(must=[HasIdCondition(has_id=eligible_ids)])
    results = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=vector,
        query_filter=query_filter,
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

    with get_graph_driver().session() as session:

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

        amount = Decimal(str(price))
        if not amount.is_finite():
            return "Không có thông tin"
        whole, _, fraction = format(amount, "f").partition(".")
        formatted = f"{int(whole):,}".replace(",", ".")
        fraction = fraction.rstrip("0")
        if fraction:
            formatted += "," + fraction
        return formatted + " VNĐ"

    except (
        ValueError,
        InvalidOperation,
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


    # CZ (Cubic Zirconia) là loại đá riêng.
    # Nhận diện như một từ độc lập để tránh khớp nhầm.
    if re.search(r"(?<!\w)cz(?!\w)", query_lower):
        return "cz"

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

    # Khach hang muon san pham co gan da,
    # nhung khong chi dinh loai da cu the.
    if any(phrase in query_lower for phrase in (
        "có đá",
        "gắn đá",
        "đính đá",
        "đá quý"
    )):
        return "__any_gemstone__"

    return None

def search_neo4j_fallback(
    category_keywords,
    price_filter,
    limit=3,
):
    """
    Read-only fallback for category + budget queries.
    Does not modify Qdrant, Neo4j or PostgreSQL.
    """

    if not category_keywords:
        return []

    min_price = price_filter.get("min_price")
    max_price = price_filter.get("max_price")

    if min_price is None and max_price is None:
        return []

    cypher = """
    MATCH (p:Product)-[:BELONGS_TO]->(c:Category)

    WHERE
        any(
            keyword IN $categories
            WHERE toLower(c.name) CONTAINS keyword
        )
        AND p.sale_price IS NOT NULL
        AND p.sale_price > 0
        AND ($min_price IS NULL OR p.sale_price >= $min_price)
        AND ($max_price IS NULL OR p.sale_price <= $max_price)
        AND coalesce(p.stock, 0) > 0

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

    ORDER BY p.sale_price ASC, p.product_id ASC
    LIMIT $limit
    """

    with get_graph_driver().session() as session:
        records = session.run(
            cypher,
            categories=[
                value.lower()
                for value in category_keywords
            ],
            min_price=min_price,
            max_price=max_price,
            limit=min(max(int(limit), 1), 10),
        )

        products = [dict(record) for record in records]

    for product in products:
        product["score"] = 0.0

    return products

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

    # Lấy ít nhất 35 ứng viên trước khi áp dụng
    # bộ lọc loại trang sức, ngân sách và chất liệu.
    candidate_k = max(top_k * 7, 35)

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

        if gemstone == "__any_gemstone__":
            gemstone_ok = (
                bool(product_gemstone)
                and product_gemstone not in (
                    "none",
                    "null",
                    "nan",
                    "không có",
                    "không"
                )
            )
        elif gemstone:
            gemstone_ok = gemstone.lower() in product_gemstone

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

    # Fallback only for category + budget queries
    # without additional material/gemstone restrictions.
    if (
        not filtered
        and category_keywords
        and (
            price_filter.get("min_price") is not None
            or price_filter.get("max_price") is not None
        )
        and not material
        and not gold_type
        and not gemstone
    ):
        print("Qdrant missed matching products. Trying Neo4j fallback.")

        filtered = search_neo4j_fallback(
            category_keywords=category_keywords,
            price_filter=price_filter,
            limit=top_k,
        )

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
    # Nhận diện ngân sách cụ thể:
    # "ngân sách 7 triệu", "budget 5 triệu",
    # "ngân sách khoảng 3 triệu".
    if min_price is None and max_price is None:
        budget_match = re.search(
            r"(?:ngân sách|budget)\s*"
            r"(?:khoảng|tầm|là|của tôi là)?\s*"
            r"(\d+(?:[.,]\d+)?)\s*"
            r"(triệu|nghìn|trăm)\b",
            query_lower,
        )

        if budget_match:
            value = budget_match.group(1).replace(",", ".")
            unit = budget_match.group(2)
            max_price = parse_money(value, unit)

    # Nhận diện ngân sách gần đúng:
    # "tầm 3 triệu", "khoảng 5 triệu",
    # "tầm giá 7 triệu", "giá khoảng 4 triệu".
    if min_price is None and max_price is None:
        approximate_match = re.search(
            r"(?:tầm\s*giá|giá\s*khoảng|tầm|khoảng)"
            r"\s*(\d+(?:[.,]\d+)?)"
            r"\s*(triệu|nghìn|trăm)\b",
            query_lower,
        )

        if approximate_match:
            value = approximate_match.group(1).replace(",", ".")
            unit = approximate_match.group(2)
            max_price = parse_money(value, unit)


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
