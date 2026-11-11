
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.routers.orders import staff_or_admin
from app.services.ai_order_tools import get_order_statistics

from pydantic import BaseModel, Field

from app.services.ai_staff_intent import (
    understand_staff_question,
)

router = APIRouter(
    prefix="/staff/ai",
    tags=["Staff AI"],
)

Database = Annotated[Session, Depends(get_db)]

ActiveStaff = Annotated[
    User,
    Depends(staff_or_admin),
]


@router.get("/order-statistics")
def staff_order_statistics(
    user: ActiveStaff,
    db: Database,
):
    """
    Thống kê đơn hàng dành cho Staff và Admin.

    - Chỉ đọc dữ liệu
    - Không trả thông tin cá nhân khách hàng
    - Không cho Customer truy cập
    """
    return get_order_statistics(db)


# ============================================================
# AI STAFF CHATBOT
# POST /staff/ai/chat
# ============================================================

class StaffChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=1000,
    )


@router.post("/chat")
def staff_ai_chat(
    request: StaffChatRequest,
    user: ActiveStaff,
    db: Database,
):
    """
    Chatbot Staff:
    - Chỉ Staff hoặc Admin được truy cập.
    - Chỉ đọc thống kê đơn hàng.
    - Không thay đổi trạng thái đơn hàng.
    - Không trả dữ liệu cá nhân khách hàng.
    """

    # Bước 1: Nhận diện câu hỏi
    intent = understand_staff_question(request.message)

    if intent.get("intent") != "order_statistics":
        return {
            "answer": intent.get(
                "message",
                "Tôi chưa hiểu yêu cầu của bạn."
            ),
            "intent": intent.get("intent", "unsupported"),
            "data": None,
        }

    # Bước 2: Lấy dữ liệu thực từ PostgreSQL
    result = get_order_statistics(db)

    # Bước 3: Chọn số liệu được phép trả lời
    field = intent.get("field")

    field_config = {
        "total_orders": (
            "Tổng số đơn hàng trong hệ thống",
            result["total_orders"],
        ),
        "pending_orders": (
            "Số đơn hàng đang chờ xử lý",
            result["pending_orders"],
        ),
        "confirmed_orders": (
            "Số đơn hàng đã xác nhận",
            result["confirmed_orders"],
        ),
        "delivered_orders": (
            "Số đơn hàng đã giao",
            result["delivered_orders"],
        ),
        "unpaid_orders": (
            "Số đơn hàng chưa thanh toán",
            result["payment_status"].get("unpaid", 0),
        ),
        "paid_orders": (
            "Số đơn hàng có trạng thái đã thanh toán",
            result["payment_status"].get("paid", 0),
        ),
    }

    if field not in field_config:
        return {
            "answer": "Tôi chưa hỗ trợ loại thống kê này.",
            "intent": "unsupported",
            "data": None,
        }

    label, value = field_config[field]

    # Bước 4: Trả câu trả lời tiếng Việt
    answer = f"{label}: {value} đơn."

    return {
        "answer": answer,
        "intent": "order_statistics",
        "field": field,
        "data": {
            "value": value,
            "scope": result["scope"],
        },
    }
