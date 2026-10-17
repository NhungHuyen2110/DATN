"""Admin-only Staff account operations; no role changes or hard deletion."""

from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.security import hash_password
from app.models import Role, User, UserSession
from app.schemas.auth import StaffAccountResponse
from app.services.orders import lock_user


def staff_query():
    return select(User).join(Role, User.role_id == Role.id).where(Role.name == "staff")


def get_staff(db, staff_id, *, lock=False):
    query = staff_query().where(User.id == staff_id)
    if lock:
        query = query.with_for_update(of=User).execution_options(populate_existing=True)
    target = db.scalar(query)
    if target is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản Staff")
    return target


@contextmanager
def staff_write(db, actor_id):
    try:
        lock_user(db, actor_id, "admin")
        yield
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email trùng hoặc dữ liệu tài khoản xung đột") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Không thể cập nhật tài khoản Staff") from None
    except Exception:
        db.rollback()
        raise


def list_staff(db, page, page_size):
    total = db.scalar(select(func.count()).select_from(User).join(Role).where(Role.name == "staff"))
    items = db.scalars(staff_query().order_by(User.id).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": items, "page": page, "page_size": page_size, "total": total}


def response(db, target):
    db.flush()
    return StaffAccountResponse.model_validate(target).model_dump()


def create_staff(db, actor_id, request):
    with staff_write(db, actor_id):
        email = str(request.email).strip().lower()
        if db.scalar(select(User.id).where(func.lower(User.email) == email)) is not None:
            raise HTTPException(status_code=409, detail="Email đã được sử dụng")
        role = db.scalar(select(Role).where(Role.name == "staff").with_for_update(read=True))
        if role is None:
            raise HTTPException(status_code=409, detail="Chưa có role Staff; không tự tạo role")
        target = User(full_name=request.full_name, email=email, phone=request.phone,
                      password_hash=hash_password(request.password.get_secret_value()), role_id=role.id, is_active=True)
        db.add(target)
        result = response(db, target)
    return result


def update_staff(db, actor_id, staff_id, request):
    with staff_write(db, actor_id):
        target = get_staff(db, staff_id, lock=True)
        if "full_name" in request.model_fields_set:
            target.full_name = request.full_name
        if "phone" in request.model_fields_set:
            target.phone = request.phone
        result = response(db, target)
    return result


def set_staff_status(db, actor_id, staff_id, active):
    with staff_write(db, actor_id):
        target = get_staff(db, staff_id, lock=True)
        target.is_active = active
        if not active:
            db.execute(delete(UserSession).where(UserSession.user_id == target.id))
        result = response(db, target)
    return result
