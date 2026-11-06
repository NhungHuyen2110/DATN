"""Persist contact inquiries without claiming to send emails."""

from typing import Annotated
import re

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ContactMessage, User
from app.routers.orders import admin

router = APIRouter(tags=["Contact"])
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(admin)]


class ContactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=5, max_length=254)
    topic: str = Field(min_length=2, max_length=100)
    message: str = Field(min_length=10, max_length=1500)

    @field_validator("full_name", "topic", "message")
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if "\x00" in value:
            raise ValueError("Ký tự không hợp lệ")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]{1,64}@[^\s@]{1,189}\.[A-Za-z]{2,63}", value):
            raise ValueError("Email không hợp lệ")
        return value


class ContactStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(new|in_progress|closed)$")


@router.post("/contact", status_code=201)
def submit(request: ContactCreate, db: DB):
    contact = ContactMessage(**request.model_dump(), status="new")
    try:
        db.add(contact)
        db.commit()
        db.refresh(contact)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Chưa thể lưu liên hệ, vui lòng thử lại") from None
    return {"id": contact.id, "status": contact.status, "message": "Đã tiếp nhận yêu cầu liên hệ"}


@router.get("/admin/contact-messages")
def inbox(actor: Actor, db: DB,
          page: Annotated[int, Query(ge=1, le=2147483647)] = 1,
          page_size: Annotated[int, Query(ge=1, le=100)] = 20):
    total = db.scalar(select(func.count(ContactMessage.id))) or 0
    items = db.scalars(select(ContactMessage).order_by(ContactMessage.id.desc())
                       .offset((page - 1)*page_size).limit(page_size)).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [{"id": r.id, "full_name": r.full_name, "email": r.email,
                       "topic": r.topic, "message": r.message, "status": r.status,
                       "created_at": r.created_at} for r in items]}


@router.patch("/admin/contact-messages/{id}")
def change_status(id: Annotated[int, Path(ge=1)], request: ContactStatus, actor: Actor, db: DB):
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
