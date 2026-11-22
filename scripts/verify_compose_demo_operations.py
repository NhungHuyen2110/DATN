"""Read-only post-browser check: actual monitoring, durable checkout projection and old demo catalog."""
import argparse
import json
from pathlib import Path
import subprocess

from run_compose_semantic_lab import ROOT, COMPOSE

PROBE = '''import json,os,sys,requests
sys.path.insert(0,'/srv')
from jewelry_agents import retrieval
with requests.Session() as client:
    client.trust_env=False
    response=client.get('http://prometheus:9090/api/v1/targets',timeout=5); response.raise_for_status()
    targets=[{'instance':t['labels']['instance'],'health':t['health']} for t in response.json()['data']['activeTargets']]
    assert {t['instance'] for t in targets}=={'business-api:8001','ai-api:8000','index-worker:9101'}
    assert all(t['health']=='up' for t in targets)
    catalog=client.get(os.environ['BUSINESS_API_URL']+'/products?page_size=100',timeout=5); catalog.raise_for_status()
    catalog=catalog.json(); assert catalog['total']==5
    product=next(p for p in catalog['items'] if p['id']==1)
    driver=retrieval.get_graph_driver()
    try:
        with driver.session() as session:
            row=session.run('MATCH (p:Product {product_id:1}) RETURN p.stock AS stock').single()
            assert row['stock']==product['stock']
    finally: driver.close()
    print(json.dumps({'prometheus_targets':targets,'catalog_products':5,
        'business_graph_stock_match':True,'current_stock_product_1':product['stock']}))
'''
QUEUE='''import json
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.product_index_job import ProductIndexJob as Job
with SessionLocal() as db:
    rows=[dict(product_id=r.product_id,generation=r.generation,delivered_generation=r.delivered_generation,status=r.status)
          for r in db.scalars(select(Job).order_by(Job.product_id))]
    assert len(rows)==5 and all(r['status']=='done' and r['generation']==r['delivered_generation'] for r in rows)
    assert next(r for r in rows if r['product_id']==1)['generation']>=2
    print(json.dumps(rows))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists(): parser.error('Choose a new report')
    baseline=json.loads((ROOT/'docs/compose-full-semantic-browser-20261122.json').read_text())
    if not baseline['successful'] or baseline['production_accessed'] is not False:
        parser.error('Passing synthetic full semantic browser suite required')
    def run(command):
        return subprocess.run(command,cwd=ROOT,capture_output=True,check=True,timeout=90).stdout
    cid=run(COMPOSE+['ps','-q','ai-api']).decode().strip()
    target=json.loads(run(['docker','inspect',cid]))[0]['Config']['Labels']
    if target.get('com.docker.compose.project')!='lumiere-rebuild-test' or target.get('com.docker.compose.service')!='ai-api':
        parser.error('Wrong project')
    report=json.loads(run(COMPOSE+['exec','-T','ai-api','python','-B','-c',PROBE]))
    report['projection_jobs']=json.loads(run(COMPOSE+['exec','-T','business-api','python','-B','-c',QUEUE]))
    report.update(successful=True,production_accessed=False,scope='single warm demo episode, not load/SLA benchmark')
    with args.report.open('x',encoding='utf-8') as output: json.dump(report,output,indent=2)
    print(json.dumps(report))


if __name__=='__main__': main()
