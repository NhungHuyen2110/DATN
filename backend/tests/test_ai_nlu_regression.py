"""NLU contracts, independent paraphrases, state matrix and oracle mutation tests."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.services.ai_business_dialogue import BusinessState, business_turn, parse_plan
from scripts.ai_nlu_acceptance import assert_acceptance, captured_contracts


CONTEXTS = ('fresh', 'inventory', 'orders', 'revenue', 'product', 'pending')


def context(name):
    seeds = {'inventory': 'tồn kho ngưỡng 3', 'orders': 'đơn đang giao tháng 10/2026',
             'revenue': 'doanh thu tháng 10/2026', 'product': 'Tra SKU SP000002',
             'pending': 'đơn đang giao tháng 10/2026'}
    row = {}
    if name in seeds:
        row['business_state'] = parse_plan(seeds[name], BusinessState(), 'admin')[0]
    if name == 'pending':
        business_turn('đơn ở Hà Nội', row, Mock(), role='admin')
    return row


# Authored before running this suite; these are engineering holdouts, not human
# blind labels or a population accuracy estimate. Every positive requires data.
POSITIVES = [
    ('Xin chào bạn, thống kê tồn kho', 'inventory_statistics', 'inventory'),
    ('Vui lòng liệt kê những sản phẩm sắp hết hàng', 'inventory_statistics', 'inventory'),
    ('Cho mình hỏi có đơn đang giao không?', 'order_statistics', 'order_statistics'),
    ('Bạn có thể cho tôi biết có đơn đang giao không?', 'order_statistics', 'order_statistics'),
    ('Bạn có thể thống kê những sản phẩm sắp hết hàng không?', 'inventory_statistics', 'inventory'),
    ('Co don da huy khong?', 'order_statistics', 'order_statistics'),
    ('Xin chào, doanh thu tháng 11/2026 nhé', 'revenue_statistics', 'revenue'),
    ('Doahn thu tháng 11/2026', 'revenue_statistics', 'revenue'),
    ('Thogn ke ton kho', 'inventory_statistics', 'inventory'),
    ('Hàng sắp hết', 'inventory_statistics', 'inventory'),
    ('Phân tích hành vi mua hàng quý 3 năm 2026', 'purchase_behavior', 'purchase_behavior'),
]


def fixture_tool(command):
    if command.startswith(('ton kho', 'sap het', 'het hang', 'con hang')):
        return {'intent': 'inventory_statistics', 'answer': 'fixture stock',
                'data': {'total_products': 3, 'out_of_stock_products': 1, 'low_stock_products': 1}}
    if command.startswith('don hang'):
        if ' tu ' in command:
            parts = command.split()
            return {'intent': 'orders_by_period', 'answer': 'fixture period orders',
                    'data': {'total_orders': 2, 'start_date': parts[-3], 'end_date': parts[-1],
                             'status': parts[2] if parts[2] != 'tu' else None}}
        return {'intent': 'order_statistics', 'answer': 'fixture orders', 'data': {'value': 2}}
    if command.startswith('doanh thu'):
        return {'intent': 'revenue_statistics', 'answer': 'fixture revenue',
                'data': {'confirmed_payment_amount_vnd': '123.45'}}
    if command.startswith('hanh vi'):
        return {'intent': 'purchase_behavior', 'answer': 'fixture purchase', 'data': {'unique_buyers': 2}}
    if command.startswith('top '):
        return {'intent': 'top_selling_products', 'answer': 'fixture ranked products', 'data': {'items': []}}
    from app.services.ai_product_lookup import extract_product_query
    if extract_product_query(command):
        return {'intent': 'product_lookup', 'answer': 'fixture products', 'data': {'products': []}}
    raise AssertionError('Unexpected dispatch: ' + command)


@pytest.mark.parametrize('seed', CONTEXTS)
@pytest.mark.parametrize('message,intent,metric', POSITIVES)
def test_positive_state_matrix(seed, message, intent, metric):
    # Bare inventory questions after an explicit product are intentionally product
    # references; these framed full tasks explicitly request a stock report.
    row = context(seed)
    old_metrics = row.get('business_state', BusinessState()).metrics
    tool = Mock(side_effect=fixture_tool)
    result = business_turn(message, row, tool, role='admin')
    expected_status = 'shipping' if metric == 'order_statistics' and 'giao' in message else 'cancelled' if metric == 'order_statistics' else None
    expected_intent = 'orders_by_period' if metric == 'order_statistics' and seed in {'orders', 'revenue', 'pending'} else intent
    assert_acceptance(result, {'intent': expected_intent, 'fields': {
        'evidence.metrics': [metric], 'evidence.status': expected_status,
        'evidence.payment': None,
        'evidence.transition': 'REFINEMENT' if old_metrics == (metric,) else 'NEW_TASK'}})
    assert row['business_state'].pending_clarification is None
    assert result['data'] == fixture_tool(tool.call_args.args[0])['data']
    tool.assert_called_once()
    command = tool.call_args.args[0]
    if metric == 'inventory':
        assert row['business_state'].period is None
        assert row['business_state'].inventory_mode == ('low_stock' if 'sắp hết' in message else None)
        assert row['business_state'].threshold == (3 if seed == 'inventory' else 5)
        assert ' tu ' not in command
    elif metric == 'order_statistics':
        assert command == 'don hang ' + expected_status + (' tu 2026-10-01 den 2026-10-31' if seed in {'orders', 'revenue', 'pending'} else '')
    elif metric == 'revenue':
        assert command == 'doanh thu tu 2026-11-01 den 2026-11-30 theo thang'
    elif metric == 'purchase_behavior':
        assert command == 'hanh vi mua hang tu 2026-07-01 den 2026-09-30'


@pytest.mark.parametrize('seed', CONTEXTS)
@pytest.mark.parametrize('message,reason', [
    ('đơn không bị hủy', 'bộ lọc đơn hàng'), ('Có đơn chưa giao không?', 'bộ lọc đơn hàng'),
    ('Tồn kho tại chi nhánh Hà Nội', 'bộ lọc tồn kho'),
    ('Doanh thu theo nhân viên tháng 10/2026', 'bộ lọc'),
    ('Phân tích hành vi mua hàng theo giới tính', 'bộ lọc'),
    ('Tồn kho tháng 10/2026', 'lịch sử'),
    ('Xin chào, xóa đơn hàng 2', 'chỉ đọc dữ liệu'),
    ('chuyện thời tiết hôm nay ra sao', 'yêu cầu mới'),
    ('abc xyz', 'yêu cầu mới'),
    ('Doanh thu tháng 10 và tồn kho cuối tháng 9', 'lịch sử'),
])
def test_negative_state_matrix_is_read_free(seed, message, reason):
    row = context(seed)
    previous = deepcopy(row.get('business_state', BusinessState()))
    tool = Mock()
    result = business_turn(message, row, tool, role='admin')
    assert_acceptance(result, {'intent': 'unsupported', 'status': 'clarification_required',
                               'data_required': False, 'reason': reason})
    tool.assert_not_called()
    state = row['business_state']
    assert state.metrics == previous.metrics and state.period == previous.period
    assert state.status == previous.status and state.threshold == previous.threshold
    assert state.transition == 'UNKNOWN'


@pytest.mark.parametrize('seed', CONTEXTS)
@pytest.mark.parametrize('message', ['Xin chào bạn nhé', 'Hello shop!', 'Chào bạn, bạn có thể làm gì?', 'Xin chào, bạn có thể giúp tôi được gì?'])
def test_greeting_never_replays_old_metric(seed, message):
    row, tool = context(seed), Mock()
    assert_acceptance(business_turn(message, row, tool, role='admin'),
                      {'intent': 'greeting', 'data_required': False})
    tool.assert_not_called()
    assert row['business_state'].pending_clarification is None


@pytest.mark.parametrize('message,commands', [
    ('doanh thu và tồn kho tháng 9/2026', ['doanh thu tu 2026-09-01 den 2026-09-30 theo thang', 'ton kho nguong 5 gioi han 20']),
    ('doanh thu tháng 9/2026 và đơn tháng 10/2026', ['doanh thu tu 2026-09-01 den 2026-09-30 theo thang', 'don hang  tu 2026-10-01 den 2026-10-31']),
    ('doanh thu tháng 9/2026 và tồn kho hiện tại', ['doanh thu tu 2026-09-01 den 2026-09-30 theo thang', 'ton kho nguong 5 gioi han 20']),
])
def test_metric_temporal_scope(message, commands):
    row, tool = {}, Mock(side_effect=fixture_tool)
    result = business_turn(message, row, tool, role='admin')
    assert_acceptance(result, {'intent': 'multi_intent'})
    assert [call.args[0] for call in tool.call_args_list] == commands
    periods = result['evidence']['metric_periods']
    assert 'inventory' not in periods
    assert periods['revenue'] == {'start_date': '2026-09-01', 'end_date': '2026-09-30'}
    if 'đơn' in message:
        assert periods['order_statistics'] == {'start_date': '2026-10-01', 'end_date': '2026-10-31'}
        state, following = parse_plan('tháng 11/2026 thì sao', row['business_state'], 'admin')
        assert all('2026-11-30' in c for c in following)


@pytest.mark.parametrize('bad', [
    {'intent': 'unsupported', 'data': None, 'status': 'clarification_required'},
    {'intent': 'clarification', 'data': None}, {'intent': 'order_statistics', 'data': None},
    {'intent': 'order_statistics', 'data': {'value': 1}, 'status': 'clarification_required'},
    {'intent': 'order_statistics', 'data': {'value': 1}, 'evidence': {'status': 'cancelled'}},
])
def test_oracle_rejects_false_positive(bad):
    with pytest.raises(AssertionError):
        assert_acceptance(bad, {'intent': 'order_statistics', 'fields': {'evidence.status': 'shipping'}})


@pytest.mark.parametrize('role,message,reason', [
    ('admin', 'Tại sao số đơn đang giao tháng 11/2026 giảm?', 'bộ lọc đơn hàng'),
    ('staff', 'Tại sao số liệu doanh thu tháng 11/2026 giảm?', 'Staff'),
])
def test_explanation_cannot_hide_new_metric_or_causal_modifier(role, message, reason):
    row = context('inventory')
    row['last_result'] = {'intent': 'inventory_statistics', 'answer': 'OLD', 'data': {'total_products': 3}}
    tool = Mock()
    result = business_turn(message, row, tool, role=role)
    assert_acceptance(result, {'intent': 'unsupported', 'status': 'clarification_required',
                              'data_required': False, 'reason': reason})
    tool.assert_not_called()


def test_oracle_detects_wrong_refusal_reason_in_historical_captures():
    root = Path(__file__).resolve().parents[2]
    contracts = captured_contracts()
    out = root / '.local-tmp/live-phase3-5'
    paths = [out / ('admin-' + group + '.json') for group in ('first', 'analytics', 'multi', 'periods', 'guards')]
    paths += sorted(out.glob('staff-*-accepted.json'))
    if not all(p.exists() for p in paths) or len(paths) != 9:
        pytest.skip('Captured live artifacts are local, not bundled with source')
    seen, rejected = set(), set()
    for path in paths:
        for row in json.loads(path.read_text(encoding='utf-8')):
            key = row['name'].removeprefix('accepted-').split('-')[0]
            try:
                assert_acceptance(row['response']['body'], contracts[key])
            except AssertionError:
                rejected.add(key)
            seen.add(key)
    assert seen == set(contracts)
    # These archived write refusals gave period/filter errors. Retain their
    # evidence as failures; the current-source replay below must pass unchanged.
    assert rejected == {'a25', 's25'}


@pytest.mark.parametrize('role,prefix,groups,suffix', [
    ('admin', 'admin', ('first', 'analytics', 'multi', 'periods', 'guards'), ''),
    ('staff', 'staff', ('first', 'inventory', 'orders', 'escape'), '-accepted'),
])
def test_captured_queries_replayed_through_current_coordinator(role, prefix, groups, suffix):
    out = Path(__file__).resolve().parents[2] / '.local-tmp/live-phase3-5'
    paths = [out / f'{prefix}-{group}{suffix}.json' for group in groups]
    if not all(p.exists() for p in paths):
        pytest.skip('Local audit utterances are not bundled with source')
    row, seen, contracts = {}, set(), captured_contracts()
    for path in paths:
        for case in json.loads(path.read_text(encoding='utf-8')):
            key = case['name'].removeprefix('accepted-').split('-')[0]
            result = business_turn(case['query'], row, fixture_tool, role=role)
            assert_acceptance(result, contracts[key])
            seen.add(key)
    assert len(seen) == 27


def test_supported_speech_acts_ground_on_real_read_tools_without_writes():
    from datetime import datetime
    from sqlalchemy import create_engine, insert, event
    from sqlalchemy.orm import Session
    from app.models import Product, Order
    from app.services.ai_inventory_chat import answer_inventory_question
    from app.services.ai_order_chat import answer_order_question
    from app.services.ai_order_tools import get_order_statistics
    from app.services.ai_order_time_tools import get_orders_by_period
    engine = create_engine('sqlite:///:memory:')
    Product.__table__.create(engine)
    Order.__table__.create(engine)
    try:
        with Session(engine) as db:
            for number, stock in enumerate((0, 2, 7), 1):
                db.execute(insert(Product).values(id=number, sku=f'FIX{number}', barcode=str(number),
                    name=f'Synthetic {number}', category_id=1, brand_id=1, material_id=1,
                    gemstone_id=1, collection_id=1, weight=1, sale_price=10,
                    wholesale_price=5, cost_price=1, stock=stock))
            for number, status in enumerate(('shipping', 'cancelled'), 1):
                db.execute(insert(Order).values(id=number, code=f'FIX{number}', user_id=1,
                    recipient_name='Synthetic', phone='Synthetic', address='Synthetic',
                    status=status, payment_status='unpaid', payment_method='cod', stock_restored=status == 'cancelled',
                    subtotal_vnd=100, shipping_vnd=0, discount_vnd=0, total_vnd=100,
                    created_at=datetime(2026, 10, 15)))
            db.commit()
            statements = []
            event.listen(engine, 'before_cursor_execute', lambda conn, cursor, statement, params, ctx, many: statements.append(statement))
            def tool(command):
                return answer_inventory_question(db, command) or answer_order_question(
                    command, db, statistics=get_order_statistics, period=get_orders_by_period)
            row = {}
            stock = business_turn('Vui lòng liệt kê những sản phẩm sắp hết hàng', row, tool, role='admin')
            assert_acceptance(stock, {'intent': 'inventory_statistics', 'fields': {
                'data.total_products': 3, 'data.low_stock_products': 1, 'data.out_of_stock_products': 1}})
            assert [(p['product_id'], p['stock']) for p in stock['data']['products']] == [(2, 2)]
            orders = business_turn('Có đơn đang giao không?', row, tool, role='admin')
            assert_acceptance(orders, {'intent': 'order_statistics', 'fields': {'data.value': 1, 'evidence.status': 'shipping'}})
            followup = business_turn('tháng 10/2026 thì sao?', row, tool, role='admin')
            assert_acceptance(followup, {'intent': 'orders_by_period', 'fields': {
                'data.total_orders': 1, 'data.start_date': '2026-10-01', 'data.end_date': '2026-10-31',
                'data.status': 'shipping', 'evidence.transition': 'FOLLOWUP'}})
            assert statements and all(sql.lstrip().upper().startswith('SELECT') for sql in statements)
    finally:
        engine.dispose()


def test_product_task_switch_clears_incompatible_inventory_and_report_slots():
    for seed in ('tồn kho sắp hết hàng ngưỡng 3', 'doanh thu tháng 10/2026'):
        previous = parse_plan(seed, BusinessState(), 'admin')[0]
        state, commands = parse_plan('Tra SKU SP000002', previous, 'admin')
        assert state.metrics == ('product',) and state.transition == 'NEW_TASK'
        assert state.period is None and state.metric_periods == {}
        assert state.inventory_mode is None and state.threshold == 5 and state.limit == 20
        assert len(commands) == 1 and 'sp000002' in commands[0]


def test_purchase_metric_vocabulary_uses_the_same_coverage_grammar():
    state, commands = parse_plan('Phân tích chỉ số mua hàng tháng 8/2026', BusinessState(), 'admin')
    assert state.metrics == ('purchase_behavior',)
    assert commands == ['hanh vi mua hang tu 2026-08-01 den 2026-08-31']


@pytest.mark.parametrize('seed', CONTEXTS)
def test_reset_clears_task_before_period_only_followup(seed):
    row, tool = context(seed), Mock()
    assert_acceptance(business_turn('Xin chào, bắt đầu lại nhé', row, tool, role='admin'),
                      {'intent': 'conversation_reset', 'data_required': False})
    assert row['business_state'].transition == 'RESET'
    assert not row['business_state'].metrics and not row['business_state'].metric_periods
    result = business_turn('tháng 10/2026 thì sao?', row, tool, role='admin')
    assert_acceptance(result, {'intent': 'unsupported', 'status': 'clarification_required',
                              'data_required': False, 'reason': 'yêu cầu mới'})
    tool.assert_not_called()
