"""Shared authentication and role dependencies, independent of business routers."""

from datetime import datetime, timezone
import hashlib
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User, UserSession


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_user(
    lumiere_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not lumiere_session:
        raise HTTPException(status_code=401, detail="Bạn chưa đăng nhập")
    token_hash = hash_session_token(lumiere_session)
    session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
    now = datetime.now(timezone.utc)
    if session is None or session.expires_at <= now:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Tài khoản không khả dụng")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def customer(user: CurrentUser):
    if user.role.name != "customer":
        raise HTTPException(status_code=403, detail="Chỉ khách hàng được đặt hàng và xem danh sách cá nhân")
    return user


def admin(user: CurrentUser):
    if user.role.name != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin được quản lý đơn hàng")
    return user


def staff_or_admin(user: CurrentUser):
    if user.role.name not in {"staff", "admin"}:
        raise HTTPException(status_code=403, detail="Chỉ Staff hoặc Admin được xử lý đơn hàng")
    return user
