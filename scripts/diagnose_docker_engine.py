"""Read-only Docker/WSL diagnosis; does not restart, reset, move disks or export raw logs."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import shutil
import subprocess


def bounded(command, timeout=12):
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout)
        return {'returncode': result.returncode, 'stdout': (result.stdout or b'').decode('utf-8', errors='replace').replace('\x00', '')[:1200],
                'stderr': (result.stderr or b'').decode('utf-8', errors='replace').replace('\x00', '')[:500]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'error_type': type(exc).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists')
    home = Path.home()
    report = {'disk_free_gib': {drive: round(shutil.disk_usage(drive + ':\\').free / 1024**3, 2) for drive in ('C', 'D')},
              'actions': 'read_only_no_restart_no_reset_no_disk_move'}
    report['wsl_list'] = bounded(['wsl', '--list', '--verbose'])
    report['docker_contexts'] = bounded(['docker', 'context', 'ls', '--format', '{{.Name}}'])
    report['desktop_server'] = bounded(['docker', '--context', 'desktop-linux', 'version', '--format', '{{json .Server.Version}}'])
    report['default_server'] = bounded(['docker', '--context', 'default', 'version', '--format', '{{json .Server.Version}}'])
    selected = []
    def settings(value, prefix=''):
        if isinstance(value, dict):
            for key, item in value.items():
                path = prefix + '.' + key
                if re.search(r'datafolder|diskimagelocation|wslengineenabled|windowscontainers', key, re.I):
                    scalar = item.get('value') if isinstance(item, dict) else item
                    if isinstance(scalar, (str, int, bool)):
                        selected.append({'setting': path, 'value': str(scalar)[:500]})
                settings(item, path)
        elif isinstance(value, list):
            for item in value:
                settings(item, prefix)
    for filename in ('settings-store.json', 'settings.json'):
        path = home / 'AppData/Roaming/Docker' / filename
        if path.is_file():
            settings(json.loads(path.read_text(encoding='utf-8-sig')))
    report['storage_settings'] = selected
    categories = {'space': r'no space left|not enough space|disk full', 'permission': r'access denied|permission denied',
                  'wsl_error': r'WSL_E_|Wsl/Service|0x80370102', 'timeout': r'timed out|timeout',
                  'engine_unavailable': r'engine.*(failed|not running)|cannot connect|failed to start',
                  'pipe_error': r'pipe.*(failed|not found|cannot)'}
    summaries = []
    logs = home / 'AppData/Local/Docker/log/host'
    for filename in ('com.docker.backend.exe.log', 'Docker Desktop.exe.log', 'docker-desktop.exe.log'):
        path = logs / filename
        if path.is_file():
            with path.open('rb') as handle:
                handle.seek(max(0, path.stat().st_size - 256000))
                tail = handle.read().decode('utf-8', errors='replace')
            counts = {key: len(re.findall(pattern, tail, re.I)) for key, pattern in categories.items()}
            summaries.append({'file': filename, 'tail_bytes': min(path.stat().st_size, 256000),
                              'category_counts': counts, 'raw_log_exported': False})
    report['log_summaries'] = summaries
    with args.report.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
