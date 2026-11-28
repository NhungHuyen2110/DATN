"""Revenue intent delegates temporal grammar and rejects unparsed constraints."""
import re
from .ai_staff_intent import normalize_text
from .ai_reporting_period import parse_reporting_period, reporting_scope_supported


def understand_revenue_question(question: str):
    text = normalize_text(question)
    if not re.search(r'\b(?:doanh thu|tong tien ban hang|tien ban hang)\b', text):
        return {'intent': 'unsupported'}
    if re.search(r'\b(?:ban chay|san pham nao|mat hang nao|ton kho|don cho)\b', text):
        return {'intent': 'unsupported', 'message': 'Vui lòng hỏi riêng hoặc dùng các nghiệp vụ kết hợp được hỗ trợ.'}
    result = parse_reporting_period(question)
    if result['intent'] != 'period':
        return result
    if not reporting_scope_supported(result.pop('_remaining')):
        return {'intent': 'unsupported', 'message': 'Báo cáo doanh thu chưa hỗ trợ bộ lọc hoặc phép phân tích trong câu hỏi. Vui lòng nêu rõ một kỳ báo cáo.'}
    return {**result, 'intent': 'revenue_statistics'}
