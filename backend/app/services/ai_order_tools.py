
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import Order


def get_order_statistics(db: Session):
    """
    Thống kê toàn bộ đơn hàng theo trạng thái.

    Chỉ đọc database, không cập nhật dữ liệu.
    Không trả về thông tin cá nhân khách hàng.

    Quyền truy cập sẽ được kiểm tra tại API.
    """

    # Tổng số đơn hàng
    total_orders = db.scalar(
        select(func.count(Order.id))
    ) or 0

    # Thống kê theo trạng thái đơn hàng
    status_rows = db.execute(
        select(
            Order.status,
            func.count(Order.id),
        ).group_by(Order.status)
    ).all()

    # Thống kê theo trạng thái thanh toán
    payment_rows = db.execute(
        select(
            Order.payment_status,
            func.count(Order.id),
        ).group_by(Order.payment_status)
    ).all()

    order_status = {
        str(status) if status is not None else "unknown": int(count)
        for status, count in status_rows
    }

    payment_status = {
        str(status) if status is not None else "unknown": int(count)
        for status, count in payment_rows
    }

    return {
        "total_orders": int(total_orders),
        "order_status": order_status,
        "payment_status": payment_status,
        "pending_orders": order_status.get("pending", 0),
        "confirmed_orders": order_status.get("confirmed", 0),
        "delivered_orders": order_status.get("delivered", 0),
        "scope": "all_time",
    }
