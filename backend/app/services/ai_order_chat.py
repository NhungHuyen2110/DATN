"""Shared read-only order dispatcher; callers retain authentication and tools."""
import re
from .ai_staff_intent import understand_staff_question, normalize_text
from .ai_order_scope import has_order_request, statistic_value, ORDER_LABELS
from .ai_order_time_intent import understand_time_order_question


def answer_order_question(message, db, *, statistics, period, classifier=None):
    text = normalize_text(message)
    if re.search(r'\b(?:liet ke|danh sach|ma don|don nao)\b', text):
        return {'intent': 'unsupported', 'data': None,
                'answer': 'Công cụ này chỉ đếm đơn; chưa hỗ trợ liệt kê hoặc tra đơn cụ thể.'}
    intent = understand_time_order_question(message)
    if intent is not None:
        if intent['intent'] != 'orders_by_period':
            return {'intent': intent['intent'], 'data': None, 'answer': intent['message']}
        result = period(db=db, start_date=intent['start_date'], end_date=intent['end_date'], status=intent['status'])
        label = ORDER_LABELS.get(result['status'], 'tổng cộng')
        return {'intent': 'orders_by_period', 'data': result,
                'answer': f"Từ {intent['start_date']:%d/%m/%Y} đến {intent['end_date']:%d/%m/%Y}, "
                          f"hệ thống có {result['total_orders']} đơn hàng {label} (tính theo ngày tạo đơn)."}
    intent = understand_staff_question(message)
    # The model cannot discard explicit order modifiers or override known slots.
    if not has_order_request(message) and classifier is not None:
        intent = classifier(message)
    if intent.get('intent') != 'order_statistics':
        return {'intent': intent.get('intent', 'unsupported'), 'data': None,
                'answer': intent.get('message', 'Chưa xác định đủ phạm vi thống kê đơn hàng.')}
    field = intent.get('field')
    allowed = {'total_orders', 'pending_orders', 'confirmed_orders', 'packing_orders',
               'shipping_orders', 'delivered_orders', 'cancelled_orders',
               'paid_orders', 'unpaid_orders', 'refunded_orders'}
    if field not in allowed:
        return {'intent': 'unsupported', 'data': None, 'answer': 'Trạng thái đơn chưa được hỗ trợ.'}
    result = statistics(db)
    label, value = statistic_value(result, field)
    return {'intent': 'order_statistics', 'field': field,
            'answer': f'{label}: {value} đơn.',
            'data': {'value': value, 'scope': result['scope']}}
