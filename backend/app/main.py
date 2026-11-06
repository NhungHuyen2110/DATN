from pathlib import Path
from fastapi.staticfiles import StaticFiles
from app.routers.auth import router as auth_router
from app.routers.catalog import router as catalog_router
from app.routers.taxonomy import router as taxonomy_router
from app.routers.cart import router as cart_router
from app.routers.orders import router as orders_router
from app.routers.payments import router as payments_router
from app.routers.admin_staff import router as admin_staff_router
from app.routers.admin_customers import router as admin_customers_router
from app.routers.coupons import router as coupons_router
from app.routers.dashboard import router as dashboard_router
from app.routers.customer_content import router as customer_content_router
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from app.core.database import check_database

import logging

logger = logging.getLogger("uvicorn.error")
app = FastAPI(
    title="LUMIÈRE Business API",
    description="Backend nghiệp vụ website bán trang sức",
    version="1.0.0",
)
app.include_router(auth_router)
app.include_router(catalog_router)
app.include_router(taxonomy_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(payments_router)
app.include_router(admin_staff_router)
app.include_router(admin_customers_router)
app.include_router(coupons_router)
app.include_router(dashboard_router)
app.include_router(customer_content_router)
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5500"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health")
def health():
    try:
        database_ok = check_database()
    except Exception as exc:
        original = getattr(exc, "orig", None)
        message = str(original or exc).lower()

        if "password authentication failed" in message:
            reason = "PASSWORD_AUTH_FAILED"
        elif "could not translate host name" in message or "name or service not known" in message:
            reason = "HOSTNAME_RESOLUTION_FAILED"
        elif "connection refused" in message:
            reason = "CONNECTION_REFUSED"
        elif "timeout" in message or "timed out" in message:
            reason = "CONNECTION_TIMEOUT"
        elif "ssl" in message or "certificate" in message:
            reason = "SSL_ERROR"
        else:
            reason = "OTHER_DATABASE_ERROR"

        logger.error(
            "LUMIERE_DATABASE_ERROR: type=%s reason=%s sqlstate=%s",
            type(exc).__name__,
            reason,
            getattr(original, "sqlstate", None)
        )

        raise HTTPException(
            status_code=503,
            detail="Không thể kết nối PostgreSQL"
        ) from None

    if not database_ok:
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL chưa sẵn sàng"
        )

    return {
        "status": "healthy",
        "database": "connected"
    }

# Serve the frontend after all API routes.
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
app.mount(
    "/",
    StaticFiles(directory=str(FRONTEND_DIR), html=True),
    name="frontend",
)
