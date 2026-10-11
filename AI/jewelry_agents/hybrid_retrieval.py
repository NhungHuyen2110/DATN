# ============================================================
# HYBRID RETRIEVAL
# QDRANT + NEO4J + RAG + QWEN 3B
# ============================================================

import requests
import json

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase


# ============================================================
# 1. CONFIG
# ============================================================

QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "jewelry_products"

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "12345678"

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:3b"

TOP_K = 5


# ============================================================
# 2. KẾT NỐI QDRANT
# ============================================================

print("Đang kết nối Qdrant...")

qdrant_client = QdrantClient(
    url=QDRANT_URL
)


# ============================================================
# 3. LOAD EMBEDDING MODEL
# ============================================================

print("Đang tải embedding model...")

embedding_model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

print("Qdrant + Embedding sẵn sàng.")


# ============================================================
# 4. KẾT NỐI NEO4J
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
# 5. QDRANT SEARCH
# ============================================================

def search_qdrant(query, top_k=5):

    vector = embedding_model.encode(
        query
    ).tolist()

    result = qdrant_client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=vector,
        limit=top_k,
        with_payload=True
    )

    products = []

    for point in result.points:

        payload = point.payload or {}

        product_id = (
            payload.get("ProductID")
            or payload.get("product_id")
            or payload.get("id")
        )

        product_name = (
            payload.get("ProductName")
            or payload.get("name")
            or "Không có tên"
        )

        products.append({
            "ProductID": product_id,
            "ProductName": product_name,
            "Score": float(point.score),
            "Payload": payload
        })

    return products


# ============================================================
# 6. NEO4J ENRICHMENT
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
            product_id=product_id
        )

        record = result.single()

        if record is None:
            return None

        return dict(record)


# ============================================================
# 7. HYBRID SEARCH
# ============================================================

def hybrid_search(query, top_k=5):

    print()
    print("=" * 70)
    print("QDRANT SEARCH")
    print("=" * 70)

    print("Query:", query)

    qdrant_results = search_qdrant(
        query,
        top_k
    )

    print()
    print("Qdrant tìm được:")

    for item in qdrant_results:

        print(
            f"- {item['ProductID']} | "
            f"{item['ProductName']} | "
            f"{item['Score']:.4f}"
        )

    print()
    print("=" * 70)
    print("NEO4J ENRICHMENT")
    print("=" * 70)

    hybrid_results = []

    for item in qdrant_results:

        product_id = item["ProductID"]

        neo4j_product = get_product_from_neo4j(
            product_id
        )

        if neo4j_product:

            neo4j_product["Score"] = item["Score"]

            hybrid_results.append(
                neo4j_product
            )

            print(
                f"- {neo4j_product['ProductID']} | "
                f"{neo4j_product['ProductName']} | "
                f"{neo4j_product['Category']} | "
                f"{neo4j_product['Brand']} | "
                f"{neo4j_product['Material']} | "
                f"{neo4j_product['Gemstone']} | "
                f"{neo4j_product['Collection']} | "
                f"{neo4j_product['Price']} | "
                f"Score: {neo4j_product['Score']:.4f}"
            )

    # ========================================================
    # HYBRID FILTERING
    # ========================================================

    print()
    print("=" * 70)
    print("HYBRID FILTERING")
    print("=" * 70)

    query_lower = query.lower()

    # --------------------------------------------------------
    # Xác định chất liệu người dùng yêu cầu
    # --------------------------------------------------------

    material_keywords = [
        "vàng",
        "bạc",
        "bạch kim",
        "platinum"
    ]

    requested_material = None

    for keyword in material_keywords:

        if keyword in query_lower:

            requested_material = keyword
            break

    # --------------------------------------------------------
    # Xác định loại sản phẩm người dùng yêu cầu
    # --------------------------------------------------------

    category_keywords = {
        "vòng tay": [
            "vòng tay",
            "lắc tay"
        ],

        "lắc tay": [
            "lắc tay",
            "vòng tay"
        ],

        "nhẫn": [
            "nhẫn"
        ],

        "dây chuyền": [
            "dây chuyền"
        ],

        "bông tai": [
            "bông tai",
            "hoa tai"
        ],

        "charm": [
            "charm"
        ]
    }

    requested_category = None

    for category, keywords in category_keywords.items():

        for keyword in keywords:

            if keyword in query_lower:

                requested_category = category
                break

        if requested_category:
            break

    print(
        "Chất liệu yêu cầu:",
        requested_material
    )

    print(
        "Danh mục yêu cầu:",
        requested_category
    )

    # --------------------------------------------------------
    # LỌC SẢN PHẨM
    # --------------------------------------------------------

    filtered_results = []

    for product in hybrid_results:

        material = str(
            product.get("Material", "")
        ).lower()

        category = str(
            product.get("Category", "")
        ).lower()

        material_match = True
        category_match = True

        # ----------------------------------------------------
        # Filter material
        # ----------------------------------------------------

        if requested_material:

            if requested_material == "vàng":

                material_match = (
                    "vàng" in material
                )

            elif requested_material == "bạc":

                material_match = (
                    "bạc" in material
                )

            elif requested_material in [
                "bạch kim",
                "platinum"
            ]:

                material_match = (
                    "bạch kim" in material
                    or "platinum" in material
                )

        # ----------------------------------------------------
        # Filter category
        # ----------------------------------------------------

        if requested_category:

            accepted_categories = category_keywords[
                requested_category
            ]

            category_match = any(
                keyword in category
                for keyword in accepted_categories
            )

        # ----------------------------------------------------
        # Kết quả
        # ----------------------------------------------------

        if material_match and category_match:

            filtered_results.append(
                product
            )

            print(
                f"[GIỮ] {product['ProductID']} | "
                f"{product['ProductName']} | "
                f"{product['Material']}"
            )

        else:

            print(
                f"[LOẠI] {product['ProductID']} | "
                f"{product['ProductName']} | "
                f"{product['Material']}"
            )

    # --------------------------------------------------------
    # Nếu không có kết quả sau filter
    # --------------------------------------------------------

    if not filtered_results:

        print(
            "Không có sản phẩm nào vượt qua Hybrid Filtering."
        )

        return []

    # --------------------------------------------------------
    # Re-ranking
    # --------------------------------------------------------

    filtered_results.sort(
        key=lambda x: x["Score"],
        reverse=True
    )

    return filtered_results


# ============================================================
# 8. BUILD RAG CONTEXT
# ============================================================

def build_rag_context(products):

    if not products:
        return "Không tìm thấy sản phẩm phù hợp."

    context = []

    for product in products:

        price = format_price(
            product.get("Price")
        )

        text = f"""
Sản phẩm:
- ProductID: {product.get('ProductID')}
- Tên: {product.get('ProductName')}
- Danh mục: {product.get('Category')}
- Thương hiệu: {product.get('Brand')}
- Chất liệu: {product.get('Material')}
- Đá quý: {product.get('Gemstone')}
- Bộ sưu tập: {product.get('Collection')}
- Giá bán chính xác: {price}
- Tồn kho: {product.get('Stock')}
- SKU: {product.get('SKU')}
- Điểm tương đồng Qdrant: {product.get('Score')}
"""

        context.append(
            text.strip()
        )

    return "\n\n".join(context)

def format_price(price):
    """
    Chuyển giá từ số thực/số nguyên
    sang định dạng VNĐ dễ đọc.

    Ví dụ:
    10898911.0 -> 10.898.911 VNĐ
    """

    if price is None:
        return "Không có thông tin"

    try:
        price = int(float(price))

        return f"{price:,}".replace(",", ".") + " VNĐ"

    except (ValueError, TypeError):

        return str(price)


# ============================================================
# 9. RAG GENERATION - QWEN 3B
# ============================================================

def generate_answer(user_query, context):

    system_prompt = """
Bạn là trợ lý tư vấn trang sức.

Trả lời bằng tiếng Việt.

Chỉ sử dụng dữ liệu trong CONTEXT.

Không được tự tạo sản phẩm.
Không được tự tạo ProductID.
Không được tự tạo giá.
Không được thay đổi giá.
Không được nhân hoặc chia giá.
Không được thêm thông tin không có trong CONTEXT.

Nếu có sản phẩm phù hợp, giới thiệu tối đa 3 sản phẩm.

Giá phải giữ nguyên chính xác như CONTEXT.

Ví dụ:
Nếu CONTEXT ghi:
Giá bán chính xác: 10.898.911 VNĐ

thì câu trả lời phải ghi:
10.898.911 VNĐ
"""

    user_prompt = f"""
Khách hàng hỏi:

{user_query}

Dữ liệu sản phẩm:

{context}

Hãy trả lời ngắn gọn bằng tiếng Việt.
"""

    payload = {
        "model": OLLAMA_MODEL,

        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],

        "stream": False,

        "options": {
            "temperature": 0.1,
            "num_predict": 300
        }
    }

    print()
    print("Đang gửi yêu cầu tới Qwen 3B...")

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=180
    )

    print(
        "Ollama HTTP:",
        response.status_code
    )

    response.raise_for_status()

    data = response.json()

    print(
        "Ollama done:",
        data.get("done")
    )

    print(
        "Ollama done_reason:",
        data.get("done_reason")
    )

    message = data.get(
        "message",
        {}
    )

    answer = message.get(
        "content",
        ""
    )

    print(
        "Độ dài câu trả lời:",
        len(answer)
    )

    if not answer.strip():

        return (
            "Qwen 3B không trả về nội dung. "
            "Vui lòng kiểm tra Ollama."
        )

    return answer.strip()

    user_prompt = f"""
CÂU HỎI CỦA KHÁCH HÀNG:

{user_query}


CONTEXT:

{context}


Hãy tư vấn sản phẩm phù hợp.
"""

    payload = {
        "model": OLLAMA_MODEL,

        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],

        "stream": False,

        "options": {
            "temperature": 0.2
        }
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=120
    )

    response.raise_for_status()

    data = response.json()

    return data["message"]["content"]


# ============================================================
# 10. MAIN TEST
# ============================================================

if __name__ == "__main__":

    try:

        user_query = (
            "Tìm cho tôi một chiếc vòng tay bằng bạch kim"
        )

        print()
        print("=" * 70)
        print("HYBRID RETRIEVAL")
        print("=" * 70)

        # ----------------------------------------------------
        # HYBRID SEARCH
        # ----------------------------------------------------

        products = hybrid_search(
            user_query,
            TOP_K
        )

        # ----------------------------------------------------
        # HIỂN THỊ KẾT QUẢ
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("HYBRID RETRIEVAL RESULT")
        print("=" * 70)

        for product in products:

            print()
            print(
                "ProductID:",
                product.get("ProductID")
            )

            print(
                "Tên:",
                product.get("ProductName")
            )

            print(
                "Danh mục:",
                product.get("Category")
            )

            print(
                "Thương hiệu:",
                product.get("Brand")
            )

            print(
                "Chất liệu:",
                product.get("Material")
            )

            print(
                "Đá quý:",
                product.get("Gemstone")
            )

            print(
                "Bộ sưu tập:",
                product.get("Collection")
            )

            print(
                "Giá:",
                format_price(product.get("Price"))
            )

            print(
                "Score:",
                product.get("Score")
            )

        # ----------------------------------------------------
        # BUILD RAG CONTEXT
        # ----------------------------------------------------

        context = build_rag_context(
            products
        )

        print()
        print("=" * 70)
        print("RAG CONTEXT")
        print("=" * 70)

        print(context)

        # ----------------------------------------------------
        # QWEN GENERATION
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("QWEN 3B - RAG GENERATION")
        print("=" * 70)

        answer = generate_answer(
            user_query,
            context
        )

        print()
        print("CÂU TRẢ LỜI CUỐI CÙNG:")
        print()
        print(answer)

    finally:

        neo4j_driver.close()