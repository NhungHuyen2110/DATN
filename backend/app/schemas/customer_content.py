"""Explicit allowlists; comments remain untrusted plain text."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.catalog import ProductResponse


Rating = Annotated[int, Field(strict=True, ge=1, le=5)]
Comment = Annotated[str, Field(min_length=1, max_length=2000)]


class DeleteMessageResponse(BaseModel):
    message: str = Field(description="Thông báo xóa thành công bằng tiếng Việt")


class WishlistAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: int = Field(strict=True, ge=1, le=2147483647)


class WishlistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product: ProductResponse
    created_at: datetime


class WishlistPage(BaseModel):
    items: list[WishlistResponse]
    page: int
    page_size: int
    total: int


class CommentValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("comment", mode="before", check_fields=False)
    @classmethod
    def normalize_comment(cls, value):
        if isinstance(value, str):
            if "\x00" in value:
                raise ValueError("Comment cannot contain NUL")
            return value.strip()
        return value


class ReviewCreate(CommentValidation):
    rating: Rating
    comment: Comment


class ReviewUpdate(CommentValidation):
    rating: Rating | None = None
    comment: Comment | None = None

    @model_validator(mode="after")
    def nonempty_patch(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Provide rating or comment; explicit null is not allowed")
        return self


class ReviewResponse(BaseModel):
    id: int
    product_id: int
    rating: int
    comment: str
    author_display_name: str
    created_at: datetime
    updated_at: datetime


class ReviewPage(BaseModel):
    items: list[ReviewResponse]
    page: int
    page_size: int
    total: int
