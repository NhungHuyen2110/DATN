"""Phase 1 scope regression: mocks for routes; real SQLite memory for tools."""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import get_db
from app.models import Order
from app.routers.auth import get_current_user
from app.services.ai_staff_intent import understand_staff_question
from app.services.ai_admin_revenue_intent import understand_revenue_question
from app.services.ai_order_time_intent import understand_time_order_question
from app.services.ai_order_time_tools import get_orders_by_period
from app.services.ai_order_tools import get_order_statistics
from app.services.ai_order_chat import answer_order_question
from app.services import ai_admin_orchestrator, ai_staff_orchestrator

staff_router = importlib.import_module('app.routers.ai_staff')
admin_router = importlib.import_module('app.routers.ai_admin')

STATES = [('đang giao', 'shipping'), ('đã hủy', 'cancelled'), ('đang đóng gói', 'packing'),
          ('đang được vận chuyển', 'shipping'), ('bị hủy', 'cancelled'),
          ('đang chuẩn bị hàng', 'packing'), ('giao thành công', 'delivered')]


@pytest.mark.parametrize('phrase,status', STATES)
def test_status_paraphrases_are_not_total(phrase, status):
    result = understand_staff_question(f'Cho tôi biết số lượng đơn {phrase}')
    assert result['field'] == status + '_orders'
    period = understand_time_order_question(f'Bao nhiêu đơn {phrase} tháng 10/2026?')
    assert period['status'] == status


@pytest.mark.parametrize('query', [
    'Có bao nhiêu đơn chưa giao?', 'Đếm đơn bị trả lại',
    'Số đơn đang giao và đã thanh toán', 'Đơn không bị hủy',
    'Có bao nhiêu đơn ở Hà Nội?', 'Đơn đã giao trên 5 triệu',
    'Số đơn theo nhân viên', 'Đơn đã giao và đã hủy',
    'Số đơn tháng 10/2026 theo ngày', 'Số đơn từ 01/09/2026 đến 30/09/2026 theo tháng',
])
def test_unknown_or_combined_order_constraints_abstain_without_data(query):
    statistics, period = Mock(), Mock()
    response = answer_order_question(query, object(), statistics=statistics, period=period)
    assert response['intent'] in {'unsupported', 'invalid'}
    assert response['data'] is None
    statistics.assert_not_called()
    period.assert_not_called()


@pytest.mark.parametrize('query,field', [
    ('Đếm đơn đã thanh toán', 'paid_orders'),
    ('Số đơn chưa thanh toán', 'unpaid_orders'),
    ('Bao nhiêu đơn đã hoàn tiền?', 'refunded_orders'),
])
def test_payment_status_is_separate(query, field):
    result = understand_staff_question(query)
    assert result['status_kind'] == 'payment'
    assert result['field'] == field
    scoped = understand_time_order_question(query + ' tháng 10/2026')
    assert scoped['intent'] == 'unsupported'


@pytest.mark.parametrize('query,start,end,group', [
    ('Doanh thu quý 3/2026', date(2026, 7, 1), date(2026, 9, 30), 'month'),
    ('Tổng tiền bán hàng quý 1 năm 2024', date(2024, 1, 1), date(2024, 3, 31), 'month'),
    ('Doanh thu năm 2025', date(2025, 1, 1), date(2025, 12, 31), 'month'),
    ('Doanh thu ngày 29/02/2024', date(2024, 2, 29), date(2024, 2, 29), 'day'),
    ('Doanh thu từ ngày 01/09/2026 đến ngày 15/10/2026', date(2026, 9, 1), date(2026, 10, 15), 'day'),
    ('Doanh thu từ 2026-08-15 tới 2026-09-02 theo tháng', date(2026, 8, 15), date(2026, 9, 2), 'month'),
    ('Doanh thu tháng 9 năm 2026', date(2026, 9, 1), date(2026, 9, 30), 'month'),
])
def test_revenue_periods(query, start, end, group):
    result = understand_revenue_question(query)
    assert result['intent'] == 'revenue_statistics'
    assert (result['start_date'], result['end_date'], result['group_by']) == (start, end, group)
    multi = ai_admin_orchestrator.resolve_period(query + ' và tồn kho')
    assert (multi['start_date'], multi['end_date'], multi['group_by']) == (start, end, group)


@pytest.mark.parametrize('query,start,end', [
    ('Doanh thu quý 2/2025', date(2025, 4, 1), date(2025, 6, 30)),
    ('Doanh thu năm 2024', date(2024, 1, 1), date(2024, 12, 31)),
    ('Doanh thu từ 01/08/2026 đến 20/09/2026', date(2026, 8, 1), date(2026, 9, 20)),
])
def test_admin_dispatches_full_period_to_existing_revenue_tool(query, start, end, monkeypatch):
    tool = Mock(return_value={'confirmed_payment_amount_vnd': '123456.25',
                              'confirmed_payment_order_count': 2})
    monkeypatch.setattr(admin_router, 'get_revenue_statistics', tool)
    result = admin_router._admin_ai_tools(admin_router.AdminChatRequest(message=query), object(), object())
    assert result['intent'] == 'revenue_statistics'
    assert result['data']['confirmed_payment_amount_vnd'] == '123456.25'
    assert tool.call_args.kwargs['start_date'] == start
    assert tool.call_args.kwargs['end_date'] == end


@pytest.mark.parametrize('query', [
    'Doanh thu quý III/2026', 'Doanh thu quý 7/2026', 'Doanh thu năm 9999',
    'Doanh thu ngày 31/02/2026', 'Doanh thu từ 30/10/2026 đến 01/10/2026',
    'So sánh doanh thu tháng 9 và tháng 10/2026', 'Doanh thu quý 1/2026 so với quý 2/2026',
    'Doanh thu năm 2025 và năm 2026', 'Doanh thu tuần trước',
    'Doanh thu từ tháng 7 đến tháng 9/2026', 'Doanh thu tháng 10/2026 theo khách hàng',
    'Doanh thu tháng 10/2026 ở chi nhánh Hà Nội', 'Doanh thu năm tài chính 2026',
    'Doanh thu đơn đã hủy tháng 10/2026', 'Doanh thu đơn chưa thanh toán tháng 10/2026',
])
def test_revenue_does_not_drop_unsupported_scope(query, monkeypatch):
    revenue = Mock()
    monkeypatch.setattr(admin_router, 'get_revenue_statistics', revenue)
    response = admin_router._admin_ai_tools(admin_router.AdminChatRequest(message=query), object(), object())
    assert response['intent'] in {'unsupported', 'invalid'}
    assert response['data'] is None
    revenue.assert_not_called()


@pytest.mark.parametrize('role,path', [('staff', '/staff/ai/chat'), ('admin', '/admin/ai/chat')])
@pytest.mark.parametrize('phrase,status', STATES[:3])
def test_role_routes_use_status_counts(role, path, phrase, status, monkeypatch):
    result = {'total_orders': 31, 'order_status': {'shipping': 7, 'cancelled': 3, 'packing': 4},
              'payment_status': {}, 'scope': 'all_time'}
    monkeypatch.setattr(staff_router, 'get_order_statistics', lambda db: result)
    monkeypatch.setattr('app.services.ai_order_tools.get_order_statistics', lambda db: result)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=923, role=SimpleNamespace(name=role))
    app.dependency_overrides[get_db] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.post(path, json={'message': f'Có bao nhiêu đơn hàng {phrase}?'})
        assert response.status_code == 200
        assert response.json()['field'] == status + '_orders'
        assert response.json()['data']['value'] == result['order_status'][status]
    finally:
        app.dependency_overrides.clear()


def test_admin_single_order_count_reuses_tool(monkeypatch):
    tool = Mock(return_value={'total_orders': 31, 'scope': 'all_time'})
    monkeypatch.setattr('app.services.ai_order_tools.get_order_statistics', tool)
    response = admin_router._admin_ai_tools(admin_router.AdminChatRequest(message='Có bao nhiêu đơn hàng?'), object(), object())
    assert response['intent'] == 'order_statistics'
    assert response['data'] == {'value': 31, 'scope': 'all_time'}
    tool.assert_called_once()


@pytest.mark.parametrize('query', [
    'Top 5 sản phẩm bán chạy tháng 10/2026 theo ngày',
    'Doanh thu và sản phẩm bán chạy quý 3/2026 theo tháng',
])
def test_top_selling_grouping_abstains_before_tools(query, monkeypatch):
    revenue, top = Mock(), Mock()
    for module in (admin_router, ai_admin_orchestrator):
        monkeypatch.setattr(module, 'get_revenue_statistics', revenue)
        monkeypatch.setattr(module, 'get_top_selling_products', top)
    result = admin_router._admin_ai_tools(admin_router.AdminChatRequest(message=query), object(), object())
    assert result['intent'] == 'unsupported'
    assert result['data'] is None
    revenue.assert_not_called()
    top.assert_not_called()


@pytest.mark.parametrize('orchestrator', [ai_admin_orchestrator.answer_admin_multi_intent,
                                         ai_staff_orchestrator.answer_staff_multi_intent])
def test_multi_order_scope_is_validated_before_tools(orchestrator, monkeypatch):
    order, inventory = Mock(), Mock()
    module = ai_admin_orchestrator if orchestrator is ai_admin_orchestrator.answer_admin_multi_intent else ai_staff_orchestrator
    monkeypatch.setattr(module, 'get_order_statistics', order)
    monkeypatch.setattr(module, 'get_inventory_statistics', inventory)
    for query in ['Đơn bị trả lại và tồn kho', 'Đơn đã giao và đã hủy và tồn kho',
                  'Đơn đang giao tháng 10/2026 và tồn kho']:
        response = orchestrator(object(), query)
        assert response['intent'] == 'unsupported'
    order.assert_not_called()
    inventory.assert_not_called()


def test_real_read_tools_on_isolated_memory_database():
    engine = create_engine('sqlite:///:memory:')
    Order.__table__.create(engine)
    try:
        with Session(engine) as db:
            for number, status in enumerate(('pending', 'confirmed', 'packing', 'shipping', 'delivered', 'cancelled'), 1):
                db.execute(insert(Order).values(id=number, code=f'TEST-{number}', user_id=1,
                    recipient_name='Synthetic', phone='0900000000', address='Synthetic',
                    status=status, payment_status='unpaid', payment_method='cod',
                    stock_restored=status == 'cancelled', subtotal_vnd=100, shipping_vnd=0,
                    discount_vnd=0, total_vnd=100, created_at=datetime(2026, 10, 15, tzinfo=timezone.utc)))
            db.commit()  # SQLite :memory: only, enforced by the safe runner.
            summary = get_order_statistics(db)
            assert summary['total_orders'] == 6
            for status in ('packing', 'shipping', 'cancelled'):
                assert summary['order_status'][status] == 1
                response = get_orders_by_period(db, date(2026, 10, 1), date(2026, 10, 31), status)
                assert response['total_orders'] == 1
                assert response['status'] == status
            assert get_orders_by_period(db, date(2026, 9, 1), date(2026, 9, 30), 'shipping')['total_orders'] == 0
    finally:
        engine.dispose()


# Phase 4–5: reuse the existing regression module and SQLAlchemy fixtures.
from app.services.ai_business_dialogue import BusinessState, Operation, business_turn, parse_plan, Clarify
from app.services.ai_inventory_tools import get_inventory_statistics
from app.models import Product
from shared.conversation import ConversationStore, converse


def test_staff_state_retains_period_status_and_clear_is_explicit():
    state, commands = parse_plan('Đơn đang giao tháng 10/2026', BusinessState(), 'staff')
    assert state.status == 'shipping'
    assert state.period.start == date(2026, 10, 1)
    state, commands = parse_plan('tháng 9/2026 thì sao?', state, 'staff')
    assert state.status == 'shipping' and state.period.end == date(2026, 9, 30)
    state, commands = parse_plan('chỉ đơn đã hủy', state, 'staff')
    assert state.status == 'cancelled' and '2026-09-30' in commands[0]
    with pytest.raises(Clarify):
        parse_plan('đơn đã thanh toán', state, 'staff')
    state, commands = parse_plan('bỏ lọc trạng thái', state, 'staff')
    assert state.status is None and state.operations['status'] == Operation.CLEAR
    state, commands = parse_plan('toàn bộ lịch sử', state, 'staff')
    assert state.period is None and commands == ['don hang ']


def test_staff_inventory_followup_threshold_and_task_switch():
    state, _ = parse_plan('tồn kho ngưỡng 8', BusinessState(), 'staff')
    state, commands = parse_plan('còn hàng sắp hết?', state, 'staff')
    assert commands == ['sap het hang nguong 8 gioi han 20']
    state, commands = parse_plan('ngưỡng 2', state, 'staff')
    assert state.threshold == 2
    state, commands = parse_plan('đơn đang giao', state, 'staff')
    assert state.inventory_mode is None and state.threshold == 5
    assert commands == ['don hang shipping']
    assert state.operations['inventory_mode'] == Operation.CLEAR
    assert state.operations['status'] == Operation.SET


@pytest.mark.parametrize('message', ['Tồn kho thì sao?', 'Giá thì sao?', 'Giá bao nhiêu nhé?', 'Còn hàng không?'])
def test_staff_product_followup_discourse_keeps_verified_query(message):
    state, _ = parse_plan('Tra SKU SP000002', BusinessState(), 'staff')
    updated, commands = parse_plan(message, state, 'staff')
    assert commands == [state.product]
    assert updated.product == state.product
    assert updated.metrics == ('product',)
    assert updated.operations['product'] == Operation.KEEP


@pytest.mark.parametrize('message', ['Hàng hết', 'Còn hàng hết', 'Hết hàng'])
def test_staff_out_of_stock_followup_replaces_low_stock_mode(message):
    state, _ = parse_plan('Tồn kho sắp hết hàng ngưỡng 3', BusinessState(), 'staff')
    updated, commands = parse_plan(message, state, 'staff')
    assert updated.inventory_mode == 'out_of_stock'
    assert updated.threshold == 3
    assert commands == ['het hang nguong 3 gioi han 20']


@pytest.mark.parametrize('message', ['đơn không bị hủy', 'đơn đang giao và đã thanh toán',
    'tồn kho tại Hà Nội', 'tồn kho tháng 9', 'tồn kho ngưỡng -1',
    'tồn kho ngưỡng 1001', 'đơn chưa giao', 'đơn ngày 31/02/2026',
    'đơn đang giao và tồn kho tại Hà Nội', 'tồn kho và doanh thu'])
def test_staff_unknown_filters_never_call_tools(message):
    tool = Mock()
    row = {}
    result = business_turn(message, row, tool, role='staff')
    assert result['data'] is None and result['intent'] == 'unsupported'
    tool.assert_not_called()


def test_shared_clarification_escape_timeout_and_atomic_state():
    row = {}
    tool = Mock(return_value={'intent': 'order_statistics', 'data': {'value': 7}, 'answer': '7 đơn'})
    business_turn('đơn đang giao', row, tool, role='staff')
    state = row['business_state']
    business_turn('đơn ở Hà Nội', row, tool, role='staff')
    assert row['business_state'].status == 'shipping' and state.pending_clarification
    assert business_turn('xin chào', row, tool, role='staff')['intent'] == 'greeting'
    assert row['business_state'].pending_clarification is None
    tool.side_effect = TimeoutError('not exposed')
    result = business_turn('đơn đã hủy', row, tool, role='staff')
    assert result['intent'] == 'source_error' and 'not exposed' not in result['answer']
    assert row['business_state'].status == 'shipping'
    assert business_turn('bỏ qua', row, tool, role='staff')['intent'] == 'conversation_reset'
    assert not row['business_state'].metrics


def test_business_conversations_do_not_share_role_user_or_session(monkeypatch):
    store = ConversationStore()
    monkeypatch.setattr('shared.conversation.STORE', store)
    tool = Mock(return_value={'intent': 'order_statistics', 'answer': '1 đơn', 'data': {'value': 1}})
    adapter = lambda message, row, fn: business_turn(message, row, fn, role='staff')
    first = converse('đơn đang giao tháng 9/2026', None, ('staff', 1), tool, dialogue=adapter)
    token = first['conversation_id']
    for scope in [('staff', 2), ('admin', 1)]:
        other = converse('tháng 10 thì sao', token, scope, tool, dialogue=adapter)
        assert other['conversation_id'] != token and other['data'] is None
    other = converse('tháng 10 thì sao', None, ('staff', 1), tool, dialogue=adapter)
    assert other['conversation_id'] != token and other['data'] is None


def test_inventory_filters_before_limit_with_independent_counts():
    from sqlalchemy import insert
    engine = create_engine('sqlite:///:memory:')
    Product.__table__.create(engine)
    try:
        with Session(engine) as db:
            stocks = [0] * 25 + [1, 3, 5, 6, 12]
            for i, stock in enumerate(stocks, 1):
                db.execute(insert(Product).values(id=i, sku=f'SP{i:06}', barcode=str(i), name=f'Fixture {i}',
                    category_id=1, brand_id=1, material_id=1, gemstone_id=1, collection_id=1,
                    weight=1, sale_price=10, wholesale_price=5, cost_price=1, stock=stock))
            db.commit()
            result = get_inventory_statistics(db, threshold=5, limit=2, mode='low_stock')
            assert (result['total_products'], result['out_of_stock_products'], result['low_stock_products']) == (30, 25, 3)
            assert [p['stock'] for p in result['products']] == [1, 3]
            assert [p['product_id'] for p in result['products']] == [26, 27]
            assert get_inventory_statistics(db, threshold=0, mode='low_stock')['products'] == []
            assert len(get_inventory_statistics(db, mode='in_stock')['products']) == 5
            assert len(get_inventory_statistics(db, mode='out_of_stock')['products']) == 20
    finally:
        engine.dispose()


def test_product_parser_covers_unaccented_name_arbitrary_sku_and_attributes():
    from app.services.ai_product_lookup import extract_product_query
    assert extract_product_query('Tìm sản phẩm Nhẫn Golden')['value'] == 'nhan golden'
    assert extract_product_query('nhan Golden con hang khong?')['value'] == 'nhan golden'
    assert extract_product_query('tra cuu SKU CUSTOM-123')['value'] == 'CUSTOM-123'
    result = extract_product_query('tim san pham chat lieu bac va loai nhan')
    assert result['attributes'] == {'material': 'bac', 'category': 'nhan'}
    assert extract_product_query('SP000001 va doanh thu')['type'] == 'unsupported'
    assert extract_product_query('tim san pham chat lieu bac va khong co da')['type'] == 'unsupported'


@pytest.mark.parametrize('message', ['xin chào', 'ban lam duoc gi', 'thời tiết hôm nay',
    'lợi nhuận tháng này', 'cập nhật tồn kho thành 10', 'xóa đơn hàng', 'dự báo doanh thu'])
def test_staff_smalltalk_unknown_and_write_requests_are_read_free(message):
    tool = Mock()
    result = business_turn(message, {}, tool, role='staff')
    assert result['data'] is None
    tool.assert_not_called()


def test_admin_followup_metric_switch_and_shared_period():
    state, _ = parse_plan('doanh thu quý 3/2026', BusinessState(), 'admin')
    state, commands = parse_plan('tháng 9 thì sao?', state, 'admin')
    assert state.period == __import__('app.services.ai_business_dialogue', fromlist=['Period']).Period(date(2026, 9, 1), date(2026, 9, 30), 'month')
    state, commands = parse_plan('top 5 sản phẩm', state, 'admin')
    assert state.metrics == ('top_selling_products',) and state.top_limit == 5
    assert '2026-09-01' in commands[0] and '2026-09-30' in commands[0]
    state, commands = parse_plan('doanh thu và đơn đang giao tháng 10/2026', state, 'admin')
    assert len(commands) == 2 and all('2026-10-01' in c and '2026-10-31' in c for c in commands)
    assert state.status == 'shipping'
    state, commands = parse_plan('tháng 9 thì sao?', state, 'admin')
    assert len(commands) == 2 and all('2026-09-30' in c for c in commands)
    assert state.status == 'shipping'


@pytest.mark.parametrize('query', ['doanh thu theo khách hàng tháng 9', 'doanh thu đơn đã hủy',
    'dự báo doanh thu', 'doanh thu và lợi nhuận', 'hành vi mua hàng tại Hà Nội',
    'hành vi mua hàng năm 2020 và năm 2021', 'top 5 sản phẩm theo ngày',
    'doanh thu và tồn kho cuối tháng 9', 'doanh thu tháng 9 và tồn kho tháng 10',
    'doanh thu và đơn đã thanh toán tháng 9', 'doanh thu so với tháng trước',
    'so sánh tồn kho tháng 9 và tháng 10', 'doanh thu tháng 9 so với tháng 8 ở Hà Nội'])
def test_admin_ambiguous_filters_no_partial_tool_calls(query):
    tool = Mock()
    result = business_turn(query, {}, tool, role='admin')
    assert result['intent'] == 'unsupported' and result['data'] is None
    tool.assert_not_called()


@pytest.mark.parametrize('baseline,current,delta,pct', [
    ('0', '0', '0', None), ('0', '12.30', '12.30', None),
    ('10.00', '12.30', '2.30', '23.00'), ('10', '5', '-5', '-50.00')])
def test_admin_comparison_decimal_and_zero_baseline(baseline, current, delta, pct):
    tool = Mock(side_effect=[
        {'intent': 'revenue_statistics', 'answer': 'current', 'data': {'confirmed_payment_amount_vnd': current}},
        {'intent': 'revenue_statistics', 'answer': 'baseline', 'data': {'confirmed_payment_amount_vnd': baseline}}])
    result = business_turn('doanh thu tháng 9/2026 so với tháng 8/2026', {}, tool, role='admin')
    assert result['intent'] == 'period_comparison'
    assert result['data']['changes']['revenue']['difference'] == delta
    assert result['data']['changes']['revenue']['percentage_change'] == pct
    assert '2026-09-01' in tool.call_args_list[0].args[0]
    assert '2026-08-31' in tool.call_args_list[1].args[0]


@pytest.mark.parametrize('query,followup,start,end', [
    ('doanh thu tháng 1/2026', 'so với tháng trước?', date(2025, 12, 1), date(2025, 12, 31)),
    ('doanh thu quý 1/2026', 'so với quý trước?', date(2025, 10, 1), date(2025, 12, 31)),
    ('doanh thu năm 2024', 'so với năm trước?', date(2023, 1, 1), date(2023, 12, 31)),
    ('đơn ngày 01/03/2024', 'so với ngày trước?', date(2024, 2, 29), date(2024, 2, 29))])
def test_comparison_followup_anchors_to_selected_period(query, followup, start, end):
    state, _ = parse_plan(query, BusinessState(), 'admin')
    state, commands = parse_plan(followup, state, 'admin')
    assert (state.comparison.start, state.comparison.end) == (start, end)
    assert len(commands) == 2


def test_multi_tool_failure_does_not_publish_partial_results_or_mutate_scope():
    previous, _ = parse_plan('doanh thu tháng 9/2026', BusinessState(), 'admin')
    row = {'business_state': previous}
    tool = Mock(side_effect=[{'intent': 'revenue_statistics', 'data': {'amount': 'SECRET_PARTIAL'}, 'answer': 'SECRET_PARTIAL'}, TimeoutError()])
    result = business_turn('doanh thu và đơn tháng 10/2026', row, tool, role='admin')
    assert result['intent'] == 'source_error' and result['data'] is None
    assert 'SECRET_PARTIAL' not in str(result)
    assert row['business_state'].period.start == date(2026, 9, 1)


def test_business_routes_flags_off_have_zero_provider_calls(monkeypatch):
    monkeypatch.setenv('STAFF_AI_LLM_ENABLED', 'false')
    monkeypatch.setenv('ADMIN_AI_LLM_ENABLED', 'false')
    monkeypatch.setenv('LUMIERE_DIALOGUE_LLM_ENABLED', 'false')
    staff_provider, admin_provider, natural_provider = Mock(), Mock(), Mock()
    monkeypatch.setattr(staff_router, 'understand_staff_question_with_llm', staff_provider)
    monkeypatch.setattr(admin_router, 'understand_admin_question_with_llm', admin_provider)
    monkeypatch.setattr('shared.local_dialogue.answer_general', natural_provider)
    monkeypatch.setattr(staff_router, 'get_order_statistics', lambda db: {'total_orders': 0, 'scope': 'all_time'})
    monkeypatch.setattr('app.services.ai_order_tools.get_order_statistics', lambda db: {'total_orders': 0, 'scope': 'all_time'})
    app.dependency_overrides[get_db] = lambda: object()
    try:
        with TestClient(app) as client:
            for role, path in [('staff', '/staff/ai/chat'), ('admin', '/admin/ai/chat')]:
                app.dependency_overrides[get_current_user] = lambda role=role: SimpleNamespace(id=980, role=SimpleNamespace(name=role))
                for message in ['xin chào', 'tình hình công việc thế nào', 'tổng đơn hàng', 'tại sao?']:
                    assert client.post(path, json={'message': message}).status_code == 200
        for provider in [staff_provider, admin_provider, natural_provider]:
            provider.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize('message', ['chỉ đơn đang giao', 'chi don dang giao',
    'không phải đơn đã thanh toán mà đơn đang giao'])
def test_explicit_replacement_clears_incompatible_payment_slot(message):
    state, _ = parse_plan('đơn đã thanh toán', BusinessState(), 'staff')
    state, commands = parse_plan(message, state, 'staff')
    assert state.status == 'shipping' and state.payment is None
    assert commands == ['don hang shipping']


def test_business_comparison_uses_same_grouping_and_invalid_source_is_not_zero():
    state, commands = parse_plan('doanh thu tháng 9/2026 so với tháng 8/2026', BusinessState(), 'admin')
    assert all(command.endswith('theo thang') for command in commands)
    tool = Mock(return_value={'intent': 'revenue_statistics', 'data': {'confirmed_payment_amount_vnd': 'NaN'}, 'answer': 'bad'})
    row = {}
    response = business_turn('doanh thu tháng 9/2026 so với tháng 8/2026', row, tool, role='admin')
    assert response['intent'] == 'source_error' and not row.get('business_state')


def test_top_limit_inventory_limit_independent_and_threshold_boundaries():
    state, commands = parse_plan('top 3 sản phẩm tháng 9/2026 và tồn kho giới hạn 40 ngưỡng 8', BusinessState(), 'admin')
    assert state.top_limit == 3 and state.limit == 40
    state, commands = parse_plan('tháng 10/2026 thì sao', state, 'admin')
    assert commands[0].startswith('top 3 san pham') and commands[1] == 'ton kho nguong 8 gioi han 40'
    from app.services.ai_inventory_chat import inventory_scope
    assert inventory_scope('sắp hết hàng dưới 5')['threshold'] == 4
    assert inventory_scope('sắp hết hàng không quá 5')['threshold'] == 5
    assert inventory_scope('còn hàng dưới 5')['mode'] == 'low_stock'
    assert inventory_scope('hết hàng và sắp hết hàng')['intent'] == 'unsupported'
    assert inventory_scope('hết hàng và còn hàng')['intent'] == 'unsupported'
    state, _ = parse_plan('sắp hết hàng', BusinessState(), 'staff')
    state, commands = parse_plan('bỏ lọc trạng thái', state, 'staff')
    assert state.inventory_mode is None and commands[0].startswith('ton kho ')
    with pytest.raises(Clarify):
        parse_plan('tồn kho toàn bộ lịch sử', BusinessState(), 'staff')


def test_llm_cannot_override_known_top_selling_period_or_limit(monkeypatch):
    monkeypatch.setenv('ADMIN_AI_LLM_ENABLED', 'true')  # Test process only; mocked provider.
    monkeypatch.setattr(admin_router, 'understand_admin_question_with_llm', Mock(return_value={
        'intent': 'top_selling_products', 'start_date': date(2025, 1, 1),
        'end_date': date(2025, 12, 31), 'limit': 20}))
    tool = Mock(return_value={'items': []})
    monkeypatch.setattr(admin_router, 'get_top_selling_products', tool)
    admin_router._admin_ai_tools(admin_router.AdminChatRequest(message='top 3 san pham ban chay thang 9/2026'), object(), object())
    assert tool.call_args.kwargs == {'db': tool.call_args.kwargs['db'],
        'start_date': date(2026, 9, 1), 'end_date': date(2026, 9, 30), 'limit': 3}
