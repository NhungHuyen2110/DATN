# Audit và cleanup Frontend — 19/11/2026

Branch: `refactor/business-frontend-20261119`. Baseline thống kê là working tree đầu phiên, gồm cả thay đổi sẵn có và untracked, không phải HEAD.

Checkpoint có thể phục hồi: `<TEMP_DIR>/lumiere-frontend-20261119-a23k6cvs` gồm frontend.zip, manifest SHA-256, Git status và binary diff tracked. Chỉ giải nén file cần phục hồi sau khi đối chiếu, không reset toàn bộ workspace. Không commit/push/merge, không sửa backend/AI/infra/database/Docker/.env.

## A. Audit và bằng chứng references

Bảng quyết định được lập trước cleanup và chuẩn hóa lại sau verification. References là ứng viên từ toàn bộ HTML/JS/MJS/CSS ở checkpoint; đã đối chiếu trực tiếp dynamic imports, window exports và event handlers cho các phần sửa. HTML là entrypoint trực tiếp nên không cần incoming link. Không xóa CSS dựa trên số lần xuất hiện selector vì có markup sinh động và demo globals.

| File | Vai trò | Vấn đề | Quyết định | Lý do |
| --- | --- | --- | --- | --- |
| `frontend/index.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/site_1.js, assets/js/shared/console-shell.mjs, assets/js/shared/site-shell.mjs |
| `frontend/playwright.config.js` | JS/controller | Có references | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: — |
| `frontend/assets/css/customer-ai.css` | Stylesheet | Có references | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: pages/product-detail.html, pages/products.html |
| `frontend/assets/css/management-ai-polish.css` | Stylesheet | Có references | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: pages/admin/dashboard.html, pages/staff/orders.html |
| `frontend/assets/css/site.css` | Stylesheet | Có references | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: pages/about.html, pages/account.html, pages/cart.html, pages/checkout.html, pages/collections.html, pages/contact.html, pages/forgot-password.html, pages/login.html, pages/order-detail.html, pages/orders.html, pages/product-detail.html, pages/products.html, pages/register.html, pages/reviews.html, pages/search.html, pages/wishlist.html, pages/admin/analytics.html, pages/admin/brands.html, pages/admin/categories.html, pages/admin/contacts.html, pages/admin/coupons.html, pages/admin/customers.html, pages/admin/dashboard.html, pages/admin/inventory.html, pages/admin/orders.html, pages/admin/products.html, pages/admin/staff.html, pages/staff/inventory.html, pages/staff/orders.html |
| `frontend/assets/css/style.css` | Stylesheet | Có references | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: index.html, pages/about.html, pages/account.html, pages/cart.html, pages/checkout.html, pages/collections.html, pages/contact.html, pages/forgot-password.html, pages/login.html, pages/order-detail.html, pages/orders.html, pages/product-detail.html, pages/products.html, pages/register.html, pages/reviews.html, pages/search.html, pages/wishlist.html, pages/admin/analytics.html, pages/admin/brands.html, pages/admin/categories.html, pages/admin/contacts.html, pages/admin/coupons.html, pages/admin/customers.html, pages/admin/dashboard.html, pages/admin/inventory.html, pages/admin/orders.html, pages/admin/products.html, pages/admin/staff.html, pages/staff/inventory.html, pages/staff/orders.html |
| `frontend/assets/js/admin-analytics.js` | JS/controller | Demo globals vẫn được HTML tải, site_1.js có lời gọi | Giữ nguyên | Luồng site.js dùng Business console; chưa xóa exports/entrypoints compatibility; refs: pages/admin/analytics.html |
| `frontend/assets/js/admin-coupons.js` | JS/controller | Demo globals vẫn được HTML tải, site_1.js có lời gọi | Giữ nguyên | Luồng site.js dùng Business console; chưa xóa exports/entrypoints compatibility; refs: pages/admin/coupons.html |
| `frontend/assets/js/admin-customers.js` | JS/controller | Demo globals vẫn được HTML tải, site_1.js có lời gọi | Giữ nguyên | Luồng site.js dùng Business console; chưa xóa exports/entrypoints compatibility; refs: pages/admin/customers.html |
| `frontend/assets/js/admin-dashboard.js` | JS/controller | Demo globals vẫn được HTML tải, site_1.js có lời gọi | Giữ nguyên | Luồng site.js dùng Business console; chưa xóa exports/entrypoints compatibility; refs: pages/admin/dashboard.html |
| `frontend/assets/js/admin-inventory.js` | JS/controller | Demo globals vẫn được HTML tải, site_1.js có lời gọi | Giữ nguyên | Luồng site.js dùng Business console; chưa xóa exports/entrypoints compatibility; refs: pages/admin/inventory.html |
| `frontend/assets/js/admin-orders.js` | JS/controller | Demo globals vẫn được HTML tải, site_1.js có lời gọi | Giữ nguyên | Luồng site.js dùng Business console; chưa xóa exports/entrypoints compatibility; refs: pages/admin/orders.html |
| `frontend/assets/js/admin-products.js` | JS/controller | Demo globals vẫn được HTML tải, site_1.js có lời gọi | Giữ nguyên | Luồng site.js dùng Business console; chưa xóa exports/entrypoints compatibility; refs: pages/admin/products.html |
| `frontend/assets/js/admin-staff.js` | JS/controller | Demo globals vẫn được HTML tải, site_1.js có lời gọi | Giữ nguyên | Luồng site.js dùng Business console; chưa xóa exports/entrypoints compatibility; refs: pages/admin/staff.html |
| `frontend/assets/js/admin-taxonomy.js` | JS/controller | Demo globals vẫn được HTML tải, site_1.js có lời gọi | Giữ nguyên | Luồng site.js dùng Business console; chưa xóa exports/entrypoints compatibility; refs: pages/admin/brands.html, pages/admin/categories.html |
| `frontend/assets/js/api.js` | JS/controller | Thêm homeSession() chia sẻ một lookup khởi tạo giữa app.js và home-auth.js; me() vẫn gửi request mới cho login/profile. | Sửa chọn lọc | Thêm homeSession() chia sẻ một lookup khởi tạo giữa app.js và home-auth.js; me() vẫn gửi request mới cho login/profile.; refs: index.html, assets/js/site.js, assets/js/site_1.js, pages/about.html, pages/account.html, pages/cart.html, pages/checkout.html, pages/collections.html, pages/contact.html, pages/forgot-password.html, pages/login.html, pages/order-detail.html, pages/orders.html, pages/product-detail.html, pages/products.html, pages/register.html, pages/reviews.html, pages/search.html, pages/wishlist.html, pages/admin/analytics.html, pages/admin/brands.html, pages/admin/categories.html, pages/admin/contacts.html, pages/admin/coupons.html, pages/admin/customers.html, pages/admin/dashboard.html, pages/admin/inventory.html, pages/admin/orders.html, pages/admin/products.html, pages/admin/staff.html, pages/staff/inventory.html, pages/staff/orders.html |
| `frontend/assets/js/app.js` | JS/controller | 5 hàm cùng tên bị ghi đè; localStorage demo; request dư | Sửa chọn lọc | Bỏ 5 định nghĩa bị ghi đè, read/save/state demo và showAccount không reference. Dùng homeWishlist cho trạng thái hiển thị; chặn thao tác đồng thời; render giỏ từ mutation response thay GET thừa; timeout chat.; refs: index.html |
| `frontend/assets/js/backend-console.js` | JS/controller | Có references | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/site.js, assets/js/site_1.js |
| `frontend/assets/js/customer-ai.js` | JS/controller | Có references | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: pages/product-detail.html, pages/products.html |
| `frontend/assets/js/home-auth.js` | JS/controller | Giữ entrypoint HTML, dùng chung promise phiên trang chủ. | Sửa chọn lọc | Giữ entrypoint HTML, dùng chung promise phiên trang chủ.; refs: index.html |
| `frontend/assets/js/management-ai.js` | JS/controller | Có references | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: pages/admin/dashboard.html, pages/staff/orders.html |
| `frontend/assets/js/product-image-map.js` | JS/controller | Có references | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: index.html, pages/about.html, pages/account.html, pages/cart.html, pages/checkout.html, pages/collections.html, pages/contact.html, pages/forgot-password.html, pages/login.html, pages/order-detail.html, pages/orders.html, pages/product-detail.html, pages/products.html, pages/register.html, pages/reviews.html, pages/search.html, pages/wishlist.html, pages/admin/analytics.html, pages/admin/brands.html, pages/admin/categories.html, pages/admin/contacts.html, pages/admin/coupons.html, pages/admin/customers.html, pages/admin/dashboard.html, pages/admin/inventory.html, pages/admin/orders.html, pages/admin/products.html, pages/admin/staff.html, pages/staff/inventory.html, pages/staff/orders.html |
| `frontend/assets/js/products.js` | JS/controller | Có references | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: index.html, assets/js/site.js, assets/js/site_1.js, pages/about.html, pages/account.html, pages/cart.html, pages/checkout.html, pages/collections.html, pages/contact.html, pages/forgot-password.html, pages/login.html, pages/order-detail.html, pages/orders.html, pages/product-detail.html, pages/products.html, pages/register.html, pages/reviews.html, pages/search.html, pages/wishlist.html, pages/admin/analytics.html, pages/admin/brands.html, pages/admin/categories.html, pages/admin/contacts.html, pages/admin/coupons.html, pages/admin/customers.html, pages/admin/dashboard.html, pages/admin/inventory.html, pages/admin/orders.html, pages/admin/products.html, pages/admin/staff.html, pages/staff/inventory.html, pages/staff/orders.html |
| `frontend/assets/js/site.js` | JS/controller | State chỉ ghi, catalog tải mọi trang, thiếu một số catches/guards | Sửa chọn lọc | Bỏ state wishlistIds chỉ ghi và biến area không đọc. Chỉ tải catalog ở trang cần dữ liệu; thêm pending guards và catches cho init/module, đặt URL recommendation trong try.; refs: pages/about.html, pages/account.html, pages/cart.html, pages/checkout.html, pages/collections.html, pages/contact.html, pages/forgot-password.html, pages/login.html, pages/order-detail.html, pages/orders.html, pages/product-detail.html, pages/products.html, pages/register.html, pages/reviews.html, pages/search.html, pages/wishlist.html, pages/admin/analytics.html, pages/admin/brands.html, pages/admin/categories.html, pages/admin/contacts.html, pages/admin/coupons.html, pages/admin/customers.html, pages/admin/dashboard.html, pages/admin/inventory.html, pages/admin/orders.html, pages/admin/products.html, pages/admin/staff.html, pages/staff/inventory.html, pages/staff/orders.html |
| `frontend/assets/js/site_1.js` | JS/controller | Không có incoming reference, bản cũ có khai báo trùng | Giữ nguyên | Untracked của người dùng; không xóa hoặc sửa; refs: — |
| `frontend/assets/js/staff-inventory.js` | JS/controller | Demo globals vẫn được HTML tải, site_1.js có lời gọi | Giữ nguyên | Luồng site.js dùng Business console; chưa xóa exports/entrypoints compatibility; refs: pages/staff/inventory.html |
| `frontend/assets/js/staff-orders.js` | JS/controller | Demo globals vẫn được HTML tải, site_1.js có lời gọi | Giữ nguyên | Luồng site.js dùng Business console; chưa xóa exports/entrypoints compatibility; refs: pages/staff/orders.html |
| `frontend/assets/js/pages/management-console.mjs` | JS/controller | Static imports giữa chức năng; pagination chưa có guard | Sửa chọn lọc | Import orders/products theo section; kiểm tra pagination không tiến triển thay vì lặp vô hạn; chặn submit taxonomy đang gửi.; refs: assets/js/backend-console.js |
| `frontend/assets/js/pages/management-orders.mjs` | JS/controller | Reload trong catch có thể reject tiếp | Sửa chọn lọc | Không await reload lần hai trong catch. Giữ trạng thái đã xác nhận, khôi phục control và báo lỗi khi request/reload thất bại.; refs: assets/js/pages/management-console.mjs |
| `frontend/assets/js/pages/management-products.mjs` | JS/controller | Chặn hai submit event khi tạo sản phẩm đang chờ API. | Sửa chọn lọc | Chặn hai submit event khi tạo sản phẩm đang chờ API.; refs: assets/js/pages/management-console.mjs |
| `frontend/assets/js/shared/console-shell.mjs` | JS/controller | Có references | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/pages/management-console.mjs |
| `frontend/assets/js/shared/http-client.mjs` | JS/controller | JSON lỗi trả null; HTTP status bị mất | Sửa chọn lọc | HTTP 2xx có JSON hỏng phải báo lỗi; gắn HTTP status cho lỗi và giữ thông báo khi validation detail rỗng.; refs: assets/js/api.js, tests/unit/http-client.test.mjs |
| `frontend/assets/js/shared/site-shell.mjs` | JS/controller | Có references | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/site.js, assets/js/site_1.js |
| `frontend/assets/js/shared/ui.mjs` | JS/controller | Có references | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/backend-console.js, assets/js/site.js, assets/js/site_1.js, assets/js/pages/management-console.mjs, assets/js/shared/console-shell.mjs |
| `frontend/pages/about.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/shared/site-shell.mjs |
| `frontend/pages/account.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/home-auth.js, assets/js/site.js, assets/js/site_1.js, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/pages/cart.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/shared/site-shell.mjs, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/pages/checkout.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/app.js, assets/js/site.js, assets/js/site_1.js, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/pages/collections.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/shared/site-shell.mjs |
| `frontend/pages/contact.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/shared/site-shell.mjs |
| `frontend/pages/forgot-password.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/site.js, assets/js/site_1.js |
| `frontend/pages/login.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: index.html, assets/js/app.js, assets/js/home-auth.js, assets/js/site.js, assets/js/site_1.js, assets/js/shared/site-shell.mjs, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/pages/order-detail.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/site.js, assets/js/site_1.js |
| `frontend/pages/orders.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/admin-dashboard.js, assets/js/app.js, assets/js/site.js, assets/js/site_1.js, assets/js/pages/management-console.mjs, assets/js/shared/site-shell.mjs, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/pages/product-detail.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/site.js, assets/js/site_1.js |
| `frontend/pages/products.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: index.html, assets/js/admin-dashboard.js, assets/js/site.js, assets/js/site_1.js, assets/js/shared/site-shell.mjs, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/pages/register.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/site.js, assets/js/site_1.js, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/pages/reviews.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/site.js, assets/js/site_1.js |
| `frontend/pages/search.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: — |
| `frontend/pages/wishlist.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/site.js, assets/js/site_1.js, assets/js/shared/site-shell.mjs, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/pages/admin/analytics.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/admin-dashboard.js |
| `frontend/pages/admin/brands.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: — |
| `frontend/pages/admin/categories.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: — |
| `frontend/pages/admin/contacts.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/shared/site-shell.mjs |
| `frontend/pages/admin/coupons.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/admin-dashboard.js, assets/js/shared/site-shell.mjs |
| `frontend/pages/admin/customers.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/shared/site-shell.mjs |
| `frontend/pages/admin/dashboard.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/app.js, assets/js/site.js, assets/js/site_1.js, assets/js/shared/site-shell.mjs, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/pages/admin/inventory.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/admin-dashboard.js, assets/js/site_1.js, assets/js/pages/management-console.mjs, assets/js/shared/site-shell.mjs, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/pages/admin/orders.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/admin-dashboard.js, assets/js/app.js, assets/js/site.js, assets/js/site_1.js, assets/js/pages/management-console.mjs, assets/js/shared/site-shell.mjs, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/pages/admin/products.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: index.html, assets/js/admin-dashboard.js, assets/js/site.js, assets/js/site_1.js, assets/js/shared/site-shell.mjs, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/pages/admin/staff.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/shared/site-shell.mjs |
| `frontend/pages/staff/inventory.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/admin-dashboard.js, assets/js/site_1.js, assets/js/pages/management-console.mjs, assets/js/shared/site-shell.mjs, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/pages/staff/orders.html` | HTML entrypoint | Trang truy cập trực tiếp bằng URL | Giữ nguyên | Bảo toàn URL, markup, CSS và compatibility; refs: assets/js/admin-dashboard.js, assets/js/app.js, assets/js/site.js, assets/js/site_1.js, assets/js/pages/management-console.mjs, assets/js/shared/site-shell.mjs, tests/browser-smoke.mjs, tests/e2e/lumiere.spec.js |
| `frontend/tests/browser-smoke.mjs` | JS/controller | Thêm kiểm tra trang chủ, request trùng, AI/API/module offline; chờ UI hoàn tất commit trước đọc fixture SQLite chung connection. Evidence nằm dưới frontend/test-results. | Sửa chọn lọc | Thêm kiểm tra trang chủ, request trùng, AI/API/module offline; chờ UI hoàn tất commit trước đọc fixture SQLite chung connection. Evidence nằm dưới frontend/test-results.; refs: — |
| `frontend/tests/e2e/lumiere.spec.js` | JS/controller | Sửa selectors logout/checkout theo UI hiện tại, chỉ xét alert hiển thị và chờ mutation hoàn tất trước chuyển trang. Chưa chạy Playwright suite. | Sửa chọn lọc | Sửa selectors logout/checkout theo UI hiện tại, chỉ xét alert hiển thị và chờ mutation hoàn tất trước chuyển trang. Chưa chạy Playwright suite.; refs: — |
| `frontend/tests/unit/http-client.test.mjs` | JS/controller | Thêm regression cho malformed JSON, HTTP 401 và validation detail rỗng. | Sửa chọn lọc | Thêm regression cho malformed JSON, HTTP 401 và validation detail rỗng.; refs: — |

## B. Kiến trúc trước và sau

Trước: presentation tier dùng `index.html → app.js + home-auth.js`; các trang khác dùng `site.js → shared UI/site shell → backend-console.js → management-console.mjs → orders/products`. `api.js → shared/http-client.mjs` gửi cookie tới Business API. Chat/recommendation gọi AI riêng. Frontend đã có ES Modules cùng classic compatibility entrypoints; không refactor lại những phần đã tách trước phiên này.

Sau: giữ mô hình trên, chỉ load catalog cho products/search/detail/cart/checkout/collections; login/account/orders/admin/staff không chờ public catalog. Orders/products modules chỉ import khi vào chức năng tương ứng. Trang chủ giữ một bản logic Business API cho giỏ/yêu thích, dùng chung lookup auth và tận dụng cart response. JSON lỗi, module lỗi và submit đang chạy có xử lý rõ hơn. Không thêm framework, repository/service/utility hay thư mục runtime. Đây vẫn là presentation tier của 3-Tier; không sửa hai tier backend/database và không tuyên bố fault isolation hoàn toàn.

Bằng chứng code chết đã bỏ:

- `app.js`: 5 cặp updateCounters/addToCart/toggleFav/showCart/showWishlist ở cùng classic scope. Function hoisting chọn bản Business API khai báo cuối, nên bản demo đầu không thể chạy qua các bindings này. read/save/state.cart chỉ phục vụ các bản bị ghi đè. showAccount chỉ có định nghĩa, không có lời gọi HTML/event/module. Không xóa dữ liệu localStorage cũ của người dùng.
- `site.js`: wishlistIds chỉ gán/add/delete, không có consumer; area không đọc. Đã đọc bản 637 dòng đầu phiên, không áp lại cleanup khai báo trùng của phiên trước.
- loadAllProducts của management khác endpoint và dữ liệu mapping storefront nên giữ độc lập. N+1 order details dùng để lấy recipient/phone chưa có ở list, chưa có bằng chứng bỏ an toàn.
- Demo admin/staff globals vẫn được HTML tải và site_1.js có lời gọi; luồng site.js hiện tại gọi Business console. Giữ toàn bộ compatibility scripts và site_1.js untracked. Forgot password hiển thị chưa kích hoạt, không giả lập khôi phục. Giá/stock/cart/order ở các luồng đang dùng lấy từ Business API. Nhãn “DEMO”/“AI dataset” còn trong markup/tài liệu cũ; không đổi UI để sửa nhãn trong phiên này.
- AI management chat còn dùng same-origin fetch riêng, còn customer chat và recommendation dùng AI base. Chưa hợp nhất vì timeout/auth/payload khác nhau; cần test deployment tách origin trước khi thay đổi.

## C. File đã sửa, giữ và xóa

| File sửa | Lý do |
| --- | --- |
| `frontend/assets/js/api.js` | Thêm homeSession() chia sẻ một lookup khởi tạo giữa app.js và home-auth.js; me() vẫn gửi request mới cho login/profile. |
| `frontend/assets/js/app.js` | Bỏ 5 định nghĩa bị ghi đè, read/save/state demo và showAccount không reference. Dùng homeWishlist cho trạng thái hiển thị; chặn thao tác đồng thời; render giỏ từ mutation response thay GET thừa; timeout chat. |
| `frontend/assets/js/home-auth.js` | Giữ entrypoint HTML, dùng chung promise phiên trang chủ. |
| `frontend/assets/js/site.js` | Bỏ state wishlistIds chỉ ghi và biến area không đọc. Chỉ tải catalog ở trang cần dữ liệu; thêm pending guards và catches cho init/module, đặt URL recommendation trong try. |
| `frontend/assets/js/pages/management-console.mjs` | Import orders/products theo section; kiểm tra pagination không tiến triển thay vì lặp vô hạn; chặn submit taxonomy đang gửi. |
| `frontend/assets/js/pages/management-orders.mjs` | Không await reload lần hai trong catch. Giữ trạng thái đã xác nhận, khôi phục control và báo lỗi khi request/reload thất bại. |
| `frontend/assets/js/pages/management-products.mjs` | Chặn hai submit event khi tạo sản phẩm đang chờ API. |
| `frontend/assets/js/shared/http-client.mjs` | HTTP 2xx có JSON hỏng phải báo lỗi; gắn HTTP status cho lỗi và giữ thông báo khi validation detail rỗng. |
| `frontend/tests/browser-smoke.mjs` | Thêm kiểm tra trang chủ, request trùng, AI/API/module offline; chờ UI hoàn tất commit trước đọc fixture SQLite chung connection. Evidence nằm dưới frontend/test-results. |
| `frontend/tests/e2e/lumiere.spec.js` | Sửa selectors logout/checkout theo UI hiện tại, chỉ xét alert hiển thị và chờ mutation hoàn tất trước chuyển trang. Chưa chạy Playwright suite. |
| `frontend/tests/unit/http-client.test.mjs` | Thêm regression cho malformed JSON, HTTP 401 và validation detail rỗng. |
| `frontend/tests/unit/asset-references.test.mjs` (mới) | Kiểm tra HTML scripts/styles và literal ES imports, gồm compatibility entrypoints. |
| `frontend/FRONTEND_AUDIT_20261119.md` (mới) | Bảng audit, quyết định, thống kê và giới hạn verification. |

Không xóa file nào. Có 562 file giữ nguyên byte so với checkpoint. Toàn bộ HTML/CSS/ảnh giữ nguyên; danh sách đầy đủ cũng có ở `test-results/safe-cleanup/change-stats.json`.

File giữ nguyên ngoài ảnh:

- `frontend/API_CONTRACT.json`
- `frontend/BACKEND_HANDOFF.md`
- `frontend/Dockerfile`
- `frontend/index.html`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/playwright.config.js`
- `frontend/README.md`
- `frontend/README_ADMIN_PRODUCTS.md`
- `frontend/assets/css/customer-ai.css`
- `frontend/assets/css/management-ai-polish.css`
- `frontend/assets/css/site.css`
- `frontend/assets/css/style.css`
- `frontend/assets/js/admin-analytics.js`
- `frontend/assets/js/admin-coupons.js`
- `frontend/assets/js/admin-customers.js`
- `frontend/assets/js/admin-dashboard.js`
- `frontend/assets/js/admin-inventory.js`
- `frontend/assets/js/admin-orders.js`
- `frontend/assets/js/admin-products.js`
- `frontend/assets/js/admin-staff.js`
- `frontend/assets/js/admin-taxonomy.js`
- `frontend/assets/js/backend-console.js`
- `frontend/assets/js/customer-ai.js`
- `frontend/assets/js/management-ai.js`
- `frontend/assets/js/product-image-map.js`
- `frontend/assets/js/products.js`
- `frontend/assets/js/site_1.js`
- `frontend/assets/js/staff-inventory.js`
- `frontend/assets/js/staff-orders.js`
- `frontend/assets/js/shared/console-shell.mjs`
- `frontend/assets/js/shared/site-shell.mjs`
- `frontend/assets/js/shared/ui.mjs`
- `frontend/pages/about.html`
- `frontend/pages/account.html`
- `frontend/pages/cart.html`
- `frontend/pages/checkout.html`
- `frontend/pages/collections.html`
- `frontend/pages/contact.html`
- `frontend/pages/forgot-password.html`
- `frontend/pages/login.html`
- `frontend/pages/order-detail.html`
- `frontend/pages/orders.html`
- `frontend/pages/product-detail.html`
- `frontend/pages/products.html`
- `frontend/pages/register.html`
- `frontend/pages/reviews.html`
- `frontend/pages/search.html`
- `frontend/pages/wishlist.html`
- `frontend/pages/admin/analytics.html`
- `frontend/pages/admin/brands.html`
- `frontend/pages/admin/categories.html`
- `frontend/pages/admin/contacts.html`
- `frontend/pages/admin/coupons.html`
- `frontend/pages/admin/customers.html`
- `frontend/pages/admin/dashboard.html`
- `frontend/pages/admin/inventory.html`
- `frontend/pages/admin/orders.html`
- `frontend/pages/admin/products.html`
- `frontend/pages/admin/staff.html`
- `frontend/pages/staff/inventory.html`
- `frontend/pages/staff/orders.html`

Ảnh giữ nguyên: toàn bộ `frontend/assets/images/products/*` trong manifest checkpoint.

## D. Thống kê thực tế so với đầu phiên

| File runtime | Trước | Sau | Thêm | Bỏ | Chênh byte |
| --- | ---: | ---: | ---: | ---: | ---: |
| `frontend/assets/js/api.js` | 216 | 220 | 4 | 0 | +152 |
| `frontend/assets/js/app.js` | 75 | 68 | 13 | 20 | -3290 |
| `frontend/assets/js/home-auth.js` | 2 | 2 | 1 | 1 | +9 |
| `frontend/assets/js/site.js` | 637 | 638 | 18 | 17 | +1113 |
| `frontend/assets/js/pages/management-console.mjs` | 356 | 365 | 13 | 4 | +397 |
| `frontend/assets/js/pages/management-orders.mjs` | 129 | 133 | 5 | 1 | +206 |
| `frontend/assets/js/pages/management-products.mjs` | 242 | 243 | 1 | 0 | +69 |
| `frontend/assets/js/shared/http-client.mjs` | 25 | 33 | 10 | 2 | +293 |

Runtime: thêm 65, bỏ 45 dòng vật lý, ròng **+20 dòng**, dung lượng UTF-8 **-1051 byte**. app.js có nhiều hàm nén trên một dòng nên số dòng không phản ánh độ dư thừa: đã bỏ 5 định nghĩa bị ghi đè, nhưng thêm guards/catches cần thiết. Tests ròng **+143 dòng** gồm test mới; tài liệu và evidence không tính là runtime. Không dùng git diff HEAD để quy công những cleanup sẵn có trước phiên.

## E. Verification

| Kiểm tra | Kết quả | Bằng chứng / giới hạn |
| --- | --- | --- |
| JavaScript syntax | PASS | `.cache/node.exe --check` cho toàn bộ 33 JS/MJS, gồm legacy/untracked và tests. |
| Unit tests | PASS | 9 tests: 8 HTTP transport và 1 asset references; chạy trực tiếp từng file bằng Node, không skip. |
| HTML scripts/styles và literal import paths | PASS | Test đọc cây frontend và xác minh các đường dẫn tồn tại; computed management loader được smoke test thực tế. |
| Browser Chrome headless + Business API SQLite in-memory | PASS | 23 nhóm kiểm tra; screenshots và result.json tại `frontend/test-results/safe-cleanup/`. Không kết nối PostgreSQL. |
| Customer | PASS trong phạm vi smoke | Register/login/profile, wishlist, giỏ/quantity, COD checkout/history/detail, role denial/logout, trang chủ và duplicate submit. |
| Staff | PASS trong phạm vi smoke | Login, order detail/search/status, stock update/logout. |
| Admin | PASS trong phạm vi smoke | Login/dashboard, products/inventory/orders/customers/staff/coupons/categories/brands/contacts/analytics, cập nhật tên/giá. |
| AI offline | PASS trong phạm vi smoke | Recommendation bị chặn, detail/reviews/add-cart vẫn dùng được. Homepage AI chat có timeout và pending guard; chưa test timeout 4 phút. |
| Business API/module lỗi | PASS trong phạm vi smoke | Public catalog lỗi hiển thị an toàn; login/admin vẫn chạy khi catalog public bị chặn; module orders/products lỗi không chặn customers/contacts; status PATCH/reload lỗi giữ control; auth submit lỗi cho retry. Không có uncaught browser exception. |
| Giữ nguyên source giao diện | PASS | SHA-256/byte equality với checkpoint cho toàn bộ HTML/CSS/ảnh. Không phải pixel comparison trên mọi màn hình. |
| Git ngoài frontend | PASS | Binary tracked diff và porcelain status ngoài frontend giống đầu phiên. Không commit/push/merge. |
| Playwright E2E suite | NOT VERIFIED | Chưa có node_modules/@playwright/test trong workspace; không báo skipped suite là PASS. Sửa selector lệch UI nhưng chưa chạy suite này. |
| PostgreSQL / môi trường triển khai / VNPay / AI thật | NOT VERIFIED | Không truy cập dữ liệu thật hay thay cấu hình. |

Lệnh chạy: `.cache/node.exe frontend/tests/unit/http-client.test.mjs`, `.cache/node.exe frontend/tests/unit/asset-references.test.mjs`, `.cache/node.exe frontend/tests/browser-smoke.mjs` từ workspace root. Browser cần fixture `backend/tests/serve_browser_fixture.py` **mới mỗi lượt chạy** và Chrome debug 19222 với profile riêng; fixture chặn engine ngoài SQLite :memory: và không load .env. Evidence là dữ liệu thử rõ ràng, không đưa vào ứng dụng.

Các lần lỗi ban đầu không được tính PASS: Node `--test` bị `spawn EPERM`; option `--test-isolation=none` không hỗ trợ Node 22.16; chạy trực tiếp node:test từng file cho TAP đầy đủ. Chrome bị sandbox chặn IPC, chạy lại với quyền được tool review cho phép. Smoke lần đầu timeout status khi polling API trong lúc SQLite shared connection cập nhật; chuyển sang chờ UI refresh rồi assert API. Một lượt chạy lại trên fixture cũ thất bại vì wishlist còn dữ liệu; các lượt xác minh cuối dùng fixture mới, không bỏ assert.

## F. Rủi ro và kiểm thử thủ công còn lại

Ghi chú evidence: các lượt smoke đầu dùng đường dẫn `.cache/refactor-browser-evidence/` vốn có trong script; lượt cuối đã ghi đủ evidence dưới `frontend/test-results/safe-cleanup/`. Một lượt mở rộng smoke gặp lỗi khai báo biến `select` trùng trong CDP evaluate; đã sửa harness và chạy lại đủ 23 nhóm trên fixture mới. Những lượt thất bại này không được tính PASS.

- Chưa có bằng chứng mọi chức năng của ba vai trò không hồi quy: cần CRUD đầy đủ customers/staff/coupons/category/brand/contacts, review đủ điều kiện mua hàng, tìm/lọc/phân trang nhiều dữ liệu và xác nhận COD đã giao.
- Cần test VNPay Sandbox end-to-end (redirect, return, IPN, lỗi sau khi tạo đơn), coupon đổi mã trong lúc request đang chạy, session hết hạn khi đang thao tác và network timeout/response JSON sai trên các form.
- Cần đối chiếu desktop/mobile, bàn phím/focus/dialog và screenshot trước/sau trên mọi trang; HTML/CSS không đổi không đủ khẳng định pixel equivalence.
- Cần test AI chat customer/admin/staff, malformed AI base, AI chậm và deployment tách origin. UI cũ còn nhãn kỹ thuật/demo; chưa thay để bảo toàn giao diện.
- Demo compatibility globals và site_1.js vẫn tồn tại có chủ đích; chỉ xóa sau khi người dùng quyết định xử lý bản untracked và chứng minh không còn consumers bên ngoài cây references hiện tại.
- Dashboard từng gom nhiều API bằng Promise.all; vấn đề này đã được xử lý trong bổ sung G bên dưới. Transport module/shared shell vẫn là phụ thuộc chung. Không tuyên bố cách ly lỗi hoàn toàn.
- Guard phía trình duyệt chỉ chặn gửi đồng thời trong page hiện tại, không thay thế idempotency phía server khi mất mạng sau khi server đã tạo đơn.

## G. Bổ sung: cách ly lỗi nguồn dữ liệu Dashboard

Phạm vi bổ sung chỉ là nhánh Dashboard trong `assets/js/pages/management-console.mjs`, regression tests và ghi chú này. Không sửa nhánh Analytics, HTML/CSS, API client/contracts, authentication hoặc Backend/AI. Checkpoint đầu lượt bổ sung: `<TEMP_DIR>/lumiere-dashboard-uwis1l29/before.zip`.

| Nguồn | Phân loại | Phần phụ thuộc | Khi nguồn lỗi |
| --- | --- | --- | --- |
| `/admin/dashboard` | Quan trọng cho tổng quan | KPI tổng quan, trạng thái đơn, đối soát | Các vùng này báo lỗi; đơn gần nhất, tồn kho và thanh toán 30 ngày vẫn dùng nguồn riêng. |
| `/admin/orders?page=1&page_size=5` | Bổ sung độc lập | Bảng đơn gần nhất | Báo lỗi ngay trong bảng; không thay bằng “Chưa có đơn”. |
| `/admin/products` (phân trang) | Bổ sung độc lập | Số sản phẩm đã tải, số tồn thấp và bảng tồn thấp | Các phần này báo lỗi; tổng sản phẩm/hết hàng từ API tổng quan vẫn hiển thị. |
| `/admin/reports/revenue` | Bổ sung độc lập | KPI và biểu đồ thanh toán 30 ngày | Chỉ hai phần này báo lỗi; không hiển thị doanh thu giả bằng 0. |

Thay Promise.all bằng Promise.allSettled, giữ trạng thái thành công/thất bại từng nguồn. Thông báo có tên nguồn và lỗi đã escape trong vùng tương ứng. Markup khi mọi nguồn thành công đã đối chiếu bằng nhau với renderer ở checkpoint; không thay stylesheet hoặc bố cục. Không thêm module runtime/thư mục/abstraction và không xóa file.

File sửa: `assets/js/pages/management-console.mjs`, `tests/browser-smoke.mjs`, báo cáo này. File mới: `tests/unit/dashboard.test.mjs` (5 cases gọi renderer thật với API fixtures chỉ ở test).

| Verification bổ sung | Kết quả |
| --- | --- |
| Toàn bộ frontend unit tests | PASS: 14 tests, không skip; chạy từng `tests/unit/*.test.mjs` trực tiếp bằng `.cache/node.exe`. |
| Browser smoke Chrome + SQLite in-memory | PASS: 27 nhóm, gồm 4 trường hợp chặn riêng từng endpoint Dashboard; không có uncaught exception. Evidence: `frontend/test-results/safe-cleanup/result.json` và screenshots. |
| Syntax JS/MJS và HTML/import references | PASS. |
| Markup Dashboard khi tất cả API thành công | PASS: so sánh renderer trước/sau với cùng dữ liệu test; không phải kiểm tra pixel mọi viewport. |
| Playwright suite, PostgreSQL và deployment thực | NOT VERIFIED; không truy cập dữ liệu thật. |

Lượt bổ sung không sửa source ngoài Frontend, không reset/commit/push. Giới hạn: allSettled vẫn chờ mọi request kết thúc; lượt này xử lý request thất bại, không thêm deadline cho request treo. Shared transport/shell và nhánh Analytics vẫn giữ nguyên, không tuyên bố cách ly lỗi hoàn toàn.

## H. Final dead code cleanup — 20/11/2026

Đã rà lại Frontend và Business Backend trên branch `refactor/business-frontend-20261119`. Checkpoint mới trước cleanup: `.cache/final-cleanup-20261120-133437/before.zip` (734 file), manifest SHA-256 và Git status/diff đầu lượt cùng thư mục. Không xóa nguyên file nào, không sửa file untracked runtime; chỉ bỏ 5 unused import bindings và biến `order_ids` không đọc trong ba file Backend tracked. Danh sách đầy đủ, dòng trước sửa, bằng chứng và quyết định giữ file ở mục “Bổ sung — Final dead code cleanup” của [báo cáo Backend](../backend/BACKEND_COMPLETION_REPORT.md).

Đính chính bằng chứng về demo ở các mục trước: `site_1.js:388-389` có textual calls tới demo globals nhưng hai định nghĩa `adminPage/staffPage` này bị định nghĩa 390-391 ghi đè trong cùng function scope. Các lời gọi cũ đó không chứng minh demo đang được gọi lúc runtime. `site.js:308-309` hiện gọi Business console. Dù vậy, vẫn giữ 9 script `admin-*.js` và 2 script `staff-*.js` vì HTML còn tải, có global exports và mục đích giữ preview/consumer ngoài source chưa xác minh. Không thay HTML/script tags hay giao diện để ép xóa chúng.

| File/nhóm rà soát | Quyết định |
|---|---|
| `assets/js/site_1.js` | Ứng viên chưa xử lý: không có incoming HTML/import đã tìm thấy; untracked chưa rõ nguồn gốc/mục đích. Có các cặp checkout/adminPage/staffPage cũ bị ghi đè. Giữ nguyên byte. |
| `assets/js/backend-console.js` | Giữ: computed import tại `site.js:550` và `site_1.js:631`, đăng ký global rồi lazy-load management-console. Không phải file unused. |
| `assets/js/pages/*.mjs`, `assets/js/shared/*.mjs` | Giữ: dynamic imports/exports có consumer; đã smoke các nhánh chức năng và module lỗi. |
| `api.js`, `app.js`, `home-auth.js`, `site.js`, customer/management AI scripts, products/image-map | Giữ: HTML/controller/event handlers có sử dụng. Không chỉnh AI integration trong lượt cleanup. |
| Demo Admin/Staff scripts | Giữ như ứng viên legacy chưa đủ chứng cứ xóa; không xác nhận consumer ngoài repo. |
| HTML entrypoints, tests, README/handoff/API_CONTRACT, Dockerfile và configs | Giữ: URL truy cập trực tiếp, test runners hoặc vận hành không cần incoming import runtime. |

Toàn bộ Frontend source/runtime, HTML/CSS/ảnh và tests giữ nguyên byte; chỉ báo cáo này được bổ sung. Không thêm module hoặc tầng kiến trúc. Các loader storefront/management khác quyền, endpoint và dữ liệu mapping nên không gộp chỉ vì giống cấu trúc vòng lặp.

| Verification sau cleanup | Kết quả và evidence trong checkpoint mới |
|---|---|
| Backend regression | **PASS**: 647 tests, 827 subtests, 1 warning; `backend-regression.log`. Chỉ SQLite in-memory. |
| Frontend unit | **PASS**: 14/14, không skip; `frontend-unit.log`. |
| JS/MJS syntax | **PASS**: 34 file; `js-syntax.json`. |
| HTML scripts/literal imports/stylesheets | **PASS**: unit asset-reference test; 151 script/module edges giữ nguyên, không thiếu target; `frontend-references.json`. Computed loader được đọc và smoke riêng. |
| Browser smoke | **PASS**: 27 checks, không uncaught exception; `browser/result.json`, `browser-smoke.log`. Fixture mới và Chrome headless profile riêng, gồm AI/API/module failure injection. |
| OpenAPI | **PASS**: bằng nhau toàn bộ, 60 paths / 74 operations; `openapi-comparison.json`. |
| File ngoài phạm vi cleanup | **PASS** theo checksum: `preservation-final.json`; AI và untracked runtime không đổi. |
| Playwright suite / deployment thật / PostgreSQL / VNPay / AI thật | **NOT VERIFIED**. Không suy rộng kết quả smoke thành bảo đảm production hoặc fault isolation hoàn toàn. |

Không có thay đổi ngoài phạm vi dự kiến. Các nhãn/demo/preview chưa xác minh vẫn còn; **không tuyên bố đã dọn sạch hoàn toàn**. Checkpoint, logs và runner smoke sao chép chỉ ở .cache được Git ignore; không xóa checkpoint/dữ liệu có sẵn, không commit/push/merge.
