
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password
from app.models import Role, User
from app.schemas.auth import RegisterRequest, RegisterResponse
from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from fastapi import Cookie, Response
from app.core.security import verify_password
from app.models import UserSession
from app.schemas.auth import LoginRequest, ProfileResponse, ProfileUpdateRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
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


# ================================================
# SESSION CONFIG
# ================================================

COOKIE_NAME = "lumiere_session"
SESSION_DAYS = 7
SESSION_SECONDS = SESSION_DAYS * 24 * 60 * 60


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_user(
    lumiere_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db)
) -> User:

    if not lumiere_session:
        raise HTTPException(
            status_code=401,
            detail="Bạn chưa đăng nhập"
        )

    token_hash = hash_session_token(lumiere_session)

    session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == token_hash
        )
    )

    now = datetime.now(timezone.utc)

    if session is None or session.expires_at <= now:
        raise HTTPException(
            status_code=401,
            detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn"
        )

    user = db.get(User, session.user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Tài khoản không khả dụng"
        )

    return user


# ================================================
# LOGIN
# ================================================

@router.post("/login")
def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
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

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,  # Chỉ dùng khi phát triển trên localhost
        samesite="lax",
        max_age=SESSION_SECONDS,
        path="/"
    )

    return {
        "success": True,
        "message": "Đăng nhập thành công",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role.name
        }
    }


# ================================================
# CURRENT USER
# ================================================

@router.get("/me", response_model=ProfileResponse)
def get_me(
    user: User = Depends(get_current_user)
):
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role.name
    }


@router.patch("/me", response_model=ProfileResponse)
def update_me(
    request: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Explicit allowlist; identity comes exclusively from the existing session.
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


# ================================================
# LOGOUT
# ================================================

@router.post("/logout")
def logout(
    response: Response,
    lumiere_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db)
):
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

    response.delete_cookie(
        key=COOKIE_NAME,
        path="/"
    )

    return {
        "success": True,
        "message": "Đăng xuất thành công"
    }

