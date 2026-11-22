"""Opt-in ASGI metrics and correlation IDs; never logs query strings or bodies."""
from contextlib import contextmanager
from contextvars import ContextVar
import hmac
import json
import logging
import os
import time
from uuid import UUID, uuid4

_current_metrics = ContextVar('lumiere_metrics', default=None)
_request_id = ContextVar('lumiere_request_id', default=None)
logger = logging.getLogger('lumiere.requests')


def correlation_headers():
    value = _request_id.get()
    return {'X-Request-ID': value} if value else {}


def record_intent(intent):
    metrics = _current_metrics.get()
    if metrics is None:
        return
    allowed = {'product_search', 'greeting', 'restricted_request', 'shipping_policy',
               'unverified_policy', 'customer_order_guidance', 'out_of_scope'}
    metrics.intent.labels(metrics.service, intent if intent in allowed else 'other').inc()


@contextmanager
def measure(stage):
    metrics = _current_metrics.get()
    if metrics is None:
        yield
        return
    allowed = {'parse', 'catalog', 'lexical', 'dense', 'graph', 'fusion', 'rerank', 'verification'}
    if stage not in allowed:
        raise ValueError('Unbounded metric stage')
    start, outcome = time.perf_counter(), 'ok'
    try:
        yield
    except BaseException:
        outcome = 'error'
        raise
    finally:
        metrics.stage.labels(metrics.service, stage, outcome).observe(time.perf_counter() - start)


class Metrics:
    def __init__(self, service):
        from prometheus_client import CollectorRegistry, Counter, Histogram, ProcessCollector
        self.service = service
        self.registry = CollectorRegistry()
        # Linux containers expose process CPU/RAM through /proc; unsupported
        # platforms may omit these families without failing HTTP instrumentation.
        ProcessCollector(namespace='lumiere', registry=self.registry)
        self.http = Counter('lumiere_http_requests_total', 'Completed HTTP requests',
                            ['service', 'method', 'route', 'status'], registry=self.registry)
        self.duration = Histogram('lumiere_http_duration_seconds', 'HTTP duration in seconds',
                                  ['service', 'method', 'route'], registry=self.registry,
                                  buckets=(.005, .025, .1, .25, .5, 1, 2.5, 5, 10, 30, 60))
        self.stage = Histogram('lumiere_ai_stage_seconds', 'AI stage duration and outcome',
                               ['service', 'stage', 'outcome'], registry=self.registry,
                               buckets=(.005, .025, .1, .25, .5, 1, 2.5, 5, 10, 30, 60))
        self.intent = Counter('lumiere_ai_requests_total', 'Public AI requests by bounded intent',
                              ['service', 'intent'], registry=self.registry)


class ObservabilityMiddleware:
    def __init__(self, app, metrics, token):
        self.app, self.metrics, self.token = app, metrics, token

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        if scope['path'] == '/internal/metrics':
            supplied = headers.get(b'authorization', b'')
            authorized = self.token and hmac.compare_digest(supplied, b'Bearer ' + self.token.encode())
            if not authorized:
                await send({'type': 'http.response.start', 'status': 404, 'headers': []})
                await send({'type': 'http.response.body', 'body': b''})
                return
            from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
            await send({'type': 'http.response.start', 'status': 200,
                        'headers': [(b'content-type', CONTENT_TYPE_LATEST.encode())]})
            await send({'type': 'http.response.body', 'body': generate_latest(self.metrics.registry)})
            return
        try:
            request_id = str(UUID(headers.get(b'x-request-id', b'').decode('ascii')))
        except (ValueError, UnicodeError):
            request_id = str(uuid4())
        request_token = _request_id.set(request_id)
        metrics_token = _current_metrics.set(self.metrics)
        start, status = time.perf_counter(), 500

        async def wrapped_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                message = {**message, 'headers': [*message.get('headers', []),
                                                  (b'x-request-id', request_id.encode())]}
            await send(message)
        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            duration = time.perf_counter() - start
            route = getattr(scope.get('route'), 'path', 'unmatched')
            method = scope.get('method', 'OTHER')
            if method not in {'GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'}:
                method = 'OTHER'
            self.metrics.http.labels(self.metrics.service, method, route, str(status)).inc()
            self.metrics.duration.labels(self.metrics.service, method, route).observe(duration)
            logger.info(json.dumps({'service': self.metrics.service, 'request_id': request_id,
                                    'method': method, 'route': route, 'status': status,
                                    'duration_seconds': round(duration, 6)}))
            _current_metrics.reset(metrics_token)
            _request_id.reset(request_token)


def install(app, service):
    if os.getenv('LUMIERE_METRICS_ENABLED', 'false').lower() != 'true':
        return None
    metrics = Metrics(service)
    app.add_middleware(ObservabilityMiddleware, metrics=metrics,
                       token=os.getenv('LUMIERE_METRICS_TOKEN', ''))
    return metrics
