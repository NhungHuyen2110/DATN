
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.dashboard import revenue


def get_revenue_statistics(
    db: Session,
    start_date: date,
    end_date: date,
    group_by: str = "month",
):
    """
    Công cụ doanh thu dành cho AI Admin.

    Tái sử dụng logic Dashboard hiện có.
    Không tự viết SQL và không thay đổi dữ liệu.
    """

    # Kiểm tra tham số thống kê
    if group_by not in {"day", "month"}:
        raise HTTPException(
            status_code=422,
            detail="group_by phải là day hoặc month",
        )

    if (
        start_date > end_date
        or end_date == date.max
        or (end_date - start_date).days > 3660
    ):
        raise HTTPException(
            status_code=422,
            detail="Khoảng thời gian không hợp lệ",
        )

    # Tận dụng hoàn toàn quy tắc doanh thu của Dashboard
    result = revenue(
        db=db,
        start_date=start_date,
        end_date=end_date,
        group_by=group_by,
    )

    # Chuyển kết quả thành dữ liệu an toàn cho AI
    # Dùng chuỗi Decimal để giữ độ chính xác.
    return {
        "start_date": result.start_date.isoformat(),
        "end_date": result.end_date.isoformat(),
        "group_by": result.group_by,
        "confirmed_payment_amount_vnd": str(
            result.confirmed_payment_amount_vnd
        ),
        "confirmed_payment_order_count": (
            result.confirmed_payment_order_count
        ),
        "items": [
            {
                "period_start": item.period_start.isoformat(),
                "confirmed_payment_amount_vnd": str(
                    item.confirmed_payment_amount_vnd
                ),
                "confirmed_payment_order_count": (
                    item.confirmed_payment_order_count
                ),
            }
            for item in result.items
        ],
    }
