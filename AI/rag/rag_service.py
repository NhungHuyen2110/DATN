
from jewelry_agents.retrieval import (
    hybrid_search,
    build_rag_context,
    format_price,
)

import os

from jewelry_agents.business_catalog import fetch_catalog, fetch_shipping_policy, CatalogUnavailable
from jewelry_agents.intent_router import classify_query
from shared.observability import record_intent
from jewelry_agents.search_service import search, RetrievalUnavailable
from jewelry_agents.retrieval import search_qdrant, extract_price_filter, graph_search_candidates
from jewelry_agents.advice_planner import GIFT_INTRO


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
        if product.get('reason'):
            lines.append('  Lý do: ' + product['reason'])

    return "\n".join(lines)


def answer_jewelry_question(query: str, top_k: int = 3):
    query = query.strip()

    if not query:
        return {
            "success": False,
            "answer": "Vui lòng nhập câu hỏi.",
            "message": "Vui lòng nhập câu hỏi.",
            "products": [],
        }

    if os.getenv("LUMIERE_RETRIEVAL_V2_ENABLED", "true").lower() == "true":
        intent = classify_query(query)
        record_intent(intent)
        messages = {
            'greeting': 'Chào bạn! Bạn muốn tìm loại trang sức, chất liệu, loại đá hoặc khoảng giá nào?',
            'restricted_request': 'Kênh tư vấn sản phẩm không cung cấp dữ liệu quản trị, giá vốn hoặc thông tin riêng tư. '
                                  'Các chức năng nghiệp vụ yêu cầu đăng nhập và phân quyền trên trang tương ứng.',
            'customer_order_guidance': 'Bạn hãy đăng nhập và mở mục Đơn hàng của tôi để xem đúng đơn thuộc tài khoản của bạn.',
            'unverified_policy': 'Hiện chưa có chính sách bảo hành hoặc đổi trả đã được xác minh để trả lời. '
                                 'Bạn có thể gửi yêu cầu tại trang Liên hệ.',
            'out_of_scope': 'Tôi hỗ trợ tìm kiếm và lựa chọn trang sức LUMIÈRE. Bạn có thể cho biết loại sản phẩm và ngân sách.'}
        if intent in messages:
            return {'success': True, 'status': intent, 'intent': intent, 'products': [], 'answer': messages[intent]}
        if intent == 'shipping_policy':
            try:
                policy = fetch_shipping_policy()
            except CatalogUnavailable:
                message = 'Tạm thời chưa xác minh được phí vận chuyển hiện tại. Bạn vui lòng thử lại sau.'
                return {'success': False, 'status': 'policy_unavailable', 'products': [], 'answer': message, 'message': message}
            fee, threshold = policy['flat_fee_vnd'], policy['free_from_vnd']
            answer = ('Chính sách hiện tại miễn phí vận chuyển.' if fee == 0 or threshold == 0 else
                      f"Phí vận chuyển hiện tại là {format_price(fee)}; miễn phí với giá trị hàng từ {format_price(threshold)}.")
            return {'success': True, 'status': 'shipping_policy', 'intent': intent,
                    'products': [], 'answer': answer, 'verified_source': 'business_shipping_policy'}
        advice=None
        if os.getenv('LUMIERE_SHOPPING_ADVICE_ENABLED','false').lower()=='true':
            try:
                from jewelry_agents.retrieval import plan_shopping_advice
                advice=plan_shopping_advice(query)
            except Exception:
                pass  # Advice is optional; authoritative retrieval still executes.
        try:
            result = search(query, top_k, dense=search_qdrant, catalog=fetch_catalog,
                            parse_price=extract_price_filter, graph=graph_search_candidates)
        except RetrievalUnavailable:
            return {"success": False, "status": "catalog_unavailable", "products": [],
                    "message": "Tạm thời chưa xác minh được giá và tồn kho. Bạn vui lòng thử lại sau.",
                    "answer": "Tạm thời chưa xác minh được giá và tồn kho. Bạn vui lòng thử lại sau."}
        except ValueError:
            return {"success": False, "status": "invalid_query", "products": [],
                    "message": "Bạn vui lòng yêu cầu Top 1 đến Top 10 sản phẩm.",
                    "answer": "Bạn vui lòng yêu cầu Top 1 đến Top 10 sản phẩm."}
        if result['status'] == 'reference_unavailable':
            return {'success': True, 'status': result['status'], 'products': [],
                    'answer': 'Không xác minh được sản phẩm tham chiếu trong danh mục hiện tại. Bạn vui lòng kiểm tra lại mã sản phẩm.'}
        if result['status'] == 'reference_changed':
            return {'success': True, 'status': result['status'], 'products': [],
                    'answer': 'Thông tin sản phẩm tham chiếu vừa thay đổi. Bạn vui lòng gửi lại yêu cầu để đối soát dữ liệu mới.'}
        if result['status'] == 'clarification_required' and any('reference_' in reason for reason in result['understanding']['ambiguities']):
            return {'success': True, 'status': result['status'], 'products': [],
                    'answer': 'Bạn vui lòng cho biết một mã sản phẩm tham chiếu và thuộc tính cần giống nhau; các điều kiện hiện tại chưa rõ hoặc đang mâu thuẫn.'}
        if result["status"] in {"clarification_required", "missing_verified_attributes"}:
            return {"success": True, "status": result["status"], "products": [],
                    "answer": ("Yêu cầu đã được nhận diện, nhưng danh mục hiện chưa có thuộc tính đã xác minh "
                               "để lọc theo độ tuổi, đối tượng hoặc phong cách này. "
                               "Bạn có thể chọn loại trang sức, chất liệu, loại đá và ngân sách để tìm trước.")}
        products = result["products"]
        answer = build_safe_answer(products) if products else "Không tìm thấy sản phẩm phù hợp với điều kiện hiện tại."
        if advice and advice['intent']=='gift_advice':
            answer=GIFT_INTRO+'\n\n'+answer
        if products and len(products) < result["requested_k"]:
            answer += f"\nHiện chỉ có {len(products)} sản phẩm phù hợp."
        if result["status"] == "degraded":
            answer += "\nMột nguồn tìm kiếm tạm gián đoạn; kết quả chỉ dùng các nguồn đang hoạt động."
        public_products = [{key: value for key, value in p.items()
                            if key not in {"score", "score_type", "rrf_score", "rerank_features", "graph_paths", "retrieval_sources"}}
                           for p in products]
        return {"success": True, "answer": answer, "products": public_products,
                "advice_intent":advice['intent'] if advice else None,
                "status": result["status"], "requested_k": result["requested_k"],
                "returned_k": len(products)}

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
        from jewelry_agents.crew import run_crew
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
