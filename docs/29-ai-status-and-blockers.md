# Trạng thái AI — cập nhật 24/11/2026

Mốc ontology/context mới nhất: code liên kết Category bằng embedding định nghĩa, làm rõ loại sản phẩm và lọc ID hợp điều kiện trước LIMIT graph đã có; 196 test chạy, 195 đạt/1 skip. Read-only graph A/B đạt 35/35 ứng viên hợp điều kiện so với 0/35 trước sửa. **Website chưa đạt: ReadTimeout ở câu đầu, warmup chưa sẵn sàng. Runtime phục hồi image checkpoint trước nâng cấp; không bật narrative mới.** Xem [báo cáo 38](38-ontology-linking-and-context-release.md) và các JSON bằng chứng kèm theo. Không đánh dấu hoàn thành hội thoại tự nhiên hoặc toàn bộ đặc tả.

Lượt semantic RAG 24/11 mới nhất: đã sửa nhánh bỏ qua intent `product_search` của bộ phân loại embedding và thêm bằng chứng graph/source deadline vào code. **Kiểm tra câu hỏi lạ qua website chưa đạt vì không lấy được catalog; runtime đưa về checkpoint trước lượt thử.** Không dùng số unit tests để khẳng định semantic accuracy. Xem [báo cáo 37](37-semantic-routing-and-graph-evidence.md); JSON planner suy sai và narrative thử nghiệm đều giữ tắt.

Cập nhật 24/11: Customer đã thêm so sánh/tham chiếu đúng mẫu vừa trả, đối chiếu lại giá và giữ điều kiện khi hỏi kiến thức xen giữa rồi đổi danh mục/ngân sách. Kiểm tra local 5/5 đạt; bộ offline 171 đạt/1 skip. Xem [báo cáo ngữ cảnh mới](36-contextual-product-discussion.md). Chưa coi đây là nghiệm thu chất lượng toàn bộ AI hoặc hosting.

Cập nhật Customer mới nhất: đã bật Qwen3 0.6B local và có câu trả lời model thật qua website, 3/3 kiểm tra kỹ thuật đạt. Xem [báo cáo model nhỏ](35-small-local-natural-dialogue.md) và `ai-small-dialogue-live-20261123.json`. Văn phong/làm theo hướng dẫn còn hạn chế; Staff/Admin LLM, benchmark chất lượng và hosting chưa nghiệm thu. Các kết quả Qwen 3B thất bại bên dưới được giữ làm lịch sử, không phải trạng thái của profile Customer mới.

**Chưa hoàn thành toàn bộ AI. Chưa nghiệm thu khả năng hội thoại tự nhiên như yêu cầu của người dùng.** Không dùng tổng số unit tests để khẳng định chất lượng tư vấn hoặc mức độ thông minh.

| Hạng mục | Đã kiểm chứng | Còn thiếu / lý do |
|---|---|---|
| Staff/Admin | API đúng route, kiểm quyền, công cụ SQL đếm đơn/tồn kho; Chrome 13 ca role/UI đạt ở mốc trước | Full write/checkout/payment UAT trên bản sao dữ liệu cũ |
| Catalog cũ | 500 sản phẩm, 500 ảnh khớp byte; 19 bảng và 13 sequence giữ nguyên khi đối chiếu | Đây không phải chấp thuận đưa thông tin khách hàng/đơn hàng lên hosting công khai |
| Retrieval | Qdrant 384/Cosine + Neo4j anchors, fusion, kiểm giá/tồn kho, Top-K đã có code và smoke thực tế | Chưa chứng minh relevance bằng ground truth người chấm; chưa calibrated reranker hoặc full semantic query planning public |
| Graph facts | UI Admin duyệt/thu hồi, evidence hash, projection graph/vector, replay và lọc đạt 8/8 QA | Catalog phục vụ vẫn 0 nhãn do người xác nhận; không được suy đoán nữ/phong cách/dịp từ tên/ảnh |
| Review outbox | Có API transaction enqueue và worker core thật | Bài nghiệm thu mở rộng bị Engine 502 rồi vượt 480 s; chưa tính là đạt HTTP→outbox→graph/vector cho review event |
| Hội thoại theo ngữ cảnh | Hỏi lý do/đính chính giữ kết quả cũ, không tự tìm bộ sản phẩm khác; Chrome 5/5 mốc trước | Test mới bổ sung Ruby definition cho ba role có kết quả riêng; chưa coi đó là chứng minh chất lượng Qwen |
| Câu hỏi kiến thức | API thật ba role trả đúng intent, không thêm sản phẩm; Staff vẫn đếm đơn đúng SQL, 4/4 checks | Đây là fallback khi LLM tắt, chưa phải câu trả lời kiến thức tự nhiên |
| Qwen | Có adapter local, giới hạn thời gian, fallback, QA độc lập và model cache kiểm SHA-256 | Hai lần nghiệm thu normal chưa đạt. Chưa chạy được các bước provider outage/recovery theo kịch bản sau normal; chưa full hybrid + LLM đồng thời |
| CI/Docker | Các image tách service; checkpoint `c8faea9` có 5 workflow thành công, gồm Neo4j integration riêng | Chưa public staging, full load/fault/security acceptance, hosting/domain/HTTPS |

## Các kết quả gần nhất

- Backend: 683 test, 833 subtest đạt, 19 cảnh báo deprecation. Log `.local-tmp/knowledge-routing-backend-tests.log`, không commit log riêng tư.
- AI/tools: 136 chạy, 135 đạt, 1 skip cần isolated graph server. `model-cache-safety-tests-20261123.json`. CI chạy bài graph riêng, không suy ra quality benchmark từ các test này.
- Dữ liệu: `original-project-reviewed-facts-20261123-r3.json`.
- Graph/vector QA: `reviewed-attributes-integration-20261123-r3.json`; các lần mở rộng r4/r5 chưa đạt được giữ riêng.
- Qwen: `qwen-dialogue-acceptance-20261123.json` và `qwen-dialogue-acceptance-20261123-r2.json` đều chưa đạt, các service đã tạm dừng được phục hồi running. Running không đồng nghĩa đã semantic-ready.
- CI: `reviewed-facts-ci-20261123.json`, đúng commit được ghi trong report; không coi đó là CI của các thay đổi chưa push.
- API phân luồng mới: `knowledge-routing-api-20261123-r2.json`, 4/4 đạt, không gọi model. Probe ad hoc đầu dùng stdin PowerShell ASCII nên không được dùng để kết luận về câu hỏi tiếng Việt; bản chạy lại từ file UTF-8 đã đạt.
- Chrome mới: `knowledge-routing-conversation-browser-20261123.json` chưa đạt điều kiện semantic readiness sau recreate. Không ghi 8/8 và không dùng kết quả cũ để khẳng định lượt khởi động mới đã ổn định.

## Vì sao bị kéo dài

Đã gặp Docker Engine HTTP 502, giới hạn process nghiệm thu bị vượt, và model warm-up không hoàn tất trong thời gian cho phép. Windows có 8.077.608 KiB RAM tổng; lúc thử Qwen đã quan sát chỉ còn 39.812 KiB khả dụng. Lệnh Docker info cũng vượt 25 s. Đây là các snapshot trong môi trường thiếu tài nguyên, không phải capacity benchmark hoặc bằng chứng rằng mọi lỗi đều chỉ do RAM.

Lần thứ hai sao chép 5 blob Qwen 3B (1.929.912.432 byte) vào volume QA riêng trên Docker data ổ D, kiểm SHA-256 theo manifest, không tải thêm model, không sửa cache gốc. Lần thử này vẫn chưa đạt; không tiếp tục tăng timeout hoặc bật mặc định Qwen trên bản phục vụ để che lỗi. Giữ volume và báo cáo phục vụ điều tra, không xóa dữ liệu.

## Gate trước hosting

1. Có câu trả lời Qwen thật cho cả ba role, giữ ngữ cảnh và không biến câu hỏi kiến thức thành product search.
2. Chạy cả hybrid retrieval và LLM cùng lúc trong ngân sách tài nguyên, kiểm thử outage/recovery và latency.
3. Người có trách nhiệm xác nhận facts và ground truth; benchmark/ablation, faithfulness và reranking có số liệu thật.
4. Hoàn tất kiểm thử nghiệp vụ, staging, secrets/backup, HTTPS và triển khai có rollback. Người dùng hiện chưa thuê VPS; không có public deployment.

Local: `http://127.0.0.1:18080`. Màn hình duyệt facts: `/pages/admin/product-attributes.html`, chỉ Admin có quyền. Chưa có sự xác nhận dữ liệu thì không tự tạo nhãn để đủ điều kiện tìm kiếm.

## Chốt phạm vi theo yêu cầu dừng lặp kiểm thử

Người dùng yêu cầu không tiếp tục chạy lặp, hoàn thiện tới mức có thể và bàn giao gấp. Không chạy thêm warm-up Qwen, benchmark hoặc full suite. Giữ code, test đã đạt, báo cáo lỗi và rollback; dừng container QA để nhường tài nguyên cho local. Chốt bản demo có giới hạn, không đánh dấu hoàn thành toàn bộ đặc tả hoặc đủ điều kiện hosting đầy đủ AI.
