"""Reporting fixtures are SQLite memory only; no production database access."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import sqlalchemy as sa
from sqlalchemy.orm import Session

import test_payments_api as payments_tests
from test_auth_profile import request


class DashboardTests(payments_tests.PaymentTests):
    def report(self, path="/admin/dashboard", cookie="admin-token", **params):
        async def wrapped(scope, receive, send):
            scope["query_string"] = urlencode(params).encode()
            await self.app(scope, receive, send)
        return asyncio.run(request(wrapped, "GET", path, cookie=
            None if cookie is None else "lumiere_session=" + cookie))

    def revenue(self, **params):
        return self.report("/admin/reports/revenue", **{
            "start_date": "2026-01-01", "end_date": "2026-01-31", **params})

    def seed_order(self, status="delivered", payment_status="paid", amount="12.34", payment=True,
                   provider="cod", tx_status="succeeded", verified="2026-01-01T00:00:00+00:00",
                   review=False, tx_amount=None, method="cod"):
        with Session(self.engine) as db, db.begin():
            order = self.Order(code="REPORT-" + str(db.scalar(sa.select(sa.func.count()).select_from(self.Order))),
                user_id=1, recipient_name="Test", phone="0912345678", address="Test address",
                status=status, payment_status=payment_status, payment_method=method,
                stock_restored=status == "cancelled", subtotal_vnd=Decimal(amount),
                shipping_vnd=Decimal("0.00"), discount_vnd=Decimal("0.00"), total_vnd=Decimal(amount))
            db.add(order)
            db.flush()
            ident = order.id
            if payment:
                db.add(self.Payment(order_id=ident, provider=provider, reference=f"REPORT-PAY-{ident}",
                    amount_vnd=Decimal(tx_amount or amount), status=tx_status, review_required=review,
                    verified_at=None if verified is None else datetime.fromisoformat(verified)))
            return ident

    def test_dashboard_empty_and_product_counts(self):
        with Session(self.engine) as db, db.begin():
            db.execute(sa.delete(self.Product))
        status, body, _ = self.report()
        self.assertEqual(status, 200)
        self.assertEqual(body["total_orders"], 0)
        self.assertEqual(body["total_products"], 0)
        self.assertEqual(body["out_of_stock_products"], 0)
        self.assertEqual(body["confirmed_payment_amount_vnd"], "0.00")
        self.assertEqual(body["reconciliation_order_value_vnd"], "0.00")
        self.assertTrue(all(value == 0 for value in body["orders_by_status"].values()))
        self.assertTrue(all(value == 0 for value in body["orders_by_payment_status"].values()))
        report = self.revenue()[1]
        self.assertEqual(report["confirmed_payment_amount_vnd"], "0.00")
        self.assertEqual(len(report["items"]), 31)
        self.assertTrue(all(item["confirmed_payment_order_count"] == 0 for item in report["items"]))

    def test_dashboard_permissions_and_inactive_admin(self):
        for path, params in (("/admin/dashboard", {}), ("/admin/reports/revenue",
                {"start_date": "2026-01-01", "end_date": "2026-01-02"})):
            for cookie, code in ((None, 401), ("test-token", 403), ("staff-token", 403), ("admin-token", 200)):
                self.assertEqual(self.report(path, cookie=cookie, **params)[0], code)
        with Session(self.engine) as db, db.begin():
            db.get(self.User, 3).is_active = False
        self.assertEqual(self.report()[0], 401)
        self.assertEqual(self.revenue()[0], 401)

    def test_dashboard_status_counts_and_current_stock(self):
        statuses = ("pending", "confirmed", "packing", "shipping", "delivered", "cancelled")
        for index, status in enumerate(statuses):
            self.seed_order(status=status, payment_status=("unpaid", "paid", "refunded")[index % 3], payment=False)
        with Session(self.engine) as db, db.begin():
            db.get(self.Product, 1).stock = 0
        body = self.report()[1]
        self.assertEqual(body["total_orders"], 6)
        self.assertEqual(body["orders_by_status"], dict.fromkeys(statuses, 1))
        self.assertEqual(body["orders_by_payment_status"], {"unpaid": 2, "paid": 2, "refunded": 2})
        self.assertEqual((body["total_products"], body["out_of_stock_products"]), (2, 1))

    def test_dashboard_exclusions_and_reconciliation_reasons(self):
        self.seed_order(amount="10.10")
        self.seed_order(payment_status="unpaid", payment=False)
        self.seed_order(payment_status="unpaid", method="vnpay", provider="vnpay", tx_status="pending")
        self.seed_order(payment_status="unpaid", method="vnpay", provider="vnpay", tx_status="failed")
        self.seed_order(status="cancelled", amount="1.00")
        self.seed_order(payment_status="refunded")
        self.seed_order(review=True, amount="2.00")
        self.seed_order(tx_amount="99.00", amount="3.00")
        self.seed_order(verified=None, amount="4.00")
        self.seed_order(provider="vnpay", amount="5.00")
        self.seed_order(payment=False, amount="6.00")
        self.seed_order(payment_status="unpaid", amount="7.00")
        body = self.report()[1]
        self.assertEqual(body["confirmed_payment_amount_vnd"], "10.10")
        self.assertEqual(body["reconciliation_order_count"], 7)
        self.assertEqual(body["reconciliation_order_value_vnd"], "28.00")
        reasons = {item["reason"] for item in body["reconciliation_reasons"]}
        self.assertIn("transaction_amount_mismatch", reasons)
        self.assertIn("transaction_provider_mismatch", reasons)
        self.assertIn("successful_transaction_missing_verified_at", reasons)
        self.assertIn("paid_order_without_single_valid_transaction", reasons)
        self.assertEqual(self.revenue()[1]["confirmed_payment_amount_vnd"], "10.10")

    def test_dashboard_duplicate_values_and_multiple_order_items(self):
        ident = self.seed_order(amount="12.34")
        self.seed_order(amount="12.34")
        with Session(self.engine) as db, db.begin():
            for product_id in (1, 2):
                product = db.get(self.Product, product_id)
                db.add(self.OrderItem(order_id=ident, product_id=product.id, sku=product.sku,
                    product_name=product.name, quantity=1, unit_price_vnd=Decimal("6.17"), line_total_vnd=Decimal("6.17")))
        self.assertEqual(self.report()[1]["confirmed_payment_amount_vnd"], "24.68")
        body = self.revenue()[1]
        self.assertEqual(body["confirmed_payment_amount_vnd"], "24.68")
        self.assertEqual(body["confirmed_payment_order_count"], 2)

    def test_dashboard_multiple_successful_transactions_quarantined(self):
        ident = self.seed_order()
        with Session(self.engine) as db, db.begin():
            db.add(self.Payment(order_id=ident, provider="vnpay", reference="SECOND-SUCCESS",
                amount_vnd=Decimal("12.34"), status="succeeded", review_required=False,
                verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        body = self.report()[1]
        self.assertEqual(body["confirmed_payment_amount_vnd"], "0.00")
        self.assertEqual(body["reconciliation_order_count"], 1)
        self.assertIn("multiple_successful_transactions", {r["reason"] for r in body["reconciliation_reasons"]})
        self.assertEqual(self.revenue()[1]["confirmed_payment_order_count"], 0)
        # Current UNIQUE(order_id, provider) prevents two fully matching rows.
        # Exercise the defensive classifier for legacy data without weakening schema.
        from app.services.dashboard import classify
        row = dict(status="delivered", payment_status="paid", candidate_count=2,
            succeeded_count=2, review_count=0, amount_mismatch=0, provider_mismatch=0, missing_verified=0)
        eligible, reasons = classify(row)
        self.assertFalse(eligible)
        self.assertIn("multiple_valid_transactions", reasons)

    def test_revenue_vietnam_day_month_boundaries_and_zero_fill(self):
        for verified in ("2025-12-31T16:59:59+00:00", "2025-12-31T17:00:00+00:00",
                         "2026-01-31T16:59:59+00:00", "2026-01-31T17:00:00+00:00"):
            self.seed_order(amount="1.01", verified=verified)
        body = self.revenue()[1]
        self.assertEqual(body["confirmed_payment_amount_vnd"], "2.02")
        self.assertEqual(body["confirmed_payment_order_count"], 2)
        self.assertEqual(body["items"][0]["confirmed_payment_amount_vnd"], "1.01")
        self.assertEqual(body["items"][-1]["confirmed_payment_amount_vnd"], "1.01")
        self.assertEqual(body["items"][1]["confirmed_payment_amount_vnd"], "0.00")
        monthly = self.revenue(end_date="2026-03-10", group_by="month")[1]
        self.assertEqual([i["period_start"] for i in monthly["items"]], ["2026-01-01", "2026-02-01", "2026-03-01"])
        self.assertEqual([i["confirmed_payment_amount_vnd"] for i in monthly["items"]], ["2.02", "1.01", "0.00"])
        partial = self.revenue(start_date="2026-01-31", end_date="2026-02-01", group_by="month")[1]
        self.assertEqual(partial["confirmed_payment_amount_vnd"], "2.02")

    def test_revenue_invalid_filters(self):
        cases = ({"start_date": "bad"}, {"end_date": "2025-12-31"}, {"group_by": "year"},
            {"end_date": "9999-12-31"}, {"end_date": "2050-01-01"},
            {"start_date": "0001-01-01", "end_date": "0001-01-02"})
        for params in cases:
            self.assertEqual(self.revenue(**params)[0], 422, params)
        self.assertEqual(self.report("/admin/reports/revenue")[0], 422)

    def test_dashboard_callback_duplicate_and_browser_return(self):
        order, result = self.online_order()
        params = self.callback_params(result)
        self.callback(params, return_url=True)
        self.assertEqual(self.report()[1]["confirmed_payment_amount_vnd"], "0.00")
        self.callback(params)
        first = self.report()[1]
        self.callback(params)
        self.assertEqual(self.report()[1], first)
        self.assertEqual(Decimal(first["confirmed_payment_amount_vnd"]), Decimal(order["total_vnd"]))

    def test_dashboard_read_only_and_decimal_precision(self):
        self.seed_order(amount="0.10")
        self.seed_order(amount="0.20")
        statements = []
        def record(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        sa.event.listen(self.engine, "before_cursor_execute", record)
        try:
            body = self.report()[1]
            report = self.revenue()[1]
        finally:
            sa.event.remove(self.engine, "before_cursor_execute", record)
        self.assertEqual(body["confirmed_payment_amount_vnd"], "0.30")
        self.assertEqual(report["confirmed_payment_amount_vnd"], "0.30")
        self.assertTrue(all(sql.lstrip().upper().startswith("SELECT") for sql in statements))
        # Numeric(38,2) precision tested independently of SQLite's numeric storage.
        from app.schemas.dashboard import RevenueBucket
        value = Decimal("123456789012345678901234567890123456.78")
        bucket = RevenueBucket(period_start="2026-01-01", confirmed_payment_amount_vnd=value, confirmed_payment_order_count=1)
        self.assertEqual(json.loads(bucket.model_dump_json())["confirmed_payment_amount_vnd"], str(value))

    def test_dashboard_postgresql_query_compiles_offline(self):
        from app.services.dashboard import payment_summary_query
        from sqlalchemy.dialects import postgresql
        statement = str(payment_summary_query().compile(dialect=postgresql.dialect()))
        self.assertIn("GROUP BY payment_transactions.order_id", statement)
        self.assertIn("LEFT OUTER JOIN", statement)
        self.assertNotIn("order_items", statement)

    def test_phase45_business_metrics_replay_and_read_only(self):
        """Independent expected values, real services and auth; offline SQLite only."""
        from pathlib import Path
        from shared.conversation import ConversationStore
        jan = self.seed_order(amount='12.34', verified='2026-01-31T16:59:59+00:00')
        feb = self.seed_order(amount='5.66', verified='2026-01-31T17:00:00+00:00')
        cancelled = self.seed_order(status='cancelled', amount='90.00', verified='2026-01-15T00:00:00+00:00')
        unpaid = self.seed_order(status='shipping', payment_status='unpaid', amount='99.00', payment=False)
        mismatch = self.seed_order(amount='80.00', tx_amount='79.00')
        with Session(self.engine) as db, db.begin():
            for ident in [jan, feb, cancelled, unpaid, mismatch]:
                db.get(self.Order, ident).created_at = datetime(2026, 1, 15, tzinfo=timezone.utc)
            for ident, pid, quantity, value in [(jan, 1, 2, '12.34'), (feb, 2, 1, '5.66'), (cancelled, 1, 20, '90.00')]:
                p = db.get(self.Product, pid)
                db.add(self.OrderItem(order_id=ident, product_id=pid, sku=p.sku, product_name=p.name,
                       quantity=quantity, unit_price_vnd=Decimal(value) / quantity, line_total_vnd=Decimal(value)))
        replay = []
        statements = []
        def record(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        def turn(role, message, token=None, cookie=None):
            code, body, _ = self.call('POST', f'/{role}/ai/chat',
                {'message': message, 'conversation_id': token},
                cookie='lumiere_session=' + (cookie or role + '-token'))
            self.assertEqual(code, 200, body)
            replay.append({'role': role, 'message': message, 'response': {k: v for k, v in body.items() if k != 'conversation_id'}})
            return body
        sa.event.listen(self.engine, 'before_cursor_execute', record)
        try:
            with patch('shared.conversation.STORE', ConversationStore()), patch.dict(os.environ, {
                    'STAFF_AI_LLM_ENABLED': 'false', 'ADMIN_AI_LLM_ENABLED': 'false',
                    'LUMIERE_DIALOGUE_LLM_ENABLED': 'false'}):
                first = turn('staff', 'đơn đang giao tháng 1/2026')
                token = first['conversation_id']
                self.assertEqual(first['data']['total_orders'], 1)
                followup = turn('staff', 'tháng 2/2026 thì sao?', token)
                self.assertEqual(followup['data']['total_orders'], 0)
                unknown = turn('staff', 'đơn tại Hà Nội', token)
                self.assertIsNone(unknown['data'])
                turn('staff', 'bỏ qua', token)
                self.assertEqual(turn('staff', 'tồn kho ngưỡng 3', token)['data']['low_stock_products'], 1)
                self.assertEqual([p['stock'] for p in turn('staff', 'còn hàng sắp hết?', token)['data']['products']], [3])
                sku = turn('staff', 'tra cứu SKU SP000001', token)
                self.assertEqual(sku['data']['products'][0]['id'], 1)
                self.assertNotIn('cost_price', json.dumps(sku))
                self.assertIsNone(turn('staff', 'doanh thu tháng 1/2026', token)['data'])
                current = turn('admin', 'doanh thu tháng 1/2026')
                token = current['conversation_id']
                self.assertEqual(Decimal(current['data']['confirmed_payment_amount_vnd']), Decimal('12.34'))
                self.assertEqual(current['data']['confirmed_payment_order_count'], 1)
                self.assertEqual(Decimal(turn('admin', 'tháng 2/2026 thì sao?', token)['data']['confirmed_payment_amount_vnd']), Decimal('5.66'))
                comparison = turn('admin', 'so với tháng trước?', token)
                self.assertEqual(comparison['data']['changes']['revenue']['difference'], '-6.68')
                self.assertEqual(comparison['data']['changes']['revenue']['percentage_change'], '-54.13')
                top = turn('admin', 'top 5 sản phẩm', token)
                self.assertEqual([(p['product_id'], p['quantity_sold']) for p in top['data']['items']], [(2, 1)])
                empty = turn('admin', 'tháng 3/2026 thì sao?', token)
                self.assertEqual(empty['data']['items'], [])
                multi = turn('admin', 'doanh thu và đơn đang giao tháng 1/2026', token)
                self.assertEqual(Decimal(multi['data']['revenue']['confirmed_payment_amount_vnd']), Decimal('12.34'))
                self.assertEqual(multi['data']['order_statistics']['total_orders'], 1)
                purchase = turn('admin', 'hành vi mua hàng tháng 1/2026', token)
                self.assertEqual((purchase['data']['total_orders'], purchase['data']['unique_buyers'],
                                  purchase['data']['repeat_buyers'], purchase['data']['total_units']), (5, 1, 1, 23))
                self.assertNotIn('user_id', json.dumps(purchase))
                # The source report and revenue intentionally have different definitions.
                self.assertIn('kể cả đơn hủy', purchase['answer'])
        finally:
            sa.event.remove(self.engine, 'before_cursor_execute', record)
            # Optional replay artifact is opt-in and stays in the requested workspace directory.
            if os.getenv('PHASE45_REPLAY_ARTIFACTS') == '1':
                destination = Path(__file__).resolve().parents[2] / '.local-tmp/phase4-5/offline-replay.json'
                destination.write_text(json.dumps({'kind': 'offline_sqlite_synthetic_not_live', 'turns': replay}, ensure_ascii=False, indent=2), encoding='utf8')
        self.assertTrue(statements and all(sql.lstrip().upper().startswith('SELECT') for sql in statements))

    def test_phase45_product_attributes_and_auth_session_isolation(self):
        from shared.conversation import ConversationStore
        from app.services.ai_product_lookup import answer_product_lookup
        with Session(self.engine) as db:
            p = db.get(self.Product, 1)
            attributes = f'tim san pham chat lieu {p.material.name} va loai {p.category.name}'
            result = answer_product_lookup(db, attributes)
            self.assertTrue(any(item['id'] == 1 for item in result['data']['products']))
            for item in result['data']['products']:
                match = db.get(self.Product, item['id'])
                self.assertEqual((match.material_id, match.category_id), (p.material_id, p.category_id))
            result = answer_product_lookup(db, 'tim san pham ' + p.name)
            self.assertTrue(any(item['id'] == 1 for item in result['data']['products']))
            self.assertEqual(answer_product_lookup(db, 'sku DOES-NOT-EXIST')['data']['products'], [])
            # Synthetic SKUs: underscore must be literal, never a SQL LIKE wildcard.
            db.get(self.Product, 1).sku = 'CUSTOM_123'
            db.get(self.Product, 2).sku = 'CUSTOMX123'
            db.flush()
            exact = answer_product_lookup(db, 'sku custom_123')
            self.assertEqual([p['id'] for p in exact['data']['products']], [1])
        with Session(self.engine) as db, db.begin():
            db.add(self.UserSession(user_id=3, token_hash=self.hash_token('admin-second'),
                expires_at=datetime.now(timezone.utc) + __import__('datetime').timedelta(days=1)))
        with patch('shared.conversation.STORE', ConversationStore()):
            _, first, _ = self.admin_call('POST', '/admin/ai/chat', {'message': 'doanh thu tháng 1/2026'})
            for cookie, role in [('admin-second', 'admin'), ('staff-token', 'staff')]:
                code, other, _ = self.call('POST', f'/{role}/ai/chat',
                    {'message': 'tháng 2 thì sao?', 'conversation_id': first['conversation_id']},
                    cookie='lumiere_session=' + cookie)
                self.assertEqual(code, 200)
                self.assertNotEqual(other['conversation_id'], first['conversation_id'])
                self.assertIsNone(other['data'])
            for cookie, code in [(None, 401), ('lumiere_session=test-token', 403), ('lumiere_session=staff-token', 403)]:
                self.assertEqual(self.call('POST', '/admin/ai/chat', {'message': 'hành vi mua hàng tháng 1/2026'}, cookie=cookie)[0], code)

    def test_phase45_order_creation_boundaries_and_empty_report(self):
        from app.services.ai_order_time_tools import get_orders_by_period
        from app.services.purchase_behavior import analyze
        from app.services.ai_business_dialogue import business_turn
        from datetime import date
        instants = ['2026-01-31T16:59:59+00:00', '2026-01-31T17:00:00+00:00',
                    '2026-02-28T16:59:59+00:00', '2026-02-28T17:00:00+00:00']
        for instant in instants:
            ident = self.seed_order(status='shipping', payment_status='unpaid', payment=False)
            with Session(self.engine) as db, db.begin():
                db.get(self.Order, ident).created_at = datetime.fromisoformat(instant)
        with Session(self.engine) as db:
            counts = get_orders_by_period(db, date(2026, 2, 1), date(2026, 2, 28), 'shipping')
            self.assertEqual(counts['total_orders'], 2)
            self.assertEqual(analyze(db, date(2026, 2, 1), date(2026, 2, 28))['total_orders'], 2)
            empty = analyze(db, date(2024, 2, 29), date(2024, 2, 29))
            self.assertEqual((empty['total_orders'], empty['unique_buyers'], empty['total_units']), (0, 0, 0))
            self.assertEqual(empty['daily_orders'], [{'date': '2024-02-29', 'orders': 0}])
        # Explicitly distinguish a supported zero count from an empty ranking.
        zero = business_turn('đơn tháng 2/2024', {}, lambda _: {'intent': 'orders_by_period',
            'data': {'total_orders': 0}, 'answer': '0 đơn'}, role='staff')
        self.assertEqual(zero['data_status'], 'zero')
        no_data = business_turn('top 5 sản phẩm tháng 2/2024', {}, lambda _: {
            'intent': 'top_selling_products', 'data': {'items': []}, 'answer': 'Không có sản phẩm'}, role='admin')
        self.assertEqual(no_data['data_status'], 'no_data')


if __name__ == "__main__":
    original_connect = sa.engine.Engine.connect
    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("Only SQLite memory is allowed")
        return original_connect(engine, *args, **kwargs)
    with patch.object(sa.engine.Engine, "connect", memory_only), patch("dotenv.load_dotenv"):
        unittest.main()
