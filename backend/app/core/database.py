
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# Đọc .env tại thư mục gốc JewelryDatasetGenerator
ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")


DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("POSTGRES_USER", "lumiere_user"),
    password=os.environ["POSTGRES_PASSWORD"],
    host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
    port=int(os.getenv("POSTGRES_PORT", "5433")),
    database=os.environ["POSTGRES_DB"],
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        return result.scalar() == 1
