"""Read-only actual model/API smoke, not a human relevance benchmark."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PROBE=r'''
import json,os,requests
from decimal import Decimal
s=requests.Session();s.trust_env=False
h={'Authorization':'Bearer '+os.environ['LUMIERE_AI_DIAGNOSTICS_TOKEN']}
r=s.post('http://127.0.0.1:8000/internal/retrieval-diagnostics',headers=h,
         json={'query':'nhẫn','semantic_entities':True},timeout=180)
report={'warmup_http_status':r.status_code,'cases':[]}
for query,gift in [('Lễ tình nhân tặng gì?',True),
 ('Muốn chọn một món quà trang sức cho người thương, tư vấn giúp mình',True),
 ('Top 3 nhẫn dưới 8 triệu',False)]:
 r=s.post('http://127.0.0.1:8000/chat',json={'query':query,'top_k':3},timeout=45)
 d=r.json();products=d.get('products',[])
 verified=r.status_code==200 and d.get('success') is True and len(products)==3
 for product in products:
  live=s.get('http://business-api:8001/products/'+str(product['ProductID']),timeout=5)
  live.raise_for_status();live=live.json()
  verified=verified and product['ProductName']==live['name'] and product['Stock']==live['stock']>0
  verified=verified and Decimal(str(product['Price']))==Decimal(str(live['price_vnd']))
  if not gift:
   verified=verified and live['category']['name']=='Nhẫn' and Decimal(str(product['Price']))<8000000
 intent_ok=(d.get('advice_intent')=='gift_advice') if gift else (d.get('advice_intent')!='gift_advice')
 advice_ok=d.get('answer','').startswith('Nếu chọn trang sức làm quà') if gift else True
 report['cases'].append({'query':query,'http':r.status_code,'advice_intent':d.get('advice_intent'),
   'status':d.get('status'),'returned_products':len(products),'live_price_stock_verified':bool(verified),
   'advice_verified':bool(intent_ok and advice_ok)})
report['successful']=all(c['live_price_stock_verified'] and c['advice_verified'] for c in report['cases'])
report.update(real_model=True,quality_benchmark=False,private_rows_accessed=False,writes_performed=False)
print(json.dumps(report))
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists(): parser.error('Preserve prior reports; choose a new path')
    command=['docker','compose','--env-file','.env.example','-f','compose.yaml','-f','compose.original-data.yaml']
    cid=subprocess.check_output(command+['ps','-q','ai-api'],cwd=ROOT).decode().strip()
    container=json.loads(subprocess.check_output(['docker','inspect',cid]))[0]
    assert container['Config']['Labels'].get('com.docker.compose.project')=='lumiere-rebuild-test'
    result=subprocess.run(command+['exec','-T','ai-api','python','-B','-'],input=PROBE.encode('utf-8'),
                          cwd=ROOT,capture_output=True,timeout=360)
    if result.returncode:
        (ROOT/'.local-tmp/advice-verification-failure.log').write_bytes(result.stdout+result.stderr)
        raise RuntimeError('Probe failed; private diagnostics retained')
    report=json.loads(result.stdout)
    report['ai_image_id']=container['Image']
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['successful'] else 1

if __name__=='__main__': raise SystemExit(main())
