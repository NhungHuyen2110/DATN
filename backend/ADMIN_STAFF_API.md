# Admin quản lý tài khoản Staff

## Phạm vi

Chỉ Admin đã đăng nhập và active. Staff/Customer active nhận 403; thiếu session,
session hết hạn/bị thu hồi hoặc user inactive nhận 401. Không có API xóa tài khoản.
Không đổi role, email, mật khẩu của tài khoản đã tồn tại. Không sửa schema hoặc
migration; dùng User, Role và UserSession hiện có.

| API | Nội dung |
|---|---|
| GET /admin/staff | Danh sách Staff, gồm cả inactive, phân trang |
| GET /admin/staff/{id} | Chi tiết Staff |
| POST /admin/staff | Tạo Staff mới, HTTP 201 |
| PATCH /admin/staff/{id} | Chỉ full_name, phone |
| PATCH /admin/staff/{id}/status | Chỉ is_active (bool thật) |

Endpoint đích chỉ truy vấn Role.name='staff'. ID Customer/Admin/không tồn tại
đều trả 404 cho GET/PATCH/status. ID đường dẫn phải nguyên dương. GET danh sách
page=1, page_size=20 mặc định; page_size tối đa 100, sắp xếp User.id ASC. Response:

```text
{items: [StaffAccountResponse], page, page_size, total}
```

StaffAccountResponse chỉ gồm id, full_name, email, phone, is_active, created_at.
GET detail/POST/PATCH/status trả trực tiếp đối tượng này. Không trả password_hash,
session token, role_id hoặc thông tin kết nối.

## Tạo và cập nhật

POST nhận full_name, email, password và phone tùy chọn. Nhập mật khẩu do bạn tự
chọn trực tiếp trên Swagger HTTPS/local test, không ghi vào code/chat/log. Schema
dùng SecretStr, tái sử dụng validator đăng ký hiện có; chỉ router quản lý Staff
lọc input/ctx khỏi lỗi validation để tránh phản chiếu mật khẩu trong response.
Không thay đổi xử lý lỗi của các endpoint cũ.

Email được trim/lowercase; kiểm tra trùng không phân biệt hoa thường với mọi role.
Database UNIQUE(email) bảo vệ các yêu cầu đồng thời đã chuẩn hóa. IntegrityError
trả 409 và rollback, không ghi đè user cũ. Hash bằng hash_password hiện có. Role
luôn tìm theo name='staff', không nhận role/ID/is_active/password_hash từ client.
Nếu role chưa có, trả 409, không tự tạo. User mới mặc định active.

PATCH nhận một hoặc hai trường full_name/phone, bỏ qua giữ nguyên, null/chuỗi rỗng
phone để xóa phone. Body rỗng hoặc trường cấm trả 422. Không có đổi email/reset
mật khẩu. Tên/phone tuân theo ProfileUpdateRequest hiện có.

Status body:

```json
{"is_active": false}
```

Không nhận 0/1/chuỗi thay bool. Trong cùng transaction, khóa Admin rồi Staff,
đặt is_active và xóa toàn bộ UserSession của Staff nếu inactive. Gọi disable lặp
cũng xóa session còn sót. Enable không tạo/khôi phục session; nhân viên phải đăng
nhập mới. Không tác động session của user khác. Lỗi lưu rollback cả trạng thái
và việc xóa session. API status không xóa user, giữ nguyên các liên kết Orders/COD.

Login hiện có được bổ sung FOR UPDATE trên dòng User trong transaction tạo
session để tuần tự hóa với disable. Nếu login hoàn thành trước, disable sẽ thu
hồi session đó; nếu disable hoàn thành trước, login đọc inactive và từ chối.
Không đổi đường dẫn, request/response, hash hoặc cookie Auth. Những request đã
được xác thực trước khi khóa có thể đã thực hiện công việc; không phải cơ chế
chấm dứt tức thì mọi request đang chạy. Thao tác ghi Orders/COD/kho đã có kiểm
tra lại actor dưới khóa riêng.

## Test và giới hạn

Từ D:\DATN:

```powershell
.\.venv\Scripts\python.exe -B backend/tests/test_admin_staff.py
.\.venv\Scripts\python.exe -B backend/tests/test_auth_profile.py
.\.venv\Scripts\python.exe -B backend/tests/test_orders_api.py
.\.venv\Scripts\python.exe -B backend/tests/test_payments_api.py
```

Suite Staff kế thừa Orders/Cart/Auth; override get_db bằng SQLite trong bộ nhớ,
chặn kết nối PostgreSQL và không đọc .env. Test tạo/đọc/cập nhật/status, phân
quyền, giới hạn mục tiêu, email trùng, lỗi unique mô phỏng race, validation,
không lộ mật khẩu, rollback session và SQL khóa login. Không chứng minh concurrency
thực tế trên PostgreSQL; cần database test riêng nếu muốn xác minh sau này.

Chưa bổ sung bảng audit ai sửa Staff/lý do khóa. Không có migration hay seed.
CSRF/rate limiting/Secure cookie production là các hạng mục Auth còn tồn tại từ
trước; phạm vi này không triển khai các hạng mục đó.

## Kiểm thử Swagger sau khi bạn quyết định chạy API

1. Dùng database test riêng; mở http://localhost:8001/docs.
2. Đăng nhập Admin hiện có qua POST /auth/login, xác nhận GET /auth/me role admin.
3. Tạo tài khoản Staff mới qua POST /admin/staff bằng email chưa sử dụng và mật
   khẩu tự nhập; kiểm tra response không chứa password/hash.
4. Dùng ID trả về để GET detail, PATCH tên/phone và xem danh sách phân trang.
5. Mở trình duyệt/profile khác đăng nhập Staff; xác nhận không vào được /admin/staff.
6. Ở profile Admin, PATCH status false. Profile Staff gọi lại API phải nhận 401.
7. Admin bật true; cookie cũ vẫn 401, Staff phải đăng nhập lại để có session mới.

Các thao tác Swagger trên sẽ ghi DB của server đang chạy; chưa thực hiện ở bước
triển khai này. Không dùng tài khoản/sản phẩm vận hành thật làm fixture.
