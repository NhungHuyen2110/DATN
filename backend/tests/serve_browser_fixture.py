"""Local browser fixture: ephemeral SQLite only; never loads the project's .env."""
import os
from pathlib import Path
import sys
from datetime import timezone
from unittest.mock import patch

import sqlalchemy as sa
from sqlalchemy.orm import Session, attributes
from sqlalchemy.pool import StaticPool


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ.update(POSTGRES_DB="browser_test_only", POSTGRES_PASSWORD="test-placeholder")
    engine = sa.create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    original_connect = sa.engine.Engine.connect

    def memory_only(db_engine, *args, **kwargs):
        if db_engine.dialect.name != "sqlite" or db_engine.url.database != ":memory:":
            raise AssertionError("Browser fixture forbids persistent database connections")
        return original_connect(db_engine, *args, **kwargs)

    with patch("dotenv.load_dotenv"), patch.object(sa.engine.Engine, "connect", memory_only):
        with patch("sqlalchemy.create_engine", return_value=engine):
            from app.core.database import Base, get_db
            from app.main import app
        from app.core.security import hash_password
        from app.models import Role, User, UserSession, Product, Brand, Category, Collection, Gemstone, Material
        Base.metadata.create_all(engine)

        def restore_utc(target, context):
            if target.expires_at.tzinfo is None:
                attributes.set_committed_value(target, "expires_at", target.expires_at.replace(tzinfo=timezone.utc))

        sa.event.listen(UserSession, "load", restore_utc)
        with Session(engine) as db, db.begin():
            for ident, role in enumerate(("customer", "staff", "admin"), 1):
                db.add(Role(id=ident, name=role))
                db.add(User(id=ident, role_id=ident, full_name=f"Browser {role}", email=f"{role}@example.com",
                            phone="0901234567", password_hash=hash_password("Browser-Test-123!"), is_active=True))
            for model, name in ((Category, "Nhẫn"), (Brand, "LUMIÈRE"), (Collection, "Classic"), (Gemstone, "Diamond"), (Material, "Gold")):
                db.add(model(id=1, name=name))
            db.flush()
            db.add(Product(id=1, sku="BROWSER001", barcode="BROWSER001", name="Nhẫn Browser Test",
                           category_id=1, brand_id=1, collection_id=1, gemstone_id=1, material_id=1,
                           weight=1, sale_price=100000, wholesale_price=90000, cost_price=80000, stock=20))

        def override_db():
            with Session(engine) as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=18001, log_level="warning")


if __name__ == "__main__":
    main()
