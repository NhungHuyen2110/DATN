"""Admin-only CRUD for categories and brands; product-referenced rows cannot be deleted."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Brand, Category, Product, User
from app.routers.orders import admin

router = APIRouter(prefix="/admin", tags=["Admin Taxonomy"])
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(admin)]
LookupID = Annotated[int, Path(ge=1, le=2147483647)]


class LookupWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=150)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        name = " ".join(value.split())
        if not name or "\x00" in name:
            raise ValueError("Tên không hợp lệ")
        return name


def model_for(kind):
    return Category if kind == "categories" else Brand


def product_count(db, kind, ident):
    column = Product.category_id if kind == "categories" else Product.brand_id
    return db.scalar(select(func.count(Product.id)).where(column == ident)) or 0


def rows(db, kind):
    model = model_for(kind)
    all_rows = db.scalars(select(model).order_by(model.id)).all()
    return [
        {"id": row.id, "name": row.name, "product_count": product_count(db, kind, row.id)}
        for row in all_rows
    ]


def add(db, kind, request):
    model = model_for(kind)
    try:
        new_id = (db.scalar(select(func.max(model.id))) or 0) + 1
        if new_id > 2147483647:
            raise HTTPException(status_code=409, detail="Đã đạt giới hạn mã")
        entry = model(id=new_id, name=request.name)
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return {"id": entry.id, "name": entry.name, "product_count": 0}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tên hoặc mã đã tồn tại; vui lòng tải lại") from None
    except Exception:
        db.rollback()
        raise


def change(db, kind, ident, request):
    model = model_for(kind)
    try:
        entry = db.scalar(select(model).where(model.id == ident).with_for_update())
        if entry is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu")
        entry.name = request.name
        db.commit()
        db.refresh(entry)
        return {"id": entry.id, "name": entry.name, "product_count": product_count(db, kind, ident)}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tên đã tồn tại") from None
    except Exception:
        db.rollback()
        raise


def remove(db, kind, ident):
    model = model_for(kind)
    try:
        entry = db.scalar(select(model).where(model.id == ident).with_for_update())
        if entry is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu")
        if product_count(db, kind, ident):
            raise HTTPException(status_code=409, detail="Đang được sản phẩm sử dụng; không thể xóa")
        db.delete(entry)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Đang có dữ liệu liên quan") from None
    except Exception:
        db.rollback()
        raise


@router.get("/categories")
def categories(actor: Actor, db: DB):
    return {"items": rows(db, "categories")}


@router.post("/categories", status_code=201)
def create_category(request: LookupWrite, actor: Actor, db: DB):
    return add(db, "categories", request)


@router.patch("/categories/{id}")
def edit_category(id: LookupID, request: LookupWrite, actor: Actor, db: DB):
    return change(db, "categories", id, request)


@router.delete("/categories/{id}", status_code=204)
def delete_category(id: LookupID, actor: Actor, db: DB):
    remove(db, "categories", id)


@router.get("/brands")
def brands(actor: Actor, db: DB):
    return {"items": rows(db, "brands")}


@router.post("/brands", status_code=201)
def create_brand(request: LookupWrite, actor: Actor, db: DB):
    return add(db, "brands", request)


@router.patch("/brands/{id}")
def edit_brand(id: LookupID, request: LookupWrite, actor: Actor, db: DB):
    return change(db, "brands", id, request)


@router.delete("/brands/{id}", status_code=204)
def delete_brand(id: LookupID, actor: Actor, db: DB):
    remove(db, "brands", id)
