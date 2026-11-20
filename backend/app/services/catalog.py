"""Catalog queries, product validation and stock transactions using existing ORM models."""
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, load_only
from app.models import Brand, Category, Collection, Gemstone, Material, Product
from app.schemas.catalog import ProductResponse, StockResponse
from app.services import orders as order_service


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


def list_categories(db):
    return db.scalars(select(Category).order_by(Category.id)).all()


def list_brands(db):
    return db.scalars(select(Brand).order_by(Brand.id)).all()


def list_products(db, q=None, category_id=None, brand_id=None, material_id=None, gemstone_id=None, collection_id=None, min_price=None, max_price=None, page=1, page_size=20):
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
    return {"items": items, "page": page, "page_size": page_size, "total": total}


def get_product(id, db):
    product = db.scalar(public_product_query().where(Product.id == id))
    if product is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    return product


def create_product(request, user, db):
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


def update_product(id, request, user, db):
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


def update_stock(id, request, user, db):
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
