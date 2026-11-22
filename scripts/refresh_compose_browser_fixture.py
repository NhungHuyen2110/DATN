"""Back up the verified synthetic DB and append fresh one-use browser fixtures; never resets data."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ['docker', 'compose', '--env-file', '.env.example', '-f', 'compose.yaml']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    folder = args.directory.resolve()
    if not folder.is_relative_to(ROOT / '.local-tmp') or args.report.exists():
        parser.error('New D workspace artifact folder/report required')
    baseline = json.loads((ROOT / 'docs/compose-core-runtime-20261122.json').read_text())
    if not baseline.get('successful') or baseline.get('project') != 'lumiere-rebuild-test' or baseline.get('production_accessed') is not False:
        parser.error('Verified synthetic core baseline required')
    def run(command, content=None):
        return subprocess.run(command, cwd=ROOT, input=content, capture_output=True, check=True, timeout=120).stdout
    user = None
    for service in ('postgres', 'business-api'):
        cid = run(COMPOSE + ['ps', '-q', service]).decode().strip()
        target = json.loads(run(['docker', 'inspect', cid]))[0]
        labels = target['Config']['Labels']
        env = dict(item.split('=', 1) for item in target['Config']['Env'] if '=' in item)
        if (labels.get('com.docker.compose.project') != 'lumiere-rebuild-test' or
                labels.get('com.docker.compose.service') != service or env.get('POSTGRES_DB') != 'lumiere_test_rebuild'):
            parser.error('Wrong database/project identity')
        if service == 'postgres':
            user = env['POSTGRES_USER']
    folder.mkdir(exist_ok=False)
    backup = run(COMPOSE + ['exec', '-T', 'postgres', 'pg_dump', '-U', user, '-d', 'lumiere_test_rebuild', '-Fc'])
    if not backup.startswith(b'PGDMP'):
        raise ValueError('Test DB backup failed')
    (folder / 'before-fixtures.dump').write_bytes(backup)
    remote = '/tmp/lumiere-browser-' + folder.name + '.json'
    run(COMPOSE + ['exec', '-T', 'business-api', 'python', '-B', '-', '--confirm-isolated', '--report', remote],
        (ROOT / 'scripts/seed_additional_browser_fixtures.py').read_bytes())
    added = json.loads(run(COMPOSE + ['exec', '-T', 'business-api', 'cat', remote]))
    previous = json.loads((ROOT / '.local-tmp/compose-core-20261122/fixture.json').read_text())
    fixture = {**previous, 'fixture_env': {**previous['fixture_env'], **added['fixture_env']}}
    fixture['project'] = 'lumiere-rebuild-test'
    (folder / 'fixture.json').write_text(json.dumps(fixture), encoding='utf-8')
    report = {'successful': True, 'synthetic_only': True, 'new_reset_users': 1, 'new_orders': 4,
        'previous_rows_preserved': True, 'backup_sha256': hashlib.sha256(backup).hexdigest(),
        'fixture': str((folder / 'fixture.json').relative_to(ROOT)), 'production_accessed': False}
    with args.report.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
