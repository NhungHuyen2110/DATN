"""Validate a local custom-format PostgreSQL backup reference before optional worker writes."""
import hashlib
import json
from pathlib import Path


def validate_backup_reference(reference, environment, database_host, database_port, database_name):
    path = Path(reference).resolve()
    record = json.loads(path.read_text(encoding='utf-8-sig'))
    canonical_host = lambda value: 'loopback' if value in {'127.0.0.1', 'localhost', '::1'} else value
    if (record.get('version') != 1 or record.get('environment') != environment
            or record.get('database_name') != database_name
            or canonical_host(record.get('database_host')) != canonical_host(database_host)
            or record.get('database_port') != database_port or record.get('format') != 'pg_dump_custom'):
        raise ValueError('Backup target/environment fingerprint differs')
    relative = Path(record['backup_file'])
    backup = (path.parent / relative).resolve()
    if relative.is_absolute() or not backup.is_relative_to(path.parent) or not backup.is_file():
        raise ValueError('Backup file must remain inside the recovery reference directory')
    digest = hashlib.sha256()
    with backup.open('rb') as handle:
        if handle.read(5) != b'PGDMP':
            raise ValueError('Expected a PostgreSQL custom-format backup')
        handle.seek(0)
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != record['backup_sha256']:
        raise ValueError('Backup checksum differs')
    return {'verified': True, 'database_name': database_name, 'backup_sha256': digest.hexdigest()}
