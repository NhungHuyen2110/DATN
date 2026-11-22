# LUMIÈRE — tiến độ ngày 22/11/2026

**Bạn có thể test bản demo local ngay tại http://127.0.0.1:18080. Toàn bộ đồ án chưa nghiệm thu xong; hosting chưa triển khai.**

**Checkpoint hội thoại mới nhất:** 5/5 scenario Chrome đạt trên source cuối sau sửa cache/warmup; AI **100 đạt/1 skip**, backend **675/829 subtest**. Cần tải lại trang để JavaScript mới gửi conversation ID; context cũ trước khi cập nhật không tự phục hồi. Câu hỏi giải thích/đính chính không đổi bộ sản phẩm. Qwen tự nhiên vẫn chưa bật local/chưa nghiệm thu trên VPS; không coi đây là đã đạt khả năng ChatGPT.

**Sửa lỗi hội thoại người dùng báo:** đã thêm context ở server và cả ba UI. Chrome thật kiểm 5 scenario: hỏi lý do giữ đúng sản phẩm trước, phản hồi không hỏi sản phẩm không sinh thẻ mới, Staff/Admin giữ đúng ngữ cảnh báo cáo. Đây chưa phải general dialogue kiểu ChatGPT; Qwen chưa bật/chưa kiểm live. Người dùng chọn VPS tối đa 300.000đ/tháng; cấu hình model đã chuẩn bị, cần chốt giá cuối và có server. [Chi tiết và giới hạn](24-conversation-and-vps-dialogue.md).

**Tư vấn ngữ nghĩa đã kiểm model thật:** “Lễ tình nhân tặng gì?” và một câu diễn đạt lại nhận lời hướng dẫn chọn quà kèm 3 sản phẩm khớp giá/tồn kho; Top 3 nhẫn dưới 8 triệu vẫn giữ đúng điều kiện. Chrome thật ở 18080 xác nhận câu trả lời và 3 link sản phẩm. Full backend mới **675 test/829 subtest**, AI **90 đạt/1 skip**. Đây chưa là hội thoại nhiều lượt/Qwen hoặc relevance benchmark. [Kết quả và giới hạn](23-semantic-advice-in-progress.md).

**AI giao diện vừa sửa:** chatbot Staff/Admin gọi thiếu `/api`, đã sửa và build vào frontend đang chạy. Widget Customer đã vẽ đủ Top 10, có ảnh SKU/link/tồn kho/lý do; lỗi chat không ảnh hưởng catalog. Chrome thực trên QA copy đầy đủ 500 sản phẩm/12 đơn đạt **13 kiểm tra AI/role**, không inject URL hoặc mock response thành công. Không thay mật khẩu/tài khoản cũ đang phục vụ. Xem [bằng chứng và giới hạn](22-ai-ui-repair-and-acceptance.md).

Đã đạt:

- **10 container chạy cùng nhau:** frontend, proxy, Business API, AI API, PostgreSQL, Neo4j, Qdrant, worker, Prometheus và Grafana. Đủ 4 image ứng dụng build riêng.
- **18/18 ca Chrome đạt, không skip/flaky**, gồm Customer/COD, Staff/Admin, reset mật khẩu, chẩn đoán AI, gợi ý và dashboard Grafana thật.
- **Retrieval dùng đủ lexical + dense + graph:** model MiniLM thật có revision cố định, graph paths được xác minh, kết quả khớp giá/tồn kho Business API.
- **Đồng bộ thật sau checkout:** outbox generation 2 đã delivered, tồn kho Neo4j khớp Business, Prometheus scrape được cả hai API và worker.
- **GitHub:** đã push nhánh mới rebuild/lumiere-demo-20261122, không merge nhánh cũ. Năm workflow trên commit nền 2ad4a93 đạt; các commit tiếp theo xem CI riêng trên GitHub.
- **Dữ liệu hosting:** diễn tập nạp 500 sản phẩm CSV và 3 tài khoản vào DB mới riêng; có backup trước/sau, kiểm SQL độc lập và từ chối seed lại DB có dữ liệu.
- **Chuẩn bị HTTPS:** Compose hosting và Caddy validate đạt; credential sinh riêng trong thư mục private bị loại khỏi Git/build context. Chưa đăng ký/mua dịch vụ, cấp chứng chỉ hoặc public deploy.

**Dữ liệu hiện tại đã đổi theo yêu cầu:** website local dùng bản sao đầy đủ database cũ: 500 sản phẩm/500 ảnh, 11 tài khoản, 12 đơn, 9 giao dịch, giữ ID/mật khẩu/quan hệ. Baseline digest 20 bảng và từng byte 500 ảnh HTTP khớp; Chrome guest đạt. **Kiểm semantic 500 đã đạt:** 500 job done, 500 Product/2.500 quan hệ/500 vector 384 chiều, cả ba nguồn và Top 3 đối chiếu giá/tồn kho/graph paths. Xem `original-project-semantic-20261122.json`. Lượt sau login/logout đối chiếu 19 bảng và 13 bộ đếm ID, ghi rõ 1 phiên cũ bỏ/1 phiên mới; không restore đè phiên người dùng. Database gốc không bị ghi. Các kết quả 18/18 phía trên thuộc DB 5 fixture; chưa thay cho full role/write suite trên dữ liệu cũ. Xem thêm `original-project-data-readonly-20261122.json`, `original-project-browser-20261122.json`.

Backend mới nhất sau sửa SMTP TLS: **673 test/829 subtest đạt**; lượt AI mới nhất sau thêm mã lỗi nội bộ: **85 đạt/1 skip** (`ai-source-diagnostics-tests-20261122.json`). Không cộng các lượt thành một full suite giả; không công bố quality metrics khi chưa có người review 105 câu. SMTP thực chưa được cấu hình/gửi mail; đã kiểm mock rằng certificate lỗi không làm lộ credential.

Còn phải làm: nhận VPS/hostname được duyệt, đưa model và catalog 500 lên môi trường staging, kiểm HTTPS/SMTP/backup/fault trên server; toàn dependency fault matrix/load test; security scans; audit từng file; dữ liệu Style/Audience có nguồn, human benchmark, LLM narrative và báo cáo đồ án. Ollama/Qwen chưa bật trong bản demo này.

Bước của bạn: [hướng dẫn test, tài khoản và lựa chọn hosting](20-demo-test-and-hosting-next-steps.md). Trần ngân sách đã ghi nhận: **300.000đ cho một tháng demo**. Chưa cần gửi mật khẩu/token qua chat.

Docker data đã chuyển sang D, backup còn giữ. **Không xóa .local-tmp** vì đang chứa Docker VHD hoạt động, database, model và backup. Website/database cũ chưa bị chuyển sang bản mới.
