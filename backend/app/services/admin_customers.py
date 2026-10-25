"""Customer-only account management using existing sessions and payment rules."""

from contextlib import contextmanager
from decimal import Decimal, localcontext

from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models import Order, Role, User, UserSession
from app.schemas.auth import StaffAccountResponse
from app.services.dashboard import classify, payment_summary_query
from app.services.orders import lock_user


def customer_query():
    return select(User).join(Role, User.role_id == Role.id).where(Role.name == "customer")


def get_customer(db, customer_id, *, lock=False):
    query = customer_query().where(User.id == customer_id)
    if lock:
        query = query.with_for_update(of=User).execution_options(populate_existing=True)
    user = db.scalar(query)
    if user is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khách hàng")
    return user


def responses(db, users):
    """Batch statistics for this page only; one row per order before aggregation."""
    ids = [user.id for user in users]
    if not ids:
        return []
    counts = dict(db.execute(select(Order.user_id, func.count(Order.id)).where(
        Order.user_id.in_(ids)
    ).group_by(Order.user_id)).all())
    spent = dict.fromkeys(ids, Decimal("0.00"))
    summary = payment_summary_query().subquery()
    query = select(Order.user_id, summary).join(summary, summary.c.id == Order.id).where(
        Order.user_id.in_(ids)
    )
    with localcontext() as context:
        context.prec = 80  # Match Dashboard, including large valid Numeric amounts.
        for row in db.execute(query).mappings():
            if classify(row)[0]:
                spent[row["user_id"]] += row["total_vnd"]
    return [dict(StaffAccountResponse.model_validate(user).model_dump(),
                 order_count=counts.get(user.id, 0), total_spent_vnd=spent[user.id])
            for user in users]


def list_customers(db, page, page_size, search=None, is_active=None):
    query = customer_query()
    if search:
        # Treat SQL LIKE metacharacters as literal search text.
        text = search.replace("/", "//").replace("%", "/%").replace("_", "/_")
        pattern = "%" + text + "%"
        query = query.where(or_(*(column.ilike(pattern, escape="/")
                                 for column in (User.full_name, User.email, User.phone))))
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    users = db.scalars(query.order_by(User.id).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": responses(db, users), "total": total, "page": page, "page_size": page_size}


def customer_detail(db, customer_id):
    return responses(db, [get_customer(db, customer_id)])[0]


@contextmanager
def customer_write(db, actor_id):
    try:
        lock_user(db, actor_id, "admin")
        yield
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dữ liệu khách hàng xung đột") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Không thể cập nhật khách hàng") from None
    except Exception:
        db.rollback()
        raise


def set_customer_status(db, actor_id, customer_id, active):
    with customer_write(db, actor_id):
        # Login also locks this User before checking active and creating a session.
        target = get_customer(db, customer_id, lock=True)
        target.is_active = active
        if not active:
            db.execute(delete(UserSession).where(UserSession.user_id == target.id))
        db.flush()
        result = responses(db, [target])[0]
    return result
