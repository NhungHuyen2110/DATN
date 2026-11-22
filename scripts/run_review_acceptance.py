"""Bounded QA acceptance with restoration of the original running services."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.host_process import run_bounded
BASE = ['docker', 'compose', '--env-file', '.env.example', '-p', 'lumiere-rebuild-test',
        '-f', 'compose.yaml', '-f', 'compose.original-data.yaml', '-f', 'compose.ai-acceptance.yaml']
QA = BASE + ['-f', 'compose.review-acceptance.yaml', '--profile', 'review-acceptance', '--profile', 'acceptance']
PAUSE = {'ai-api', 'neo4j', 'qdrant', 'index-worker', 'prometheus', 'grafana'}
RUNNER = 'lumiere-reviewed-attributes-qa-runner'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--suite', choices=['review', 'dialogue'], default='review')
    parser.add_argument('--model-cache', type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Choose a new report path')
    log = ROOT / '.local-tmp' / (args.report.stem + '.private.log')
    if log.exists():
        parser.error('Choose a new report/log name')
    engine_retries = []
    def run(command, timeout=180, retain_output=True, retry_engine_502=False):
        for attempt in range(2 if retry_engine_502 else 1):
            try:
                result = run_bounded(command, cwd=ROOT, timeout=timeout)
            except subprocess.TimeoutExpired as error:
                if retain_output:
                    with log.open('ab') as handle:
                        handle.write((error.output or b'') + (error.stderr or b''))
                raise
            if retain_output:
                with log.open('ab') as handle:
                    handle.write(result.stdout + result.stderr)
            if result.returncode == 0:
                return result.stdout.decode('utf-8')
            if attempt == 0 and retry_engine_502 and b'502 Bad Gateway' in result.stdout + result.stderr:
                engine_retries.append('idempotent compose up retried once after Docker Engine 502')
                time.sleep(2)
                continue
            raise RuntimeError('Local review acceptance command failed; inspect the local log')
    qa = QA
    runner, runner_service = RUNNER, 'review-acceptance'
    dialogue_output = None
    if args.suite == 'dialogue':
        if not args.model_cache or not args.model_cache.is_dir():
            parser.error('Dialogue acceptance requires an existing local model cache')
        manifest = args.model_cache / 'manifests/registry.ollama.ai/library/qwen2.5/3b'
        model = json.loads(manifest.read_text(encoding='utf-8'))
        layers = model['layers']
        if not layers or any(not (args.model_cache / 'blobs' / layer['digest'].replace(':', '-')).is_file()
                             for layer in layers):
            raise ValueError('Cached model is incomplete; this suite never downloads models')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('http://127.0.0.1:11434/api/ps', timeout=5) as response:
            if json.load(response).get('models'):
                raise ValueError('Native Ollama already has a loaded model; avoid overlapping model processes')
        run(['docker', 'image', 'inspect', 'ollama/ollama:0.13.0'], retain_output=False)
        dialogue_output = ROOT / '.local-tmp/original-db-20261122-014434/ai-acceptance' / args.report.stem
        dialogue_output.mkdir(exist_ok=False)
        os.environ['OLLAMA_LOCAL_MODEL_CACHE'] = str(args.model_cache.resolve())
        os.environ['DIALOGUE_QA_OUTPUT'] = str(dialogue_output)
        qa = QA + ['-f', 'compose.dialogue-acceptance.yaml', '--profile', 'dialogue-acceptance']
        runner, runner_service = 'lumiere-dialogue-qa-runner', 'dialogue-acceptance'
    # Check Compose volume mounts before starting or pausing any service.
    config = json.loads(run(qa + ['config', '--format', 'json'], retain_output=False))
    for service, target in [('neo4j-facts-qa', '/data'), ('qdrant-facts-qa', '/qdrant/storage')]:
        mount = next(item for item in config['services'][service]['volumes'] if item['target'] == target)
        if mount['type'] != 'volume' or not mount['source'].startswith('review_qa_'):
            raise ValueError('QA graph/vector must use distinct managed QA volumes')
    if dialogue_output:
        mount = next(item for item in config['services']['ollama']['volumes'] if item['target'] == '/cached-models')
        if mount['type'] != 'bind' or mount.get('read_only') is not True:
            raise ValueError('Existing model cache must be mounted read-only')
    # Config includes example runtime credentials; do not retain its raw dump.
    # Only later tool output is useful to diagnose acceptance.
    log.write_bytes(b'QA target/volume validation passed\n')
    existing = run_bounded(['docker', 'container', 'inspect', runner], cwd=ROOT, timeout=20)
    if existing.returncode == 0:
        raise ValueError('A review acceptance runner already exists; do not overlap tests')
    active = set(run(BASE + ['ps', '--services', '--status', 'running']).split())
    paused = sorted(PAUSE & active)
    restore_ids = []
    if paused:
        containers = run(BASE + ['ps', '-q', *paused]).split()
        details = json.loads(run(['docker', 'inspect', *containers], retain_output=False))
        seen = set()
        for detail in details:
            labels = detail['Config']['Labels']
            service = labels.get('com.docker.compose.service')
            if labels.get('com.docker.compose.project') != 'lumiere-rebuild-test' or service not in paused or service in seen:
                raise ValueError('Refuse to restore an unexpected service container')
            seen.add(service)
            restore_ids.append(detail['Id'])
        if seen != set(paused):
            raise ValueError('Unable to checkpoint all running service identities')
    report = {'successful': False, 'suite': args.suite, 'paused_services': paused}
    try:
        if paused:
            report['stage'] = 'pause_main_ai_services'
            run(BASE + ['stop', '-t', '20', *paused], timeout=150)
        if dialogue_output:
            report['stage'] = 'start_dialogue_qa'
            run(qa + ['up', '-d', '--no-deps', '--wait', '--wait-timeout', '180',
                      'business-qa', 'ai-dialogue-qa', 'proxy-dialogue-qa', 'ollama'], timeout=220, retry_engine_502=True)
            actual_mounts = json.loads(run(['docker', 'inspect', run(qa + ['ps', '-q', 'ollama']).strip()],
                                          retain_output=False))[0]['Mounts']
            assert any(m['Destination'] == '/cached-models' and m['RW'] is False for m in actual_mounts)
            phases = []
            for phase in ('normal', 'outage', 'recovery'):
                report['stage'] = 'dialogue_' + phase
                if phase == 'outage':
                    run(qa + ['stop', '-t', '15', 'ollama'], timeout=60)
                elif phase == 'recovery':
                    run(qa + ['start', 'ollama'], timeout=60)
                output = run(qa + ['run', '--rm', '--no-deps', '-T', '--name', runner,
                                  runner_service, '--phase', phase], timeout=480)
                phases.append(json.loads(output.strip().splitlines()[-1]))
                report['phases'] = phases
            report.update(successful=all(p['successful'] for p in phases),
                          passed=sum(p['passed'] for p in phases), model_cache_read_only=True,
                          full_hybrid_llm_stack_tested=False)
        else:
            report['stage'] = 'start_review_qa'
            run(qa + ['up', '-d', '--no-deps', '--wait', '--wait-timeout', '180',
                      'business-qa', 'frontend-review-qa', 'proxy-review-qa', 'neo4j-facts-qa', 'qdrant-facts-qa'], timeout=220, retry_engine_502=True)
            report['stage'] = 'review_encoder_and_live_integration'
            # The 8 GB Windows lab exceeded the old 480 s cold-import budget.
            # This bounds the whole offline-model acceptance process, not any
            # application request, database statement or retrieval deadline.
            output = run(qa + ['run', '--rm', '--no-deps', '-T', '--name', runner, runner_service], timeout=900)
            report.update(json.loads(output.strip().splitlines()[-1]))
    except Exception as error:
        report['failure_type'] = type(error).__name__
        raise
    finally:
        try:
            remaining = run_bounded(['docker', 'inspect', runner], cwd=ROOT, timeout=20)
            if remaining.returncode == 0:
                detail = json.loads(remaining.stdout)[0]
                labels = detail['Config']['Labels']
                if labels.get('com.docker.compose.project') != 'lumiere-rebuild-test' or labels.get('com.docker.compose.service') != runner_service:
                    raise ValueError('Refuse to stop an unrecognized QA runner')
                run(['docker', 'stop', '-t', '10', runner], timeout=45)
            stopped = (['ollama', 'ai-dialogue-qa', 'proxy-dialogue-qa', 'business-qa'] if dialogue_output
                       else ['neo4j-facts-qa', 'qdrant-facts-qa'])
            run(qa + ['stop', '-t', '15', *stopped], timeout=90)
        except Exception as error:
            report['cleanup_failure_type'] = type(error).__name__
            report['successful'] = False
        finally:
            try:
                if restore_ids:
                    # Start the exact prior containers. Compose start can wait on
                    # Neo4j's cold Java healthcheck before resuming an idle worker.
                    run(['docker', 'start', *restore_ids], timeout=120)
                running = set(run(BASE + ['ps', '--services', '--status', 'running']).split())
                report['paused_services_restored_running'] = set(paused).issubset(running)
            except Exception as error:
                report['restoration_failure_type'] = type(error).__name__
                report['paused_services_restored_running'] = False
            finally:
                report['docker_engine_retries'] = engine_retries
                if not report.get('paused_services_restored_running'):
                    report['successful'] = False
                args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
