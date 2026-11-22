"""Actual Chrome against frontend/proxy/business/AI containers, using only seeded synthetic accounts."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--artifact-directory', type=Path, default=ROOT / '.local-tmp/compose-browser-20261122')
    parser.add_argument('--grep', help='Run a targeted existing browser subset; report does not claim full coverage')
    parser.add_argument('--fixture', type=Path, default=ROOT / '.local-tmp/compose-core-20261122/fixture.json')
    parser.add_argument('--semantic', action='store_true', help='Require the separately verified real three-source demo')
    parser.add_argument('--monitoring', action='store_true', help='Include actual Grafana browser acceptance')
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists')
    if args.semantic:
        verified = json.loads((ROOT / 'docs/compose-semantic-verified-r2-20261122.json').read_text())
        if not verified.get('successful') or verified.get('production_accessed') is not False:
            parser.error('Verified isolated semantic lab required')
    if args.monitoring and not os.getenv('LUMIERE_GRAFANA_TEST_PASSWORD'):
        parser.error('Explicit synthetic Grafana password required')
    core = json.loads((ROOT / 'docs/compose-core-runtime-20261122.json').read_text())
    if core.get('project') != 'lumiere-rebuild-test' or not core.get('successful') or core.get('production_accessed') is not False:
        parser.error('Verified synthetic container baseline required')
    if not args.fixture.resolve().is_relative_to(ROOT / '.local-tmp'):
        parser.error('Fixture must remain in ignored D lab artifacts')
    fixture = json.loads(args.fixture.read_text())
    if not fixture.get('synthetic_only'):
        parser.error('Synthetic fixture required')
    folder = args.artifact_directory.resolve()
    if not folder.is_relative_to(ROOT / '.local-tmp'):
        parser.error('Browser artifacts must stay in the D workspace temporary area')
    folder.mkdir(exist_ok=False)
    env = {**os.environ, **fixture['fixture_env'], 'LUMIERE_E2E_BASE_URL': 'http://127.0.0.1:18080',
        'LUMIERE_E2E_API_PREFIX': '/api', 'LUMIERE_E2E_DB_KIND': 'isolated', 'LUMIERE_E2E_ALLOW_WRITE': '1',
        'LUMIERE_BROWSER_WITH_AI': '1', 'LUMIERE_BROWSER_WITH_MONITORING': '1' if args.monitoring else '0',
        'LUMIERE_BROWSER_WITH_SEMANTIC': '1' if args.semantic else '0',
        'LUMIERE_GRAFANA_SCREENSHOT': str(folder / 'grafana.png'),
        'LUMIERE_BROWSER_ARTIFACT_DIR': str(folder / 'artifacts'),
        'LUMIERE_BROWSER_JSON_REPORT': str(folder / 'playwright.json'),
        'LUMIERE_E2E_BROWSER_PATH': r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        'NODE_PATH': str(ROOT / '.local-tmp/browser-tools/node_modules'),
        'TEMP': str(ROOT / '.local-tmp'), 'TMP': str(ROOT / '.local-tmp')}
    cli = ROOT / '.local-tmp/browser-tools/node_modules/@playwright/test/cli.js'
    with (folder / 'browser.log').open('wb') as output:
        browser_command = ['node', str(cli), 'test', '--config', str(ROOT / 'scripts/browser/playwright.config.cjs')]
        if args.grep:
            browser_command.extend(['--grep', args.grep])
        result = subprocess.run(browser_command,
            cwd=ROOT, env=env, timeout=600, stdout=output, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    raw_report = json.loads((folder / 'playwright.json').read_text(encoding='utf-8'))
    report = {'successful': result.returncode == 0, 'browser': 'actual installed Chrome',
        'target': 'actual frontend/proxy/business/AI/PostgreSQL containers',
        'base_url': env['LUMIERE_E2E_BASE_URL'], 'api_prefix': '/api', 'stats': raw_report['stats'],
        'production_accessed': False, 'public_deployment': False,
        'selection': args.grep or 'full configured suite',
        'optional_dense_graph': 'actual Compose graph/vector and pinned model' if args.semantic else 'not required; lexical fallback expectation',
        'monitoring_case': 'actual Compose Grafana browser' if args.monitoring else 'skipped; native evidence separate',
        'artifacts': str(folder.relative_to(ROOT))}
    with args.report.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
    print(json.dumps(report))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
