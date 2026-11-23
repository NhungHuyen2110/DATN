"""Exactly three local turns: real generation, contextual rewrite, shopping regression."""
import argparse
import json
from decimal import Decimal
from pathlib import Path
import time
import requests
import urllib.request


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    assert not args.report.exists(),'Preserve reports'
    report={'successful':False,'cases':[],'retries':0,'downloaded_during_chat':False,'model':'qwen3:0.6b-q4_K_M'}
    with requests.Session() as client:
        client.trust_env=False
        def turn(query,token=None):
            started=time.monotonic()
            r=client.post('http://127.0.0.1:18080/ai/chat',json={'query':query,'conversation_id':token},timeout=(3,44))
            r.raise_for_status();value=r.json()
            report['cases'].append({'query':query,'answer':value.get('answer'),'response_mode':value.get('response_mode'),
                                   'status':value.get('status'),'seconds':round(time.monotonic()-started,3),
                                   'product_ids':[p['ProductID'] for p in value.get('products',[])]})
            assert value.get('success') is True
            return value
        try:
            first=turn('Viết lời chúc tốt nghiệp ngắn cho bạn thân, xưng mình và cậu.')
            assert first.get('response_mode')=='local_llm_dialogue' and not first['products']
            second=turn('Viết lại trang trọng hơn, chỉ một câu.',first['conversation_id'])
            assert second.get('response_mode')=='local_llm_dialogue' and not second['products']
            third=turn('nữ thanh lịch chọn gì dưới 3 triệu')
            assert third.get('intent')=='shopping_advice' and third['products']
            assert all(Decimal(str(p['Price']))<3_000_000 and p['Stock']>0 for p in third['products'])
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open('http://127.0.0.1:11435/api/ps',timeout=5) as response:
                loaded=json.load(response)['models']
            assert any(model['name']==report['model'] for model in loaded)
            report['resident_model_bytes']=next(model['size'] for model in loaded if model['name']==report['model'])
            report.update(successful=True,passed=3,
                          scope='Real Customer model generation and contextual rewrite, not a general quality benchmark')
        except Exception as error:
            report['failure_type']=type(error).__name__
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=True))
    return 0 if report['successful'] else 1


if __name__=='__main__':
    raise SystemExit(main())
