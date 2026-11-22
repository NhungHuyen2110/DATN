"""Read only active human approvals; public DTOs never contain reviewer/source text."""
from sqlalchemy import select
from app.models.product_attribute_review import ProductAttributeReview
from app.schemas.product_attributes import PublicVerifiedAttribute
from app.schemas.catalog import ProductResponse
from shared.verified_attributes import reviews_enabled


def active_reviews(db, product_ids):
    if not reviews_enabled() or not product_ids:
        return {}
    rows = db.scalars(select(ProductAttributeReview).where(
        ProductAttributeReview.product_id.in_(product_ids), ProductAttributeReview.active.is_(True))
        .order_by(ProductAttributeReview.product_id, ProductAttributeReview.label,
                  ProductAttributeReview.canonical_id)).all()
    result = {}
    for row in rows:
        result.setdefault(row.product_id, []).append(row)
    return result


def public_products(db, products):
    reviews = active_reviews(db, [product.id for product in products])
    return [ProductResponse.model_validate(product).model_copy(update={
        'verified_attributes': [PublicVerifiedAttribute.model_validate(review)
                                for review in reviews.get(product.id, [])]}) for product in products]


def projected_reviews(db, product_id):
    return [{**PublicVerifiedAttribute.model_validate(row).model_dump(),
             'review_id': row.id, 'review_version': row.version,
             'reviewed_at': row.reviewed_at.isoformat()}
            for row in active_reviews(db, [product_id]).get(product_id, [])]
