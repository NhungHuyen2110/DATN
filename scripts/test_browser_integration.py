"""Real Chrome + source Business API + EMPTY isolated PostgreSQL; synthetic accounts only."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', required=True, action='store_true')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists')
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session
    url = make_url(os.environ['LUMIERE_SYNC_TEST_URL'])
    if (url.drivername != 'postgresql+psycopg' or url.host != '127.0.0.1' or url.port != 15439
            or not url.database or not url.database.startswith('lumiere_test_browser_')):
        parser.error('Explicit dedicated native browser-test database required')
    with_ai = os.getenv('LUMIERE_BROWSER_WITH_AI') == '1'
    with_monitoring = os.getenv('LUMIERE_BROWSER_WITH_MONITORING') == '1'
    for port in ([18001, 18000] if with_ai else [18001]):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    artifacts = ROOT / '.local-tmp' / url.database
    artifacts.mkdir(exist_ok=False)
    env = {**os.environ, 'LUMIERE_LOAD_DOTENV': 'false', 'POSTGRES_DB': url.database,
           'POSTGRES_USER': url.username, 'POSTGRES_PASSWORD': url.password, 'POSTGRES_HOST': '127.0.0.1',
           'POSTGRES_PORT': '15439', 'PRODUCT_INDEX_SYNC_ENABLED': 'false', 'COOKIE_SECURE': 'false',
           'SMTP_HOST': '', 'PASSWORD_RESET_DEMO_MODE': 'false', 'LUMIERE_METRICS_ENABLED': 'false',
           'LUMIERE_E2E_BASE_URL': 'http://127.0.0.1:18001', 'LUMIERE_E2E_DB_KIND': 'isolated',
           'LUMIERE_E2E_ALLOW_WRITE': '1', 'LUMIERE_E2E_STOCK_PRODUCT_ID': '1',
           'LUMIERE_BROWSER_ARTIFACT_DIR': str(artifacts / 'artifacts'),
           'LUMIERE_BROWSER_JSON_REPORT': str(artifacts / 'playwright.json'),
           'LUMIERE_E2E_BROWSER_PATH': os.getenv('LUMIERE_E2E_BROWSER_PATH') or shutil.which('google-chrome') or r'C:\Program Files\Google\Chrome\Application\chrome.exe',
           'NODE_PATH': str(ROOT / '.local-tmp/browser-tools/node_modules'),
           'TEMP': str(ROOT / '.local-tmp'), 'TMP': str(ROOT / '.local-tmp')}
    os.environ.update(env)
    sys.path[:0] = [str(ROOT), str(ROOT / 'backend')]
    from app.main import app  # Loads all models, including optional password reset.
    from app.core.database import Base
    from app.core.security import hash_password
    from app.models import Role, User, Product, Category, Brand, Material, Gemstone, Collection, Order, OrderItem
    from app.routers.password_reset import PasswordResetToken
    engine = create_engine(url, connect_args={'connect_timeout': 3})
    process, ai_process, monitoring = None, None, None
    try:
        if inspect(engine).get_table_names():
            raise ValueError('Target database is not empty')
        if os.getenv('LUMIERE_BROWSER_USE_MIGRATIONS') == '1':
            from alembic.config import Config
            from alembic import command
            config = Config(str(ROOT / 'backend/alembic.ini'))
            config.set_main_option('script_location', str(ROOT / 'backend/alembic'))
            command.upgrade(config, 'head')
            if set(Base.metadata.tables) - set(inspect(engine).get_table_names()):
                raise AssertionError('Migration chain did not create all application tables')
        else:
            Base.metadata.create_all(engine)
        password = 'Synthetic-E2E-Password-2026!'
        with Session(engine) as db, db.begin():
            for index, role in enumerate(('customer', 'admin', 'staff'), 1):
                db.add(Role(id=index, name=role))
                db.flush()
                email = f'lumiere-e2e-{role}@example.com'
                db.add(User(id=index, role_id=index, full_name='Synthetic ' + role, email=email,
                            phone='0901234567', password_hash=hash_password(password), is_active=True))
                env['LUMIERE_E2E_' + role.upper() + '_EMAIL'] = email
                env['LUMIERE_E2E_' + role.upper() + '_PASSWORD'] = password
            reset_token = 'synthetic-browser-reset-token-2026-abcdef1234567890'
            db.add(User(id=4, role_id=1, full_name='Synthetic reset customer', email='lumiere-reset@example.com',
                        phone='0901234567', password_hash=hash_password(password), is_active=True))
            db.flush()
            db.add(PasswordResetToken(user_id=4, token_hash=hashlib.sha256(reset_token.encode()).hexdigest(),
                                      expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)))
            env.update({'LUMIERE_E2E_RESET_EMAIL': 'lumiere-reset@example.com',
                        'LUMIERE_E2E_RESET_OLD_PASSWORD': password, 'LUMIERE_E2E_RESET_TOKEN': reset_token})
            for model, name in ((Category, 'Nhẫn'), (Brand, 'Synthetic'), (Material, 'Bạc 925'),
                                (Gemstone, 'CZ'), (Collection, 'Synthetic')):
                db.add(model(id=1, name=name))
            db.flush()
            for pid in range(1, 6):
                db.add(Product(id=pid, sku=f'SYNTHETIC{pid}', barcode=f'90000{pid}', name=f'Nhẫn kiểm thử {pid}',
                               category_id=1, brand_id=1, material_id=1, gemstone_id=1, collection_id=1,
                               weight=1, sale_price=1000000, wholesale_price=800000, cost_price=600000, stock=100))
            db.flush()
            for oid, state in ((101, 'pending'), (102, 'pending'), (201, 'delivered'), (202, 'delivered')):
                db.add(Order(id=oid, code=f'E2E-{oid}', user_id=1, recipient_name='Synthetic customer',
                             phone='0901234567', address='Synthetic test address', status=state,
                             payment_status='unpaid', payment_method='cod', stock_restored=False,
                             subtotal_vnd=1000000, shipping_vnd=0, discount_vnd=0, total_vnd=1000000))
                db.flush()
                db.add(OrderItem(order_id=oid, product_id=1, sku='SYNTHETIC1', product_name='Synthetic ring',
                                 quantity=1, unit_price_vnd=1000000, line_total_vnd=1000000))
            db.flush()
            # Explicit fixture IDs do not advance PostgreSQL identity sequences.
            for table in ('users', 'roles', 'orders'):
                db.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT max(id) FROM {table}), true)"))
        engine.dispose()
        env['LUMIERE_AI_DIAGNOSTICS_TOKEN'] = 'synthetic-browser-diagnostics' if with_ai else ''
        if with_monitoring:
            env.update({'LUMIERE_METRICS_ENABLED': 'true', 'LUMIERE_METRICS_TOKEN': 'synthetic-native-monitoring',
                        'LUMIERE_GRAFANA_SCREENSHOT': str(artifacts / 'grafana-dashboard.png'),
                        'LUMIERE_GRAFANA_TEST_PASSWORD': 'synthetic-monitoring-admin-2026'})
        if with_ai:
            env.update({'LUMIERE_AI_INTERNAL_URL': 'http://127.0.0.1:18000',
                        'BUSINESS_API_URL': 'http://127.0.0.1:18001',
                        'LUMIERE_RETRIEVAL_V2_ENABLED': 'true', 'LUMIERE_DENSE_ENABLED': 'false',
                        'LUMIERE_GRAPH_ENABLED': 'false', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                        'HF_HOME': str(ROOT / '.local-tmp/models')})
        env.update({'LUMIERE_E2E_ORDER_ID': '101', 'LUMIERE_E2E_ORDER_STATUS': 'confirmed',
                    'LUMIERE_E2E_COD_ORDER_ID': '201', 'LUMIERE_E2E_ADMIN_ORDER_ID': '101',
                    'LUMIERE_E2E_STAFF_ORDER_ID': '102', 'LUMIERE_E2E_ADMIN_COD_ORDER_ID': '201',
                    'LUMIERE_E2E_STAFF_COD_ORDER_ID': '202'})
        with (artifacts / 'server.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, '-B', '-m', 'uvicorn', 'app.main:app',
                                        '--host', '127.0.0.1', '--port', '18001', '--no-access-log'],
                                       cwd=ROOT / 'backend', env=env, stdout=log, stderr=log,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            ready = False
            for _ in range(30):
                if process.poll() is not None:
                    break
                try:
                    with urlopen('http://127.0.0.1:18001/health/ready', timeout=2) as response:
                        ready = response.status == 200
                    if ready:
                        break
                except OSError:
                    time.sleep(1)
            if not ready:
                raise RuntimeError('Isolated Business API did not become ready; inspect test server.log')
            if with_ai:
                with (artifacts / 'ai-server.log').open('w', encoding='utf-8') as ai_log:
                    ai_process = subprocess.Popen([sys.executable, '-B', '-m', 'uvicorn', 'api:app', '--host', '127.0.0.1',
                                                   '--port', '18000', '--no-access-log'], cwd=ROOT / 'AI',
                                                  env=env, stdout=ai_log, stderr=ai_log,
                                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                ai_ready = False
                for _ in range(90):
                    if ai_process.poll() is not None:
                        break
                    try:
                        with urlopen('http://127.0.0.1:18000/health/live', timeout=2) as response:
                            ai_ready = response.status == 200
                        if ai_ready:
                            break
                    except OSError:
                        time.sleep(1)
                if not ai_ready:
                    raise RuntimeError('Isolated AI API failed startup; inspect ai-server.log')
            monitoring_result = None
            if with_monitoring:
                from native_monitoring_lab import NativeMonitoringLab
                monitoring = NativeMonitoringLab(artifacts, env)
                monitoring.start()
                monitoring_result = monitoring.verify()
            cli = ROOT / '.local-tmp/browser-tools/node_modules/@playwright/test/cli.js'
            with (artifacts / 'browser.log').open('w', encoding='utf-8') as browser_log:
                browser = subprocess.run(['node', str(cli), 'test', '--config', str(ROOT / 'scripts/browser/playwright.config.cjs')],
                                         cwd=ROOT, env=env, stdout=browser_log, stderr=subprocess.STDOUT, timeout=540)
        report = {'successful': browser.returncode == 0, 'database': 'actual isolated PostgreSQL',
                  'browser': 'actual installed Chrome', 'business_api': 'source on loopback port18001',
                  'production_accessed': False, 'external_browser_requests_blocked': True,
                  'artifacts': str(artifacts.relative_to(ROOT)), 'returncode': browser.returncode}
        report['ai_api'] = 'actual source; dense/graph explicitly disabled to test lexical fallback' if with_ai else 'not started'
        report['monitoring'] = monitoring_result
        report['schema_setup'] = 'alembic upgrade head on empty test database' if os.getenv('LUMIERE_BROWSER_USE_MIGRATIONS') == '1' else 'metadata.create_all'
        if os.getenv('LUMIERE_BROWSER_NATIVE_FAULT') == '1' and with_ai and browser.returncode == 0:
            ai_process.terminate()
            ai_process.wait(timeout=10)
            from native_fault_lab import exercise_business_without_ai
            fault = exercise_business_without_ai(env, artifacts, ROOT)
            recovery_started = time.perf_counter()
            with (artifacts / 'ai-recovery.log').open('w', encoding='utf-8') as ai_log:
                ai_process = subprocess.Popen([sys.executable, '-B', '-m', 'uvicorn', 'api:app', '--host', '127.0.0.1',
                                               '--port', '18000', '--no-access-log'], cwd=ROOT / 'AI', env=env,
                                              stdout=ai_log, stderr=ai_log,
                                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            recovered = False
            for _ in range(90):
                try:
                    payload = json.dumps({'query': 'Top 1 nhẫn', 'top_k': 1}).encode()
                    from urllib.request import Request
                    with urlopen(Request('http://127.0.0.1:18000/chat', data=payload,
                                         headers={'Content-Type': 'application/json'}), timeout=3) as response:
                        recovered = json.load(response)['returned_k'] == 1
                    if recovered:
                        break
                except OSError:
                    time.sleep(1)
            fault['ai_recovered_with_verified_product'] = recovered
            fault['recovery_seconds'] = time.perf_counter() - recovery_started
            if not recovered:
                raise AssertionError('AI source did not recover after restart')
            report['native_fault_injection'] = fault
        raw_report = artifacts / 'playwright.json'
        if raw_report.is_file():
            report['stats'] = json.loads(raw_report.read_text(encoding='utf-8'))['stats']
        with args.report.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps(report))
        return browser.returncode
    finally:
        if monitoring is not None:
            monitoring.stop()
        if ai_process is not None and ai_process.poll() is None:
            ai_process.terminate()
            try:
                ai_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                ai_process.kill()
                ai_process.wait(timeout=5)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
