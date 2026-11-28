
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Order
from app.schemas.order import OrderStatus
from typing import get_args


VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")

ALLOWED_STATUSES = frozenset(get_args(OrderStatus))


def get_orders_by_period(
    db: Session,
    start_date: date,
    end_date: date,
    status: str | None = None,
):
    """
    Đếm các đơn được tạo trong khoảng ngày tại Việt Nam.

    - Chỉ sử dụng SELECT
    - Không trả thông tin khách hàng
    - Không sửa trạng thái đơn
    """

    if (
        start_date > end_date
        or end_date == date.max
        or (end_date - start_date).days > 3660
    ):
        raise HTTPException(
            status_code=422,
            detail="Khoảng thời gian không hợp lệ",
        )

    if status is not None and status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=422,
            detail="Trạng thái đơn hàng không được hỗ trợ",
        )

    # Đầu ngày Việt Nam -> UTC
    start_utc = datetime.combine(
        start_date,
        time.min,
        tzinfo=VIETNAM,
    ).astimezone(timezone.utc)

    # Đầu ngày kế tiếp -> UTC, dùng khoảng [start, end)
    end_utc = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
        tzinfo=VIETNAM,
    ).astimezone(timezone.utc)

    query = select(func.count(Order.id)).where(
        Order.created_at >= start_utc,
        Order.created_at < end_utc,
    )

    if status is not None:
        query = query.where(Order.status == status)

    total = db.scalar(query) or 0

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timezone": "Asia/Ho_Chi_Minh",
        "date_field": "created_at",
        "status": status,
        "total_orders": int(total),
    }
