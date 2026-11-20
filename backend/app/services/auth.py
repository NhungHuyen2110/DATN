"""Account and session business operations using existing SQLAlchemy models."""
from datetime import datetime, timedelta, timezone
import secrets
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.core.dependencies import hash_session_token
from app.core.security import hash_password, verify_password, SESSION_DAYS
from app.models import Role, User, UserSession


def register(request, db):
    email = str(request.email).strip().lower()

    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email đã được sử dụng"
        )

    customer_role = db.scalar(
        select(Role).where(Role.name == "customer")
    )

    if customer_role is None:
        raise HTTPException(
            status_code=500,
            detail="Hệ thống chưa cấu hình vai trò khách hàng"
        )

    new_user = User(
        full_name=request.full_name,
        email=email,
        phone=request.phone,
        password_hash=hash_password(request.password),
        role_id=customer_role.id,
        is_active=True
    )

    db.add(new_user)

    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email đã được sử dụng"
        )

    return {
        "success": True,
        "message": "Đăng ký tài khoản thành công",
        "user_id": new_user.id,
        "email": new_user.email,
        "role": "customer"
    }


def login(request, db):
    email = str(request.email).strip().lower()

    user = db.scalar(
        select(User).where(User.email == email).with_for_update()
    )

    if (
        user is None
        or not user.is_active
        or not verify_password(
            request.password,
            user.password_hash
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Email hoặc mật khẩu không chính xác"
        )

    token = secrets.token_urlsafe(32)

    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(days=SESSION_DAYS)
            )
        )
    )
    db.commit()

    return token, {
        "success": True,
        "message": "Đăng nhập thành công",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role.name
        }
    }


def profile(user):
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role.name
    }


def update_profile(request, user, db):
    if "full_name" in request.model_fields_set:
        user.full_name = request.full_name
    if "phone" in request.model_fields_set:
        user.phone = request.phone

    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Không thể cập nhật hồ sơ") from None

    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role.name
    }


def logout(lumiere_session, db):
    if lumiere_session:
        token_hash = hash_session_token(lumiere_session)

        session = db.scalar(
            select(UserSession).where(
                UserSession.token_hash == token_hash
            )
        )

        if session:
            db.delete(session)
            db.commit()

    return {
        "success": True,
        "message": "Đăng xuất thành công"
    }
