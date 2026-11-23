"""Single bounded probe of the existing Windows model. Never downloads/retries."""
import json
from pathlib import Path
import time
import urllib.request


def main():
    output=Path('.local-tmp/host-dialogue-probe-20261123.json')
    assert not output.exists(),'Preserve previous evidence'
    started=time.monotonic()
    report={'successful':False,'downloaded':False,'retries':0,'model':'qwen2.5:3b'}
    data={'model':'qwen2.5:3b','stream':False,'keep_alive':'5m',
          'options':{'num_ctx':1024,'num_predict':64,'num_thread':2,'temperature':0.2},
          'messages':[{'role':'system','content':'Bạn là trợ lý tiếng Việt. Trả lời ngắn gọn đúng yêu cầu.'},
                      {'role':'user','content':'Viết một lời chúc sinh nhật ngắn dành cho bạn thân, xưng mình và cậu.'}]}
    try:
        request=urllib.request.Request('http://127.0.0.1:11435/api/chat',data=json.dumps(data).encode(),
                                       headers={'Content-Type':'application/json'})
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request,timeout=55) as response:
            value=json.loads(response.read(65536))
        report.update(successful=bool(value['message']['content'].strip()),answer=value['message']['content'],
                      done=value.get('done'),done_reason=value.get('done_reason'),
                      eval_count=value.get('eval_count'),load_duration=value.get('load_duration'))
    except Exception as error:
        report['failure_type']=type(error).__name__
    report['seconds']=round(time.monotonic()-started,3)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=True))
    return 0 if report['successful'] else 1


if __name__=='__main__':
    raise SystemExit(main())
