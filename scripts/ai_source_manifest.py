"""Fingerprint deployment inputs without building images or reading secrets.

The source fingerprint identifies dirty checkouts as well as committed ones.
Image IDs/digests are recorded separately after an approved build.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def source_manifest(include_worker=False):
    files = set()
    for directory in ('AI', 'backend', 'shared', 'data'):
        for path in (ROOT / directory).rglob('*'):
            relative = path.relative_to(ROOT)
            if (not path.is_file() or any(part in {'__pycache__', '.venv', 'node_modules', '.git'} for part in relative.parts)
                    or path.name.startswith('.env') or path.suffix in {'.pem', '.key', '.bak', '.dump', '.zip'}
                    or relative.as_posix() == 'data/suppliers.json'):
                continue
            files.add(relative.as_posix())
    for name in ('.dockerignore', 'output/products_ai.csv', 'compose.yaml',
                 'compose.original-data.yaml', 'compose.semantic-dst.yaml'):
        files.add(name)
    if include_worker:
        files.update({'infra/index-worker.Dockerfile', 'scripts/run_index_worker.py'})
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(files)}
    # Hash paths too, so renames and missing modules alter the fingerprint.
    fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain=v1'], cwd=ROOT, text=True).splitlines()
    return {'git_commit': head, 'source_sha256': fingerprint,
            'scope': 'AI backend shared data COPY inputs plus deployment recipes'
                     + (' and worker Dockerfile/entrypoint' if include_worker else '') + '; no env/model/DB files',
            'dirty_paths': dirty, 'files': hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--include-worker', action='store_true', help='Include index-worker build recipe and entrypoint')
    args = parser.parse_args()
    manifest = source_manifest(include_worker=args.include_worker)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(manifest, handle, indent=2)
        handle.write('\n')
    print(json.dumps({key: manifest[key] for key in ('git_commit', 'source_sha256')}))


if __name__ == '__main__':
    main()
