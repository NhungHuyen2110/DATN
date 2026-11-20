"""Customer inquiries and admin inbox backed by the existing ORM."""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from app.models import ContactMessage


def submit(request, db):
    contact = ContactMessage(**request.model_dump(), status="new")
    try:
        db.add(contact)
        db.commit()
        db.refresh(contact)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Chưa thể lưu liên hệ, vui lòng thử lại") from None
    return {"id": contact.id, "status": contact.status, "message": "Đã tiếp nhận yêu cầu liên hệ"}


def inbox(db, page=1, page_size=20):
    total = db.scalar(select(func.count(ContactMessage.id))) or 0
    items = db.scalars(select(ContactMessage).order_by(ContactMessage.id.desc())
                       .offset((page - 1)*page_size).limit(page_size)).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [{"id": r.id, "full_name": r.full_name, "email": r.email,
                       "topic": r.topic, "message": r.message, "status": r.status,
                       "created_at": r.created_at} for r in items]}


def change_status(id, request, db):
    try:
        contact = db.scalar(select(ContactMessage).where(ContactMessage.id == id).with_for_update())
        if contact is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu")
        contact.status = request.status
        db.commit()
        return {"id": contact.id, "status": contact.status}
    except Exception:
        db.rollback()
        raise
