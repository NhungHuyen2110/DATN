
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OrderItem
from app.services.dashboard import (
    VIETNAM,
    payment_summary_query,
    classify,
)


def get_top_selling_products(
    db: Session,
    start_date: date,
    end_date: date,
    limit: int = 5,
):
    if start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="Ngày bắt đầu phải trước hoặc bằng ngày kết thúc",
        )

    if not 1 <= limit <= 20:
        raise HTTPException(
            status_code=422,
            detail="limit phải từ 1 đến 20",
        )

    if end_date == date.max or (end_date - start_date).days > 3660:
        raise HTTPException(
            status_code=422,
            detail="Khoảng thời gian không hợp lệ",
        )

    start_utc = datetime.combine(
        start_date, time.min, VIETNAM
    ).astimezone(timezone.utc)

    end_utc = datetime.combine(
        end_date + timedelta(days=1), time.min, VIETNAM
    ).astimezone(timezone.utc)

    # Tận dụng quy tắc xác nhận thanh toán của Dashboard.
    summary = payment_summary_query().subquery()

    payment_rows = db.execute(
        select(summary).where(
            summary.c.verified_at >= start_utc,
            summary.c.verified_at < end_utc,
        )
    ).mappings().all()

    eligible_order_ids = [
        row["id"]
        for row in payment_rows
        if classify(row)[0]
    ]

    if not eligible_order_ids:
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "metric": "confirmed_payment_sales",
            "items": [],
        }

    order_items = db.scalars(
        select(OrderItem).where(
            OrderItem.order_id.in_(eligible_order_ids)
        )
    ).all()

    products = {}

    for item in order_items:
        product = products.setdefault(
            item.product_id,
            {
                "product_id": item.product_id,
                "product_name": item.product_name,
                "quantity_sold": 0,
                "gross_item_value_vnd": Decimal("0"),
            },
        )

        product["quantity_sold"] += item.quantity
        product["gross_item_value_vnd"] += item.line_total_vnd

    ranked = sorted(
        products.values(),
        key=lambda item: (
            -item["quantity_sold"],
            -item["gross_item_value_vnd"],
            item["product_id"],
        ),
    )

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "metric": "confirmed_payment_sales",
        "items": [
            {
                **item,
                "gross_item_value_vnd": str(
                    item["gross_item_value_vnd"]
                ),
            }
            for item in ranked[:limit]
        ],
    }
