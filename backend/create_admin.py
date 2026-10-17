"""Local Staff/Admin provisioning. Defaults to Staff; never a public API."""

import argparse
import getpass
import sys
import warnings


class AdminCreationError(Exception):
    """A safe, user-facing reason for refusing account creation."""


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--role", choices=("staff", "admin"), default="staff",
        help="Vai trò tài khoản mới (mặc định: staff; chọn admin tường minh nếu cần)",
    )
    args = parser.parse_args(argv)
    role_name = args.role

    try:
        from pydantic import ValidationError
        from sqlalchemy import func, select
        from sqlalchemy.exc import IntegrityError

        from app.schemas.auth import RegisterRequest

        print(f"Tạo tài khoản mới với vai trò: {role_name}")
        email = input("Email tài khoản mới: ").strip().lower()
        full_name = input("Họ tên: ").strip()
        # Fail closed if the terminal cannot hide input; never fall back to echo.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Mật khẩu (nhập ẩn): ")
            confirmation = getpass.getpass("Nhập lại mật khẩu (nhập ẩn): ")
        if password != confirmation:
            raise AdminCreationError("Hai lần nhập mật khẩu không khớp; chưa tạo tài khoản.")
        if "\x00" in full_name:
            raise AdminCreationError("Họ tên không được chứa ký tự NUL.")

        try:
            data = RegisterRequest(email=email, full_name=full_name, password=password)
        except ValidationError as exc:
            # Never render ValidationError: its input data can contain passwords.
            fields = sorted({str(error["loc"][0]) for error in exc.errors(include_input=False)})
            raise AdminCreationError(
                "Dữ liệu không hợp lệ ở trường: " + ", ".join(fields)
                + ". Email cần hợp lệ; họ tên 2–150 ký tự; mật khẩu 8–128 ký tự."
            ) from None

        # Import configuration only during an explicit manual execution.
        from app.core.database import SessionLocal
        from app.core.security import hash_password
        from app.models import Role, User

        try:
            with SessionLocal() as db:
                # Context manager commits on success and rolls back on any error.
                with db.begin():
                    existing = db.scalar(select(User.id).where(
                        func.lower(User.email) == str(data.email).lower()
                    ))
                    if existing is not None:
                        raise AdminCreationError(
                            "Email đã tồn tại; không đổi quyền hoặc mật khẩu tài khoản đó."
                        )
                    role = db.scalar(select(Role).where(Role.name == role_name).with_for_update(read=True))
                    if role is None:
                        raise AdminCreationError(
                            f"Chưa có role {role_name} trong database; dừng, không tự seed role."
                        )
                    db.add(User(
                        full_name=data.full_name,
                        email=str(data.email).lower(),
                        phone=None,
                        password_hash=hash_password(data.password),
                        role_id=role.id,
                        is_active=True,
                    ))
                    db.flush()
        except IntegrityError:
            raise AdminCreationError(
                "Không thể tạo tài khoản do xung đột dữ liệu; transaction đã rollback."
            ) from None

        print(f"Đã tạo tài khoản {role_name} mới. Có thể đăng nhập qua POST /auth/login.")
        return 0
    except AdminCreationError as exc:
        print(str(exc), file=sys.stderr)
    except getpass.GetPassWarning:
        print("Terminal không hỗ trợ nhập ẩn; đã dừng. Hãy chạy trực tiếp trong PowerShell.", file=sys.stderr)
    except (KeyboardInterrupt, EOFError):
        print("Đã hủy thao tác tạo tài khoản.", file=sys.stderr)
    except Exception:
        # No traceback/driver messages: they may contain connection details or SQL parameters.
        print("Không thể tạo tài khoản. Kiểm tra dependency, cấu hình Backend và database; không có chi tiết nhạy cảm được xuất ra.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
