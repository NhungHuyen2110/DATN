# Tư vấn theo nhu cầu — semantic smoke đạt, toàn dự án chưa nghiệm thu

## Kết quả sau khi giảm tải ngày 22/11/2026

Đã bật `LUMIERE_SHOPPING_ADVICE_ENABLED=true` trên local sau khi kiểm tuần tự đạt. Full backend **675 passed/829 subtests**, AI **90 passed/1 skipped** (`ai-advice-contract-final-20261122.json`). Bộ kiểm model thật nhận đúng gift intent cho “Lễ tình nhân tặng gì?” và một câu diễn đạt lại về quà cho người thương; cả hai trả lời tư vấn kèm 3 sản phẩm. Câu “Top 3 nhẫn dưới 8 triệu” giữ product-search intent, đúng loại/giá. Từng sản phẩm ở cả ba câu khớp tên, giá và tồn kho Business; cả ba `status=ok`, warmup HTTP 200. Xem `semantic-shopping-advice-live-20261122.json`.

Chrome thật ở **18080**, không inject config/mock API, xác nhận lời tư vấn nhìn thấy và 3 thẻ link chi tiết: `shopping-advice-browser-20261122.json`. Các case này là smoke chức năng, không phải human relevance benchmark hoặc bằng chứng mọi paraphrase đều đúng. Đây là semantic intent + lời hướng dẫn được kiểm soát, chưa là Qwen narrative/hội thoại nhiều lượt.

Nền thuộc tính có nguồn đã qua full regression nhưng **chưa migrate database đang phục vụ, chưa có UI review và chưa nối graph/vector/filter**. Không có fact Audience/Style giả được tự thêm. CI/môi trường mới dùng head 0010; helper fixture/restore vẫn hỗ trợ checkpoint 0009. Các mục này không được đánh dấu hoàn thành toàn bộ.

Rollback tư vấn: đổi feature flag về false và recreate riêng AI bằng đúng override; giữ toàn bộ DB/graph/vector. Không downgrade bảng review có evidence: migration chủ động chặn rollback khi bảng có dữ liệu. Log full backend nằm tại `.local-tmp/attribute-foundation-backend-after-close.log`; checksum/scope được cập nhật trong `current-implementation.json`.

## Lịch sử các lượt chưa đạt trước khi giảm tải

Yêu cầu bổ sung: câu như “Lễ tình nhân tặng gì?” cần tư vấn lựa chọn rồi dẫn tới sản phẩm thật, không chỉ truy vấn node/cụm từ. Không cam kết AI đúng tuyệt đối.

Đã tạo `advice_planner.py`: phân loại ý nghĩa câu bằng cosine giữa embedding query và các mô tả nhu cầu, dùng MiniLM local hiện có. Không sửa câu hỏi/ngân sách, không tạo giá/tên/ID và không khẳng định sản phẩm có thuộc tính dịp lễ. Khi nhận gift intent, thêm hướng dẫn chọn quà và dùng retriever V2 kiểm giá/tồn kho.

AI offline: **88 đạt, 1 skip**, `ai-semantic-advice-tests-20261122.json`. Probe model thật chưa đạt: API warmup 503, dense fallback/catalog timeout và chưa có advice intent. Lần đo Windows chỉ còn **95.136 KiB (~93 MiB) RAM khả dụng**. Đã dừng 2 service QA, dừng test backend nặng của agent và giữ `LUMIERE_SHOPPING_ADVICE_ENABLED=false` trên môi trường đang chạy. Không bật tính năng chưa đạt hoặc ghi nghiệm thu thành công.

Nền thuộc tính có nguồn đã viết: registry Audience/Style, bảng riêng/migration additive 0010, API Admin xác nhận/thu hồi với optimistic version và lịch sử, xác nhận evidence và enqueue cùng transaction. **2 test memory đạt**, 673 test khác deselected trong lượt riêng (`.local-tmp/attribute-review-targeted.log`). Chưa chạy migration vào DB đang phục vụ, chưa nối public catalog/graph/vector/filter hoặc có UI review. Không tự gán fact cho sản phẩm cũ.

Full backend đầu lỗi import shared đã sửa; lượt sau dừng khi thiếu RAM và phát hiện assertion head 0009 cũ, đã sửa thành 0010. Lượt full cuối cũng dừng chủ động vì RAM còn ~93 MiB. Chưa có full backend pass cho phần source mới; không dùng 673 pass lịch sử thay kết quả này.

Checkpoint UI đã push: `b336e0a`, 13 browser checks AI/role/Top 10; nguyên nhân HTTP 404 Staff/Admin là thiếu `/api`, đã sửa. Source semantic advice/attribute foundation đang ở working tree để tiếp tục test, chưa công bố là release hoàn chỉnh.

Tiếp theo khi RAM đủ: chạy lại full backend, kiểm model thật/các paraphrase và ngân sách, kiểm browser advice, rồi hoàn thiện fact review → outbox → graph/vector → hard filters. Qwen narrative, benchmark có người review và hosting/VPS vẫn mở. Không xóa dữ liệu, backup, volume hoặc tài khoản cũ để giảm tải.
