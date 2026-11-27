"""Opt-in semantic turn coordinator: one owner for plan/state/result snapshots."""
import os
from jewelry_agents.dialogue_plan import DialoguePlan
from jewelry_agents.semantic_planner import plan_dialogue
from jewelry_agents.dialogue_plan_validator import validate_dialogue_plan, InvalidDialoguePlan
from jewelry_agents.dialogue_fast_path import fast_plan
from jewelry_agents.dialogue_state_query import render_shopping_query
from jewelry_agents.intent_router import classify_query
from jewelry_agents.retrieval import extract_price_filter
from .contextual_response import compact_shopping_answer, explain_previous_products
from .domain_dialogue import domain_answer
from .product_dialogue import discussion_reply


QUESTIONS={'category':'Bạn muốn chọn loại trang sức nào?',
           'material':'Bạn muốn đổi sang chất liệu nào?',
           'gemstone':'Bạn muốn chọn loại đá nào?',
           'min_price':'Bạn muốn đặt mức giá tối thiểu bao nhiêu?',
           'max_price':'Bạn muốn đặt mức giá tối đa bao nhiêu?',
           'top_k':'Bạn muốn xem bao nhiêu mẫu, từ 1 đến 10?',
           'references':'Bạn muốn nói đến những mẫu số mấy trong danh sách trước?'}


def _finish(row,message,response):
    row['history']=[*row.get('history',[]),{'user':message,'answer':response.get('answer','')}][-6:]
    return response


def semantic_turn(message,row,tool,*,top_k=3,planner=None):
    """Called only while the conversation lock is held; never writes databases."""
    from shared.conversation import knowledge_request
    before=row.get('shopping_state')
    pending=row.get('semantic_pending')
    previous=(row.get('last_result') or {}).get('products',[])
    guard=classify_query(message)
    if guard in {'restricted_request','shipping_policy','unverified_policy','customer_order_guidance','greeting'}:
        return _finish(row,message,tool(message))
    plan=fast_plan(message,before,extract_price_filter,pending)
    method='complete_lexical_coverage'
    if plan is None:
        method='validated_semantic_plan'
        plan=(planner or plan_dialogue)(message,before,history=row.get('history',()),
                    products=previous,pending=pending)
    if plan is None:
        row['semantic_last_turn']={'method':method,'status':'planner_unavailable','query':None}
        return _finish(row,message,{'success':False,'status':'nlu_unavailable','intent':'clarification',
              'products':[],'answer':'Mình chưa phân tích chắc yêu cầu lúc này. Mình giữ nguyên các điều kiện đã chọn; bạn có thể thử lại.'})
    # Deterministic access/explicit knowledge guards cannot be overridden by LLM.
    if knowledge_request(message) and plan.intent in {'new_search','refine_search','consultation'}:
        plan=DialoguePlan(intent='knowledge',operations=[])
    if pending and plan.intent in {'refine_search','new_search'} and not any(
            op.field=='task' and op.op=='RESET' for op in plan.operations):
        # Retain all already verified operations from an unfinished request, with
        # their original quote. Current operations replace matching fields.
        replacement={op.field for op in plan.operations}
        deferred=[op for op in DialoguePlan.model_validate(pending['plan']).operations if op.field not in replacement
                  and op.field!='pending_slot' and op.op!='UNKNOWN']
        plan=plan.model_copy(update={'operations':deferred+plan.operations})
    try:
        from jewelry_agents import retrieval
        validated=validate_dialogue_plan(plan,message,before,products=previous,pending=pending,
                                         encoder=retrieval.embedding_model,top_k=top_k)
    except (ValueError,TypeError) as error:
        row['semantic_last_turn']={'method':method,'status':'plan_rejected','reason':str(error),'query':None}
        return _finish(row,message,{'success':True,'status':'clarification_required','intent':'clarification',
                 'products':[],'answer':'Mình chưa xác minh đủ các điều kiện trong câu này. Mình giữ nguyên yêu cầu trước; bạn nói rõ điều kiện muốn đổi giúp mình nhé.'})
    row['semantic_last_turn']={'method':method,'status':'validated','intent':validated.intent,
                              'operations':[op.model_dump() for op in validated.operations],
                              'query':validated.query}
    intent=validated.intent
    if intent=='clarification' or validated.pending_slot:
        field=validated.pending_slot or 'category'
        row['semantic_pending']={'field':field,'message':message,'plan':plan.model_dump()}
        return _finish(row,message,{'success':True,'status':'clarification_required','intent':'clarification',
               'products':[],'answer':QUESTIONS.get(field,'Bạn muốn thay đổi cụ thể điều kiện nào?')})
    if intent in {'restricted','out_of_scope'}:
        return _finish(row,message,{'success':True,'status':'restricted_request' if intent=='restricted' else 'out_of_scope',
              'intent':'restricted_request' if intent=='restricted' else 'out_of_scope','products':[],
              'answer':'Kênh này chỉ hỗ trợ kiến thức và lựa chọn trang sức công khai; dữ liệu nội bộ yêu cầu đúng quyền truy cập.'})
    if intent=='correction':
        row.pop('semantic_pending',None)
        return _finish(row,message,{'success':True,'intent':'conversation_correction','status':'conversation_correction',
                                   'products':[],'answer':'Mình đã dừng tìm sản phẩm và giữ lại các điều kiện để bạn có thể tiếp tục khi cần.'})
    if intent=='knowledge':
        natural=domain_answer(message,row.get('history',()))
        return _finish(row,message,{'success':True,'status':'general_question','intent':'general_question','products':[],
                   **(natural or {'answer':'Mình hiểu bạn đang hỏi kiến thức về trang sức. Mình chưa có tài liệu đã xác minh cho nội dung này nên không muốn đoán.'})})
    if intent=='explanation':
        response=explain_previous_products(row) or {'success':True,'status':'clarification_required',
                 'intent':'clarification','products':[],'answer':QUESTIONS['references']}
        return _finish(row,message,response)
    if intent in {'comparison','product_information'}:
        refs=validated.references
        if not refs and len(previous)==1:
            refs=(1,)
        if not refs:
            return _finish(row,message,{'success':True,'status':'clarification_required','intent':'clarification',
                      'products':[],'answer':QUESTIONS['references']})
        canonical=('So sánh ' if intent=='comparison' else '')+' và '.join('mẫu số '+str(i) for i in refs)
        if intent=='product_information':canonical+=' có chất liệu gì, giá bao nhiêu và còn hàng không?'
        response=discussion_reply(canonical,row.get('last_result'))
        return _finish(row,message,response or {'success':True,'status':'clarification_required',
                     'intent':'clarification','products':[],'answer':QUESTIONS['references']})
    if intent not in {'new_search','refine_search','consultation'}:
        raise InvalidDialoguePlan('Unhandled validated intent')
    if validated.state.category is None:
        row['semantic_pending']={'field':'category','message':message,'plan':plan.model_dump()}
        return _finish(row,message,{'success':True,'status':'clarification_required','intent':'clarification',
                                   'products':[],'answer':QUESTIONS['category']})
    # Accepted language state is distinct from retrieval availability. An outage
    # cannot erase the new requirement or replace the last verified result.
    row['shopping_state']=validated.state
    row['shopping_context']=validated.query
    row.pop('semantic_pending',None)
    result=tool(validated.query)
    if result.get('products') and result.get('success') is not False:
        compact=compact_shopping_answer(validated.state,result,before)
        if compact:result={**result,'answer':compact,'response_mode':'contextual_grounded_response'}
        row['last_result']=result
        row['last_result_state']=validated.state
    elif result.get('success') is False:
        result={**result,'answer':result.get('answer','Chưa truy xuất được dữ liệu.')+' Mình đã giữ các điều kiện bạn vừa yêu cầu.'}
    return _finish(row,message,result)
