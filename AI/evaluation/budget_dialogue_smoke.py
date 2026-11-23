"""One local read-only acceptance run, finite turns, no retries or model warmup."""
import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import time
import requests


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():
        parser.error('Preserve previous reports')
    report={'successful':False,'cases':[],'database_written':False,'retry_or_warmup':False}
    with requests.Session() as client:
        client.trust_env=False
        base='http://127.0.0.1:18080'
        def get(path):
            r=client.get(base+path,timeout=(3,8));r.raise_for_status();return r
        def chat(query,token=None):
            started=time.monotonic()
            r=client.post(base+'/ai/chat',json={'query':query,'conversation_id':token},timeout=(3,28))
            r.raise_for_status();value=r.json()
            report['cases'].append({'query':query,'seconds':round(time.monotonic()-started,3),
                'intent':value.get('intent'),'status':value.get('status'),
                'response_mode':value.get('response_mode'),'answer':value.get('answer'),
                'product_ids':[p['ProductID'] for p in value.get('products',[])]})
            assert value.get('success') is True
            return value
        try:
            total=get('/api/products?page_size=1').json()['total']
            payment=get('/api/checkout/payment-methods').json()['vnpay']['enabled']
            frontend=hashlib.sha256(get('/assets/js/site.js').content).hexdigest()
            first=chat('thanh lịch')
            assert first.get('intent')=='shopping_advice'
            for query in ('dưới 3tr','dưới 3 triệu','3 triệu'):
                value=chat(query,first['conversation_id'])
                assert value.get('intent')=='shopping_advice' and value['products']
                for product in value['products']:
                    current=get('/api/products/'+str(product['ProductID'])).json()
                    assert Decimal(str(product['Price']))==Decimal(current['price_vnd'])
                    assert Decimal(current['price_vnd'])<=3_000_000 and current['stock']>0
            knowledge=chat('Moissanite là gì?',first['conversation_id'])
            assert knowledge.get('response_mode')=='reviewed_domain_answer' and not knowledge['products']
            shorter=chat('nói ngắn gọn hơn',first['conversation_id'])
            assert len(shorter['answer'])<len(knowledge['answer']) and not shorter['products']
            fresh=chat('dưới 3 triệu')
            assert fresh.get('intent')!='general_question'
            assert 'Lớp trả lời tự nhiên hiện chưa sẵn sàng' not in fresh['answer']
            assert get('/api/products?page_size=1').json()['total']==total
            assert get('/api/checkout/payment-methods').json()['vnpay']['enabled']==payment
            assert hashlib.sha256(get('/assets/js/site.js').content).hexdigest()==frontend
            report.update(successful=True,passed=len(report['cases']),catalog_total=total,
                          frontend_vnpay_unchanged=True)
        except Exception as error:
            report['failure_type']=type(error).__name__
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=True))
    return 0 if report['successful'] else 1


if __name__=='__main__':
    raise SystemExit(main())
