"""Transactional enqueue plus leased delivery; external I/O never under DB locks."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

from sqlalchemy import and_, case, event, func, or_, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_index_job import ProductIndexJob as Job


def enabled():
    return os.getenv('PRODUCT_INDEX_SYNC_ENABLED', 'false').lower() == 'true'


def now_utc():
    return datetime.now(timezone.utc)


def enqueue(session, product_id, now=None):
    """Called inside the SAME transaction as the business change; never commits."""
    now = now or now_utc()
    dialect = session.get_bind().dialect.name
    if dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise ValueError('Unsupported outbox dialect')
    processing = Job.status == 'processing'
    statement = insert(Job).values(product_id=product_id, generation=1, delivered_generation=0,
                                   status='pending', attempts=0, next_attempt_at=now, dirty_since=now)
    statement = statement.on_conflict_do_update(index_elements=[Job.product_id], set_={
        'generation': Job.generation + 1, 'dirty_since': func.coalesce(Job.dirty_since, now),
        # Keep an active lease: another worker must not overtake its write.
        'status': case((processing, Job.status), else_='pending'),
        'attempts': case((processing, Job.attempts), else_=0),
        'next_attempt_at': case((processing, Job.next_attempt_at), else_=now),
        'last_error_type': case((processing, Job.last_error_type), else_=None),
    })
    session.execute(statement)
    return session.scalar(select(Job).where(Job.product_id == product_id).execution_options(populate_existing=True))


def before_flush(session, context, instances):
    if not enabled():
        return  # Critical: no query of the new table before migration/activation.
    ids = set()
    for item in [*session.new, *session.dirty, *session.deleted]:
        if isinstance(item, Product) and item.id is not None:
            if item in session.new or item in session.deleted or session.is_modified(item, include_collections=False):
                ids.add(item.id)
    # Taxonomy renames also change embeddings and graph display names.
    from app.models import Brand, Category, Collection, Gemstone, Material
    columns = {Brand: Product.brand_id, Category: Product.category_id, Collection: Product.collection_id,
               Gemstone: Product.gemstone_id, Material: Product.material_id}
    for item in session.dirty:
        if type(item) in columns and session.is_modified(item, include_collections=False):
            ids.update(session.scalars(select(Product.id).where(columns[type(item)] == item.id)).all())
    seen = session.info.setdefault('product_index_enqueued', set())
    for pid in sorted(ids - seen):
        enqueue(session, pid)
        seen.add(pid)


def transaction_end(session, transaction):
    if transaction.parent is None:
        session.info.pop('product_index_enqueued', None)


def rollback_markers(session, transaction):
    session.info.pop('product_index_enqueued', None)


event.listen(Session, 'before_flush', before_flush)
event.listen(Session, 'after_transaction_end', transaction_end)
event.listen(Session, 'after_soft_rollback', rollback_markers)


@dataclass(frozen=True)
class Claim:
    product_id: int
    generation: int
    token: str
    dirty_since: datetime | None = None


def claim_one(session, now=None, lease_seconds=120, max_attempts=5, product_ids=None):
    if lease_seconds < 30 or max_attempts < 1:
        raise ValueError('Lease >=30 seconds and positive retry budget required')
    now = now or now_utc()
    while True:
        query = select(Job).where(or_(
            and_(Job.status == 'pending', Job.next_attempt_at <= now),
            and_(Job.status == 'processing', Job.lease_until <= now),
        ))
        if product_ids is not None:
            query = query.where(Job.product_id.in_(product_ids))
        job = session.scalar(query.order_by(Job.next_attempt_at, Job.product_id)
                             .with_for_update(skip_locked=True).limit(1))
        if job is None:
            return None
        if job.attempts < max_attempts:
            break
        job.status, job.lease_token, job.lease_until = 'dead', None, None
        job.last_error_type = 'LeaseRetryBudgetExhausted'
        # SessionLocal disables autoflush: flush before selecting the next row.
        # An exhausted lease must not make a non-watch worker stop draining jobs.
        session.flush()
    job.status, job.lease_token = 'processing', uuid4().hex
    job.lease_until = now + timedelta(seconds=lease_seconds)
    job.attempts += 1
    return Claim(job.product_id, job.generation, job.lease_token, job.dirty_since)


def acknowledge(session, claim, error=None, now=None, max_attempts=5):
    now = now or now_utc()
    job = session.scalar(select(Job).where(Job.product_id == claim.product_id).with_for_update())
    if job is None or job.status != 'processing' or job.lease_token != claim.token:
        return False  # An expired worker cannot acknowledge somebody else's lease.
    job.lease_token, job.lease_until = None, None
    if job.generation != claim.generation:
        job.status, job.attempts, job.next_attempt_at = 'pending', 0, now
        job.last_error_type = None
    elif error is None:
        job.status, job.completed_at = 'done', now
        job.delivered_generation, job.dirty_since, job.last_error_type = claim.generation, None, None
    else:
        job.last_error_type = type(error).__name__[:100]  # Never store raw query/credential/PII errors.
        job.status = 'dead' if job.attempts >= max_attempts else 'pending'
        job.next_attempt_at = now + timedelta(seconds=min(3600, 2 ** min(job.attempts, 10)))
    return True


def sync_status(session, now=None, product_ids=None):
    if not enabled():
        return {'enabled': False, 'states': {}, 'last_success': None, 'oldest_pending_seconds': None}
    now = now or now_utc()
    scope = [] if product_ids is None else [Job.product_id.in_(product_ids)]
    counts = dict(session.execute(select(Job.status, func.count()).where(*scope).group_by(Job.status)).all())
    last = session.scalar(select(func.max(Job.completed_at)).where(*scope))
    oldest = session.scalar(select(func.min(Job.dirty_since)).where(*scope, Job.delivered_generation < Job.generation))
    if oldest is not None and oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    return {'enabled': True, 'states': counts, 'last_success': last.isoformat() if last else None,
            'oldest_pending_seconds': max(0, (now - oldest).total_seconds()) if oldest else None}
