"""Loopback-only Prometheus/Grafana lab around source test APIs, all storage on D."""
import base64
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TOKEN = 'synthetic-native-monitoring'
ADMIN_PASSWORD = 'synthetic-monitoring-admin-2026'


class NativeMonitoringLab:
    def __init__(self, artifact_dir, environment):
        self.root = artifact_dir / 'monitoring'
        self.root.mkdir(exist_ok=False)
        self.environment = environment
        self.processes = []

    def launch(self, arguments, name, cwd, environment):
        with (self.root / (name + '.log')).open('w', encoding='utf-8') as log:
            process = subprocess.Popen(arguments, cwd=cwd, env=environment, stdout=log, stderr=log,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.processes.append(process)
        return process

    @staticmethod
    def json_get(url, grafana=False):
        headers = {}
        if grafana:
            headers['Authorization'] = 'Basic ' + base64.b64encode(('admin:' + ADMIN_PASSWORD).encode()).decode()
        with urlopen(Request(url, headers=headers), timeout=4) as response:
            return json.load(response)

    def start(self):
        for port in (19090, 13000):
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', port))
        binaries = ROOT / '.local-tmp/native-monitoring/binaries'
        prometheus = next((binaries / 'prometheus').rglob('prometheus.exe'))
        grafana = next((binaries / 'grafana').rglob('grafana.exe'))
        grafana_home = grafana.parent.parent
        config = self.root / 'prometheus.yml'
        config.write_text('''global:
  scrape_interval: 2s
  evaluation_interval: 2s
scrape_configs:
  - job_name: lumiere-applications
    metrics_path: /internal/metrics
    authorization:
      type: Bearer
      credentials: synthetic-native-monitoring
    static_configs:
      - targets: ['127.0.0.1:18001', '127.0.0.1:18000']
''', encoding='utf-8')
        self.launch([str(prometheus), '--config.file=' + str(config), '--web.listen-address=127.0.0.1:19090',
                     '--storage.tsdb.path=' + str(self.root / 'prometheus-data'), '--storage.tsdb.retention.time=1d'],
                    'prometheus', prometheus.parent, self.environment)
        provisioning = self.root / 'provisioning'
        (provisioning / 'datasources').mkdir(parents=True)
        (provisioning / 'dashboards').mkdir()
        dashboards = self.root / 'dashboards'
        dashboards.mkdir()
        shutil.copy2(ROOT / 'infra/grafana/dashboards/lumiere.json', dashboards / 'lumiere.json')
        (provisioning / 'datasources/prometheus.yml').write_text('''apiVersion: 1
datasources:
  - name: Prometheus
    uid: lumiere-prometheus
    type: prometheus
    access: proxy
    url: http://127.0.0.1:19090
    isDefault: true
    editable: false
''', encoding='utf-8')
        (provisioning / 'dashboards/lumiere.yml').write_text('''apiVersion: 1
providers:
  - name: Lumiere
    type: file
    options:
      path: ''' + json.dumps(str(dashboards)) + '\n', encoding='utf-8')
        data, logs, plugins = (self.root / name for name in ('grafana-data', 'grafana-logs', 'grafana-plugins'))
        for directory in (data, logs, plugins):
            directory.mkdir(parents=True)
        env = {**self.environment, 'GF_SERVER_HTTP_ADDR': '127.0.0.1', 'GF_SERVER_HTTP_PORT': '13000',
               'GF_SERVER_ROOT_URL': 'http://127.0.0.1:13000/', 'GF_SERVER_SERVE_FROM_SUB_PATH': 'false',
               'GF_PATHS_DATA': str(data), 'GF_PATHS_LOGS': str(logs), 'GF_PATHS_PLUGINS': str(plugins),
               'GF_PATHS_PROVISIONING': str(provisioning), 'GF_DATABASE_TYPE': 'sqlite3',
               'GF_DATABASE_PATH': str(data / 'grafana.db'), 'GF_SECURITY_ADMIN_USER': 'admin',
               'GF_SECURITY_ADMIN_PASSWORD': ADMIN_PASSWORD, 'GF_AUTH_ANONYMOUS_ENABLED': 'false',
               'GF_AUTH_BASIC_ENABLED': 'true', 'GF_USERS_ALLOW_SIGN_UP': 'false',
               'GF_ANALYTICS_REPORTING_ENABLED': 'false', 'GF_ANALYTICS_CHECK_FOR_UPDATES': 'false',
               'GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES': 'false', 'GF_PLUGINS_PREINSTALL_DISABLED': 'true'}
        self.launch([str(grafana), 'server', '--homepath', str(grafana_home),
                     'cfg:default.paths.logs=' + str(logs)], 'grafana', grafana_home, env)
        ready = False
        for _ in range(90):
            if any(process.poll() is not None for process in self.processes):
                break
            try:
                health = self.json_get('http://127.0.0.1:13000/api/health')
                if health.get('database') == 'ok':
                    ready = True
                    break
            except OSError:
                time.sleep(1)
        if not ready:
            raise RuntimeError('Native monitoring startup failed; inspect isolated logs')

    def verify(self):
        query = urlencode({'query': 'up{job="lumiere-applications"}'})
        samples = []
        for _ in range(20):
            data = self.json_get('http://127.0.0.1:19090/api/v1/query?' + query)
            samples = data['data']['result']
            if len(samples) == 2 and all(float(item['value'][1]) == 1 for item in samples):
                break
            time.sleep(1)
        if len(samples) != 2 or any(float(item['value'][1]) != 1 for item in samples):
            raise ValueError('Both actual API targets must be scraped successfully')
        for _ in range(20):
            with urlopen('http://127.0.0.1:18001/health/live', timeout=3) as response:
                assert response.status == 200
            payload = json.dumps({'query': 'Top 1 nhẫn', 'top_k': 1}).encode()
            with urlopen(Request('http://127.0.0.1:18000/chat', data=payload,
                                 headers={'Content-Type': 'application/json'}), timeout=5) as response:
                assert json.load(response)['returned_k'] == 1
            time.sleep(.2)
        dashboard = self.json_get('http://127.0.0.1:13000/api/dashboards/uid/lumiere-runtime', grafana=True)
        proxy = self.json_get('http://127.0.0.1:13000/api/datasources/proxy/uid/lumiere-prometheus/api/v1/query?' + query,
                              grafana=True)
        if len(proxy['data']['result']) != 2:
            raise ValueError('Grafana datasource did not query actual Prometheus data')
        result = {'successful': True, 'prometheus_targets_up': [item['metric']['instance'] for item in samples],
                  'grafana_dashboard_uid': dashboard['dashboard']['uid'], 'grafana_datasource_query_verified': True,
                  'source': 'actual source APIs and PostgreSQL synthetic fixtures, lexical AI fallback',
                  'production_accessed': False, 'native_not_docker': True}
        with (self.root / 'verification.json').open('x', encoding='utf-8') as handle:
            json.dump(result, handle, indent=2)
        return result

    def stop(self):
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
