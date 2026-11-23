# Bàn giao local có giới hạn — 23/11/2026

**Cập nhật nghiệp vụ:** [Sửa mã giảm giá, khôi phục VNPAY và thêm ảnh sản phẩm](31-checkout-vnpay-product-images.md). Cấu hình VNPAY cũ đã được chọn riêng vào file local bỏ qua Git; không mất cấu hình gốc.

Không tiếp tục vòng thử model hoặc full test suite theo yêu cầu của người dùng. Đây là bản demo để kiểm thử nghiệp vụ và các công cụ AI đã triển khai; chưa phải nghiệm thu toàn bộ AI/hosting.

## Kiểm thử ngay

Mở **http://127.0.0.1:18080**. Dùng tài khoản cũ đúng vai trò; không có thao tác reset mật khẩu. Website dùng bản sao đầy đủ dữ liệu cũ, database nguồn và backup vẫn giữ nguyên. Chỉ các thao tác của bạn trên bản sao local mới cập nhật nghiệp vụ của bản sao.

1. Customer: xem 500 sản phẩm, mở ảnh/chi tiết, thử giỏ hàng/đặt COD và xem đơn. Thử AI “Top 3 nhẫn dưới 8 triệu”; nếu nguồn semantic chưa sẵn sàng, giữ thông báo lỗi để báo lại, không coi là không có hàng.
2. Staff: “Có bao nhiêu đơn chờ xử lý?”. Số liệu do công cụ SQL tính, không để LLM đoán.
3. Admin: hỏi tồn kho/thống kê. Mở `/pages/admin/product-attributes.html` khi muốn xác nhận nhãn có căn cứ. Không tự tick nhãn chỉ để làm kết quả đẹp.
4. Customer: hỏi tiếp “Tại sao lại gợi ý sản phẩm đó?” rồi “Tôi không hỏi sản phẩm”. Trợ lý phải giữ ngữ cảnh, không tạo bộ sản phẩm khác.
5. Câu hỏi kiến thức như “Đá Ruby là gì?” hiện được phân luồng riêng ở cả ba role và không thêm sản phẩm. **Qwen chưa hoạt động ổn định**, nên có thể nhận thông báo lớp hội thoại chưa sẵn sàng. Không coi đây là AI đã trả lời được mọi câu hỏi.

## Đã kiểm chứng và giới hạn

- Backend 683 tests/833 subtests đạt; AI/tools 135 đạt, 1 skip; API thật phân luồng ba role và SQL Staff đạt 4/4. Các phép kiểm này không đo độ thông minh.
- Graph/vector projection QA 8/8 và màn hình duyệt nhãn QA 7/7 đạt tại mốc ghi trong báo cáo. Luồng review event qua outbox mở rộng chưa nghiệm thu xong.
- Hai lần thử Qwen chưa đạt; lượt Chrome mới chưa qua semantic readiness sau restart. Không bật Qwen mặc định hoặc công bố full stack AI ổn định.
- Không có human ground truth cho Audience/Style/Occasion; benchmark chất lượng, reranker calibration, toàn bộ fault/load/security acceptance và hosting/TLS vẫn mở.
- Nhánh Git riêng: `rebuild/lumiere-demo-20261122`, không merge vào nhánh cũ. CI checkpoint `c8faea9` có 5 workflow thành công; xem CI đúng commit mới nhất trước khi triển khai.

Chi tiết: [Trạng thái AI và lý do chưa đạt](29-ai-status-and-blockers.md). Kết quả kiểm tra nhẹ cuối cùng nằm trong `local-handoff-20261123.json`; health/process running không đồng nghĩa retrieval hoặc Qwen đã đạt chất lượng.

## Chạy lại local sau khi đóng máy

Tại thư mục dự án, khi Docker Engine sẵn sàng:

```powershell
docker compose --env-file .env.example -p lumiere-rebuild-test -f compose.yaml -f compose.original-data.yaml -f compose.verified-attributes.yaml -f compose.payments-local.yaml --profile sync --profile monitoring up -d
```

Lệnh dùng cấu hình demo local và volumes hiện có, không tạo lại dữ liệu nguồn. Không dùng mật khẩu mẫu cho hosting công khai. Không chạy lại migrate/import/seed để sửa sự cố khởi động. Không xóa `.local-tmp`, Docker VHD, volumes hay backup; không dùng `down -v`.

Overlay `compose.payments-local.yaml` cần file riêng tư đã chuẩn bị trong workspace này. Khi clone mới chưa có merchant/file đó, bỏ overlay để chạy COD, hoặc chuẩn bị bằng script hướng dẫn trong tài liệu nghiệp vụ.

## Trước hosting

Chưa thuê VPS/domain và chưa public deploy. Bộ Compose/CI/monitoring đã có, nhưng cần staging có đủ tài nguyên, secrets riêng, phục hồi backup đã kiểm tra, HTTPS và smoke tests trên server. Không đưa database/đơn hàng/thông tin khách hàng hay `.env` lên repository public. Ngân sách đã chốt không quá 300.000đ/tháng; chưa mua dịch vụ thay người dùng.
