"""Customer-only conversation coordinator; shared business conversation unchanged."""
from shared import conversation as shared
from jewelry_agents.shopping_advice import followup_query, standalone_budget
from jewelry_agents.intent_router import classify_query
from .domain_dialogue import domain_answer


def converse(message, conversation_id, scope, tool):
    token,row=shared.STORE.resolve(conversation_id,scope)
    if not row['lock'].acquire(blocking=False):
        return {'success':False,'status':'conversation_busy','products':[],
                'answer':'Mình đang xử lý câu trước, bạn đợi câu trả lời rồi gửi tiếp nhé.',
                'conversation_id':token}
    try:
        response=shared.followup_reply(message,row)
        if response is None:
            effective=followup_query(message,row.get('shopping_context'))
            if effective==message:
                effective=standalone_budget(message) or message
            # Knowledge/writing requests never become product searches.
            knowledge=shared.knowledge_request(message)
            natural=domain_answer(message,row['history']) if knowledge or classify_query(effective)=='general_question' else None
            if natural:
                response={'success':True,'intent':'general_question','status':'general_question','products':[],**natural}
            elif knowledge:
                response={'success':True,'intent':'general_question','status':'general_question','products':[]}
            else:
                response=tool(effective)
            if (response.get('intent') in {'unsupported','general_question','out_of_scope'}
                    and response.get('response_mode')!='reviewed_domain_answer'):
                natural=domain_answer(message,row['history'])
                if natural:
                    response={**response,**natural,'success':True,'products':[]}
                else:
                    from shared.local_dialogue import answer_general
                    generated=answer_general(message,row['history'],str(scope[0]))
                    response={**response,'answer':generated or (
                        'Mình chưa có thông tin đáng tin cậy để trả lời phần này. '
                        'Bạn muốn tìm hiểu cách chọn quà, phân biệt loại đá hay cách bảo quản trang sức?'),
                        'products':[],'response_mode':'local_llm_dialogue' if generated else 'clarification'}
            if response.get('success') is not False and response.get('intent') not in {
                    'unsupported','general_question','out_of_scope'}:
                row['last_result']=response
        if response.get('intent') in {'conversation_correction','general_question','out_of_scope'}:
            row.pop('shopping_context',None)
        row['history']=[*row['history'],{'user':message,'answer':response.get('answer','')}][-6:]
        return {**response,'conversation_id':token}
    finally:
        row['lock'].release()
