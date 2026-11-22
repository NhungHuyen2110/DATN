"""LUMIÈRE password reset, separate from existing login and register routes.

For localhost demo: set PASSWORD_RESET_DEMO_MODE=true in backend's shell.
A reset URL is printed ONLY in the backend terminal, not returned by the API.
For real deployment configure SMTP and disable demo mode.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.models import User, UserSession


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)


router = APIRouter(prefix="/auth", tags=["Authentication"])
_GENERIC_MESSAGE = "Nếu email đã được đăng ký, hướng dẫn đặt lại mật khẩu sẽ được gửi đến email đó."


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _send_email(recipient: str, url: str) -> bool:
    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", username)
    if not (host and username and password and sender):
        return False

    message = EmailMessage()
    message["Subject"] = "LUMIÈRE - Đặt lại mật khẩu"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(f"Đường dẫn đặt lại mật khẩu (hết hạn sau 15 phút):\n{url}\n\nNếu bạn không yêu cầu, hãy bỏ qua email này.")
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as client:
        client.starttls()
        client.login(username, password)
        client.send_message(message)
    return True


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if user is None:
        return {"success": True, "message": _GENERIC_MESSAGE}

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    # Invalidate existing outstanding links for this account.
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    db.add(PasswordResetToken(user_id=user.id, token_hash=_token_hash(token), expires_at=now + timedelta(minutes=15)))
    db.commit()

    base = os.getenv("PASSWORD_RESET_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
    reset_url = f"{base}/pages/reset-password.html?token={quote(token, safe='')}"

    if os.getenv("PASSWORD_RESET_DEMO_MODE", "false").lower() == "true":
        print("\n[LOCAL DEMO ONLY] Password reset link:", reset_url, flush=True)
    else:
        try:
            if not _send_email(email, reset_url):
                print("Password reset email not configured. Configure SMTP or enable LOCAL demo mode.", flush=True)
        except (OSError, smtplib.SMTPException):
            print("Password reset email delivery failed.", flush=True)

    return {"success": True, "message": _GENERIC_MESSAGE}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    record = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == _token_hash(payload.token), PasswordResetToken.used_at.is_(None))
        .with_for_update()
    )
    if record is None or record.expires_at <= now:
        raise HTTPException(status_code=400, detail="Liên kết không hợp lệ hoặc đã hết hạn")

    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Liên kết không hợp lệ hoặc đã hết hạn")

    user.password_hash = hash_password(payload.new_password)
    record.used_at = now
    # Sign out existing sessions after resetting the password.
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    db.commit()
    return {"success": True, "message": "Đặt lại mật khẩu thành công. Vui lòng đăng nhập lại."}
