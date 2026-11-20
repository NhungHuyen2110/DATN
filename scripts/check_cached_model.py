"""Load only the existing workspace model cache with network connections forbidden."""
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"AI"))

def main():
    cache=ROOT/".cache/hf/models"
    if not cache.is_dir():
        print("BLOCKED: existing model cache is absent; no download attempted")
        return 2
    os.environ.update({"AI_MODEL_CACHE":str(cache),"AI_ALLOW_MODEL_DOWNLOAD":"false",
                       "HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1"})
    before={str(p.relative_to(cache)):p.stat().st_size for p in cache.rglob("*") if p.is_file()}
    from lumiere.bootstrap import SemanticModelProvider,DEFAULT_MODEL
    with patch("socket.socket.connect",side_effect=AssertionError("Network is forbidden during cached-model check")):
        vectors=SemanticModelProvider().encode(["nhẫn bạc", "trang sức"])
    after={str(p.relative_to(cache)):p.stat().st_size for p in cache.rglob("*") if p.is_file()}
    assert before==after,"Model cache files changed during offline verification"
    assert len(vectors)==2 and all(len(v)==384 for v in vectors)
    report={"status":"PASS","model":DEFAULT_MODEL,"dimension":384,"vectors":2,
        "allow_model_download":False,"network_connections_forbidden":True,"cache_unchanged":True,
        "scope":"Existing-cache runtime smoke; not a semantic quality benchmark"}
    output=ROOT/"docs/evidence/model-cache-policy.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
