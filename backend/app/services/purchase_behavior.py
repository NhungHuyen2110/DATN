"""Purchase-only behavior indicators from real orders; no fabricated browsing events."""

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Order, OrderItem, Product

VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")


def analyze(db, start_date: date, end_date: date):
    if start_date > end_date or (end_date-start_date).days > 366 or end_date == date.max:
        raise HTTPException(status_code=422, detail="Khoảng thống kê phải từ 1 đến 367 ngày")
    start = datetime.combine(start_date, time.min, VIETNAM).astimezone(timezone.utc)
    end = datetime.combine(end_date + timedelta(days=1), time.min, VIETNAM).astimezone(timezone.utc)
    orders = db.scalars(
        select(Order).where(Order.created_at >= start, Order.created_at < end)
        .order_by(Order.created_at)
    ).all()
    order_ids = [row.id for row in orders]
    by_status, by_payment = Counter(), Counter()
    by_day = Counter()
    buyers = Counter()
    coupons = 0
    for order in orders:
        by_status[order.status] += 1
        by_payment[order.payment_method] += 1
        buyers[order.user_id] += 1
        if order.coupon_code:
            coupons += 1
        created = order.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        by_day[created.astimezone(VIETNAM).date().isoformat()] += 1

    counts = Counter()
    names = {}
    quantities = 0
    for order_id, product_id, product_name, quantity in db.execute(
        select(OrderItem.order_id, OrderItem.product_id, OrderItem.product_name, OrderItem.quantity)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.created_at >= start, Order.created_at < end)
    ):
        counts[product_id] += quantity
        names[product_id] = product_name
        quantities += quantity

    days = []
    cursor = start_date
    while cursor <= end_date:
        days.append({"date": cursor.isoformat(), "orders": by_day[cursor.isoformat()]})
        cursor += timedelta(days=1)

    return {
        "source": "PostgreSQL orders and order_items; not website view/search events",
        "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        "total_orders": len(orders), "unique_buyers": len(buyers),
        "repeat_buyers": sum(1 for count in buyers.values() if count > 1),
        "total_units": quantities, "orders_using_coupons": coupons,
        "average_units_per_order": round(quantities/len(orders),2) if orders else 0,
        "orders_by_status": dict(by_status), "orders_by_payment_method": dict(by_payment),
        "daily_orders": days,
        "top_products": [{"product_id": pid, "name": names[pid], "units": units}
                         for pid,units in counts.most_common(10)],
    }
