"""Opt-in real PostgreSQL locking tests against an explicitly EMPTY test database."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Refusing to overwrite report')
    from sqlalchemy import create_engine, inspect, select, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker
    url = make_url(os.environ.get('LUMIERE_SYNC_TEST_URL', ''))
    if (url.drivername != 'postgresql+psycopg' or url.host not in {'127.0.0.1', 'localhost', 'postgres'}
            or not url.database or not url.database.startswith('lumiere_test_')):
        parser.error('Explicit isolated lumiere_test_* PostgreSQL URL required')
    os.environ.update({'LUMIERE_LOAD_DOTENV': 'false', 'POSTGRES_DB': 'unused',
                       'POSTGRES_PASSWORD': 'unused', 'PRODUCT_INDEX_SYNC_ENABLED': 'false'})
    sys.path[:0] = [str(ROOT), str(ROOT / 'backend')]
    from app.core.database import Base
    from app.models import Product, Category, Material, Gemstone, Brand, Collection, ProductIndexJob as Job
    from app.services.product_index_jobs import enqueue, claim_one, acknowledge
    from app.services.product_index_worker import run_one, projection_lock, ProjectionBusy
    engine = create_engine(url, connect_args={'connect_timeout': 3, 'options': '-c statement_timeout=5000 -c lock_timeout=3000'})
    checks = []
    try:
        if inspect(engine).get_table_names():
            raise ValueError('Target is not empty; refusing all writes')
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        with factory() as db, db.begin():
            for model in (Category, Material, Gemstone, Brand, Collection):
                db.add(model(id=1, name='Synthetic ' + model.__name__))
            db.flush()
            db.add(Product(id=900010, sku='SYNTHETIC900010', barcode='900010', name='Synthetic sync fixture',
                           category_id=1, material_id=1, gemstone_id=1, brand_id=1, collection_id=1,
                           weight=1, sale_price=100, wholesale_price=80, cost_price=60, stock=10))
        os.environ['PRODUCT_INDEX_SYNC_ENABLED'] = 'true'
        with factory() as db:
            db.get(Product, 900010).stock = 9
            db.flush()
            assert db.get(Job, 900010).generation == 1
            db.rollback()
        with factory() as db:
            assert db.get(Job, 900010) is None
            assert db.get(Product, 900010).stock == 10
        checks.append('business_and_outbox_rollback_atomic')
        def enqueue_thread(_):
            with factory() as db, db.begin():
                enqueue(db, 900010)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(enqueue_thread, range(12)))
        with factory() as db:
            assert db.get(Job, 900010).generation == 12
        checks.append('concurrent_upsert_preserves_all_12_generations')
        # Sequential distinct connections exercise actual PG session locks,
        # without starting parallel heavyweight jobs or contacting any index.
        with projection_lock(factory, 900010):
            try:
                with projection_lock(factory, 900010):
                    raise AssertionError('Concurrent advisory lock unexpectedly acquired')
            except ProjectionBusy:
                pass
        with projection_lock(factory, 900010):
            pass
        checks.append('advisory_lock_excludes_other_connection_and_releases_after_use')
        with factory() as db, db.begin():
            enqueue(db, 900011)
        now = datetime.now(timezone.utc)
        with factory() as first, first.begin():
            first.scalar(select(Job).where(Job.product_id == 900010).with_for_update())
            with factory() as second, second.begin():
                claim = claim_one(second, now=now)
                assert claim.product_id == 900011
                assert acknowledge(second, claim, now=now)
        checks.append('skip_locked_claims_other_job_while_first_row_locked')
        received = []
        result = run_one(factory, lambda pid, row, gen: received.append((pid, row['Stock'], gen)))
        assert result['acknowledged'] and received == [(900010, 10, 12)]
        checks.append('worker_reads_current_product_and_acknowledges_real_postgres_job')
        with factory() as db, db.begin():
            db.get(Product, 900010).stock = 7
        received = []
        assert run_one(factory, lambda pid, row, gen: received.append(row['Stock']))['acknowledged']
        assert received == [7]
        checks.append('orm_update_emits_next_job_without_manual_enqueue')
        with factory() as db, db.begin():
            db.delete(db.get(Product, 900010))
        received = []
        assert run_one(factory, lambda pid, row, gen: received.append(row))['acknowledged']
        assert received == [None]
        checks.append('delete_keeps_tombstone_job_after_product_disappears')
        from shared.worker_metrics import WorkerMetrics
        with factory() as db, db.begin():
            enqueue(db, 900012)
        observer = WorkerMetrics('synthetic-postgres-metrics')
        try:
            observer.refresh(factory)
            observer.start(0)
            endpoint = 'http://127.0.0.1:' + str(observer.server.server_port) + '/internal/metrics'
            try:
                urlopen(endpoint, timeout=3)
            except HTTPError as exc:
                assert exc.code == 404
            else:
                raise AssertionError('Worker metrics must not be public')
            request = Request(endpoint, headers={'Authorization': 'Bearer synthetic-postgres-metrics'})
            with urlopen(request, timeout=3) as response:
                text_metrics = response.read().decode()
            assert 'lumiere_sync_jobs{state="pending"} 1.0' in text_metrics
            assert 'lumiere_sync_status_available 1.0' in text_metrics
            started = time.perf_counter()
            result = run_one(factory, lambda *args: None)
            observer.record(result, time.perf_counter() - started)
            assert result['acknowledged']
        finally:
            observer.close()
        checks.append('authenticated_worker_metrics_export_actual_postgres_queue_state')
        with engine.connect() as connection:
            version = connection.scalar(text('SHOW server_version'))
        report = {'successful': True, 'postgres_version': version, 'checks': checks,
                  'projection_delivery': 'injected function; not full Neo4j/Qdrant integration',
                  'production_accessed': False, 'fixture_data_preserved_for_inspection': True}
        with args.report.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps(report))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
