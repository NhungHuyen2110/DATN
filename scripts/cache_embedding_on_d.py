"""Copy an existing pinned embedding snapshot to the workspace's D cache; no download."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42'
MODEL = 'models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    destination = ROOT / '.local-tmp/models/hub' / MODEL / 'snapshots' / REVISION
    if source.name != REVISION or not (source / 'model.safetensors').is_file():
        parser.error('Expected the known pinned cached snapshot with model.safetensors')
    if args.report.exists() or destination.exists():
        parser.error('Refusing to overwrite a report or cached snapshot')
    size = sum(path.stat().st_size for path in source.rglob('*') if path.is_file())
    if shutil.disk_usage(ROOT).free < size * 2 + 1024**3:
        parser.error('Insufficient free workspace storage')
    shutil.copytree(source, destination)
    reference = destination.parents[1] / 'refs/main'
    reference.parent.mkdir(parents=True, exist_ok=True)
    if reference.exists():
        raise ValueError('Refusing to change an existing main reference')
    reference.write_text(REVISION, encoding='ascii')
    def digest(path):
        value = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                value.update(chunk)
        return value.hexdigest()
    original, copied = digest(source / 'model.safetensors'), digest(destination / 'model.safetensors')
    if original != copied:
        raise ValueError('Cached weight checksum mismatch')
    report = {'successful': True, 'revision': REVISION, 'bytes_copied': size,
              'destination': str(destination), 'weights_sha256': copied,
              'network_download': False, 'source_modified': False}
    with args.report.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
