"""Explicit dev/test index worker. Never reads root .env or applies migrations."""
import argparse
from contextlib import ExitStack, closing
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def local_endpoint(value, schemes, container_host):
    parsed = urlsplit(value or '')
    return (parsed.scheme in schemes and parsed.hostname in {'localhost', '127.0.0.1', '::1', container_host}
            and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', choices=['dev', 'test'], required=True)
    parser.add_argument('--confirm-isolated', action='store_true')
    parser.add_argument('--backup-reference', type=Path)
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--reconcile', action='store_true')
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--max-jobs', type=int, default=100)
    args = parser.parse_args()
    if not args.confirm_isolated or not 1 <= args.max_jobs <= 10000:
        parser.error('Confirm an isolated dev/test environment and max-jobs 1..10000')
    # Parse separate worker credentials; never infer a production target from .env.
    from sqlalchemy.engine import make_url
    try:
        target = make_url(os.environ['LUMIERE_SYNC_DATABASE_URL'])
    except Exception:
        parser.error('Explicit LUMIERE_SYNC_DATABASE_URL required')
    if (target.drivername != 'postgresql+psycopg' or target.host not in {'localhost', '127.0.0.1', '::1', 'postgres'}
            or not target.database or not target.database.startswith('lumiere_' + args.environment)):
        parser.error('Only explicit isolated lumiere_dev*/lumiere_test* PostgreSQL targets are supported')
    if not args.status and (not args.backup_reference or not args.backup_reference.is_file()):
        parser.error('Writes require an existing recovery/backup reference')
    if not args.status:
        from shared.recovery import validate_backup_reference
        try:
            validate_backup_reference(args.backup_reference, args.environment, target.host,
                                      target.port or 5432, target.database)
        except (OSError, ValueError, KeyError, TypeError):
            parser.error('A verified backup-reference JSON matching this exact dev/test database is required')
    os.environ.update({'LUMIERE_LOAD_DOTENV': 'false', 'PRODUCT_INDEX_SYNC_ENABLED': 'true',
                       'POSTGRES_HOST': target.host, 'POSTGRES_PORT': str(target.port or 5432),
                       'POSTGRES_DB': target.database, 'POSTGRES_USER': target.username or '',
                       'POSTGRES_PASSWORD': target.password or '', 'HF_HUB_OFFLINE': '1',
                       'TRANSFORMERS_OFFLINE': '1'})
    sys.path[:0] = [str(ROOT), str(ROOT / 'backend'), str(ROOT / 'AI')]
    try:
        from app.core.database import SessionLocal, engine
        from app.services.product_index_jobs import sync_status
        from app.services.product_index_worker import run_one, reconcile
        with ExitStack() as stack:
            stack.callback(engine.dispose)
            if args.status:
                with SessionLocal() as db:
                    print(json.dumps(sync_status(db)))
                return 0
            observer = None
            metrics_port = int(os.getenv('LUMIERE_WORKER_METRICS_PORT', '0'))
            if metrics_port:
                from shared.worker_metrics import WorkerMetrics
                observer = WorkerMetrics(os.environ.get('LUMIERE_METRICS_TOKEN', ''))
                observer.start(metrics_port, os.getenv('LUMIERE_WORKER_METRICS_HOST', '127.0.0.1'))
                stack.callback(observer.close)
            uri, url = os.environ.get('LUMIERE_SYNC_NEO4J_URI'), os.environ.get('LUMIERE_SYNC_QDRANT_URL')
            if not local_endpoint(uri, {'bolt', 'neo4j'}, 'neo4j') or not local_endpoint(url, {'http', 'https'}, 'qdrant'):
                raise ValueError('Explicit isolated graph/vector endpoints required')
            model_path = Path(os.environ['LUMIERE_SYNC_MODEL_PATH'])
            revision = os.environ['LUMIERE_SYNC_MODEL_REVISION']
            if not model_path.is_dir() or not revision:
                raise ValueError('Cached model path and pinned revision required')
            from sentence_transformers import SentenceTransformer
            from neo4j import GraphDatabase
            from qdrant_client import QdrantClient
            from product_projection import ProductProjection
            # Load before claiming any lease; no event is held during cold start.
            encoder = SentenceTransformer(str(model_path), device='cpu', local_files_only=True)
            driver = stack.enter_context(GraphDatabase.driver(uri, auth=('neo4j', os.environ['LUMIERE_SYNC_GRAPH_PASSWORD']),
                                                               connection_timeout=5, max_transaction_retry_time=10))
            qdrant = stack.enter_context(closing(QdrantClient(url=url, timeout=5)))
            deliver = ProductProjection(driver, 'neo4j', qdrant, encoder,
                                        'paraphrase-multilingual-MiniLM-L12-v2', revision)
            if args.reconcile:
                projected = deliver.known_product_ids()
                with SessionLocal() as db, db.begin():
                    print(json.dumps({'reconciled_jobs': reconcile(db, projected)}))
            processed = 0
            while args.watch or processed < args.max_jobs:
                if observer:
                    observer.refresh(SessionLocal)
                attempt_start = time.perf_counter()
                result = run_one(SessionLocal, deliver)
                if observer:
                    observer.record(result, time.perf_counter() - attempt_start)
                if result['claimed']:
                    print(json.dumps(result), flush=True)
                    processed += 1
                elif args.watch:
                    time.sleep(5)
                else:
                    break
            return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(json.dumps({'error_type': type(exc).__name__, 'completed': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
