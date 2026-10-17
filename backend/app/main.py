from app.routers.auth import router as auth_router
from app.routers.catalog import router as catalog_router
from app.routers.cart import router as cart_router
from app.routers.orders import router as orders_router
from app.routers.payments import router as payments_router
from app.routers.admin_staff import router as admin_staff_router
from app.routers.dashboard import router as dashboard_router
from app.routers.customer_content import router as customer_content_router
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import check_database


app = FastAPI(
    title="LUMIÈRE Business API",
    description="Backend nghiệp vụ website bán trang sức",
    version="1.0.0",
)
app.include_router(auth_router)
app.include_router(catalog_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(payments_router)
app.include_router(admin_staff_router)
app.include_router(dashboard_router)
app.include_router(customer_content_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/")
def home():
    return {
        "success": True,
        "message": "LUMIÈRE Business API đang hoạt động"
    }


@app.get("/health")
def health():
    try:
        database_ok = check_database()
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Không thể kết nối PostgreSQL"
        )

    if not database_ok:
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL chưa sẵn sàng"
        )

    return {
        "status": "healthy",
        "database": "connected"
    }
