# Giỏ hàng LUMIÈRE

## Mô hình và phạm vi

- `carts`: id tự tăng; user_id NOT NULL, UNIQUE, FK users.id ON DELETE CASCADE.
  Mỗi user chỉ có một giỏ. Tạo giỏ khi thêm sản phẩm đầu tiên thành công;
  GET giỏ chưa tồn tại trả giỏ rỗng, không ghi dữ liệu.
- `cart_items`: id tự tăng; cart_id FK carts.id ON DELETE CASCADE; product_id
  FK products.id ON DELETE RESTRICT; quantity Integer NOT NULL và > 0.
  UNIQUE(cart_id, product_id) chống item trùng. Composite unique cũng phục vụ
  truy vấn theo cart_id; thêm index product_id cho khóa ngoại.
- Không lưu giá client hoặc snapshot giá trong cart_items. Response lấy giá bán
  hiện tại từ products.sale_price, tính bằng Decimal với precision 50, không float.
- Không sửa cấu trúc users/products, không đổi ID sản phẩm, không giữ chỗ/trừ kho.
  Checkout sau này phải kiểm tra lại giá và kho trong transaction riêng.

## API (Business API cổng 8001)

Tất cả endpoint dùng get_current_user và cookie lumiere_session hiện có.
Browser cần `credentials: 'include'`. user_id/cart_id không lấy từ client.

| API | Body | Kết quả |
|---|---|---|
| GET /cart | Không | 200, giỏ của user hiện tại |
| POST /cart/items | {"product_id":1,"quantity":2} | 200, thêm mới hoặc cộng dồn |
| PATCH /cart/items/{id} | {"quantity":3} | 200, thay thế số lượng |
| DELETE /cart/items/{id} | Không | 200, giỏ sau khi xóa |

`{id}` là cart_items.id, KHÔNG phải ProductID. POST và PATCH từ chối trường
ngoài schema, bao gồm giá, user_id và cart_id. product_id/quantity trong JSON
phải là số nguyên thật từ 1 đến 2147483647; không nhận bool, float hoặc chuỗi.
PATCH không nhận product_id; xóa item bằng DELETE, không PATCH quantity=0.

Mọi API trả cùng dạng CartResponse. Ví dụ cấu trúc minh họa:

```json
{
  "id": 1,
  "items": [
    {
      "id": 1,
      "product": {"id": 1, "sku": "SP000001", "name": "Bông tai Angel", "stock": 96},
      "quantity": 2,
      "unit_price_vnd": "5597326.00",
      "line_total_vnd": "11194652.00",
      "in_stock": true
    }
  ],
  "total_quantity": 2,
  "subtotal_vnd": "11194652.00"
}
```

Tiền trong JSON là chuỗi Decimal, đơn vị VND. subtotal chưa có ship, thuế hay
giảm giá. Không trả giá vốn/giá sỉ hoặc thông tin tài khoản/session. Items tăng
dần theo cart_items.id. Giỏ chưa tạo có id=null, items=[], total_quantity=0,
subtotal_vnd="0.00". Giỏ đã xóa hết item giữ nguyên cart.id.

## Lỗi và transaction

- 401: session thiếu/sai/hết hạn, user không tồn tại hoặc inactive.
- 404: sản phẩm không tồn tại; item không tồn tại HOẶC không thuộc giỏ của user.
  Không tiết lộ sự tồn tại item người khác.
- 409: tổng số lượng sau cộng dồn/vừa cập nhật vượt tồn kho, hoặc xung đột
  integrity khi ghi. Không tự ghi đè hay tự retry một POST có thể cộng dồn.
- 422: body/path không hợp lệ hoặc trường không được phép.
- 500: lỗi DB khác, thông báo chung không chứa SQL/driver details.

Các thao tác ghi dùng cùng Session với Auth. Auth đã bắt đầu transaction nên
không gọi db.begin lồng nhau. Khóa users.id FOR UPDATE trước; đọc/tạo giỏ và
tính lại số lượng sau khi có khóa. Khi thêm/sửa, khóa products.id FOR UPDATE
trước khi kiểm tra stock. Mọi lượt ghi giỏ của cùng user đi qua cùng khóa này,
kể cả giỏ chưa tồn tại. UNIQUE là lớp bảo vệ bổ sung ở database. Các lỗi được
rollback; chỉ commit sau khi flush và dựng response thành công.

Các thao tác không giữ chỗ kho: nhiều user có thể cùng có một sản phẩm trong
giỏ. Khi kho giảm sau đó, GET vẫn trả số lượng đã lưu và in_stock=false, để user
giảm số lượng hoặc xóa. Không tự sửa giỏ khi đọc. POST/PATCH luôn kiểm tra lại kho.

Khóa chỉ có ý nghĩa khi migration được áp dụng và request chạy PostgreSQL.
Code ghi giỏ khác sau này phải giữ cùng thứ tự khóa users → products để tránh
lost update/deadlock. Không tự retry lỗi DB; có thể chờ khóa nếu request khác
đang giữ khóa. Rate limiting/CSRF token và secure cookie production là các
hạng mục Auth hiện chưa có, không được thay đổi trong bước này.

## Migration Cart — đã nằm trong lịch sử áp dụng

Revision Cart: `20261016_0002`, down_revision=`20261015_0001`.
Theo xác nhận ngày 17/10/2026, PostgreSQL thật đã ở `20261017_0005`, bao gồm revision này.
Các lệnh áp dụng bên dưới chỉ tham khảo cho môi trường khác còn ở revision 0001,
không phải yêu cầu chạy lại trên database hiện tại.
Upgrade chỉ CREATE carts, CREATE cart_items và index; không seed, không sửa/xóa
dữ liệu sản phẩm hoặc tài khoản. Nếu bảng trùng tên đã tồn tại, migration sẽ
báo lỗi; không tự nhận cấu trúc khác là hợp lệ. Downgrade bị chặn để tránh mất giỏ.

Từ D:\DATN, xem lịch sử (không cần DB):

```powershell
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini heads
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini history
```

Xem SQL CHỈ của revision mới, không kết nối DB:

```powershell
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini upgrade 20261015_0001:20261016_0002 --sql
```

Không dùng `upgrade head --sql` mặc định cho database đã có dữ liệu, vì nó xuất
cả lịch sử từ đầu. Không lấy SQL toàn bộ đó chạy trực tiếp lên database hiện có.

Sau khi bạn duyệt, kiểm tra version hiện tại bằng lệnh chỉ đọc:

```powershell
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini current
```

Xác nhận database đích là lumiere_db và current là 20261015_0001, kiểm tra không
có bảng carts/cart_items khác cấu trúc, sao lưu database trước khi áp dụng.
CHỈ sau khi duyệt bước thay đổi DB mới chạy:

```powershell
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini upgrade 20261016_0002
```

Môi trường mới phải có bảng Cart trước khi gọi API. Môi trường hiện tại đã được xác nhận
áp dụng đến 0005; lần cập nhật tài liệu này không thực hiện migration.

## Test

Từ D:\DATN:

```powershell
.\.venv\Scripts\python.exe -B backend/tests/test_cart_api.py
.\.venv\Scripts\python.exe -B backend/tests/test_catalog_api.py
.\.venv\Scripts\python.exe -B backend/tests/test_import_catalog.py
```

Cart suite gồm các test Auth kế thừa, dùng cookie thật qua ASGI, override get_db
bằng SQLite trong bộ nhớ và bật foreign_keys. Chặn mọi kết nối PostgreSQL; không
đọc .env. Dữ liệu nguồn chỉ được nạp làm fixture trong bộ nhớ, không import thật.
Test bao gồm phân quyền, trùng item, tồn kho, Decimal, validation, rollback,
constraint và SQL offline. Kiểm tra SQL PostgreSQL có khóa users trước products.
SQLite không mô phỏng được FOR UPDATE; chưa có test concurrency PostgreSQL thật.
