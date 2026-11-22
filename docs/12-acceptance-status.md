# Đối chiếu đặc tả — cập nhật 22/11/2026

**Toàn dự án chưa hoàn thành.** Source mới chưa kích hoạt vào website đang phục vụ. Native tests không thay container tests; smoke predictions không phải benchmark chất lượng.

**Mốc 22/11 thay thế các gate Docker cũ trong bảng lịch sử:** Docker data đã chuyển D, có backup/checksum/rollback (`16-docker-storage-on-d.md`). Đã build 3 image và chạy 5 core containers. Full Chrome trên image trước: 17 đạt/1 skip Grafana. AI container outage: COD vẫn hoạt động, AI phục hồi có đối chiếu live. Worker dùng model thật và Qdrant HTTP container + PG/Neo4j native đã đạt retry/update/delete. Đó chưa là full Compose.

AI regression mới: 84 đạt/1 skip (`ai-limits-contract-final-20261122.json`); 3 SKU/Top-K smoke queries đạt trên image giới hạn nguồn. Browser subset mới: public recommendations đạt, Admin diagnostics timeout; cold-start đầu thiếu trường kết quả. Giữ các lỗi và gate chưa đóng, không ghi nghiệm thu thành công. Source/full worker image, monitoring containers, toàn fault matrix, human labels và remote deployment còn thiếu.

| Yêu cầu | Chứng cứ đã đạt | Gate còn thiếu |
|---|---|---|
| Audit, AS-IS/TO-BE/GAP | `00-audit-as-is.md`, inventory, baseline | Semantic review từng file |
| Giữ Customer/Staff/Admin | 671 backend tests/829 subtests; 18/18 Chrome, 0 skip/flaky, DB test migration thật | Deployment qua proxy/container; UAT |
| CSV → Neo4j Python | 500 sản phẩm, 2.500 cạnh, 2 lần import, 6 constraints, không duplicate; graph sample export bằng code | Container/máy sạch, ảnh Neo4j Browser minh họa |
| Vietnamese linking | Alias/context/ambiguity, optional encoder, references theo ID/tên duy nhất | Fact Audience/Style, unseen-synonym human evaluation |
| Qdrant semantic | MiniLM pinned revision, 384 chiều/COSINE, versioned index, 500 sản phẩm | Qdrant server/container runtime |
| Hybrid, Top-K, graph | RRF + actual graph paths; Business HTTP/PG kiểm giá/tồn kho giữa query | Human relevance labels; graph-feature reranker mới opt-in |
| Grounding | Deterministic cards từ dữ liệu live, không tạo giá/tên/fact | LLM narrative và groundedness evaluation |
| RBAC/diagnostics | Guards + browser guest/customer/staff/admin; internal diagnostics token | Analytics/AI role acceptance toàn deployment |
| Sync | PG 7 checks; PG/Neo4j native → Qdrant HTTP container/model thật retry/update/delete | Worker image/full Compose; chưa bật DB cũ |
| Docker độc lập | Engine/data D có backup; 3 images và 5 core containers qua proxy | Worker image, toàn Compose/fault matrix |
| Fault isolation | Dừng process/container AI: catalog/login/COD/role guard đạt, AI phục hồi | Toàn dependency matrix; cold-start/repeated requests |
| Monitoring | Prometheus scrape 2 API + Grafana/dashboard/Chrome screenshot; worker queue thật | Container deployment, host/disk/restart metrics, alert baseline |
| CI/CD | Backend/AI/graph/PG/browser workflows; chọn build theo path | Chưa chạy GitHub; scan/publish/staging/approval pipeline |
| Backup/hosting | pg_dump/restore test 22 bảng/invariants; target/checksum guard; runbook | Production restore; host/domain/budget/HTTPS chưa phê duyệt |
| Evaluation | 105 câu draft, 5-mode runner/525 smoke predictions, scorer, latency smoke chart | 0 human-reviewed labels; chưa quality scores/controlled comparison |
| Báo cáo bảo vệ | Schema/ingest/retrieval/sync/deploy/demo; graph export/dashboard image | ERD/UML/report hoàn chỉnh, metric và demo bắt buộc chưa đủ dữ liệu |

Chứng cứ chính:

- `native-public-recommendation-browser-final-20261121.json`: migration head `20261121_0009`, 18/18 Chrome và native AI outage; public recommendation không tin client customer identity.
- `live-business-model-graph-retrieval-20261121.json`: Business HTTP/PG 500 CSV-seeded products, model thật, graph thật, cập nhật giá/tồn kho giữa query.
- `postgres-worker-metrics-integration.json`, `postgres-graph-vector-integration.json`: sync và queue exporter.
- `backup-restore-guard-final-20261121.json`: restore synthetic fixtures và worker backup-reference guard, không production.
- `ai-public-adapter-verified-final-20261121.json`, `backend-regression-latest-20261121.json`, `current-implementation.json`: test và trạng thái hiện tại.
- `ablation-smoke-20261121/summary.json`: smoke trước reference-query mới, không là nghiệm thu chất lượng hiện tại.


Không cần quyền bổ sung để đọc/sửa/test cách ly đã được giao. Production writes, thay secrets, public deploy, chi phí và thay đổi Docker storage hiện có chỉ làm khi được phê duyệt rõ ràng.

Mốc kiểm tra tiếp theo 22/11: `compose-ai-container-fault-final-20261122.json` đạt trên image mới. `compose-browser-budget-final-20261122.json` có Admin đạt nhưng API gợi ý lỗi; subset chưa đạt ổn định. Chưa đóng cold-start/catalog failure gate. Chi tiết: [17-compose-test-runtime.md](17-compose-test-runtime.md).
