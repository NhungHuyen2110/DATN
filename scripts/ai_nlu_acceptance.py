"""Fail-closed acceptance assertions, independent of parser predictions.

Expected paths are authored from the case contract, never from actual evidence.
Functional/data reconciliation must run after this NLU/status gate.
"""


def assert_acceptance(body, expected):
    assert body.get('intent') == expected['intent'], ('intent', body.get('intent'), expected['intent'])
    assert body.get('status', 'ok') == expected.get('status', 'ok'), ('status', body.get('status'))
    assert body.get('success') is not False, 'unsuccessful response'
    if expected.get('data_required', True):
        assert body.get('data') is not None, 'positive case requires business data'
        assert body.get('intent') not in {'unsupported', 'clarification', 'invalid', 'source_error'}
    else:
        assert body.get('data') is None, 'negative/control case must not publish data'
    for path, value in expected.get('fields', {}).items():
        actual = body
        for key in path.split('.'):
            assert isinstance(actual, dict) and key in actual, ('missing', path)
            actual = actual[key]
        assert actual == value, (path, actual, value)
    if expected.get('reason'):
        assert expected['reason'].casefold() in body.get('answer', '').casefold(), 'incorrect refusal reason'


def captured_contracts():
    """Reviewed contracts for the 54 Phase 3–5 business turns (not predictions)."""
    admin = {
        1: 'greeting', 2: 'revenue_statistics', 3: 'revenue_statistics', 4: 'revenue_statistics',
        5: 'period_comparison', 6: 'orders_by_period', 7: 'orders_by_period', 8: 'period_comparison',
        9: 'revenue_statistics', 10: 'top_selling_products', 11: 'purchase_behavior',
        12: 'inventory_statistics', 13: 'multi_intent', 14: 'multi_intent', 15: 'period_comparison',
        16: 'revenue_statistics', 17: 'revenue_statistics', 18: 'revenue_statistics',
        19: 'revenue_statistics', 20: 'period_comparison', 21: 'unsupported',
        22: 'conversation_reset', 23: 'unsupported', 24: 'purchase_behavior',
        25: 'unsupported', 26: 'conversation_reset', 27: 'unsupported'}
    staff = {i: 'inventory_statistics' for i in range(6, 12)}
    staff.update({1: 'greeting', 2: 'product_lookup', 3: 'product_lookup', 4: 'product_lookup',
                  5: 'product_lookup', **{i: 'order_statistics' for i in range(12, 16)},
                  16: 'orders_by_period', 17: 'orders_by_period', 18: 'order_statistics',
                  19: 'order_statistics', 20: 'unsupported', 21: 'conversation_reset',
                  22: 'inventory_statistics', 23: 'unsupported', 24: 'unsupported',
                  25: 'unsupported', 26: 'conversation_reset', 27: 'unsupported'})
    result = {}
    metric = {'revenue_statistics': 'revenue', 'orders_by_period': 'order_statistics',
              'order_statistics': 'order_statistics', 'top_selling_products': 'top_selling_products',
              'purchase_behavior': 'purchase_behavior', 'inventory_statistics': 'inventory', 'product_lookup': 'product'}
    for role, cases in [('a', admin), ('s', staff)]:
        for number, intent in cases.items():
            supported = intent not in {'greeting', 'unsupported', 'conversation_reset'}
            fields = {}
            if supported:
                metrics = ['revenue', 'order_statistics'] if intent == 'multi_intent' or (role == 'a' and number == 15) else [
                    'order_statistics' if role == 'a' and number == 8 else 'revenue'] if intent == 'period_comparison' else [metric[intent]]
                fields['evidence.metrics'] = metrics
                fields['evidence.status'] = 'shipping' if role == 'a' and number in {6, 7, 8, 13, 14, 15} or role == 's' and number in {13, 16, 17, 18} else 'cancelled' if role == 's' and number == 14 else 'packing' if role == 's' and number == 15 else None
                fields['evidence.payment'] = 'paid' if role == 's' and number == 19 else None
                period = None
                if role == 'a':
                    periods = {**{i: ('2026-11-01', '2026-11-30') for i in (2, 4, 5, 6, 9, 10, 11, 13)},
                               **{i: ('2026-10-01', '2026-10-31') for i in (3, 7, 8, 14, 15, 24)},
                               16: ('2026-07-01', '2026-09-30'), 17: ('2026-01-01', '2026-12-31'),
                               18: ('2024-02-29', '2024-02-29'), 19: ('2026-09-01', '2026-10-15'),
                               20: ('2026-09-01', '2026-09-30')}
                    period = periods.get(number)
                elif number in {16, 17}:
                    period = ('2026-11-01', '2026-11-30') if number == 16 else ('2026-10-01', '2026-10-31')
                fields['evidence.period'] = dict(zip(('start_date', 'end_date'), period)) if period else None
            result[f'{role}{number:02}'] = {'intent': intent, 'data_required': supported,
                'status': 'clarification_required' if intent == 'unsupported' else 'ok', 'fields': fields}
    reasons = {'a21': 'bộ lọc', 'a23': 'kỳ', 'a25': 'chỉ đọc dữ liệu', 'a27': 'lịch sử',
               's20': 'bộ lọc đơn hàng', 's23': 'Staff', 's24': 'Staff',
               's25': 'chỉ đọc dữ liệu', 's27': 'nghiệp vụ'}
    for key, reason in reasons.items():
        result[key]['reason'] = reason
    return result
