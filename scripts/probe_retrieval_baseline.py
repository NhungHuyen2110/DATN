"""Reproduce retrieval defects offline using actual function AST and fake inputs.

No import of retrieval.py: its model/driver initialization must not run in audit.
Exit 1 means a defect was reproduced; it is not an infrastructure test result.
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
from pathlib import Path
import re


def probe(root: Path) -> dict:
    path = root / "AI/jewelry_agents/retrieval.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    names = {"extract_category", "extract_material", "extract_gold_type", "extract_gemstone",
             "parse_money", "extract_price_filter", "hybrid_search"}
    selected = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names],
                          type_ignores=[])
    namespace = {"re": re}
    exec(compile(selected, str(path), "exec"), namespace)
    product = {"ProductID": 1, "Category": "Nhẫn", "Material": "Bạc 925", "Gemstone": "CZ",
               "Price": 7_000_000, "Stock": 1}
    namespace["search_qdrant"] = lambda *a, **k: [{"ProductID": 1, "score": 0.8}]
    namespace["search_neo4j_fallback"] = lambda *a, **k: []
    report = {}
    for label, changes in (("missing_price", {"Price": None}), ("out_of_stock", {"Stock": 0}),
                           ("strict_upper_bound", {"Price": 8_000_000})):
        namespace["get_product_from_neo4j"] = lambda pid, changes=changes: dict(product, **changes)
        with contextlib.redirect_stdout(io.StringIO()):
            actual = namespace["hybrid_search"]("Top 3 nhẫn dưới 8 triệu", top_k=3)
        report[label] = {"expected_count": 0, "actual_count": len(actual), "pass": not actual}

    def unavailable(*args, **kwargs):
        raise ConnectionError("synthetic Qdrant outage")

    namespace["search_qdrant"] = unavailable
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            namespace["hybrid_search"]("nhẫn dưới 8 triệu", top_k=3)
    except ConnectionError:
        report["qdrant_outage"] = {"pass": False, "actual": "unhandled ConnectionError"}
    else:
        # This proves only that ConnectionError was contained, not fallback relevance.
        report["qdrant_outage"] = {"pass": True, "actual": "ConnectionError contained"}
    return report


if __name__ == "__main__":
    result = probe(Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if all(item["pass"] for item in result.values()) else 1)
