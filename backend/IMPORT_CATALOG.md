# Import catalog gốc vào PostgreSQL

Chạy từ `D:\DATN\backend`, sử dụng môi trường Python ở thư mục gốc.
Chương trình luôn đọc 5 JSON trong `data/` và `output/products.csv` theo đường dẫn
tính từ vị trí mã nguồn, không phụ thuộc thư mục chạy lệnh.

## Kiểm tra không kết nối database

```powershell
..\.venv\Scripts\python.exe -B -m app.import_catalog --validate-only
```

Đối chiếu dữ liệu nguồn với model. Không kết nối PostgreSQL. Model dùng cấu hình
database hiện có nên dependency và biến môi trường Backend vẫn phải đầy đủ.

## Dry-run (chỉ đọc PostgreSQL)

```powershell
..\.venv\Scripts\python.exe -B -m app.import_catalog --dry-run
```

Kiểm tra nguồn, rồi đối chiếu 6 bảng bằng transaction `REPEATABLE READ, READ ONLY`.
Không INSERT, UPDATE, DELETE, tạo bảng hoặc thay đổi sequence. Báo số bản ghi sẽ
thêm và số bản ghi giống hệt được bỏ qua. Kết quả là ảnh chụp tại thời điểm kiểm
tra; lần import thật luôn kiểm tra lại.

## Import thật — chỉ chạy sau khi đã duyệt

```powershell
..\.venv\Scripts\python.exe -B -m app.import_catalog --apply
```

Cần migration `20261015_0001` đã áp dụng. Dùng `SessionLocal` hiện có, không có
URL/mật khẩu riêng. Không seed tài khoản/role, không gọi create_all hoặc Alembic.

Một transaction bao gồm:

1. Khóa 6 bảng bằng `SHARE ROW EXCLUSIVE` để tránh ghi đồng thời trong lúc đối chiếu.
   Chờ tối đa 5 giây cho mỗi yêu cầu lấy khóa; nếu có tranh chấp thì dừng, không
   tự thử lại. Các lượt đọc SELECT thông thường vẫn có thể hoạt động.
2. Kiểm tra toàn bộ dữ liệu hiện có trước khi thêm bất kỳ bản ghi nào.
3. Cùng ID và giống toàn bộ thuộc tính: bỏ qua. Cùng ID nhưng khác bất kỳ thuộc
   tính nào: báo bảng, ID, tên trường khác và dừng. Tên danh mục/SKU/barcode đã
   thuộc ID khác cũng là lỗi. Không cập nhật dữ liệu để ép cho khớp CSV.
4. Chèn bảng danh mục trước, products sau. Flush mỗi bảng, commit duy nhất khi
   tất cả thành công. Nếu lỗi thì rollback toàn bộ phần đã chèn trong lượt này.

Không có chế độ mặc định ghi dữ liệu: bắt buộc chọn rõ một trong ba cờ trên.
Exit code 0 khi thành công, 1 khi lỗi kiểm tra/import (argparse dùng 2 khi sai lệnh).
Không in URL kết nối, mật khẩu hay toàn bộ lỗi driver chứa tham số SQL.

## Quy tắc dữ liệu

- Đúng 500 sản phẩm; ID nguyên dương trong giới hạn Integer, không trùng.
- Giữ `ProductID` vào `products.id`, không tự tạo hay đánh lại số.
- Giữ SKU, barcode, tên và mọi thuộc tính trong CSV; không tự trim/đổi chữ hoa.
- Barcode là chuỗi nên không mất số 0 ở đầu.
- Giá và trọng lượng dùng Decimal đọc trực tiếp từ chuỗi, không qua float;
  không làm tròn dữ liệu có quá 2 chữ số thập phân có nghĩa.
- Kiểm tra giá không âm, trọng lượng dương, stock nguyên không âm, trường bắt
  buộc, độ dài, JSON/CSV sai cấu trúc, unique và 5 khóa ngoại về danh mục nguồn.
- `SalePrice` → `sale_price`; `WholesalePrice` → `wholesale_price`;
  `CostPrice` → `cost_price`. Không tính lại giá. Stock lấy từ products.csv,
  không ghép hoặc thay thế bằng inventory.csv.
- Dữ liệu DB không thuộc bộ nguồn vẫn được giữ nguyên; nếu đụng unique với bộ
  nguồn thì báo lỗi. Việc dữ liệu bán hàng đổi giá/stock sau này cũng làm lần
  nhập lại báo xung đột: đây là chủ đích để không ghi đè vận hành thật.

## Kiểm thử cô lập

Từ `D:\DATN`:

```powershell
.\.venv\Scripts\python.exe -B backend/tests/test_import_catalog.py
```

Test chỉ cho phép SQLite trong bộ nhớ, cấm kết nối PostgreSQL, không đọc `.env`.
Bao gồm đối chiếu nguồn/model, dữ liệu sai, xung đột, chạy lại không trùng,
giữ thuộc tính và rollback khi sản phẩm lỗi sau khi chèn danh mục.
Không thay thế kiểm thử tích hợp trên PostgreSQL. Cơ chế khóa và quyền DB thật
chỉ có thể được xác nhận khi được phép chạy dry-run/import ở bước sau.

Chương trình tải dữ liệu hiện có của 6 bảng vào bộ nhớ để đối chiếu; phù hợp bộ
500 sản phẩm hiện tại. Không dùng nguyên thiết kế này cho catalog rất lớn.
