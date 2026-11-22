"""Admin-confirmed product facts; no automatic classification from names/images."""
from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import Product, User
from app.models.product_attribute_review import ProductAttributeReview as Review
from app.routers.orders import admin
from app.schemas.product_attributes import AttributeReviewRequest, AttributeReviewResponse
from app.services.orders import lock_user, transaction
from app.services.product_index_jobs import enabled, enqueue
from shared.verified_attributes import ATTRIBUTE_NAMES

router=APIRouter(tags=['Verified product attributes'])
Database=Annotated[Session,Depends(get_db)]
ActiveAdmin=Annotated[User,Depends(admin)]
ProductID=Annotated[int,Path(ge=1,le=2147483647)]


@router.get('/admin/product-attributes/options')
def options(user:ActiveAdmin):
    return ATTRIBUTE_NAMES


@router.get('/admin/products/{product_id}/verified-attributes',response_model=list[AttributeReviewResponse])
def list_reviews(product_id:ProductID,user:ActiveAdmin,db:Database):
    if db.get(Product,product_id) is None:
        raise HTTPException(404,'Sản phẩm không tồn tại')
    return db.scalars(select(Review).where(Review.product_id==product_id).order_by(Review.id)).all()


@router.post('/admin/products/{product_id}/verified-attributes',response_model=AttributeReviewResponse)
def confirm_review(product_id:ProductID,request:AttributeReviewRequest,user:ActiveAdmin,db:Database):
    with transaction(db):
        lock_user(db,user.id,'admin')
        product=db.scalar(select(Product).where(Product.id==product_id).with_for_update())
        if product is None:
            raise HTTPException(404,'Sản phẩm không tồn tại')
        review=db.scalar(select(Review).where(Review.product_id==product_id,Review.label==request.label,
                                              Review.canonical_id==request.canonical_id).with_for_update())
        if review is not None and review.active:
            raise HTTPException(409,'Thuộc tính đã được xác minh; hãy thu hồi trước khi đánh giá lại')
        now=datetime.now(timezone.utc)
        if review is None:
            review=Review(product_id=product_id,label=request.label,canonical_id=request.canonical_id,
                          version=1,review_log=[])
            db.add(review)
        else:
            review.version+=1
        review.active=True
        review.source_reference=request.source_reference
        review.reviewed_by=user.id
        review.reviewed_at=now
        review.review_log=[*review.review_log,{'action':'confirm','actor_id':user.id,
            'source_reference':request.source_reference,'at':now.isoformat(),'version':review.version}]
        db.flush()
        if enabled():
            enqueue(db,product_id)
    return review


@router.delete('/admin/products/{product_id}/verified-attributes/{review_id}',status_code=204)
def revoke_review(product_id:ProductID,review_id:Annotated[int,Path(ge=1)],user:ActiveAdmin,db:Database,
                  expected_version:Annotated[int,Query(ge=1)]):
    with transaction(db):
        lock_user(db,user.id,'admin')
        db.scalar(select(Product).where(Product.id==product_id).with_for_update())
        review=db.scalar(select(Review).where(Review.id==review_id,Review.product_id==product_id).with_for_update())
        if review is None:
            raise HTTPException(404,'Đánh giá không tồn tại')
        if review.version!=expected_version:
            raise HTTPException(409,'Đánh giá đã thay đổi; vui lòng tải lại')
        if review.active:
            review.active=False
            review.version+=1
            review.review_log=[*review.review_log,{'action':'revoke','actor_id':user.id,
                'at':datetime.now(timezone.utc).isoformat(),'version':review.version}]
            db.flush()
            if enabled():
                enqueue(db,product_id)
    return Response(status_code=204)
