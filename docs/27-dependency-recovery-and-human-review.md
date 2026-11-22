# Phục hồi dependency và bộ gán nhãn dữ liệu cũ — 22/11/2026

## CURRENT / CHANGE

Checkpoint trước thay đổi: `a7a5c46`, nhánh riêng `rebuild/lumiere-demo-20261122`. Năm workflow CI của checkpoint đạt (`dense-anchor-ci-20261122.json`). Chưa deploy công khai.

Fault test PostgreSQL đầu tiên cho thấy API chờ quá lâu, trong khi diagnostic AI đã trả 503. Bản sửa:

- `backend/app/core/database.py`: giới hạn connect/pool wait mặc định 3 giây, cấu hình trong khoảng 1–30 giây. Compose và `.env.example` chuyển tiếp hai biến `DATABASE_CONNECT_TIMEOUT_SECONDS`, `DATABASE_POOL_TIMEOUT_SECONDS`.
- `backend/app/main.py`: OperationalError, InterfaceError và pool timeout trả 503 + Retry-After, không xuất SQL/parameters/driver message. Không bắt IntegrityError bằng handler này; logic auth/order/payment giữ nguyên.
- `scripts/fault_injection.py`: kiểm tra dense/graph và live filters trong lúc dependency tắt, quan sát semantic recovery; có budget baseline/recovery rõ ràng. Nếu baseline không khỏe, lưu report và không tắt container. Luôn bật lại container đã dừng trong finally.

## TEST

| Kiểm tra thật | Kết quả / phạm vi |
|---|---|
| Backend toàn bộ | 680 passed, 829 subtests; 13 deprecation warnings. SQLite memory/network guards; không kết nối DB thật trong unit tests |
| AI/tool contracts cuối lượt | 118 tests, 117 passed/1 skipped; không lỗi. Không là benchmark chất lượng model |
| Chrome sau bản sửa 503 | 13/13 role/UI cases, `postgres-control-roles-browser-20261122.json` |
| AI container tắt | Website/business API tiếp tục 200; AI health 502; HTTP phục hồi 28,9 giây. Không là checkout hoặc semantic-quality test |
| Qdrant tắt | Graph còn 19 ứng viên, trả 3 sản phẩm hợp live filters; cả hai nguồn phục hồi sau 20,7 giây |
| Neo4j tắt | Dense còn 19 ứng viên, trả 3 sản phẩm hợp live filters; lần đầu chưa phục hồi trong 60 giây. Lần đo budget 180 giây phục hồi 115,6 giây |
| PostgreSQL tắt sau sửa | Frontend/live API còn 200; readiness và products trả 503; AI diagnostic 503. Retrieval phục hồi 12,4 giây |
| Sau toàn bộ outage | `post-fault-full-recovery-20261122.json`: 8/8 checks, dense/graph, filters, context, 500 jobs done |

Report chưa đạt được giữ nguyên: `dense-anchor-fault-neo4j-20261122.json`, `dense-anchor-fault-postgres-20261122.json`. Report sau sửa/đo lại có hậu tố `r2`. Không đổi kết quả cũ thành pass. Trường hợp preflight không khỏe đã dừng trước khi tắt service; guard được unit test.

Chưa chạy fault với Ollama hoạt động thật. Mốc HTTP recovery không thay cho semantic recovery; thời gian này là số đo local trong môi trường đang phát triển, không phải SLA hay so sánh hiệu năng có kiểm soát.

## COMPATIBILITY / DATA

`original-project-after-faults-20261122.json` đối chiếu bản phục vụ với clone audit network=none/default_transaction_read_only=on:

- 19 bảng nghiệp vụ giữ nguyên toàn bộ digest dòng; 13 ID sequences giữ nguyên.
- 13 session gốc còn tồn tại không thay đổi; một session bị đăng xuất và một session mới từ thao tác đăng nhập trước đó được phân biệt, không ghi đè session để ép khớp.
- Catalog 500 sản phẩm; 500 ảnh qua HTTP khớp byte với file gốc.
- Không reset tài khoản, không export private rows. Nguồn PostgreSQL cũ vẫn stopped. Clone audit đã stop lại sau đối chiếu.

## HUMAN REVIEW

Người dùng xác nhận chưa có bảng nhãn. `prepare_human_review_kit.py --source original-api` đã xuất đúng 500 sản phẩm từ API của bản sao database cũ, không dùng nhầm CSV seed. Source adapter chỉ dùng endpoint loopback; snapshot/CSV có whitelist trường công khai và chống công thức CSV. Không ghi DB, không tự xác nhận nhãn/reviewer và không ghi đè bộ người dùng đang làm.

Folder local: `.local-tmp/human-review-original-20261122/`.

1. Mở `catalog-for-human-review.csv` bằng Excel UTF-8; cột `product_url` mở ảnh/chi tiết.
2. Chỉ điền các sản phẩm có thể xác nhận. `audience_proposal`: female/male/child_female. `style_proposal`: elegant/minimalist/refined. Nhiều nhãn cách nhau bằng `|`.
3. Ghi evidence_source, reviewer, reviewed_at; approved=true sau khi thực sự đánh giá. Chưa biết thì để trống.
4. `queries-for-human-review.csv` gồm 105 câu dự thảo, không có ground truth tự sinh. Gán relevance theo snapshot và chia validation/test trước khi tính metric.

Hiện có **0 sản phẩm/0 câu được người đánh giá xác nhận**. Bảng này chuẩn bị input cho bước review/import; chưa tự nối nhãn vào graph hoặc bộ lọc. Không công bố precision/recall/MRR/nDCG khi chưa có labels hợp lệ. Manifest: `human-review-original-20261122.json`.

## RISK / ROLLBACK / NEXT

Giữ nguyên persistent volumes và backup trên D. Nếu cần rollback source, revert checkpoint của thay đổi này rồi build/recreate riêng business-api/index-worker, cùng các override đang dùng. Không rollback PostgreSQL bằng cách xóa volume; thay đổi timeout/503 không có migration dữ liệu.

Vẫn cần hoàn thiện reviewed facts xuyên catalog/outbox/graph/filter, public semantic planning, Qwen hội thoại thật, calibrated ranking/ground-truth evaluation và hosting/staging/HTTPS. Người dùng chọn tiếp tục local, chưa thuê VPS; không mua dịch vụ hoặc thay lựa chọn provider tự động.
