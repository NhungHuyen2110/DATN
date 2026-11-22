"""Build one local test image and persist actual image identity; never push/deploy or run databases."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILES = {'frontend': 'frontend/Dockerfile', 'business-api': 'backend/Dockerfile',
               'ai-api': 'AI/Dockerfile', 'index-worker': 'infra/index-worker.Dockerfile'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service', required=True, choices=DOCKERFILES)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--record-existing-log', type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists')
    if not json.loads((ROOT / 'docs/docker-storage-verification-20261122.json').read_text())['successful']:
        parser.error('Verified storage on D required before large builds')
    if Path(r'C:\Users\Admin\AppData\Local\Docker\wsl\disk').resolve() != ROOT / '.local-tmp/docker-desktop-data/disk':
        parser.error('Docker data must physically resolve to D')
    log = (args.record_existing_log or (ROOT / '.local-tmp' / (args.report.stem + '.log'))).resolve()
    if not log.is_relative_to(ROOT):
        parser.error('Build log must remain inside the workspace')
    if args.record_existing_log:
        raw = log.read_bytes()
        text = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig', errors='replace')
        if 'Built' not in text or 'ERROR:' in text:
            parser.error('Existing build success log required')
        exit_code = 0
    else:
        if log.exists():
            parser.error('Log exists; preserve it and choose a new report')
        with log.open('xb') as output:
            try:
                built = subprocess.run(['docker', 'compose', '--env-file', '.env.example', '-f', 'compose.yaml',
                    'build', args.service], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=1200,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                exit_code = built.returncode
            except subprocess.TimeoutExpired:
                exit_code = 124
    report = {'successful': exit_code == 0, 'service': args.service, 'exit_code': exit_code,
              'completed_utc': datetime.now(timezone.utc).isoformat(),
              'dockerfile_sha256': hashlib.sha256((ROOT / DOCKERFILES[args.service]).read_bytes()).hexdigest(),
              'log': str(log.relative_to(ROOT)), 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
              'source_state': 'uncommitted local changes; image is not a published release',
              'pushed': False, 'containers_started': False, 'production_database_accessed': False}
    if exit_code == 0:
        image = subprocess.run(['docker', 'image', 'inspect', 'lumiere-rebuild-test-' + args.service + ':latest',
            '--format', '{{json .Id}}'], capture_output=True, text=True, timeout=15)
        if image.returncode:
            report['successful'] = False
            report['error_type'] = 'ImageInspectionFailed'
        else:
            report['image_id'] = json.loads(image.stdout)
    with args.report.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
    print(json.dumps(report))
    return 0 if report['successful'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
