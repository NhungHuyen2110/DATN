"""Opt-in worker metrics. HTTP reads cached gauges; never queries the DB under a scrape."""
from datetime import datetime, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading


class WorkerMetrics:
    def __init__(self, token):
        if not token:
            raise ValueError('Worker metrics require a private scrape token')
        from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
        self.token = token
        self.registry = CollectorRegistry()
        self.enabled = Gauge('lumiere_sync_enabled', 'Whether product synchronization is enabled', registry=self.registry)
        self.available = Gauge('lumiere_sync_status_available', 'Whether the last status poll succeeded', registry=self.registry)
        self.jobs = Gauge('lumiere_sync_jobs', 'Durable jobs by bounded state', ['state'], registry=self.registry)
        self.lag = Gauge('lumiere_sync_oldest_pending_seconds', 'Age of oldest undelivered generation', registry=self.registry)
        self.last_success = Gauge('lumiere_sync_last_success_timestamp_seconds', 'Last acknowledged success', registry=self.registry)
        self.outcomes = Counter('lumiere_sync_attempts_total', 'Claimed delivery outcomes', ['outcome'], registry=self.registry)
        self.poll_errors = Counter('lumiere_sync_status_poll_errors_total', 'Failed status polls', registry=self.registry)
        self.lease_lost = Counter('lumiere_sync_lease_lost_total', 'Deliveries requiring lease-lost repair', registry=self.registry)
        self.duration = Histogram('lumiere_sync_job_seconds', 'Claim/read/deliver/ack duration', registry=self.registry)
        self.event_lag = Histogram('lumiere_sync_event_to_index_seconds', 'Dirty generation to both indexes acknowledged',
                                   registry=self.registry, buckets=(1, 5, 10, 30, 60, 120, 300, 3600, 86400))
        self.server = self.thread = None

    def update(self, status):
        self.enabled.set(int(status['enabled']))
        self.available.set(1)
        for state in ('pending', 'processing', 'done', 'dead'):
            self.jobs.labels(state).set(status['states'].get(state, 0))
        self.lag.set(status.get('oldest_pending_seconds') or 0)
        timestamp = status.get('last_success')
        value = datetime.fromisoformat(timestamp) if timestamp else None
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        self.last_success.set(value.timestamp() if value else 0)

    def refresh(self, factory):
        from app.services.product_index_jobs import enabled, sync_status
        if not enabled():
            self.update({'enabled': False, 'states': {}, 'oldest_pending_seconds': None, 'last_success': None})
            return
        try:
            with factory() as db:
                self.update(sync_status(db))
        except Exception:
            self.available.set(0)
            self.poll_errors.inc()

    def record(self, result, elapsed):
        if result.get('claimed'):
            self.outcomes.labels('delivered' if result['delivered'] else 'error').inc()
            self.duration.observe(elapsed)
            if not result['acknowledged']:
                self.lease_lost.inc()
            lag = result.get('event_to_index_seconds')
            if result.get('completed') and lag is not None:
                self.event_lag.observe(lag)

    def authorized(self, header):
        return hmac.compare_digest((header or '').encode(), ('Bearer ' + self.token).encode())

    def start(self, port, host='127.0.0.1'):
        if host not in {'127.0.0.1', '0.0.0.0'} or not 0 <= port <= 65535:
            raise ValueError('Invalid metrics bind address')
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # Do not log request paths, authorization or query strings.
            def do_GET(self):
                if self.path != '/internal/metrics' or not owner.authorized(self.headers.get('Authorization')):
                    self.send_response(404)
                    self.end_headers()
                    return
                from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
                content = generate_latest(owner.registry)
                self.send_response(200)
                self.send_header('Content-Type', CONTENT_TYPE_LATEST)
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
        self.server = ThreadingHTTPServer((host, port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
