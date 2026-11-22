from app.services.ai_admin_business import get_revenue_statistics
from app.services.ai_inventory_chat import answer_inventory_question
from app.services.ai_admin_revenue_intent import understand_revenue_question
import os
from datetime import date
from decimal import Decimal
from typing import Annotated
from app.services.ai_product_lookup import answer_product_lookup
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.routers.orders import admin
from app.services.ai_admin_analytics import get_top_selling_products
from app.services.ai_admin_intent import understand_admin_question
from app.services.ai_admin_llm import understand_admin_question_with_llm

from app.services.ai_admin_orchestrator import (
    answer_admin_multi_intent,
)

# ============================================================
# ROUTER AI ADMIN
# ============================================================

router = APIRouter(
    prefix="/admin/ai",
    tags=["Admin AI"],
)

Database = Annotated[Session, Depends(get_db)]
ActiveAdmin = Annotated[User, Depends(admin)]


class RetrievalDiagnosticsRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=10)
    rerank: bool = False
    semantic_entities: bool = False


@router.post('/retrieval-diagnostics')
def diagnose_retrieval(request: RetrievalDiagnosticsRequest, user: ActiveAdmin):
    from app.services.ai_retrieval_diagnostics import retrieval_diagnostics
    return retrieval_diagnostics(request.model_dump())


@router.get('/sync-status')
def product_sync_status(user: ActiveAdmin, db: Database):
    from app.services.product_index_jobs import sync_status
    return sync_status(db)


# ============================================================
# API 1: THỐNG KÊ SẢN PHẨM BÁN CHẠY
# GET /admin/ai/top-selling-products
# ============================================================

@router.get("/top-selling-products")
def top_selling_products(
    user: ActiveAdmin,
    db: Database,
    start_date: date,
    end_date: date,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
):
    return get_top_selling_products(
        db=db,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


# ============================================================
# REQUEST MODEL
# ============================================================

class AdminChatRequest(BaseModel):
    conversation_id: str | None = Field(default=None,max_length=128)
    message: str = Field(
        min_length=1,
        max_length=1000,
    )


# ============================================================
# HELPER: ĐỊNH DẠNG TIỀN
# ============================================================

def format_money(value):
    amount = Decimal(str(value))
    return f"{amount:,.0f}".replace(",", ".") + " ₫"


# ============================================================
# HELPER: KIỂM TRA INTENT HỢP LỆ
# ============================================================

def is_valid_top_selling_intent(intent):
    """
    Chỉ cho phép gọi công cụ thống kê khi:
    - intent đúng loại
    - đầy đủ tham số
    - ngày và limit hợp lệ

    Tránh lỗi KeyError và dữ liệu LLM không hợp lệ.
    """

    if not isinstance(intent, dict):
        return False

    if intent.get("intent") != "top_selling_products":
        return False

    start_date = intent.get("start_date")
    end_date = intent.get("end_date")
    limit = intent.get("limit")

    if not isinstance(start_date, date):
        return False

    if not isinstance(end_date, date):
        return False

    if start_date > end_date:
        return False

    if type(limit) is not int or not 1 <= limit <= 20:
        return False

    return True


# ============================================================
# API 2: CHATBOT AI ADMIN
# POST /admin/ai/chat
# ============================================================

def _admin_ai_tools(
    request: AdminChatRequest,
    user: ActiveAdmin,
    db: Database,
):
    """
    Chatbot AI Admin:
    1. Nhận câu hỏi tiếng Việt.
    2. Nhận diện ý định bằng rule hoặc LLM.
    3. Kiểm tra tính hợp lệ của intent.
    4. Truy vấn dữ liệu PostgreSQL.
    5. Trả lời bằng tiếng Việt.

    Chỉ Admin được truy cập.
    """

    product_response = answer_product_lookup(
        db=db,
        message=request.message,
    )

    if product_response is not None:
        return product_response
    # --------------------------------------------------------
    # BƯỚC 1: NHẬN DIỆN CÂU HỎI

    # Ưu tiên xử lý nhiều nghiệp vụ.
    multi_response = answer_admin_multi_intent(
        db=db,
        message=request.message,
    )

    if multi_response is not None:
        return multi_response
    # --------------------------------------------------------
    # Ưu tiên nhận diện câu hỏi doanh thu.

    inventory_response = answer_inventory_question(
        db, request.message
    )

    if inventory_response is not None:
        return inventory_response
    revenue_intent = understand_revenue_question(request.message)

    if revenue_intent.get("intent") == "revenue_statistics":
        result = get_revenue_statistics(
            db=db,
            start_date=revenue_intent["start_date"],
            end_date=revenue_intent["end_date"],
            group_by=revenue_intent["group_by"],
        )

        amount = format_money(
            result["confirmed_payment_amount_vnd"]
        )
        count = result["confirmed_payment_order_count"]

        answer = (
            "Từ ngày "
            f"{revenue_intent['start_date']:%d/%m/%Y} "
            "đến ngày "
            f"{revenue_intent['end_date']:%d/%m/%Y}, "
            f"tổng tiền thanh toán được xác nhận là {amount}, "
            f"với {count} đơn hàng hợp lệ."
        )

        return {
            "answer": answer,
            "intent": "revenue_statistics",
            "data": result,
        }

    if revenue_intent.get("intent") == "invalid":
        return {
            "answer": revenue_intent.get(
                "message", "Khoảng thời gian không hợp lệ."
            ),
            "intent": "invalid",
            "data": None,
        }

    # Không trả lời một phần câu hỏi có nhiều nghiệp vụ.
    if revenue_intent.get("message"):
        return {
            "answer": revenue_intent["message"],
            "intent": "unsupported",
            "data": None,
        }

    # Giữ nguyên luồng AI sản phẩm bán chạy.
    enable_llm = (
        os.getenv("ADMIN_AI_LLM_ENABLED", "false").lower()
        == "true"
    )

    if enable_llm:
        intent = understand_admin_question_with_llm(
            request.message
        )
    else:
        intent = understand_admin_question(
            request.message
        )


    # --------------------------------------------------------
    # BƯỚC 2: KIỂM TRA INTENT TRƯỚC KHI TRUY VẤN
    # --------------------------------------------------------

    if not is_valid_top_selling_intent(intent):
        message = (
            intent.get("message")
            if isinstance(intent, dict)
            else None
        )

        return {
            "answer": message or (
                "Tôi chưa hiểu rõ yêu cầu thống kê. "
                "Bạn có thể hỏi, ví dụ: "
                "'Top 5 sản phẩm bán chạy tháng 10/2026'."
            ),
            "intent": "unsupported",
            "data": None,
        }

    # --------------------------------------------------------
    # BƯỚC 3: TRUY VẤN POSTGRESQL
    # --------------------------------------------------------

    result = get_top_selling_products(
        db=db,
        start_date=intent["start_date"],
        end_date=intent["end_date"],
        limit=intent["limit"],
    )

    items = result["items"]

    # --------------------------------------------------------
    # BƯỚC 4: TẠO CÂU TRẢ LỜI TIẾNG VIỆT
    # --------------------------------------------------------

    if not items:
        answer = (
            "Không tìm thấy sản phẩm bán chạy trong khoảng "
            f"thời gian từ {intent['start_date']:%d/%m/%Y} "
            f"đến {intent['end_date']:%d/%m/%Y}."
        )

    else:
        lines = [
            "Các sản phẩm bán chạy nhất từ "
            f"{intent['start_date']:%d/%m/%Y} "
            "đến "
            f"{intent['end_date']:%d/%m/%Y}:"
        ]

        for index, item in enumerate(items, 1):
            lines.append(
                f"{index}. {item['product_name']}: "
                f"{item['quantity_sold']} sản phẩm, "
                "giá trị bán hàng "
                f"{format_money(item['gross_item_value_vnd'])}"
            )

        answer = "\n".join(lines)

    # --------------------------------------------------------
    # BƯỚC 5: TRẢ KẾT QUẢ
    # --------------------------------------------------------

    return {
        "answer": answer,
        "intent": "top_selling_products",
        "data": result,
    }


@router.post('/chat')
def admin_ai_chat(request:AdminChatRequest,user:ActiveAdmin,db:Database):
    from shared.conversation import converse
    return converse(request.message,request.conversation_id,('admin',user.id),
                    lambda message:_admin_ai_tools(AdminChatRequest(message=message),user,db))
