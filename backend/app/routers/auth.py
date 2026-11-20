"""Authentication HTTP endpoints; account/session operations live in services.auth."""
from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlalchemy.orm import Session
import os
from app.core.database import get_db
from app.core.dependencies import get_current_user, hash_session_token  # Compatibility exports
from app.models import User
from app.services import auth as service
from app.core.security import COOKIE_NAME, SESSION_SECONDS
from app.schemas.auth import RegisterRequest, RegisterResponse

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
    return service.register(request, db)


# ================================================
# LOGIN
# ================================================

@router.post("/login")
def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    token, result = service.login(request, db)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        max_age=SESSION_SECONDS,
        path="/"
    )
    return result


# ================================================
# CURRENT USER
# ================================================

@router.get("/me", response_model=ProfileResponse)
def get_me(
    user: User = Depends(get_current_user)
):
    return service.profile(user)


@router.patch("/me", response_model=ProfileResponse)
def update_me(
    request: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Explicit allowlist; identity comes exclusively from the existing session.
    return service.update_profile(request, user, db)


# ================================================
# LOGOUT
# ================================================

@router.post("/logout")
def logout(
    response: Response,
    lumiere_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db)
):
    result = service.logout(lumiere_session, db)
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return result

