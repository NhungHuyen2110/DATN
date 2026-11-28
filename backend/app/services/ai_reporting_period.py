"""Read-only reporting scope grammar. Never replace an unparsed period with now.

Only one period is accepted. Comparisons require a separate tool contract.
The remainder permits callers to validate non-temporal constraints as well.
"""
import re
from calendar import monthrange
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from .ai_staff_intent import normalize_text
from shared.conversation import normalize_utterance, scope_remainder

VIETNAM = ZoneInfo('Asia/Ho_Chi_Minh')
TEMPORAL = r'\b(?:hom|ngay|thang|tuan|quy|nam|ky|nien)\b|\d'
DATE = r'(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{4})'


def has_period(message):
    return bool(re.search(TEMPORAL, normalize_text(message)))


def unsupported_period():
    return {'intent': 'unsupported', 'message':
            'Chưa hỗ trợ hoặc chưa xác định đủ phạm vi này. '
            'Hãy nêu một ngày, tháng, quý, năm hoặc khoảng ngày đầy đủ; '
            'yêu cầu so sánh nhiều kỳ cần hỏi riêng từng kỳ.'}


def parse_reporting_period(message, *, default_month=True):
    text = normalize_utterance(message)
    if re.search(r'\b(?:so sanh|chenh lech|tang truong|so voi|cung ky|ty le|phan tram)\b|%', text):
        return unsupported_period()
    today = datetime.now(VIETNAM).date()
    spans, periods = [], []
    grouping = re.search(r'\b(?:theo|moi|tung)\s+(ngay|thang)\b', text)
    group_by = {'ngay': 'day', 'thang': 'month'}[grouping[1]] if grouping else None
    if grouping:
        spans.append(grouping.span())

    def covered(match):
        return any(match.start() < b and match.end() > a for a, b in spans)

    def add(pattern, resolve):
        for m in re.finditer(pattern, text):
            if not covered(m):
                periods.append(resolve(m))
                spans.append(m.span())

    def day(value):
        if '-' in value:
            y, m, d = map(int, value.split('-'))
        else:
            d, m, y = map(int, value.split('/'))
        return date(y, m, d)

    def month(y, m):
        return date(y, m, 1), date(y, m, monthrange(y, m)[1]), 'month'

    def quarter(y, q):
        if not 1 <= q <= 4:
            raise ValueError('Invalid quarter')
        m = (q - 1) * 3 + 1
        return date(y, m, 1), date(y, m + 2, monthrange(y, m + 2)[1]), 'month'

    def year(m):
        return int(m[2] or m[3] or today.year)

    try:
        add(r'\btu\s+(?:ngay\s+)?(' + DATE + r')\s+(?:den|toi)\s+(?:ngay\s+)?(' + DATE + r')\b',
            lambda m: (day(m[1]), day(m[2]), 'day'))
        add(r'\b(?:ngay\s+)?(' + DATE + r')\b', lambda m: (day(m[1]), day(m[1]), 'day'))
        for phrase, d in [('hom nay', today), ('hom qua', today - timedelta(days=1))]:
            add(r'\b' + phrase + r'\b', lambda m, d=d: (d, d, 'day'))
        previous = today.replace(day=1) - timedelta(days=1)
        for phrase, y, m in [('thang nay', today.year, today.month),
                             ('thang truoc', previous.year, previous.month)]:
            add(r'\b' + phrase + r'\b', lambda match, y=y, m=m: month(y, m))
        for phrase, y in [('nam nay', today.year), ('nam truoc', today.year - 1)]:
            add(r'\b' + phrase + r'\b', lambda match, y=y: (date(y, 1, 1), date(y, 12, 31), 'month'))
        q = (today.month - 1) // 3 + 1
        for phrase, y, value in [('quy nay', today.year, q),
                                  ('quy truoc', today.year if q > 1 else today.year - 1, q - 1 if q > 1 else 4)]:
            add(r'\b' + phrase + r'\b', lambda match, y=y, value=value: quarter(y, value))
        add(r'\bthang\s+(\d{1,2})(?:\s*/\s*(\d{4})|\s+nam\s+(\d{4}))?\b',
            lambda m: month(year(m), int(m[1])))
        add(r'\bquy\s+(\d+)(?:\s*/\s*(\d{4})|\s+nam\s+(\d{4}))?\b',
            lambda m: quarter(year(m), int(m[1])))
        add(r'\bnam\s+(\d{4})\b', lambda m: (date(int(m[1]), 1, 1), date(int(m[1]), 12, 31), 'month'))
        remaining = list(text)
        for a, b in spans:
            remaining[a:b] = ' ' * (b - a)
        remaining = ''.join(remaining)
        # Top K belongs to a different slot, not a year/day number.
        temporal_remainder = re.sub(r'\btop\s*\d+\b', ' ', remaining)
        if re.search(TEMPORAL, temporal_remainder):
            return unsupported_period()
        if len(periods) > 1:
            return {'intent': 'invalid', 'message': 'Có nhiều mốc thời gian. Vui lòng chọn một kỳ chung.'}
        if not periods:
            if not default_month:
                return unsupported_period()
            periods = [month(today.year, today.month)]
        start, end, default_group = periods[0]
        if not 2000 <= start.year <= 2100 or not 2000 <= end.year <= 2100 or start > end or (end-start).days > 3660:
            raise ValueError('Invalid reporting range')
    except (ValueError, OverflowError):
        return {'intent': 'invalid', 'message': 'Ngày, tháng, quý, năm hoặc khoảng thời gian không hợp lệ.'}
    return {'intent': 'period', 'start_date': start, 'end_date': end,
            'group_by': group_by or default_group, '_remaining': remaining}


def reporting_scope_supported(remaining, *, selling=False, multi=False):
    """Allow only supported report vocabulary; unknown filters must abstain."""
    remaining = re.sub(r'\btop\s*\d+\b', ' ', remaining)
    patterns = [r'doanh thu|tien ban hang|thanh toan da xac nhan|gia tri',
                r'thong ke|tong cong|tong|tat ca|toan bo lich su|duoc|trong|nay|va']
    if selling or multi:
        patterns += [r'san pham|mat hang|ban chay(?: nhat)?|ban nhieu|mua nhieu nhat|top|so luong']
    if multi:
        patterns += [r'ton kho|sap het hang|het hang|con hang|dem|don hang']
        from .ai_order_scope import STATE_PHRASES
        patterns += [re.escape(phrase) for phrases in STATE_PHRASES.values() for phrase in phrases]
    return not scope_remainder(remaining, patterns)
