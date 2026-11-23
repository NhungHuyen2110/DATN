"""One fixed read-only local flow; no retries, warmup loops, or database writes."""
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
    assert not args.report.exists(),'Preserve reports'
    report={'successful':False,'cases':[],'retries':0,'database_written':False}
    with requests.Session() as client:
        client.trust_env=False
        base='http://127.0.0.1:18080'
        def get(path):
            r=client.get(base+path,timeout=(3,8));r.raise_for_status();return r
        def turn(query,token=None):
            start=time.monotonic()
            r=client.post(base+'/ai/chat',json={'query':query,'conversation_id':token},timeout=(3,40))
            r.raise_for_status();value=r.json()
            report['cases'].append({'query':query,'seconds':round(time.monotonic()-start,3),
                'intent':value.get('intent'),'response_mode':value.get('response_mode'),
                'status':value.get('status'),'answer':value.get('answer'),
                'product_ids':[p['ProductID'] for p in value.get('products',[])],
                'referenced_product_ids':value.get('referenced_product_ids',[])})
            assert value.get('success') is True
            return value
        try:
            total=get('/api/products?page_size=1').json()['total']
            payment=get('/api/checkout/payment-methods').json()['vnpay']['enabled']
            frontend=hashlib.sha256(get('/assets/js/site.js').content).hexdigest()
            first=turn('nữ thanh lịch chọn gì dưới 3 triệu')
            assert len(first['products'])>=2
            ids=[p['ProductID'] for p in first['products']]
            token=first['conversation_id']
            compare=turn('So sánh 2 mẫu đầu',token)
            assert compare['referenced_product_ids']==ids[:2] and not compare['products']
            assert compare['status']=='ok'
            for pid in ids[:2]:
                item=get('/api/products/'+str(pid)).json()
                assert item['name'] in compare['answer']
                assert f"{Decimal(item['price_vnd']):,.0f}".replace(',','.') in compare['answer']
            detail=turn('Mẫu thứ hai có chất liệu gì?',token)
            assert detail['referenced_product_ids']==[ids[1]] and detail['status']=='ok'
            knowledge=turn('Moissanite là gì?',token)
            assert not knowledge['products'] and knowledge.get('response_mode')=='local_llm_dialogue'
            refined=turn('đổi sang bông tai dưới 2tr',token)
            assert refined.get('intent')=='shopping_advice' and refined['products']
            for product in refined['products']:
                item=get('/api/products/'+str(product['ProductID'])).json()
                assert item['category']['id']==3 and Decimal(item['price_vnd'])<2_000_000 and item['stock']>0
            assert get('/api/products?page_size=1').json()['total']==total
            assert get('/api/checkout/payment-methods').json()['vnpay']['enabled']==payment
            assert hashlib.sha256(get('/assets/js/site.js').content).hexdigest()==frontend
            report.update(successful=True,passed=5,catalog_total=total,frontend_vnpay_unchanged=True,
                          scope='Fixed contextual flow, not an overall model quality benchmark')
        except Exception as error:
            report['failure_type']=type(error).__name__
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=True))
    return 0 if report['successful'] else 1


if __name__=='__main__':
    raise SystemExit(main())
