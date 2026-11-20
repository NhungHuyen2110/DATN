"""Admin-only CRUD for categories and brands; product-referenced rows cannot be deleted."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.core.dependencies import admin
from app.schemas.taxonomy import LookupWrite
from app.services.taxonomy import add, change, remove, rows  # Compatibility exports

router = APIRouter(prefix="/admin", tags=["Admin Taxonomy"])
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(admin)]
LookupID = Annotated[int, Path(ge=1, le=2147483647)]


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
