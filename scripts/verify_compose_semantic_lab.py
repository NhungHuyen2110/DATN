"""Read-only verification of the already guarded/reconciled synthetic semantic Compose lab."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from run_compose_semantic_lab import ROOT, COMPOSE, VERIFY, STATUS
sys.path.insert(0, str(ROOT))
from shared.recovery import validate_backup_reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Choose a new report')
    prior = json.loads((ROOT / 'docs/compose-semantic-worker-demo-20261122.json').read_text())
    if prior.get('project') != 'lumiere-rebuild-test' or prior.get('sync_status', {}).get('states') != {'done':5}:
        parser.error('Guarded five-job reconciliation evidence required')
    recovery = validate_backup_reference(ROOT / '.local-tmp/recovery/compose-demo-20261122/backup-reference.json',
                                         'test', 'postgres', 5432, 'lumiere_test_rebuild')
    def run(command, timeout=60):
        return subprocess.run(command, cwd=ROOT, capture_output=True, check=True, timeout=timeout).stdout
    cid = run(COMPOSE + ['ps', '-q', 'ai-api']).decode().strip()
    target = json.loads(run(['docker', 'inspect', cid]))[0]
    labels = target['Config']['Labels']
    if labels.get('com.docker.compose.project') != 'lumiere-rebuild-test' or labels.get('com.docker.compose.service') != 'ai-api':
        parser.error('Wrong AI target')
    report = {'successful':False, 'project':'lumiere-rebuild-test', 'production_accessed':False,
              'scope':'read-only verification of actual Compose with five synthetic products and pinned model',
              'backup_guard':recovery}
    try:
        report['sync_status'] = json.loads(run(COMPOSE + ['exec', '-T', 'business-api', 'python', '-B', '-c', STATUS]))
        if report['sync_status']['states'] != {'done':5}:
            raise ValueError('All five projection jobs must be done')
        report['retrieval'] = json.loads(run(COMPOSE + ['exec', '-T', 'ai-api', 'python', '-B', '-c', VERIFY], timeout=300))
        report['successful'] = report['retrieval']['successful']
    except (subprocess.SubprocessError, ValueError, KeyError) as error:
        report['error_type'] = type(error).__name__
        if isinstance(error, subprocess.CalledProcessError):
            (ROOT / '.local-tmp' / (args.report.stem + '.log')).write_bytes(error.stdout + error.stderr)
    report['verified_utc'] = datetime.now(timezone.utc).isoformat()
    with args.report.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
    print(json.dumps(report))
    return 0 if report['successful'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
