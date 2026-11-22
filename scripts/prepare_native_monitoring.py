"""Download pinned official OSS monitoring archives to D and verify SHA256 before extraction."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.local-tmp/native-monitoring'
PROMETHEUS_URL = 'https://github.com/prometheus/prometheus/releases/download/v3.7.3/prometheus-3.7.3.windows-amd64.zip'
PROMETHEUS_SHA256 = 'a775b4718910cacfa5c80e97c39c4666818640afef59bc0c0d96b5398cc84531'
GRAFANA_URL = 'https://dl.grafana.com/oss/grafana_12.2.1_18966576697_windows_amd64.zip'


def download(url, destination):
    if destination.exists():
        return
    result = subprocess.run(['curl.exe', '--fail', '--location', '--retry', '1', '--connect-timeout', '10',
                             '--max-time', '300', '--output', str(destination), url], capture_output=True, timeout=340)
    if result.returncode:
        raise RuntimeError('Official download failed: ' + destination.name)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def extract(archive, destination):
    if destination.exists():
        raise ValueError('Refusing to overwrite extracted binaries')
    with zipfile.ZipFile(archive) as package:
        for item in package.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError('Archive path escapes intended directory')
        package.extractall(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists')
    BASE.mkdir(parents=True, exist_ok=True)
    grafana_checksum = BASE / 'grafana-official.sha256'
    download(GRAFANA_URL + '.sha256', grafana_checksum)
    match = re.search(r'\b[a-fA-F0-9]{64}\b', grafana_checksum.read_text())
    if not match:
        raise ValueError('Official Grafana checksum could not be parsed')
    tools = [('prometheus', PROMETHEUS_URL, PROMETHEUS_SHA256), ('grafana', GRAFANA_URL, match.group().lower())]
    report = {'sources': [], 'system_installation': False, 'services_started': False}
    for name, url, expected in tools:
        archive = BASE / (name + '.zip')
        download(url, archive)
        actual = digest(archive)
        if actual != expected:
            raise ValueError(name + ' checksum mismatch; archive preserved, not executed')
        target = BASE / 'binaries' / name
        extract(archive, target)
        report['sources'].append({'tool': name, 'url': url, 'sha256': actual, 'extracted_to': str(target)})
        print(json.dumps({'verified': name, 'sha256': actual}), flush=True)
    with args.report.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)


if __name__ == '__main__':
    main()
