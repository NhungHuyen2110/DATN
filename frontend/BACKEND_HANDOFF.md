# BÀN GIAO FRONTEND → BACKEND — LUMIÈRE

Tài liệu định hướng triển khai theo *Hướng đi khóa luận* và *Luồng hoạt động & Đặc tả Use Case* do nhóm cung cấp. Những API dưới đây ngoài `/auth/*` là **đề xuất hợp đồng**, chưa phải endpoint đã triển khai.

## Vai trò
- Khách vãng lai: duyệt, tìm kiếm, lọc, xem chi tiết, hỏi chatbot, xem recommendation không cá nhân hóa.
- Customer: giỏ hàng, yêu thích, địa chỉ, đặt hàng, lịch sử đơn, đánh giá đơn đã giao.
- Staff: xem, xử lý đơn hàng; cập nhật trạng thái hợp lệ; kiểm tra tồn kho.
- Admin: sản phẩm, danh mục, thương hiệu, kho, khách hàng, nhân viên, mã giảm giá, thống kê và phân tích hành vi.

## Các API đã có (backend hiện tại)
| Method | Endpoint | Nghiệp vụ |
|---|---|---|
| POST | `/auth/register` | đăng ký customer (201) |
| POST | `/auth/login` | tạo session HttpOnly |
| GET | `/auth/me` | user hiện tại |
| POST | `/auth/logout` | thu hồi session |
| GET | `/health` | DB health |

API AI riêng có `GET /recommendations/v2?customer_id=...&product_id=...&number=5` và `POST /chat` (`{query, top_k}`); cần cho phép CORS `http://localhost:5500` và chuẩn hóa ProductID.

## Các API đề xuất để người viết backend triển khai tiếp
| Method | Path | Vai trò | Chức năng |
|---|---|---|---|
| GET | `/products` | public | `q,category_id,brand_id,min_price,max_price,sort,page,page_size` |
| GET | `/products/{id}` | public | chi tiết ảnh, chất liệu, đá quý, tồn kho |
| GET | `/categories`, `/brands`, `/collections` | public | danh mục |
| GET/PUT | `/cart`, `/cart/items/{id}` | customer | lấy/sửa giỏ hàng |
| POST | `/cart/items` | customer | thêm số lượng (backend kiểm tra) |
| DELETE | `/cart/items/{id}` | customer | xóa |
| GET/POST/DELETE | `/wishlist` | customer | yêu thích |
| GET/POST/PATCH/DELETE | `/addresses` | customer | địa chỉ giao hàng |
| POST | `/orders` | customer | đặt hàng theo cart/địa chỉ, server tính giá và tồn |
| GET | `/orders/me` | customer | danh sách đơn user |
| GET | `/orders/{id}` | customer/staff/admin | xác thực sở hữu hoặc role |
| POST | `/payments/intent` | customer | tạo giao dịch sandbox/simulator |
| GET | `/shipments/{order_id}` | owner/staff/admin | tình trạng vận chuyển |
| POST/GET | `/products/{id}/reviews` | customer/public | kiểm tra mua hàng hoàn thành |
| POST | `/auth/forgot-password` | public | phản hồi đồng nhất chống enumerate |
| POST | `/auth/reset-password` | public | token một lần/hết hạn |
| GET/PATCH | `/users/me` | customer | cập nhật hồ sơ |
| GET | `/admin/dashboard` | admin | báo cáo tổng quan |
| CRUD | `/admin/products`,`/admin/categories`,`/admin/brands` | admin | quản trị catalog |
| CRUD | `/admin/coupons` | admin | điều kiện và thời hạn |
| GET/PATCH | `/staff/orders`, `/staff/orders/{id}/status` | staff/admin | xử lý đơn |
| GET | `/admin/customers`,`/admin/staff` | admin | quản lý tài khoản |
| POST | `/events` | guest/customer | ghi product_view, search, add_to_cart, wishlist, purchase |
| GET | `/admin/analytics` | admin | event funnel, conversion, doanh thu |

## Đề xuất bảng PostgreSQL
`roles, users, user_sessions` (đã có); `addresses, categories, brands, collections, products, product_images, inventory_movements, carts, cart_items, wishlists, coupons, coupon_usages, orders, order_items, payments, shipments, reviews, behavior_events, search_history, recommendation_logs, chat_sessions, chat_messages`.

Ràng buộc: `orders` / `order_items` lưu snapshot giá + tên/sku tại thời điểm đặt. `inventory_movements` phục vụ audit. Order state machine `pending -> confirmed -> packing -> shipping -> delivered` (hủy từ một số trạng thái; tránh tùy tiện quay ngược). Payment trạng thái riêng; không suy ra đã thanh toán từ client. Quản lý số lượng bằng transaction, không race. Các giá trị tiền nên dùng NUMERIC/Decimal và đơn vị VND; xác định rõ quy tắc VAT/phí ship. Password hash Argon2id.

## Chuẩn response đề xuất
Products GET: `{items:[{id,sku,name,slug,category:{id,name},brand:{id,name},material,gemstone,price_vnd,stock,images:[{url,alt}],description}],page,page_size,total}`.
Product detail GET: same item + attributes/collection + reviews summary.
Orders POST: `{order_id,code,status,total_vnd,payment_status,items:[...]}` (HTTP 201) sau transaction.
Error thống nhất: `{detail:"...",code:"..."}`; HTTP 400/401/403/404/409/422/500. Validate server-side Pydantic.

## Mã định danh và tích hợp AI
Demo `LUMIERE_PRODUCTS` ID 1..12 **không được coi là** ID đã liên kết database. CSV AI hiện trả `ProductID` khác. Backend cần mapping table `ai_product_id ↔ products.id` hoặc đồng bộ catalog trong Qdrant/Neo4j với ID sản phẩm chuẩn; tương tự `CustomerID` so với users.id. Sau đó frontend chỉ gọi backend business làm gateway hoặc gọi trực tiếp AI API có CORS, không hardcode tên/giá từ AI lên checkout.

## Đặc tả quan trọng
- Checkout yêu cầu đăng nhập; backend tính tổng và ship từ DB, kiểm tra kho; không lấy tổng từ browser.
- Các trang Admin/Staff hiện là demo hiển thị; **phải** phân quyền phía server và ghi audit log.
- Cookie session: `HttpOnly`, `SameSite=Lax`, `Secure` ở production; có CSRF token chống cross-site action, rate limiting, quản lý hết hạn.
- Dùng Alembic migration thay `create_all()` khi có nhiều bảng.
- Xây bộ test API: hợp lệ, sai role, thiếu stock, trùng email, giao dịch đồng thời, đổi giá trước checkout, đơn của user khác.
