"""Restore only the existing VNPAY configuration into an ignored local env file."""
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
KEYS = ('VNPAY_ENABLED', 'VNPAY_TMN_CODE', 'VNPAY_HASH_SECRET', 'VNPAY_RETURN_URL')


def main():
    values = dotenv_values(ROOT / '.env')
    selected = {key: values.get(key) or '' for key in KEYS}
    url = urlsplit(selected['VNPAY_RETURN_URL'])
    if (selected['VNPAY_ENABLED'].lower() != 'true'
            or not re.fullmatch('[A-Za-z0-9]{8}', selected['VNPAY_TMN_CODE'])
            or not selected['VNPAY_HASH_SECRET'] or url.scheme != 'https' or not url.hostname
            or url.username or url.password or url.query or url.fragment
            or url.path not in {'/payments/vnpay/return', '/api/payments/vnpay/return'}
            or any('\n' in value or '\r' in value or '\x00' in value for value in selected.values())):
        raise ValueError('Original VNPAY settings are incomplete or invalid; no values printed or changed')
    folder = ROOT / '.local-tmp/local-commerce'
    folder.mkdir(exist_ok=True)
    target = folder / 'vnpay.env'
    content = '\n'.join(key + '=' + selected[key] for key in KEYS) + '\n'
    if target.exists():
        if target.read_text(encoding='utf-8') != content:
            raise ValueError('A different private configuration exists; refusing to overwrite')
    else:
        with target.open('x', encoding='utf-8') as stream:
            stream.write(content)
    print(json.dumps({'successful': True, 'selected_keys': list(KEYS), 'source_env_modified': False,
                      'secret_values_printed': False, 'public_callback_reachability_verified': False}))


if __name__ == '__main__':
    main()
