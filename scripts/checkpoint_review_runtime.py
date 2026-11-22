"""Preserve exact local pre-review images and a non-destructive rollback override."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.host_process import run_bounded
PROJECT = 'lumiere-rebuild-test'
COMPOSE = ['docker', 'compose', '--env-file', '.env.example', '-p', PROJECT,
           '-f', 'compose.yaml', '-f', 'compose.original-data.yaml']
DOCKERFILES = {'business-api': 'backend/Dockerfile', 'ai-api': 'AI/Dockerfile',
               'index-worker': 'infra/index-worker.Dockerfile', 'frontend': 'frontend/Dockerfile'}


def main():
    folder = ROOT / '.local-tmp/review-runtime-checkpoint-20261123'
    folder.mkdir(exist_ok=True)
    if any(folder.iterdir()):
        raise ValueError('Preserve existing runtime checkpoint files')
    def run(command, timeout=30):
        result = run_bounded(command, cwd=ROOT, timeout=timeout)
        if result.returncode:
            with (ROOT / '.local-tmp/review-checkpoint-build.private.log').open('ab') as handle:
                handle.write(result.stdout + result.stderr)
            raise RuntimeError('Runtime checkpoint failed; do not activate review feature')
        return result.stdout.decode('utf-8')
    revision = run(['git', 'rev-parse', 'f4a7a6a']).strip()
    source = ROOT / '.local-tmp/review-rollback-source-f4a7a6a'
    def rebuild(service, tag):
        if not source.exists():
            run(['git', 'worktree', 'add', '--detach', str(source), revision])
        if run(['git', '-C', str(source), 'rev-parse', 'HEAD']).strip() != revision:
            raise ValueError('Rollback source must be the detached baseline')
        requirements = {'AI/requirements-test.txt', 'AI/requirements-runtime.txt', 'backend/requirements.txt'}
        # Git checkout on Windows may change only CRLF. Reuse the existing
        # dependency cache without changing any requirement or application code.
        for name in requirements:
            if (source / name).read_text(encoding='utf-8') != (ROOT / name).read_text(encoding='utf-8'):
                raise ValueError('Baseline dependency content differs; refusing substitution')
            (source / name).write_bytes((ROOT / name).read_bytes())
        changes = run(['git', '-C', str(source), 'status', '--porcelain']).splitlines()
        if any(line[3:].replace('\\', '/') not in requirements for line in changes):
            raise ValueError('Rollback application source has unexpected changes')
        run(['git', '-C', str(source), 'diff', '--ignore-space-at-eol', '--exit-code'])
        run(['docker', 'build', '-f', str(source / DOCKERFILES[service]),
             '--label', 'lumiere.checkpoint.source_revision=' + revision,
             '--label', 'lumiere.checkpoint.service=' + service,
             '--label', 'lumiere.checkpoint.project=' + PROJECT, '-t', tag, str(source)], timeout=300)
    services = {}
    for service in ('business-api', 'ai-api', 'index-worker', 'frontend'):
        container = run(COMPOSE + ['ps', '-aq', service]).strip()
        item = json.loads(run(['docker', 'inspect', container]))[0]
        labels = item['Config']['Labels']
        if labels.get('com.docker.compose.project') != PROJECT or labels.get('com.docker.compose.service') != service:
            raise ValueError('Unexpected checkpoint target')
        env = dict(value.split('=', 1) for value in item['Config']['Env'] if '=' in value)
        if service == 'business-api' and env.get('POSTGRES_DB') != 'lumiere_test_original_data':
            raise ValueError('Checkpoint only supports the serving local copy')
        if env.get('LUMIERE_ATTRIBUTE_REVIEWS_ENABLED', 'false').lower() == 'true':
            raise ValueError('Expected pre-review checkpoint')
        # The existing containers keep the original image IDs reachable. Preserve
        # an additional explicit tag before recreating those containers.
        tag = 'lumiere-review-rollback-' + service + ':20261123'
        old = run_bounded(['docker', 'image', 'inspect', tag], cwd=ROOT, timeout=20)
        if old.returncode == 0:
            saved = json.loads(old.stdout)[0]
            saved_labels = saved['Config'].get('Labels') or {}
            if (saved['Id'] != item['Image'] and not
                    (saved_labels.get('lumiere.checkpoint.source_revision') == revision and
                     saved_labels.get('lumiere.checkpoint.service') == service and
                     saved_labels.get('lumiere.checkpoint.project') == PROJECT)):
                raise ValueError('Refuse to replace a different rollback tag')
        else:
            original = run_bounded(['docker', 'image', 'inspect', item['Image']], cwd=ROOT, timeout=20)
            if original.returncode == 0:
                run(['docker', 'tag', item['Image'], tag])
            else:
                # Rebuild the tested Git baseline in its own detached worktree.
                # Never reset the user's tree or snapshot runtime credentials.
                rebuild(service, tag)
        saved = json.loads(run(['docker', 'image', 'inspect', tag]))[0]
        services[service] = {'image': saved['Id']}
        if service != 'frontend':
            services[service]['environment'] = {'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED': 'false'}
    services['index-worker']['volumes'] = [{'type': 'bind', 'source': str(ROOT / '.local-tmp/recovery/original-data-20261122'),
                                          'target': '/recovery', 'read_only': True}]
    rollback = folder / 'rollback.compose.json'
    rollback.write_text(json.dumps({'services': services}, indent=2) + '\n', encoding='utf-8')
    disable = folder / 'disable-reviews.compose.json'
    disable.write_text(json.dumps({'services': {service: {'environment': {'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED': 'false'}}
                         for service in ('business-api', 'ai-api', 'index-worker')}}, indent=2) + '\n', encoding='utf-8')
    (folder / 'source.json').write_text(json.dumps({'fallback_git_revision': revision,
        'services': services, 'source_worktree': str(source.relative_to(ROOT))}, indent=2) + '\n', encoding='utf-8')
    command = ' '.join(COMPOSE + ['-f', str(rollback.relative_to(ROOT)), 'up', '-d', '--no-deps', '--no-build', *services])
    disable_command = ' '.join(COMPOSE + ['-f', str(disable.relative_to(ROOT)), 'up', '-d', '--no-deps', '--no-build',
                                         'business-api', 'ai-api', 'index-worker'])
    (folder / 'README.txt').write_text('Preferred flag rollback, keep current compatible images:\n' + disable_command +
        '\nBaseline image rollback, only before reviewed graph nodes exist:\n' + command +
        '\nThe old baseline worker rejects Audience/Style nodes; after reviews exist use flag rollback or retain the new worker.\n'
        'Local runtime images only: do not publish checkpoint images or runtime environment.\n'
        'Retain review schema, audit history, data volumes and backups. No database restore or schema downgrade.\n', encoding='utf-8')
    print(json.dumps({'successful': True, 'services': len(services), 'checkpoint': str(folder.relative_to(ROOT)),
                      'database_written': False, 'rollback_override': str(rollback.relative_to(ROOT))}))


if __name__ == '__main__':
    main()
