# Cập nhật hồ sơ qua session hiện có

## API

`PATCH /auth/me` dùng cookie `lumiere_session` và `get_current_user()` hiện có.
Không nhận ID người dùng từ request. Chỉ cập nhật tài khoản đang đăng nhập và
đang active; không cung cấp chức năng chỉnh sửa người dùng khác.

```json
{"full_name": "Nguyễn Văn An", "phone": "0912345678"}
```

HTTP 200:

```json
{
  "id": 1,
  "full_name": "Nguyễn Văn An",
  "email": "customer@example.com",
  "phone": "0912345678",
  "role": "customer"
}
```

Đây là ví dụ hợp đồng, không phải tài khoản được tạo trong PostgreSQL.
GET /auth/me giữ các trường cũ và trả thêm phone để đọc lại hồ sơ.
Browser phải gửi cookie, ví dụ fetch với `credentials: 'include'`.

## Quy tắc

- Có thể gửi một hoặc cả hai trường full_name, phone. Trường bỏ qua giữ nguyên.
- full_name không được null; từ 2 đến 150 ký tự, gộp khoảng trắng như đăng ký,
  kiểm tra lại độ dài tối thiểu sau chuẩn hóa và từ chối ký tự NUL.
- phone theo quy tắc đăng ký hiện có: 10 chữ số ASCII, bắt đầu bằng 0, bỏ khoảng
  trắng hai đầu. Gửi null, chuỗi rỗng hoặc toàn khoảng trắng để xóa phone.
- Body rỗng, giá trị sai hoặc trường ngoài allowlist trả HTTP 422; không cập nhật
  một phần khi có lỗi. Các trường role, role_id, email, password, password_hash,
  is_active, user_id, id và mọi trường khác đều bị từ chối, không âm thầm bỏ qua.
- Thiếu cookie, cookie sai/hết hạn, user không còn tồn tại hoặc inactive: HTTP 401
  theo get_current_user hiện có. Không thay đổi thời hạn/giá trị session.
- Lỗi lưu DB: rollback, HTTP 500 với thông báo chung; không trả chi tiết driver.
- Response chỉ chứa id, full_name, email, phone, role; không trả hash mật khẩu,
  token session hoặc thông tin nội bộ database.
- Không thêm phân quyền mới theo role: người dùng active đã đăng nhập chỉ sửa
  hồ sơ của chính mình. Không có API quản trị chỉnh hồ sơ người khác.

## Phạm vi thay đổi và kiểm tra Auth

User đã có full_name VARCHAR(150) NOT NULL và phone VARCHAR(20) nullable,
nên không cần thay đổi model hay migration. UserSession đã liên kết user_id,
token_hash và expires_at. Tiếp tục dùng get_db/SessionLocal, pwdlib để kiểm tra
mật khẩu và session token SHA-256 hiện có; không tạo hệ thống xác thực mới.
Không đổi register/login/logout, Catalog, database.py hoặc .env.

Các giới hạn Auth đang có được giữ nguyên: cookie secure=False phục vụ localhost;
chưa thấy cơ chế CSRF token và rate limiting trong mã Auth hiện tại. Bước này
không triển khai các hạng mục đó. Chưa kiểm thử tích hợp trên PostgreSQL thật.

## Kiểm thử

Từ D:\DATN:

```powershell
.\.venv\Scripts\python.exe -B backend/tests/test_auth_profile.py
.\.venv\Scripts\python.exe -B backend/tests/test_catalog_api.py
```

Test hồ sơ gọi FastAPI qua ASGI, dùng cookie thật và get_current_user thật;
chỉ override get_db bằng SQLite trong bộ nhớ. Chặn mọi kết nối PostgreSQL và
không đọc .env. Tạo/xóa fixture chỉ trong bộ nhớ. Vì SQLite không giữ timezone,
test khôi phục UTC khi load session; không thay đổi model hoặc code production.

Bao gồm cập nhật thành công, PATCH từng trường/xóa phone, không sửa tài khoản
khác, session lỗi/hết hạn, inactive/deleted user, dữ liệu không hợp lệ, mass
assignment, rollback và luồng register → login → PATCH → logout.
