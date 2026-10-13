# LUMIÈRE — Vanilla Frontend First

## Công nghệ
HTML5 / CSS3 / JavaScript ES6+ thuần, **không có React/Vite/Tailwind/Bootstrap**. Dùng Python `http.server` để chạy tĩnh trên localhost. FastAPI Business API (:8001), AI API (:8000) là các dịch vụ riêng.

## Cài đặt không xóa website đang có
1. **Sao lưu** thư mục `frontend` hiện tại (`frontend_backup_YYYYMMDD`).
2. Giải nén ZIP; copy nội dung thư mục `lumiere-full-frontend` vào `frontend` mới.
3. `cd D:\JewelryDatasetGenerator\frontend`
4. `python -m http.server 5500`
5. Mở `http://localhost:5500` và `http://localhost:5500/pages/products.html`.

Không cần `npm install`. Các ảnh demo sử dụng Unsplash, cần internet để hiển thị.

## Trạng thái chức năng
- Trang chủ: bố cục, bộ lọc sản phẩm, giỏ nhanh, yêu thích, chatbot (sẵn gọi `POST http://localhost:8000/chat`).
- Trang danh sách: tìm kiếm, lọc, sắp xếp từ **12 bản ghi demo**.
- Trang chi tiết: số lượng, giới hạn tồn kho demo, giỏ hàng/yêu thích; liên kết sản phẩm liên quan theo danh mục demo.
- Giỏ hàng: lưu `lumiere_cart` dạng `{ "1": 2 }`; yêu thích: `lumiere_favorites` dạng `[1,3]` trong localStorage. Không lưu mật khẩu/token.
- Đăng ký/đăng nhập/đăng xuất/tài khoản: gọi các endpoint đã có của Business API (:8001); cookie HttpOnly, `credentials: 'include'`. Có thể đọc `GET /auth/me` để hiển thị thông tin user.
- Trang đặt hàng: biểu mẫu và tính tổng *demo*, **không ghi đơn hàng thật**, không trừ kho, không trừ tiền.
- Quên mật khẩu: UI scaffold **chưa kích hoạt**; backend phải xây cơ chế reset token/email.
- Đơn hàng, đánh giá: UI scaffold, chưa có API.
- Admin/nhân viên: giao diện quản lý và bảng DEMO; **không phải dashboard có phân quyền an toàn**; các nút CRUD chưa tạo giao dịch. Backend phải bảo vệ các endpoint bằng vai trò. Trên bản giao diện tĩnh, trang quản trị vẫn truy cập được để trình diễn; đừng coi đó là rào chắn bảo mật.
- Phân tích hành vi và recommendation: giao diện placeholder; sẽ chỉ chạy thật sau khi đồng bộ ProductID/UserID và các API.

## Quy ước
`assets/js/products.js` là **nguồn dữ liệu demo duy nhất**. Chưa dùng dữ liệu PostgreSQL hoặc CSV Qdrant/Neo4j. Không giả mạo trạng thái thanh toán/đơn hàng. Không sửa AI Service. UI không phụ thuộc framework.

## Trang có sẵn
- Khách hàng: index, products, product-detail, collections, search, wishlist, cart, checkout, login, register, forgot-password, account, orders, order-detail, reviews, about, contact.
- Admin: dashboard, products, categories, brands, inventory, orders, customers, coupons, staff, analytics.
- Nhân viên: orders, inventory.

## Backend contract
Xem `BACKEND_HANDOFF.md` và `API_CONTRACT.json` để phát triển backend. Ưu tiên auth/users → product catalog → cart/order/payment → tracking/review → admin/behavior → AI sync.

## Security
- Tài khoản public chỉ được tạo với role `customer`; admin/staff do quản trị cấp.
- Bật HTTPS + Secure cookie trên production, CSRF protection cho session cookie, rate limiting đăng nhập, xác thực role ở backend.
- Không tin tổng tiền, stock, phí ship, mã giảm giá từ frontend. Backend phải tính lại qua transaction và khóa tồn kho hợp lý.
- Đọc sản phẩm/giao dịch qua API PostgreSQL; thống nhất ProductID với AI dataset trước khi liên kết chatbot và recommendation.
