"""Contact request validation."""
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=5, max_length=254)
    topic: str = Field(min_length=2, max_length=100)
    message: str = Field(min_length=10, max_length=1500)

    @field_validator("full_name", "topic", "message")
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if "\x00" in value:
            raise ValueError("Ký tự không hợp lệ")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]{1,64}@[^\s@]{1,189}\.[A-Za-z]{2,63}", value):
            raise ValueError("Email không hợp lệ")
        return value


class ContactStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(new|in_progress|closed)$")
