"""Actual source-process outage checks against ONLY the fixed native test ports."""
import json
import os
from pathlib import Path
import subprocess
import time


def exercise_business_without_ai(environment, artifacts, root):
    import requests
    with requests.Session() as client:
        client.trust_env = False
        try:
            client.get('http://127.0.0.1:18000/health/live', timeout=2)
        except requests.ConnectionError:
            pass
        else:
            raise AssertionError('AI process must actually be unavailable')
        base = 'http://127.0.0.1:18001'
        assert client.get(base + '/health/ready', timeout=3).status_code == 200
        assert client.get(base + '/products', timeout=3).status_code == 200
        response = client.post(base + '/auth/login', json={
            'email': environment['LUMIERE_E2E_CUSTOMER_EMAIL'],
            'password': environment['LUMIERE_E2E_CUSTOMER_PASSWORD']}, timeout=3)
        assert response.status_code == 200
        assert client.get(base + '/auth/me', timeout=3).json()['role'] == 'customer'
        assert client.post(base + '/cart/items', json={'product_id': 5, 'quantity': 1}, timeout=3).status_code == 200
        order = client.post(base + '/orders', json={'recipient_name': 'Synthetic outage customer', 'phone': '0901234567',
                            'address': 'Synthetic isolated outage address', 'payment_method': 'cod'}, timeout=3)
        assert order.status_code == 201
        identity = order.json()['id']
        assert client.get(base + '/orders/' + str(identity), timeout=3).json()['payment_method'] == 'cod'
        assert client.get(base + '/admin/orders', timeout=3).status_code == 403
    browser_env = {**environment, 'LUMIERE_BROWSER_JSON_REPORT': str(artifacts / 'fault-browser.json')}
    cli = root / '.local-tmp/browser-tools/node_modules/@playwright/test/cli.js'
    with (artifacts / 'fault-browser.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(['node', str(cli), 'test', '--config', str(root / 'scripts/browser/playwright.config.cjs'),
                                 '--grep', 'catalog remains available'], cwd=root, env=browser_env,
                                stdout=log, stderr=log, timeout=90)
    if result.returncode:
        raise AssertionError('Real browser catalog must survive the actual AI outage')
    report = {'actual_ai_process_unavailable': True, 'business_readiness': 200, 'catalog': 200,
              'customer_login': 200, 'customer_cod_checkout': 201, 'customer_order_read': 200,
              'customer_admin_access': 403, 'guest_browser_catalog': 'passed',
              'scope': 'actual native source processes, not a container failure test', 'production_accessed': False}
    return report
