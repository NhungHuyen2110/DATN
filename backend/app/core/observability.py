"""Request metrics and structured logs; never record cookies, bodies or query text."""

from collections import Counter
import json
import logging
from threading import Lock
from time import perf_counter

from fastapi.responses import PlainTextResponse


def install_observability(app):
    counts, elapsed, lock = Counter(), Counter(), Lock()
    logger = logging.getLogger("uvicorn.error")

    @app.middleware("http")
    async def observe(request, call_next):
        started = perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            duration = perf_counter() - started
            if route != "/metrics":
                key = (route, request.method, str(status))
                with lock:
                    counts[key] += 1
                    elapsed[key] += duration
                logger.info(json.dumps({"event": "http_request", "route": route,
                                        "method": request.method, "status": status,
                                        "duration_seconds": round(duration, 6)}))

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        lines = ["# TYPE lumiere_http_requests_total counter", "# TYPE lumiere_http_duration_seconds_total counter"]
        with lock:
            for (route, method, status), count in sorted(counts.items()):
                labels = f'route={json.dumps(route)},method={json.dumps(method)},status="{status}"'
                lines.extend([f"lumiere_http_requests_total{{{labels}}} {count}",
                              f"lumiere_http_duration_seconds_total{{{labels}}} {elapsed[(route, method, status)]}"])
        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
