"""Taxonomy input validation."""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LookupWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=150)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        name = " ".join(value.split())
        if not name or "\x00" in name:
            raise ValueError("Tên không hợp lệ")
        return name
