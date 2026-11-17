
from jewelry_agents.retrieval import (
    hybrid_search,
    build_rag_context,
    format_price,
)

from jewelry_agents.crew import run_crew


def build_safe_answer(products):
    """
    Generate a grounded response using retrieved product data.
    Never invent names, IDs or prices.
    """
    lines = [
        "Đây là các sản phẩm phù hợp với yêu cầu của bạn:"
    ]

    for product in products:
        lines.extend([
            "",
            f"• {product.get('ProductName', 'Sản phẩm')}",
            f"  Mã sản phẩm: {product.get('ProductID')}",
            f"  Chất liệu: {product.get('Material') or 'Chưa cập nhật'}",
            f"  Đá quý: {product.get('Gemstone') or 'Chưa cập nhật'}",
            f"  Giá bán: {format_price(product.get('Price'))}",
        ])

    return "\n".join(lines)


def answer_jewelry_question(query: str, top_k: int = 3):
    query = query.strip()

    if not query:
        return {
            "success": False,
            "answer": "Vui lòng nhập câu hỏi.",
            "products": [],
        }

    products = hybrid_search(
        query,
        top_k=top_k,
    )

    if not products:
        return {
            "success": True,
            "answer": "Không tìm thấy sản phẩm phù hợp.",
            "products": [],
        }

    context = build_rag_context(products)

    # Keep existing CrewAI generation
    try:
        answer = str(run_crew(query, context)).strip()
    except Exception:
        answer = ""

    invalid_phrases = [
        "không tìm thấy sản phẩm",
        "không có sản phẩm phù hợp",
        "không tìm được sản phẩm",
        "hệ thống không tìm thấy",
    ]

    if (
        not answer
        or any(
            phrase in answer.lower()
            for phrase in invalid_phrases
        )
    ):
        answer = build_safe_answer(products)

    return {
        "success": True,
        "answer": answer,
        "products": products,
    }
