
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False
    )

    users: Mapped[list["User"]] = relationship(
        "User", back_populates="role"
    )
