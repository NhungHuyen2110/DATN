"""Dry-run by default; bootstrap a NEW demo catalog with backup and no overwrite.

--local-lab rehearses in an additional named DB on the owned test PostgreSQL.
Hosting mode requires only its new empty PostgreSQL service to be running first.
Never reuses the current five-product DB or graph/vector volumes for this catalog.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'AI'))
from knowledge_graph.csv_validation import validate_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-demo', action='store_true')
    parser.add_argument('--local-lab', action='store_true')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Choose a new report')
    source = ROOT / 'output/products_ai.csv'
    validated = validate_csv(source, ROOT / 'data')
    if validated['errors'] or len(validated['records']) != 500:
        parser.error('Expected the completely validated 500-product seed')
    result = {'successful':False, 'mode':'apply' if args.apply else 'dry-run', 'products':500,
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(), 'production_accessed':False}
    if not args.apply:
        result.update(successful=True, database_accessed=False)
    else:
        if not args.confirm_demo:
            parser.error('--apply requires --confirm-demo')
        if os.name == 'posix' and os.geteuid() != 0:
            parser.error('Run apply as the server administrator to assign the private backup read group safely')
        env_file = ROOT / ('.env.example' if args.local_lab else 'private/demo.env')
        compose = ['docker','compose','--env-file',str(env_file),'-f','compose.yaml']
        if not args.local_lab:
            compose.extend(['-f','compose.hosting.yaml'])
        recovery = ROOT / ('.local-tmp/recovery/hosting-bootstrap-20261122' if args.local_lab else 'private/recovery')
        if recovery.exists():
            parser.error('Preserve existing recovery/data; no automatic reseeding')
        def run(command, content=None, timeout=180):
            completed = subprocess.run(command, cwd=ROOT, input=content, capture_output=True, timeout=timeout)
            if completed.returncode:
                raise RuntimeError('Demo bootstrap command failed (exit '+str(completed.returncode)+')')
            return completed.stdout
        target_db = 'lumiere_test_demo_hosting'
        cid = run(compose+['ps','-q','postgres']).decode().strip()
        container = json.loads(run(['docker','inspect',cid]))[0]
        values = dict(v.split('=',1) for v in container['Config']['Env'] if '=' in v)
        labels = container['Config']['Labels']
        expected_project = 'lumiere-rebuild-test' if args.local_lab else 'lumiere-demo-hosting'
        expected_db = 'lumiere_test_rebuild' if args.local_lab else target_db
        if labels.get('com.docker.compose.project') != expected_project or labels.get('com.docker.compose.service') != 'postgres' or values.get('POSTGRES_DB') != expected_db:
            raise ValueError('Wrong PostgreSQL project/database')
        user = values['POSTGRES_USER']
        if args.local_lab:
            exists = run(compose+['exec','-T','postgres','psql','-U',user,'-d','postgres','-Atc',
                "SELECT count(*) FROM pg_database WHERE datname='lumiere_test_demo_hosting'"]).decode().strip()
            if exists != '0':
                raise ValueError('Rehearsal DB exists: preserved without reseeding')
            run(compose+['exec','-T','postgres','createdb','-U',user,target_db])
        else:
            tables = run(compose+['exec','-T','postgres','psql','-U',user,'-d',target_db,'-Atc',
                "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"]).decode().strip()
            if tables != '0':
                raise ValueError('Hosting target must be newly created with no tables')
        base = compose+['run','--rm','--no-deps','-e','POSTGRES_DB='+target_db,
                        '-e','PRODUCT_INDEX_SYNC_ENABLED=false']
        run(base+['business-api','alembic','upgrade','head'])
        recovery.mkdir(mode=0o700, parents=True, exist_ok=False)
        if os.name == 'posix':
            os.chown(recovery, 0, 10001)
            os.chmod(recovery, 0o750)
        def backup(name):
            content = run(compose+['exec','-T','postgres','pg_dump','-U',user,'-d',target_db,'-Fc'])
            if not content.startswith(b'PGDMP'):
                raise ValueError('Valid custom-format backup required')
            (recovery/name).write_bytes(content)
            os.chmod(recovery/name,0o600)
            if os.name == 'posix':
                os.chown(recovery/name, 0, 10001)
                os.chmod(recovery/name, 0o440)
            record = {'version':1,'environment':'test','database_host':'postgres','database_port':5432,
                      'database_name':target_db,'format':'pg_dump_custom','backup_file':name,
                      'backup_sha256':hashlib.sha256(content).hexdigest()}
            (recovery/'backup-reference.json').write_text(json.dumps(record),encoding='utf-8')
            os.chmod(recovery/'backup-reference.json',0o600)
            if os.name == 'posix':
                os.chown(recovery/'backup-reference.json', 0, 10001)
                os.chmod(recovery/'backup-reference.json', 0o440)
            return record['backup_sha256']
        result['empty_database_backup_sha256'] = backup('before-seed.dump')
        passwords = {role:secrets.token_urlsafe(24) for role in ('customer','admin','staff')}
        (recovery/'demo-accounts.json').write_text(json.dumps({role:{'email':'demo-'+role+'@example.com','password':pw}
            for role,pw in passwords.items()}),encoding='utf-8')
        os.chmod(recovery/'demo-accounts.json',0o600)
        payload = json.dumps({'confirm_demo':True,'records':validated['records'],'passwords':passwords}).encode()
        seeded = json.loads(run(base+['-v',str(recovery)+':/recovery:ro','business-api','python','-B','-c',
            (ROOT/'backend/scripts/bootstrap_demo_seed.py').read_text(encoding='utf-8')], payload))
        counts = run(compose+['exec','-T','postgres','psql','-U',user,'-d',target_db,'-Atc',
            'SELECT (SELECT count(*) FROM products),(SELECT count(*) FROM users),(SELECT count(*) FROM orders)']).decode().strip()
        if counts != '500|3|0' or not seeded['successful']:
            raise ValueError('Independent SQL counts differ')
        result.update(seeded, successful=True, independent_sql_counts=counts,
            seeded_database_backup_sha256=backup('after-seed.dump'),
            previous_five_product_database_preserved=args.local_lab,
            credentials_file=str((recovery/'demo-accounts.json').relative_to(ROOT)),
            note='No graph/vector activation; use separate hosting project volumes for this catalog')
    result['completed_utc'] = datetime.now(timezone.utc).isoformat()
    with args.report.open('x',encoding='utf-8') as output:
        json.dump(result,output,indent=2)
    print(json.dumps(result))
    return 0 if result['successful'] else 1


if __name__ == '__main__':
    main()
