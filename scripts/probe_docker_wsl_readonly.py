"""Read-only process/socket/disk probes inside Docker's own WSL distribution."""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists')
    probes = {'process_names': 'ps -o pid,comm', 'docker_cli': 'command -v docker',
              'docker_socket': 'ls -l /var/run/docker.sock', 'docker_disk': 'df -h /var/lib/docker'}
    results = {'changes_made': False, 'distro': 'docker-desktop', 'probes': {}}
    for name, command in probes.items():
        try:
            result = subprocess.run(['wsl', '--distribution', 'docker-desktop', '--exec', 'sh', '-c', command],
                                    capture_output=True, timeout=12)
            results['probes'][name] = {'returncode': result.returncode,
                'stdout': (result.stdout or b'').decode('utf-8', errors='replace').replace('\x00', '')[:2500],
                'stderr': (result.stderr or b'').decode('utf-8', errors='replace').replace('\x00', '')[:300]}
        except (OSError, subprocess.TimeoutExpired) as exc:
            results['probes'][name] = {'error_type': type(exc).__name__}
    with args.report.open('x', encoding='utf-8') as handle:
        json.dump(results, handle, indent=2)
    print(json.dumps(results))


if __name__ == '__main__':
    main()
