"""Check the staged demo commit for excluded artifacts and obvious credentials without printing values.

Heuristic local preflight, not a replacement for dependency or repository security scans.
Reads Git index blobs, never .env contents or credential-manager secrets.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?\n'),
    'github_token': re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b'),
    'aws_access_key': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'api_key': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{35,}\b'),
    'database_password': re.compile(r'postgres(?:ql)?(?:\+psycopg)?://[^\s\'"/:]+:([^@\s\'"/]+)@', re.I),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Preserve reports; choose a new file')
    def git(*arguments):
        return subprocess.check_output(['git', *arguments], cwd=ROOT, timeout=30)
    paths = [value.decode('utf-8') for value in git('diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z').split(b'\0') if value]
    findings = []
    for name in paths:
        path = Path(name)
        private_path = any(part in {'.local-tmp', '.aws', '.codex', '.agents', '.venv', 'node_modules'} for part in path.parts)
        excluded = (private_path or path.suffix.lower() in {'.bak', '.dump', '.vhd', '.vhdx', '.key', '.pem'} or
                    (path.name.startswith('.env') and path.name != '.env.example') or
                    name in {'output/customers.csv', 'output/customer_behavior.csv', 'output/orders.csv', 'output/order_details.csv', 'data/suppliers.json'})
        if excluded:
            findings.append({'path': name, 'kind': 'excluded_release_artifact'})
            continue
        content = git('show', ':' + name)
        if b'\x00' in content[:8192]:
            continue
        source = content.decode('utf-8-sig', errors='replace')
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(source):
                if kind == 'database_password' and any(value in match.group(1).lower() for value in
                        ('test', 'synthetic', 'placeholder', '${', 'example')):
                    continue
                findings.append({'path': name, 'line': source.count('\n', 0, match.start()) + 1, 'kind': kind})
    report = {'successful': bool(paths) and not findings, 'staged_files_checked': len(paths), 'findings': findings,
              'values_printed': False, 'scope': 'staged added/modified blobs; heuristic patterns and private artifact paths only',
              'historical_repository_content_scanned': False, 'dependency_vulnerabilities_scanned': False}
    with args.report.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
    print(json.dumps(report))
    return 0 if report['successful'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
