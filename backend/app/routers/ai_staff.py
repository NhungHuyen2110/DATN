from app.services.ai_product_lookup import answer_product_lookup
from app.services.ai_order_time_tools import get_orders_by_period
from app.services.ai_inventory_chat import answer_inventory_question
from fastapi import Query, Request
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

    from app.services.ai_order_chat import answer_order_question
    classifier = (understand_staff_question_with_llm
                  if os.getenv('STAFF_AI_LLM_ENABLED', 'false').lower() == 'true'
                  else understand_staff_question)
    return answer_order_question(request.message, db, statistics=get_order_statistics,
                                 period=get_orders_by_period, classifier=classifier)


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
def staff_ai_chat(request:StaffChatRequest,user:ActiveStaff,db:Database,http_request:Request):
    from shared.conversation import converse
    from app.services.ai_business_dialogue import business_turn
    from app.routers.auth import COOKIE_NAME, hash_session_token
    session_scope = hash_session_token(http_request.cookies.get(COOKIE_NAME, ''))
    return converse(request.message,request.conversation_id,('staff',user.id,session_scope),
                    lambda message:_staff_ai_tools(StaffChatRequest(message=message),user,db),
                    dialogue=lambda message,row,tool:business_turn(message,row,tool,role='staff'))
