"""Back up and add review schema only to the two explicit local test copies."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.host_process import run_bounded
PROJECT = 'lumiere-rebuild-test'
TARGETS = {'qa': 'lumiere_test_ai_acceptance', 'serving-copy': 'lumiere_test_original_data'}
COMPOSE = ['docker', 'compose', '--env-file', '.env.example', '-p', PROJECT,
           '-f', 'compose.yaml', '-f', 'compose.original-data.yaml']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', choices=TARGETS, required=True)
    parser.add_argument('--confirm-local-test', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Preserve reports; choose a new path')
    private = ROOT / '.local-tmp/original-db-20261122-014434'
    if not json.loads((private / 'working-copy/restore.json').read_text())['successful']:
        raise ValueError('Verified private original-copy recovery record required')
    folder = private / ('review-schema-' + args.database + '-20261122')
    folder.mkdir(exist_ok=False)  # Inherits the protected Admin/SYSTEM ACL.
    def run(command, content=None):
        result = run_bounded(command, cwd=ROOT, input=content, timeout=180)
        if result.returncode:
            (folder / 'failure.log').write_bytes(result.stdout + result.stderr)
            raise RuntimeError('Review migration failed; private log retained')
        return result.stdout
    pg = run(COMPOSE + ['ps', '-q', 'postgres']).decode().strip()
    details = json.loads(run(['docker', 'inspect', pg]))[0]
    labels = details['Config']['Labels']
    if labels.get('com.docker.compose.project') != PROJECT or labels.get('com.docker.compose.service') != 'postgres':
        raise ValueError('Wrong PostgreSQL container')
    environment = dict(value.split('=', 1) for value in details['Config']['Env'] if '=' in value)
    user, target = environment['POSTGRES_USER'], TARGETS[args.database]
    def sql(statement):
        return run(['docker', 'exec', pg, 'psql', '-XqAt', '-v', 'ON_ERROR_STOP=1',
                    '-U', user, '-d', target, '-c', statement]).decode().strip()
    revision = sql('BEGIN READ ONLY; SELECT version_num FROM alembic_version; COMMIT;')
    if revision not in {'20261121_0009', '20261122_0010'}:
        raise ValueError('Unexpected review-migration baseline')
    tables = json.loads(sql("BEGIN READ ONLY; SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables WHERE schemaname='public'; COMMIT;"))
    tables = [table for table in tables if table != 'alembic_version']
    def digests():
        result = {}
        for table in tables:
            if not re.fullmatch('[a-z_]+', table):
                raise ValueError('Unexpected source table identifier')
            statement = ("BEGIN READ ONLY; SET LOCAL TIME ZONE 'UTC'; SELECT json_build_object('rows',count(*),'sha256',"
                         "encode(sha256(convert_to(coalesce(string_agg(s,E'\\n' ORDER BY s COLLATE \"C\"),''),'UTF8')),'hex')) "
                         'FROM (SELECT row_to_json(t)::text AS s FROM public."' + table + '" t) source; COMMIT;')
            result[table] = json.loads(sql(statement))
        return result
    before = digests()
    archive = run(['docker', 'exec', pg, 'pg_dump', '-U', user, '-d', target, '-Fc', '--no-owner', '--no-acl'])
    if not archive.startswith(b'PGDMP'):
        raise ValueError('Expected a PostgreSQL custom backup')
    dump = folder / 'before-reviewed-attributes.dump'
    dump.write_bytes(archive)
    reference = {'version': 1, 'environment': 'test', 'database_name': target,
                 'database_host': 'postgres', 'database_port': 5432, 'format': 'pg_dump_custom',
                 'backup_file': dump.name, 'backup_sha256': hashlib.sha256(archive).hexdigest()}
    reference_path = folder / 'backup-reference.json'
    reference_path.write_text(json.dumps(reference, indent=2), encoding='utf-8')
    from shared.recovery import validate_backup_reference
    validate_backup_reference(reference_path, 'test', 'postgres', 5432, target)
    (folder / 'before-table-digests.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
    run(COMPOSE + ['run', '--rm', '--no-deps', '-T', '-e', 'POSTGRES_DB=' + target,
                   '-e', 'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED=false', 'business-api',
                   'alembic', 'upgrade', '20261122_0010'])
    after = digests()
    (folder / 'after-table-digests.json').write_text(json.dumps(after, indent=2), encoding='utf-8')
    if before != after:
        raise ValueError('Existing rows changed during migration; preserve evidence and do not restore over user work')
    report = {'successful': True, 'database': target, 'revision_before': revision,
              'revision_after': sql('SELECT version_num FROM alembic_version'),
              'preexisting_tables_preserved': len(tables), 'backup_sha256': reference['backup_sha256'],
              'private_backup_directory': str(folder.relative_to(ROOT)),
              'private_dump_created': True, 'private_rows_published': False,
              'verified_utc': datetime.now(timezone.utc).isoformat()}
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
