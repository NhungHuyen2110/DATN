"""Start only the isolated rebuilt core, migrate/seed empty test DB, smoke through the real proxy.

Leaves the test project running for browser/fault tests. Never starts pre-existing
containers or resets volumes. Uses only .env.example with synthetic credentials.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ['docker', 'compose', '--env-file', '.env.example', '-f', 'compose.yaml']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists')
    folder = ROOT / '.local-tmp/compose-core-20261122'
    folder.mkdir(exist_ok=False)
    def run(arguments, name, content=None, timeout=180):
        result = subprocess.run(arguments, input=content, capture_output=True, cwd=ROOT, timeout=timeout,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (folder / (name + '.log')).write_bytes((result.stdout or b'') + (result.stderr or b''))
        if result.returncode:
            raise RuntimeError('Core lab command failed; see ' + name + '.log')
        return result.stdout
    run([*COMPOSE, 'up', '-d', '--no-deps', 'postgres', 'business-api', 'frontend', 'reverse-proxy', 'ai-api'], 'up', timeout=240)
    postgres_user = None
    for service in ('postgres', 'business-api'):
        identity = run([*COMPOSE, 'ps', '-q', service], service + '-id').decode().strip()
        details = json.loads(run(['docker', 'inspect', identity], service + '-inspect'))[0]
        # Keep full inspect (synthetic env) only in ignored lab artifacts, never stdout/docs.
        labels = details['Config']['Labels']
        if labels.get('com.docker.compose.project') != 'lumiere-rebuild-test' or labels.get('com.docker.compose.service') != service:
            raise ValueError('Unexpected service identity')
        values = dict(item.split('=', 1) for item in details['Config']['Env'] if '=' in item)
        if values.get('POSTGRES_DB') != 'lumiere_test_rebuild':
            raise ValueError('Unexpected database namespace')
        if service == 'postgres':
            postgres_user = values['POSTGRES_USER']
    ready = False
    for _ in range(30):
        try:
            run([*COMPOSE, 'exec', '-T', 'postgres', 'pg_isready', '-U', postgres_user, '-d', 'lumiere_test_rebuild'], 'pg-ready', timeout=5)
            ready = True
            break
        except RuntimeError:
            time.sleep(1)
    if not ready:
        raise RuntimeError('Test Postgres not ready')
    run([*COMPOSE, 'exec', '-T', 'business-api', 'alembic', 'upgrade', 'head'], 'migrations')
    run([*COMPOSE, 'exec', '-T', 'business-api', 'python', '-B', '-', '--confirm-isolated',
         '--report', '/tmp/lumiere-acceptance-fixture.json'], 'seed',
         content=(ROOT / 'scripts/seed_compose_acceptance_fixture.py').read_bytes())
    fixture = json.loads(run([*COMPOSE, 'exec', '-T', 'business-api', 'cat', '/tmp/lumiere-acceptance-fixture.json'], 'fixture'))
    (folder / 'fixture.json').write_text(json.dumps(fixture), encoding='utf-8')
    statuses = {}
    for path in ('/', '/pages/login.html', '/api/health/live', '/api/health/ready', '/ai/health/live'):
        for attempt in range(20):
            try:
                with urlopen('http://127.0.0.1:18080' + path, timeout=3) as response:
                    statuses[path] = response.status
                break
            except OSError:
                if attempt == 19:
                    raise
                time.sleep(1)
    with urlopen('http://127.0.0.1:18080/api/products?page_size=1', timeout=3) as response:
        assert json.load(response)['total'] == 5
    request = Request('http://127.0.0.1:18080/ai/chat', data=json.dumps({'query': 'Top 3 nhẫn dưới 8 triệu'}).encode(),
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=60) as response:
        chat = json.load(response)
    assert chat['returned_k'] == 3 and all(item['verified_source'] == 'business_api' for item in chat['products'])
    report = {'successful': True, 'project': 'lumiere-rebuild-test', 'proxy': 'http://127.0.0.1:18080',
        'services': ['postgres', 'business-api', 'frontend', 'reverse-proxy', 'ai-api'], 'statuses': statuses,
        'schema': 'actual alembic upgrade head', 'catalog': '5 synthetic test products, not production/quality benchmark',
        'chat': {'status': chat['status'], 'returned_k': chat['returned_k'], 'verified_source': 'business_api'},
        'scope': 'real containers/proxy; optional dense/graph dependencies not yet started', 'production_accessed': False,
        'test_services_left_running': True}
    with args.report.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
