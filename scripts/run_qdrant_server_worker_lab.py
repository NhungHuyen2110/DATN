"""Use an EXISTING Qdrant image and named volumes in the verified D-backed Docker VHD.

Does not pull/build images, reuse old containers, touch production data, or move
Docker storage. Stops only the uniquely named container this script created.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def command(arguments, timeout=30):
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('Lab command failed: ' + arguments[0] + ' ' + arguments[1])
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', required=True, action='store_true')
    parser.add_argument('--attempt', required=True, type=int, choices=range(1, 10))
    parser.add_argument('--projection-attempt', required=True, type=int, choices=range(1, 10))
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists')
    if Path(r'C:\Users\Admin\AppData\Local\Docker\wsl\disk').resolve() != ROOT / '.local-tmp/docker-desktop-data/disk':
        parser.error('Verified Docker data on D is required for named test volumes')
    name = 'lumiere-rebuild-test-qdrant-worker-' + str(args.attempt)
    folder = ROOT / '.local-tmp' / name
    if folder.exists():
        parser.error('Lab directory exists; preserve evidence and use a new attempt')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 16334))
    existing = subprocess.run(['docker', 'container', 'inspect', name], capture_output=True, timeout=15)
    if existing.returncode == 0:
        parser.error('Test container already exists; never replace it')
    image_id = command(['docker', 'image', 'inspect', 'qdrant/qdrant:latest', '--format', '{{.Id}}'])
    if not image_id.startswith('sha256:'):
        raise ValueError('Existing local image ID required; no automatic pulls')
    folder.mkdir()
    volume_names = {part: name + '-' + part for part in ('storage', 'snapshots')}
    for volume in volume_names.values():
        exists = subprocess.run(['docker', 'volume', 'inspect', volume], capture_output=True, timeout=15)
        if exists.returncode == 0:
            raise ValueError('Test volume exists; preserve it and choose a new attempt')
        command(['docker', 'volume', 'create', '--label', 'com.docker.compose.project=lumiere-rebuild-test', volume])
    started = False
    try:
        container_id = command(['docker', 'run', '-d', '--pull=never', '--name', name,
            '--label', 'com.docker.compose.project=lumiere-rebuild-test',
            '--memory', '512m', '--cpus', '1', '--log-opt', 'max-size=10m', '--log-opt', 'max-file=3',
            '-p', '127.0.0.1:16334:6333', '-e', 'QDRANT__TELEMETRY_DISABLED=true',
            '--mount', 'type=volume,source=' + volume_names['storage'] + ',target=/qdrant/storage',
            '--mount', 'type=volume,source=' + volume_names['snapshots'] + ',target=/qdrant/snapshots', image_id])
        started = True
        ready = False
        for _ in range(30):
            try:
                with urlopen('http://127.0.0.1:16334/', timeout=2) as response:
                    server = json.load(response)
                ready = True
                break
            except OSError:
                time.sleep(1)
        if not ready:
            raise RuntimeError('Dedicated Qdrant server failed readiness')
        env = {**os.environ, 'LUMIERE_SYNC_TEST_QDRANT_URL': 'http://127.0.0.1:16334',
               'LUMIERE_SYNC_TEST_GRAPH_URI': 'bolt://127.0.0.1:17687',
               'LUMIERE_SYNC_TEST_GRAPH_PASSWORD': 'test-only-lumiere-2026',
               'HF_HOME': str(ROOT / '.local-tmp/models'), 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
        projection_report = folder / 'projection-result.json'
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/run_native_postgres_sync.py'),
            '--confirm-isolated', '--resume-initialized-test-cluster', '--projection-test',
            '--projection-attempt', str(args.projection_attempt), '--report', str(projection_report)],
            env=env, capture_output=True, timeout=450,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (folder / 'worker.log').write_bytes((result.stdout or b'') + (result.stderr or b''))
        if result.returncode or not projection_report.is_file():
            raise RuntimeError('Worker lifecycle failed; see isolated worker.log')
        projection = json.loads(projection_report.read_text(encoding='utf-8'))
        if not projection['successful']:
            raise AssertionError('Worker proof failed')
        report = {'successful': True, 'container_name': name, 'container_id': container_id,
                  'image_id': image_id, 'server_version': server.get('version'), 'images_pulled': False,
                  'data_mounts_on_d': True, 'projection': projection, 'production_accessed': False,
                  'storage_backend': 'Docker named volumes inside the verified D-backed VHD',
                  'test_volumes_preserved': volume_names,
                  'scope': 'Qdrant container + native isolated PG/Neo4j + real cached model; not full Compose deployment'}
        with args.report.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps(report))
    finally:
        if started:
            logs = subprocess.run(['docker', 'logs', name], capture_output=True, timeout=15)
            (folder / 'qdrant.log').write_bytes((logs.stdout or b'') + (logs.stderr or b''))
            command(['docker', 'stop', '--time', '20', name], timeout=30)


if __name__ == '__main__':
    main()
