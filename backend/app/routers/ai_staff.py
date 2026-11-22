from app.services.ai_product_lookup import answer_product_lookup
from app.services.ai_staff_intent import normalize_text
from app.services.ai_order_time_tools import get_orders_by_period
from app.services.ai_order_time_intent import understand_time_order_question
from app.services.ai_inventory_chat import answer_inventory_question
from fastapi import Query
from app.services.ai_staff_orchestrator import answer_staff_multi_intent
from app.services.ai_inventory_tools import (
    get_inventory_statistics,
)
import os

from app.services.ai_staff_llm import (
    understand_staff_question_with_llm,
)

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
    conversation_id: str | None = Field(default=None,max_length=128)
    message: str = Field(
        min_length=1,
        max_length=1000,
    )


def _staff_ai_tools(
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

    product_response = answer_product_lookup(
        db=db,
        message=request.message,
    )

    if product_response is not None:
        return product_response

    # Ưu tiên 1: Câu hỏi nhiều nghiệp vụ
    multi_response = answer_staff_multi_intent(
        db=db,
        message=request.message,
    )

    if multi_response is not None:
        return multi_response

    # Ưu tiên 2: Câu hỏi tồn kho đơn nghiệp vụ
    inventory_response = answer_inventory_question(
        db, request.message
    )

    if inventory_response is not None:
        return inventory_response

    time_intent = understand_time_order_question(
        request.message
    )

    if time_intent is not None:
        if time_intent.get("intent") != "orders_by_period":
            return {
                "answer": time_intent.get(
                    "message", "Câu hỏi chưa được hỗ trợ."
                ),
                "intent": time_intent.get(
                    "intent", "unsupported"
                ),
                "data": None,
            }

        result = get_orders_by_period(
            db=db,
            start_date=time_intent["start_date"],
            end_date=time_intent["end_date"],
            status=time_intent["status"],
        )

        status_names = {
            None: "tổng cộng",
            "pending": "đang chờ xử lý",
            "confirmed": "đã xác nhận",
            "delivered": "đã giao",
        }

        status_label = status_names[result["status"]]

        answer = (
            f"Từ {time_intent['start_date']:%d/%m/%Y} "
            f"đến {time_intent['end_date']:%d/%m/%Y}, "
            f"hệ thống có {result['total_orders']} "
            f"đơn hàng {status_label} "
            "(tính theo ngày tạo đơn)."
        )

        return {
            "answer": answer,
            "intent": "orders_by_period",
            "data": result,
        }

    # Bước 1: Nhận diện câu hỏi
    # Mặc định dùng bộ nhận diện cũ đã hoạt động ổn định.
        # Chặn yêu cầu vượt phạm vi thống kê hiện tại,
    # áp dụng cho cả chế độ bật và tắt Ollama.
    text = normalize_text(request.message)

    unsupported_patterns = (
        "hom nay",
        "hom qua",
        "thang nay",
        "thang truoc",
        "tuan nay",
        "ngay ",
        "liet ke",
        "danh sach",
        "ma don",
        "don nao",
    )

    if any(pattern in text for pattern in unsupported_patterns):
        return {
            "answer": (
                "Hiện tại tôi chỉ hỗ trợ thống kê số lượng "
                "đơn hàng trong toàn bộ lịch sử. "
                "Chức năng lọc thời gian và liệt kê "
                "đơn cụ thể chưa được hỗ trợ."
            ),
            "intent": "unsupported",
            "data": None,
        }
    enable_llm = (
        os.getenv("STAFF_AI_LLM_ENABLED", "false").lower()
        == "true"
    )

    if enable_llm:
        intent = understand_staff_question_with_llm(
            request.message
        )
    else:
        intent = understand_staff_question(
            request.message
        )

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


@router.get("/inventory-statistics")
def staff_inventory_statistics(
    user: ActiveStaff,
    db: Database,
    threshold: int = Query(default=5, ge=0, le=1000),
    limit: int = Query(default=20, ge=1, le=50),
):
    """
    Công cụ AI tồn kho cho Staff và Admin.
    Chỉ đọc số lượng tồn hiện tại.
    """
    return get_inventory_statistics(
        db=db,
        threshold=threshold,
        limit=limit,
    )


@router.post('/chat')
def staff_ai_chat(request:StaffChatRequest,user:ActiveStaff,db:Database):
    from shared.conversation import converse
    return converse(request.message,request.conversation_id,('staff',user.id),
                    lambda message:_staff_ai_tools(StaffChatRequest(message=message),user,db))
