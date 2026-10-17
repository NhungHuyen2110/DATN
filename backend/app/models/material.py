from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from .product import Product


class Material(Base):
    __tablename__ = "materials"
    __table_args__ = (
        CheckConstraint("id > 0", name="ck_materials_id_positive"),
        CheckConstraint("length(trim(name)) > 0", name="ck_materials_name_not_blank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)

    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="material"
    )
