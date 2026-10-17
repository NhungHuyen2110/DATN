# Alembic cho Backend LUMIÈRE

## Trạng thái

Theo xác nhận của người dùng ngày 17/10/2026, PostgreSQL thật đã áp dụng đến
`20261017_0005`. Không cần chạy lại các migration cũ trên môi trường này.
File `backend/requirements-migrations.txt` khai báo dependency cho môi trường mới.
Lần cập nhật tài liệu này không kết nối database để kiểm chứng lại.

Lịch sử hiện có: `20261015_0001` (tài khoản/catalog) → `20261016_0002` (Cart)
→ `20261016_0003` (Orders) → `20261016_0004` (Payments)
→ `20261017_0005` (Wishlist/Reviews).

`env.py` dùng `Base.metadata`, `DATABASE_URL` và `engine` từ
`app.core.database`; import `app.models` để đăng ký toàn bộ model hiện hành.
Không đặt URL hoặc mật khẩu trong `alembic.ini` hay migration.
Không sửa `database.py`, `.env`, model hoặc chức năng tài khoản.

## Revision đầu tiên

- Tạo các bảng còn thiếu: `roles`, `users`, `user_sessions`, `categories`,
  `brands`, `materials`, `gemstones`, `collections`, `products`.
- Alembic tự quản lý thêm bảng `alembic_version` để ghi revision đã áp dụng.
- Giữ nguyên cấu trúc của 9 model tại thời điểm tạo revision. Revision không
  import model hiện hành để tránh lịch sử migration thay đổi theo model tương lai.
- Giữ ID catalog tường minh, Numeric cho giá, khóa ngoại, chỉ mục, unique và check.
- Chế độ online kiểm tra bảng đã có trước khi tạo bảng ứng dụng: cột, kiểu dữ liệu,
  nullable, khóa chính, unique, chỉ mục, khóa ngoại và check bắt buộc.
  Nếu cấu trúc không phù hợp, dừng để kiểm tra thủ công; không tự sửa bảng.
  Đây không phải công cụ đối chiếu mọi thuộc tính PostgreSQL (trigger, quyền,
  constraint bổ sung, v.v.). Cần kiểm tra database thật trước khi áp dụng.
- Không chứa thao tác xóa bảng, xóa cột hoặc thay đổi dữ liệu ứng dụng.
- `downgrade()` chủ động báo lỗi để tránh xóa cả bảng tài khoản có sẵn.
- Không seed role hay sản phẩm. Database mới cần seed các role
  `customer`, `staff`, `admin` trong bước được duyệt riêng trước khi đăng ký.
  Không chạy `app.init_db` để thay thế migration.

## Lệnh tham khảo (PowerShell, từ D:\DATN)

Cài dependency khi được phép:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-migrations.txt
```

Kiểm tra lịch sử, không cần kết nối database:

```powershell
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini heads
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini history --verbose
```

Xuất SQL ra màn hình để xem, không áp dụng lên PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini upgrade head --sql
```

Chế độ offline dùng cấu hình kết nối hiện có nhưng không mở kết nối. SQL này
mô tả toàn bộ lịch sử từ database trống, gồm cả các revision sau 0001;
không thể biết bảng nào đã tồn tại.
Không lấy SQL offline này chạy thẳng trên database đã có tài khoản.

Sau khi được phép kiểm tra database thật (các lệnh dưới chỉ đọc):

```powershell
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini current
```

Cần kiểm tra cấu trúc thực tế và sao lưu dữ liệu trước khi áp dụng. Nếu database
đã có revision không thuộc lịch sử này hoặc schema khác model, dừng để đối chiếu;
không tự chạy `stamp`, không tự xóa bảng.

CHỈ khi đã duyệt bước áp dụng migration mới chạy:

```powershell
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini upgrade head
```

Lệnh cuối sẽ thay đổi database, chỉ dùng cho môi trường còn thiếu revision đã được duyệt.
Database hiện tại đã ở 20261017_0005 theo xác nhận; current/heads dự kiến cùng revision này.
Không có lệnh migration nào được chạy trong lần đồng bộ tài liệu.
