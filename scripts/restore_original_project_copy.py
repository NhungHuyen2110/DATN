"""Restore the audited old project into a NEW local DB, preserve all rows, verify SKU images.

No source writes, CSV seeding, account resets, data deletion, or public export.
Does not switch the serving application until the separate activation step.
"""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
COMPOSE=['docker','compose','--env-file','.env.example','-f','compose.yaml']
SOURCE_DB='lumiere_backend_test'
TARGET_DB='lumiere_test_original_data'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit',type=Path,required=True)
    parser.add_argument('--confirm-authorized-restore',action='store_true',required=True)
    args=parser.parse_args()
    audit_path=args.audit.resolve()
    if not audit_path.is_relative_to(ROOT/'.local-tmp'):
        parser.error('Private workspace audit required')
    audited=json.loads(audit_path.read_text(encoding='utf-8'))
    if not audited.get('successful') or not audited.get('source_volume_still_identical'):
        parser.error('Verified original copy required')
    origin=audited['databases'][SOURCE_DB]
    backup=(audit_path.parent/origin['backup_file']).resolve()
    if not backup.is_relative_to(audit_path.parent) or hashlib.sha256(backup.read_bytes()).hexdigest()!=origin['backup_sha256']:
        parser.error('Original backup checksum differs')
    folder=audit_path.parent/'working-copy'
    folder.mkdir(exist_ok=False)
    step=0
    def run(command, content=None, timeout=180):
        nonlocal step
        step+=1
        completed=subprocess.run(command,cwd=ROOT,input=content,capture_output=True,timeout=timeout)
        # Inherit private audit ACL; logs may contain schema diagnostics, never published.
        (folder/(str(step)+'.log')).write_bytes(completed.stdout+completed.stderr)
        if completed.returncode:
            raise RuntimeError('Restore step failed; private artifact '+str(step))
        return completed.stdout
    original=json.loads(run(['docker','inspect',audited['source_container']]))[0]
    if original['State']['Running']:
        raise ValueError('Source was restarted; review snapshot freshness before continuing')
    clone=json.loads(run(['docker','inspect',audited['clone_container']]))[0]
    if clone['Config']['Labels'].get('lumiere.purpose')!='original-readonly-audit' or clone['HostConfig']['NetworkMode']!='none':
        raise ValueError('Wrong read-only audit container')
    source_env=dict(v.split('=',1) for v in original['Config']['Env'] if '=' in v)
    source_user=source_env['POSTGRES_USER']
    pgid=run(COMPOSE+['ps','-q','postgres']).decode().strip()
    target=json.loads(run(['docker','inspect',pgid]))[0]
    if target['Config']['Labels'].get('com.docker.compose.project')!='lumiere-rebuild-test' or target['Config']['Labels'].get('com.docker.compose.service')!='postgres':
        raise ValueError('Wrong isolated target server')
    values=dict(v.split('=',1) for v in target['Config']['Env'] if '=' in v)
    if values.get('POSTGRES_DB')!='lumiere_test_rebuild':
        raise ValueError('Unexpected target server namespace')
    target_user=values['POSTGRES_USER']
    def query(container,user,database,sql):
        return json.loads(run(['docker','exec',container,'psql','-XqAt','-v','ON_ERROR_STOP=1','-U',user,'-d',database,
            '-c',"BEGIN READ ONLY; SET LOCAL TIME ZONE 'UTC'; SET LOCAL statement_timeout='30s'; "+sql+'; COMMIT;']).decode())
    if query(pgid,target_user,'postgres',"SELECT count(*) FROM pg_database WHERE datname='lumiere_test_original_data'")!=0:
        raise ValueError('Target exists; preserve it without automatic overwrite')
    quote=lambda value:'"'+value.replace('"','""')+'"'
    def snapshot(container,user,database):
        result={}
        for table in origin['table_counts']:
            checksum="SELECT json_build_object('rows',count(*),'sha256',encode(sha256(convert_to(coalesce(string_agg(s,E'\\n' ORDER BY s COLLATE \"C\"),''),'UTF8')),'hex')) FROM (SELECT row_to_json(t)::text AS s FROM public."+quote(table)+' t) src'
            result[table]=query(container,user,database,checksum)
        return result
    before=snapshot(audited['clone_container'],source_user,SOURCE_DB)
    run(['docker','exec',pgid,'createdb','-U',target_user,TARGET_DB])
    run(['docker','exec','-i',pgid,'pg_restore','-U',target_user,'-d',TARGET_DB,'--no-owner','--no-acl','--exit-on-error'],backup.read_bytes())
    if snapshot(pgid,target_user,TARGET_DB)!=before:
        raise ValueError('Restored row digests differ before migration')
    run(COMPOSE+['run','--rm','--no-deps','-e','POSTGRES_DB='+TARGET_DB,'-e','PRODUCT_INDEX_SYNC_ENABLED=false',
        'business-api','alembic','upgrade','head'])
    after=snapshot(pgid,target_user,TARGET_DB)
    if any(after[table]!=before[table] for table in before if table!='alembic_version'):
        raise ValueError('Existing rows changed during additive migration')
    heads=query(pgid,target_user,TARGET_DB,"SELECT json_agg(version_num) FROM alembic_version")
    if heads!=['20261121_0009']:
        raise ValueError('Migration head differs')
    # Match original database SKUs to the actual local image assets, not placeholders.
    skus=query(pgid,target_user,TARGET_DB,"SELECT json_agg(sku ORDER BY id) FROM products")
    source_map=(ROOT/'frontend/assets/js/product-image-map.js').read_text(encoding='utf-8-sig')
    mapping=json.loads(re.search(r'window\.LUMIERE_PRODUCT_IMAGES\s*=\s*(\{.*?\});',source_map,re.S).group(1))
    files={p.relative_to(ROOT/'frontend').as_posix():p for p in (ROOT/'frontend/assets/images/products').iterdir() if p.is_file()}
    missing=[]
    for sku in skus:
        path=mapping.get(sku.upper(),'').lstrip('/')
        if path not in files:
            missing.append(sku)
    if missing:
        raise ValueError('Some original product images need reconciliation; no activation performed')
    recovery=ROOT/'.local-tmp/recovery/original-data-20261122'
    recovery.mkdir(mode=0o700,parents=True,exist_ok=False)
    if os.name=='nt':
        identity=next(csv.reader(io.StringIO(run(['whoami','/user','/fo','csv','/nh']).decode().strip())))
        sid=identity[-1]
        if not re.fullmatch(r'S-1-[0-9-]+',sid):
            raise ValueError('Cannot identify private backup owner')
        run(['icacls',str(recovery),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F',
             '*S-1-5-18:(OI)(CI)F','*S-1-5-32-544:(OI)(CI)F'])
    if os.name=='posix':
        os.chown(recovery,0,10001); os.chmod(recovery,0o750)
    dump=run(['docker','exec',pgid,'pg_dump','-U',target_user,'-d',TARGET_DB,'-Fc','--no-owner','--no-acl'])
    if not dump.startswith(b'PGDMP'):
        raise ValueError('Invalid migrated backup')
    (recovery/'before-activation.dump').write_bytes(dump)
    reference={'version':1,'environment':'test','database_name':TARGET_DB,'database_host':'postgres',
        'database_port':5432,'format':'pg_dump_custom','backup_file':'before-activation.dump',
        'backup_sha256':hashlib.sha256(dump).hexdigest()}
    (recovery/'backup-reference.json').write_text(json.dumps(reference),encoding='utf-8')
    if os.name=='posix':
        for name in ('before-activation.dump','backup-reference.json'):
            os.chown(recovery/name,0,10001); os.chmod(recovery/name,0o440)
    report={'successful':True,'source_database':SOURCE_DB,'target_database':TARGET_DB,
        'source_container_untouched':True,'all_existing_table_row_digests_preserved':True,
        'original_counts':origin['table_counts'],'migration_heads':heads,'matched_local_product_images':len(skus),
        'missing_images':0,'backup_sha256':reference['backup_sha256'],'serving_application_switched':False,
        'accounts_reset':False,'public_data_exported':False}
    (folder/'restore.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'successful':True,'private_report':str((folder/'restore.json').relative_to(ROOT)),
        'products':len(skus),'matched_images':len(skus),'customers_accounts':origin['table_counts']['users'],
        'orders':origin['table_counts']['orders'],'existing_rows_preserved':True,'serving_application_switched':False}))


if __name__=='__main__': main()
