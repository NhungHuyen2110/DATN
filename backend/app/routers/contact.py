"""Persist contact inquiries without claiming to send emails."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.core.dependencies import admin
from app.schemas.contact import ContactCreate, ContactStatus
from app.services import contact as service

router = APIRouter(tags=["Contact"])
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(admin)]


@router.post("/contact", status_code=201)
def submit(request: ContactCreate, db: DB):
    return service.submit(request, db)


@router.get("/admin/contact-messages")
def inbox(actor: Actor, db: DB,
          page: Annotated[int, Query(ge=1, le=2147483647)] = 1,
          page_size: Annotated[int, Query(ge=1, le=100)] = 20):
    return service.inbox(db, page, page_size)


@router.patch("/admin/contact-messages/{id}")
def change_status(id: Annotated[int, Path(ge=1)], request: ContactStatus, actor: Actor, db: DB):
    return service.change_status(id, request, db)
