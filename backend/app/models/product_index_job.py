"""Coalescing transactional outbox, one durable pending generation per product."""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProductIndexJob(Base):
    __tablename__ = 'product_index_jobs'
    __table_args__ = (
        CheckConstraint('product_id > 0 AND generation > 0 AND delivered_generation >= 0 AND delivered_generation <= generation', name='ck_index_job_generation'),
        CheckConstraint("status IN ('pending','processing','done','dead') AND attempts >= 0", name='ck_index_job_status'),
        CheckConstraint("(status = 'processing' AND lease_token IS NOT NULL AND lease_until IS NOT NULL) OR (status <> 'processing' AND lease_token IS NULL AND lease_until IS NULL)", name='ck_index_job_lease'),
    )
    # No product FK: preserve a tombstone when a product is deleted.
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    delivered_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    dirty_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lease_token: Mapped[str | None] = mapped_column(String(32))
    last_error_type: Mapped[str | None] = mapped_column(String(100))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
