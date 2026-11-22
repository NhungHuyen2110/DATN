"""Actual Qwen API acceptance, exclusively through the private QA proxy.

Run inside the dialogue-acceptance container. No model/HTTP response mocks.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import traceback
import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['normal', 'outage', 'recovery'], required=True)
    args = parser.parse_args()
    base, main_base, provider = (os.environ[name] for name in ('QA_BASE', 'MAIN_BASE', 'OLLAMA_BASE'))
    assert (base, main_base, provider) == ('http://proxy-dialogue-qa:8080',
                                        'http://reverse-proxy:8080', 'http://ollama:11434')
    fixture = json.loads(Path('/qa/private/fixture.json').read_text())
    assert fixture['synthetic_accounts_only'] is True
    results, samples, generation = [], [], {}
    output = Path('/qa/output') / (args.phase + '.json')
    assert not output.exists(), 'Preserve previous dialogue results'
    client = requests.Session()
    client.trust_env = False

    def warm():
        deadline = time.monotonic() + 120
        while True:
            try:
                response = client.get(provider + '/api/tags', timeout=(3, 5))
                response.raise_for_status()
                assert any(model['name'] == 'qwen2.5:3b' for model in response.json()['models'])
                break
            except requests.RequestException:
                if time.monotonic() >= deadline:
                    raise RuntimeError('QA provider did not start within its startup budget') from None
                time.sleep(2)
        response = client.post(provider + '/api/generate', json={
            'model':'qwen2.5:3b', 'prompt':'Xin chào', 'stream':False, 'keep_alive':'5m',
            'options':{'num_ctx':2048,'num_predict':1,'num_thread':2}}, timeout=(3, 180))
        response.raise_for_status()
        value = response.json()
        for key in ('model','load_duration','prompt_eval_count','prompt_eval_duration','eval_count','eval_duration'):
            generation[key] = value.get(key)
        loaded = client.get(provider + '/api/ps', timeout=(3, 5)).json()['models']
        assert len(loaded) == 1 and loaded[0]['name'] == 'qwen2.5:3b'
        generation['resident_model_bytes'] = loaded[0].get('size')
        generation['vram_bytes'] = loaded[0].get('size_vram')

    def login(role):
        session = requests.Session()
        session.trust_env = False
        response = session.post(base + '/api/auth/login', json=fixture['accounts'][role], timeout=(3, 10))
        assert response.status_code == 200, 'QA fixture login failed'
        identity = session.get(base + '/api/auth/me', timeout=(3, 10)).json()
        assert identity['role'] == role
        return session

    def question(session, role, text, conversation_id=None):
        endpoint = '/ai/chat' if role == 'customer' else '/api/' + role + '/ai/chat'
        body = {'query' if role == 'customer' else 'message':text}
        if conversation_id:
            body['conversation_id'] = conversation_id
        started = time.monotonic()
        response = session.post(base + endpoint, json=body, timeout=(3, 48))
        assert response.status_code == 200, 'QA chat returned a non-success HTTP status'
        value = response.json()
        assert isinstance(value.get('answer'), str) and value['answer'].strip()
        assert value.get('products', []) == [], 'Knowledge must not become shopping recommendations'
        return value, time.monotonic() - started

    def business_alive():
        assert client.get(main_base + '/', timeout=(3, 10)).status_code == 200
        data = client.get(main_base + '/api/products?page_size=1', timeout=(3, 10)).json()
        assert data['total'] == 500
        with login('staff') as staff:
            response = staff.post(base + '/api/staff/ai/chat',
                json={'message':'Có bao nhiêu đơn chờ xử lý?'}, timeout=(3, 15))
            assert response.status_code == 200
            data = response.json()
            assert data.get('intent') == 'order_statistics'
            assert data.get('response_mode') != 'local_llm_dialogue'
            # Validate the actual structured aggregate, never ask the LLM to count.
            assert data['data']['value'] == fixture['expected_pending_orders']

    if args.phase in {'normal', 'recovery'}:
        warm()
    if args.phase == 'normal':
        with login('customer') as customer:
            answer, seconds = question(customer, 'customer', 'Đá Ruby là gì?')
            assert answer.get('response_mode') == 'local_llm_dialogue' and answer.get('success') is True
            samples.append({'role':'customer','question':'Đá Ruby là gì?', 'answer':answer['answer'], 'seconds':seconds})
            follow, seconds = question(customer, 'customer', 'Ngắn gọn hơn, chỉ một câu.', answer['conversation_id'])
            assert follow.get('response_mode') == 'local_llm_dialogue'
            assert follow['conversation_id'] == answer['conversation_id']
            samples.append({'role':'customer','question':'Ngắn gọn hơn, chỉ một câu.', 'answer':follow['answer'], 'seconds':seconds})
        results.extend(['customer knowledge uses actual Qwen without products', 'customer follow-up retains server conversation'])
        for role, text in [('staff','Giải thích sự khác nhau giữa dữ liệu và thông tin.'),
                           ('admin','Hãy viết một lời chào ngắn gọn, lịch sự bằng tiếng Việt.')]:
            with login(role) as session:
                answer, seconds = question(session, role, text)
                assert answer.get('response_mode') == 'local_llm_dialogue' and answer.get('success') is True
                samples.append({'role':role, 'question':text, 'answer':answer['answer'], 'seconds':seconds})
            results.append(role + ' authenticated general question uses actual Qwen')
    elif args.phase == 'outage':
        for role in ('customer','staff','admin'):
            with login(role) as session:
                answer, seconds = question(session, role, 'Đá Ruby là gì?')
                assert answer.get('response_mode') != 'local_llm_dialogue'
            results.append(role + ' provider outage produces controlled fallback without product cards')
    else:
        with login('customer') as customer:
            deadline = time.monotonic() + 60
            while True:
                answer, seconds = question(customer, 'customer', 'Đá Ruby là gì?')
                if answer.get('response_mode') == 'local_llm_dialogue':
                    break
                assert time.monotonic() < deadline, 'Dialogue cooldown did not recover'
                time.sleep(5)
            samples.append({'role':'customer', 'question':'Đá Ruby là gì?', 'answer':answer['answer'], 'seconds':seconds})
        results.append('actual Qwen generation resumes after provider restart')
    business_alive()
    results.append('website, 500-product Business catalog and authoritative staff order count remain available')
    report = {'successful':True, 'phase':args.phase, 'cases':results, 'passed':len(results),
              'verified_utc':datetime.now(timezone.utc).isoformat(), 'samples':samples, 'generation':generation,
              'model':'qwen2.5:3b', 'http_mocks':False, 'model_mocks':False,
              'serving_database_written':False, 'qa_login_session_writes':True,
              'human_answer_quality_evaluated':False, 'full_hybrid_llm_stack_tested':False}
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Fixtures/headers never go to published output. Preserve local detail.
        target = Path('/qa/output/failure-detail.log')
        target.write_text(traceback.format_exc(), encoding='utf-8')
        print(json.dumps({'successful':False,'error_type':type(error).__name__,'private_detail_retained':True}))
        raise SystemExit(1)
