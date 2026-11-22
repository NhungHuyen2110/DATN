"""Offline source inventory. Never imports application code or reads .env/data.

Run from any directory: python -B scripts/audit_workspace.py --report <new-file>
The report is written exclusively when requested; existing reports are protected.
Static parsing is NOT a claim that a file was semantically reviewed or tested.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = ("AI", "backend", "frontend", "Website", "scripts", "generators", "utils", "config", ".github")
EXCLUDED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "test-results", "backup"}
SUFFIXES = {".py", ".js", ".html", ".css", ".yml", ".yaml", ".toml", ".cypher", ".ini", ".ps1"}


def source_paths(root: Path):
    for path in sorted(root.iterdir()):
        if path.is_file() and path.suffix.lower() in SUFFIXES:
            yield path
    for directory in SOURCE_ROOTS:
        base = root / directory
        if not base.is_dir() or base.is_symlink():
            continue
        for current, directories, filenames in os.walk(base, followlinks=False):
            directories[:] = sorted(name for name in directories if name not in EXCLUDED
                                     and (Path(current) / name).resolve().is_relative_to(root.resolve()))
            for name in sorted(filenames):
                yield Path(current) / name


def inventory(root: Path) -> dict:
    files = []
    for path in source_paths(root):
            relative = path.relative_to(root)
            if (not path.is_file() or path.is_symlink()
                    or any(part in EXCLUDED for part in relative.parts)
                    or path.suffix.lower() not in SUFFIXES
                    or path.name.startswith(".env")):
                continue
            # Resolve before reading, so a directory junction cannot escape root.
            if not path.resolve().is_relative_to(root.resolve()):
                continue
            raw = path.read_bytes()
            entry = {
                "path": relative.as_posix(), "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "review_status": "inventory-only",
            }
            try:
                source = raw.decode("utf-8-sig")
                entry["lines"] = len(source.splitlines())
                if path.suffix == ".py":
                    tree = ast.parse(source, filename=str(relative))
                    entry["syntax"] = "pass"
                    entry["definitions"] = [
                        {"name": node.name, "line": node.lineno}
                        for node in ast.walk(tree)
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                    ]
            except (UnicodeError, SyntaxError) as exc:
                entry["syntax"] = "fail"
                # Do not include source text from syntax exceptions.
                entry["error"] = {"type": type(exc).__name__, "line": getattr(exc, "lineno", None)}
            files.append(entry)
    return {
        "format_version": 1,
        "scope": "offline inventory and Python AST syntax only; no imports, database or model calls",
        "files": files,
        "summary": {"files": len(files), "python_files": sum(f["path"].endswith(".py") for f in files),
                    "syntax_failures": sum(f.get("syntax") == "fail" for f in files)},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Create a NEW JSON report, never overwrite")
    args = parser.parse_args()
    result = inventory(ROOT)
    if args.report:
        with args.report.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    print(json.dumps(result["summary"]))
    return 1 if result["summary"]["syntax_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
