"""Public catalog reads and authenticated Staff/Admin stock adjustments."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.core.dependencies import admin, staff_or_admin
from app.schemas.catalog import (
    LookupResponse, ProductPage, ProductResponse, StockUpdateRequest, StockResponse,
    ProductUpdateRequest, ProductCreateRequest,
)
from app.services import catalog as service
from app.services.catalog import public_product_query  # Compatibility export


router = APIRouter(tags=["Catalog"])
Database = Annotated[Session, Depends(get_db)]
FilterID = Annotated[int | None, Query(ge=1, le=2147483647)]
Price = Annotated[
    Decimal | None,
    Query(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False),
]


@router.get("/categories", response_model=list[LookupResponse])
def list_categories(db: Database):
    return service.list_categories(db)


@router.get("/brands", response_model=list[LookupResponse])
def list_brands(db: Database):
    return service.list_brands(db)


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
    return service.list_products(
        db, q=q, category_id=category_id, brand_id=brand_id,
        material_id=material_id, gemstone_id=gemstone_id, collection_id=collection_id,
        min_price=min_price, max_price=max_price, page=page, page_size=page_size,
    )


@router.get("/products/{id}", response_model=ProductResponse)
def get_product(id: Annotated[int, Path(ge=1, le=2147483647)], db: Database):
    return service.get_product(id, db)


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
    return service.create_product(request, user, db)


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
    return service.update_product(id, request, user, db)


@router.patch("/staff/products/{id}/stock", response_model=StockResponse, tags=["Staff Inventory"])
def update_stock(
    id: Annotated[int, Path(ge=1, le=2147483647)],
    request: StockUpdateRequest,
    user: Annotated[User, Depends(staff_or_admin)],
    db: Database,
):
    return service.update_stock(id, request, user, db)
