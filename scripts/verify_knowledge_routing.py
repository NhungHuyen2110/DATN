"""Real local API smoke: knowledge routing, not natural answer quality."""
import argparse
import json
from pathlib import Path
import time
import traceback
import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Preserve previous evidence; choose a new report')
    private = ROOT / '.local-tmp/original-db-20261122-014434/ai-acceptance'
    fixture = json.loads((private / 'fixture.json').read_text(encoding='utf-8'))
    assert fixture['synthetic_accounts_only'] is True
    question = 'Đá Ruby là gì?'
    report = {'successful': False, 'cases': [], 'main_accounts_modified': False,
              'qa_login_sessions_written': True, 'natural_llm_live_verified': False,
              'scope': 'Actual local API routing with dialogue disabled; not answer quality or full hybrid acceptance'}
    try:
        for role in ('customer', 'staff', 'admin'):
            with requests.Session() as session:
                session.trust_env = False
                base = 'http://127.0.0.1:18080' if role == 'customer' else 'http://127.0.0.1:18081'
                if role != 'customer':
                    response = session.post(base + '/api/auth/login', json=fixture['accounts'][role],
                                            timeout=(3, 10), allow_redirects=False)
                    assert response.status_code == 200, 'QA login unavailable'
                    response = session.get(base + '/api/auth/me', timeout=(3, 10), allow_redirects=False)
                    assert response.status_code == 200 and response.json()['role'] == role
                endpoint = '/ai/chat' if role == 'customer' else '/api/' + role + '/ai/chat'
                started = time.monotonic()
                response = session.post(base + endpoint,
                    json={'query' if role == 'customer' else 'message': question},
                    timeout=(3, 15), allow_redirects=False)
                assert response.status_code == 200, 'Knowledge endpoint unavailable'
                value = response.json()
                assert value.get('success') is True and value.get('intent') == 'general_question'
                assert value.get('products') == [] and value.get('response_mode') != 'local_llm_dialogue'
                report['cases'].append({'role': role, 'question': question, 'http_status': 200,
                    'intent': value['intent'], 'products': 0, 'fallback_not_model_answer': True,
                    'seconds': round(time.monotonic() - started, 3)})
                if role == 'staff':
                    response = session.post(base + endpoint, json={'message': 'Có bao nhiêu đơn chờ xử lý?'},
                                            timeout=(3, 15), allow_redirects=False)
                    assert response.status_code == 200
                    value = response.json()
                    assert value['intent'] == 'order_statistics'
                    assert value['data']['value'] == fixture['expected_pending_orders']
                    report['authoritative_staff_order_count_verified'] = True
        report.update(successful=True, passed=4)
    except Exception as error:
        (private / (args.report.stem + '-failure.log')).write_text(traceback.format_exc(), encoding='utf-8')
        report.update(failure_type=type(error).__name__, private_detail_retained=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['successful'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
