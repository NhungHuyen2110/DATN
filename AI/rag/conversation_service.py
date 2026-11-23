"""Customer-only conversation coordinator; shared business conversation unchanged."""
from shared import conversation as shared
from jewelry_agents.shopping_advice import followup_query, standalone_budget
from jewelry_agents.intent_router import classify_query
from jewelry_agents.entity_linking import link_query
from .domain_dialogue import domain_answer
import os
import time


def converse(message, conversation_id, scope, tool):
    token,row=shared.STORE.resolve(conversation_id,scope)
    if not row['lock'].acquire(blocking=False):
        return {'success':False,'status':'conversation_busy','products':[],
                'answer':'Mình đang xử lý câu trước, bạn đợi câu trả lời rồi gửi tiếp nhé.',
                'conversation_id':token}
    try:
        started=time.monotonic()
        from .product_dialogue import discussion_reply
        response=(shared.followup_reply(message,row) if shared.followup_kind(message)=='correction'
                  else discussion_reply(message,row.get('last_result')))
        if response is None:
            response=shared.followup_reply(message,row)
        if response is None:
            effective=followup_query(message,row.get('shopping_context'))
            if effective==message:
                effective=standalone_budget(message) or message
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
                    not link_query(effective)['entities'] and 'sku' not in shared.normalized(message).split()):
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
            if (response.get('products') and {'dense','graph'}.issubset(response.get('retrieval_sources_used',[]))
                    and os.getenv('LUMIERE_GROUNDED_NARRATIVE_ENABLED','false').lower()=='true'):
                from .natural_dialogue import answer_natural
                facts=[{key:p[key] for key in ('Category','Material','Gemstone','matched_relationships') if key in p}
                       for p in response['products'][:3]]
                remaining=min(8,35-(time.monotonic()-started))
                paragraph=answer_natural(message,evidence={'verified_product_attributes':facts},time_budget=remaining) if remaining>=2 else None
                if paragraph:
                    response['answer']=paragraph+'\n\n'+response.get('answer','')
                    response['response_mode']='grounded_llm_rag'
            if response.get('success') is not False and response.get('intent') not in {
                    'unsupported','general_question','out_of_scope'}:
                row['last_result']=response
        if (response.get('intent') in {'conversation_correction','out_of_scope'} or
                (response.get('intent')=='general_question' and not domain_answer(message,row['history']))):
            row.pop('shopping_context',None)
        row['history']=[*row['history'],{'user':message,'answer':response.get('answer','')}][-6:]
        return {**response,'conversation_id':token}
    finally:
        row['lock'].release()
