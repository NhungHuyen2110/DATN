
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator, model_validator
from datetime import datetime, timezone


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


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None):
        if value is None or "\x00" in value:
            raise ValueError("Họ tên không được null hoặc chứa ký tự NUL")
        return RegisterRequest.validate_name(value)

    @field_validator("phone")
    @classmethod
    def validate_profile_phone(cls, value: str | None):
        return RegisterRequest.validate_phone(value)

    @model_validator(mode="after")
    def require_update(self):
        if not self.model_fields_set:
            raise ValueError("Cần cung cấp full_name hoặc phone")
        return self


class ProfileResponse(UserResponse):
    phone: str | None


class StaffCreateRequest(RegisterRequest):
    model_config = ConfigDict(extra="forbid")
    password: SecretStr = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("full_name")
    @classmethod
    def reject_nul_name(cls, value):
        if "\x00" in value:
            raise ValueError("Họ tên không được chứa ký tự NUL")
        return value


class StaffStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool = Field(strict=True)


class StaffAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr
    phone: str | None
    is_active: bool
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc_created_at(cls, value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class StaffAccountPage(BaseModel):
    items: list[StaffAccountResponse]
    page: int
    page_size: int
    total: int
