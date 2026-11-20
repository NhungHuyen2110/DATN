"""Cart HTTP contract; persistence and business rules live behind CartService."""
from typing import Annotated, Callable
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from app.application.cart import CartService
from app.core.database import get_db
from app.domain.cart import CartError
from app.infrastructure.cart import SqlAlchemyCartRepository
from app.models import User
from app.core.dependencies import get_current_user
from app.schemas.cart import AddCartItem, CartResponse, UpdateCartItem

router = APIRouter(prefix="/cart", tags=["Cart"])
CurrentUser = Annotated[User, Depends(get_current_user)]
ItemID = Annotated[int, Path(ge=1, le=2147483647)]


def get_cart_service(db: Annotated[Session, Depends(get_db)]) -> CartService:
    return CartService(SqlAlchemyCartRepository(db))


Service = Annotated[CartService, Depends(get_cart_service)]


def present(operation: Callable, *args) -> dict:
    try:
        return operation(*args)
    except CartError as exc:
        status = {"unauthorized": 401, "missing": 404, "conflict": 409, "persistence": 500}[exc.code]
        raise HTTPException(status_code=status, detail=str(exc)) from None


@router.get("", response_model=CartResponse)
def get_cart(user: CurrentUser, service: Service):
    return present(service.get, user.id)


@router.post("/items", response_model=CartResponse)
def add_item(request: AddCartItem, user: CurrentUser, service: Service):
    return present(service.add, user.id, request.product_id, request.quantity)


@router.patch("/items/{id}", response_model=CartResponse)
def update_item(id: ItemID, request: UpdateCartItem, user: CurrentUser, service: Service):
    return present(service.update, user.id, id, request.quantity)


@router.delete("/items/{id}", response_model=CartResponse)
def delete_item(id: ItemID, user: CurrentUser, service: Service):
    return present(service.delete, user.id, id)
