"""Read-only classification shared by dashboard and confirmed-payment reports."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, localcontext
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, case, func, select

from app.models import Order, PaymentTransaction as Payment, Product
from app.schemas.dashboard import DashboardResponse, RevenueBucket, RevenueResponse


VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")
ZERO = Decimal("0.00")
ORDER_STATUSES = ("pending", "confirmed", "packing", "shipping", "delivered", "cancelled")
PAYMENT_STATUSES = ("unpaid", "paid", "refunded")


def payment_summary_query():
    # Group before joining orders; never join order_items or sum DISTINCT amounts.
    candidate = and_(
        Payment.status == "succeeded", Payment.review_required.is_(False),
        Payment.verified_at.is_not(None), Payment.amount_vnd == Order.total_vnd,
        Payment.provider == Order.payment_method,
    )
    def count_if(condition):
        return func.sum(case((condition, 1), else_=0))

    payments = select(
        Payment.order_id.label("order_id"),
        count_if(candidate).label("candidate_count"),
        count_if(Payment.status == "succeeded").label("succeeded_count"),
        count_if(Payment.review_required.is_(True)).label("review_count"),
        count_if(Payment.amount_vnd != Order.total_vnd).label("amount_mismatch"),
        count_if(Payment.provider != Order.payment_method).label("provider_mismatch"),
        count_if(and_(Payment.status == "succeeded", Payment.verified_at.is_(None))).label("missing_verified"),
        func.max(case((candidate, Payment.verified_at), else_=None)).label("verified_at"),
    ).join(Order, Order.id == Payment.order_id).group_by(Payment.order_id).subquery()
    return select(
        Order.id, Order.status, Order.payment_status, Order.total_vnd,
        *[func.coalesce(payments.c[name], 0).label(name) for name in (
            "candidate_count", "succeeded_count", "review_count", "amount_mismatch",
            "provider_mismatch", "missing_verified",
        )],
        payments.c.verified_at,
    ).outerjoin(payments, payments.c.order_id == Order.id)


def classify(row):
    """One order is eligible once or excluded with explicit reconciliation reasons."""
    reasons = []
    for field, reason in (
        ("review_count", "transaction_requires_review"),
        ("amount_mismatch", "transaction_amount_mismatch"),
        ("provider_mismatch", "transaction_provider_mismatch"),
        ("missing_verified", "successful_transaction_missing_verified_at"),
    ):
        if row[field]:
            reasons.append(reason)
    if row["candidate_count"] > 1:
        reasons.append("multiple_valid_transactions")
    if row["succeeded_count"] > 1:
        reasons.append("multiple_successful_transactions")
    if row["payment_status"] == "paid" and row["candidate_count"] != 1:
        reasons.append("paid_order_without_single_valid_transaction")
    if row["succeeded_count"] and row["payment_status"] == "unpaid":
        reasons.append("unpaid_order_with_successful_transaction")
    if row["succeeded_count"] and row["status"] == "cancelled":
        reasons.append("cancelled_order_with_successful_transaction")
    eligible = (row["payment_status"] == "paid" and row["status"] != "cancelled"
                and row["candidate_count"] == 1 and not reasons)
    return eligible, reasons


def dashboard(db):
    statuses = dict.fromkeys(ORDER_STATUSES, 0)
    payment_statuses = dict.fromkeys(PAYMENT_STATUSES, 0)
    reason_counts = {}
    total = review_count = 0
    with localcontext() as context:
        context.prec = 80
        confirmed = review_value = ZERO
        for row in db.execute(payment_summary_query()).mappings():
            total += 1
            statuses[row["status"]] += 1
            payment_statuses[row["payment_status"]] += 1
            eligible, reasons = classify(row)
            if eligible:
                confirmed += row["total_vnd"]
            if reasons:
                review_count += 1
                # Exposure measured by order value ONCE, not money assumed collected.
                review_value += row["total_vnd"]
                for reason in reasons:
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
    products, out_of_stock = db.execute(select(
        func.count(Product.id), func.coalesce(func.sum(case((Product.stock == 0, 1), else_=0)), 0)
    )).one()
    return DashboardResponse(
        total_orders=total, orders_by_status=statuses, orders_by_payment_status=payment_statuses,
        confirmed_payment_amount_vnd=confirmed, reconciliation_order_count=review_count,
        reconciliation_order_value_vnd=review_value,
        reconciliation_reasons=[{"reason": key, "order_count": value} for key, value in sorted(reason_counts.items())],
        total_products=products, out_of_stock_products=out_of_stock,
    )


def revenue(db, start_date, end_date, group_by):
    if start_date > end_date or end_date == date.max:
        raise HTTPException(status_code=422, detail="Invalid date range")
    # A bounded response prevents an accidental multi-million-day chart.
    if (end_date - start_date).days > 3660:
        raise HTTPException(status_code=422, detail="Date range must not exceed 3661 days")
    try:
        start_utc = datetime.combine(start_date, time.min, VIETNAM).astimezone(timezone.utc)
        end_utc = datetime.combine(end_date + timedelta(days=1), time.min, VIETNAM).astimezone(timezone.utc)
    except (OverflowError, ValueError):
        raise HTTPException(status_code=422, detail="Unsupported date boundary") from None
    buckets = {}
    cursor = start_date if group_by == "day" else start_date.replace(day=1)
    while cursor <= end_date:
        buckets[cursor] = RevenueBucket(period_start=cursor, confirmed_payment_amount_vnd=ZERO,
                                       confirmed_payment_order_count=0)
        if cursor == end_date or (group_by == "month" and (cursor.year, cursor.month) == (end_date.year, end_date.month)):
            break
        if group_by == "day":
            cursor += timedelta(days=1)
        else:
            cursor = date(cursor.year + cursor.month // 12, cursor.month % 12 + 1, 1)
    summary = payment_summary_query().subquery()
    query = select(summary).where(summary.c.verified_at >= start_utc, summary.c.verified_at < end_utc)
    with localcontext() as context:
        context.prec = 80
        amount, count = ZERO, 0
        for row in db.execute(query).mappings():
            if not classify(row)[0]:
                continue
            verified_at = row["verified_at"]
            if verified_at.tzinfo is None:  # SQLite fixtures; PostgreSQL uses timestamptz.
                verified_at = verified_at.replace(tzinfo=timezone.utc)
            day = verified_at.astimezone(VIETNAM).date()
            key = day if group_by == "day" else day.replace(day=1)
            buckets[key].confirmed_payment_amount_vnd += row["total_vnd"]
            buckets[key].confirmed_payment_order_count += 1
            amount += row["total_vnd"]
            count += 1
    return RevenueResponse(start_date=start_date, end_date=end_date, group_by=group_by,
        confirmed_payment_amount_vnd=amount, confirmed_payment_order_count=count, items=list(buckets.values()))
