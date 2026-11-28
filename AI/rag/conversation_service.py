"""Customer-only conversation coordinator; shared business conversation unchanged."""
from shared import conversation as shared
from jewelry_agents.shopping_advice import followup_query, standalone_budget
from jewelry_agents.intent_router import classify_query
from jewelry_agents.entity_linking import link_query
from jewelry_agents.dialogue_state_controller import prepare_refinement, missing_refinement_field, cheaper_request, prepare_state, identity_request
from jewelry_agents.dialogue_state_query import render_shopping_query
from jewelry_agents.dialogue_state import ShoppingState, PendingClarification
from jewelry_agents.query_reference import reference_request
from jewelry_agents.retrieval import extract_price_filter
from .domain_dialogue import domain_answer
from .contextual_response import (
    compact_shopping_answer,
    explain_previous_products
)
import os
import time
import re


def _clarify(row, goal, answer, *, mode='state_preserving_clarification'):
    pending = row.get('pending_clarification')
    attempts = pending.attempts + 1 if isinstance(pending, PendingClarification) and pending.goal == goal else 1
    row['pending_clarification'] = PendingClarification(goal, attempts)
    if attempts > 1:
        answer = ('Mình tạm dừng tìm kiếm và giữ các điều kiện hiện tại. '
                  'Bạn có thể nêu loại trang sức hoặc điều kiện cụ thể, '
                  'nói “bắt đầu lại” để bỏ điều kiện cũ, hoặc “hủy” để dừng câu hỏi này.')
        mode = 'clarification_escape'
    return {'success': True, 'intent': 'clarification', 'status': 'clarification_required',
            'products': [], 'answer': answer, 'response_mode': mode}


def _control_turn(message, row, top_k):
    """Cheap task policy runs before either deterministic or optional planner NLU."""
    from jewelry_agents.dialogue_state_controller import task_transition
    guard = classify_query(message)
    if guard in {'restricted_request', 'shipping_policy', 'unverified_policy', 'customer_order_guidance'}:
        return None
    text = shared.normalized(message)
    if guard == 'greeting' or text in {'ban giup duoc gi', 'ban co the lam gi', 'huong dan su dung'}:
        for key in ('pending_slot', 'pending_category', 'pending_clarification', 'semantic_pending', 'pending_refinement'):
            row.pop(key, None)
        return {'success': True, 'intent': 'greeting', 'status': 'ok', 'products': [],
                'answer': 'Chào bạn! Mình có thể tìm trang sức theo loại, chất liệu, đá và ngân sách; tư vấn quà tặng, so sánh hoặc giải thích các mẫu đã xem. Bạn đang muốn chọn món gì?'}
    if shared.knowledge_request(message):
        return None
    if guard in {'general_question', 'product_search'} and not reference_request(message)['active']:
        from jewelry_agents.dialogue_state_extractor import extract_state_changes
        from jewelry_agents.dialogue_plan_validator import _positive_entity
        try:
            updates, _ = extract_state_changes(message, extract_price_filter)
            if any(field in updates and not _positive_entity(field, updates[field], message)
                   for field in ('category', 'material', 'gemstone', 'audience', 'style')):
                return _clarify(row, 'constraints', 'Mình chưa hiểu điều kiện thay thế cho phần bạn phủ định. Bạn muốn chọn loại, chất liệu hoặc đá nào? Mình giữ điều kiện cũ.')
        except (ValueError, TypeError):
            return _clarify(row, 'constraints', 'Các điều kiện trong câu này chưa xác định được một lựa chọn hợp lệ. Bạn muốn dùng chất liệu hoặc mức giá nào? Mình giữ điều kiện cũ.')
    if text in {'huy', 'dung lai', 'thoi', 'bo qua'}:
        for key in ('pending_slot', 'pending_category', 'pending_clarification', 'semantic_pending', 'pending_refinement'):
            row.pop(key, None)
        return {'success': True, 'intent': 'conversation_navigation', 'status': 'ok', 'products': [],
                'answer': 'Mình đã dừng câu hỏi đang chờ và giữ các điều kiện mua sắm. Bạn có thể tiếp tục khi cần.'}
    pending = row.get('pending_clarification')
    transition = task_transition(message, pending.goal if isinstance(pending, PendingClarification) else None)
    if transition == 'return':
        row.pop('pending_clarification', None)
        return {'success': True, 'intent': 'unverified_policy', 'status': 'unsupported', 'products': [],
                'answer': 'Bạn đang cần đổi sản phẩm đã mua. Mình chưa có chính sách đổi trả đã xác minh và không thể thực hiện đổi trả trong chat. Bạn liên hệ cửa hàng qua kênh hỗ trợ chính thức, kèm mã đơn và vấn đề cần hỗ trợ nhé.'}
    if transition == 'exchange':
        return _clarify(row, 'exchange', 'Bạn muốn đổi mẫu đang được tư vấn hay đổi trả sản phẩm đã mua?')
    if transition == 'selection':
        row.pop('pending_category', None)
        row.pop('semantic_pending', None)
        # A concrete category/material in this reply can be consumed normally.
        from jewelry_agents.dialogue_state_extractor import extract_state_changes
        updates, clear = extract_state_changes(message, extract_price_filter)
        if not updates and not clear:
            return _clarify(row, 'selection', 'Bạn muốn xem loại trang sức hoặc thay điều kiện nào? Mình giữ ngân sách và các điều kiện cũ đến khi bạn yêu cầu đổi.')
    if transition == 'keep':
        return {'success': True, 'intent': 'conversation_navigation', 'status': 'ok', 'products': [],
                'answer': 'Mình giữ nguyên yêu cầu hiện tại.'}
    if transition == 'reset':
        for key in ('shopping_state', 'shopping_context', 'pending_slot', 'pending_category',
                    'pending_clarification', 'semantic_pending', 'pending_refinement', 'last_result', 'last_result_state', 'selected_product_ids'):
            row.pop(key, None)
        from jewelry_agents.dialogue_state_extractor import extract_state_changes
        updates, clear = extract_state_changes(message, extract_price_filter)
        # A new task can start with budget/material before a category is chosen.
        row['shopping_state'] = ShoppingState(top_k=top_k)
        if updates or clear:
            return None
        return _clarify(row, 'category', 'Mình đã bắt đầu nhu cầu mới và bỏ điều kiện cũ. Bạn muốn chọn loại trang sức nào?')
    return None


def _remember_legacy_result(row, effective, result, top_k):
    """Compatibility path state writes also belong to this coordinator."""
    if result.get('clarification_options'):
        row['shopping_context']=effective
        row['pending_category']={'query':effective,'options':result['clarification_options']}
        try:
            from jewelry_agents.dialogue_state_extractor import extract_state_changes
            from jewelry_agents.dialogue_state import StatePatch
            updates, clear = extract_state_changes(effective, extract_price_filter)
            row['shopping_state'] = StatePatch(updates, frozenset(clear)).apply(
                row.get('shopping_state') or ShoppingState(top_k=top_k))
        except (ValueError, TypeError):
            pass
    elif result.get('advice_intent')=='style_advice':
        row['shopping_context']=effective if effective.startswith('Tư vấn ') else 'Tư vấn '+effective
        # Advisory style/audience are preferences, never verified product facts.
        from jewelry_agents.dialogue_state_extractor import extract_state_changes
        from jewelry_agents.dialogue_state import StatePatch
        try:
            updates, clear = extract_state_changes(effective, extract_price_filter)
            updates = {k: v for k, v in updates.items() if k not in {'audience', 'style'}}
            row['shopping_state'] = StatePatch(updates, frozenset(clear)).apply(
                row.get('shopping_state') or ShoppingState(top_k=top_k))
        except (TypeError, ValueError):
            pass
    elif result.get('products'):
        row['shopping_context']=effective
    if (result.get('success') is not False and result.get('status') in {'ok','degraded'}
            and not result.get('clarification_options') and result.get('advice_intent')!='style_advice'):
        try:
            candidate=prepare_state(effective,extract_price_filter,top_k=top_k,allow_partial=True)
            if candidate is not None:
                row['shopping_state']=candidate
                row['shopping_context']=render_shopping_query(candidate)
        except (TypeError,ValueError):
            pass


def converse(message, conversation_id, scope, tool, top_k=3):
    token,row=shared.STORE.resolve(conversation_id,scope)
    if not row['lock'].acquire(blocking=False):
        return {'success':False,'status':'conversation_busy','products':[],
                'answer':'Mình đang xử lý câu trước, bạn đợi câu trả lời rồi gửi tiếp nhé.',
                'conversation_id':token}
    try:
        control = _control_turn(message, row, top_k)
        if control is not None:
            row['history'] = [*row['history'], {'user': message, 'answer': control['answer']}][-6:]
            return {**control, 'conversation_id': token}
        # Explicit policy/security/new-domain requests precede references and
        # pending category handlers. The existing tool remains policy authority.
        if classify_query(message) in {'restricted_request', 'shipping_policy', 'unverified_policy',
                                      'customer_order_guidance', 'out_of_scope'}:
            response = tool(message)
            for key in ('pending_slot', 'pending_category', 'pending_clarification', 'semantic_pending', 'pending_refinement'):
                row.pop(key, None)
            row['history'] = [*row['history'], {'user': message, 'answer': response['answer']}][-6:]
            return {**response, 'conversation_id': token}
        if os.getenv('LUMIERE_HYBRID_NLU_ENABLED','false').lower()=='true':
            from .semantic_conversation import semantic_turn
            response=semantic_turn(message,row,tool,top_k=top_k)
            return {**response,'conversation_id':token}
        raw_tool=tool
        def legacy_tool(query, **options):
            result=raw_tool(query,**options)
            _remember_legacy_result(row,query,result,top_k)
            return result
        tool=legacy_tool
        started=time.monotonic()
        previous_shopping_state = row.get('shopping_state')
        if row.get('pending_refinement') and row.get('pending_slot'):
            from jewelry_agents.dialogue_state_extractor import extract_state_changes
            try:
                updates, clear = extract_state_changes(message, extract_price_filter)
                if row['pending_slot'] in updates or row['pending_slot'] in clear:
                    message = row['pending_refinement'] + '; ' + message
            except (ValueError, TypeError):
                pass

        state_snapshot = {
            key: row[key]
            for key in (
                'shopping_state',
                'shopping_context',
                'pending_category',
                'last_result'
            )
            if key in row
        }
        from .category_clarification import pending_category_reply
        from .product_dialogue import discussion_reply
        from .product_dialogue import previous_reference_query
        discussion_previous = row.get('last_result')
        if re.search(r'\bmau (?:nay|do)\b', shared.normalized(message)) and row.get('selected_product_ids'):
            selected = [p for p in (discussion_previous or {}).get('products', [])
                        if p.get('ProductID') in row['selected_product_ids']]
            if len(selected) == 1:
                discussion_previous = {'products': selected}
        reference = previous_reference_query(message, discussion_previous)
        if isinstance(reference, dict):
            row['history'] = [*row['history'], {'user': message, 'answer': reference['answer']}][-6:]
            return {**reference, 'conversation_id': token}
        if reference:
            # Related-product retrieval uses the existing canonical-ID contract
            # and all current hard constraints, never ordinal numbers as IDs.
            message = reference
            if isinstance(previous_shopping_state, ShoppingState):
                message += ' ' + render_shopping_query(previous_shopping_state)
        response=pending_category_reply(message,row,tool)
        if response is None:
            response=(shared.followup_reply(message,row) if shared.followup_kind(message)=='correction'
                      else discussion_reply(message,discussion_previous))
        if response is None:
            if shared.followup_kind(message) == 'explanation':
                response = explain_previous_products(row)

            if response is None:
                response=shared.followup_reply(message,row)
        if response is None:
            refinement = None
            from jewelry_agents.shopping_advice import advisory_request
            advisory_turn = advisory_request(message)

            if not row.get('pending_category') and not advisory_turn:
                refinement = prepare_refinement(
                    message,
                    row.get('shopping_state'),
                    extract_price_filter,
                    (row.get('last_result') or {}).get('products', [])
                )

            missing = missing_refinement_field(message) if previous_shopping_state and refinement is None else None
            if missing:
                row['pending_slot'] = missing[0]
                row['pending_refinement'] = message
                response = _clarify(row, missing[0], missing[1])
                row['history'] = [*row['history'], {'user': message, 'answer': response['answer']}][-6:]
                return {**response, 'conversation_id': token}

            # Fail-safe: an unresolved follow-up must not
            # silently become an unrestricted product search.
            if (
                refinement is None
                and isinstance(previous_shopping_state, ShoppingState)
                and not row.get('pending_category')
                and classify_query(message) in {
                    'general_question', 'product_search'
                }
                and not shared.knowledge_request(message)
                and not advisory_turn
                and 'khong can tim san pham' not in shared.normalized(message)
                and not shared.followup_kind(message)
                and not reference_request(message).get('active')
                and not identity_request(message)
                and domain_answer(message, row['history']) is None
            ):
                answer = (
                    'Mình chưa chắc bạn muốn thay đổi điều kiện nào. '
                    'Mình vẫn giữ loại trang sức, ngân sách, '
                    'chất liệu và số lượng đã chọn trước đó. '
                    'Bạn muốn ưu tiên mẫu giá thấp hơn, '
                    'đổi ngân sách hay thay đổi nhu cầu khác?'
                )

                response = _clarify(row, 'refinement', answer)
                row['history'] = [
                    *row['history'],
                    {'user': message, 'answer': response['answer']}
                ][-6:]

                return {**response, 'conversation_id': token}

            if refinement is not None:
                effective = refinement[1]
                if row.get('shopping_context', '').startswith('Tư vấn '):
                    preferences = [e['alias'] for e in link_query(row['shopping_context'])['entities']
                                   if e['label'] in {'Audience', 'Style'} and e.get('alias')]
                    if preferences:
                        effective = 'Tư vấn ' + re.sub(r'^Top \d+\s*', '', effective) + ' ' + ' '.join(preferences)
            else:
                effective=followup_query(message,row.get('shopping_context'))
                if advisory_turn and isinstance(previous_shopping_state, ShoppingState):
                    from jewelry_agents.dialogue_state_extractor import apply_shopping_message
                    try:
                        advice_state = apply_shopping_message(previous_shopping_state, message, extract_price_filter)
                        effective = 'Tư vấn ' + re.sub(r'^Top \d+\s*', '', render_shopping_query(advice_state)) + ' ' + message
                    except (TypeError, ValueError):
                        pass
            if effective==message:
                effective=standalone_budget(message) or message
            # Canonicalize only supported product constraints; advice, product
            # identities and knowledge keep their established routing.
            if (refinement is None and not previous_shopping_state
                    and classify_query(effective) == 'product_search'
                    and not shared.knowledge_request(message)
                    and not reference_request(message).get('active')):
                from jewelry_agents.shopping_advice import advisory_request
                explicit_category = any(e['label'] == 'Category' and e.get('method') != 'ontology_constraint'
                                        for e in link_query(effective)['entities'])
                if (explicit_category and not advisory_request(effective)
                        and not row.get('shopping_context', '').startswith('Tư vấn ')
                        and not re.search(r'\b(?:sku|ma|sp\d+)\b|#\d+', shared.normalized(message))):
                    try:
                        initial = prepare_state(effective, extract_price_filter, top_k=top_k)
                        if initial is not None:
                            # Preserve descriptive terms used by lexical/dense ranking.
                            effective = render_shopping_query(initial) + ' ' + effective
                    except (ValueError, TypeError):
                        pass
            # Knowledge/writing requests never become product searches.
            knowledge=shared.knowledge_request(message)
            if ('khong can tim san pham' in shared.normalized(message) and
                    classify_query(message) not in {'restricted_request','unverified_policy','shipping_policy','customer_order_guidance'}):
                knowledge=True
            if row['history'] and shared.normalized(message).startswith((
                    'viet lai ', 'doi sang giong ', 'noi theo cach ', 'rut gon ', 'than mat hon')):
                knowledge=True
            natural=domain_answer(message,row['history']) if knowledge or classify_query(effective)=='general_question' else None
            plan=None
            if (not knowledge and natural is None and effective==message and
                    classify_query(effective) in {'general_question','product_search'} and
                    all(
                        entity.get('method') == 'ontology_constraint'
                        for entity in link_query(effective)['entities']
                    ) and 'sku' not in shared.normalized(message).split()):
                from jewelry_agents.semantic_planner import plan_query
                plan=plan_query(message)
            if plan is not None and plan.intent=='off_topic':
                response={'success':True,'intent':'out_of_scope','status':'out_of_scope','products':[],
                          'answer':'Mình tập trung hỗ trợ lựa chọn và tìm hiểu trang sức LUMIÈRE.'}
            elif plan is not None and plan.intent=='clarify':
                response={'success':True,'intent':'clarification','status':'clarification_required','products':[],
                          'answer':'Bạn muốn tư vấn cách chọn, tìm một món trang sức hay giải thích điều gì về trang sức?'}
            elif natural:
                response={'success':True,'intent':'general_question','status':'general_question','products':[],**natural}
            elif knowledge or (plan is not None and plan.intent=='knowledge'):
                response={'success':True,'intent':'general_question','status':'general_question','products':[]}
            else:
                response=tool(effective,semantic_plan=plan) if plan is not None and plan.intent in {'shop','consult'} else tool(effective)
            # The API callback may clear state before we know
            # whether a refinement has succeeded.
            if refinement is not None and (response.get('success') is False
                    or response.get('status') not in {'ok', 'degraded'}):
                for key in (
                    'shopping_state',
                    'shopping_context',
                    'pending_category',
                    'last_result'
                ):
                    if key in state_snapshot:
                        row[key] = state_snapshot[key]
                    else:
                        row.pop(key, None)

                answer = (
                    response.get('answer')
                    or 'Mình chưa tìm được kết quả phù hợp.'
                )

                answer += (
                    ' Mình vẫn giữ yêu cầu mua sắm trước đó; '
                    'điều chỉnh vừa rồi chưa được áp dụng.'
                )

                row['history'] = [
                    *row['history'],
                    {'user': message, 'answer': answer}
                ][-6:]

                return {
                    **response,
                    'answer': answer,
                    'products': [],
                    'response_mode': 'state_preserved',
                    'conversation_id': token
                }

            if (
                refinement is not None
                and response.get('success') is not False
                and response.get('status') in {'ok', 'degraded'}
            ):
                row['shopping_state'] = refinement[0]
                row['shopping_context'] = effective if effective.startswith('Tư vấn ') else refinement[1]
                row.pop('pending_slot', None)
                row.pop('pending_refinement', None)
                if cheaper_request(message) and not response.get('products') and response.get('status') == 'ok':
                    response['answer'] = 'Không có mẫu rẻ hơn phù hợp với các điều kiện hiện tại. Mình đã giữ giới hạn giá mới.'

            if response.get('intent') in {'unsupported','general_question','out_of_scope'}:
                from .natural_dialogue import answer_natural
                natural=domain_answer(message,row['history'])
                remaining=min(24,35-(time.monotonic()-started))
                generated=answer_natural(message,row['history'],evidence=natural['answer'] if natural else None,
                                         time_budget=remaining) if remaining>=2 else None
                if generated:
                    response={**response,'success':True,'answer':generated,'products':[],
                              'response_mode':'local_llm_dialogue'}
                    response.pop('sources',None)
                    response.pop('summary',None)
                elif natural:
                    response={**response,**natural,'success':True,'products':[]}
                else:
                    response={**response,'answer':(
                        'Mình chưa có thông tin đáng tin cậy để trả lời phần này. '
                        'Bạn muốn tìm hiểu cách chọn quà, phân biệt loại đá hay cách bảo quản trang sức?'),
                        'products':[],'response_mode':'clarification'}
                bridge=(response.get('intent')=='out_of_scope' or
                        response.get('intent')=='general_question' and natural is None and not link_query(message)['entities'])
                if bridge and not row.get('domain_bridge_offered'):
                    response['answer']+='\n\nNếu bạn đang chuẩn bị một dịp đặc biệt, mình có thể giúp chọn trang sức hoặc quà tặng. Bạn đang chọn cho dịp nào?'
                    row['domain_bridge_offered']=True
        if response.get('products') and response.get('intent') not in {
                'product_discussion', 'shopping_advice'}:
            if os.getenv(
                'LUMIERE_COMPACT_SHOPPING_RESPONSE_ENABLED', 'false'
            ).lower() == 'true':

                compact = compact_shopping_answer(
                    row.get('shopping_state'),
                    response,
                    previous_shopping_state
                )

                if compact:
                    response['answer'] = compact
                    response['response_mode'] = 'contextual_grounded_response'

        if (0<len(response.get('products',[]))<=3 and {'dense','graph'}.issubset(response.get('retrieval_sources_used',[]))
                and os.getenv('LUMIERE_GROUNDED_NARRATIVE_ENABLED','false').lower()=='true'):
            from .natural_dialogue import answer_natural
            facts=[]
            for p in response['products']:
                item={key:p[key] for key in ('Category','Material','Gemstone') if key in p}
                item['relationships']=[{'type':path['relationship'],'value':path.get('target_name')}
                                       for path in p.get('matched_relationships',[])[:1]]
                facts.append(item)
            remaining=min(24,35-(time.monotonic()-started))
            narrative_question=row.get('shopping_context',message) if response.get('clarification_resolution') else message
            state = row.get('shopping_state')
            evidence = {
                'verified_product_attributes': facts
            }

            if state is not None and hasattr(state, 'to_dict'):
                evidence['shopping_state'] = state.to_dict()

            paragraph=answer_natural(
                narrative_question,
                evidence=evidence,
                time_budget=remaining
            ) if remaining>=2 else None
            if paragraph:
                response['answer']=paragraph+'\n\n'+response.get('answer','')
                response['response_mode']='grounded_llm_rag'
        if response.get('products') and response.get('success') is not False and response.get('intent') not in {
                'unsupported','general_question','out_of_scope','product_discussion','conversation_explanation','conversation_correction'}:
            row['last_result']=response
            row['last_result_state'] = row.get('shopping_state')
            row.pop('selected_product_ids', None)
        if response.get('intent') == 'product_discussion' and len(response.get('referenced_product_ids', [])) == 1:
            row['selected_product_ids'] = response['referenced_product_ids']
        if response.get('status') in {'ok', 'degraded'} and response.get('success') is not False:
            row.pop('pending_clarification', None)
        if shared.knowledge_request(message) and re.match(
                r'^(?:viet|soan|tom tat|dien dat)\b', shared.normalized(message)):
            # Switching to a writing task ends advisory prose/pending goals.
            # Hard shopping slots remain available for an explicit later refinement.
            for key in ('shopping_context', 'pending_slot', 'pending_category', 'pending_refinement', 'pending_clarification'):
                row.pop(key, None)
        if (response.get('intent') == 'conversation_correction' or
                (not row.get('shopping_state') and response.get('intent') == 'general_question'
                 and not domain_answer(message, row['history'])
                 and not (shared.knowledge_request(message) and link_query(message)['entities']))):
            row.pop('shopping_context',None)
            row.pop('shopping_state',None)
            row.pop('pending_category',None)
        previous=row.get('last_result') or {}
        if (response.get('intent')=='conversation_explanation'
                and previous.get('recommendation_scope')=='advisory_unverified_preferences'
                and previous.get('products')):
            reasons=['• '+str(p.get('ProductName',''))+': '+str(p.get('reason',''))
                     for p in previous.get('products',[])]
            response['answer']=('Mình giữ nguyên các mẫu vừa gợi ý. Lý do có thể kiểm tra được là:\n'
                +'\n'.join(reasons)+'\n\nGu bạn nêu là định hướng tư vấn; '
                'mình chưa khẳng định từng mẫu có đầy đủ nhãn phong cách hay đối tượng sử dụng đã xác nhận.')
        row['history']=[*row['history'],{'user':message,'answer':response.get('answer','')}][-6:]
        return {**response,'conversation_id':token}
    finally:
        row['lock'].release()
