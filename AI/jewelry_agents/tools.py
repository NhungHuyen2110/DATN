from typing import Type
from pydantic import BaseModel, Field

from crewai.tools import BaseTool

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from neo4j import GraphDatabase


# =========================================================
# QDRANT CONFIG
# =========================================================

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "jewelry_products"

qdrant_client = QdrantClient(
    url=QDRANT_URL
)

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

embedding_model = SentenceTransformer(
    MODEL_NAME
)


# =========================================================
# NEO4J CONFIG
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
# QDRANT TOOL INPUT
# =========================================================

class QdrantSearchInput(BaseModel):

    query: str = Field(
        ...,
        description=(
            "Yêu cầu tìm kiếm sản phẩm trang sức "
            "bằng ngôn ngữ tự nhiên."
        )
    )

    top_k: int = Field(
        default=5,
        description=(
            "Số lượng sản phẩm muốn tìm."
        )
    )


# =========================================================
# QDRANT SEARCH TOOL
# =========================================================

class QdrantSearchTool(BaseTool):

    name: str = "qdrant_product_search"

    description: str = (
        "Tìm kiếm sản phẩm trang sức bằng "
        "semantic vector search trong Qdrant. "
        "Sử dụng tool này khi cần tìm sản phẩm "
        "phù hợp với yêu cầu tự nhiên của khách hàng."
    )

    args_schema: Type[BaseModel] = QdrantSearchInput

    def _run(
        self,
        query: str,
        top_k: int = 5
    ) -> str:

        try:

            vector = embedding_model.encode(
                query
            ).tolist()

            results = qdrant_client.query_points(
                collection_name=COLLECTION_NAME,
                query=vector,
                limit=top_k,
                with_payload=True
            ).points

            if not results:

                return (
                    "Qdrant không tìm thấy sản phẩm "
                    "phù hợp."
                )

            output = []

            for result in results:

                payload = result.payload or {}

                product_id = payload.get(
                    "ProductID",
                    payload.get("product_id")
                )

                product_name = payload.get(
                    "ProductName",
                    payload.get("product_name")
                )

                output.append(
                    {
                        "product_id": product_id,
                        "product_name": product_name,
                        "score": result.score,
                        "payload": payload
                    }
                )

            return str(output)

        except Exception as e:

            return (
                "Lỗi khi tìm kiếm Qdrant: "
                + str(e)
            )


# =========================================================
# NEO4J TOOL INPUT
# =========================================================

class Neo4jProductInput(BaseModel):

    product_ids: str = Field(
        ...,
        description=(
            "Danh sách ProductID cần tìm trong Neo4j, "
            "phân cách bằng dấu phẩy. "
            "Ví dụ: 1,2,3,4,5"
        )
    )


# =========================================================
# NEO4J PRODUCT TOOL
# =========================================================

class Neo4jProductTool(BaseTool):

    name: str = "neo4j_product_lookup"

    description: str = (
        "Truy vấn Knowledge Graph Neo4j để lấy "
        "thông tin chi tiết và quan hệ của sản phẩm "
        "trang sức như danh mục, thương hiệu, "
        "chất liệu, đá quý, bộ sưu tập, giá và tồn kho."
    )

    args_schema: Type[BaseModel] = Neo4jProductInput

    def _run(
        self,
        product_ids: str
    ) -> str:

        try:

            ids = []

            for value in product_ids.split(","):

                value = value.strip()

                if value:

                    ids.append(
                        int(value)
                    )

            if not ids:

                return (
                    "Không có ProductID hợp lệ."
                )

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

                p.sku AS sku,

                p.sale_price AS sale_price,

                p.wholesale_price AS wholesale_price,

                p.cost_price AS cost_price,

                p.stock AS stock,

                p.weight AS weight,

                category.name AS category,

                brand.name AS brand,

                material.name AS material,

                gemstone.name AS gemstone,

                collection.name AS collection

            ORDER BY p.product_id
            """

            with neo4j_driver.session() as session:

                result = session.run(
                    query,
                    product_ids=ids
                )

                records = [
                    record.data()
                    for record in result
                ]

            if not records:

                return (
                    "Neo4j không tìm thấy sản phẩm "
                    "với các ProductID đã cung cấp."
                )

            return str(records)

        except Exception as e:

            return (
                "Lỗi khi truy vấn Neo4j: "
                + str(e)
            )


# =========================================================
# CLOSE CONNECTION
# =========================================================

def close_connections():

    try:
        neo4j_driver.close()
    except Exception:
        pass