# LUMIÈRE — tiến độ ngày 22/11/2026

**Bạn có thể test bản demo local ngay tại http://127.0.0.1:18080. Toàn bộ đồ án chưa nghiệm thu xong; hosting chưa triển khai.**

Đã đạt:

- **10 container chạy cùng nhau:** frontend, proxy, Business API, AI API, PostgreSQL, Neo4j, Qdrant, worker, Prometheus và Grafana. Đủ 4 image ứng dụng build riêng.
- **18/18 ca Chrome đạt, không skip/flaky**, gồm Customer/COD, Staff/Admin, reset mật khẩu, chẩn đoán AI, gợi ý và dashboard Grafana thật.
- **Retrieval dùng đủ lexical + dense + graph:** model MiniLM thật có revision cố định, graph paths được xác minh, kết quả khớp giá/tồn kho Business API.
- **Đồng bộ thật sau checkout:** outbox generation 2 đã delivered, tồn kho Neo4j khớp Business, Prometheus scrape được cả hai API và worker.
- **GitHub:** đã push nhánh mới rebuild/lumiere-demo-20261122, không merge nhánh cũ. Năm workflow trên commit nền 2ad4a93 đạt; các commit tiếp theo xem CI riêng trên GitHub.
- **Dữ liệu hosting:** diễn tập nạp 500 sản phẩm CSV và 3 tài khoản vào DB mới riêng; có backup trước/sau, kiểm SQL độc lập và từ chối seed lại DB có dữ liệu.
- **Chuẩn bị HTTPS:** Compose hosting và Caddy validate đạt; credential sinh riêng trong thư mục private bị loại khỏi Git/build context. Chưa đăng ký/mua dịch vụ, cấp chứng chỉ hoặc public deploy.

Lưu ý dữ liệu: website local hiện dùng **5 sản phẩm giả**, đã index thành 5 Product/25 cạnh/5 vector 384 chiều. DB 500 sản phẩm là bước chuẩn bị riêng, chưa chuyển vào website/graph/vector hosting. Bằng chứng CSV → Neo4j 500 sản phẩm/2.500 cạnh và import hai lần thuộc lab trước, không trộn các số liệu này.

Backend mới nhất sau sửa SMTP TLS: **673 test/829 subtest đạt**; AI 84 đạt/1 skip ở lượt riêng. Không cộng các lượt thành một full suite giả; không công bố quality metrics khi chưa có người review 105 câu. SMTP thực chưa được cấu hình/gửi mail; đã kiểm mock rằng certificate lỗi không làm lộ credential.

Còn phải làm: nhận VPS/hostname được duyệt, đưa model và catalog 500 lên môi trường staging, kiểm HTTPS/SMTP/backup/fault trên server; toàn dependency fault matrix/load test; security scans; audit từng file; dữ liệu Style/Audience có nguồn, human benchmark, LLM narrative và báo cáo đồ án. Ollama/Qwen chưa bật trong bản demo này.

Bước của bạn: [hướng dẫn test, tài khoản và lựa chọn hosting](20-demo-test-and-hosting-next-steps.md). Trần ngân sách đã ghi nhận: **300.000đ cho một tháng demo**. Chưa cần gửi mật khẩu/token qua chat.

Docker data đã chuyển sang D, backup còn giữ. **Không xóa .local-tmp** vì đang chứa Docker VHD hoạt động, database, model và backup. Website/database cũ chưa bị chuyển sang bản mới.
