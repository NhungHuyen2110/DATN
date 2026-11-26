"""Focused real Chrome acceptance; all writes go to the existing commerce QA database."""
import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.local-tmp/browser-python'))
from playwright.sync_api import sync_playwright, expect
from verify_core_commerce_acceptance import db_snapshot, docker, QA, MAIN, FIXTURE

BASE = 'http://127.0.0.1:18082'
PRIVATE = ROOT / '.local-tmp/website-ui-qa'
PRIVATE.mkdir(exist_ok=True)
STATE = PRIVATE / 'state.json'


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', nargs='*')
    parser.add_argument('--report', default='docs/website-ui-acceptance-20261126.json')
    args = parser.parse_args()
    output = ROOT / args.report
    assert not output.exists(), 'Preserve previous evidence; choose a new report'
    detail = json.loads(docker('inspect', QA))[0]
    env = dict(x.split('=', 1) for x in detail['Config']['Env'] if '=' in x)
    assert env['POSTGRES_DB'] == 'lumiere_test_commerce_acceptance'
    assert env['PRODUCT_INDEX_SYNC_ENABLED'] == 'false' and not env.get('SMTP_HOST')
    assert env['VNPAY_TMN_CODE'] == 'TESTONLY'
    assert env['VNPAY_HASH_SECRET'] == 'synthetic-only-commerce-test-secret'
    assert env['VNPAY_RETURN_URL'] == 'https://example.invalid/payments/vnpay/return'
    assert any(m['Destination'] == '/srv/product-uploads' and m['Name'] == 'lumiere-rebuild-test_commerce_acceptance_product_images' for m in detail['Mounts'])
    baseline = db_snapshot(MAIN)
    assert baseline['database'] == 'lumiere_test_original_data'
    fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
    assert fixture['synthetic_accounts_only'] is True
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    report = {'date': '2026-11-26', 'browser': 'Installed Google Chrome, headless, real UI and HTTP',
              'qa_database': env['POSTGRES_DB'], 'ai_requests_sent': 0, 'external_payment_sent': False,
              'reused_evidence': ['core-commerce-acceptance-20261126.json', 'commerce-browser-20261123.json', 'commerce-layout-20261123.json', 'commerce-backend-tests-20261123.json'],
              'cases': [], 'page_errors': [], 'console_errors': [], 'http_errors': [], 'blocked_external_requests': 0, 'blocked_ai_requests': 0}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        def context():
            ctx = browser.new_context(viewport={'width': 1440, 'height': 1000})
            def route(r):
                u = urlsplit(r.request.url)
                if '/ai/' in u.path or 'recommendations' in u.path or u.path.endswith('/chat'):
                    report['blocked_ai_requests'] += 1
                    r.abort()
                elif u.hostname not in ('127.0.0.1', 'localhost'):
                    report['blocked_external_requests'] += 1
                    r.abort()
                else:
                    r.continue_()
            ctx.route('**/*', route)
            ctx.on('page', lambda p: p.on('pageerror', lambda e: report['page_errors'].append(str(e)[:300])))
            ctx.on('page', lambda p: p.on('console', lambda m: report['console_errors'].append(m.text[:500]) if m.type == 'error' else None))
            ctx.on('response', lambda r: report['http_errors'].append({'path': urlsplit(r.url).path, 'status': r.status}) if r.status >= 400 and '/auth/me' not in r.url else None)
            ctx.set_default_timeout(15000)
            return ctx
        def login(ctx, role=None, credentials=None):
            p = ctx.new_page()
            p.goto(BASE + '/pages/login.html')
            c = credentials or fixture['accounts'][role]
            p.get_by_label('Email', exact=True).fill(c['email'])
            p.locator('#password').fill(c['password'])
            p.get_by_role('button', name='ĐĂNG NHẬP', exact=True).click()
            expect(p).not_to_have_url(re.compile('/pages/login.html$'))
            return p
        def get(ctx, path):
            r = ctx.request.get(BASE + '/api' + path)
            assert r.ok, f'QA GET {path} returned {r.status}'
            return r.json()
        def case(name, function):
            if args.only and name not in args.only:
                return
            item = {'name': name}
            try:
                result = function()
                item.update(status='PASS', evidence=result)
            except Exception as e:
                item.update(status='FAIL', error_type=type(e).__name__, error=str(e)[:1200])
            report['cases'].append(item)
            STATE.write_text(json.dumps(state), encoding='utf-8')
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(name + ': ' + item['status'], flush=True)

        def registration():
            ctx = context()
            p = ctx.new_page()
            stamp = secrets.token_hex(5)
            c = {'email': f'ui-qa-{stamp}@example.com', 'password': secrets.token_hex(20), 'full_name': 'UI QA Customer'}
            p.goto(BASE + '/pages/register.html')
            p.get_by_label('Họ tên', exact=True).fill(c['full_name'])
            p.get_by_label('Số điện thoại', exact=True).fill('0901234567')
            p.get_by_label('Email', exact=True).fill(c['email'])
            p.get_by_label('Mật khẩu', exact=True).fill(c['password'])
            p.get_by_label('Nhập lại mật khẩu', exact=True).fill(c['password'])
            p.get_by_role('button', name='ĐĂNG KÝ', exact=True).click()
            expect(p).to_have_url(re.compile('/pages/login.html$'))
            p.close()
            p = login(ctx, credentials=c)
            expect(p).to_have_url(re.compile('/pages/account.html$'))
            c['id'] = get(ctx, '/auth/me')['id']
            state['customer'] = c
            p.locator('#logout-main').click()
            expect(p).to_have_url(re.compile('/pages/login.html$'))
            assert ctx.request.get(BASE + '/api/auth/me').status == 401
            ctx.close()
            return 'Registered through form, UI login/account and logout clear actual server session'

        def catalog():
            ctx = context(); p = ctx.new_page()
            p.goto(BASE + '/pages/products.html')
            cards = p.locator('#catalog-results .catalog-card')
            expect(cards.first).to_be_visible()
            total = p.locator('#result-count').inner_text()
            sample = p.evaluate('window.LUMIERE_PRODUCTS.find(x=>x.stock>0)')
            p.locator('#keyword').fill(sample['name'])
            expect(cards.first.locator('h3')).to_contain_text(sample['name'])
            p.locator('#keyword').fill('QA-NO-MATCH-UNIQUE-20261126')
            expect(cards).to_have_count(0)
            p.locator('#reset-filter').click()
            p.locator('#category').select_option(sample['category'])
            assert all(sample['category'] in x for x in cards.locator('small').all_text_contents())
            p.locator('#max-price').select_option('10000000')
            p.locator('#sort').select_option('asc')
            prices = [int(re.sub(r'\D', '', s)) for s in cards.locator('strong').all_text_contents()]
            assert prices and max(prices) <= 10000000 and prices == sorted(prices)
            p.locator('#reset-filter').click()
            first_id = cards.first.locator('[data-add]').get_attribute('data-add')
            cards.first.locator('a').first.click()
            expect(p).to_have_url(re.compile('product-detail.html\\?id=' + first_id))
            photo = p.locator('.detail-photo'); expect(photo).to_be_visible()
            photo.evaluate('(img)=>img.decode()')
            assert photo.evaluate('(img)=>img.naturalWidth>0')
            p.screenshot(path=str(PRIVATE / 'customer-detail-desktop.png'), full_page=True)
            state['product_id'] = int(first_id)
            ctx.close()
            return {'catalog_count_label': total, 'search_empty_category_price_sort_detail_image': True}

        def customer_orders():
            ctx = context(); p = login(ctx, credentials=state['customer'])
            p.goto(BASE + '/pages/orders.html')
            expect(p.get_by_role('heading', name='Đơn hàng của tôi', exact=True)).to_be_visible()
            links = p.locator('#page-content a[href*="order-detail.html?id="]')
            expect(links.first).to_be_visible()
            href = links.first.get_attribute('href')
            oid = int(href.split('id=')[-1]); data = get(ctx, f'/orders/{oid}')
            links.first.click()
            expect(p.locator('#page-content')).to_contain_text(data['code'])
            expect(p.locator('#page-content')).to_contain_text(data['recipient_name'])
            ctx.close()
            return {'history_detail_order_id': oid, 'code_and_recipient_match_server': True}

        def staff_operations():
            ctx = context(); p = login(ctx, 'staff')
            expect(p).to_have_url(re.compile('/pages/staff/orders.html$'))
            expect(p.locator('[data-status]').first).to_be_visible()
            orders = get(ctx, '/staff/orders')['items']
            pending = next((x for x in orders if x['status'] == 'pending'), None)
            assert pending, 'No pending QA order fixture'
            oid = pending['id']
            p.locator(f'[data-detail="{oid}"]').click()
            expect(p.locator('#order-detail')).to_contain_text(pending['code'])
            with p.expect_response(lambda r: r.request.method == 'PATCH' and f'/staff/orders/{oid}/status' in r.url) as response:
                p.locator(f'[data-status="{oid}"]').select_option('confirmed')
            assert response.value.status == 200
            p.reload(); expect(p.locator(f'[data-status="{oid}"]')).to_have_value('confirmed')
            p.goto(BASE + '/pages/staff/inventory.html')
            button = p.locator('[data-stock]').first
            expect(button).to_be_visible()
            pid = button.get_attribute('data-stock'); old = int(button.get_attribute('data-value'))
            p.once('dialog', lambda d: d.accept(str(old + 1)))
            button.click()
            expect(p.locator(f'[data-stock="{pid}"]')).to_have_attribute('data-value', str(old + 1))
            p.once('dialog', lambda d: d.accept(str(old)))
            p.locator(f'[data-stock="{pid}"]').click()
            expect(p.locator(f'[data-stock="{pid}"]')).to_have_attribute('data-value', str(old))
            assert p.locator('[data-edit]').count() == 0 and p.locator('#product-create').count() == 0
            ctx.close()
            return {'order_id': oid, 'status_persists_reload': True, 'inventory_increment_and_restore': True, 'no_product_price_or_creation_controls': True}

        def admin_products_orders_stats():
            ctx = context(); p = login(ctx, 'admin')
            expect(p.locator('.lm-kpis')).to_be_visible()
            dashboard = get(ctx, '/admin/dashboard')
            expect(p.locator('.lm-kpi').filter(has_text='Tổng đơn hàng').locator('strong')).to_have_text(str(dashboard['total_orders']))
            p.goto(BASE + '/pages/admin/products.html')
            button = p.locator('[data-edit]').first; expect(button).to_be_visible()
            pid = button.get_attribute('data-edit'); name = button.get_attribute('data-name'); price = button.get_attribute('data-price')
            values = iter([name + ' QA', price])
            handler = lambda d: d.accept(next(values))
            p.on('dialog', handler); button.click()
            expect(p.locator(f'[data-edit="{pid}"]')).to_have_attribute('data-name', name + ' QA')
            p.remove_listener('dialog', handler)
            values = iter([name, price]); p.on('dialog', handler)
            p.locator(f'[data-edit="{pid}"]').click()
            expect(p.locator(f'[data-edit="{pid}"]')).to_have_attribute('data-name', name)
            p.remove_listener('dialog', handler)
            p.goto(BASE + '/pages/admin/orders.html')
            detail = p.locator('[data-detail]').first; expect(detail).to_be_visible()
            oid = detail.get_attribute('data-detail'); data = get(ctx, f'/orders/{oid}')
            detail.click(); expect(p.locator('#order-detail')).to_contain_text(data['code'])
            p.goto(BASE + '/pages/admin/analytics.html')
            expect(p.locator('#behavior-results .lm-kpis')).to_be_visible()
            p.locator('#behavior-days').select_option('7')
            expect(p.locator('#behavior-results .lm-kpis')).to_be_visible()
            expect(p.locator('.form-alert:visible')).to_have_count(0)
            ctx.close()
            return 'Admin dashboard matches API, product name/price edit saved and restored, real order detail, analytics 30/7 days'

        def admin_accounts():
            assert 'customer' in state, 'Registration fixture required'
            ctx = context(); p = login(ctx, 'admin'); c = state['customer']
            p.goto(BASE + '/pages/admin/customers.html')
            p.locator('#customer-search').fill(c['email']); p.locator('#customer-search').press('Enter')
            toggle = p.locator(f'[data-toggle="{c["id"]}"]'); expect(toggle).to_be_visible()
            p.locator(f'[data-detail="{c["id"]}"]').click()
            expect(p.locator('#customer-detail')).to_contain_text(c['email'])
            toggle.click(); expect(p.locator(f'[data-toggle="{c["id"]}"]')).to_have_attribute('data-active', 'false')
            toggle = p.locator(f'[data-toggle="{c["id"]}"]'); toggle.click()
            expect(p.locator(f'[data-toggle="{c["id"]}"]')).to_have_attribute('data-active', 'true')
            p.goto(BASE + '/pages/admin/staff.html')
            stamp = secrets.token_hex(5)
            newstaff = {'email': f'ui-staff-{stamp}@example.com', 'password': secrets.token_hex(20), 'name': 'UI QA Staff'}
            values = iter([newstaff['name'], newstaff['email'], newstaff['password'], '0901234567'])
            handler = lambda d: d.accept(next(values)); p.on('dialog', handler)
            p.locator('#staff-create').click()
            row = p.locator('tr').filter(has_text=newstaff['email']); expect(row).to_be_visible()
            p.remove_listener('dialog', handler)
            values = iter(['UI QA Staff Edited', '0901234567']); p.on('dialog', handler)
            row.locator('[data-edit]').click(); expect(row).to_contain_text('UI QA Staff Edited')
            p.remove_listener('dialog', handler)
            row.locator('[data-toggle]').click(); expect(row.locator('[data-toggle]')).to_have_attribute('data-active', 'false')
            row.locator('[data-toggle]').click(); expect(row.locator('[data-toggle]')).to_have_attribute('data-active', 'true')
            ctx2 = context(); staffpage = login(ctx2, credentials=newstaff)
            expect(staffpage).to_have_url(re.compile('/pages/staff/orders.html$'))
            ctx2.close(); ctx.close()
            return 'Customer search/detail/lock/unlock; Staff create/edit/lock/unlock and actual UI login, all synthetic QA accounts'

        def rbac():
            results = []
            for role in ['guest', 'customer', 'staff', 'admin']:
                ctx = context(); p = ctx.new_page() if role == 'guest' else login(ctx, role)
                denied = {'guest': ['/pages/admin/dashboard.html', '/pages/staff/orders.html', '/pages/orders.html'],
                          'customer': ['/pages/admin/products.html', '/pages/staff/inventory.html'],
                          'staff': ['/pages/admin/dashboard.html', '/pages/admin/staff.html'],
                          'admin': ['/pages/staff/orders.html']}[role]
                expected = {'guest': '/pages/login.html', 'customer': '/pages/products.html', 'staff': '/pages/staff/orders.html', 'admin': '/pages/admin/dashboard.html'}[role]
                for path in denied:
                    p.goto(BASE + path)
                    if role == 'guest' and path == '/pages/orders.html':
                        expect(p.locator('#page-content')).to_contain_text('Vui lòng đăng nhập')
                        expect(p.locator('#page-content a')).to_have_attribute('href', 'login.html')
                        results.append({'role': role, 'denied': path, 'login_prompt_without_private_data': True})
                        continue
                    expect(p).to_have_url(BASE + expected)
                    results.append({'role': role, 'denied': path, 'redirect': expected})
                ctx.close()
            return results

        def visual():
            measurements = []
            for role, pages in [('guest', ['products.html', 'product-detail.html?id=1', 'login.html']), ('staff', ['staff/orders.html', 'staff/inventory.html']), ('admin', ['admin/dashboard.html', 'admin/products.html', 'admin/customers.html', 'admin/staff.html', 'admin/orders.html', 'admin/analytics.html'])]:
                ctx = context(); p = ctx.new_page() if role == 'guest' else login(ctx, role)
                for page in pages:
                    p.goto(BASE + '/pages/' + page)
                    expect(p.locator('#page-content')).not_to_be_empty()
                    if role != 'guest':
                        expect(p.locator('#console-body')).not_to_be_empty()
                    elif page == 'products.html':
                        expect(p.locator('.catalog-card').first).to_be_visible()
                    elif page.startswith('product-detail'):
                        expect(p.locator('.detail-photo')).to_be_visible()
                    for width in [1440, 390]:
                        p.set_viewport_size({'width': width, 'height': 900})
                        p.wait_for_timeout(250)
                        measured = p.evaluate('({viewport:innerWidth,body:document.documentElement.scrollWidth})')
                        measurements.append({'page': page, 'width': width, **measured})
                        p.screenshot(path=str(PRIVATE / (page.split('?')[0].replace('/', '-') + f'-{width}.png')), full_page=True)
                    p.set_viewport_size({'width': 1440, 'height': 1000})
                    images = p.locator('#page-content img')
                    for img in images.all()[:4]:
                        img.scroll_into_view_if_needed()
                        img.evaluate('(img)=>img.decode()')
                        assert img.evaluate('(img)=>img.naturalWidth>0'), page + ' broken image'
                    # Check local navigation targets without triggering any protected mutations.
                    paths = p.locator('a[href]').evaluate_all('(links)=>[...new Set(links.map(x=>x.href).filter(x=>x.startsWith(location.origin)&&!x.includes("#")))]')
                    for href in paths:
                        assert ctx.request.get(href).status < 400, 'Broken local link: ' + urlsplit(href).path
                ctx.close()
            state['measurements'] = measurements
            overflows = [x for x in measurements if x['body'] > x['viewport'] + 2]
            assert not overflows, 'Horizontal viewport overflow: ' + json.dumps(overflows)
            return {'measurements': measurements, 'sample_product_images_decoded': True, 'visible_local_navigation_links_http_ok': True}

        def vnpay():
            ctx = context(); p = login(ctx, credentials=state['customer'])
            pending = next((o for o in get(ctx, '/orders/my')['items'] if o['payment_method'] == 'vnpay' and o['payment_status'] == 'unpaid'), None)
            if pending:
                # Resume the UI-created transaction if Chrome navigated before the
                # response body was available to the runner. No second checkout.
                created = ctx.request.post(BASE + '/api/orders/' + str(pending['id']) + '/payments/vnpay')
                assert created.status == 200
                payment = created.json()
            else:
                payment = None
            if payment is None:
                payment = create_vnpay_through_ui(ctx, p)
            transaction = payment['transaction']; oid = transaction['order_id']
            state['vnpay_ui_order_id'] = oid
            params = dict(parse_qsl(urlsplit(payment['payment_url']).query))
            signed = params.pop('vnp_SecureHash')
            sign = lambda d: hmac.new(env['VNPAY_HASH_SECRET'].encode(), urlencode(sorted(d.items())).encode(), hashlib.sha512).hexdigest()
            assert hmac.compare_digest(signed, sign(params))
            assert urlsplit(payment['payment_url']).hostname == 'sandbox.vnpayment.vn'
            assert params['vnp_TmnCode'] == 'TESTONLY' and params['vnp_ReturnUrl'] == env['VNPAY_RETURN_URL']
            assert int(params['vnp_Amount']) == int(Decimal(transaction['amount_vnd']) * 100)
            callback = {'vnp_TxnRef': transaction['reference'], 'vnp_TmnCode': 'TESTONLY', 'vnp_Amount': params['vnp_Amount'], 'vnp_OrderInfo': params['vnp_OrderInfo'], 'vnp_ResponseCode': '00', 'vnp_TransactionStatus': '00', 'vnp_TransactionNo': str(secrets.randbelow(10**12) + 1), 'vnp_BankCode': 'NCB', 'vnp_PayDate': datetime.now(timezone(timedelta(hours=7))).strftime('%Y%m%d%H%M%S')}
            def cb(path, data):
                signed_data = dict(data, vnp_SecureHash=sign(data))
                return ctx.request.get(BASE + '/api/payments/vnpay/' + path + '?' + urlencode(signed_data))
            tamper = dict(callback, vnp_SecureHash='0' * 128)
            rejected = ctx.request.get(BASE + '/api/payments/vnpay/ipn?' + urlencode(tamper)).json()
            assert rejected['RspCode'] == '97'
            wrong_amount = dict(callback, vnp_Amount=str(int(callback['vnp_Amount']) + 100))
            assert cb('ipn', wrong_amount).json()['RspCode'] == '04'
            ret = cb('return', callback); assert ret.status == 200 and ret.json()['payment_status'] == 'unpaid'
            assert get(ctx, f'/orders/{oid}')['payment_status'] == 'unpaid'
            return_local = BASE + '/api/payments/vnpay/return?' + urlencode(dict(callback, vnp_SecureHash=sign(callback)))
            p.goto(return_local)
            expect(p.get_by_role('heading', name='Kết quả chuyển về từ VNPay')).to_be_visible()
            assert cb('ipn', callback).json()['RspCode'] == '00'
            assert cb('ipn', callback).json()['RspCode'] == '02'
            assert get(ctx, f'/orders/{oid}')['payment_status'] == 'paid'
            assert cb('return', callback).json()['transaction_status'] == 'succeeded'
            p.goto(BASE + '/pages/order-detail.html?id=' + str(oid))
            expect(p.locator('#page-content')).to_contain_text('paid')
            state['vnpay_order_id'] = oid
            ctx.close()
            return {'mode': 'SIMULATED callback signed with synthetic QA secret, no gateway contacted', 'order_id': oid, 'url_signature_amount_return_config': True, 'invalid_signature_97': True, 'wrong_amount_04': True, 'return_read_only_and_html': True, 'ipn_success_00_duplicate_02': True, 'order_ui_paid': True, 'real_sandbox_transaction': 'BLOCKED: requires valid merchant, public HTTPS Return/IPN and user payment'}

        def customer_toolbar_fix():
            ctx = context(); p = login(ctx, 'admin')
            p.goto(BASE + '/pages/admin/customers.html')
            expect(p.locator('#customer-search')).to_be_visible()
            measurements = []
            for width in [1440, 390, 320]:
                p.set_viewport_size({'width': width, 'height': 900})
                measured = p.evaluate('({viewport:innerWidth,body:document.documentElement.scrollWidth})')
                assert measured['body'] <= width + 2
                for selector in ['#customer-search', '#customer-active']:
                    box = p.locator(selector).bounding_box()
                    assert box['x'] >= 0 and box['x'] + box['width'] <= width + 1
                measurements.append(measured)
                p.screenshot(path=str(PRIVATE / f'admin-customers-fixed-{width}.png'), full_page=True)
            # The wide table remains scrollable independently of the viewport.
            p.locator('[data-toggle]').first.scroll_into_view_if_needed()
            expect(p.locator('[data-toggle]').first).to_be_visible()
            ctx.close()
            return {'toolbar_and_viewport': measurements, 'table_actions_reachable_by_horizontal_scroll': True}

        def customer_order_mobile():
            ctx = context(); p = login(ctx, credentials=state['customer'])
            measurements = []
            for path in ['orders.html', 'order-detail.html?id=' + str(state['vnpay_order_id'])]:
                p.goto(BASE + '/pages/' + path)
                expect(p.locator('#page-content .panel')).to_be_visible()
                for width in [390, 320]:
                    p.set_viewport_size({'width': width, 'height': 844})
                    measured = p.evaluate('({viewport:innerWidth,body:document.documentElement.scrollWidth})')
                    assert measured['body'] <= width + 2, path + ' viewport overflow'
                    measurements.append({'page': path.split('?')[0], **measured})
                    p.screenshot(path=str(PRIVATE / (path.split('?')[0] + f'-{width}.png')), full_page=True)
                if path == 'orders.html':
                    link = p.locator('#page-content a[href*="order-detail.html?id="]').first
                    link.scroll_into_view_if_needed()
                    expect(link).to_be_visible()
            ctx.close()
            return measurements

        def create_vnpay_through_ui(ctx, p):
            p.goto(BASE + '/pages/products.html')
            card = p.locator('.catalog-card').filter(has=p.locator('[data-add]:not([disabled])')).first
            expect(card).to_be_visible()
            with p.expect_response(lambda r: r.request.method == 'POST' and '/cart/items' in r.url):
                card.locator('[data-add]').click()
            p.goto(BASE + '/pages/checkout.html')
            p.locator('#recipient').fill('UI QA Customer'); p.locator('#phone').fill('0901234567')
            p.locator('#address').fill('123 Duong Kiem Thu'); p.locator('#province').fill('Ha Noi')
            p.wait_for_function('!document.querySelector("#payment-method option[value=vnpay]").disabled')
            p.locator('#payment-method').select_option('vnpay')
            with p.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/payments/vnpay')) as created:
                p.get_by_role('button', name='ĐẶT HÀNG', exact=True).click()
            assert created.value.status == 200
            # A successful URL response may be followed immediately by navigation;
            # read the persisted order and request its same idempotent URL through
            # the API context rather than reading a detached Chrome response body.
            pending = next(o for o in get(ctx, '/orders/my')['items'] if o['payment_method'] == 'vnpay' and o['payment_status'] == 'unpaid')
            saved = ctx.request.post(BASE + '/api/orders/' + str(pending['id']) + '/payments/vnpay')
            assert saved.status == 200
            return saved.json()

        try:
            for name, function in [('customer_registration_login_logout', registration), ('customer_catalog_filters_detail', catalog), ('customer_order_history_detail', customer_orders), ('staff_orders_inventory', staff_operations), ('admin_products_orders_statistics', admin_products_orders_stats), ('admin_accounts', admin_accounts), ('ui_role_guards', rbac), ('responsive_images_links', visual), ('vnpay_simulated_callbacks', vnpay), ('customer_toolbar_responsive_fix', customer_toolbar_fix), ('customer_orders_mobile', customer_order_mobile)]:
                case(name, function)
        finally:
            browser.close()
            report['main_relevant_tables_unchanged'] = baseline == db_snapshot(MAIN)
            report['successful'] = all(c['status'] == 'PASS' for c in report['cases']) and not report['page_errors'] and report['main_relevant_tables_unchanged']
            report['real_vnpay_sandbox'] = 'BLOCKED; simulated merchant only, no bank/user interaction performed'
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'successful': report['successful'], 'cases': len(report['cases']), 'page_errors': len(report['page_errors']), 'main_unchanged': report['main_relevant_tables_unchanged']}))


if __name__ == '__main__':
    run()
