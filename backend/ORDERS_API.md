# Đặt hàng và quản lý đơn LUMIÈRE

## Phạm vi và các giả định cần duyệt

Code hiện có products.stock Integer, NOT NULL, CHECK stock >= 0. Không cần thêm
cột hoặc sửa bảng products. Chưa đọc database thật: kết luận dựa trên model,
migration và trạng thái bạn đã cung cấp. Theo xác nhận ngày 17/10/2026,
PostgreSQL thật đã ở `20261017_0005`, bao gồm migration Orders `20261016_0003`.

- Chỉ role customer được đặt hàng và xem /orders/my. Admin giữ các API /admin/.
  Staff và Admin quản lý đơn qua /staff/orders. /orders/{id} vẫn chỉ cho chủ đơn
  hoặc Admin; Staff dùng endpoint chi tiết riêng với response giới hạn.
- Đặt toàn bộ item trong giỏ, không chọn một phần, không nhận danh sách item hay
  giá từ client. Không sửa thông tin giao hàng sau khi đặt ở bước này.
- Đơn bắt đầu pending, payment_status=unpaid. Chưa có gateway, callback, tự đánh
  dấu đã thanh toán hoặc refund. Hoàn kho KHÔNG đồng nghĩa hoàn tiền.
- shipping_vnd=0 và discount_vnd=0 là chính sách tạm thời, CHƯA tích hợp báo phí
  giao hàng, thuế hoặc coupon. Tổng tiền hiện bằng tổng giá bán các item. Cần
  xác nhận chính sách giá/thuế/phí này trước triển khai; không quảng bá là phí
  giao hàng thực tế. Không nhận các khoản này từ frontend.
- Staff/Admin hủy đơn chưa thanh toán ở pending/confirmed. Không có endpoint khách
  tự hủy, không hủy khi packing trở đi, không xử lý hoàn hàng sau giao.
- Gửi lại cùng trạng thái là no-op 200. Gửi lại cancelled không hoàn kho lần hai.
- Không có idempotency key riêng cho POST. Hai checkout cùng giỏ được tuần tự
  hóa, lần sau thấy giỏ rỗng sẽ lỗi. Nếu client mất response, kiểm tra /orders/my
  trước khi đặt lại; giỏ được thêm hàng lại có thể tạo một đơn mới.

## Models và migration

`orders`: id, code duy nhất, user_id FK users.id RESTRICT, snapshot người nhận/
phone/address, status, payment_status, stock_restored, subtotal/shipping/discount/
total, created_at và updated_at. Tiền tổng dùng Numeric(38,2) để chứa tổng nhiều
item. Thời gian do database sinh, updated_at được ORM cập nhật khi trạng thái đổi.

`order_items`: order_id và product_id FK RESTRICT, snapshot SKU/product_name,
quantity, unit_price_vnd Numeric(18,2), line_total_vnd Numeric(38,2).
UNIQUE(order_id,product_id), quantity>0 và line_total=unit_price*quantity.
Không đọc lại tên/giá hiện tại của product để ghi đè snapshot khi xem lịch sử.
RESTRICT chủ động giữ lịch sử khi ai đó định xóa tài khoản/sản phẩm/đơn.

Revision `20261016_0003` nối `20261016_0002`: chỉ tạo orders, order_items và index,
không sửa bảng/dữ liệu cũ. Downgrade bị chặn để tránh mất lịch sử và sai hoàn kho.

## API — Business API cổng 8001

Tất cả dùng cookie lumiere_session và get_current_user hiện có. Không tin user_id
hoặc role trong request. JSON ngoài schema bị từ chối, không âm thầm bỏ qua.

POST /orders (201), body:

```json
{
  "recipient_name": "Nguyễn Văn An",
  "phone": "0912345678",
  "address": "123 Đường Nguyễn Huệ, TP HCM"
}
```

Tên 2..150 ký tự, địa chỉ 5..1000 ký tự; gộp khoảng trắng, cấm NUL, kiểm tra lại
độ dài sau chuẩn hóa. Phone theo Auth: 10 chữ số ASCII bắt đầu bằng 0, bắt buộc.

POST và GET /orders/{id} trả OrderResponse gồm:

```text
id, code, user_id, status, payment_status,
recipient_name, phone, address,
subtotal_vnd, shipping_vnd, discount_vnd, total_vnd,
created_at, updated_at,
items: [{id, product_id, sku, product_name, quantity, unit_price_vnd, line_total_vnd}]
```

Tiền là chuỗi Decimal trong JSON, đơn vị VND; không float. Không trả giá vốn,
giá sỉ, mật khẩu hoặc token. ProductID vẫn là ID gốc.

GET /orders/my và GET /admin/orders trả:

```text
{items: [OrderSummary], page: 1, page_size: 20, total: ...}
```

OrderSummary gồm thông tin ID/code/user/status/payment/tổng tiền/thời gian, không
gồm địa chỉ giao hàng hoặc item. page>=1, page_size=1..100; mặc định 1/20; sắp xếp
orders.id DESC ổn định. /my được khai báo trước /{id} để không bị hiểu là ID.

PATCH /admin/orders/{id}/status (200), body:

```json
{"status": "confirmed"}
```

Luồng hợp lệ:

```text
pending -> confirmed -> packing -> shipping -> delivered
pending/confirmed -> cancelled
```

Không nhảy bước/quay ngược; delivered và cancelled là trạng thái kết thúc.
Không thể sửa payment_status qua API status. Chuyển sang delivered không tự
đánh dấu paid; việc xác nhận thanh toán dùng module Payment riêng.

## Staff Orders

| API | Quyền |
|---|---|
| GET /staff/orders | Staff và Admin, danh sách toàn hệ thống |
| GET /staff/orders/{id} | Staff và Admin, chi tiết xử lý đơn |
| PATCH /staff/orders/{id}/status | Staff và Admin, body {"status":"confirmed"} |

Customer nhận 403, chưa đăng nhập nhận 401. Phân trang dùng cùng quy tắc 1/20,
tối đa 100 mỗi trang, ID giảm dần. Không có phân công đơn theo nhân viên ở bước
này. Detail/update trả StaffOrderResponse: thông tin đơn, item snapshot và tên/
số điện thoại/địa chỉ người nhận; không trả user_id, email, role hoặc thông tin
xác thực khách hàng. Danh sách cũng bỏ user_id và không trả địa chỉ giao hàng.

Tái sử dụng list_orders, order_query và change_status, không tách bản sao state
machine. Service kiểm tra Staff/Admin lại trong transaction khi endpoint Staff
gọi; mặc định service vẫn chỉ cho Admin để giữ nguyên route /admin/ hiện có.
Các giới hạn hủy, hoàn kho một lần, chặn hủy giao dịch chưa rõ và chặn xử lý đơn
VNPay chưa paid được giữ nguyên. Hủy có thể hoàn kho theo nghiệp vụ Orders;
không bổ sung quyền hoặc API điều chỉnh kho thủ công cho Staff.

Staff có thể chuyển COD sang delivered; việc chuyển trạng thái không tự xác
nhận thu tiền. Staff/Admin xác nhận thủ công qua POST /staff/orders/{id}/cod/confirm;
POST /admin/orders/{id}/cod/confirm vẫn chỉ Admin. Không thay đổi các route
customer, callback VNPay, Auth hoặc Catalog. Không cần đổi schema/migration.

Test Staff được thêm trực tiếp vào tests/test_orders_api.py, gồm 401/403,
Staff/Admin được phép, response giới hạn, phân trang, 404/422, chuyển trạng thái,
hủy lặp, rollback và không vượt quyền COD/payment. Chạy cùng lệnh test Orders
ở phần cuối tài liệu. Tất cả dùng database bộ nhớ; không truy cập PostgreSQL thật.

HTTP lỗi: 401 chưa đăng nhập/session lỗi; 403 sai role; 404 đơn không tồn tại hoặc
không thuộc user; 409 giỏ rỗng/thiếu hàng/sản phẩm mất/chuyển trạng thái sai/hủy
đơn đã trả tiền/hoàn kho tràn Integer; 422 request sai; 500 lỗi database chung.
Không trả thông tin SQL/driver nội bộ. Không có route /orders/me ở bước này:
frontend phải thống nhất dùng /orders/my theo yêu cầu mới nhất.

## Transaction và concurrency

Checkout dùng cùng Session đã được Auth mở transaction, không lồng db.begin():

1. Khóa users.id FOR UPDATE, dùng chung khóa đầu tiên với Cart để chặn thêm/sửa
   giỏ trong lúc checkout và tuần tự hóa hai checkout cùng user.
2. Đọc giỏ, khóa cart_items; từ chối giỏ rỗng.
3. Khóa các products FOR UPDATE theo ID tăng dần; đọc lại stock và giá hiện tại.
4. Kiểm tra tất cả item, tính tiền Decimal precision 50, tạo snapshots, giảm stock,
   tạo order/items và xóa đúng các cart item vừa đặt.
5. Flush, dựng response đã validate trước commit; bất kỳ lỗi nào rollback tất cả.

Hủy đơn khóa user Staff/Admin, rồi order FOR UPDATE để đọc lại trạng thái. Nếu được
hủy, khóa products theo ID tăng dần; cộng lại quantity snapshot đúng một lần và
ghi status=cancelled, stock_restored=true trong cùng transaction. Constraint
orders ràng buộc cancelled với stock_restored. Retry sau commit không hoàn tiếp.
Nếu một product có nguy cơ tràn Integer, rollback cả lượt, kể cả các product đã
được điều chỉnh trong bộ nhớ/flush. Không khôi phục cart item khi hủy.

Đơn khác nhau mua cùng hàng phải chờ cùng khóa sản phẩm rồi kiểm tra tồn kho
mới nhất trên PostgreSQL READ COMMITTED mặc định. Thứ tự khóa products ổn định
giảm deadlock. Mọi code ghi kho/checkout/payment sau này phải tuân thủ chiến lược
khóa và cập nhật trong transaction; không ghi SQL tùy tiện ngoài cơ chế này.
Lỗi DB không tự retry POST. Chưa có lock timeout riêng hoặc audit lịch sử chuyển
trạng thái/người thao tác. Đây là các hạng mục cần xem xét trước triển khai thật.

## Migration Orders — tham khảo cho môi trường mới

Database hiện tại đã áp dụng đến 20261017_0005 theo xác nhận của người dùng.
Các bước nâng từ 0002 lên 0003 dưới đây không cần chạy lại trên database hiện tại.

Từ D:\DATN, xem head và SQL riêng revision mới, không kết nối DB:

```powershell
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini heads
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini upgrade 20261016_0002:20261016_0003 --sql
```

Sau khi được phép, kiểm tra current (chỉ đọc), đúng database lumiere_db, sao lưu
và xác nhận không có bảng orders/order_items trùng tên với cấu trúc khác.
Current phải là 20261016_0002. Không stamp để bỏ qua migration chưa áp dụng.
CHỈ sau khi duyệt thao tác thay đổi DB mới chạy:

```powershell
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini upgrade 20261016_0003
```

Các điều kiện current=0002 ở trên chỉ dành cho môi trường khác chưa có Orders.
Trên database hiện tại, current dự kiến 20261017_0005; không stamp/reset để quay về revision cũ.
Lần cập nhật tài liệu này không chạy các lệnh trên.

## Test

Từ D:\DATN:

```powershell
.\.venv\Scripts\python.exe -B backend/tests/test_orders_api.py
.\.venv\Scripts\python.exe -B backend/tests/test_catalog_api.py
.\.venv\Scripts\python.exe -B backend/tests/test_import_catalog.py
```

Order suite kế thừa test Cart/Auth. Mọi test dùng SQLite trong bộ nhớ, bật FK,
override get_db và chặn kết nối PostgreSQL; không đọc .env. Kiểm tra checkout,
snapshot, giá, tồn kho, rollback, phân quyền/list, hủy, lặp hủy, chuyển trạng thái,
validation, SQL khóa PostgreSQL và migration offline. Bài test hai khách mua
hàng lần lượt kiểm tra đọc lại tồn kho, KHÔNG chứng minh concurrency thực tế.

Chưa kiểm thử concurrency, deadlock, Decimal/constraint trên PostgreSQL test thật.
SQLite không mô phỏng row lock và Numeric của PostgreSQL đầy đủ. Trước triển
khai cần một database PostgreSQL test riêng được cho phép, không dùng database
500 sản phẩm hiện tại. Auth hiện còn thiếu CSRF token, rate limit và Secure
cookie production như các bước trước; không đổi hệ thống Auth trong bước này.
