"""Bounded server-owned conversation state; role/account isolation, no DB writes."""
from collections import OrderedDict
import secrets
import threading
import time
import re
import unicodedata


def normalized(text):
    value=unicodedata.normalize('NFD',text.casefold()).replace('đ','d')
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',''.join(c for c in value if unicodedata.category(c)!='Mn')).split())


class ConversationStore:
    def __init__(self,limit=256,ttl=1800,clock=time.monotonic):
        self.limit,self.ttl,self.clock=limit,ttl,clock
        self.rows=OrderedDict()
        self.lock=threading.RLock()

    def resolve(self,token,scope):
        with self.lock:
            now=self.clock()
            for key in list(self.rows):
                if self.rows[key]['expires']<=now:
                    del self.rows[key]
            row=self.rows.get(token)
            if row is None or row['scope']!=scope:
                token=secrets.token_urlsafe(24)
                row={'scope':scope,'expires':now+self.ttl,'last_result':None,'history':[],
                     'lock':threading.Lock()}
                self.rows[token]=row
            row['expires']=now+self.ttl
            self.rows.move_to_end(token)
            while len(self.rows)>self.limit:
                self.rows.popitem(last=False)
            return token,row


STORE=ConversationStore()


def followup_kind(message):
    text=normalized(message)
    if any(p in text for p in ('co hoi san pham dau','khong hoi san pham','dung goi y',
                               'dung tim san pham','toi khong can goi y','khong can goi y')):
        return 'correction'
    asks_why=any(p in text for p in ('tai sao','vi sao','ly do','dua vao dau','can cu nao'))
    refers_back=any(p in text for p in ('goi y','san pham do','san pham nay','ket qua','so lieu',
                                        'so don','vua roi','nhu vay','nhu the','lua chon'))
    if asks_why and (refers_back or text in {'tai sao','vi sao','ly do la gi'}):
        return 'explanation'
    return None


def followup_reply(message,row):
    kind=followup_kind(message)
    if kind=='correction':
        return {'success':True,'status':'conversation_correction','intent':'conversation_correction',
                'answer':'Bạn đúng, tôi đã hiểu nhầm ý và tự chuyển sang tìm sản phẩm. '
                         'Tôi sẽ trả lời câu hỏi của bạn, không tự thêm danh sách gợi ý. '
                         'Bạn muốn tôi giải thích lựa chọn vừa rồi hay trao đổi thêm về cách chọn quà?',
                'products':[]}
    if kind=='explanation':
        previous=row.get('last_result') or {}
        products=previous.get('products',[])
        if products:
            names='; '.join(str(p.get('ProductName',p.get('name',''))) for p in products)
            answer=('Bạn đang hỏi về các lựa chọn vừa rồi: '+names+'. '
                    'Chúng được xếp hạng theo độ liên quan với yêu cầu trước của bạn và dữ liệu sản phẩm; '
                    'giá, tồn kho đã được đối chiếu tại thời điểm trả lời. '
                    'Tuy nhiên, việc còn hàng và phù hợp truy vấn chưa chứng minh đây là món quà hợp sở thích người nhận. '
                    'Tôi chưa biết ngân sách, kích cỡ hoặc sở thích của họ, nên đây mới là các lựa chọn tham khảo. '
                    'Tôi giữ nguyên danh sách vừa rồi, không tìm bộ sản phẩm khác để trả lời câu hỏi này.')
        elif previous.get('answer'):
            definitions={
                'order_statistics':'Kết quả là số đơn ở trạng thái được hỏi trong phạm vi thời gian đã trả lời; mỗi đơn được tính một lần.',
                'inventory_statistics':'Kết quả phân loại theo tồn kho hiện tại: hết hàng khi bằng 0; sắp hết hàng khi lớn hơn 0 và không vượt ngưỡng của báo cáo.',
                'revenue_statistics':'Kết quả dùng phạm vi ngày và tiêu chí thanh toán được xác nhận của báo cáo; không phải tổng tiền của mọi đơn được tạo.',
                'top_selling_products':'Danh sách được tính từ lượng sản phẩm bán trong kỳ theo điều kiện đơn hợp lệ của báo cáo, không phải thứ hạng gợi ý mua hàng.',
            }
            answer=('Bạn đang hỏi về kết quả vừa rồi: '+str(previous['answer'])+'\n\n'+
                    definitions.get(previous.get('intent'),'Tôi có thể giải thích thêm điều kiện hoặc phạm vi của kết quả này.'))
        else:
            answer=('Bạn muốn tôi giải thích kết quả hoặc nhận định nào trong câu trả lời vừa rồi? '
                    'Tôi sẽ giải thích phần đó thay vì tự tìm sản phẩm mới.')
        return {'success':True,'status':'conversation_explanation','intent':'conversation_explanation',
                'answer':answer,'products':[],
                'referenced_product_ids':[p.get('ProductID',p.get('id')) for p in products]}
    return None


def converse(message,conversation_id,scope,tool):
    token,row=STORE.resolve(conversation_id,scope)
    # One turn per conversation: no concurrent overwriting of the prior result.
    if not row['lock'].acquire(blocking=False):
        return {'success':False,'status':'conversation_busy','products':[],
                'answer':'Tôi đang xử lý câu trước trong cuộc trò chuyện này. Bạn vui lòng đợi câu trả lời rồi gửi tiếp.',
                'conversation_id':token}
    try:
        response=followup_reply(message,row)
        if response is None:
            response=tool(message)
            if response.get('intent') in {'unsupported','general_question','out_of_scope'}:
                from .local_dialogue import answer_general
                natural=answer_general(message,row['history'],str(scope[0]))
                if natural:
                    response={**response,'answer':natural,'products':[],
                              'response_mode':'local_llm_dialogue'}
            if response.get('success') is not False and response.get('intent') not in {
                    'unsupported','general_question','out_of_scope'}:
                row['last_result']=response
        row['history']=[*row['history'],{'user':message,'answer':response.get('answer','')}][-6:]
        return {**response,'conversation_id':token}
    finally:
        row['lock'].release()
