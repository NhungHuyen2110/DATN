# Đối chiếu đặc tả — cập nhật 23/11/2026

**Toàn dự án chưa hoàn thành.** Website local `http://127.0.0.1:18080` đã dùng bản sao đầy đủ database cũ và AI mới. Chưa có Qwen hội thoại chạy thật hoặc hosting công khai. Smoke tests không phải benchmark chất lượng.

Đọc bảng trạng thái và lý do chưa đạt tại [Trạng thái AI](29-ai-status-and-blockers.md). Hai lần nghiệm thu Qwen local chưa đạt; giữ model tắt trên bản phục vụ. Checkpoint `c8faea9` đã có 5 workflow CI thành công (`reviewed-facts-ci-20261123.json`).

## Trạng thái mới thay thế các gate lịch sử phía dưới

- Luồng nhãn được xác nhận: backend mới 683 tests/833 subtests đạt; AI/tools 136 run, 135 đạt/1 skip; Chrome QA 7/7; graph/vector/encoder thật QA 8/8, gồm replay và thu hồi. Flag đã bật trên bản sao local, 500 sản phẩm PG/graph/vector, outbox 500 done, review store 0. Chưa có ground truth người duyệt cho catalog. Xem `28-reviewed-product-facts.md`; lỗi readiness sau rollout và kiểm tra hội thoại được giữ bằng report riêng.
- Người dùng chưa thuê VPS và chọn tiếp tục hoàn thiện local; chưa có public staging/HTTPS.
- Đã push checkpoint `f4a7a6a` lên `rebuild/lumiere-demo-20261122`; năm workflow của mốc `a7a5c46` đạt, không merge nhánh cũ. Thay đổi mới chỉ tính đã push/CI sau khi có commit và kết quả riêng.
- Bản sao dữ liệu cũ có đủ 500 sản phẩm/ảnh, 11 tài khoản, 12 đơn, 15 dòng đơn và 9 giao dịch; nguồn và backup được giữ nguyên.
- Runtime dense → Neo4j anchor expansion → RRF/filter/live recheck → Top-K đạt 8/8 checks. Outbox 500 done sau restart, không requeue toàn bộ.
- Chrome thật đạt 13 ca role/UI và 5 ca context; Staff trả số đơn đúng SQL, Admin đếm 500 sản phẩm, Customer hiển thị Top-3/Top-10. Đây chưa là full write/checkout/payment UAT trên dữ liệu cũ.
- Local backend mới 680 tests/829 subtests đạt; AI/tool contracts mới 118 tests, 117 đạt/1 skip. Bản sửa DB timeout/503 đã qua container fault và 13 ca Chrome.
- AI/Qdrant/Neo4j/PostgreSQL outage và phục hồi đã có report riêng. Giữ lần Neo4j chưa đạt 60 giây và PostgreSQL timeout trước sửa; không coi là full fault matrix khi Ollama chưa chạy thật.
- Còn thiếu: semantic audit đủ từng file; public semantic planning/entity linking hoàn chỉnh; facts Audience/Style/Occasion có evidence; Qwen live; calibrated reranker; human ground truth/ablation; full fault/load/security/staging/hosting/TLS acceptance.

Chứng cứ: `25-master-spec-runtime-audit.md`, `26-dense-anchor-recovery.md`, các report `dense-anchor-*`, `current-implementation.json`. Xem [Test và bước hosting](20-demo-test-and-hosting-next-steps.md). Ngân sách hosting tối đa 300.000đ/tháng; chưa có VPS/IP/domain và chưa public deploy.

## Các mốc và bảng gate lịch sử

**Mốc mới nhất 22/11:** 10 container demo, 4 image riêng; Chrome **18/18, không skip/flaky**. Có model thật, ba nguồn lexical/dense/graph, 5 job hoàn tất và đồng bộ checkout generation 2. Prometheus có 3 target up, Grafana có ảnh thật. Nhánh GitHub mới đã push; 5 workflow commit `2ad4a93` đạt. Bootstrap 500 CSV/3 user ở DB mới riêng, backup và guard không overwrite đạt. Compose/Caddy hosting validate đạt nhưng chưa public deploy. Các gate cũ phía dưới là lịch sử; audit, human benchmark, LLM, hosting, full fault matrix và security scans vẫn mở. [Test và bước hosting](20-demo-test-and-hosting-next-steps.md).

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
