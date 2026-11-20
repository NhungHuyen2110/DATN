"""Run isolated regression tests and capture contracts for a Git checkpoint or HEAD."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", help="Read the old cart router from this Git ref, without changing files")
    parser.add_argument("--openapi", type=Path)
    parser.add_argument("--sqlite-bootstrap", action="store_true", help="Use an unused memory engine during app import; no libpq driver needed")
    parser.add_argument("--pytest", action="store_true", help="Include function-style AI/RBAC tests")
    parser.add_argument("--tests", nargs="+", help="Target test filenames inside backend/tests (requires --pytest)")
    args = parser.parse_args()
    if args.tests and not args.pytest:
        parser.error("--tests requires --pytest")
    targets = []
    for name in args.tests or []:
        target = (ROOT / "backend/tests" / name).resolve()
        if target.parent != (ROOT / "backend/tests").resolve() or not target.is_file():
            parser.error("--tests accepts existing filenames inside backend/tests only")
        targets.append(str(target))
    os.environ.setdefault("POSTGRES_DB", "lumiere_test_only")
    os.environ.setdefault("POSTGRES_PASSWORD", "test-placeholder")
    sys.path.insert(0, str(ROOT / "backend"))
    sys.path.insert(0, str(ROOT / "backend/tests"))
    with patch("dotenv.load_dotenv"):
        if args.sqlite_bootstrap:
            import sqlalchemy as sa
            bootstrap_engine = sa.create_engine("sqlite:///:memory:")
            with patch("sqlalchemy.create_engine", return_value=bootstrap_engine):
                import app.core.database
        if args.baseline:
            source = subprocess.check_output(["git", "show", f"{args.baseline}:backend/app/routers/cart.py"], cwd=ROOT)
            module = types.ModuleType("app.routers.cart")
            module.__file__ = str(ROOT / "backend/app/routers/cart.py")
            sys.modules[module.__name__] = module
            exec(compile(source, module.__file__, "exec"), module.__dict__)
        from app.main import app
        if args.openapi:
            args.openapi.parent.mkdir(parents=True, exist_ok=True)
            args.openapi.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
        import run_safe
        if args.pytest:
            import pytest
            import sqlalchemy as sa
            original = sa.engine.Engine.connect

            def memory_only(engine, *a, **kw):
                if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
                    raise AssertionError("Only isolated in-memory SQLite connections are allowed")
                return original(engine, *a, **kw)

            with patch.object(sa.engine.Engine, "connect", memory_only):
                return pytest.main([*(targets or [str(ROOT / "backend/tests")]), "-q", "--disable-warnings"])
        return run_safe.main()


if __name__ == "__main__":
    raise SystemExit(main())
