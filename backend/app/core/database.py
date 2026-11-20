
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# Đọc .env tại thư mục gốc JewelryDatasetGenerator
ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")


def _positive_int(name, default):
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


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
    pool_timeout=_positive_int("DB_POOL_TIMEOUT_SECONDS", 5),
    connect_args={
        "connect_timeout": _positive_int("DB_CONNECT_TIMEOUT_SECONDS", 5),
        "options": (
            f"-c statement_timeout={_positive_int('DB_STATEMENT_TIMEOUT_MS', 15000)} "
            f"-c lock_timeout={_positive_int('DB_LOCK_TIMEOUT_MS', 5000)}"
        ),
    },
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
