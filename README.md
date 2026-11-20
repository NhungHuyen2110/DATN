# LUMIÈRE

Jewelry storefront, FastAPI business backend and independent AI service.
The existing vanilla HTML/CSS/JavaScript frontend and business API remain in place.

Architectural refactoring is incremental. Cart now uses a domain/application/repository
boundary; modular AI retrieval is opt-in with `AI_PIPELINE=modular`.
The default local AI path remains legacy. Isolated staging Compose explicitly selects modular.

Start with [the audit and requirement status matrix](docs/00-audit-as-is.md),
[migration ledger](docs/02-migration-plan.md), [validation results](docs/06-testing-and-evaluation.md)
and [staging/rollback runbook](docs/07-deployment-and-rollback.md).
The original `MASTER_PROMPT_LUMIERE_AI_REBUILD_VSCODE.md` is now available and has been read.
See [the 19-section conformance audit](docs/08-master-prompt-conformance.md) for the
continuation gaps and acceptance evidence; full-system acceptance remains pending.

Reuse the current `.venv` for offline checks; audit dependencies before installing anything:

```text
python scripts/run_business_checks.py --sqlite-bootstrap --pytest
python -m unittest discover -s AI/tests -p test_modular_pipeline.py -v
python -m unittest discover -s AI/tests -p test_api_contract.py -v
python AI/sync_catalog.py
node --test frontend/tests/unit/http-client.test.mjs
```

Before installing, run `.venv/Scripts/python.exe scripts/audit_dependencies.py` and read
[the environment audit](docs/11-dependencies-and-environment.md). The current `.venv`
already satisfies runtime/dev/semantic requirements; no installation is needed for the
maintained checks. Root `requirements.txt` and `requirements-dev.txt` collect these profiles.
Modular model loading defaults to local files only; downloads require explicit operator opt-in.

`sync_catalog.py` validates only unless explicitly given `--apply`.
Use `compose.rebuild.yaml` for isolated staging; `docker-compose.yml` and its existing
PostgreSQL volume are preserved. Real Neo4j, multilingual embeddings and local Qdrant
acceptance have passed; see [live evidence](docs/evidence/ai-live-acceptance.json).
Container runtime and browser end-to-end validation remain pending.

The [500-product label review CSV](docs/review/product-label-review.csv) and
[136 Vietnamese benchmark candidates](docs/review/benchmark-candidates.csv) are all
`PENDING_REVIEW`. See [review instructions](docs/09-data-review-and-benchmark.md).
Pending rows are excluded from evaluation; no AI quality score is published from them.

```text
python scripts/run_ai_checks.py
python AI/evaluate_retrieval.py --dataset docs/review/benchmark-candidates.csv --output docs/evidence/benchmark-review-status.json --inspect-only
```
