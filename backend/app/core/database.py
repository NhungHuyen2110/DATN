
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# Đọc .env tại thư mục gốc JewelryDatasetGenerator
ROOT_DIR = Path(__file__).resolve().parents[3]
if os.getenv('LUMIERE_LOAD_DOTENV', 'true').lower() == 'true':
    load_dotenv(ROOT_DIR / ".env")


DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("POSTGRES_USER", "lumiere_user"),
    password=os.environ["POSTGRES_PASSWORD"],
    host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
    port=int(os.getenv("POSTGRES_PORT", "5433")),
    database=os.environ["POSTGRES_DB"],
)

connect_timeout = int(os.getenv('DATABASE_CONNECT_TIMEOUT_SECONDS', '3'))
pool_timeout = float(os.getenv('DATABASE_POOL_TIMEOUT_SECONDS', '3'))
if not 1 <= connect_timeout <= 30 or not 1 <= pool_timeout <= 30:
    raise ValueError('Database connection/pool timeouts must be 1..30 seconds')

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_timeout=pool_timeout,
    connect_args={'connect_timeout': connect_timeout},
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
