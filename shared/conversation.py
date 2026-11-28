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


def normalize_utterance(message):
    """Fold accents, preserve dates/operators, repair only unique transpositions.

    No fuzzy entity matching. Repairs require adjacent domain evidence; numbers
    and operators stay untouched. This is lexical, not example-question lookup.
    """
    value = unicodedata.normalize('NFD', message.casefold()).replace('đ', 'd')
    value = ''.join(c for c in value if unicodedata.category(c) != 'Mn')
    vocabulary = {'doanh', 'thong', 'khong', 'hang', 'thang', 'nguong'}
    evidence = {
        'doanh': (r'$', r'^\s+thu\b'), 'thong': (r'$', r'^\s+ke\b'),
        'thang': (r'$', r'^\s+(?:\d|nay\b|truoc\b)'),
        'nguong': (r'$', r'^\s+\d'),
        'hang': (r'\b(?:don|mua|het|con)\s+$', r'(?!)'),
        'khong': (r'\bco\b.*\s+$', r'^\s*[?!.]*$'),
    }
    def repair(match):
        token = match[0]
        if token == 'ko':
            return 'khong'
        if token in vocabulary or len(token) < 4:
            return token
        candidates = {token[:i] + token[i+1] + token[i] + token[i+2:]
                      for i in range(len(token)-1)} & vocabulary
        if len(candidates) != 1:
            return token
        candidate = next(iter(candidates))
        before, after = value[:match.start()], value[match.end():]
        left, right = evidence[candidate]
        if candidate == 'khong':
            grounded = re.search(left, before) and re.search(right, after)
        elif candidate == 'hang':
            grounded = re.search(left, before)
        else:
            grounded = re.search(right, after)
        return candidate if grounded else token
    return re.sub(r'\b[a-z]+\b', repair, value).strip()


def task_body(message):
    """Remove greeting/politeness framing, retaining all task constraints."""
    text = normalize_utterance(message)
    text = re.sub(r'^\s*(?:(?:xin\s+)?chao|hello|hi)\b(?:\s+(?:ban(?!\s+(?:chay|nhieu|hang)\b)|shop|lumiere))?[\s!,.:;]*', '', text)
    modal = re.match(r'^(?:(?:ban|shop)\s+)?co the\s+(?=(?:cho|thong ke|liet ke|dem|bao cao|phan tich|tim|tra cuu)\b)', text)
    if modal:
        text = re.sub(r'\s+khong\s*[?!.]*$', '', text[modal.end():])
    text = re.sub(r'\b(?:xin vui long|vui long|cho (?:toi|minh) (?:hoi|biet|xem)|'
                  r'(?:giup|ho) (?:toi|minh)|lam on)\b', ' ', text)
    text = re.sub(r'\b(?:nhe|nha|a|voi|nhi)\s*[?!.]*$', '', text)
    return ' '.join(text.strip(' ,;!?').split())


def scope_remainder(message, patterns):
    """Unexplained content after semantic spans and conversational framing.

    Negations, quantities and unknown modifiers are evidence, never stopwords.
    """
    text = task_body(message)
    # A terminal question operator is different from predicate negation.
    if re.match(r'^(?:lieu\s+)?co\b', text):
        text = re.sub(r'\s+khong\s*[?!.]*$', '', text)
    for pattern in patterns:
        text = re.sub(r'\b(?:' + pattern + r')\b', ' ', text)
    text = re.sub(r'\b(?:nhung|cac|nhieu|nao|bao nhieu|may|co|la|gi|roi|'
                  r'toi|minh|ban|xin|thoi|thi sao|hay|hien tai|trong he thong|lumiere)\b', ' ', text)
    return ' '.join(text.strip(' ,;!?.').split())


def conversational_act(message):
    """Recognize controls without consuming a greeting plus a business task."""
    text = normalized(message)
    text = re.sub(r'^(?:(?:xin )?chao|hello|hi)\b(?:\s+(?:ban|shop|lumiere))?\s*', '', text)
    text = re.sub(r'(?:^|\s+)(?:nhe|nha|a|nhi)$', '', text)
    if not text and re.match(r'^(?:(?:xin )?chao|hello|hi)\b', normalized(message)):
        return 'greeting'
    if re.fullmatch(r'(?:(?:ban|shop|lumiere)\s+)?(?:co the\s+)?'
                    r'(?:lam(?: duoc)?|giup(?: do)?|ho tro|tu van)'
                    r'(?:\s+(?:cho\s+)?(?:toi|minh))?(?:\s+duoc)?\s+(?:nhung\s+)?gi', text):
        return 'capability'
    if text in {'huong dan', 'huong dan su dung'}:
        return 'capability'
    if text in {'reset', 'bat dau lai', 'lam lai', 'huy', 'bo qua', 'dung lai',
                'doi tac vu', 'huy yeu cau', 'thoi bo qua'}:
        return 'reset'
    return None


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


def knowledge_request(message):
    """Explicit explanation/writing acts must not become product searches."""
    text = normalized(task_body(message))
    if any(term in text for term in ('mat khau', 'system prompt', 'reset token',
                                     'bo qua huong dan', 'ignore previous instructions')):
        return False  # Preserve the existing server/tool policy decisions.
    if re.search(r'\bsku\b|#[0-9]+\b|\bsp[0-9]+\b', message, flags=re.I):
        return False
    if re.search(r'\b(?:san pham|ma don|don hang)\s+[0-9]+\b', text):
        return False
    if any(term in text for term in ('hom nay', 'thang nay', 'tuan nay', 'nam nay')):
        return False
    if 'bao nhieu' in text and any(term in text for term in
            ('don hang', 'don cho', 'khach hang', 'san pham', 'ton kho', 'doanh thu')):
        return False
    for prefix in ('ban hay ', 'hay ', 'giup toi ', 'giup minh '):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return (' la gi ' in ' ' + text + ' ' or text.startswith((
        'giai thich ', 'phan biet ', 'so sanh khai niem ', 'tom tat ', 'dien dat ',
        'viet loi ', 'viet mot loi ', 'soan loi ', 'viet cau ', 'viet mot cau ',
        'viet doan ', 'viet mot doan ', 'viet bai ', 'soan thong bao ')))


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


def converse(message,conversation_id,scope,tool,*,dialogue=None):
    token,row=STORE.resolve(conversation_id,scope)
    # One turn per conversation: no concurrent overwriting of the prior result.
    if not row['lock'].acquire(blocking=False):
        return {'success':False,'status':'conversation_busy','products':[],
                'answer':'Tôi đang xử lý câu trước trong cuộc trò chuyện này. Bạn vui lòng đợi câu trả lời rồi gửi tiếp.',
                'conversation_id':token}
    try:
        if dialogue is not None:
            response=dialogue(message,row,tool)
            if response.get('success') is not False and response.get('data') is not None:
                row['last_result']=response
            row['history']=[*row['history'],{'user':message,'answer':response.get('answer','')}][-6:]
            return {**response,'conversation_id':token}
        response=followup_reply(message,row)
        if response is None:
            if knowledge_request(message):
                response={'success':True,'status':'general_question','intent':'general_question','products':[],
                    'answer':'Tôi hiểu bạn đang muốn giải thích hoặc trao đổi, không phải tìm sản phẩm. '
                             'Lớp hội thoại tự nhiên hiện chưa sẵn sàng; tôi chưa thể trả lời đầy đủ câu này.'}
            else:
                response=tool(message)
            if response.get('intent') in {'unsupported','general_question','out_of_scope'}:
                from .local_dialogue import answer_general
                natural=answer_general(message,row['history'],str(scope[0]))
                if natural:
                    response={**response,'success':True,'answer':natural,'products':[],
                              'response_mode':'local_llm_dialogue'}
            if response.get('success') is not False and response.get('intent') not in {
                    'unsupported','general_question','out_of_scope'}:
                row['last_result']=response
        row['history']=[*row['history'],{'user':message,'answer':response.get('answer','')}][-6:]
        return {**response,'conversation_id':token}
    finally:
        row['lock'].release()
