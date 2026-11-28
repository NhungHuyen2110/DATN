"""One job at a time; per-product advisory locks serialize cooperating PG workers."""
from contextlib import contextmanager
from datetime import timezone
from sqlalchemy import select, text
from sqlalchemy.orm import joinedload

from app.models import Product, ProductIndexJob as Job
from app.services.product_index_jobs import acknowledge, claim_one, enqueue, now_utc


class ProjectionBusy(RuntimeError):
    pass


class ClaimLost(RuntimeError):
    pass


@contextmanager
def projection_lock(session_factory, product_id):
    """Session advisory lock survives commit, releases on process/connection exit.

    No business transaction/row lock spans external I/O. SQLite is used only by
    single-worker isolated tests; its adapter is not a distributed lock.
    """
    with session_factory() as db:
        engine = db.get_bind()
    if engine.dialect.name != 'postgresql':
        yield
        return
    with engine.connect() as conn:
        locked = conn.scalar(text('SELECT pg_try_advisory_lock(1279870537, :id)'), {'id': product_id})
        conn.commit()
        if not locked:
            raise ProjectionBusy('Another writer holds this product')
        try:
            yield
        finally:
            # A broken connection must never return a session lock to the pool.
            try:
                if not conn.scalar(text('SELECT pg_advisory_unlock(1279870537, :id)'), {'id': product_id}):
                    raise ClaimLost('Projection lock ownership lost')
                conn.commit()
            except BaseException:
                conn.invalidate()
                raise


def current_product(session, product_id):
    product = session.scalar(select(Product).where(Product.id == product_id).options(
        joinedload(Product.category), joinedload(Product.brand), joinedload(Product.material),
        joinedload(Product.gemstone), joinedload(Product.collection)))
    if product is None:
        return None
    snapshot = {
        'ProductID': product.id, 'SKU': product.sku, 'Barcode': product.barcode,
        'ProductName': product.name, 'Weight': str(product.weight), 'SalePrice': str(product.sale_price),
        'Stock': product.stock, 'source_row': product.id,
        **{prefix + 'ID': getattr(product, prefix.lower() + '_id')
           for prefix in ('Category', 'Brand', 'Material', 'Gemstone', 'Collection')},
        **{prefix + 'Name': getattr(product, prefix.lower()).name
           for prefix in ('Category', 'Brand', 'Material', 'Gemstone', 'Collection')},
    }
    from app.services.product_attributes import reviews_enabled, projected_reviews
    if reviews_enabled():
        snapshot['verified_attributes'] = projected_reviews(session, product_id)
    return snapshot


def run_one(session_factory, deliver, now=None, lease_seconds=120, max_attempts=5, product_ids=None):
    with session_factory() as db, db.begin():
        claim = claim_one(db, now=now, lease_seconds=lease_seconds, max_attempts=max_attempts,
                          product_ids=product_ids)
    if claim is None:
        return {'claimed': False}
    error = None
    try:
        with projection_lock(session_factory, claim.product_id):
            with session_factory() as db:
                job = db.get(Job, claim.product_id)
                clock = now or now_utc()
                until = job.lease_until if job else None
                if until is not None and until.tzinfo is None:
                    until = until.replace(tzinfo=timezone.utc)
                if (job is None or job.status != 'processing' or job.lease_token != claim.token
                        or until is None or until <= clock):
                    raise ClaimLost('Reclaimed/expired lease before delivery')
                snapshot = current_product(db, claim.product_id)
            # Keep only the advisory connection; no transaction/row lock.
            deliver(claim.product_id, snapshot, claim.generation)
    except Exception as exc:
        error = exc
    with session_factory() as db, db.begin():
        accepted = acknowledge(db, claim, error=error, now=now, max_attempts=max_attempts)
        job = db.get(Job, claim.product_id)
        completed = accepted and error is None and job is not None and job.status == 'done'
        if not accepted:
            # A lease-lost delivery may have touched an index. Queue a fresh read
            # to converge again instead of silently accepting a stale projection.
            enqueue(db, claim.product_id, now=now)
    since = claim.dirty_since
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    lag = max(0, ((now or now_utc()) - since).total_seconds()) if completed and since else None
    return {'claimed': True, 'product_id': claim.product_id, 'generation': claim.generation,
            'delivered': error is None, 'acknowledged': accepted,
            'completed': completed, 'event_to_index_seconds': lag,
            'error_type': type(error).__name__ if error else None}


def reconcile(session, projected_ids=(), *, product_ids=None):
    """Explicit full reconciliation; catches bulk SQL changes bypassing ORM hooks."""
    ids = (set(session.scalars(select(Product.id)).all()) | set(projected_ids)
           if product_ids is None else set(product_ids))
    if any(not isinstance(pid, int) or isinstance(pid, bool) or not 1 <= pid <= 2147483647 for pid in ids):
        raise ValueError('Positive product IDs required')
    for product_id in sorted(ids):
        enqueue(session, product_id)
    return len(ids)
