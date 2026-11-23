"""Three live held-out requests, actual vector/graph evidence, no retries."""
import argparse
import json
from pathlib import Path
from decimal import Decimal
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
        def turn(query,token=None):
            start=time.monotonic()
            r=client.post(base+'/ai/chat',json={'query':query,'conversation_id':token},timeout=(3,42))
            r.raise_for_status();value=r.json()
            report['cases'].append({'query':query,'seconds':round(time.monotonic()-start,3),'answer':value.get('answer'),
                'status':value.get('status'),'response_mode':value.get('response_mode'),
                'resolved_entities':value.get('resolved_entities',[]),
                'clarification_options':value.get('clarification_options',[]),
                'clarification_resolution':value.get('clarification_resolution'),
                'retrieval_sources_used':value.get('retrieval_sources_used',[]),'products':value.get('products',[])})
            assert value.get('success') is True
            return value
        def current(pid):
            r=client.get(base+'/api/products/'+str(pid),timeout=(3,8));r.raise_for_status();return r.json()
        try:
            first=turn('Một món ôm quanh ngón tay, đừng quá 3 triệu.')
            if first.get('status')=='clarification_required':
                assert first['clarification_options'][0]['canonical_id']=='ring'
                report['clarification_used']=True
                first=turn('Loại đầu tiên',first['conversation_id'])
            assert first.get('products'),'Semantic shopping was not routed to retrieval'
            report['dense_and_graph_verified']={'dense','graph'}.issubset(first.get('retrieval_sources_used',[]))
            assert report['dense_and_graph_verified']
            live=[current(p['ProductID']) for p in first['products']]
            report['ring_relevance_passed']=all(p['category']['id']==1 for p in live)
            assert report['ring_relevance_passed']
            assert all(Decimal(p['price_vnd'])<=3_000_000 and p['stock']>0 for p in live)
            anchor=first['products'][0]['ProductID']
            related=turn('Tìm mẫu cùng loại đá với sản phẩm '+str(anchor))
            assert related.get('products')
            assert all(any(path['relationship']=='HAS_GEMSTONE' and path.get('source_product_id')==anchor
                           for path in p.get('matched_relationships',[])) for p in related['products'])
            assert all(current(p['ProductID'])['gemstone']['id']==live[0]['gemstone']['id'] for p in related['products'])
            outside=turn('Nói về cách gieo hạt cà chua ở ban công.')
            assert not outside.get('products')
            assert 'Bạn đang chọn cho dịp nào' in outside['answer']
            report.update(successful=True,passed=len(report['cases']),
                          scope='Held-out paraphrase, graph relationship and off-topic bridge; not general AI accuracy')
        except Exception as error:report['failure_type']=type(error).__name__
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},ensure_ascii=True))
    return 0 if report['successful'] else 1


if __name__=='__main__':raise SystemExit(main())
