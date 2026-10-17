# Catalog API

## Staff/Admin cập nhật số lượng tồn kho

Phần Admin Products nằm ở cuối tài liệu; Backend local dùng cổng 8001.

PATCH /staff/products/{id}/stock dùng session hiện có và staff_or_admin.
Staff/Admin được phép, Customer nhận 403, chưa đăng nhập nhận 401.
Không thêm model, migration hoặc bảng lịch sử kho.

```json
{"expected_stock": 10, "stock": 15}
```

Hai trường bắt buộc là số nguyên thật từ 0 đến 2147483647; từ chối bool, float,
chuỗi, null và trường thừa. ID đường dẫn phải là số nguyên dương. Product không
tồn tại trả 404. Nếu stock trong database khác expected_stock, trả 409 và không
cập nhật. Staff cần tải lại số lượng, kiểm tra lại rồi mới gửi yêu cầu khác.
Không tự retry bằng cách thay expected_stock mà bỏ qua việc đối chiếu.

Response 200:

```json
{"id": 1, "sku": "SP000001", "stock": 15}
```

id là ProductID gốc. Chỉ gán products.stock, không sửa SKU, giá hoặc trường khác.
Tái sử dụng transaction và lock_user của Orders; khóa user trước rồi product
FOR UPDATE, đọc lại giá trị trước khi so expected_stock. Commit một lần; lỗi
rollback. Không sửa logic checkout/hoàn kho hiện có. Nếu request checkout vừa
trừ kho, dữ liệu UI cũ sẽ nhận 409 thay vì ghi đè số lượng vừa bán.

Chạy test từ D:\DATN:

```powershell
.\.venv\Scripts\python.exe -B backend/tests/test_orders_api.py
```

Test bổ sung ngay trong file hiện có: phân quyền, strict validation, biên Integer,
404, stock lệch sau thao tác khác/checkout, giữ nguyên các cột khác, rollback và
thứ tự SQL khóa PostgreSQL. Test chạy SQLite trong bộ nhớ, cấm kết nối PostgreSQL.
Chưa chứng minh cạnh tranh nhiều request trên PostgreSQL test thật. expected_stock
so sánh số lượng, không phải version tăng đơn điệu hoặc nhật ký mọi thay đổi.

Kiểm thử Swagger khi bạn muốn: mở http://localhost:8001/docs, đăng nhập qua
POST /auth/login bằng Staff/Admin, đọc stock từ GET /products/{id}, dùng giá trị
đó làm expected_stock rồi gọi PATCH. Các thao tác Swagger này SẼ ghi vào database
của server đang chạy; ưu tiên database test riêng. Chưa chạy chúng ở bước này.
Ví dụ JSON chỉ minh họa; không giả định stock thực tế của sản phẩm 1 bằng 10.

4 endpoint public nằm trong Business API, dùng `get_db` và model hiện có.
Các endpoint public không tạo bảng, seed hoặc thay đổi dữ liệu. Không yêu cầu
đăng nhập để đọc catalog. Chỉ endpoint Staff nêu trên được phép sửa stock.

## Chạy ứng dụng local — cổng 8001

Từ `D:\DATN\backend`, dùng môi trường Python hiện có và PostgreSQL đã migration/import:

```powershell
..\.venv\Scripts\python.exe -B -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Swagger: http://localhost:8001/docs

OpenAPI: http://localhost:8001/openapi.json

## Response

`GET /categories` và `GET /brands` trả mảng JSON, sắp xếp ID tăng dần:

```json
[{"id": 1, "name": "Nhẫn"}]
```

Ví dụ trên chỉ minh họa một mục của categories. API đọc toàn bộ dữ liệu DB;
không hardcode số lượng 6/4, vì danh mục có thể được bổ sung sau này.

`GET /products` trả:

```json
{
  "items": [
    {
      "id": 1,
      "sku": "SP000001",
      "barcode": "893000000001",
      "name": "Bông tai Angel",
      "category": {"id": 3, "name": "Bông tai"},
      "brand": {"id": 2, "name": "PNJ"},
      "material": {"id": 5, "name": "Vàng trắng 18K"},
      "gemstone": {"id": 5, "name": "Moissanite"},
      "collection": {"id": 4, "name": "Minimal"},
      "weight": "14.47",
      "price_vnd": "5597326.00",
      "stock": 96
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 500
}
```

Ví dụ rút gọn items còn một phần tử, dùng dữ liệu file nguồn tại thời điểm viết.
API thật luôn truy vấn PostgreSQL. `total` đếm kết quả sau lọc, trước phân trang.

`GET /products/1` trả trực tiếp đối tượng sản phẩm giống một mục trong `items`.
`id` chính là ProductID gốc. Không tìm thấy trả HTTP 404:

```json
{"detail": "Không tìm thấy sản phẩm"}
```

Không trả cost_price/wholesale_price, không truy vấn hai cột giá nội bộ trong
SELECT sản phẩm. Không tự thêm slug, ảnh, mô tả, review hoặc thuộc tính chưa có.

## Query parameters cho /products

| Tham số | Quy tắc |
|---|---|
| q | Tìm chuỗi con trong tên hoặc SKU, không phân biệt hoa thường, tối đa 255 ký tự |
| category_id, brand_id, material_id, gemstone_id, collection_id | Số nguyên từ 1 đến 2147483647 |
| min_price, max_price | Decimal không âm, tối đa 16 chữ số phần nguyên và 2 chữ số thập phân; bao gồm hai đầu khoảng |
| page | Mặc định 1; từ 1 đến 2147483647 |
| page_size | Mặc định 20; từ 1 đến 100 |

Các bộ lọc kết hợp bằng AND; tên và SKU trong tìm kiếm kết hợp bằng OR.
q được bỏ khoảng trắng hai đầu; q rỗng/toàn khoảng trắng là không tìm kiếm.
Ký tự `%`, `_` được tìm như ký tự thường, không làm wildcard SQL. Các giá trị
được truyền dưới dạng bound parameters. Không bỏ dấu tiếng Việt; hành vi hoa
thường tuân theo PostgreSQL/collation hiện tại.

Luôn sắp xếp `products.id ASC`, không hỗ trợ sort tùy chọn ở bước này.
ID bộ lọc hợp lệ nhưng không tồn tại hoặc trang vượt kết quả trả items rỗng,
HTTP 200. Tham số sai kiểu/ngoài giới hạn, số vô hạn/NaN, giá quá độ chính xác,
min_price > max_price hoặc ID đường dẫn không hợp lệ trả HTTP 422.

Ví dụ:

```text
http://localhost:8001/products?q=SP000001
http://localhost:8001/products?category_id=1&brand_id=2&min_price=1000000&max_price=5000000&page=1&page_size=20
```

## Frontend và AI

- Business API: cổng 8001; AI API hiện dùng cổng 8000. Cùng đường dẫn /products
  nhưng khác cổng nên không xung đột router. Không thay đổi dịch vụ AI.
- Frontend cần đổi nguồn catalog từ AI sang Business API và đọc `items`, không
  đọc `{success, data}`. Danh mục/thương hiệu là mảng `{id, name}`.
- price_vnd và weight là chuỗi Decimal trong JSON để tránh mất độ chính xác.
  Frontend cần thống nhất cách định dạng tiền; không dùng kết quả tính giá từ
  browser làm căn cứ giao dịch. Tiền API là SalePrice, đơn vị VND.
- category, brand, material, gemstone, collection là đối tượng `{id, name}`.
  Frontend cũ dùng chuỗi hoặc trường gem/image/price phải tự ánh xạ lại.
- Không có ảnh/mô tả/slug khi dữ liệu chưa có. Cần thống nhất cách UI hiển thị
  trạng thái thiếu nội dung, không giả định các trường này luôn tồn tại.
- Dùng cùng ProductID gốc để liên kết với Chatbot, Qdrant và Neo4j.
- CORS hiện cho phép http://localhost:5500; origin http://127.0.0.1:5500 khác
  origin đó. Không sửa cấu hình CORS/xác thực ở bước này.
- Hai SELECT đếm và lấy trang dùng transaction hiện tại của get_db; nếu catalog
  thay đổi đồng thời thì tổng/trang có thể thay đổi. Đây không phải snapshot cố
  định xuyên suốt nhiều request phân trang.

## Kiểm thử

Từ `D:\DATN`:

```powershell
.\.venv\Scripts\python.exe -B backend/tests/test_catalog_api.py
```

Test gọi app qua ASGI trực tiếp, không cần httpx, không mở cổng server.
Override get_db bằng SQLite trong bộ nhớ; cấm mọi kết nối PostgreSQL và không
đọc .env. Nạp dữ liệu nguồn vào bộ nhớ chỉ để làm fixture. Kiểm tra response,
tìm kiếm, mọi bộ lọc, phân trang, 422, 404, Decimal, route xác thực, chỉ SELECT,
và biên dịch truy vấn bằng dialect PostgreSQL. Không thay thế kiểm thử tích hợp
trên PostgreSQL thật (đặc biệt collation và quyền truy cập).

## Admin quản lý sản phẩm hiện có

Ba API sau chỉ dành cho **Admin đang hoạt động**, dùng session cookie từ POST /auth/login.
Staff/Customer nhận 403; chưa đăng nhập, session sai/hết hạn hoặc tài khoản khóa nhận 401.

| API | Chức năng / response 200 |
| --- | --- |
| GET /admin/products | Tìm kiếm, phân trang; trả `{items, page, page_size, total}` |
| GET /admin/products/{id} | Trả một đối tượng sản phẩm |
| PATCH /admin/products/{id} | Sửa trường được phép; trả đối tượng sản phẩm sau cập nhật |

Danh sách Admin nhận `q` (tên hoặc SKU, không phân biệt hoa thường, tối đa 255 ký tự),
`page` mặc định 1 (1–2147483647), `page_size` mặc định 20 (1–100).
Tìm chuỗi con, trim q; `%`/`_` là ký tự thường, q rỗng không lọc.
Sắp xếp ProductID tăng dần; trang vượt kết quả trả items rỗng và total đúng.
Endpoint Admin chỉ khai báo ba tham số này; bộ lọc phân loại/giá thuộc GET /products công khai.

ID đường dẫn là số nguyên 1–2147483647; ID hợp lệ nhưng không tồn tại nhận 404.
Response dùng cùng ProductResponse với Catalog: `id`, `sku`, `barcode`, `name`,
category/brand/material/gemstone/collection dạng `{id, name}`, `weight`, `price_vnd`, `stock`.
Không trả `cost_price`/`wholesale_price`. Giá và trọng lượng là chuỗi Decimal;
`price_vnd` chính là `sale_price` trong database.

PATCH chỉ nhận các trường sau:

| Trường | Validation |
| --- | --- |
| name | Chuỗi, trim hai đầu; dài 1–255 ký tự sau trim |
| weight | Decimal hữu hạn > 0; tối đa 10 chữ số, 2 chữ số thập phân |
| category_id, brand_id, material_id, gemstone_id, collection_id | Số nguyên thực sự 1–2147483647; từ chối bool/float/string; bản ghi liên quan phải tồn tại |
| sale_price | Decimal hữu hạn >= 0; tối đa 18 chữ số, 2 chữ số thập phân |
| expected_sale_price | Cùng giới hạn với sale_price; giá kỳ vọng để kiểm tra xung đột, không lưu thành cột |

Body phải có ít nhất một trường được sửa; từ chối null và mọi trường ngoài danh sách.
Không cho sửa `id`, `sku`, `barcode`, `stock`, `cost_price`, `wholesale_price`.
Khóa ngoại không tồn tại, dữ liệu sai hoặc trường bị cấm nhận 422.

Ví dụ sửa thông tin:

```json
{"name": "Tên sản phẩm cập nhật", "weight": "12.34"}
```

Khi sửa giá, bắt buộc gửi **đồng thời** sale_price và expected_sale_price.
Đọc giá từ GET /admin/products/{id}, lấy `price_vnd` làm giá kỳ vọng:

```json
{"sale_price": "5600000.00", "expected_sale_price": "5597326.00"}
```

Các giá trên chỉ minh họa. Nếu giá database khác giá kỳ vọng, trả 409 và rollback
toàn bộ PATCH (kể cả trường khác gửi cùng request); cần tải lại và kiểm tra trước khi gửi tiếp.
Thiếu một trong hai trường giá hoặc chỉ gửi expected_sale_price nhận 422.
Tiền xử lý bằng Decimal; nên gửi chuỗi thập phân để tránh mất chính xác ở client.

Thao tác ghi khóa user Admin trước, rồi Product FOR UPDATE; commit trong transaction,
lỗi thì rollback. Xung đột dữ liệu có thể trả 409, lỗi database trả 500 không lộ thông tin kết nối.
Không ghi đè tồn kho, không đổi ProductID/SKU/barcode hoặc snapshot đơn hàng cũ.
Cập nhật tồn kho tiếp tục dùng endpoint Staff. Chưa có API tạo/xóa/ẩn/ngừng bán sản phẩm;
tạo sản phẩm mới đang tạm hoãn.

Swagger: http://localhost:8001/docs, nhóm **Admin Products**.
Test liên quan (từ D:\DATN):

```powershell
.\.venv\Scripts\python.exe backend/tests/test_admin_products.py
```
