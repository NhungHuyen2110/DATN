"""Offline copy of the stopped original PostgreSQL volume, then read-only audit/dump of the copy.

Never starts the source, mounts it writable, edits its auth, or exports rows to stdout.
All dumps/metadata remain in ignored private D artifacts, not in Git or hosting.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'lumiere-postgres'
VOLUME = 'jewelrydatasetgenerator_lumiere_postgres_data'
FINGERPRINT = "cd /data && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-authorized-copy', action='store_true', required=True)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    folder = ROOT / '.local-tmp' / ('original-db-' + stamp)
    folder.mkdir(mode=0o700, exist_ok=False)
    def run(command, timeout=120):
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=timeout)
        if completed.returncode:
            # Never interpolate full commands/env/results into a public exception.
            raise RuntimeError('Original database operation failed (exit '+str(completed.returncode)+')')
        return completed.stdout
    if os.name == 'nt':
        identity = next(csv.reader(io.StringIO(run(['whoami','/user','/fo','csv','/nh']).decode().strip())))
        sid = identity[-1]
        if not re.fullmatch(r'S-1-[0-9-]+', sid):
            raise ValueError('Cannot identify private artifact owner')
        run(['icacls',str(folder),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F',
             '*S-1-5-18:(OI)(CI)F','*S-1-5-32-544:(OI)(CI)F'])
    source = json.loads(run(['docker','inspect',SOURCE]))[0]
    env = dict(item.split('=',1) for item in source['Config']['Env'] if '=' in item)
    if source['State']['Running'] or source['State']['ExitCode'] != 0:
        raise ValueError('Source must already be stopped cleanly; it is never stopped by this script')
    mounts = [m for m in source['Mounts'] if m['Destination']=='/var/lib/postgresql/data']
    if len(mounts)!=1 or mounts[0]['Type']!='volume' or mounts[0]['Name']!=VOLUME or env.get('PGDATA')!='/var/lib/postgresql/data':
        raise ValueError('Unexpected original storage layout')
    ids = run(['docker','ps','-q']).decode().split()
    if ids:
        for container in json.loads(run(['docker','inspect',*ids])):
            if any(m.get('Name')==VOLUME for m in container['Mounts']):
                raise ValueError('A running container uses the original volume')
    image = source['Image']
    def readonly(command):
        return run(['docker','run','--rm','--network','none','--user','0','--entrypoint','sh',
            '--mount','type=volume,source='+VOLUME+',target=/data,readonly',image,'-c',command], timeout=600)
    version = readonly('cat /data/PG_VERSION').decode().strip()
    if version!='17':
        raise ValueError('Expected PostgreSQL 17')
    readonly('test ! -e /data/postmaster.pid && test ! -L /data/pg_wal && test ! -e /data/standby.signal && test ! -e /data/recovery.signal && test -z "$(find /data/pg_tblspc -mindepth 1 -print -quit)"')
    before = readonly(FINGERPRINT).decode().split()[0]
    target_volume = 'lumiere-original-copy-' + stamp
    clone = 'lumiere-original-audit-' + stamp
    # Names are new and task-owned; refuse any pre-existing destination.
    for kind, name in (('volume',target_volume),('container',clone)):
        exists = subprocess.run(['docker',kind,'inspect',name], capture_output=True, timeout=30)
        if exists.returncode==0:
            raise ValueError('Clone destination already exists')
    run(['docker','volume','create','--label','lumiere.purpose=original-data-copy',target_volume])
    run(['docker','run','--rm','--network','none','--user','0','--entrypoint','sh',
        '--mount','type=volume,source='+VOLUME+',target=/source,readonly',
        '--mount','type=volume,source='+target_volume+',target=/target',image,'-c',
        'test -z "$(ls -A /target)" && cp -a /source/. /target/'],timeout=600)
    copied = run(['docker','run','--rm','--network','none','--user','0','--entrypoint','sh',
        '--mount','type=volume,source='+target_volume+',target=/data,readonly',image,'-c',FINGERPRINT],timeout=600).decode().split()[0]
    if copied != before or readonly(FINGERPRINT).decode().split()[0]!=before:
        raise ValueError('Physical copy/source checksums differ')
    user = env['POSTGRES_USER']
    default_db = env['POSTGRES_DB']
    run(['docker','run','-d','--name',clone,'--network','none','--memory','512m',
        '--label','lumiere.purpose=original-readonly-audit','--mount','type=volume,source='+target_volume+',target=/var/lib/postgresql/data',
        '-e','PGDATA=/var/lib/postgresql/data',image,'postgres','-c','default_transaction_read_only=on',
        '-c','listen_addresses=','-c','archive_mode=off','-c','autovacuum=off','-c','shared_buffers=32MB'])
    for _ in range(30):
        ready = subprocess.run(['docker','exec',clone,'pg_isready','-U',user,'-d',default_db],capture_output=True,timeout=5)
        if ready.returncode==0:
            break
        time.sleep(1)
    else:
        raise RuntimeError('Read-only clone not ready')
    def query(database, sql):
        return json.loads(run(['docker','exec',clone,'psql','-XqAt','-v','ON_ERROR_STOP=1','-U',user,'-d',database,
            '-c',"BEGIN READ ONLY; SET LOCAL statement_timeout='30s'; "+sql+'; COMMIT;']).decode())
    databases = query(default_db,"SELECT coalesce(json_agg(datname ORDER BY datname),'[]'::json) FROM pg_database WHERE NOT datistemplate AND datallowconn")
    report = {'source_container':SOURCE,'source_volume':VOLUME,'postgres_major':version,
        'source_volume_sha256_manifest':before,'clone_copy_sha256_manifest':copied,
        'clone_container':clone,'clone_volume':target_volume,'network':'none','published_ports':[],
        'database_transaction_mode':'read-only','databases':{},'data_rows_printed':False,
        'public_data_exported':False,'artifact_directory':str(folder.relative_to(ROOT))}
    quoted = lambda value:'"'+value.replace('"','""')+'"'
    for database in databases:
        tables = query(database,"SELECT coalesce(json_agg(tablename ORDER BY tablename),'[]'::json) FROM pg_tables WHERE schemaname='public'")
        counts = {table:query(database,'SELECT count(*) FROM public.'+quoted(table)) for table in tables}
        columns = query(database,"SELECT coalesce(json_agg(row_to_json(t)),'[]'::json) FROM (SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position) t")
        record = {'table_counts':counts,'columns':columns}
        if 'alembic_version' in tables:
            record['migration_heads'] = query(database,"SELECT coalesce(json_agg(version_num),'[]'::json) FROM alembic_version")
        if tables:
            name = hashlib.sha256(database.encode()).hexdigest()[:12] + '.dump'
            dump = run(['docker','exec',clone,'pg_dump','-U',user,'-d',database,'-Fc','--no-owner','--no-acl'],timeout=600)
            if not dump.startswith(b'PGDMP'):
                raise ValueError('Invalid logical backup format')
            (folder/name).write_bytes(dump)
            os.chmod(folder/name,0o600)
            record['backup_file'] = name
            record['backup_sha256'] = hashlib.sha256(dump).hexdigest()
            record['backup_bytes'] = len(dump)
        report['databases'][database] = record
    report['source_still_stopped'] = not json.loads(run(['docker','inspect',SOURCE]))[0]['State']['Running']
    report['source_volume_still_identical'] = readonly(FINGERPRINT).decode().split()[0] == before
    report['successful'] = report['source_still_stopped'] and report['source_volume_still_identical']
    report['completed_utc'] = datetime.now(timezone.utc).isoformat()
    (folder/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'successful':report['successful'],'artifact_directory':report['artifact_directory'],
        'source_unchanged':report['source_volume_still_identical'],'source_still_stopped':report['source_still_stopped'],
        'database_counts':{db:record['table_counts'] for db,record in report['databases'].items()},
        'clone_container':clone,'data_rows_printed':False,'public_data_exported':False}))


if __name__=='__main__':
    main()
