"""Server-owned business dialogue. Plans are validated atomically before read tools.

No model calls, SQL generation, authentication changes or business definitions here.
ConversationStore owns locking, TTL and role/account isolation.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, timedelta
from calendar import monthrange
from decimal import Decimal, InvalidOperation, localcontext
from enum import Enum
import re
from typing import Literal

from shared.conversation import followup_reply, task_body, scope_remainder, conversational_act
from .ai_multi_intent import detect_requested_tools, normalize_question, PURCHASE_REQUEST
from .ai_order_scope import parse_order_scope
from .ai_reporting_period import parse_reporting_period, reporting_scope_supported
from .ai_inventory_chat import inventory_scope
from .ai_product_lookup import extract_product_query


class Operation(str, Enum):
    SET = 'SET'
    KEEP = 'KEEP'
    CLEAR = 'CLEAR'
    RESET = 'RESET'
    UNKNOWN = 'UNKNOWN'


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    group: str


@dataclass
class BusinessState:
    intent: str | None = None
    metrics: tuple[str, ...] = ()
    period: Period | None = None
    status: Literal['pending', 'confirmed', 'packing', 'shipping', 'delivered', 'cancelled'] | None = None
    payment: Literal['paid', 'unpaid', 'refunded'] | None = None
    product: str | None = None
    threshold: int = 5
    inventory_mode: str | None = None
    limit: int = 20
    top_limit: int = 5
    pending_clarification: str | None = None
    operations: dict[str, Operation] = field(default_factory=dict)
    comparison: Period | None = None
    transition: str = 'UNKNOWN'
    metric_periods: dict[str, Period] = field(default_factory=dict)


class Clarify(ValueError):
    pass


def reply(intent, answer, **kwargs):
    return {'intent': intent, 'answer': answer, 'data': None, **kwargs}


def capabilities(role):
    text = 'Tôi có thể tra sản phẩm theo tên, SKU, thuộc tính; báo cáo tồn kho và đếm đơn theo phạm vi API hỗ trợ.'
    if role == 'admin':
        text += ' Bạn có thể hỏi thêm doanh thu, bán chạy, so sánh kỳ và chỉ số mua hàng.'
    return text + ' Tôi chỉ đọc dữ liệu.'


def validated_plan(previous, candidate, commands):
    """Make implicit task-scope clears visible in the typed transition metadata."""
    candidate.pending_clarification = None
    for slot in ('intent', 'metrics', 'period', 'status', 'payment', 'product', 'threshold',
                 'inventory_mode', 'limit', 'top_limit', 'comparison', 'pending_clarification', 'metric_periods'):
        old, new = getattr(previous, slot), getattr(candidate, slot)
        if old != new:
            candidate.operations[slot] = Operation.CLEAR if new is None else Operation.SET
        else:
            candidate.operations.setdefault(slot, Operation.KEEP)
    return candidate, commands


def parse_plan(message, previous, role):
    """Compile complete constraints, retaining only compatible prior slots."""
    message = task_body(message)
    text = normalize_question(message)
    if role not in {'staff', 'admin'}:
        raise Clarify('Vai trò không được hỗ trợ.')
    if re.search(r'\b(?:xoa|cap nhat|chinh sua|sua|tao(?: moi)?|huy)\s+(?:don(?: hang)?|ton kho|stock|san pham|gia)\b', text):
        raise Clarify('Tôi chỉ đọc dữ liệu; không thể thực hiện thay đổi nghiệp vụ qua chat.')
    if role == 'staff' and re.search(r'\b(?:doanh thu|ban chay|hanh vi|khach hang|loi nhuan|du bao)\b', text):
        raise Clarify('Phạm vi Staff không hỗ trợ báo cáo này.')
    from .ai_staff_intent import normalize_text
    comparison_text = normalize_text(message)
    if re.search(r'\b(?:so voi|so sanh)\b', comparison_text):
        if role != 'admin':
            raise Clarify('So sánh kỳ hiện chỉ được hỗ trợ cho Admin.')
        comparison_text = re.sub(r'^\s*so sanh\s+', '', comparison_text)
        parts = re.split(r'\s+so voi\s+|\s+voi\s+', ' ' + comparison_text, maxsplit=1)
        if len(parts) != 2:
            parts = re.split(r'\s+va\s+', comparison_text, maxsplit=1)
        if len(parts) != 2:
            raise Clarify('Hãy nêu kỳ hiện tại và kỳ gốc để so sánh.')
        left, right = parts[0].strip(), parts[1].strip(' ?')
        if not left:
            current = deepcopy(previous)
            commands = commands_for_period(current, role)
        else:
            if previous.period is None and not re.search(r'\b(?:hom|ngay|thang|quy|nam|tu)\b', left):
                raise Clarify('Hãy nêu kỳ hiện tại trước khi so sánh.')
            current, commands = parse_plan(left, previous, role)
        if not current.period or not set(current.metrics) <= {'revenue', 'order_statistics'}:
            raise Clarify('So sánh hỗ trợ doanh thu hoặc số đơn theo hai kỳ có cùng bộ lọc; hãy nêu rõ kỳ hiện tại.')
        if right in {'thang truoc', 'quy truoc', 'nam truoc', 'hom truoc', 'ngay truoc'}:
            baseline = preceding_period(current.period, right)
        else:
            parsed = parse_reporting_period(right, default_month=False)
            if parsed['intent'] != 'period' or parsed.get('_remaining', '').strip(' ?'):
                raise Clarify('Chưa xác định đủ kỳ gốc; không thay đổi bộ lọc khi so sánh.')
            baseline = Period(parsed['start_date'], parsed['end_date'], current.period.group)
        base = deepcopy(current)
        base.period = baseline
        current.comparison = baseline
        return validated_plan(previous, current, commands + commands_for_period(base, role))
    candidate = deepcopy(previous)
    candidate.operations = {k: Operation.KEEP for k in ('intent', 'metrics', 'period', 'status', 'payment', 'product', 'threshold')}
    candidate.pending_clarification = None
    candidate.comparison = None
    # Controls consume only their own scope; arbitrary negation is never discarded.
    clear_period = bool(re.search(r'\b(?:bo loc thoi gian|toan bo lich su)\b', text))
    clear_status = bool(re.search(r'\b(?:bo loc trang thai|tat ca trang thai)\b', text))
    clear_threshold = bool(re.search(r'\bbo nguong\b', text))
    text = re.sub(r'\b(?:bo loc thoi gian|toan bo lich su|bo loc trang thai|tat ca trang thai|bo nguong)\b', ' ', text)
    # Keep original punctuation for date ranges and product names.
    cleaned = message
    for phrase in ('bo loc thoi gian', 'toan bo lich su', 'bo loc trang thai', 'tat ca trang thai', 'bo nguong'):
        if phrase in normalize_question(cleaned):
            cleaned = text  # Controls have no slash dates; combined date/control is rejected below.
    # Accent-independent discourse words without losing date separators.
    cleaned = normalize_text(cleaned)
    exclusive_pattern = r'\bchi\s+(?=(?:don|da|chua|dang|ton kho|sap het|het hang)\b)'
    exclusive = bool(re.search(exclusive_pattern, cleaned))
    correction = re.match(r'^\s*khong phai\s+(.+?)\s+ma(?: la)?\s+(.+)$', cleaned)
    if correction:
        old_scope = parse_order_scope(correction[1])
        if old_scope['intent'] != 'order_statistics' or not old_scope['status']:
            raise Clarify('Chưa xác định được bộ lọc cần thay thế trong câu phủ định.')
        cleaned = correction[2]
        exclusive = True
    cleaned = re.sub(exclusive_pattern, ' ', cleaned)
    cleaned = re.sub(r'\s+(?:thoi|thi sao|nhe)\s*[?!.]*$', '', cleaned)
    cleaned = re.sub(r'\bhang het\b', 'het hang', cleaned)
    cleaned = re.sub(r'^\s*con\s+(?=(?:don|thang|quy|nam|sap het|het hang)\b)', '', cleaned)
    metrics = tuple(detect_requested_tools(cleaned, role))
    product = extract_product_query(message)
    if previous.product and normalize_question(cleaned) in {'con bao nhieu', 'ton kho', 'gia', 'gia bao nhieu', 'con hang khong'}:
        candidate.pending_clarification = None
        candidate.transition = 'FOLLOWUP'
        return validated_plan(previous, candidate, [previous.product])
    if product and not any(m in metrics for m in ('revenue', 'top_selling_products', 'order_statistics')):
        if product['type'] not in {'sku', 'name', 'attributes'}:
            raise Clarify('Chưa hiểu đầy đủ điều kiện sản phẩm; hãy tra từng tên, SKU hoặc tổ hợp thuộc tính được hỗ trợ.')
        candidate.intent, candidate.metrics, candidate.product = 'product_lookup', ('product',), message
        candidate.transition = 'NEW_TASK'
        candidate.period, candidate.status, candidate.payment = None, None, None
        candidate.metric_periods = {}
        candidate.inventory_mode, candidate.threshold, candidate.limit = None, 5, 20
        candidate.operations.update(intent=Operation.SET, metrics=Operation.SET, product=Operation.SET)
        return validated_plan(previous, candidate, [message])
    if not metrics:
        # Slot-only turns are followups only when their complete content has a
        # supported interpretation in the previous task. Unknown never repeats it.
        period_only = parse_reporting_period(cleaned, default_month=False)
        temporal_followup = (period_only['intent'] == 'period' and
                             not scope_remainder(period_only['_remaining'], []))
        slot_followup = bool(re.fullmatch(
            r'\s*(?:nguong\s+\d+|gioi han\s+\d+|bo loc thoi gian|'
            r'bo loc trang thai|tat ca trang thai|bo nguong|toan bo lich su)\s*',
            normalize_question(message)))
        order_followup = (previous.metrics == ('order_statistics',) and
                          parse_order_scope(cleaned)['intent'] == 'order_statistics' and
                          bool(parse_order_scope(cleaned)['status']))
        if previous.metrics and (temporal_followup or slot_followup or order_followup or clear_period or clear_status or clear_threshold):
            metrics = previous.metrics
        else:
            raise Clarify('Chưa xác định được yêu cầu mới; không lặp lại nghiệp vụ trước. ' + capabilities(role))
    if not metrics or 'product' in metrics:
        raise Clarify('Hãy nêu nghiệp vụ cần tra cứu: ' + capabilities(role))
    switched = metrics != previous.metrics
    candidate.transition = 'NEW_TASK' if switched else 'REFINEMENT' if detect_requested_tools(cleaned, role) else 'FOLLOWUP'
    candidate.metrics = metrics
    candidate.intent = metrics[0] if len(metrics) == 1 else 'multi_intent'
    candidate.operations.update(intent=Operation.SET if switched else Operation.KEEP,
                                metrics=Operation.SET if switched else Operation.KEEP)
    if switched:
        candidate.product = None
        if not ('order_statistics' in metrics and 'order_statistics' in previous.metrics):
            candidate.status = candidate.payment = None
        if not ('inventory' in metrics and 'inventory' in previous.metrics):
            candidate.inventory_mode = None
            candidate.threshold, candidate.limit = 5, 20
        if set(metrics) == {'inventory'}:
            candidate.period = None
        if 'top_selling_products' in metrics and 'top_selling_products' not in previous.metrics:
            candidate.top_limit = 5
    if clear_period:
        if 'toan bo lich su' in normalize_question(message) and 'inventory' in metrics:
            raise Clarify('Tồn kho chỉ có ảnh chụp hiện tại; chưa hỗ trợ toàn bộ lịch sử tồn kho.')
        if set(metrics) & {'revenue', 'top_selling_products', 'purchase_behavior'}:
            raise Clarify('Báo cáo này yêu cầu kỳ rõ ràng; không thể bỏ thời gian thành toàn bộ lịch sử.')
        candidate.period = None
        candidate.operations['period'] = Operation.CLEAR
    if clear_status:
        candidate.status = candidate.payment = None
        if 'inventory' in metrics:
            candidate.inventory_mode = None
            candidate.operations['inventory_mode'] = Operation.CLEAR
        candidate.operations.update(status=Operation.CLEAR, payment=Operation.CLEAR)
    if clear_threshold:
        candidate.threshold = 5
        candidate.operations['threshold'] = Operation.CLEAR
    # Split clauses on business conjunctions, never silently omit any clause.
    clauses = re.split(r'\s+va\s+|[,;]', cleaned)
    assigned = {}
    if len(metrics) > 1 and not detect_requested_tools(cleaned, role):
        period_only = parse_reporting_period(cleaned, default_month=False)
        if period_only['intent'] == 'period' and not period_only['_remaining'].strip(' ?'):
            assigned = {m: cleaned for m in metrics if m != 'inventory'}
            clauses = []
    for clause in clauses:
        if not clause.strip():
            continue
        detected = detect_requested_tools(clause, role)
        if len(detected) > 1:
            raise Clarify('Hãy phân tách rõ từng chỉ số bằng “và”.')
        metric = detected[0] if detected else metrics[0] if len(metrics) == 1 else None
        if metric is None or metric in assigned:
            raise Clarify('Chưa xác định đủ phạm vi từng chỉ số.')
        assigned[metric] = clause
    # A single explicit reporting period applies to all period-based metrics.
    # Inventory remains a current snapshot and may never consume a dated clause.
    periods = {}
    dated_inventory = None
    for metric, clause in assigned.items():
        if re.search(r'\b(?:hom|ngay|thang|quy|nam|tuan|tu)\b', clause):
            parsed = parse_reporting_period(clause, default_month=False)
            if parsed['intent'] != 'period':
                raise Clarify(parsed['message'])
            value = Period(parsed['start_date'], parsed['end_date'], parsed['group_by'])
            if metric == 'inventory':
                dated_inventory = (clause, parsed, value)
            else:
                periods[metric] = value
    if dated_inventory:
        clause, parsed, value = dated_inventory
        # A trailing period can scope the reporting list; an explicitly dated
        # snapshot or a second local period is a historical inventory request.
        if len(metrics) == 1 or periods or re.search(r'\b(?:lich su|tai thoi diem|cuoi|dau|cua)\b', clause):
            raise Clarify('Tồn kho chỉ phản ánh hiện tại, chưa có lịch sử theo kỳ.')
        assigned['inventory'] = parsed['_remaining']
        periods = {m: value for m in metrics if m != 'inventory'}
    if periods:
        unique = set(periods.values())
        if len(unique) > 1 and set(metrics) - {'inventory'} - periods.keys():
            raise Clarify('Hãy nêu rõ kỳ cho từng chỉ số; có nhiều kỳ khác nhau trong yêu cầu.')
        candidate.period = next(iter(unique)) if len(unique) == 1 else None
        candidate.operations['period'] = Operation.SET
    if not candidate.period and not periods and set(metrics) & {'revenue', 'top_selling_products', 'purchase_behavior'}:
        default = parse_reporting_period('')
        candidate.period = Period(default['start_date'], default['end_date'], default['group_by'])
        candidate.operations['period'] = Operation.SET
    candidate.metric_periods = {}
    for metric in metrics:
        if metric != 'inventory':
            value = periods.get(metric, candidate.period if periods else previous.metric_periods.get(metric, candidate.period))
            if clear_period:
                value = None
            if value:
                candidate.metric_periods[metric] = value
    commands = []
    for metric in metrics:
        metric_period = candidate.metric_periods.get(metric)
        clause = assigned.get(metric, '')
        grouped = bool(re.search(r'\b(?:theo|moi|tung)\s+(?:ngay|thang)\b', clause))
        if metric == 'inventory':
            if re.search(r'\b(?:ngay|thang|quy|nam|tuan)\b', clause):
                raise Clarify('Tồn kho chỉ phản ánh hiện tại, chưa có lịch sử theo kỳ.')
            scope = inventory_scope(clause if detect_requested_tools(clause, role) else 'ton kho ' + clause)
            if scope is None or scope['intent'] != 'inventory_statistics':
                raise Clarify((scope or {}).get('message', 'Chưa rõ phạm vi tồn kho.'))
            if scope['mode'] is not None or switched:
                candidate.inventory_mode = scope['mode']
            if scope['explicit_threshold']:
                candidate.threshold = scope['threshold']
                candidate.operations['threshold'] = Operation.SET
            if scope['explicit_limit']:
                candidate.limit = scope['limit']
            mode = {None: 'ton kho', 'low_stock': 'sap het hang', 'out_of_stock': 'het hang', 'in_stock': 'con hang'}[candidate.inventory_mode]
            commands.append(f'{mode} nguong {candidate.threshold} gioi han {candidate.limit}')
        elif metric == 'order_statistics':
            has_time = bool(re.search(r'\b(?:hom|ngay|thang|quy|nam|tuan|tu)\b|\d', clause))
            if has_time:
                period = parse_reporting_period(clause, default_month=False)
                if period['intent'] != 'period':
                    raise Clarify(period['message'])
                metric_period = Period(period['start_date'], period['end_date'], period['group_by'])
                candidate.metric_periods[metric] = metric_period
                candidate.operations['period'] = Operation.SET
                clause = period['_remaining']
            scope = parse_order_scope(clause)
            if scope['intent'] != 'order_statistics':
                raise Clarify(scope['message'])
            if scope['status']:
                if exclusive:
                    candidate.status = candidate.payment = None
                    candidate.operations.update(status=Operation.CLEAR, payment=Operation.CLEAR)
                # Status and payment are separate constraints; never silently replace one with the other.
                setattr(candidate, 'payment' if scope['status_kind'] == 'payment' else 'status', scope['status'])
                candidate.operations['payment' if scope['status_kind'] == 'payment' else 'status'] = Operation.SET
            if candidate.status and candidate.payment:
                raise Clarify('API chưa hỗ trợ ghép trạng thái đơn và thanh toán; hãy bỏ bộ lọc trạng thái trước.')
            if metric_period and candidate.payment:
                raise Clarify('API đếm đơn theo kỳ chưa lọc trạng thái thanh toán; hãy bỏ bộ lọc thời gian hoặc trạng thái.')
            if grouped:
                raise Clarify('Công cụ đếm đơn chưa hỗ trợ chia nhóm theo ngày/tháng.')
            command = 'don hang ' + (candidate.status or candidate.payment or '')
            if metric_period:
                command += f' tu {metric_period.start.isoformat()} den {metric_period.end.isoformat()}'
            commands.append(command)
        elif metric in {'revenue', 'top_selling_products', 'purchase_behavior'}:
            parsed = parse_reporting_period(clause)
            if parsed['intent'] != 'period':
                raise Clarify(parsed['message'])
            remaining = parsed['_remaining']
            if metric == 'purchase_behavior':
                if not metric_period or (metric_period.end - metric_period.start).days > 366:
                    raise Clarify('Report mua hàng hỗ trợ tối đa 367 ngày.')
                if scope_remainder(remaining, [PURCHASE_REQUEST, r'phan tich|thong ke|bao cao|chi so|khach hang|va']):
                    raise Clarify('Report chỉ có chỉ số mua hàng tổng hợp; chưa hỗ trợ bộ lọc hoặc suy luận hành vi này.')
            elif not reporting_scope_supported(remaining, selling=metric == 'top_selling_products'):
                raise Clarify('Chưa hỗ trợ đầy đủ bộ lọc hoặc phép phân tích này.')
            if metric == 'top_selling_products':
                if re.search(r'\b(?:theo|moi|tung)\s+(?:ngay|thang)\b', clause):
                    raise Clarify('Báo cáo bán chạy chưa hỗ trợ chia nhóm theo ngày/tháng.')
                top = re.search(r'\btop\s*(\d+)\b', clause)
                if top:
                    candidate.top_limit = int(top[1])
                if not 1 <= candidate.top_limit <= 20:
                    raise Clarify('Top sản phẩm phải từ 1 đến 20.')
            command = {'revenue': 'doanh thu', 'top_selling_products': f'top {candidate.top_limit} san pham ban chay',
                       'purchase_behavior': 'hanh vi mua hang'}[metric]
            if not metric_period:
                raise Clarify('Hãy nêu kỳ cho từng chỉ số báo cáo.')
            command += f' tu {metric_period.start.isoformat()} den {metric_period.end.isoformat()}'
            if metric == 'revenue':
                command += ' theo ' + ('ngay' if metric_period.group == 'day' else 'thang')
            commands.append(command)
        else:
            raise Clarify('Nghiệp vụ chưa được hỗ trợ trong phạm vi này.')
    return validated_plan(previous, candidate, commands)


def commands_for_period(state, role):
    if not state.period or not state.metrics:
        raise Clarify('Cần kỳ và chỉ số hiện tại trước khi so sánh.')
    prefix = {'revenue': 'doanh thu', 'order_statistics': 'don hang ' + (state.status or state.payment or '')}
    if not set(state.metrics) <= set(prefix):
        raise Clarify('Chỉ hỗ trợ so sánh số đơn và doanh thu.')
    message = ' va '.join(prefix[m] for m in state.metrics)
    message += f' tu {state.period.start.isoformat()} den {state.period.end.isoformat()}'
    commands = parse_plan(message, state, role)[1]
    group = 'ngay' if state.period.group == 'day' else 'thang'
    return [re.sub(r' theo (?:ngay|thang)$', ' theo ' + group, command)
            if command.startswith('doanh thu ') else command for command in commands]


def preceding_period(period, phrase):
    start, end = period.start, period.end
    if phrase in {'hom truoc', 'ngay truoc'} and start == end:
        return Period(start - timedelta(days=1), start - timedelta(days=1), period.group)
    if phrase == 'thang truoc' and start.day == 1 and end == date(start.year, start.month, monthrange(start.year, start.month)[1]):
        end = start - timedelta(days=1)
        return Period(end.replace(day=1), end, period.group)
    if phrase == 'quy truoc' and start.day == 1 and start.month in {1, 4, 7, 10} and end.month == start.month + 2 and end.day == monthrange(end.year, end.month)[1]:
        end = start - timedelta(days=1)
        return Period(date(end.year, end.month - 2, 1), end, period.group)
    if phrase == 'nam truoc' and start == date(start.year, 1, 1) and end == date(start.year, 12, 31):
        return Period(date(start.year - 1, 1, 1), date(start.year - 1, 12, 31), period.group)
    raise Clarify('Kỳ hiện tại không tương ứng một ngày/tháng/quý/năm đầy đủ để suy ra kỳ trước.')


def business_turn(message, row, tool, *, role):
    text = normalize_question(message)
    previous = row.get('business_state') or BusinessState()
    act = conversational_act(message)
    if act == 'reset':
        row['business_state'] = BusinessState(operations={'intent': Operation.RESET}, transition='RESET')
        row['last_result'] = None
        return reply('conversation_reset', 'Đã xóa ngữ cảnh nghiệp vụ. ' + capabilities(role))
    if act in {'greeting', 'capability'}:
        previous.pending_clarification = None
        row['business_state'] = previous
        return reply('greeting', capabilities(role))
    explicit_task = detect_requested_tools(message, 'admin') or re.search(r'\b(?:loi nhuan|du bao|khach hang)\b', text)
    explanation = followup_reply(message, row) if not explicit_task else None
    if explanation:
        previous.pending_clarification = None
        return explanation
    try:
        candidate, commands = parse_plan(message, previous, role)
    except Clarify as exc:
        previous.pending_clarification = str(exc)
        previous.operations = {'intent': Operation.UNKNOWN}
        previous.transition = 'UNKNOWN'
        row['business_state'] = previous
        return reply('unsupported', str(exc) + ' Bạn có thể nói “bỏ qua” để thoát hoặc hỏi nghiệp vụ khác.', status='clarification_required')
    try:
        results = [tool(command) for command in commands]
    except Exception:
        # No exception details (credentials/SQL) or partial facts in responses.
        return reply('source_error', 'Nguồn dữ liệu chưa sẵn sàng hoặc đã hết thời gian chờ; chưa áp dụng thay đổi phạm vi.', success=False, status='source_error')
    if any(not isinstance(r, dict) for r in results):
        return reply('source_error', 'Nguồn chưa trả đủ dữ liệu đã xác minh; chưa áp dụng thay đổi phạm vi.', success=False, status='source_error')
    if any(r.get('intent') in {'unsupported', 'invalid', 'source_error'} or r.get('success') is False for r in results):
        return reply('unsupported', 'Chưa thể trả đầy đủ yêu cầu; chưa áp dụng thay đổi phạm vi.', status='clarification_required')
    if any(r.get('data') is None for r in results):
        return reply('source_error', 'Nguồn chưa trả đủ dữ liệu đã xác minh; chưa áp dụng thay đổi phạm vi.', success=False, status='source_error')
    if candidate.comparison:
        n = len(candidate.metrics)
        changes = {}
        try:
            with localcontext() as ctx:
                ctx.prec = 50
                for metric, current, base in zip(candidate.metrics, results[:n], results[n:]):
                    key = 'confirmed_payment_amount_vnd' if metric == 'revenue' else 'total_orders'
                    a, b = Decimal(str(current['data'][key])), Decimal(str(base['data'][key]))
                    if not a.is_finite() or not b.is_finite():
                        raise ValueError('Non-finite report amount')
                    changes[metric] = {'current': str(a), 'baseline': str(b), 'difference': str(a - b),
                                       'percentage_change': str(((a-b)*100/b).quantize(Decimal('0.01'))) if b else None,
                                       'unit': 'VND' if metric == 'revenue' else 'orders'}
        except (KeyError, TypeError, ValueError, InvalidOperation):
            return reply('source_error', 'Không đủ số liệu hợp lệ để so sánh; chưa áp dụng thay đổi phạm vi.', success=False, status='source_error')
        lines = [f"Kỳ hiện tại {candidate.period.start:%d/%m/%Y}–{candidate.period.end:%d/%m/%Y}; "
                 f"kỳ gốc {candidate.comparison.start:%d/%m/%Y}–{candidate.comparison.end:%d/%m/%Y}."]
        for metric, values in changes.items():
            pct = values['percentage_change']
            label = 'Doanh thu thanh toán xác nhận' if metric == 'revenue' else 'Số đơn theo ngày tạo'
            lines.append(f"{label}: {values['current']} so với {values['baseline']} {values['unit']}; "
                         f"chênh lệch {values['difference']} {values['unit']}; " +
                         (f"thay đổi {pct}%." if pct is not None else 'tỷ lệ không xác định vì kỳ gốc bằng 0.'))
        lines.append('Các kỳ dùng cùng định nghĩa và bộ lọc; chưa đủ dữ liệu kết luận nguyên nhân, lợi nhuận hoặc dự báo.')
        row['business_state'] = candidate
        return {'intent': 'period_comparison', 'data': {'changes': changes, 'current': [r['data'] for r in results[:n]],
                'baseline': [r['data'] for r in results[n:]]}, 'answer': '\n'.join(lines),
                'evidence': evidence(candidate)}
    row['business_state'] = candidate
    result = results[0] if len(results) == 1 else {
        'intent': 'multi_intent', 'tools_used': list(candidate.metrics),
        'data': dict(zip(candidate.metrics, [r.get('data') for r in results])),
        'answer': '\n\n'.join(r['answer'] for r in results)}
    return {**result, 'evidence': evidence(candidate), 'data_status': result_data_status(result),
            'state_operations': {k: v.value for k, v in candidate.operations.items()}}


def result_data_status(result):
    data = result.get('data') or {}
    if result['intent'] in {'product_lookup', 'top_selling_products'}:
        return 'available' if data.get('products', data.get('items')) else 'no_data'
    scalar = next((data[k] for k in ('value', 'total_orders', 'confirmed_payment_amount_vnd', 'total_products') if k in data), None)
    return 'zero' if scalar is not None and Decimal(str(scalar)) == 0 else 'available'


def evidence(candidate):
    return {'source': 'business_services', 'metrics': list(candidate.metrics), 'transition': candidate.transition,
            'metric_periods': {m: {'start_date': p.start.isoformat(), 'end_date': p.end.isoformat()} for m, p in candidate.metric_periods.items()},
            'period': {'start_date': candidate.period.start.isoformat(), 'end_date': candidate.period.end.isoformat()} if candidate.period else None,
            'status': candidate.status, 'payment': candidate.payment,
            'comparison_period': {'start_date': candidate.comparison.start.isoformat(), 'end_date': candidate.comparison.end.isoformat()} if candidate.comparison else None,
            'time_basis': {m: {'revenue': 'verified_payment_at', 'top_selling_products': 'verified_payment_at',
                              'order_statistics': 'order_created_at', 'purchase_behavior': 'order_created_at',
                              'inventory': 'current_snapshot', 'product': 'current_snapshot'}[m] for m in candidate.metrics}}
