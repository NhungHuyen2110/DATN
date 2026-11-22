"""Back up serving original-data copy, restore NEW QA DB, add QA-only accounts.

No original account/password/product/order changes; private fixture never enters Git.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
COMPOSE=['docker','compose','--env-file','.env.example','-f','compose.yaml','-f','compose.original-data.yaml']
TARGET='lumiere_test_ai_acceptance'
SEED=r'''
import json,secrets
from sqlalchemy import select,func,text
from app.core.database import SessionLocal,engine
from app.core.security import hash_password
from app.models import User,Role,Product,Order
assert engine.url.database=='lumiere_test_ai_acceptance' and engine.url.host=='postgres'
accounts={}
with SessionLocal() as db,db.begin():
    assert db.scalar(select(func.count()).select_from(Product))==500
    before=db.scalar(select(func.count()).select_from(User))
    assert before==11
    for role in ('admin','staff','customer'):
        password=secrets.token_urlsafe(24)
        email='qa-ai-'+role+'-'+secrets.token_hex(4)+'@example.com'
        role_id=db.scalar(select(Role.id).where(Role.name==role))
        assert role_id is not None
        db.add(User(role_id=role_id,full_name='QA AI '+role,email=email,
                    phone='0901234567',password_hash=hash_password(password),is_active=True))
        accounts[role]={'email':email,'password':password}
    pending=db.scalar(text("SELECT count(*) FROM orders WHERE status='pending'"))
    orders=db.scalar(select(func.count()).select_from(Order))
print(json.dumps({'accounts':accounts,'original_users_preserved':before,
                 'expected_pending_orders':pending,'expected_total_orders':orders,'synthetic_accounts_only':True}))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-local-qa-copy',action='store_true',required=True)
    args=parser.parse_args()
    # Inherit the existing private ACL; fail closed if original backup/restore isn't present.
    private=ROOT/'.local-tmp/original-db-20261122-014434'
    assert json.loads((private/'working-copy/restore.json').read_text())['successful']
    folder=private/'ai-acceptance'
    folder.mkdir(exist_ok=False)
    def run(command,content=None):
        result=subprocess.run(command,cwd=ROOT,input=content,capture_output=True,timeout=180)
        if result.returncode:
            (folder/'failure.log').write_bytes(result.stdout+result.stderr)
            raise RuntimeError('QA preparation failed; inspect private failure log')
        return result.stdout
    business=json.loads(run(['docker','inspect',run(COMPOSE+['ps','-q','business-api']).decode().strip()]))[0]
    values=dict(v.split('=',1) for v in business['Config']['Env'] if '=' in v)
    assert values['POSTGRES_DB']=='lumiere_test_original_data'
    pg=run(COMPOSE+['ps','-q','postgres']).decode().strip()
    user=values['POSTGRES_USER']
    found=run(['docker','exec',pg,'psql','-XqAt','-U',user,'-d','postgres','-c',
               "SELECT count(*) FROM pg_database WHERE datname='"+TARGET+"'"]).decode().strip()
    assert found=='0','Preserve existing QA DB; never overwrite'
    dump=run(['docker','exec',pg,'pg_dump','-U',user,'-d',values['POSTGRES_DB'],'-Fc','--no-owner','--no-acl'])
    assert dump.startswith(b'PGDMP')
    (folder/'before-qa.dump').write_bytes(dump)
    run(['docker','exec',pg,'createdb','-U',user,TARGET])
    run(['docker','exec','-i',pg,'pg_restore','-U',user,'-d',TARGET,'--no-owner','--no-acl','--exit-on-error'],dump)
    fixture=run(COMPOSE+['run','--rm','--no-deps','-T','-e','POSTGRES_DB='+TARGET,
                         '-e','PRODUCT_INDEX_SYNC_ENABLED=false','business-api','python','-B','-'],SEED.encode())
    data=json.loads(fixture)
    (folder/'fixture.json').write_bytes(fixture)
    report={'successful':True,'source_serving_database':'lumiere_test_original_data','qa_database':TARGET,
        'original_account_passwords_unchanged':True,'qa_accounts_added':3,'catalog_products':500,
        'original_orders':data['expected_total_orders'],'backup_sha256':hashlib.sha256(dump).hexdigest(),
        'private_fixture':str((folder/'fixture.json').relative_to(ROOT)),
        'prepared_utc':datetime.now(timezone.utc).isoformat(),'public_data_exported':False}
    (folder/'preparation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__': main()
