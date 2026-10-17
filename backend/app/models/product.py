from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from .brand import Brand
    from .category import Category
    from .collection import Collection
    from .gemstone import Gemstone
    from .material import Material


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("id > 0", name="ck_products_id_positive"),
        CheckConstraint("length(trim(sku)) > 0", name="ck_products_sku_not_blank"),
        CheckConstraint("length(trim(barcode)) > 0", name="ck_products_barcode_not_blank"),
        CheckConstraint("length(trim(name)) > 0", name="ck_products_name_not_blank"),
        CheckConstraint("weight > 0", name="ck_products_weight_positive"),
        CheckConstraint("sale_price >= 0", name="ck_products_sale_price_nonnegative"),
        CheckConstraint("wholesale_price >= 0", name="ck_products_wholesale_price_nonnegative"),
        CheckConstraint("cost_price >= 0", name="ck_products_cost_price_nonnegative"),
        CheckConstraint("stock >= 0", name="ck_products_stock_nonnegative"),
    )

    # Assign the original CSV ProductID explicitly; never generate a new AI identity.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    barcode: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    gemstone_id: Mapped[int] = mapped_column(
        ForeignKey("gemstones.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    weight: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # All prices are in VND. Decimal avoids floating-point rounding errors.
    sale_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    wholesale_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)

    category: Mapped["Category"] = relationship("Category", back_populates="products")
    brand: Mapped["Brand"] = relationship("Brand", back_populates="products")
    material: Mapped["Material"] = relationship("Material", back_populates="products")
    gemstone: Mapped["Gemstone"] = relationship("Gemstone", back_populates="products")
    collection: Mapped["Collection"] = relationship("Collection", back_populates="products")
