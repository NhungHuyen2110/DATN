# LUMIÈRE — Hướng dẫn tải và kiểm thử bản hoàn thiện

## Phiên bản cần lấy

Nhánh **feature/final-demo-polish** dựa trên bản ổn định `integration/full-system`. Không merge vào `main` trước khi kiểm thử.

```powershell
cd D:\
git clone --branch feature/final-demo-polish --single-branch https://github.com/NhungHuyen2110/DATN.git LUMIERE-FINAL-TEST
cd D:\LUMIERE-FINAL-TEST
git log -1 --oneline
```

Giữ nguyên `D:\DATN-Backend-Integration` làm bản dự phòng. **Dừng Backend/AI chạy từ thư mục cũ** trước khi thử bản mới để tránh cổng 8000/8001 còn phục vụ source cũ.

## Cấu hình

- Backend đọc `.env` ở **gốc repository** (`D:\LUMIERE-FINAL-TEST\.env`). Không commit file này.
- AI có cấu hình riêng ở `AI\.env`; dùng các thông tin Neo4j, Qdrant, Ollama của hệ thống đang hoạt động. Không chia sẻ mật khẩu.
- PostgreSQL/Neo4j/Qdrant là **dữ liệu dịch vụ bên ngoài Git**, không được tải kèm source.
- Trước khi thử tính năng mới trên cơ sở dữ liệu demo, **sao lưu PostgreSQL** bằng công cụ phù hợp, hoặc thử trên DB bản sao.

Ví dụ các biến Backend cần có (điền mật khẩu thật *chỉ trên máy*; không đưa mẫu này lên Git):

```dotenv
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433
POSTGRES_DB=lumiere_backend_test
POSTGRES_USER=lumiere_user
POSTGRES_PASSWORD=YOUR_LOCAL_PASSWORD
SHIPPING_FLAT_VND=30000
SHIPPING_FREE_FROM_VND=2000000
VNPAY_ENABLED=false
```

**Phí vận chuyển**: khi có cấu hình trên, đơn dưới 2.000.000đ tính 30.000đ, đơn từ ngưỡng này trở lên miễn phí. Nếu không cấu hình `SHIPPING_FLAT_VND`, mức phí mặc định là 0đ để tương thích dữ liệu/kiểm thử cũ. Phí được tính ở Backend và ghi vào `orders.shipping_vnd`; coupon giảm giá trên giá hàng trước phí vận chuyển.

**Mã giảm giá**: phải nhập mã có định dạng hợp lệ, nhấn Kiểm tra trước khi đặt hàng. Backend vẫn kiểm tra lại mã và số tiền khi tạo đơn.

## Cập nhật database — BẮT BUỘC cho mục Liên hệ

Bản mới có migration `20261106_0007_contact.py` thêm bảng `contact_messages`.

**Chỉ chạy sau khi đã sao lưu và xác nhận đang trỏ đúng database demo.**

```powershell
cd D:\LUMIERE-FINAL-TEST\backend
python -m alembic current
python -m alembic upgrade head
```

Cần kết quả nâng lên revision `20261106_0007`. Nếu `alembic current` không phải chuỗi migration dự kiến, dừng để kiểm tra; không chạy `stamp`, không xóa bảng.

## Chạy Backend và AI

Mở hai Terminal, sử dụng Python đã cài đúng thư viện mỗi dịch vụ:

```powershell
cd D:\LUMIERE-FINAL-TEST\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

```powershell
cd D:\LUMIERE-FINAL-TEST\AI
& "D:\JewelryDatasetGenerator\.venv\Scripts\python.exe" -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Cần Qdrant, Neo4j và Ollama chạy theo cấu hình AI hiện có. Mở `http://127.0.0.1:8001/health`.

Kiểm tra tự động **không ghi database**:

```powershell
cd D:\LUMIERE-FINAL-TEST
powershell -ExecutionPolicy Bypass -File .\scripts\check_final_demo.ps1
```

## Kiểm thử giao diện một lượt

1. **Customer:** đăng nhập; duyệt/lọc sản phẩm; thêm giỏ; kiểm tra tạm tính, phí ship; nhập mã coupon đúng/sai; COD; xem lịch sử đơn; đánh giá.
2. **Liên hệ:** gửi biểu mẫu có tên, email, chủ đề và lời nhắn từ trang `/pages/contact.html`. Admin vào `/pages/admin/contacts.html`, kiểm tra yêu cầu được lưu và đổi trạng thái.
3. **Admin:** Dashboard, tình trạng đơn, thanh toán xác nhận, đơn gần nhất, cảnh báo tồn kho; phân tích hành vi mua hàng theo 7/30/90 ngày; danh mục/thương hiệu (thêm, sửa tên, xóa mục **chưa được sản phẩm sử dụng**); mã giảm giá.
4. **Staff:** cập nhật trạng thái đơn, xác nhận COD đã giao, kiểm tra tồn kho.
5. **AI:** Chatbot trả lời và Hybrid Recommendation V2 hiển thị các sản phẩm trên trang chi tiết.
6. **VNPay:** chạy bộ test giả lập và xác minh giao diện khóa phương thức khi không cấu hình merchant. Chỉ thử giao dịch Sandbox thật khi có merchant và IPN công khai hợp lệ.

## VNPay Sandbox: không có merchant thì không thể giao dịch thật

Backend đã có API tạo URL, xử lý IPN và Return; Frontend mới đã có lựa chọn VNPay, và tự chỉ bật khi Backend xác nhận cấu hình hợp lệ.

Muốn thử Sandbox thực tế cần **merchant thử nghiệm hợp lệ**, biến môi trường:

```dotenv
VNPAY_ENABLED=true
VNPAY_TMN_CODE=YOUR_8_CHARACTER_TEST_CODE
VNPAY_HASH_SECRET=YOUR_SANDBOX_SECRET
VNPAY_RETURN_URL=https://your-public-https-backend.example/payments/vnpay/return
```

- Địa chỉ Return bắt buộc HTTPS với đường dẫn chính xác `/payments/vnpay/return`.
- IPN `https://your-public-https-backend.example/payments/vnpay/ipn` phải truy cập được từ VNPay và được khai báo cho merchant; `127.0.0.1` không thể nhận IPN từ cổng thanh toán.
- **Chỉ IPN đã xác minh** mới cập nhật trạng thái `paid`. Trang Return chỉ thông báo trạng thái đọc từ server.
- Không dùng mã merchant/secret giả, không test thanh toán thật, không commit secrets.

## Phạm vi tính năng mới

- Giới thiệu: câu chuyện thương hiệu đầy đủ, nội dung rõ là đồ án.
- Liên hệ: lưu thực vào PostgreSQL và Admin xử lý.
- Vận chuyển: cấu hình được, Backend tính và lưu tiền.
- Coupon: có kiểm tra mã và đồng bộ tổng sau giảm + phí ship.
- Dashboard: đọc số liệu thực từ PostgreSQL, không dùng số liệu giả.
- Phân tích hành vi: thống kê **hành vi mua hàng từ đơn thực**, không tự nhận là lượt xem/tìm kiếm vì chưa có event-tracking.
- Danh mục & thương hiệu: CRUD có role Admin, chặn xóa mục được sử dụng.
- VNPay: hiển thị khi cấu hình Sandbox hợp lệ và dẫn sang URL Sandbox; không thể hoàn tất giao dịch thực khi thiếu merchant/IPN.

## An toàn

Không đẩy `.env`, backup, log hoặc credentials lên GitHub. Không dùng `git add .` khi thư mục chứa file dự phòng. Nhánh `integration/full-system` và `main` không bị sửa bởi các commit này.
