"""Read-only validation of the activated original-data copy; exports aggregate evidence only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.request import urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.host_process import run_bounded
COMPOSE = ['docker','compose','--env-file','.env.example','-f','compose.yaml','-f','compose.original-data.yaml']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--semantic', action='store_true')
    parser.add_argument('--wait-sync-seconds', type=int, default=0)
    parser.add_argument('--allow-session-lifecycle', action='store_true',
                        help='Allow login/logout additions/removals after activation; surviving sessions must match')
    args = parser.parse_args()
    if args.report.exists() or not args.audit.resolve().is_relative_to(ROOT/'.local-tmp'):
        parser.error('New report and private local audit required')
    audit = json.loads(args.audit.read_text(encoding='utf-8'))
    restored = json.loads((args.audit.parent/'working-copy/restore.json').read_text())
    if not audit.get('successful') or not restored.get('successful'):
        parser.error('Verified backup and restore required')
    def run(command, timeout=120):
        result = run_bounded(command,cwd=ROOT,timeout=timeout)
        if result.returncode:
            # Inherit the private audit directory ACL; do not expose command/env details.
            failure=args.audit.parent/('verification-failure-'+str(time.time_ns())+'.log')
            failure.write_bytes(result.stdout+result.stderr)
            raise RuntimeError('Verification command failed; no raw private output exported')
        return result.stdout
    def inspect(name):
        return json.loads(run(['docker','inspect',name]))[0]
    source = inspect(audit['source_container'])
    if source['State']['Running']:
        raise ValueError('Original must remain stopped')
    service = inspect(run(COMPOSE+['ps','-q','business-api']).decode().strip())
    env = dict(v.split('=',1) for v in service['Config']['Env'] if '=' in v)
    if env.get('POSTGRES_DB') != 'lumiere_test_original_data':
        raise ValueError('Serving application has not switched')
    target = inspect(run(COMPOSE+['ps','-q','postgres']).decode().strip())
    if target['Config']['Labels'].get('com.docker.compose.project') != 'lumiere-rebuild-test':
        raise ValueError('Wrong local PostgreSQL project')
    target_user = dict(v.split('=',1) for v in target['Config']['Env'] if '=' in v)['POSTGRES_USER']
    source_user = dict(v.split('=',1) for v in source['Config']['Env'] if '=' in v)['POSTGRES_USER']
    clone = inspect(audit['clone_container'])
    if (not clone['State']['Running'] or clone['HostConfig']['NetworkMode'] != 'none'
            or 'default_transaction_read_only=on' not in (clone['Config'].get('Cmd') or [])):
        raise ValueError('An isolated read-only audit clone must be running')
    deadline = time.monotonic() + 180
    while True:
        if time.monotonic() >= deadline:
            raise RuntimeError('Read-only audit clone did not finish recovery within its startup budget')
        try:
            ready = run_bounded(['docker', 'exec', audit['clone_container'], 'pg_isready', '-q', '-t', '3',
                                 '-U', source_user, '-d', 'lumiere_backend_test'], cwd=ROOT,
                                timeout=max(1, min(30, deadline - time.monotonic())))
            if ready.returncode == 0:
                break
        except subprocess.TimeoutExpired:
            pass  # Docker CLI cold start is part of this overall startup budget.
        time.sleep(1)
    preserved, session_lifecycle = [], None
    counts = audit['databases']['lumiere_backend_test']['table_counts']
    for table in counts:
        if table == 'alembic_version':
            continue
        if not re.fullmatch('[a-z_]+',table):
            raise ValueError('Unexpected table name')
        sql = ("BEGIN READ ONLY; SET LOCAL TIME ZONE 'UTC'; SELECT json_build_object('rows',count(*),'sha256',"
               "encode(sha256(convert_to(coalesce(string_agg(s,E'\\n' ORDER BY s COLLATE \"C\"),''),'UTF8')),'hex')) "
               'FROM (SELECT row_to_json(t)::text AS s FROM public."'+table+'" t) src; COMMIT;')
        digests = []
        for container,user,database in ((audit['clone_container'],source_user,'lumiere_backend_test'),
                                       (target['Id'],target_user,'lumiere_test_original_data')):
            digests.append(json.loads(run(['docker','exec',container,'psql','-XqAt','-v','ON_ERROR_STOP=1',
                                           '-U',user,'-d',database,'-c',sql])))
        if table=='user_sessions' and args.allow_session_lifecycle:
            rows=[]
            for container,user,database in ((audit['clone_container'],source_user,'lumiere_backend_test'),
                                           (target['Id'],target_user,'lumiere_test_original_data')):
                sql="BEGIN READ ONLY; SET LOCAL TIME ZONE 'UTC'; SELECT coalesce(json_object_agg(id,encode(sha256(convert_to(row_to_json(t)::text,'UTF8')),'hex')),'{}'::json) FROM user_sessions t; COMMIT;"
                rows.append(json.loads(run(['docker','exec',container,'psql','-XqAt','-v','ON_ERROR_STOP=1',
                                             '-U',user,'-d',database,'-c',sql])))
            old,new=rows
            common=set(old)&set(new)
            if any(old[key]!=new[key] for key in common):
                raise ValueError('A surviving original session changed')
            session_lifecycle={'source_rows':len(old),'current_rows':len(new),
                'unchanged_surviving_rows':len(common),'removed_rows':len(set(old)-set(new)),
                'added_rows':len(set(new)-set(old)), 'baseline_restore_all_sessions_preserved':True}
            if old!=new:
                continue
        if digests[0] != digests[1]:
            raise ValueError('Existing rows differ in table '+table)
        preserved.append(table)
    # Restore must preserve ID generators as well as existing rows.
    # Sequence ownership may change to the isolated local restore role.
    sequences=[]
    for container,user,database in ((audit['clone_container'],source_user,'lumiere_backend_test'),
                                   (target['Id'],target_user,'lumiere_test_original_data')):
        sql="BEGIN READ ONLY; SELECT coalesce(jsonb_object_agg(sequencename,to_jsonb(s)-'sequenceowner'),'{}'::jsonb) FROM pg_sequences s WHERE schemaname='public'; COMMIT;"
        sequences.append(json.loads(run(['docker','exec',container,'psql','-XqAt','-v','ON_ERROR_STOP=1',
                                        '-U',user,'-d',database,'-c',sql])))
    sequence_names=set(sequences[0])
    if args.allow_session_lifecycle:
        sequence_names.discard('user_sessions_id_seq')
    if any(sequences[1].get(name)!=sequences[0][name] for name in sequence_names):
        raise ValueError('Original ID sequence state differs')
    http_retries=[]
    def get(path):
        for attempt in range(3):
            try:
                with urlopen('http://127.0.0.1:18080'+path,timeout=30) as response:
                    return response.status,response.headers.get_content_type(),response.read()
            except HTTPError as error:
                if error.code not in (502,503,504) or attempt==2:
                    raise
                http_retries.append(error.code)
                time.sleep(1)
    rows=[]
    for page in range(1,6):
        data=json.loads(get('/api/products?page_size=100&page='+str(page))[2])
        assert data['total']==500
        rows.extend(data['items'])
    assert len({row['id'] for row in rows})==500
    mapping_source=(ROOT/'frontend/assets/js/product-image-map.js').read_text(encoding='utf-8-sig')
    mapping=json.loads(re.search(r'window\.LUMIERE_PRODUCT_IMAGES\s*=\s*(\{.*?\});',mapping_source,re.S).group(1))
    def check_image(row):
        path=mapping[row['sku'].upper()]
        status,kind,content=get(path)
        assert status==200 and kind in ('image/png','image/webp') and len(content)>100
        assert content==(ROOT/'frontend'/path.lstrip('/')).read_bytes()
        return True
    with ThreadPoolExecutor(max_workers=3) as pool:
        matched=sum(pool.map(check_image,rows))
    report={'successful':True,'verified_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'read-only original-project copy; not full role/browser acceptance or relevance benchmark',
        'source_database':'lumiere_backend_test','active_database':env['POSTGRES_DB'],
        'serving_application_switched':True,'original_source_still_stopped':True,
        'existing_tables_row_digests_preserved':len(preserved),'original_counts':counts,
        'original_id_sequences_preserved':len(sequence_names),
        'interactive_session_lifecycle':session_lifecycle,
        'public_catalog_products':len(rows),'original_sku_images_http_bytes_verified':matched,
        'transient_http_retry_statuses':http_retries,
        'accounts_reset':False,'public_deployment':False,'private_rows_exported':False}
    if args.semantic:
        from run_compose_semantic_lab import VERIFY, STATUS
        deadline=time.monotonic()+min(max(args.wait_sync_seconds,0),600)
        while True:
            status=json.loads(run(COMPOSE+['exec','-T','business-api','python','-B','-c',STATUS]))
            if status['states']=={'done':500} or time.monotonic()>=deadline:
                break
            time.sleep(5)
        assert status['states']=={'done':500}, status['states']
        # Same actual three-source/price/stock checks, sized to the full original catalog.
        verification=VERIFY.replace("points_count'] == 5 ","points_count'] == 500 ").replace('nodes == 5 and edges == 25','nodes == 500 and edges == 2500')
        report['sync_status']=status
        report['semantic']=json.loads(run(COMPOSE+['exec','-T','ai-api','python','-B','-c',verification],timeout=300))
    with args.report.open('x',encoding='utf-8') as output:
        json.dump(report,output,indent=2)
    print(json.dumps(report))


if __name__=='__main__': main()
