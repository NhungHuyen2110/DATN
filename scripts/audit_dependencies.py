"""Offline inventory only: no installation, service startup, model load or DB call."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
PROBES = ("fastapi", "sqlalchemy", "psycopg", "neo4j", "qdrant_client", "sentence_transformers", "pandas", "numpy", "sklearn", "pytest", "httpx")


def command(arguments, timeout=15, env=None):
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout, env=env, encoding="utf-8", errors="replace")
        return {"exit_code": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error_type": type(exc).__name__}


def requirement_status(path, visited=None):
    visited = visited or set()
    path = path.resolve()
    if path in visited:
        raise ValueError("Recursive requirements include")
    records = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.split(" #",1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            records.extend(requirement_status(path.parent/line[3:].strip(), visited|{path}))
            continue
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate():
            status, version = "skipped_marker", None
        else:
            try:
                version = metadata.version(requirement.name)
                status = "compatible" if requirement.specifier.contains(version,prereleases=True) else "version_mismatch"
            except metadata.PackageNotFoundError:
                status, version = "not_installed", None
        records.append({"file":path.relative_to(ROOT).as_posix(), "requirement":str(requirement), "installed":version, "status":status})
    return records


def import_probe(module):
    # Import SDK/library only. Never instantiate SentenceTransformer or a client.
    code = "import importlib,json,sys\ntry:\n importlib.import_module(sys.argv[1]); print(json.dumps({'status':'importable'}))\nexcept Exception as exc:\n print(json.dumps({'status':'import_failed','error_type':type(exc).__name__,'application_control_blocked':'Application Control' in str(exc)}))"
    env = {**os.environ, "HF_HUB_OFFLINE":"1", "TRANSFORMERS_OFFLINE":"1"}
    result = command([sys.executable,"-I","-c",code,module], timeout=45, env=env)
    try:
        return {"module":module, **json.loads(result.get("stdout", "").splitlines()[-1])}
    except (IndexError,ValueError):
        return {"module":module, "status":"probe_failed", "error_type":result.get("error_type", "subprocess_failed")}


def source_imports():
    groups = {"backend_runtime":[ROOT/"backend/app"], "backend_tests":[ROOT/"backend/tests"],
              "backend_tools":[*list((ROOT/"backend").glob("*.py")),ROOT/"backend/alembic"],
              "modular_ai":[ROOT/"AI/lumiere",ROOT/"AI/api.py",ROOT/"AI/sync_catalog.py",ROOT/"AI/evaluate_retrieval.py"],
              "ai_tests":[ROOT/"AI/tests"], "dataset_tools":[ROOT/"generators",ROOT/"utils",ROOT/"config",ROOT/"main.py",ROOT/"convert_images.py",ROOT/"download_jewelry_images.py"],
              "scripts":[ROOT/"scripts"]}
    groups["legacy_ai"] = [p for p in (ROOT/"AI").rglob("*.py") if "lumiere" not in p.parts and "tests" not in p.parts and p.name not in {"api.py","sync_catalog.py","evaluate_retrieval.py"}]
    files = {name:sorted({f for p in paths for f in (p.rglob("*.py") if p.is_dir() else [p]) if f.exists()}) for name,paths in groups.items()}
    local_names = {p.stem for paths in files.values() for p in paths} | {"app","lumiere","generators","utils","config","jewelry_agents","knowledge_graph","rag","tests"}
    distributions = metadata.packages_distributions()
    missing_names = {"PIL":"Pillow","faker":"Faker","requests":"requests","crewai":"crewai"}
    report = {}
    for name,paths in files.items():
        imports, errors = set(), []
        for path in paths:
            try:
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
                for node in ast.walk(tree):
                    if isinstance(node,ast.Import):
                        imports.update(alias.name.split(".")[0] for alias in node.names)
                    elif isinstance(node,ast.ImportFrom) and node.level == 0 and node.module:
                        imports.add(node.module.split(".")[0])
            except (SyntaxError,UnicodeError) as exc:
                errors.append({"file":path.relative_to(ROOT).as_posix(),"error_type":type(exc).__name__})
        external = sorted(imports-set(sys.stdlib_module_names)-local_names-{"__future__"})
        report[name] = {"scanned_files":len(paths),"parse_errors":errors,"third_party":[
            {"import":module,"distributions":distributions.get(module,[missing_names.get(module,module)]),
             "installed_distribution_found":module in distributions} for module in external]}
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"docs/evidence/dependency-audit.json")
    parser.add_argument("--metadata-only",action="store_true")
    args=parser.parse_args()
    packages=sorted(({"name":d.metadata["Name"],"version":d.version} for d in metadata.distributions()),key=lambda p:p["name"].casefold())
    paths=[ROOT/"requirements.txt",ROOT/"requirements-dev.txt",*sorted((ROOT/"backend").glob("requirements*.txt")),*sorted((ROOT/"AI").glob("requirements*.txt"))]
    cfg=Path(sys.prefix)/"pyvenv.cfg"
    system_site=("include-system-site-packages = true" in cfg.read_text(encoding="utf-8").lower()) if cfg.exists() else None
    report={"generated_utc":datetime.now(timezone.utc).isoformat(),"policy":"offline inventory; no installs, model loads, database calls or Docker start",
            "python":{"version":sys.version.split()[0],"executable":sys.executable,"is_venv":sys.prefix!=sys.base_prefix,"system_site_packages":system_site},
            "installed_distributions":packages,"requirements":{p.relative_to(ROOT).as_posix():requirement_status(p) for p in paths},
            "source_imports":source_imports(),"pip_check":command([sys.executable,"-m","pip","check"]),
            "import_probes":[],"tools":{}}
    if not args.metadata_only:
        with ThreadPoolExecutor(max_workers=3) as executor:
            for future in as_completed([executor.submit(import_probe,module) for module in PROBES]):
                probe=future.result()
                report["import_probes"].append(probe)
                print(probe["module"],probe["status"],flush=True)
    report["tools"]["node"] = command([str(ROOT/".cache/node.exe"),"--version"]) if (ROOT/".cache/node.exe").exists() else {"path":shutil.which("node")}
    docker=shutil.which("docker")
    if docker:
        images=command([docker,"image","ls","--format","{{.Repository}}:{{.Tag}} {{.Size}}"])
        report["tools"]["docker"]={"cli_present":True,"images_inventory":images.get("stdout","").splitlines() if images.get("exit_code")==0 else None,
            "status":"available" if images.get("exit_code")==0 else "engine_unavailable_or_access_denied"}
    else:
        report["tools"]["docker"]={"cli_present":False,"images_inventory":None}
    report["tools"]["frontend"]={"node_modules_present":(ROOT/"frontend/node_modules").exists(),"npm_on_path":shutil.which("npm") is not None,
        "playwright_lock_version":json.loads((ROOT/"frontend/package-lock.json").read_text(encoding="utf-8"))["packages"]["node_modules/@playwright/test"]["version"]}
    cache=ROOT/".cache/hf/models"
    report["cached_model"]={"path":".cache/hf/models","present":cache.exists(),"stored_bytes":sum(p.stat().st_size for p in cache.rglob("*") if p.is_file()) if cache.exists() else 0,
        "note":"Disk usage only; no model loaded/downloaded, no new transfer size estimated"}
    report["portable_runtimes"]=[p.name for p in (ROOT/".cache/runtime").iterdir() if p.is_dir()] if (ROOT/".cache/runtime").exists() else []
    args.output.parent.mkdir(parents=True,exist_ok=True)
    active=report["requirements"]["requirements-dev.txt"]+report["requirements"]["AI/requirements-semantic.txt"]
    gaps=[r for r in active if r["status"] not in {"compatible","skipped_marker"}]
    report["summary"]={"installed_distributions":len(packages),"active_profile_gaps":gaps,
        "import_probe_failures":[p for p in report["import_probes"] if p["status"] != "importable"]}
    report["status"]="METADATA_ONLY" if args.metadata_only else ("READY" if not gaps and report["pip_check"].get("exit_code")==0 and not report["summary"]["import_probe_failures"] else "PARTIAL")
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"packages":len(packages),"active_profile_gaps":gaps,"pip_check_exit":report["pip_check"].get("exit_code")}),flush=True)
    return 0 if not gaps and report["pip_check"].get("exit_code")==0 and not report["summary"]["import_probe_failures"] else 1

if __name__=="__main__":
    raise SystemExit(main())
