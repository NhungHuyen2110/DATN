
from jewelry_agents.retrieval import (
    hybrid_search,
    build_rag_context
)

from jewelry_agents.crew import run_crew


def answer_jewelry_question(query: str, top_k: int = 3):
    query = query.strip()

    if not query:
        return {
            "success": False,
            "answer": "Vui lòng nhập câu hỏi.",
            "products": []
        }

    # 1. Tìm sản phẩm bằng Qdrant + Neo4j
    products = hybrid_search(
        query,
        top_k=top_k
    )

    # 2. Không có sản phẩm phù hợp
    if not products:
        return {
            "success": True,
            "answer": "Không tìm thấy sản phẩm phù hợp.",
            "products": []
        }

    # 3. Tạo RAG Context
    context = build_rag_context(products)

    # 4. Sinh câu trả lời bằng CrewAI + Qwen
    answer = run_crew(query, context)

    # 5. Trả về dữ liệu
    return {
        "success": True,
        "answer": answer,
        "products": products
    }
