# Wishlist và Product Reviews

Phạm vi chỉ gồm danh sách yêu thích và đánh giá sản phẩm của Customer.
Không thay đổi Orders, COD/VNPay, ProductID, SKU, barcode, giá hoặc tồn kho.

## Trạng thái đã xác nhận ngày 17/10/2026

- Theo xác nhận của người dùng, PostgreSQL thật đã áp dụng `20261017_0005`.
- Wishlist và Product Reviews đã kiểm thử thành công qua Swagger trên PostgreSQL thật.
- Sau đó hai DELETE đổi từ 204 sang **200 kèm JSON message** như tài liệu này;
  automated tests liên quan **20/20 PASS**, nhưng **chưa kiểm thử Swagger lại sau thay đổi DELETE**.
- Backend local dùng cổng **8001**. Đây là thông tin do người dùng xác nhận;
  lần đồng bộ tài liệu này không truy cập database hoặc chạy lại tests/Swagger.

## API và quyền truy cập

| Method / Path | Quyền | Response thành công |
| --- | --- | --- |
| GET /wishlist | Customer hoạt động | 200, danh sách phân trang |
| POST /wishlist/items | Customer hoạt động | 200, item mới hoặc item đã tồn tại |
| DELETE /wishlist/items/{product_id} | Customer hoạt động | 200, JSON thông báo thành công |
| GET /products/{product_id}/reviews | Công khai, mọi role/Guest | 200, danh sách phân trang |
| GET /reviews/my | Customer hoạt động | 200, đánh giá của chính mình |
| POST /products/{product_id}/reviews | Customer hoạt động, đủ điều kiện đã mua | 201, đánh giá |
| PATCH /reviews/{id} | Customer sở hữu đánh giá | 200, đánh giá sau cập nhật |
| DELETE /reviews/{id} | Customer sở hữu đánh giá | 200, JSON thông báo thành công |

Route Customer: Guest/session sai hoặc hết hạn/tài khoản bị khóa nhận 401;
Staff/Admin nhận 403. Lấy user_id từ session, không nhận từ request.
GET công khai không yêu cầu session; chỉ trả thông tin công khai, không thao tác tài khoản.

Các danh sách nhận `page=1`, `page_size=20`, tối đa 100/trang; sắp xếp ID giảm dần,
trả `{items, page, page_size, total}`. Tham số sai hoặc trường body ngoài allowlist nhận 422.

## Wishlist

Request POST:

```json
{"product_id": 1}
```

ProductID phải là số nguyên dương PostgreSQL Integer; từ chối bool/float/string.
Sản phẩm không tồn tại nhận 404. Mỗi Customer chỉ có một item cho mỗi ProductID;
thêm lại trả cùng item, không tăng số lượng. Các thao tác ghi khóa user trước và có
UNIQUE(user_id, product_id) tại database để bảo vệ yêu cầu đồng thời.

Item gồm `id`, `created_at` và `product`. `product` dùng schema Catalog công khai hiện có:
ID/SKU/barcode/tên, các phân loại, weight, price_vnd (chuỗi Decimal) và stock.
Không trả giá vốn/giá sỉ. Giá/tồn kho được đọc hiện tại, không snapshot.
DELETE dùng **ProductID**, không phải id của wishlist item; chỉ xóa item của chính mình.
Không có item của mình hoặc sản phẩm không tồn tại nhận 404.

DELETE thành công trả HTTP 200:

```json
{"message": "Đã xóa sản phẩm khỏi danh sách yêu thích"}
```

## Reviews

Request tạo:

```json
{"rating": 5, "comment": "Sản phẩm đẹp"}
```

- Rating là số nguyên 1–5; từ chối bool/float/string.
- Comment bắt buộc, bỏ khoảng trắng đầu/cuối, dài 1–2000 ký tự sau trim;
  từ chối ký tự NUL không tương thích PostgreSQL.
- Chỉ Customer có Order của chính mình chứa đúng ProductID, `status=delivered`
  và `payment_status=paid`, mới được tạo. Kiểm tra từ Order/OrderItem trong database,
  không tin order_id/user_id/cờ đã mua từ client. Thiếu điều kiện nhận 403 kèm thông báo.
- Một Customer chỉ có một đánh giá cho sản phẩm, dù mua nhiều lần; gửi trùng nhận 409.
- Sản phẩm không tồn tại nhận 404. Sửa/xóa đánh giá không tồn tại hoặc của người khác nhận 404.
- PATCH nhận rating và/hoặc comment; từ chối body rỗng, null và các trường khác.
- Không xét lại điều kiện mua khi sửa/xóa đánh giá đã có; không tự xóa nếu đơn sau đó refunded.
- Comment là văn bản không đáng tin cậy. API giữ nguyên nội dung sau trim, không diễn giải HTML.
  Bên hiển thị phải render dưới dạng text, không đưa trực tiếp vào HTML.

Response đánh giá chỉ gồm:

```json
{
  "id": 1,
  "product_id": 1,
  "rating": 5,
  "comment": "Sản phẩm đẹp",
  "author_display_name": "N***",
  "created_at": "2026-10-17T00:00:00Z",
  "updated_at": "2026-10-17T00:00:00Z"
}
```

Tên hiển thị chỉ lấy ký tự đầu và che phần còn lại. Không trả email, điện thoại,
địa chỉ, user_id, order_id, password_hash hoặc session/token.

DELETE đánh giá thành công trả HTTP 200:

```json
{"message": "Đã xóa đánh giá thành công"}
```

## Migration — đã áp dụng tới 20261017_0005

Head trước bước này đã được kiểm tra bằng Alembic: `20261016_0004`.
Revision mới: `20261017_0005`, nối sau `20261016_0004`.

Migration chỉ tạo `wishlist_items`, `product_reviews`, index ProductID,
UNIQUE(user_id, product_id), khóa ngoại RESTRICT tới users/products và CHECK rating/comment.
Unique index bắt đầu bằng user_id cũng phục vụ truy vấn theo user.
Không sửa các bảng hoặc dữ liệu cũ. Downgrade bị chặn để tránh mất nội dung Customer.
**Người dùng đã xác nhận migration này được áp dụng trên PostgreSQL thật.**

Lệnh tham khảo để kiểm tra version (current kết nối database, chỉ đọc):

```powershell
Set-Location D:\DATN\backend
..\.venv\Scripts\python.exe -m alembic heads
..\.venv\Scripts\python.exe -m alembic current
```

Trên môi trường đã xác nhận, `heads` và `current` dự kiến đều là `20261017_0005`.
Không cần chạy lại upgrade cho database hiện tại. Nếu khác dự kiến hoặc có nhiều head,
dừng để kiểm tra, không tự stamp/reset/drop bảng.

Xuất SQL của riêng bước mới để đọc trước (không ghi database):

```powershell
..\.venv\Scripts\python.exe -m alembic upgrade 20261016_0004:20261017_0005 --sql
```

Chỉ dành cho môi trường khác còn ở revision 20261016_0004, sau khi kiểm tra/sao lưu và duyệt:

```powershell
..\.venv\Scripts\python.exe -m alembic upgrade 20261017_0005
..\.venv\Scripts\python.exe -m alembic current
```

Current sau áp dụng phải là `20261017_0005`. Không cần import lại sản phẩm.
Các lệnh này dùng cấu hình database hiện có, không cần đưa secret lên dòng lệnh/chat.

## Swagger local — cổng 8001

```powershell
Set-Location D:\DATN\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

1. Mở http://localhost:8001/docs. Đọc `GET /products/1/reviews` không đăng nhập.
2. Đăng nhập Customer qua POST /auth/login trong cùng trình duyệt, không dán mật khẩu vào chat.
3. POST /wishlist/items với ProductID có thật; gọi lại hai lần để thấy cùng item.
4. GET /wishlist; thử phân trang; DELETE /wishlist/items/{product_id} rồi GET lại.
5. Chọn sản phẩm đã có trong đơn của Customer, delivered + paid, rồi POST đánh giá.
   Nếu chưa có đơn đủ điều kiện, 403 là đúng; không sửa trực tiếp trạng thái trong PostgreSQL để vượt kiểm tra.
6. GET /reviews/my, PATCH rating/comment bằng review id, GET đánh giá công khai, DELETE bằng review id.
7. Dùng Customer khác để xác minh không đọc được wishlist cá nhân và sửa/xóa review người khác nhận 404.
8. Đăng nhập Staff/Admin kiểm tra các API Customer trả 403; logout kiểm tra 401. GET đánh giá công khai vẫn dùng được.

Cần kiểm thử lại sau thay đổi: cả hai DELETE trả HTTP 200 và đúng JSON message thay vì 204;
GET lại để kiểm tra item/review đã xóa. Chưa ghi nhận lần kiểm thử Swagger mới này.

Những thao tác POST/PATCH/DELETE trên server sẽ ghi vào database cấu hình của server;
ưu tiên môi trường test riêng khi thử Swagger. Không có thao tác này được tự chạy trong bước triển khai code.

## Automated tests

Test mới dùng dữ liệu giả lập hoàn toàn trong SQLite in-memory; override get_db, cookie thật,
chặn mọi kết nối ngoài SQLite memory và chặn load_dotenv. Không cần đọc dữ liệu nguồn sản phẩm.

```powershell
Set-Location D:\DATN
.\.venv\Scripts\python.exe backend/tests/test_customer_content.py
```

Chạy regression hiện có với cùng lớp bảo vệ:

```powershell
@'
import sys, unittest
from unittest.mock import patch
import sqlalchemy as sa
sys.path.insert(0, 'backend/tests')
original = sa.engine.Engine.connect
def memory_only(engine, *args, **kwargs):
    if engine.dialect.name != 'sqlite' or engine.url.database != ':memory:':
        raise AssertionError('Only SQLite memory allowed')
    return original(engine, *args, **kwargs)
with patch.object(sa.engine.Engine, 'connect', memory_only), patch('dotenv.load_dotenv'):
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.discover('backend/tests'))
sys.exit(not result.wasSuccessful())
'@ | .\.venv\Scripts\python.exe -
```

Regression Catalog/Cart/Orders hiện có dùng dữ liệu nguồn làm fixture đọc, không thay đổi các file nguồn.
SQLite không mô phỏng được khóa dòng PostgreSQL thực tế. Test xác minh UNIQUE, thứ tự khóa
và SQL FOR UPDATE PostgreSQL offline; kiểm thử tải đồng thời thực tế cần PostgreSQL test riêng sau này.
