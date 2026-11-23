
from jewelry_agents.retrieval import (
    hybrid_search,
    build_rag_context,
    format_price,
)

import os
from functools import partial

from jewelry_agents.business_catalog import fetch_catalog, fetch_shipping_policy, CatalogUnavailable
from jewelry_agents.intent_router import classify_query
from shared.observability import record_intent
from jewelry_agents.search_service import search, RetrievalUnavailable
from jewelry_agents.retrieval import search_qdrant, extract_price_filter, graph_search_candidates, graph_expand_candidates
from jewelry_agents.advice_planner import GIFT_INTRO
from jewelry_agents.shopping_advice import advisory_request, advice_intro, next_question, budget_text, strict_preference_request
from jewelry_agents.entity_linking import link_query


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


def answer_jewelry_question(query: str, top_k: int = 3, semantic_plan=None):
    original_query=query.strip()
    query = budget_text(query.strip())

    if not query:
        return {
            "success": False,
            "answer": "Vui lòng nhập câu hỏi.",
            "message": "Vui lòng nhập câu hỏi.",
            "products": [],
        }

    if os.getenv("LUMIERE_RETRIEVAL_V2_ENABLED", "true").lower() == "true":
        advice=None
        intent = classify_query(query)
        if semantic_plan is not None and semantic_plan.intent in {'shop','consult'} and intent not in {
                'restricted_request','shipping_policy','unverified_policy','customer_order_guidance'}:
            intent='product_search'
        advisory = intent == 'product_search' and advisory_request(query)
        if semantic_plan is not None and semantic_plan.intent=='consult' and not strict_preference_request(query):
            advisory=True
        if semantic_plan is None and intent=='general_question' and os.getenv('LUMIERE_SHOPPING_ADVICE_ENABLED','false').lower()=='true':
            try:
                from jewelry_agents.retrieval import plan_shopping_advice
                advice=plan_shopping_advice(query)
                if advice.get('accepted') and advice['intent'] in {'gift_advice','product_search'}:
                    intent='product_search'
            except Exception:
                pass
        record_intent(intent)
        messages = {
            'greeting': 'Chào bạn! Bạn muốn tìm loại trang sức, chất liệu, loại đá hoặc khoảng giá nào?',
            'restricted_request': 'Kênh tư vấn sản phẩm không cung cấp dữ liệu quản trị, giá vốn hoặc thông tin riêng tư. '
                                  'Các chức năng nghiệp vụ yêu cầu đăng nhập và phân quyền trên trang tương ứng.',
            'customer_order_guidance': 'Bạn hãy đăng nhập và mở mục Đơn hàng của tôi để xem đúng đơn thuộc tài khoản của bạn.',
            'unverified_policy': 'Hiện chưa có chính sách bảo hành hoặc đổi trả đã được xác minh để trả lời. '
                                 'Bạn có thể gửi yêu cầu tại trang Liên hệ.',
            'out_of_scope': 'Tôi hỗ trợ tìm kiếm và lựa chọn trang sức LUMIÈRE. Bạn có thể cho biết loại sản phẩm và ngân sách.'}
        messages['general_question']=(
            'Tôi hiểu đây là câu hỏi trao đổi, không phải yêu cầu tìm sản phẩm. '
            'Bạn có thể nói rõ phần bạn muốn tìm hiểu; tôi sẽ không tự thêm danh sách gợi ý. '
            'Lớp trả lời tự nhiên hiện chưa sẵn sàng, nên tôi không muốn đoán câu trả lời.')
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
        # A style consultation already has an intent. Do not encode it a second
        # time just to run the optional gift prototype classifier.
        has_preferences = any(e['label'] in {'Audience','Style'} for e in link_query(query)['entities'])
        if (semantic_plan is None and not advisory and not has_preferences and advice is None and
                os.getenv('LUMIERE_SHOPPING_ADVICE_ENABLED','false').lower()=='true'):
            try:
                from jewelry_agents.retrieval import plan_shopping_advice
                advice=plan_shopping_advice(query)
            except Exception:
                pass  # Advice is optional; authoritative retrieval still executes.
        try:
            from jewelry_agents.query_reference import reference_request
            if advice and advice.get('accepted') and advice.get('semantic_category_scores') and not reference_request(query)['active']:
                from .category_clarification import category_question
                clarification=category_question(query,advice['semantic_category_scores'])
                if clarification:return clarification
            dense = (partial(search_qdrant, request_embedding=advice['_request_embedding'])
                     if advice and advice.get('_request_embedding') is not None else search_qdrant)
            options = {'preference_mode': 'advisory'} if advisory else {}
            if advice and getattr(advice.get('_request_embedding'),'entity_links',()):
                options['entity_context']=advice['_request_embedding']
            if semantic_plan is not None:options.update(semantic_plan=semantic_plan,semantic_source_query=original_query)
            result = search(query, top_k, dense=dense, catalog=fetch_catalog,
                            parse_price=extract_price_filter, graph=graph_search_candidates,
                            graph_expander=graph_expand_candidates, **options)
        except RetrievalUnavailable:
            if advisory:
                return {'success':True, 'intent':'shopping_advice', 'advice_intent':'style_advice',
                    'status':'catalog_unavailable', 'products':[],
                    'answer':advice_intro(query)+'\n\nMình chưa kiểm tra được giá và tồn kho lúc này, nên chưa đưa tên mẫu cụ thể. '+next_question(query)}
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
            understanding = result.get('understanding') or link_query(query)
            if 'child_catalog_not_verified' in understanding.get('ambiguities', []):
                message = 'Bạn đang chọn cho bé bao nhiêu tuổi? Mình cần biết độ tuổi và kích cỡ trước, không dùng mẫu người lớn để suy ra là phù hợp cho bé.'
            else:
                message = (advice_intro(query)+'\n\nMình chưa xác nhận được mẫu nào đáp ứng chính xác nhãn bạn yêu cầu. '
                    'Bạn có thể chọn theo loại trang sức, chất liệu và ngân sách trước. '+next_question(query))
            return {"success": True, "status": result["status"], "products": [],
                    "answer": message}
        products = result["products"]
        for product in products:
            if product.get('graph_paths'):
                product['matched_relationships']=[{key:value for key,value in path.items() if key in
                    {'relationship','target_id','target_name','source_product_id'}} for path in product['graph_paths']]
        retrieval_metadata={'retrieval_sources_used':result.get('retrieval_sources_used',[]),
            'resolved_entities':result.get('understanding',{}).get('entities',[]),
            'query_planning_method':'local_llm_semantic' if semantic_plan is not None else 'existing_query_understanding'}
        if advisory:
            unverified = result.get('understanding', {}).get('unverified_preferences', [])
            answer = advice_intro(query)
            if products:
                answer += '\n\nBạn có thể xem các mẫu còn hàng bên dưới để so sánh kiểu dáng và giá.'
                if unverified:
                    answer += ' Đây là các lựa chọn tham khảo; mình chưa khẳng định từng mẫu đã được phân loại đúng gu bạn nêu.'
            elif result['status'] == 'degraded':
                answer += '\n\nHiện mình chưa kiểm tra được danh sách mẫu cụ thể; phần tư vấn cách chọn vẫn có thể giúp bạn thu hẹp lựa chọn.'
            else:
                answer += '\n\nChưa có mẫu còn hàng đáp ứng những điều kiện kiểm tra được trong yêu cầu này.'
            answer += '\n\n'+next_question(query)
            public_products = [{key:value for key,value in p.items() if key not in
                {'score','score_type','rrf_score','rerank_features','graph_paths','retrieval_sources'}} for p in products]
            return {'success':True,'intent':'shopping_advice','advice_intent':'style_advice',**retrieval_metadata,
                'answer':answer,'products':public_products,'status':result['status'],
                'requested_k':result['requested_k'],'returned_k':len(products),
                'recommendation_scope':'advisory_unverified_preferences' if unverified else 'verified_recommendations',
                'unverified_preferences':unverified}
        answer = build_safe_answer(products) if products else "Không tìm thấy sản phẩm phù hợp với điều kiện hiện tại."
        if not products and result['status']=='degraded':
            answer=('Một nguồn tìm kiếm chưa sẵn sàng, nên tôi chưa thể xác nhận danh sách phù hợp. '
                    'Bạn hãy thử lại sau; tôi không muốn kết luận là không có sản phẩm khi nguồn tìm kiếm đang gián đoạn.')
        if advice and advice['intent']=='gift_advice':
            answer=GIFT_INTRO+'\n\n'+answer
        if products and len(products) < result["requested_k"]:
            answer += f"\nHiện chỉ có {len(products)} sản phẩm phù hợp."
        if result["status"] == "degraded":
            answer += "\nMột nguồn tìm kiếm tạm gián đoạn; kết quả chỉ dùng các nguồn đang hoạt động."
        public_products = [{key: value for key, value in p.items()
                            if key not in {"score", "score_type", "rrf_score", "rerank_features", "graph_paths", "retrieval_sources"}}
                           for p in products]
        return {"success": True, "answer": answer, "products": public_products,**retrieval_metadata,
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
