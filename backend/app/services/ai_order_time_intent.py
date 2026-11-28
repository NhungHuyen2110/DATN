"""Date-scoped order counts with complete status and temporal coverage."""
import re
from .ai_reporting_period import has_period, parse_reporting_period
from .ai_order_scope import has_order_request, parse_order_scope
from .ai_staff_intent import normalize_text


def understand_time_order_question(question: str):
    if not has_period(question):
        return None
    if not has_order_request(question):
        return {'intent': 'unsupported', 'message': 'Chưa hỗ trợ yêu cầu thống kê này.'}
    if re.search(r'\b(?:theo|moi|tung)\s+(?:ngay|thang)\b', normalize_text(question)):
        return {'intent': 'unsupported', 'message': 'Công cụ đếm đơn chưa hỗ trợ chia nhóm theo ngày hoặc tháng.'}
    period = parse_reporting_period(question, default_month=False)
    if period['intent'] != 'period':
        return period
    remaining = period.pop('_remaining')
    if re.search(r'\b(?:liet ke|danh sach|don nao|ma don)\b', normalize_text(remaining)):
        return {'intent': 'unsupported', 'message': 'Chỉ hỗ trợ đếm đơn trong khoảng thời gian.'}
    scope = parse_order_scope(remaining)
    if scope['intent'] != 'order_statistics':
        return scope
    if scope['status_kind'] == 'payment':
        return {'intent': 'unsupported', 'message': 'Công cụ theo thời gian hiện lọc trạng thái đơn, chưa lọc trạng thái thanh toán.'}
    return {'intent': 'orders_by_period', 'start_date': period['start_date'],
            'end_date': period['end_date'], 'status': scope['status']}
