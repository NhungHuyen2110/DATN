"""Refresh local progress from existing reports and the latest guarded backend log; no service access."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    log = ROOT / '.local-tmp/conversation-backend.log'
    raw = log.read_bytes()
    text = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig', errors='replace')
    result = re.search(r'(\d+) passed, (\d+) warnings?, (\d+) subtests passed in ([\d.]+)s', text)
    if not result or re.search(r'\b(?:FAILED|ERRORS|failed)\b', text):
        raise ValueError('Latest complete passing backend summary required')
    backend = {'passed': int(result[1]), 'subtests_passed': int(result[3]),
               'warnings': int(result[2]), 'duration_seconds': float(result[4]),
               'log': str(log.relative_to(ROOT)), 'log_sha256': hashlib.sha256(raw).hexdigest(),
               'scope': 'guarded offline runner: SQLite memory only, external network blocked',
               'unique_scenarios_not_claimed': True}

    def report(name):
        return json.loads((ROOT / 'docs' / name).read_text(encoding='utf-8-sig'))

    ai_name = ('dense-anchor-worker-tests-20261122.json'
               if (ROOT / 'docs/dense-anchor-worker-tests-20261122.json').exists() else
               'conversation-context-model-tests-20261122.json'
               if (ROOT / 'docs/conversation-context-model-tests-20261122.json').exists() else
               'ai-advice-contract-final-20261122.json'
               if (ROOT / 'docs/ai-advice-contract-final-20261122.json').exists() else
               'ai-source-diagnostics-tests-20261122.json'
               if (ROOT / 'docs/ai-source-diagnostics-tests-20261122.json').exists()
               else 'ai-limits-contract-final-20261122.json')
    ai = report(ai_name)
    browser = report('native-public-recommendation-browser-final-20261121.json')
    live = report('live-business-model-graph-retrieval-final-20261121.json')
    backup = report('backup-restore-guard-final-20261121.json')
    sync = report('postgres-worker-metrics-integration.json')
    ablation = report('ablation-smoke-20261121/summary.json')
    docker_browser_name = 'compose-release-full-browser-20261122.json'
    docker_browser = report(docker_browser_name)
    storage = report('docker-storage-verification-20261122.json')
    network_worker = report('qdrant-named-volume-real-model-worker-20261122.json')
    fault_name = 'compose-semantic-ai-fault-20261122.json'
    fault = report(fault_name)
    subset_name = docker_browser_name
    subset = report(subset_name)
    worker_build = report('docker-worker-bootstrap-image-20261122.json')
    semantic = report('compose-semantic-verified-r2-20261122.json')
    operations = report('compose-demo-operations-20261122.json')
    ci = report('github-ci-baseline-20261122.json')
    hosting_seed = report('hosting-catalog-bootstrap-rehearsal-20261122.json')
    caption = report('compose-public-copy-browser-20261122.json')
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
    if not all(item['successful'] for item in (ai, browser, live, backup, sync, storage, network_worker, docker_browser, semantic, operations, ci, hosting_seed)):
        raise ValueError('Required evidence contains a failed result')
    if not all(fault.get(key) is True for key in ('isolation_passed', 'recovered', 'recovered_product_live_price_stock_verified')):
        raise ValueError('Container fault/recovery evidence required')
    current = {
        'updated_utc': datetime.now(timezone.utc).isoformat(),
        'branch': branch, 'complete_project': False,
        'source_state': 'Demo branch; exact source/CI commits recorded separately; no production activation',
        'acceptance_checklist': '12-acceptance-status.md',
        'backend_regression': backend,
        'offline_ai_tests': {**ai, 'passed': ai['tests_run'] - ai['skipped'],
                             'report': ai_name},
        'docker_browser_integration': {**docker_browser,
            'report': docker_browser_name,
            'scope_note': '18/18 with actual graph/vector/model, worker and Grafana; five synthetic products'},
        'compose_semantic': semantic,
        'compose_operations': operations,
        'github_ci_baseline': ci,
        'hosting_catalog_bootstrap_rehearsal': hosting_seed,
        'frontend_caption_smoke': caption,
        'docker_storage': {**storage, 'old_c_copy_removed_after_verified_hash': True,
            'cleanup_report': 'docker-storage-cleanup-20261122.json',
            'active_data_do_not_delete': '.local-tmp/docker-desktop-data'},
        'docker_ai_fault': {**fault, 'report': fault_name,
            'scope_note': 'Single synthetic lab episode on bounded-source image; not an SLA'},
        'docker_browser_latest_subset': {**subset, 'report': subset_name,
            'scope_note': 'Supersedes failed earlier subsets; full dependency/cold-start/load matrix still pending'},
        'runtime_open_issue': 'Local 18-case semantic/monitoring demo passed; hosting and wider load/fault acceptance pending',
        'runtime_resources': {'report': 'runtime-memory-pressure-20261122.json',
            'native_graph_lab_running': False, 'original_user_applications_closed': False},
        'browser_integration': {'passed': browser['stats']['expected'],
                                'skipped': browser['stats']['skipped'], 'flaky': browser['stats']['flaky'],
                                'unexpected': browser['stats']['unexpected'], 'schema_setup': browser['schema_setup'],
                                'report': 'native-public-recommendation-browser-final-20261121.json'},
        'csv_to_graph': {'catalog_products': 500, 'catalog_relationships': 2500, 'imports_executed': 2,
                         'uniqueness_constraints': 6, 'historical_import_report': 'neo4j-catalog-import-second.json',
                         'note': 'Additional synthetic fixtures exist; do not mistake historical counts for current global counts'},
        'real_live_catalog_smoke': {'successful': live['successful'], 'catalog': live['catalog'],
                                    'qdrant': live['qdrant'], 'model_revision': live['model_revision'],
                                    'concurrent_change_candidate_excluded': live['concurrent_price_stock_change']['stale_candidate_excluded'],
                                    'quality_benchmark': False, 'report': 'live-business-model-graph-retrieval-final-20261121.json'},
        'product_index_sync': {'postgres_checks_passed': len(sync['checks']),
                               'enabled_on_current_business_database': False,
                               'migration_applied_to_current_database': False,
                               'network_qdrant_real_model_worker_verified': network_worker['successful'],
                               'full_compose_worker_verified': True,
                               'enabled_on_isolated_compose_demo': True,
                               'reports': ['postgres-worker-metrics-integration.json', 'qdrant-named-volume-real-model-worker-20261122.json']},
        'observability': {**browser['monitoring'], 'enabled_on_existing_serving_processes': False,
                          'screenshot': 'figures/grafana-native-20261121.png',
                          'worker_queue_verified': True},
        'compose_monitoring': {'targets': operations['prometheus_targets'],
                              'screenshot':'figures/grafana-compose-20261122.png', 'browser_verified':True},
        'native_fault_injection': browser['native_fault_injection'],
        'backup_restore': {'successful': backup['successful'], 'table_count': len(backup['table_counts']),
                           'migration_head': backup['migration_head'], 'production_accessed': False,
                           'worker_backup_guard': backup['worker_backup_guard'],
                           'report': 'backup-restore-guard-final-20261121.json'},
        'deployment_packaging': {'services': 11, 'independent_builds': ['frontend', 'business-api', 'ai-api', 'index-worker'],
                                 'compose_parse': 'passed', 'images_built': ['frontend', 'business-api', 'ai-api', 'index-worker'],
                                 'worker_image_built': worker_build['successful'],
                                 'worker_build_attempt': worker_build,
                                 'core_containers_started': ['postgres', 'business-api', 'frontend', 'reverse-proxy', 'ai-api'],
                                 'core_runtime_report': 'compose-core-runtime-20261122.json',
                                 'core_optional_graph_dense': 'actual Compose graph/dense/model verified',
                                 'running_demo_services':10, 'ollama_enabled':False,
                                 'container_ai_fault_test_executed': True, 'full_fault_matrix_executed': False,
                                 'github_workflows_executed': True,
                                 'docker_data_vhd_physically_on_d': True, 'public_deployment': False},
        'evaluation': {'draft_queries': 105, 'human_reviewed_queries': 0,
                       'smoke_predictions': sum(mode['queries'] for mode in ablation['modes'].values()),
                       'quality_metrics_computed': False, 'controlled_latency_comparison': False,
                       'note': 'Smoke run predates related-reference query enhancement',
                       'report': 'ablation-smoke-20261121/summary.json'},
        'remaining': ['Full per-file semantic audit', 'Evidence-backed Audience/Style facts and human-reviewed benchmark',
                      'Remaining dependency fault matrix; controlled cold-start/concurrency/load acceptance',
                      '500-catalog full hosting semantic acceptance; 105-query SQL ablation',
                      'LLM narrative/grounding evaluation', 'Full CI/CD scans/staging/approved hosting/HTTPS',
                      'Host/container exporters, alerts and complete DATN diagrams/report']}
    original_path = ROOT / 'docs/original-project-data-readonly-20261122.json'
    if original_path.exists():
        original = report(original_path.name)
        if not original.get('successful') or not original.get('serving_application_switched'):
            raise ValueError('Original data activation evidence failed')
        current['active_dataset'] = {**original, 'report': original_path.name,
            'browser': report('original-project-browser-20261122.json'),
            'prior_18_case_suite_scope': 'historical synthetic five-product DB; not rerun against original accounts'}
        semantic_path = ROOT / 'docs/original-project-semantic-20261122.json'
        current['active_dataset']['semantic_verification'] = report(semantic_path.name) if semantic_path.exists() else 'pending'
        advice_path = ROOT / 'docs/semantic-shopping-advice-live-20261122.json'
        if advice_path.exists():
            current['active_dataset']['shopping_advice_smoke']=report(advice_path.name)
            current['active_dataset']['shopping_advice_browser']=report('shopping-advice-browser-20261122.json')
        current['runtime_open_issue'] = 'Original project data activated; full role/write regression on original-data copy and hosting acceptance pending'
        conversation_path=ROOT/'docs/dense-anchor-conversation-browser-20261122.json'
        if not conversation_path.exists():
            conversation_path=ROOT/'docs/conversation-browser-final-20261122.json'
        if conversation_path.exists():
            current['conversation_regression']=report(conversation_path.name)
            current['natural_dialogue_llm']={'live_verified':False,'local_enabled':False,
                'prepared_override':'compose.dialogue.yaml','target':'approved VPS; monthly budget <=300000 VND',
                'needs':['server and model provisioning','actual Qwen quality, latency and privacy acceptance']}
        current['product_index_sync']['enabled_on_current_business_database'] = True
        current['product_index_sync']['migration_applied_to_current_database'] = True
    anchor_final = ROOT / 'docs/dense-anchor-runtime-final-20261122.json'
    if anchor_final.exists():
        current['dense_anchor_runtime'] = report(anchor_final.name)
        current['dense_anchor_runtime']['report'] = anchor_final.name
        current['dense_anchor_runtime']['failed_cold_probe_report'] = 'dense-anchor-runtime-20261122.json'
        current['runtime_open_issue'] = ('Dense-anchor smoke recorded; cold/concurrent load, full role/write regression, '
                                         'real Qwen dialogue and approved hosting acceptance remain open')
    roles_path = ROOT / 'docs/dense-anchor-roles-browser-20261122.json'
    if roles_path.exists():
        current['original_data_roles_browser'] = report(roles_path.name)
    for filename, data in [('backend-regression-demo-final-20261122.json', backend), ('current-implementation.json', current)]:
        (ROOT / 'docs' / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'backend_passed': backend['passed'], 'backend_subtests': backend['subtests_passed'],
                      'ai_passed': current['offline_ai_tests']['passed'], 'browser_passed': browser['stats']['expected'],
                      'project_complete': False}))


if __name__ == '__main__':
    main()
