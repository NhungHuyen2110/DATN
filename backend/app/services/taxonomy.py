"""Taxonomy business rules and ORM persistence; no route registration."""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from app.models import Brand, Category, Product


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
