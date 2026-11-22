# Dense → graph và phục hồi sau khi máy tắt ngang

Ngày: 22/11/2026. Baseline trước sửa: `0684da5`, nhánh `rebuild/lumiere-demo-20261122`.

## CURRENT / CHANGE

Audit nền nằm trong `25-master-spec-runtime-audit.md`; inventory 313 file chưa phải chứng nhận review đầy đủ từng file. Các kết luận AS-IS trong audit mô tả baseline trước thay đổi dưới đây.

- `shared/retrieval_limits.py`: thêm budget riêng cho warmup; vẫn dùng cùng worker, khóa single-flight, bỏ kết quả trễ và circuit breaker. Không tạo hàng đợi thứ hai.
- `AI/jewelry_agents/retrieval.py`: khóa chống nạp trùng model; warmup tối đa 60 giây ở background. Truy vấn thường giữ mặc định 3 giây; override demo Windows dùng 6 giây, cấu hình chỉ chấp nhận 1–10 giây. Đây là điều chỉnh vận hành, chưa chứng minh hết lỗi cold start.
- Thêm Neo4j expansion từ các ID ứng viên dense thật. Cypher có tham số, chỉ qua Category/Material/Gemstone đã tồn tại. Tối đa 6 paths cho mỗi ứng viên để giới hạn payload. Không ghi thêm node/cạnh.
- `search_service.py`: đối soát cả source/candidate của path với catalog hiện tại, hợp nhất vào một nhánh graph để tránh tính hai phiếu graph; RRF, dedup, lọc và Top-K vẫn được giữ. Kiểm lại path sau lần đọc catalog cuối. Reference-product traversal cũ được giữ.
- Customer RAG và diagnostics dùng adapter mới; lý do gợi ý có thể chỉ ra quan hệ và anchor ID thật. Không khẳng định birthday là thuộc tính được chứng nhận của sản phẩm.
- `scripts/verify_dense_graph_runtime.py`: kiểm thử đọc dữ liệu thật, không xuất credentials hoặc dữ liệu tài khoản.

## TEST / COMPATIBILITY

Offline AI suite đã chạy 107 tests: 106 đạt, 1 skip, 0 failures/errors. Test mới bao gồm single-flight khi startup vượt budget thường, dense anchors, path giả/sai ID, graph/dense outage, duplicate và thuộc tính source đổi trước khi trả lời.

Lượt live đầu sau khởi động lại đạt 6 checks tại lần thăm dò thứ 5: ba truy vấn birthday/Top-3 nhẫn dưới 8 triệu/Top-5 bông tai có dense+graph; birthday có anchor paths; hội thoại giải thích/đính chính giữ đúng danh sách. Những lần trước đó có in-flight/timeout/cooldown hoặc probe lỗi, được giữ trong report. Không coi kết quả warm này là chứng minh cold start ổn định.

Lượt Chrome tiếp theo chưa vượt qua readiness tìm kiếm. Không đánh dấu lượt này đạt. Số đo riêng truy vấn `nhẫn` sau đó: dense 2,251 giây, graph 1,429 giây, tổng 4,682 giây; RAM host chỉ còn khoảng 440 MiB. Budget demo 6 giây được thêm sau các số đo này. Kết quả nghiệm thu bản cuối phải được ghi riêng, không ghi đè report thất bại.

Không đổi schema PostgreSQL, tài khoản gốc, đơn hàng, payment/auth, ảnh hoặc dữ liệu nguồn. QA dùng bản sao và tài khoản QA đã có. Trong kiểm thử có tạm dừng index-worker để giảm tải; cần bật lại trước khi bàn giao và kiểm tra backlog.

## RISK / NEXT

Chưa hoàn thành toàn dự án. Các mục còn mở:

1. Cold/repeated/concurrent availability và Chrome đủ ba vai trò trên bản cuối; đầy đủ fault matrix sau thay đổi.
2. Qwen chạy thật và hội thoại tự nhiên cả ba vai trò: adapter có nhưng chưa live acceptance; không được mô tả là tương đương ChatGPT.
3. Reviewed Audience/Style/Occasion chưa nối xuyên catalog → worker → graph/vector → lọc. Không tự gán các fact này cho 500 sản phẩm.
4. Semantic entity linking public và typed planning cần hoàn thiện/đánh giá; reranking chưa được hiệu chỉnh trên ground truth.
5. Benchmark relevance có nhãn người đánh giá và ablation; chưa có bằng chứng định lượng graph cải thiện chất lượng.
6. Hosting chưa có VPS/IP/domain; chưa provision, chưa deploy public hoặc nghiệm thu HTTPS. Không mua dịch vụ khi chưa có giá cuối được duyệt trong ngân sách 300.000đ/tháng.

## ROLLBACK

Giữ checkpoint Git trước khi phát hành. Nếu cần quay lại source, revert commit thay đổi này trên nhánh mới rồi build/recreate riêng `ai-api` bằng cùng `compose.yaml` và `compose.original-data.yaml`. Không dùng `reset --hard`, `down -v` hoặc đụng vào Docker VHD/backup. Thay đổi này không có migration/data import nên không cần rollback database. Giữ nguyên volumes và bộ backup dữ liệu cũ trên D.

## Lệnh tái lập

```powershell
python -B scripts/run_ai_tests.py --report .local-tmp/ai-contract-new.json
python -B scripts/verify_dense_graph_runtime.py --report .local-tmp/dense-graph-new.json
$env:NODE_PATH='D:\LUMIERE-FINAL-TEST\.local-tmp\browser-tools\node_modules'
node scripts/browser/verify-conversation.cjs .local-tmp/original-db-20261122-014434/ai-acceptance/fixture.json .local-tmp/conversation-new.json
```

Lệnh browser cần QA services trên 18081. Không copy fixture chứa thông tin đăng nhập lên Git. Python cần môi trường test đã cài dependencies; lệnh không tự tải model.

## Bổ sung tối ưu worker

Sau khi bật máy, trạng thái thực tế là 8 done / 491 pending / 1 processing. Nguyên nhân requeue là `--reconcile` trong command khởi động trước đây. Override demo nay chỉ `--watch`; full reconciliation vẫn có thể chạy chủ động bằng CLI gốc có backup reference.

`vector_index.py` bổ sung cache replay tùy chọn, được worker bật: chỉ tái sử dụng point khi fingerprint/model/revision, metadata và source digest đều khớp; vector phải đúng dimension, hữu hạn và khác zero. Dữ liệu đổi, point mất hoặc sai contract buộc encode lại. Đây là kiểm tra tính nhất quán cache, không chứng minh mọi vector có metadata hợp lệ đều không thể bị sửa trái phép. Import CSV mặc định vẫn encode mới.

`graph_writer.py` kiểm tra uniqueness schema bằng một lần SHOW CONSTRAINTS trước khi tạo phần thiếu. Constraint có cùng tên nhưng sai label/property/type bị từ chối trước thao tác tạo mới. Không bỏ validation graph hoặc quản lý ownership.

`run_index_worker.py` chỉ nạp encoder khi có pending/processing jobs, trước khi claim lease; giải phóng tham chiếu model khi hết việc. Trong lượt chạy thực, log đã tới product_id 500, generation 3, delivered/acknowledged true. Cần xác nhận aggregate backlog sau restart riêng, không suy ra mọi job đều done chỉ từ log sản phẩm cuối.

Kiểm thử mới: 111 AI tests (110 đạt, 1 skip), 15 backend tests về product-index/outbox đạt, 660 bài khác không chạy lại trong lượt kiểm tra backend này. Report có tên `dense-anchor-worker-tests-20261122.json`. Kết quả live được lưu cả bản chưa đạt và bản phục hồi; không dùng quality metrics từ những smoke tests này.

Sau build/restart cuối: outbox `done: 500`, không pending/processing và oldest pending null; worker không xếp lại 500 jobs. RAM worker ở lần đọc là 179,2 MiB. `dense-anchor-runtime-final-20261122.json` đạt 8/8 checks trên dữ liệu thật, gồm backlog sạch, dense/graph, budget/stock và giữ ngữ cảnh. Đây vẫn là smoke test sau khi sẵn sàng, không phải benchmark độ thông minh hoặc chứng minh cold/concurrent load đã ổn định.

Chrome thật sau tối ưu đạt 5/5 ca hội thoại Customer/Staff/Admin (`dense-anchor-conversation-browser-20261122.json`), readiness cả QA và model đều ở lần thử đầu. Không mock API, không chèn config trình duyệt và không thay tài khoản gốc. Lượt thất bại readiness trước đó vẫn được nêu ở phần TEST; kết quả mới không xóa giới hạn cold start hoặc thay cho Qwen live acceptance.

`dense-anchor-roles-browser-20261122.json` đạt thêm 13/13 ca trên QA: đăng nhập cả ba role; guest/customer/staff bị chặn đúng quyền; Staff trả số đơn chờ khớp SQL; Admin đếm 500 sản phẩm; widget Customer hiển thị Top-3/Top-10 có ảnh/link/stock; lỗi mạng chat không làm mất catalog. Đây không phải kiểm thử checkout/payment ghi đơn mới trên dữ liệu cũ.
