"""One bounded read-only live conversation; no warm-up, retries or database writes."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time

import requests

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from shared.host_process import run_bounded


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    assert not args.report.exists(),'Preserve prior reports'
    report={'successful':False,'scope':'Single local consultation flow, not a relevance benchmark or LLM evaluation',
            'cases':[],'database_written':False,'warmup_or_retry_loops':False}
    base='http://127.0.0.1:18080'
    try:
        with requests.Session() as client:
            client.trust_env=False
            def get(path):
                response=client.get(base+path,timeout=(3,8));response.raise_for_status();return response
            baseline_total=get('/api/products?page_size=1').json()['total']
            baseline_vnpay=get('/api/checkout/payment-methods').json()['vnpay']['enabled']
            frontend_hash=hashlib.sha256(get('/assets/js/site.js').content).hexdigest()
            def turn(query,token=None):
                started=time.monotonic()
                response=client.post(base+'/ai/chat',json={'query':query,'conversation_id':token},timeout=(3,28))
                assert response.status_code==200
                value=response.json();assert value.get('success') is True
                report['cases'].append({'query':query,'seconds':round(time.monotonic()-started,3),
                    'status':value.get('status'),'intent':value.get('intent'),'answer':value.get('answer'),
                    'product_ids':[p['ProductID'] for p in value.get('products',[])]})
                return value
            def grounded(value,maximum=None,category=None):
                for product in value.get('products',[]):
                    current=get('/api/products/'+str(product['ProductID'])).json()
                    assert Decimal(str(product['Price']))==Decimal(current['price_vnd'])
                    assert product['Stock']>0 and current['stock']>0
                    if maximum is not None:assert Decimal(current['price_vnd'])<Decimal(maximum)
                    if category is not None:assert current['category']['id']==category
                    unverified={e['label'] for e in value.get('unverified_preferences',[])}
                    assert not any(e['label'] in unverified for e in product.get('matched_entities',[]))
            first=turn('nữ thanh lịch chọn gì')
            assert first.get('intent')=='shopping_advice' and 1<=len(first['products'])<=3
            assert 'Yêu cầu đã được nhận diện' not in first['answer']
            grounded(first)
            token=first['conversation_id']
            why=turn('tại sao lại gợi ý sản phẩm đó',token)
            assert why.get('products')==[]
            assert why['referenced_product_ids']==[p['ProductID'] for p in first['products']]
            budget=turn('duoi3tr',token)
            assert budget.get('intent')=='shopping_advice';grounded(budget,3_000_000)
            category=turn('mình thích bông tai',token)
            assert category.get('intent')=='shopping_advice';grounded(category,3_000_000,3)
            assert get('/api/products?page_size=1').json()['total']==baseline_total
            assert get('/api/checkout/payment-methods').json()['vnpay']['enabled']==baseline_vnpay
            assert hashlib.sha256(get('/assets/js/site.js').content).hexdigest()==frontend_hash
        baseline=json.loads((ROOT/'.local-tmp/ai-consultation-unchanged-services.json').read_text())
        result=run_bounded(['docker','inspect',*baseline.keys()],timeout=20)
        assert result.returncode==0
        current={item['Name']:{'id':item['Id'],'started_at':item['State']['StartedAt']} for item in json.loads(result.stdout)}
        assert current==baseline,'A non-AI container changed during deployment'
        report.update(successful=True,passed=4,catalog_total=baseline_total,
            frontend_checkout_vnpay_and_non_ai_containers_unchanged=True)
    except Exception as error:
        report['failure_type']=type(error).__name__
    report['verified_utc']=datetime.now(timezone.utc).isoformat()
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
    return 0 if report['successful'] else 1


if __name__=='__main__':
    raise SystemExit(main())
