# LUMIÈRE: tiến độ thực tế ngày 22/11/2026

**Đã có code và kiểm thử thật; toàn bộ đồ án chưa hoàn thành.** Website và database cũ chưa được chuyển sang bản mới.

**Mốc demo mới nhất:** đã tạo nhánh `rebuild/lumiere-demo-20261122`, chưa merge nhánh cũ. Image worker build đã đạt sau khi dùng cache AI, hiện đủ 4 image riêng. Full Chrome container mới nhất đạt **17 ca, 1 skip Grafana, 0 lỗi/flaky** (`compose-demo-full-browser-r2-20261122.json`); 9 lượt đọc nội bộ cũng đạt. Các lỗi/runtime build phía dưới là lịch sử trước mốc này, vẫn giữ report. Phần full semantic/monitoring Compose và hosting còn thiếu. [Phạm vi nhánh demo](19-demo-release-20261122.md).

Đã làm được:

- **Docker chạy lại và dùng ổ D:** backup VHD độc lập, đối chiếu SHA-256, chuyển data và kiểm tra giữ nguyên container/image/volume tại mốc chuyển. C hiện còn khoảng 16,42 GiB. Backup vẫn giữ trên D. [Bằng chứng và rollback](16-docker-storage-on-d.md).
- **Bản thử container:** frontend, Business API và AI API đã build; 5 container chạy tại http://127.0.0.1:18080 với 5 sản phẩm giả. Full Chrome trên image trước đạt 17 ca, bỏ qua 1 ca Grafana. Chưa phải toàn bộ Compose 11 service.
- **AI hỏng không làm dừng đặt hàng:** thực sự dừng AI container; đăng nhập, COD, đọc đơn và phân quyền vẫn đạt. Khởi động lại AI trả sản phẩm khớp giá/tồn kho Business API. [Báo cáo trên image mới](compose-ai-container-fault-final-20261122.json).
- **CSV → Knowledge Graph:** Python kiểm tra 500 sản phẩm, tạo 2.500 cạnh taxonomy, import hai lần không trùng; 6 constraints và graph paths thật.
- **Semantic/hybrid/Top-K:** linking tiếng Việt, MiniLM có revision cố định, lexical/dense/graph RRF, tham chiếu sản phẩm và kiểm giá/tồn kho live. Có sửa SKU chính xác và tránh nhầm số Top-K thành SKU. Chưa khẳng định chất lượng ranking khi chưa có human labels.
- **Worker đồng bộ model thật:** PostgreSQL/Neo4j native và Qdrant HTTP container 1.18.3 đã đạt retry sau lỗi graph, vector identity ổn định, cập nhật giá/tồn kho, xóa/tombstone. [Báo cáo](qdrant-named-volume-real-model-worker-20261122.json). Chưa phải worker chạy toàn bộ trong Compose, chưa bật trên DB cũ.
- **Kiểm thử nền:** backend 671 test/829 subtest đạt; native Chrome 18/18. AI mới nhất 84 đạt/1 skip, thêm 8 backend checks liên quan đạt. Đây là các lượt riêng, không cộng thành một full suite mới.
- **Giám sát/phục hồi/evaluation:** Prometheus/Grafana native và worker queue metrics thật; pg_dump/restore DB test đối chiếu 22 bảng đạt. SQL baseline đạt 5 PostgreSQL checks. Có 105 câu draft, 525 smoke predictions và scorer; chưa có quality metrics.

**Lỗi còn mở:** ba truy vấn smoke trên image giới hạn nguồn đã đạt, nhưng lượt cold-start đầu thiếu trường kết quả. Browser subset mới có một lượt public recommendations đạt/Admin timeout; lượt sau Admin đạt/API gợi ý lỗi. Chưa ổn định nên chưa nghiệm thu runtime. Giữ nguyên các báo cáo thất bại, timeout API/proxy không bị tăng để che lỗi.

Build image worker đã hết ngân sách 20 phút ở bước cài dependencies (`docker-worker-image-20261122.json`, exit 124); chưa có image được nghiệm thu. Windows có khoảng 8 GB RAM, trống khoảng 54 MB lúc đo, Docker CLI cũng từng timeout. Đã dừng đúng Neo4j lab để giảm tải và giữ dữ liệu graph, không đóng ứng dụng của bạn. Chưa kết luận mọi lỗi đều do RAM.

**Còn phải làm:** đóng lỗi runtime; audit ngữ nghĩa từng file; build/run worker và full Compose graph/dense/monitoring; dependency fault matrix; human benchmark/tuning; LLM narrative có grounding; CI remote/security scans; hosting/HTTPS; báo cáo/UML đầy đủ.

Bạn có thể hỗ trợ bằng người review sản phẩm/105 câu, rubric của trường và thông tin hosting/repository khi đến bước đó. Human review kit đã xuất tại .local-tmp/human-review-kit-20261122/. Không cần tự viết code hoặc mở lại Docker. [Danh sách thiếu, lý do và phần cần hỗ trợ](15-remaining-work-and-user-support.md), [checklist nghiệm thu](12-acceptance-status.md), [hướng dẫn bản thử](17-compose-test-runtime.md), [trạng thái tổng hợp](current-implementation.json).

**Không xóa .local-tmp: đang chứa Docker data hoạt động và backup.** Model, binary, cache và dữ liệu test mới đều nằm trên D. Chưa push, public deploy, đổi secrets hoặc migrate DB cũ.
