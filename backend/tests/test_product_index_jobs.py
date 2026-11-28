from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import Product, Category, Brand, Material, Gemstone, Collection, ProductIndexJob as Job
from app.services.product_index_jobs import enqueue, claim_one, acknowledge, sync_status
from app.services.product_index_worker import run_one, reconcile, current_product
from app.services.product_index_worker import ProjectionBusy, projection_lock


class ProductIndexJobTests(unittest.TestCase):
    def setUp(self):
        self.flags = patch.dict(os.environ, {'PRODUCT_INDEX_SYNC_ENABLED': 'false'})
        self.flags.start()
        self.addCleanup(self.flags.stop)
        self.engine = sa.create_engine('sqlite:///:memory:', poolclass=StaticPool,
                                       connect_args={'check_same_thread': False})
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.factory() as db, db.begin():
            for model in (Category, Brand, Material, Gemstone, Collection):
                db.add(model(id=1, name=model.__name__))
            db.flush()
            db.add(Product(id=1, sku='TEST1', barcode='00001', name='Synthetic fixture', category_id=1,
                           brand_id=1, material_id=1, gemstone_id=1, collection_id=1, weight=1,
                           sale_price=100, wholesale_price=80, cost_price=60, stock=10))
        self.now = datetime(2026, 11, 18, tzinfo=timezone.utc)

    def change(self, stock):
        with patch.dict(os.environ, {'PRODUCT_INDEX_SYNC_ENABLED': 'true'}), self.factory() as db, db.begin():
            db.get(Product, 1).stock = stock

    def queue(self):
        with self.factory() as db, db.begin():
            enqueue(db, 1, now=self.now)

    def test_disabled_hook_does_not_query_missing_outbox_table(self):
        Job.__table__.drop(self.engine)
        with self.factory() as db, db.begin():
            db.get(Product, 1).stock = 9
        with self.factory() as db:
            self.assertEqual(sync_status(db)['enabled'], False)

    def test_new_product_with_explicit_catalog_id_is_queued_in_same_transaction(self):
        with patch.dict(os.environ, {'PRODUCT_INDEX_SYNC_ENABLED': 'true'}), self.factory() as db, db.begin():
            product = Product(id=2, sku='NEW-ID', barcode='00002', name='New identity', category_id=1,
                              brand_id=1, material_id=1, gemstone_id=1, collection_id=1,
                              weight=1, sale_price=100, wholesale_price=80, cost_price=60, stock=2)
            db.add(product)
            db.flush()
            self.assertIsNotNone(product.id)
            self.assertEqual(db.get(Job, product.id).generation, 1)
            product_id = product.id
        received = []
        run_one(self.factory, lambda pid, row, gen: received.append((pid, row['Stock'])))
        self.assertEqual(received, [(product_id, 2)])

    def test_reconcile_repairs_bulk_updates_and_missing_projected_products(self):
        with self.factory() as db, db.begin():
            db.execute(sa.update(Product).where(Product.id == 1).values(stock=4))
            self.assertEqual(reconcile(db, projected_ids=[1, 999]), 2)
        received = []
        for _ in range(2):
            run_one(self.factory, lambda pid, row, gen: received.append((pid, None if row is None else row['Stock'])))
        self.assertEqual(received, [(1, 4), (999, None)])

    def test_lost_lease_delivery_queues_repair_after_newer_worker_finishes(self):
        self.queue()
        def overlapping_delivery(pid, row, generation):
            result = run_one(self.factory, lambda *args: None, now=self.now + timedelta(seconds=121))
            self.assertTrue(result['acknowledged'])
        result = run_one(self.factory, overlapping_delivery, now=self.now)
        self.assertFalse(result['acknowledged'])
        with self.factory() as db:
            self.assertEqual(db.get(Job, 1).status, 'pending')
            self.assertEqual(db.get(Job, 1).generation, 2)
        self.assertTrue(run_one(self.factory, lambda *args: None, now=self.now)['acknowledged'])

    def test_business_rollback_also_rolls_back_queue(self):
        with patch.dict(os.environ, {'PRODUCT_INDEX_SYNC_ENABLED': 'true'}), self.factory() as db:
            db.get(Product, 1).stock = 8
            db.flush()
            self.assertEqual(db.get(Job, 1).generation, 1)
            db.rollback()
        with self.factory() as db:
            self.assertEqual(db.get(Product, 1).stock, 10)
            self.assertIsNone(db.get(Job, 1))

    def test_flushes_coalesce_but_next_transaction_advances_generation(self):
        with patch.dict(os.environ, {'PRODUCT_INDEX_SYNC_ENABLED': 'true'}), self.factory() as db, db.begin():
            product = db.get(Product, 1)
            product.stock = 9
            db.flush()
            product.stock = 8
            db.flush()
            self.assertEqual(db.get(Job, 1).generation, 1)
        self.change(7)
        with self.factory() as db:
            self.assertEqual(db.get(Job, 1).generation, 2)

    def test_taxonomy_rename_enqueues_affected_products(self):
        with patch.dict(os.environ, {'PRODUCT_INDEX_SYNC_ENABLED': 'true'}), self.factory() as db, db.begin():
            db.get(Category, 1).name = 'Updated synthetic category'
        with self.factory() as db:
            self.assertEqual(db.get(Job, 1).generation, 1)

    def test_active_lease_is_not_overtaken_and_expired_ack_is_rejected(self):
        self.queue()
        with self.factory() as db, db.begin():
            first = claim_one(db, now=self.now)
        with self.factory() as db, db.begin():
            self.assertIsNone(claim_one(db, now=self.now + timedelta(seconds=1)))
        with self.factory() as db, db.begin():
            second = claim_one(db, now=self.now + timedelta(seconds=121))
        self.assertNotEqual(first.token, second.token)
        with self.factory() as db, db.begin():
            self.assertFalse(acknowledge(db, first, now=self.now + timedelta(seconds=122)))
            self.assertTrue(acknowledge(db, second, now=self.now + timedelta(seconds=122)))

    def test_exhausted_lease_does_not_hide_next_pending_job(self):
        self.queue()
        with self.factory() as db, db.begin():
            first = claim_one(db, now=self.now, max_attempts=1)
            enqueue(db, 2, now=self.now)
        with self.factory(autoflush=False) as db, db.begin():
            next_claim = claim_one(db, now=self.now + timedelta(seconds=121), max_attempts=1)
            self.assertEqual(next_claim.product_id, 2)
            self.assertEqual(db.get(Job, first.product_id).status, 'dead')

    def test_new_business_update_during_delivery_is_not_lost(self):
        self.queue()
        with self.factory() as db, db.begin():
            first = claim_one(db, now=self.now)
        self.change(8)
        with self.factory() as db, db.begin():
            self.assertEqual(db.get(Job, 1).status, 'processing')
            acknowledge(db, first, now=self.now)
        received = []
        result = run_one(self.factory, lambda pid, row, gen: received.append((pid, row['Stock'], gen)), now=self.now)
        self.assertTrue(result['delivered'])
        self.assertEqual(received, [(1, 8, 2)])
        with self.factory() as db:
            self.assertEqual(db.get(Job, 1).delivered_generation, 2)

    def test_retry_backoff_dead_letter_and_error_redaction(self):
        self.queue()
        def fail(*args):
            raise ConnectionError('SECRET-MUST-NOT-BE-STORED')
        first = run_one(self.factory, fail, now=self.now, max_attempts=2)
        self.assertEqual(first['error_type'], 'ConnectionError')
        self.assertFalse(run_one(self.factory, fail, now=self.now + timedelta(seconds=1))['claimed'])
        run_one(self.factory, fail, now=self.now + timedelta(seconds=3), max_attempts=2)
        with self.factory() as db:
            job = db.get(Job, 1)
            self.assertEqual(job.status, 'dead')
            self.assertEqual(job.last_error_type, 'ConnectionError')

    def test_restart_after_partial_delivery_replays_idempotently(self):
        self.queue()
        graph, vectors = set(), set()
        def interrupted(pid, row, generation):
            graph.add(pid)
            raise TimeoutError('synthetic failure before vectors')
        run_one(self.factory, interrupted, now=self.now)
        def recovered(pid, row, generation):
            graph.add(pid)
            vectors.add(pid)
        run_one(self.factory, recovered, now=self.now + timedelta(seconds=3))
        self.assertEqual(graph, {1})
        self.assertEqual(vectors, {1})
        with self.factory() as db:
            self.assertEqual(db.get(Job, 1).status, 'done')

    def test_delete_preserves_tombstone_job_without_customer_data(self):
        with patch.dict(os.environ, {'PRODUCT_INDEX_SYNC_ENABLED': 'true'}), self.factory() as db, db.begin():
            db.delete(db.get(Product, 1))
        received = []
        # Use real current time since the hook timestamp is generated at commit.
        run_one(self.factory, lambda pid, row, gen: received.append((pid, row)))
        self.assertEqual(received, [(1, None)])

    def test_sync_status_is_admin_only_and_disabled_mode_is_schema_independent(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.core.database import get_db
        from app.routers.auth import get_current_user
        from app.routers.ai_admin import router
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: object()
        client = TestClient(app)
        self.assertEqual(client.get('/admin/ai/sync-status').status_code, 401)
        for role, status in (('customer', 403), ('staff', 403), ('admin', 200)):
            app.dependency_overrides[get_current_user] = lambda role=role: SimpleNamespace(role=SimpleNamespace(name=role))
            response = client.get('/admin/ai/sync-status')
            self.assertEqual(response.status_code, status)
            if status == 200:
                self.assertFalse(response.json()['enabled'])

    def test_targeted_reconciliation_and_claim_leave_unselected_jobs_untouched(self):
        with self.factory() as db, db.begin():
            enqueue(db, 1, now=self.now)
            reconcile(db, product_ids=[999, 999])
        received = []
        result = run_one(self.factory, lambda pid, row, gen: received.append((pid, row)),
                         product_ids=[999])
        self.assertTrue(result['completed'])
        self.assertEqual(received, [(999, None)])
        with self.factory() as db:
            self.assertEqual(db.get(Job, 1).status, 'pending')
            self.assertIsNone(claim_one(db, product_ids=[888]))
        with self.factory() as db, db.begin():
            with self.assertRaises(ValueError):
                reconcile(db, product_ids=[0])

    def test_old_event_and_replay_read_latest_business_state(self):
        self.queue()
        self.change(8)
        self.change(3)
        # A delayed notification carries an identity, never a stale payload.
        with self.factory() as db, db.begin():
            enqueue(db, 1, now=self.now)
        received = []
        result = run_one(self.factory, lambda pid, row, gen: received.append((row['Stock'], gen)))
        self.assertEqual(received, [(3, 4)])
        self.assertTrue(result['completed'])
        self.assertFalse(run_one(self.factory, lambda *args: self.fail('Duplicate claim'))['claimed'])

    def test_projection_busy_does_not_write_or_acknowledge_success(self):
        self.queue()
        deliver = unittest.mock.Mock()
        with patch('app.services.product_index_worker.projection_lock', side_effect=ProjectionBusy):
            result = run_one(self.factory, deliver, now=self.now)
        deliver.assert_not_called()
        self.assertFalse(result['completed'])
        self.assertEqual(result['error_type'], 'ProjectionBusy')
        self.assertIsNone(result['event_to_index_seconds'])
        with self.factory() as db:
            job = db.get(Job, 1)
            self.assertEqual(job.status, 'pending')
            self.assertEqual(job.delivered_generation, 0)

    def test_lease_reclaimed_before_snapshot_blocks_old_delivery(self):
        from contextlib import contextmanager
        self.queue()
        old_deliver = unittest.mock.Mock()
        @contextmanager
        def reclaim(*args):
            with self.factory() as db, db.begin():
                newer = claim_one(db, now=self.now + timedelta(seconds=121))
                acknowledge(db, newer, now=self.now + timedelta(seconds=121))
            yield
        with patch('app.services.product_index_worker.projection_lock', reclaim):
            result = run_one(self.factory, old_deliver, now=self.now)
        old_deliver.assert_not_called()
        self.assertEqual(result['error_type'], 'ClaimLost')
        self.assertFalse(result['acknowledged'])
        with self.factory() as db:
            self.assertEqual(db.get(Job, 1).status, 'pending')

    def test_coalesced_update_is_not_a_completed_sync_or_latency_sample(self):
        self.queue()
        result = run_one(self.factory, lambda *args: self.change(4), now=self.now)
        self.assertTrue(result['acknowledged'])
        self.assertFalse(result['completed'])
        self.assertIsNone(result['event_to_index_seconds'])
        final = run_one(self.factory, lambda *args: None, now=self.now + timedelta(seconds=5))
        self.assertTrue(final['completed'])
        self.assertEqual(final['event_to_index_seconds'], 5)

    def test_savepoint_rollback_does_not_lose_later_outbox_change(self):
        with patch.dict(os.environ, {'PRODUCT_INDEX_SYNC_ENABLED': 'true'}), self.factory() as db, db.begin():
            nested = db.begin_nested()
            db.get(Product, 1).stock = 2
            db.flush()
            nested.rollback()
            db.get(Product, 1).stock = 7
        received = []
        result = run_one(self.factory, lambda pid, row, gen: received.append(row['Stock']))
        self.assertTrue(result['completed'])
        self.assertEqual(received, [7])

    def test_advisory_lock_adapter_unlocks_on_error_and_invalidates_on_unlock_failure(self):
        from unittest.mock import MagicMock
        factory = MagicMock()
        engine = factory.return_value.__enter__.return_value.get_bind.return_value
        engine.dialect.name = 'postgresql'
        conn = engine.connect.return_value.__enter__.return_value
        conn.scalar.side_effect = [True, True]
        with self.assertRaises(TimeoutError):
            with projection_lock(factory, 1):
                raise TimeoutError('projection failed')
        self.assertEqual(conn.commit.call_count, 2)
        self.assertIn('pg_advisory_unlock', str(conn.scalar.call_args.args[0]))
        conn.scalar.side_effect = [True, False]
        with self.assertRaises(RuntimeError):
            with projection_lock(factory, 1):
                pass
        conn.invalidate.assert_called_once()

    def test_worker_cli_rejects_unbounded_identity_and_remote_target_before_clients(self):
        import importlib.util
        from pathlib import Path
        from contextlib import redirect_stderr
        from io import StringIO
        path = Path(__file__).resolve().parents[2] / 'scripts/run_index_worker.py'
        spec = importlib.util.spec_from_file_location('phase2_worker_cli', path)
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        for extra in [['--product-id', '0'], ['--max-jobs', '0'], []]:
            with patch('sys.argv', ['worker', '--environment', 'test', '--confirm-isolated', *extra]), \
                    patch.dict(os.environ, {'LUMIERE_SYNC_DATABASE_URL': 'postgresql+psycopg://fixture@remote/lumiere_test_fixture'}), \
                    redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
                worker.main()
            self.assertEqual(error.exception.code, 2)

    def test_all_mutable_projection_fields_emit_jobs_and_deliver_current_taxonomy(self):
        from decimal import Decimal
        with self.factory() as db, db.begin():
            for model in (Category, Brand, Material, Gemstone, Collection):
                db.add(model(id=2, name='Updated ' + model.__name__))
        fields = [('name', 'Changed name', 'ProductName'), ('sku', 'NEW-SKU', 'SKU'),
                  ('barcode', 'NEW-BARCODE', 'Barcode'), ('weight', Decimal('2.00'), 'Weight'),
                  ('sale_price', Decimal('123.00'), 'SalePrice'), ('stock', 0, 'Stock')]
        fields += [(prefix.lower() + '_id', 2, prefix + 'ID')
                   for prefix in ('Category', 'Brand', 'Material', 'Gemstone', 'Collection')]
        for generation, (field, value, key) in enumerate(fields, 1):
            with self.subTest(field=field):
                with patch.dict(os.environ, {'PRODUCT_INDEX_SYNC_ENABLED': 'true'}), self.factory() as db, db.begin():
                    setattr(db.get(Product, 1), field, value)
                received = []
                result = run_one(self.factory, lambda pid, row, gen: received.append((row[key], gen)))
                observed, actual_generation = received[0]
                self.assertEqual(Decimal(observed) if isinstance(value, Decimal) else observed, value)
                self.assertEqual(actual_generation, generation)
                self.assertTrue(result['completed'])
        with self.factory() as db:
            row = current_product(db, 1)
            for prefix in ('Category', 'Brand', 'Material', 'Gemstone', 'Collection'):
                self.assertEqual(row[prefix+'Name'], 'Updated '+prefix)


if __name__ == '__main__':
    unittest.main()
