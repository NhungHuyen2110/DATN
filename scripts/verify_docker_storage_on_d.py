"""Read-only verification of D storage and exact pre-move Docker identities."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def command(arguments, timeout=15):
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('Docker verification command failed: ' + arguments[1])
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists')
    logical = Path(r'C:\Users\Admin\AppData\Local\Docker\wsl\disk')
    physical = ROOT / '.local-tmp/docker-desktop-data/disk'
    if logical.resolve(strict=True) != physical.resolve(strict=True) or not os.path.samefile(
            logical / 'docker_data.vhdx', physical / 'docker_data.vhdx'):
        raise ValueError('Docker data path is not physically redirected to the approved D directory')
    before = json.loads((ROOT / '.local-tmp/docker-recovery/20261122/before-state.json').read_text(encoding='utf-8-sig'))
    version = None
    for _ in range(12):
        try:
            version = json.loads(command(['docker', 'version', '--format', '{{json .Server.Version}}'], timeout=5))
            if version:
                break
        except (RuntimeError, subprocess.TimeoutExpired, ValueError):
            time.sleep(2)
    if not version:
        raise RuntimeError('Docker Server did not recover; original C directory retained')
    after = {'container_ids': sorted(command(['docker', 'container', 'ls', '-aq', '--no-trunc']).splitlines()),
             'image_ids': sorted(set(command(['docker', 'image', 'ls', '-q', '--no-trunc']).splitlines())),
             'volume_names': sorted(command(['docker', 'volume', 'ls', '-q']).splitlines()),
             'running_container_ids': sorted(command(['docker', 'container', 'ls', '-q', '--no-trunc']).splitlines())}
    for key in after:
        if sorted(before[key]) != after[key]:
            raise ValueError('Pre/post-move Docker identities differ for ' + key + '; originals retained')
    (ROOT / '.local-tmp/docker-recovery/20261122/after-state.json').write_text(json.dumps(after, indent=2), encoding='utf-8')
    report = {'successful': True, 'verified_utc': datetime.now(timezone.utc).isoformat(),
              'server_version': version, 'logical_path': str(logical), 'physical_path': str(physical),
              'same_file_identity_through_junction': True,
              'container_ids_preserved': len(after['container_ids']), 'image_ids_preserved': len(after['image_ids']),
              'volume_names_preserved': len(after['volume_names']),
              'running_container_state_preserved': True,
              'independent_backup': str(ROOT / '.local-tmp/docker-recovery/20261122/docker_data.before-move.vhdx'),
              'original_c_directory_retained_for_final_cleanup': True,
              'method': 'NTFS directory junction; Docker logical setting remains C, actual data VHD is D'}
    with args.report.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
