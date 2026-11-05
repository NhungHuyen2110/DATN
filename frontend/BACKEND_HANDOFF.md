# LUMIÈRE Business API — contract đối chiếu trực tiếp

Tài liệu này được đối chiếu với `backend/app/main.py`, routers, schemas và services. Backend FastAPI là nguồn có thẩm quyền; OpenAPI có tại `/openapi.json` khi chạy service.

## Cấu hình và bảo mật

- Frontend production dùng same-origin Business API; local static frontend dùng `http://localhost:8001`. Có thể override bằng `window.LUMIERE_API_BASE`.
- Session chỉ nằm trong cookie HttpOnly; mọi yêu cầu gửi `credentials: "include"`. Không lưu token hay mật khẩu trong Web Storage.
- AI là dịch vụ độc lập; `window.LUMIERE_AI_BASE` hoặc `<meta name="lumiere-ai-api-base" content="...">` cấu hình endpoint AI. Local mặc định là `http://127.0.0.1:8000`; AI offline không chặn catalog Business API.
- Role check ở giao diện chỉ phục vụ điều hướng. Backend vẫn xác thực session và role trên từng route.
- UI chỉ gửi COD. VNPay không được khởi tạo từ frontend; chỉ bật sau khi merchant/IPN được cấu hình và xác nhận.

## Endpoint hiện có

| Method | Path | Quyền Backend | Request / kết quả chính |
|---|---|---|---|
| POST | `/auth/register` | Public, chỉ tạo Customer | `full_name,email,phone?,password`; trả `user_id,email,role` |
| POST | `/auth/login` | Public | `email,password`; trả user và cookie session HttpOnly |
| GET / PATCH | `/auth/me` | User đã đăng nhập | Đọc/sửa `full_name,phone` |
| POST | `/auth/logout` | Public/session nếu có | Thu hồi session và xóa cookie |
| GET | `/categories`, `/brands` | Public | Danh sách lookup |
| GET | `/products`, `/products/{id}` | Public | Tìm/lọc và phân trang; `page_size` tối đa 100 |
| GET | `/admin/products`, `/admin/products/{id}` | Admin | Danh sách/chi tiết sản phẩm |
| PATCH | `/admin/products/{id}` | Admin | Sửa trường cho phép; cập nhật giá cần `sale_price` và `expected_sale_price` |
| PATCH | `/staff/products/{id}/stock` | Staff/Admin | `{expected_stock,stock}`; phát hiện tồn kho cũ |
| GET / POST | `/cart`, `/cart/items` | User đã đăng nhập | Đọc/thêm giỏ; giá, subtotal do Backend lấy/tính |
| PATCH / DELETE | `/cart/items/{id}` | User đã đăng nhập, chủ sở hữu item | Cập nhật số lượng/xóa |
| POST | `/orders` | Customer | Người nhận, số điện thoại, địa chỉ, `payment_method`, `coupon_code?`; checkout transaction |
| GET | `/orders/my` | Customer | Danh sách đơn của mình |
| GET | `/orders/{id}` | User đã đăng nhập; Admin có thể xem mọi đơn | Chi tiết đơn, Backend kiểm tra quyền sở hữu |
| GET / PATCH | `/admin/orders`, `/admin/orders/{id}/status` | Admin | Danh sách và cập nhật trạng thái theo state machine |
| GET / GET detail / PATCH | `/staff/orders`, `/staff/orders/{id}`, `/staff/orders/{id}/status` | Staff/Admin | Xem và xử lý đơn; state machine vẫn do Backend kiểm tra |
| POST | `/admin/orders/{id}/cod/confirm` | Admin | `{collection_reference}`; xác nhận thu COD hợp lệ |
| POST | `/staff/orders/{id}/cod/confirm` | Staff/Admin | `{collection_reference}`; xác nhận thu COD theo quyền |
| GET | `/admin/customers`, `/admin/customers/{id}` | Admin | Tìm kiếm, lọc, phân trang và chi tiết |
| PATCH | `/admin/customers/{id}/status` | Admin | `{is_active}` |
| GET / POST | `/admin/staff` | Admin | Danh sách và tạo tài khoản Staff |
| GET / PATCH | `/admin/staff/{id}` | Admin | Chi tiết và sửa hồ sơ Staff |
| PATCH | `/admin/staff/{id}/status` | Admin | Khóa/mở tài khoản Staff |
| GET | `/admin/dashboard` | Admin | Tổng đơn, trạng thái, tồn kho, khoản thanh toán được xác nhận và đối soát |
| GET | `/admin/reports/revenue` | Admin | `start_date,end_date,group_by`; khoản thanh toán xác nhận, không phải lợi nhuận |
| GET / POST | `/admin/coupons` | Admin | Danh sách/tạo coupon |
| GET / PATCH | `/admin/coupons/{id}` | Admin | Chi tiết/cập nhật coupon |
| PATCH | `/admin/coupons/{id}/status` | Admin | Bật/tắt coupon; không có API xóa |
| POST | `/checkout/coupon/validate` | Customer | `{coupon_code}`; kiểm tra trên giỏ Backend |
| GET | `/wishlist` | Customer | Danh sách yêu thích |
| POST / DELETE | `/wishlist/items`, `/wishlist/items/{product_id}` | Customer | Thêm/xóa yêu thích |
| GET / POST | `/products/{product_id}/reviews` | Public đọc; Customer ghi | Review sản phẩm; Backend kiểm tra điều kiện mua hàng |
| GET | `/reviews/my` | Customer | Đánh giá của mình |
| PATCH / DELETE | `/reviews/{id}` | Customer, chủ sở hữu | Sửa/xóa review |
| POST | `/orders/{id}/payments/vnpay` | Customer | Endpoint tạo URL có tồn tại nhưng frontend không gọi |
| GET | `/payments/vnpay/ipn`, `/payments/vnpay/return` | Gateway callback | Xử lý callback/return theo service thanh toán |
| GET | `/health` | Public | Kiểm tra Business API/PostgreSQL |

## Chưa có API / không được giả lập như nghiệp vụ thật

- Chưa có API tạo/xóa sản phẩm; chỉ sửa sản phẩm hiện có.
- Category/brand chỉ có API đọc lookup; chưa có CRUD taxonomy.
- Chưa có API inventory movement/nhập-xuất, phiếu kho hoặc audit ledger; UI chỉ cập nhật số tồn qua endpoint compare-and-set, không giả tạo chứng từ.
- Dashboard có dữ liệu đơn/thanh toán/tồn kho và revenue report; chưa có API analytics hành vi/funnel.
- Chưa có quên mật khẩu/email reset, quản lý địa chỉ giao hàng hoặc API liên hệ.
- Coupon không có API xóa; frontend chỉ tạo/sửa/đổi trạng thái.

## Playwright E2E an toàn

`npm run test:e2e` chạy từ `frontend/`. Test chỉ được kích hoạt khi `LUMIERE_E2E_BASE_URL` trỏ localhost, `LUMIERE_E2E_DB_KIND=isolated`; luồng ghi cần thêm `LUMIERE_E2E_ALLOW_WRITE=1`. Cấp thông tin Customer/Admin/Staff và fixture qua các biến `LUMIERE_E2E_<ROLE>_EMAIL/PASSWORD`, `LUMIERE_E2E_ORDER_ID`, `LUMIERE_E2E_ORDER_STATUS`, `LUMIERE_E2E_STOCK_PRODUCT_ID`, `LUMIERE_E2E_COD_ORDER_ID`. Không chạy các test ghi dữ liệu trên Render/production.
