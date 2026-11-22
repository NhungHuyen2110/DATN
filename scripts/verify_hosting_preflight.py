"""Exercise hosting guards and Linux backup permissions without a host purchase or deployment."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'AI'))
from knowledge_graph.csv_validation import validate_csv

PERMISSIONS = '''import os,json
from pathlib import Path
p=Path('/tmp/lumiere-permission-test'); p.mkdir(mode=0o750); os.chown(p,0,10001)
for name in ('backup.dump','backup-reference.json'):
    f=p/name; f.write_text('test-only'); os.chown(f,0,10001); os.chmod(f,0o440)
account=p/'demo-accounts.json'; account.write_text('test-only'); os.chmod(account,0o600)
os.setgroups([]); os.setgid(10001); os.setuid(10001)
assert (p/'backup.dump').read_text()=='test-only'
assert (p/'backup-reference.json').read_text()=='test-only'
try: account.read_text()
except PermissionError: pass
else: raise AssertionError('Worker could read bootstrap credentials')
try: (p/'backup.dump').write_text('modified')
except PermissionError: pass
else: raise AssertionError('Worker could modify backup')
print(json.dumps({'worker_can_read_backup':True,'worker_cannot_read_account_passwords':True,'worker_cannot_write_backup':True}))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists(): parser.error('Choose a new report')
    def run(command, content=None):
        return subprocess.run(command,cwd=ROOT,input=content,capture_output=True,timeout=180)
    preview=ROOT/'.local-tmp/hosting-preview-20261122'
    digest=hashlib.sha256((preview/'demo.env').read_bytes()).hexdigest()
    overwrite=run([sys.executable,'-B','scripts/prepare_demo_hosting.py','--domain','lumiere.example.invalid',
        '--preview','--directory',str(preview)])
    assert overwrite.returncode==2 and hashlib.sha256((preview/'demo.env').read_bytes()).hexdigest()==digest
    invalid=ROOT/'.local-tmp/hosting-invalid-domain-20261122'
    assert not invalid.exists()
    rejected=run([sys.executable,'-B','scripts/prepare_demo_hosting.py','--domain','https://example.com/path','--directory',str(invalid)])
    assert rejected.returncode==2 and not invalid.exists()
    permissions=run(['docker','run','--rm','-i','--network','none','--user','0','--entrypoint','python',
        'lumiere-rebuild-test-business-api:latest','-B','-'],PERMISSIONS.encode())
    assert permissions.returncode==0
    rows=validate_csv(ROOT/'output/products_ai.csv',ROOT/'data')
    assert not rows['errors']
    recovery=ROOT/'.local-tmp/recovery/hosting-bootstrap-20261122'
    prefix=['docker','compose','--env-file','.env.example','-f','compose.yaml']
    refusal=run(prefix+['run','--rm','--no-deps','-e','POSTGRES_DB=lumiere_test_demo_hosting',
        '-e','PRODUCT_INDEX_SYNC_ENABLED=false','-v',str(recovery)+':/recovery:ro','business-api','python','-B','-c',
        (ROOT/'backend/scripts/bootstrap_demo_seed.py').read_text(encoding='utf-8')],
        json.dumps({'confirm_demo':True,'records':rows['records'],'passwords':{}}).encode())
    assert refusal.returncode!=0 and b'bootstrap refuses any nonempty table' in refusal.stderr
    count=run(prefix+['exec','-T','postgres','psql','-U','lumiere_test','-d','lumiere_test_demo_hosting','-Atc',
        'SELECT (SELECT count(*) FROM products),(SELECT count(*) FROM users),(SELECT count(*) FROM orders)'])
    assert count.returncode==0 and count.stdout.strip()==b'500|3|0'
    report={'successful':True,'existing_credentials_preserved':True,'invalid_domain_rejected':True,
        'linux_permissions':json.loads(permissions.stdout),'nonempty_database_reseed_rejected':True,
        'independent_sql_counts':'500|3|0','production_accessed':False,'public_deployment':False}
    with args.report.open('x',encoding='utf-8') as output: json.dump(report,output,indent=2)
    print(json.dumps(report))


if __name__=='__main__': main()
