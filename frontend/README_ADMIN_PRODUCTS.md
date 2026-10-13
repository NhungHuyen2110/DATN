# LUMIÈRE – Nâng cấp trang Admin Sản phẩm (frontend-only)

## Cách dùng

1. Sao lưu bốn file đích trong repository hiện tại.
2. Chép các file dưới thư mục `frontend/` trong gói này vào đúng thư mục `D:\JewelryDatasetGenerator\frontend\` (cho phép ghi đè đúng 3 file cũ: `pages/admin/products.html`, `assets/css/site.css`, `assets/js/site.js`; và thêm `assets/js/admin-products.js`).
3. Giữ các file gốc `assets/js/products.js`, `assets/js/api.js`, `assets/css/style.css` hiện tại.
4. Chạy `python -m http.server 5500` tại thư mục frontend, mở `http://localhost:5500/pages/admin/products.html`.
5. Nhấn Ctrl+F5 để bỏ cache JS/CSS nếu thay đổi chưa xuất hiện.

## Tính năng
- Tìm bằng ID/tên/SKU, lọc danh mục/thương hiệu/trạng thái (bao gồm tồn kho thấp <=5).
- Bảng có ảnh, giá, số lượng, trạng thái; phân trang 5/10/20.
- Modal thêm/sửa có xác thực dữ liệu, không cho SKU trùng, giá/tồn kho không âm.
- Ngừng bán/mở bán demo, reset về dữ liệu gốc.
- Bản nháp chỉ nằm trong `sessionStorage` của tab; KHÔNG cập nhật dữ liệu sản phẩm storefront, backend hay PostgreSQL.
- Đây là chế độ phát triển/preview, KHÔNG có chức năng quản trị thật. Backend bắt buộc phân quyền cho các API ghi.

## Hợp đồng API dự kiến cho backend
`GET /admin/products?q=&category=&brand=&status=&page=1&page_size=10`, `POST /admin/products`, `PATCH /admin/products/{id}`, `PATCH /admin/products/{id}/status`, danh mục/thương hiệu từ API. Dữ liệu tối thiểu: id, sku, name, category, brand, material, gem, image, price, stock, status, description. Backend kiểm tra role admin, unique SKU, ràng buộc giá và tồn kho và ghi log thay đổi. Product ID dùng chung với AI cần đồng bộ riêng.
