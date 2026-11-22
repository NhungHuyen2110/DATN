"""One job at a time; claim/ack transactions are separate from external writes."""
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models import Product
from app.services.product_index_jobs import acknowledge, claim_one, enqueue


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


def run_one(session_factory, deliver, now=None, lease_seconds=120, max_attempts=5):
    with session_factory() as db, db.begin():
        claim = claim_one(db, now=now, lease_seconds=lease_seconds, max_attempts=max_attempts)
    if claim is None:
        return {'claimed': False}
    error = None
    try:
        with session_factory() as db:
            snapshot = current_product(db, claim.product_id)
        # No database session/transaction/row lock is held here.
        deliver(claim.product_id, snapshot, claim.generation)
    except Exception as exc:
        error = exc
    with session_factory() as db, db.begin():
        accepted = acknowledge(db, claim, error=error, now=now, max_attempts=max_attempts)
        if not accepted:
            # A lease-lost delivery may have touched an index. Queue a fresh read
            # to converge again instead of silently accepting a stale projection.
            enqueue(db, claim.product_id, now=now)
    return {'claimed': True, 'product_id': claim.product_id, 'generation': claim.generation,
            'delivered': error is None, 'acknowledged': accepted,
            'error_type': type(error).__name__ if error else None}


def reconcile(session, projected_ids=()):
    """Explicit full reconciliation; catches bulk SQL changes bypassing ORM hooks."""
    ids = set(session.scalars(select(Product.id)).all()) | set(projected_ids)
    for product_id in sorted(ids):
        enqueue(session, product_id)
    return len(ids)
