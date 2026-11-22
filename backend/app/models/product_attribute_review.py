"""Human-approved facts, separate from the preserved original product columns."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
# Native `cd backend` and the isolated worker both need the shared package root.
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from shared.verified_attributes import validate_attribute


class ProductAttributeReview(Base):
    __tablename__='product_attribute_reviews'
    __table_args__=(
        UniqueConstraint('product_id','label','canonical_id',name='uq_product_review_attribute'),
        CheckConstraint("(label='Audience' AND canonical_id IN ('female','male','child_female')) OR "
                        "(label='Style' AND canonical_id IN ('elegant','minimalist','refined'))",
                        name='ck_reviewed_attribute_canonical'),
        CheckConstraint('version > 0',name='ck_attribute_review_version'),
        CheckConstraint('length(trim(source_reference)) > 0',name='ck_attribute_review_source'),
    )
    id: Mapped[int]=mapped_column(primary_key=True)
    product_id: Mapped[int]=mapped_column(ForeignKey('products.id',ondelete='CASCADE'),index=True)
    label: Mapped[str]=mapped_column(String(16))
    canonical_id: Mapped[str]=mapped_column(String(32))
    source_reference: Mapped[str]=mapped_column(String(200))
    reviewed_by: Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'))
    reviewed_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    active: Mapped[bool]=mapped_column(Boolean,default=True)
    version: Mapped[int]=mapped_column(Integer,default=1)
    review_log: Mapped[list]=mapped_column(JSON,default=list)

    @property
    def name(self):
        return validate_attribute(self.label,self.canonical_id)

    @property
    def source_reference_sha256(self):
        return hashlib.sha256(self.source_reference.encode('utf-8')).hexdigest()
