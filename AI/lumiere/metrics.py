"""Process-local chat metrics, intentionally excluding query content."""

from collections import Counter
from threading import Lock

counts = Counter()
lock = Lock()


def record_chat(result):
    with lock:
        counts["requests"] += 1
        counts["products"] += len(result.get("products", []))
        for source in result.get("degraded_sources", []):
            if source in ("dense", "graph", "lexical"):
                counts[source] += 1


def render():
    with lock:
        lines = ["# TYPE lumiere_ai_chat_requests_total counter",
                 f'lumiere_ai_chat_requests_total {counts["requests"]}',
                 "# TYPE lumiere_ai_products_returned_total counter",
                 f'lumiere_ai_products_returned_total {counts["products"]}',
                 "# TYPE lumiere_ai_source_failures_total counter"]
        for source in ("dense", "graph", "lexical"):
            lines.append(f'lumiere_ai_source_failures_total{{source="{source}"}} {counts[source]}')
        return "\n".join(lines) + "\n"
