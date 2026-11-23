"""Public catalog reads and authenticated Staff/Admin stock adjustments."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, load_only

from app.core.database import get_db
from app.models import Brand, Category, Collection, Gemstone, Material, Product, User
from app.routers.orders import admin, staff_or_admin
from app.schemas.catalog import (
    LookupResponse, ProductPage, ProductResponse, StockUpdateRequest, StockResponse,
    ProductUpdateRequest, ProductCreateRequest, ProductImageResponse,
)
from app.services import orders as order_service
from app.services.product_attributes import public_products


router = APIRouter(tags=["Catalog"])
Database = Annotated[Session, Depends(get_db)]
FilterID = Annotated[int | None, Query(ge=1, le=2147483647)]
Price = Annotated[
    Decimal | None,
    Query(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False),
]


@router.get('/products/{id}/image', response_class=FileResponse,
            responses={200: {'content': {'image/webp': {}}}})
def product_image(id: Annotated[int, Path(ge=1, le=2147483647)], db: Database):
    from app.services.product_images import cover_path
    if db.get(Product, id) is None or not cover_path(id).is_file():
        raise HTTPException(404, 'Sản phẩm chưa có ảnh tải lên.')
    return FileResponse(cover_path(id), media_type='image/webp', headers={'Cache-Control': 'no-cache'})


@router.post('/admin/products/{id}/image', tags=['Admin Products'], response_model=ProductImageResponse,
    openapi_extra={'requestBody': {'required': True, 'content': {
        mime: {'schema': {'type': 'string', 'format': 'binary'}}
        for mime in ('image/jpeg', 'image/png', 'image/webp')}}})
async def upload_product_image(id: Annotated[int, Path(ge=1, le=2147483647)],
        request: Request, user: Annotated[User, Depends(admin)], db: Database):
    from app.services.product_images import MAX_IMAGE_BYTES, save_cover
    if db.get(Product, id) is None:
        raise HTTPException(404, 'Không tìm thấy sản phẩm.')
    if request.headers.get('content-type', '').split(';')[0].lower() not in {
            'image/jpeg', 'image/png', 'image/webp'}:
        raise HTTPException(415, 'Chỉ nhận ảnh JPEG, PNG hoặc WebP.')
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_IMAGE_BYTES:
            raise HTTPException(413, 'Ảnh không được vượt quá 5 MB.')
        data.extend(chunk)
    try:
        return await run_in_threadpool(save_cover, id, bytes(data))
    except OSError:
        raise HTTPException(503, 'Chưa lưu được ảnh. Sản phẩm vẫn được giữ; vui lòng thử tải ảnh lại.') from None


def public_product_query():
    return select(Product).options(
        load_only(
            Product.id, Product.sku, Product.barcode, Product.name,
            Product.category_id, Product.brand_id, Product.material_id,
            Product.gemstone_id, Product.collection_id,
            Product.weight, Product.sale_price, Product.stock,
        ),
        joinedload(Product.category), joinedload(Product.brand),
        joinedload(Product.material), joinedload(Product.gemstone),
        joinedload(Product.collection),
    )


@router.get("/categories", response_model=list[LookupResponse])
def list_categories(db: Database):
    return db.scalars(select(Category).order_by(Category.id)).all()


@router.get("/brands", response_model=list[LookupResponse])
def list_brands(db: Database):
    return db.scalars(select(Brand).order_by(Brand.id)).all()


@router.get("/products", response_model=ProductPage)
def list_products(
    db: Database,
    q: Annotated[str | None, Query(max_length=255)] = None,
    category_id: FilterID = None,
    brand_id: FilterID = None,
    material_id: FilterID = None,
    gemstone_id: FilterID = None,
    collection_id: FilterID = None,
    min_price: Price = None,
    max_price: Price = None,
    page: Annotated[int, Query(ge=1, le=2147483647)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=422, detail="min_price không được lớn hơn max_price")

    filters = []
    if q is not None and q.strip():
        # Search literal text; % and _ supplied by clients are not SQL wildcards.
        term = q.strip()
        filters.append(or_(
            Product.name.icontains(term, autoescape=True),
            Product.sku.icontains(term, autoescape=True),
        ))
    for column, value in (
        (Product.category_id, category_id), (Product.brand_id, brand_id),
        (Product.material_id, material_id), (Product.gemstone_id, gemstone_id),
        (Product.collection_id, collection_id),
    ):
        if value is not None:
            filters.append(column == value)
    if min_price is not None:
        filters.append(Product.sale_price >= min_price)
    if max_price is not None:
        filters.append(Product.sale_price <= max_price)

    total = db.scalar(select(func.count()).select_from(Product).where(*filters))
    items = db.scalars(
        public_product_query().where(*filters).order_by(Product.id)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": public_products(db, items), "page": page, "page_size": page_size, "total": total}


@router.get("/products/{id}", response_model=ProductResponse)
def get_product(id: Annotated[int, Path(ge=1, le=2147483647)], db: Database):
    product = db.scalar(public_product_query().where(Product.id == id))
    if product is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    return public_products(db, [product])[0]


@router.get("/admin/products", response_model=ProductPage, tags=["Admin Products"])
def admin_products(
    user: Annotated[User, Depends(admin)],
    db: Database,
    q: Annotated[str | None, Query(max_length=255)] = None,
    page: Annotated[int, Query(ge=1, le=2147483647)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return list_products(db, q=q, page=page, page_size=page_size)


@router.post(
    "/admin/products",
    response_model=ProductResponse,
    status_code=201,
    tags=["Admin Products"],
)
def create_product(
    request: ProductCreateRequest,
    user: Annotated[User, Depends(admin)],
    db: Database,
):
    try:
        with order_service.transaction(db):
            order_service.lock_user(db, user.id, "admin")
            if db.get(Product, request.id) is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Product ID already exists"
                )
            if db.scalar(
                select(Product.id).where(Product.sku == request.sku)
            ) is not None:
                raise HTTPException(
                    status_code=409,
                    detail="SKU already exists"
                )
            if db.scalar(
                select(Product.id).where(Product.barcode == request.barcode)
            ) is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Barcode already exists"
                )
            for field, model in (
                ("category_id", Category),
                ("brand_id", Brand),
                ("material_id", Material),
                ("gemstone_id", Gemstone),
                ("collection_id", Collection),
            ):
                if db.get(model, getattr(request, field)) is None:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Unknown {field}"
                    )
            product = Product(**request.model_dump())
            db.add(product)
            db.flush()
            product = db.scalar(
                public_product_query().where(
                    Product.id == request.id
                )
            )
            result = ProductResponse.model_validate(product)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Product ID, SKU or barcode already exists, or related data changed"
        ) from None
    return result
@router.get(
    "/admin/products/{id}",
    response_model=ProductResponse,
    tags=["Admin Products"],
)
def admin_product(
    id: Annotated[int, Path(ge=1, le=2147483647)],
    user: Annotated[User, Depends(admin)], db: Database,
):
    return get_product(id, db)


@router.patch("/admin/products/{id}", response_model=ProductResponse, tags=["Admin Products"])
def update_product(
    id: Annotated[int, Path(ge=1, le=2147483647)],
    request: ProductUpdateRequest,
    user: Annotated[User, Depends(admin)], db: Database,
):
    try:
        with order_service.transaction(db):
            order_service.lock_user(db, user.id, "admin")
            # Lock only products, never the outer-joined lookup rows.
            product = db.scalar(select(Product).where(Product.id == id)
                .with_for_update().execution_options(populate_existing=True))
            if product is None:
                raise HTTPException(status_code=404, detail="Product not found")
            changes = request.model_dump(exclude_unset=True, exclude={"expected_sale_price"})
            if "sale_price" in changes and product.sale_price != request.expected_sale_price:
                raise HTTPException(status_code=409, detail="Price changed; reload the product")
            for field, model in (
                ("category_id", Category), ("brand_id", Brand), ("material_id", Material),
                ("gemstone_id", Gemstone), ("collection_id", Collection),
            ):
                if field in changes and db.get(model, changes[field]) is None:
                    raise HTTPException(status_code=422, detail=f"Unknown {field}")
            for field, value in changes.items():
                setattr(product, field, value)
            db.flush()
            # Refresh relationships after changing their foreign keys.
            product = db.scalar(public_product_query().where(Product.id == id)
                .execution_options(populate_existing=True))
            result = ProductResponse.model_validate(product)
    except HTTPException as exc:
        if exc.status_code in {409, 500} and exc.detail not in {"Price changed; reload the product"}:
            raise HTTPException(status_code=exc.status_code, detail="Unable to update product") from None
        raise
    return result


@router.patch("/staff/products/{id}/stock", response_model=StockResponse, tags=["Staff Inventory"])
def update_stock(
    id: Annotated[int, Path(ge=1, le=2147483647)],
    request: StockUpdateRequest,
    user: Annotated[User, Depends(staff_or_admin)],
    db: Database,
):
    try:
        # Share Orders' transaction and lock order without changing its stock logic.
        with order_service.transaction(db):
            order_service.lock_user(db, user.id, {"staff", "admin"})
            product = db.scalar(select(Product).where(Product.id == id).options(
                load_only(Product.id, Product.sku, Product.stock)
            ).with_for_update().execution_options(populate_existing=True))
            if product is None:
                raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
            if product.stock != request.expected_stock:
                raise HTTPException(status_code=409, detail="Tồn kho đã thay đổi; hãy tải lại dữ liệu")
            product.stock = request.stock
            db.flush()
            result = StockResponse.model_validate(product).model_dump()
    except HTTPException as exc:
        if exc.status_code == 500:
            raise HTTPException(status_code=500, detail="Không thể cập nhật tồn kho") from None
        raise
    return result
