
from sqlalchemy import select

from app.core.database import Base, engine, SessionLocal
from app.models import Role, User


def init_database():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        for name in ["customer", "staff", "admin"]:
            role = db.scalar(
                select(Role).where(Role.name == name)
            )

            if role is None:
                db.add(Role(name=name))

        db.commit()

    print("DATABASE INITIALIZED SUCCESSFULLY")


if __name__ == "__main__":
    init_database()
