"""Shared finite order/payment scopes. Unknown filters never mean total."""
import re
from .ai_multi_intent import normalize_question
from shared.conversation import task_body, scope_remainder

ORDER_LABELS = {
    'pending': 'đang chờ xử lý', 'confirmed': 'đã xác nhận',
    'packing': 'đang đóng gói', 'shipping': 'đang giao',
    'delivered': 'đã giao', 'cancelled': 'đã hủy',
}
PAYMENT_LABELS = {'unpaid': 'chưa thanh toán', 'paid': 'có trạng thái đã thanh toán',
                  'refunded': 'có trạng thái hoàn tiền'}
STATE_PHRASES = {
    ('order', 'pending'): ('dang cho xu ly', 'cho xu ly', 'chua xu ly', 'dang cho', 'pending'),
    ('order', 'confirmed'): ('da xac nhan', 'xac nhan', 'confirmed'),
    ('order', 'packing'): ('dang dong goi', 'dong goi', 'dang chuan bi hang', 'chuan bi hang', 'packing'),
    ('order', 'shipping'): ('dang giao hang', 'dang giao', 'dang duoc van chuyen', 'dang van chuyen', 'shipping'),
    ('order', 'delivered'): ('da giao hang thanh cong', 'da giao thanh cong', 'giao thanh cong', 'da giao hang', 'da giao', 'delivered'),
    ('order', 'cancelled'): ('da bi huy', 'da huy', 'bi huy', 'huy', 'cancelled', 'canceled'),
    ('payment', 'unpaid'): ('chua thanh toan', 'chua tra tien', 'unpaid'),
    ('payment', 'paid'): ('da thanh toan', 'da tra tien', 'paid'),
    ('payment', 'refunded'): ('da hoan tien', 'hoan tien', 'refunded'),
}


def has_order_request(message):
    return bool(re.search(r'\bdon\b', normalize_question(message)))


def order_clause(message):
    """An explicit order clause in a multi-tool request."""
    parts = re.split(r'\s+va\s+|[,;]', normalize_question(message))
    selected, active = [], False
    for part in parts:
        if has_order_request(part):
            active = True
        elif re.search(r'\b(?:ton kho|san pham|doanh thu|ban chay)\b', part):
            active = False
        if active:
            selected.append(part)
    return ' '.join(selected)


def parse_order_scope(message):
    text = normalize_question(task_body(message))
    if re.match(r'^(?:lieu\s+)?co\b', text):
        text = re.sub(r'\s+khong$', '', text)
    choices = set()
    phrases = sorted([(phrase, scope) for scope, values in STATE_PHRASES.items()
                      for phrase in values], key=lambda p: -len(p[0]))
    for phrase, scope in phrases:
        pattern = r'\b' + re.escape(phrase) + r'\b'
        if re.search(pattern, text):
            choices.add(scope)
            text = re.sub(pattern, ' ', text)
    residual = scope_remainder(text, [r'tong so luong|so luong|tong so|tat ca|toan bo lich su',
                                     r'don(?: hang)?|thong ke|dem|tong|so|hien con|duoc'])
    if len(choices) > 1 or residual:
        return {'intent': 'unsupported', 'message':
                'Chưa xác định đầy đủ trạng thái hoặc bộ lọc đơn hàng. '
                'Vui lòng hỏi một trạng thái đơn hoặc một trạng thái thanh toán, '
                'không ghép thêm điều kiện chưa được hỗ trợ.'}
    kind, status = next(iter(choices)) if choices else ('order', None)
    return {'intent': 'order_statistics', 'field': status + '_orders' if status else 'total_orders',
            'status_kind': kind, 'status': status}


def statistic_value(result, field):
    if field == 'total_orders':
        return 'Tổng số đơn hàng trong hệ thống', result['total_orders']
    status = field.removesuffix('_orders')
    if status in ORDER_LABELS:
        value = result.get('order_status', {}).get(status, result.get(field, 0))
        return 'Số đơn hàng ' + ORDER_LABELS[status], value
    if status in PAYMENT_LABELS:
        return 'Số đơn hàng ' + PAYMENT_LABELS[status], result['payment_status'].get(status, 0)
    raise ValueError('Unsupported order field')
