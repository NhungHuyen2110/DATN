"""Capture a checkpoint's route schema without executing its model/database imports."""

import argparse
import ast
import json
from pathlib import Path
import subprocess
import types

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ref")
    args = parser.parse_args()
    source = subprocess.check_output(["git", "show", f"{args.ref}:AI/api.py"], cwd=ROOT).decode("utf-8")
    tree = ast.parse(source)
    # Schema-only capture: route handlers are not called. Remove known eager imports
    # and CSV reads; preserve every decorator, signature and Pydantic schema.
    excluded = {"rag.rag_service", "hybrid_recommendation", "hybrid_recommendation_v2"}
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.ImportFrom) and node.module in excluded
        or isinstance(node, ast.Import) and any(alias.name == "pandas" for alias in node.names)
        or isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "products" for target in node.targets)
    )]
    module = types.ModuleType("api")
    exec(compile(tree, "AI/api.py", "exec"), module.__dict__)
    destination = ROOT / "docs/baseline/ai-openapi.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(module.app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Captured {len(module.app.openapi()['paths'])} AI paths (schema only)")


if __name__ == "__main__":
    main()
