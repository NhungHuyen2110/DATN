"""Copy and hash-check one cached QA model into a dedicated Docker volume.

No download, overwrite, source mutation or pruning. Run network-disabled with
the existing host cache read-only and only the new QA volume writable.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

SOURCE = Path('/cached-models')
TARGET = Path('/qa-models')
MANIFEST = Path('manifests/registry.ollama.ai/library/qwen2.5/3b')


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    raw = (SOURCE / MANIFEST).read_bytes()
    manifest = json.loads(raw)
    records = [manifest['config'], *manifest['layers']]
    copied = reused = byte_count = 0
    for item in records:
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', item['digest']) or type(item['size']) is not int or item['size'] <= 0:
            raise ValueError('Invalid cached model manifest')
        name = item['digest'].replace(':', '-')
        source, destination = SOURCE / 'blobs' / name, TARGET / 'blobs' / name
        if source.stat().st_size != item['size']:
            raise ValueError('Incomplete source model blob')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.stat().st_size != item['size'] or digest_file(destination) != item['digest'][7:]:
                raise ValueError('Existing QA blob differs; refusing to overwrite it')
            reused += 1
        else:
            digest = hashlib.sha256()
            with source.open('rb') as original, tempfile.NamedTemporaryFile(
                    mode='wb', dir=destination.parent, prefix=name + '.', suffix='.partial', delete=False) as output:
                temporary = Path(output.name)
                for chunk in iter(lambda: original.read(4 * 1024 * 1024), b''):
                    output.write(chunk)
                    digest.update(chunk)
                output.flush()
                os.fsync(output.fileno())
            if temporary.stat().st_size != item['size'] or digest.hexdigest() != item['digest'][7:]:
                raise ValueError('Copied model failed its source manifest checksum')
            # Publish without replacing an existing blob. Only this exact
            # temporary file is removed; interrupted copies remain for review.
            os.link(temporary, destination)
            temporary.unlink()
            copied += 1
        byte_count += item['size']
    target_manifest = TARGET / MANIFEST
    target_manifest.parent.mkdir(parents=True, exist_ok=True)
    if target_manifest.exists():
        if target_manifest.read_bytes() != raw:
            raise ValueError('Refuse to replace an existing QA model manifest')
    else:
        with target_manifest.open('xb') as stream:
            stream.write(raw)
    print(json.dumps({'successful': True, 'model': 'qwen2.5:3b', 'blobs_copied': copied,
                      'blobs_reused': reused, 'bytes_verified': byte_count,
                      'manifest_sha256': hashlib.sha256(raw).hexdigest(),
                      'source_modified': False, 'downloaded': False}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'successful': False, 'error_type': type(error).__name__,
                          'source_modified': False, 'downloaded': False}))
        raise SystemExit(1)
