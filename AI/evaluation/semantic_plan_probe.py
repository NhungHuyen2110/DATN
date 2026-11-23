"""Two held-out paraphrases; actual local model, no retries or answer templates."""
import os
import json
from pathlib import Path
import sys
import time
import argparse

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'AI'),str(ROOT)]
os.environ['LUMIERE_SEMANTIC_PLANNER_ENABLED']='true'
os.environ['LUMIERE_CUSTOMER_DIALOGUE_URL']='http://127.0.0.1:11435/api/chat'
os.environ['LUMIERE_CUSTOMER_DIALOGUE_MODEL']='qwen3:0.6b-q4_K_M'
from jewelry_agents.semantic_planner import plan_query,_gate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,default=ROOT/'docs/ai-semantic-plan-probe-20261124.json')
    output=parser.parse_args().report
    assert not output.exists(),'Preserve reports'
    report={'successful':False,'cases':[],'retries':0,'scope':'Two unseen wording cases, not general semantic accuracy'}
    try:
        for query,expected in [('Một món ôm quanh ngón tay, đừng quá 3 triệu.','ring'),
                               ('Nói về cách gieo hạt cà chua ở ban công.','off_topic')]:
            started=time.monotonic();plan=plan_query(query)
            passed=bool(plan and (plan.intent=='off_topic' if expected=='off_topic' else
                         plan.intent in {'shop','consult'} and any(e.canonical_id==expected for e in plan.entities)))
            report['cases'].append({'query':query,'plan':plan.model_dump() if plan else None,
                                    'seconds':round(time.monotonic()-started,3),'passed':passed})
        report['successful']=all(case['passed'] for case in report['cases'])
    finally:_gate.close()
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=True))
    return 0 if report['successful'] else 1


if __name__=='__main__':raise SystemExit(main())
