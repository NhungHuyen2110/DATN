"""Bounded live API acceptance on the existing, explicitly isolated commerce QA stack."""
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import secrets
import subprocess
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs/core-commerce-acceptance-20261126.json'
QA = 'lumiere-rebuild-test-business-qa-1'
MAIN = 'lumiere-rebuild-test-business-api-1'
BASE = 'http://127.0.0.1:18082/api'
FIXTURE = ROOT / '.local-tmp/original-db-20261122-014434/ai-acceptance/fixture.json'


def docker(*args):
    return subprocess.check_output(['docker', *args], cwd=ROOT, timeout=30, text=True).strip()


def db_snapshot(container):
    # Digest relevant rows inside the container; never export business identities or credentials.
    code = '''import json
from sqlalchemy import text
from app.core.database import engine
tables = ('users', 'products', 'carts', 'cart_items', 'orders', 'order_items', 'payment_transactions')
with engine.connect() as db:
 result = {'database': engine.url.database, 'tables': {}}
 for table in tables:
  if db.scalar(text("SELECT to_regclass(:t)"), {'t': table}) is not None:
   rows = db.execute(text('SELECT count(*), md5(coalesce(string_agg(row_to_json(t)::text, chr(10) ORDER BY t.id), :empty)) FROM ' + table + ' t'), {'empty': ''}).one()
   result['tables'][table] = {'rows': rows[0], 'digest': rows[1]}
 print(json.dumps(result))'''
    return json.loads(docker('exec', container, 'python', '-c', code))


def session():
    s = requests.Session()
    s.trust_env = False
    return s


def call(s, method, path, expected=200, body=None):
    r = s.request(method, BASE + path, json=body, timeout=20)
    assert r.status_code == expected, f'{method} {path}: expected {expected}, received {r.status_code}'
    return r.json() if r.content else None


def main():
    assert not REPORT.exists(), 'Choose a fresh report path'
    report = {'successful': False, 'date': '2026-11-26', 'scope': 'Joined Customer COD -> Staff fulfillment/collection -> Admin orders/revenue, live HTTP and actual RBAC',
              'reused_evidence': ['commerce-browser-20261123.json', 'compose-release-full-browser-20261122.json'],
              'current_browser_retested': False, 'checks': [], 'phase': 'isolation'}
    before = None
    try:
        details = json.loads(docker('inspect', QA))[0]
        env = dict(x.split('=', 1) for x in details['Config']['Env'] if '=' in x)
        assert env['POSTGRES_DB'] == 'lumiere_test_commerce_acceptance'
        assert env['PRODUCT_INDEX_SYNC_ENABLED'] == 'false'
        assert not env.get('SMTP_HOST'), 'No external mail allowed'
        mounts = [m for m in details['Mounts'] if m['Destination'] == '/srv/product-uploads']
        assert len(mounts) == 1 and mounts[0]['Name'] == 'lumiere-rebuild-test_commerce_acceptance_product_images'
        qa_before = db_snapshot(QA)
        assert qa_before['database'] == 'lumiere_test_commerce_acceptance'
        before = db_snapshot(MAIN)
        assert before['database'] == 'lumiere_test_original_data'
        report['qa_database'] = qa_before['database']
        report['checks'].append('Runtime QA database, separate images, sync disabled, mail disabled verified before writes')
        fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
        assert fixture['synthetic_accounts_only'] is True
        admin, staff, other, customer, guest = (session() for _ in range(5))
        report['phase'] = 'login'
        for role, s in [('admin', admin), ('staff', staff), ('customer', other)]:
            call(s, 'POST', '/auth/login', body=fixture['accounts'][role])
            assert call(s, 'GET', '/auth/me')['role'] == role
        stamp = secrets.token_hex(6)
        credentials = {'email': f'core-qa-{stamp}@example.com', 'password': secrets.token_hex(24)}
        call(customer, 'POST', '/auth/register', 201, dict(credentials, full_name='Core commerce QA', phone='0901234567'))
        call(customer, 'POST', '/auth/login', body=credentials)
        assert call(customer, 'GET', '/auth/me')['role'] == 'customer'
        report['checks'].append('Three roles authenticate with actual sessions; fresh synthetic Customer used')
        today = datetime.now(ZoneInfo('Asia/Bangkok')).date().isoformat()
        revenue_path = f'/admin/reports/revenue?start_date={today}&end_date={today}&group_by=day'
        baseline = call(admin, 'GET', '/admin/dashboard')
        revenue_before = call(admin, 'GET', revenue_path)
        amount = lambda d: Decimal(str(d['confirmed_payment_amount_vnd']))
        report['phase'] = 'customer_cod'
        catalog = call(customer, 'GET', '/products?page_size=100')
        product = next(p for p in catalog['items'] if p['stock'] > 0)
        pid = product['id']
        stock_before = call(customer, 'GET', f'/products/{pid}')['stock']
        call(customer, 'POST', '/cart/items', body={'product_id': pid, 'quantity': 1})
        assert any(x['product']['id'] == pid for x in call(customer, 'GET', '/cart')['items'])
        checkout = {'recipient_name': 'Core commerce QA', 'phone': '0901234567', 'address': '123 Duong Kiem Thu, Ha Noi', 'payment_method': 'cod'}
        order = call(customer, 'POST', '/orders', 201, checkout)
        oid = order['id']
        report['qa_order_id'] = oid
        assert order['status'] == 'pending' and order['payment_status'] == 'unpaid'
        assert order['payment_method'] == 'cod'
        assert call(customer, 'GET', '/cart')['items'] == []
        assert call(customer, 'GET', f'/products/{pid}')['stock'] == stock_before - 1
        assert call(customer, 'GET', f'/orders/{oid}')['id'] == oid
        assert any(o['id'] == oid for o in call(customer, 'GET', '/orders/my')['items'])
        assert amount(call(admin, 'GET', revenue_path)) == amount(revenue_before)
        report['checks'].append('Customer selects in-stock product, cart persists, COD pending/unpaid, cart cleared, stock deducted once, own history/detail correct')
        report['phase'] = 'rbac'
        for path in ['/orders/my', '/staff/orders', '/admin/orders', '/admin/dashboard', revenue_path]:
            call(guest, 'GET', path, 401)
        for path in ['/staff/orders', '/admin/orders', '/admin/dashboard', revenue_path]:
            call(customer, 'GET', path, 403)
        for prefix in ['staff', 'admin']:
            call(customer, 'PATCH', f'/{prefix}/orders/{oid}/status', 403, {'status': 'confirmed'})
            call(customer, 'POST', f'/{prefix}/orders/{oid}/cod/confirm', 403, {'collection_reference': 'FORBIDDEN-QA'})
        call(other, 'GET', f'/orders/{oid}', 404)
        for path in ['/admin/orders', '/admin/dashboard', revenue_path]:
            call(staff, 'GET', path, 403)
        call(staff, 'PATCH', f'/admin/orders/{oid}/status', 403, {'status': 'confirmed'})
        for s in [staff, admin]:
            call(s, 'POST', '/orders', 403, checkout)
        assert call(customer, 'GET', f'/orders/{oid}')['status'] == 'pending'
        report['checks'].append('Guest 401; Customer denied operational reads/writes and other Customer detail 404; Staff denied Admin orders/revenue/status; Staff/Admin cannot checkout')
        report['phase'] = 'staff_fulfillment'
        assert any(o['id'] == oid for o in call(staff, 'GET', '/staff/orders')['items'])
        assert call(staff, 'GET', f'/staff/orders/{oid}')['id'] == oid
        call(staff, 'POST', f'/staff/orders/{oid}/cod/confirm', 409, {'collection_reference': f'CORE-QA-{stamp}'})
        call(staff, 'PATCH', f'/staff/orders/{oid}/status', 409, {'status': 'delivered'})
        for state in ['confirmed', 'packing', 'shipping', 'delivered']:
            result = call(staff, 'PATCH', f'/staff/orders/{oid}/status', body={'status': state})
            assert result['status'] == state
            assert call(customer, 'GET', f'/orders/{oid}')['status'] == state
        assert amount(call(admin, 'GET', revenue_path)) == amount(revenue_before)
        report['checks'].append('Staff sees same order/detail, rejects early COD collection and skipped transitions, fulfills all four legal transitions; delivered unpaid excluded from revenue')
        report['phase'] = 'cod_collection_admin_revenue'
        receipt = {'collection_reference': f'CORE-QA-{stamp}'}
        payment = call(staff, 'POST', f'/staff/orders/{oid}/cod/confirm', body=receipt)
        assert payment['status'] == 'succeeded'
        replay = call(staff, 'POST', f'/staff/orders/{oid}/cod/confirm', body=receipt)
        assert replay['id'] == payment['id']
        final = call(admin, 'GET', f'/orders/{oid}')
        assert final['payment_status'] == 'paid' and final['status'] == 'delivered'
        assert any(o['id'] == oid for o in call(admin, 'GET', '/admin/orders')['items'])
        dashboard = call(admin, 'GET', '/admin/dashboard')
        revenue = call(admin, 'GET', revenue_path)
        total = Decimal(str(order['total_vnd']))
        assert dashboard['total_orders'] == baseline['total_orders'] + 1
        assert amount(dashboard) - amount(baseline) == total
        assert amount(revenue) - amount(revenue_before) == total
        assert revenue['confirmed_payment_order_count'] == revenue_before['confirmed_payment_order_count'] + 1
        assert call(customer, 'GET', f'/products/{pid}')['stock'] == stock_before - 1
        assert call(customer, 'GET', f'/orders/{oid}')['payment_status'] == 'paid'
        report['checks'].append('Staff COD receipt succeeds and repeated receipt is idempotent; Admin sees same delivered/paid order, dashboard +1 and verified revenue increases exactly by order total; stock not deducted twice')
        report['order_total_vnd'] = str(total)
        report['successful'] = True
        report['phase'] = 'complete'
    except Exception as error:
        # Do not leak fixture credentials, session cookies, private responses or database URLs.
        report['failure_type'] = type(error).__name__
        if isinstance(error, AssertionError):
            report['failure'] = str(error)
        raise
    finally:
        if before:
            after = db_snapshot(MAIN)
            report['main_relevant_tables_unchanged'] = before == after
            report['main_snapshot'] = after
            if before != after:
                report['successful'] = False
        REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
