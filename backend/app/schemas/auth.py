
from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = None
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, value: str):
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Họ tên phải có ít nhất 2 ký tự")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None):
        if value is None or not value.strip():
            return None

        value = value.strip()

        if not (
            len(value) == 10
            and value.isascii()
            and value.isdigit()
            and value.startswith("0")
        ):
            raise ValueError(
                "Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0"
            )

        return value


class RegisterResponse(BaseModel):
    success: bool
    message: str
    user_id: int
    email: EmailStr
    role: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
