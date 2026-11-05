# LUMIÈRE frontend

Frontend dùng HTML/CSS/JavaScript thuần. Business Backend sở hữu dữ liệu sản phẩm, giá, tồn kho, giỏ hàng và đơn hàng; AI Service chỉ dùng cho chat/recommendations.

## Chạy local

1. Chạy Business FastAPI trên `http://localhost:8001`, cấu hình `CORS_ORIGINS` cho origin frontend và dùng database local/test.
2. Từ thư mục `frontend`, chạy `python -m http.server 5500`.
3. Mở `http://localhost:5500/`.

`assets/js/api.js` tự chọn Business API local ở cổng 8001 và same-origin trên Render. Session được gửi bằng cookie HttpOnly với `credentials: include`; không lưu token trong Web Storage. AI mặc định `http://127.0.0.1:8000` ở local; môi trường khác cần cấu hình `window.LUMIERE_AI_BASE` hoặc meta `lumiere-ai-api-base`. AI offline không ngăn catalog tải từ Business API.

## Phân quyền và giới hạn API

- Guest: xem catalog và chi tiết; các route Admin/Staff giao diện chuyển về đăng nhập.
- Customer: giỏ hàng, COD checkout, coupon validation, hồ sơ, đơn hàng, wishlist và reviews theo API.
- Admin: dashboard/revenue, sản phẩm hiện có, đơn hàng, khách hàng, tài khoản Staff, coupon, tồn kho và danh sách category/brand.
- Staff: xử lý đơn, cập nhật tồn kho và xác nhận COD theo Backend.
- Backend là ranh giới bảo mật cuối cùng. Không hiển thị VNPay như lựa chọn thanh toán; không tự tạo giao dịch hay phiếu kho.
- Category/brand hiện chỉ có API đọc; inventory movement ledger, analytics hành vi, tạo/xóa sản phẩm, quên mật khẩu, liên hệ và quản lý địa chỉ chưa có contract Backend. Các chức năng này không được giả lập là đã ghi dữ liệu.

Contract đã đối chiếu trực tiếp: [BACKEND_HANDOFF.md](./BACKEND_HANDOFF.md). Không dùng `API_CONTRACT.json` bản nháp làm nguồn thẩm quyền.

## Backend tests và browser E2E

Backend unit/API suite chỉ dùng database in-memory qua `backend/tests/run_safe.py`; test không kết nối PostgreSQL thật.

Playwright:

```powershell
cd frontend
npm install
npm run test:e2e
```

E2E mặc định BLOCKED/skip nếu chưa xác nhận local isolated database. Chỉ bật test ghi khi `LUMIERE_E2E_BASE_URL` dùng localhost, `LUMIERE_E2E_DB_KIND=isolated` và `LUMIERE_E2E_ALLOW_WRITE=1`; cấp tài khoản/fixture thử nghiệm qua các biến môi trường được mô tả trong `BACKEND_HANDOFF.md`. Không dùng Render hoặc production cho E2E ghi dữ liệu.
