"""Versioned data configuration; no SDK or environment side effects."""

import json
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def load_aliases(path: Path | None = None) -> dict:
    data = json.loads((path or CONFIG_DIR / "aliases_vi.json").read_text(encoding="utf-8"))
    if not data.get("version") or not isinstance(data.get("entities"), dict):
        raise ValueError("Alias dictionary needs a version and entities")
    for kind, concepts in data["entities"].items():
        for canonical_id, definition in concepts.items():
            if not canonical_id or not definition.get("name") or not definition.get("aliases"):
                raise ValueError(f"Invalid alias definition: {kind}/{canonical_id}")
    return data


def load_graph_schema() -> dict:
    data = json.loads((CONFIG_DIR / "knowledge_graph_schema.json").read_text(encoding="utf-8"))
    # Prevent configuration from injecting Cypher identifiers; labels/types are schema choices.
    import re
    for definition in data["taxonomy"] + data["evidence_facets"]:
        for key in ("label", "key", "relationship"):
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", definition[key]):
                raise ValueError("Graph schema contains an invalid identifier")
    return data
