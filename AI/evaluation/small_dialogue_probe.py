"""Three fixed local generation cases, no retries; compare with recorded 3B failure."""
import json
from pathlib import Path
import time
import urllib.request


def main():
    report={'model':'qwen3:0.6b-q4_K_M','successful':False,'cases':[],
            'scope':'Small live feasibility sample; not a Vietnamese quality benchmark','retries':0}
    output=Path('docs/ai-small-dialogue-probe-20261123.json')
    assert not output.exists(),'Preserve reports'
    messages=[{'role':'system','content':'Bạn là trợ lý LUMIÈRE. Trả lời tiếng Việt đúng câu hỏi, ngắn gọn. Không bịa dữ liệu cửa hàng. Không tự tìm sản phẩm.'}]
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        for query in ('Viết một lời chúc sinh nhật ngắn dành cho bạn thân, xưng mình và cậu.',
                      'Viết lại gần gũi hơn, chỉ một câu.',
                      'Tôi đi dự tiệc với váy đơn sắc, nên phối trang sức thế nào? Không cần tìm sản phẩm.'):
            messages.append({'role':'user','content':query})
            started=time.monotonic()
            request=urllib.request.Request('http://127.0.0.1:11435/api/chat',
                data=json.dumps({'model':report['model'],'messages':messages,'stream':False,'think':False,
                                 'keep_alive':'15m','options':{'num_ctx':1024,'num_predict':128,'num_thread':2,'temperature':0.5}}).encode(),
                headers={'Content-Type':'application/json'})
            with opener.open(request,timeout=25) as response:value=json.load(response)
            answer=value['message']['content']
            report['cases'].append({'query':query,'answer':answer,'seconds':round(time.monotonic()-started,3),
                                    'done':value.get('done'),'done_reason':value.get('done_reason'),
                                    'eval_count':value.get('eval_count')})
            assert answer.strip() and value.get('done') is True
            messages.append({'role':'assistant','content':answer})
        report['successful']=True
    except Exception as error:
        report['failure_type']=type(error).__name__
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=True))
    return 0 if report['successful'] else 1


if __name__=='__main__':
    raise SystemExit(main())
