"""Prepare new private demo hosting configuration locally; no network, purchase or deployment."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', required=True)
    parser.add_argument('--directory', type=Path, default=ROOT / 'private')
    parser.add_argument('--preview', action='store_true', help='Allow an .invalid hostname for local config validation')
    args = parser.parse_args()
    domain = args.domain.lower()
    if (len(domain) > 253 or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', domain)
            or domain.endswith('.invalid') and not args.preview):
        parser.error('DNS hostname required; no URL, port, path, whitespace or template characters')
    folder = args.directory.resolve()
    if folder != ROOT / 'private' and not folder.is_relative_to(ROOT / '.local-tmp'):
        parser.error('Use this checkout private directory or the ignored local preview area')
    if folder.exists():
        parser.error('Never overwrite existing credentials/configuration')
    prometheus = (ROOT / 'infra/prometheus/prometheus.yml').read_text(encoding='utf-8-sig')
    old = 'credentials: test-only-local-scrape-token'
    if prometheus.count(old) != 2:
        parser.error('Unexpected metrics template; review before generating')
    prometheus = prometheus.replace(old, 'credentials_file: /run/secrets/metrics.token')
    values = {
        'DEMO_DOMAIN': domain, 'POSTGRES_DB': 'lumiere_test_demo_hosting', 'POSTGRES_USER': 'lumiere_demo',
        'POSTGRES_PASSWORD': secrets.token_urlsafe(32), 'NEO4J_PASSWORD': secrets.token_urlsafe(32),
        'GRAFANA_ADMIN_PASSWORD': secrets.token_urlsafe(32), 'LUMIERE_METRICS_TOKEN': secrets.token_urlsafe(32),
        'LUMIERE_AI_DIAGNOSTICS_TOKEN': secrets.token_urlsafe(32), 'PUBLIC_PORT': '18080',
        'MODEL_CACHE_PATH': './private/models', 'QDRANT_COLLECTION': 'jewelry_products_v_c0efd814ee4f',
        'EMBEDDING_REVISION': 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42',
        'SMTP_HOST': '', 'SMTP_PORT': '587', 'SMTP_USER': '', 'SMTP_PASSWORD': '', 'SMTP_FROM': ''}
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, content, mode in (
        ('demo.env', '\n'.join(key + '=' + value for key, value in values.items()) + '\n', 0o600),
        ('metrics.token', values['LUMIERE_METRICS_TOKEN'] + '\n', 0o444),
        ('prometheus.yml', prometheus, 0o644)):
        path = folder / name
        with path.open('x', encoding='utf-8') as output:
            output.write(content)
        os.chmod(path, mode)
    print(json.dumps({'prepared':True, 'directory':str(folder), 'domain':domain,
        'credentials_printed':False, 'purchased':False, 'deployed':False,
        'note':'Linux file modes applied; Windows ACL verification is separate. SMTP/model/DB/backup still need setup.'}))


if __name__ == '__main__':
    main()
