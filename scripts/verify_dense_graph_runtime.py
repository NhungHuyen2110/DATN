"""Read-only live dense-anchor-graph checks; credentials remain inside AI container."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Refusing to replace an existing report')
    # Fixed public catalog queries only. No credentials or customer data printed.
    probe = r'''
import json,os,urllib.request
from decimal import Decimal
rows=[]
for query in ['sinh nh\u1eadt t\u1eb7ng g\u00ec','Top 3 nh\u1eabn d\u01b0\u1edbi 8 tri\u1ec7u','Top 5 b\u00f4ng tai']:
 request=urllib.request.Request('http://127.0.0.1:8000/internal/retrieval-diagnostics',
   data=json.dumps({'query':query,'top_k':3}).encode(),
   headers={'Content-Type':'application/json','Authorization':'Bearer '+os.environ['LUMIERE_AI_DIAGNOSTICS_TOKEN']})
 with urllib.request.urlopen(request,timeout=30) as response: data=json.load(response)
 d=data.get('diagnostics',{})
 rows.append({'query':query,'status':data['status'],'requested_k':data['requested_k'],
  'product_ids':[p['ProductID'] for p in data['products']],
  'dense_candidates':len(d.get('source_ranks',{}).get('dense',[])),
  'graph_candidates':len(d.get('source_ranks',{}).get('graph',[])),
  'anchor_paths':sum(1 for p in data['products'] for edge in p.get('graph_paths',[]) if edge.get('source_product_id')),
  'live_values_verified':all(p.get('verified_source')=='business_api' and p['Stock']>0 and Decimal(str(p['Price']))>=0 for p in data['products']),
  'budget_category_verified':all(p['CategoryID']==1 and Decimal(str(p['Price']))<8000000 for p in data['products']) if '8 tri' in query else None,
  'source_errors':d.get('source_errors',{}),'timings_seconds':d.get('timings_seconds',{})})
print(json.dumps(rows,ensure_ascii=True))
'''
    command = ['docker', 'compose', '--env-file', '.env.example', '-p', 'lumiere-rebuild-test',
               '-f', 'compose.yaml', '-f', 'compose.original-data.yaml',
               'exec', '-T', 'ai-api', 'python', '-B', '-']
    attempts = []
    rows = []
    for attempt in range(6):
        result = subprocess.run(command, input=probe, text=True, encoding='utf-8',
                                capture_output=True, timeout=110, cwd=ROOT)
        if result.returncode:
            attempts.append({'attempt': attempt + 1, 'ready': False, 'error': 'container_probe_failed'})
        else:
            rows = json.loads(result.stdout)
            ready = all(row['status'] == 'ok' and row['dense_candidates'] > 0 for row in rows)
            attempts.append({'attempt': attempt + 1, 'ready': ready,
                             'source_errors': [row['source_errors'] for row in rows]})
            if ready:
                break
        if attempt < 5:
            time.sleep(5)

    def chat(query, token=None):
        request = urllib.request.Request('http://127.0.0.1:18080/ai/chat',
            data=json.dumps({'query': query, 'conversation_id': token}).encode(),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=40) as response:
            return json.load(response)

    first = chat('sinh nhật tặng gì')
    second = chat('tại sao lại gợi ý sản phẩm đó', first.get('conversation_id'))
    third = chat('có hỏi sản phẩm đâu mà trả lời', first.get('conversation_id'))
    worker_command = command.copy()
    worker_command[worker_command.index('ai-api')] = 'business-api'
    worker_probe = ('import json; from app.core.database import SessionLocal; '
                    'from app.services.product_index_jobs import sync_status; '
                    'session=SessionLocal(); print(json.dumps(sync_status(session))); session.close()')
    worker_result = subprocess.run(worker_command, input=worker_probe, text=True, encoding='utf-8',
                                   capture_output=True, timeout=40, cwd=ROOT)
    worker = json.loads(worker_result.stdout) if worker_result.returncode == 0 else {'error': 'read_failed'}
    ids = [p['ProductID'] for p in first.get('products', [])]
    checks = {
        'all_dense_graph_sources_healthy': bool(rows) and all(r['status'] == 'ok' and r['dense_candidates'] for r in rows),
        'birthday_has_anchor_paths': bool(rows) and rows[0]['anchor_paths'] > 0,
        'top_k_count_unique': bool(rows) and all(len(r['product_ids']) == len(set(r['product_ids'])) <= r['requested_k'] for r in rows),
        'live_values_and_budget_verified': bool(rows) and all(r['live_values_verified'] and r['budget_category_verified'] is not False for r in rows),
        'public_birthday_has_products': first.get('status') == 'ok' and bool(ids),
        'explanation_keeps_previous_ids': second.get('referenced_product_ids') == ids and not second.get('products'),
        'correction_does_not_search_products': third.get('status') == 'conversation_correction' and not third.get('products'),
        'original_catalog_sync_queue_drained': worker.get('states') == {'done': 500},
    }
    report = {'read_only': True, 'dataset': 'original_full_project_copy', 'attempts': attempts,
              'queries': rows, 'worker': worker, 'checks': checks, 'successful': all(checks.values()),
              'natural_llm_live_verified': False, 'quality_benchmark': 'not_evaluated'}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'successful': report['successful'], 'checks': checks}))
    return 0 if report['successful'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
