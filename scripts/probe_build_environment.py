"""Read-only, bounded prerequisite probe; never reads .env or changes services."""
import importlib.metadata as metadata
import json
import shutil
import subprocess
from pathlib import Path

result = {'tools': {name: shutil.which(name) for name in ('docker', 'node')}}
result['disk_free_gib'] = {drive: round(shutil.disk_usage(drive + ':\\').free / 1024**3, 2)
                           for drive in ('C', 'D')}
settings = Path.home() / 'AppData/Roaming/Docker/settings-store.json'
if settings.is_file():
    try:
        values = json.loads(settings.read_text(encoding='utf-8-sig'))
        result['docker_storage_settings'] = {key: values.get(key) for key in
                                             ('diskImageLocation', 'dataFolder', 'wslEngineEnabled', 'useWindowsContainers')
                                             if key in values}
    except (OSError, ValueError):
        result['docker_storage_settings'] = 'unavailable'
for name in ('prometheus-client', 'sentence-transformers', 'torch', 'PyYAML', 'pytest', 'uvicorn'):
    try:
        result[name] = metadata.version(name)
    except metadata.PackageNotFoundError:
        result[name] = None
try:
    process = subprocess.run(['docker', 'version', '--format', '{{json .Server}}'],
                             capture_output=True, text=True, timeout=12)
    result['docker_server'] = {'returncode': process.returncode, 'output': process.stdout[:1500],
                               'error': process.stderr[:500]}
except (OSError, subprocess.TimeoutExpired) as exc:
    result['docker_server'] = {'error_type': type(exc).__name__}
if result['docker_server'].get('error_type'):
    try:
        process = subprocess.run(['docker', '--context', 'default', 'version', '--format', '{{json .Server.Version}}'],
                                 capture_output=True, text=True, timeout=12)
        result['default_context_server'] = {'returncode': process.returncode, 'output': process.stdout[:200],
                                            'error': process.stderr[:300]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        result['default_context_server'] = {'error_type': type(exc).__name__}
print(json.dumps(result, indent=2))
