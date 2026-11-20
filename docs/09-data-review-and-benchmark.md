# Rà soát dữ liệu và benchmark có người duyệt

Theo chỉ dẫn bổ sung của người dùng, thiếu nhãn không chặn CSV/graph/vector/hybrid.
Không có human gold benchmark hiện tại. Các file dưới đây là ứng viên cần duyệt.

| Hạng mục | Trạng thái | Bằng chứng/giới hạn |
| --- | --- | --- |
| 500 sản phẩm CSV, ID/name taxonomy | VERIFIED | 6 category, 4 brand, 5 material, 6 gemstone, 5 collection; không có reference mismatch |
| Audience/Style/Occasion của 500 sản phẩm | PENDING_REVIEW | 0 fact có bằng chứng; không có description trong CSV |
| Nhãn nguồn qua PostgreSQL live | BLOCKED | Chưa có AI_DATABASE_URL chỉ đọc riêng; chưa kiểm nội dung DB live |
| Schema products trong code/migrations | VERIFIED trong code | Không có description/published/Audience/Style/Occasion; không chứng minh DB deploy hiện tại |
| 136 câu benchmark | PENDING_REVIEW | 0 approved; không có quality metrics |
| Evaluator/review gates | VERIFIED chức năng | Tests và chạy inspect; không phải relevance score của AI |

## Duyệt nhãn sản phẩm

Mở [product-label-review.csv](review/product-label-review.csv) bằng Excel nhập UTF-8
hoặc công cụ CSV giữ nguyên JSON/text. Mỗi dòng là một sản phẩm gốc; source hash/row/SKU
giữ nguyên. File không chứa giá vốn, giá sỉ hoặc dữ liệu khách hàng.

1. Điền `candidate_audience`, `candidate_style`, `candidate_occasion` bằng canonical ID
   trong `AI/config/aliases_vi.json`, chỉ cho các thuộc tính có nguồn đáng tin.
2. Với thuộc tính đã điền, bổ sung `*_evidence`, `*_evidence_field`, `*_confidence` (0..1).
   Evidence phải là span có thật trong field nguồn. Nếu người có trách nhiệm cung cấp
   một nhãn nghiệp vụ mới, dùng field `human_review`, evidence cụ thể và review_notes
   giải thích căn cứ. Không dùng confidence cao thay cho evidence/phê duyệt.
3. Điền reviewer, review_notes; đổi `review_status` thành APPROVED hoặc REJECTED.
   Để PENDING_REVIEW khi thiếu căn cứ. Không đồng loạt APPROVED chỉ để đạt số lượng.

Không có mô tả trong CSV hiện tại nên generator **không tự đề xuất** Audience/Style/Occasion.
Tên như Angel/Rose Gold và collection Minimal/Wedding không được dùng làm fact optional.
Chưa gọi LLM tạo candidates; nếu bổ sung extractor về sau, nó phải xuất evidence span,
confidence, provenance và PENDING_REVIEW qua cùng gate, không được nối trực tiếp fact graph.

```powershell
# Chỉ sau khi thực sự duyệt; output bắt buộc là file mới, không ghi đè nguồn.
.venv/Scripts/python.exe scripts/export_reviewed_labels.py --source output/products_ai.csv --review docs/review/product-label-review.csv --output .cache/products-reviewed.csv
.venv/Scripts/python.exe AI/sync_catalog.py --file .cache/products-reviewed.csv --dry-run --report .cache/reviewed-validation.json
```

Exporter bỏ mọi dòng chưa duyệt, kiểm source hash/SKU/canonical/evidence/reviewer,
ghi review SHA256 + source SHA256 trong provenance và validate CSV mới trước publish.
Không có approved facts thì exit 2, không tạo output. Script không import Neo4j/PostgreSQL.
Tiếp theo operator kiểm tra diff và chọn target test/staging rõ ràng theo runbook ingestion.

## Duyệt benchmark

[benchmark-candidates.csv](review/benchmark-candidates.csv) có 136 câu tiếng Việt,
đủ synonym/paraphrase/entity linking/multi-constraint/graph/Top-K/SKU/availability/
ambiguity/authorization và routing. Tất cả PENDING_REVIEW, reviewer để trống.
Các cột bắt buộc đúng yêu cầu: query_id, query, expected_intent, expected_entities,
expected_product_ids, hard_constraints, expected_graph_evidence, reviewer, review_status.
Có thêm top_k, cohort, candidate_product_ids, review_notes phục vụ rà soát.

`expected_entities`, `hard_constraints`, `expected_graph_evidence` ban đầu là **đề xuất**.
`candidate_product_ids` chỉ là gợi ý thuộc tính sơ bộ; không phải ranking hay relevant IDs.
`expected_product_ids` thường để trống để reviewer gán nhãn liên quan thật; SKU có ID
đề xuất từ dữ liệu nguồn cũng vẫn PENDING_REVIEW. Không dùng 8 synthetic fixtures làm
ground truth cho 500 sản phẩm. Catalog hiện không có stock=0: các ca hết hàng là câu hỏi
ứng viên, cần fixture test riêng hoặc snapshot thực tế có bằng chứng trước nghiệm thu.

Reviewer xác nhận/sửa intent, các canonical entities và hard constraints; điền JSON array
expected_product_ids, kể cả `[]` cho no-result được xác nhận. Ô trống không đồng nghĩa
với đáp án rỗng. Graph evidence cần source/target IDs và quan hệ/entity có thật trên
snapshot được duyệt. Duyệt bằng nguồn catalog/graph độc lập, không chép output model làm đáp án.

Có thể thêm `allowed_product_ids` trong JSON hard_constraints để evaluator đo vi phạm
hard filters; nếu không có, số vi phạm là null, không mặc định 0. Giữ entity values là
JSON lists. Intents retrieval hiện hỗ trợ product_search/recommendation; các intent khác
trong file là mục tiêu cần kiểm chứng, không phải tuyên bố router mới đã có đầy đủ.

## Chạy evaluator

```powershell
.venv/Scripts/python.exe AI/evaluate_retrieval.py --dataset docs/review/benchmark-candidates.csv --output docs/evidence/benchmark-review-status.json --inspect-only
# Sau khi có dữ liệu được người duyệt, cấu hình catalog/index/graph phù hợp snapshot:
.venv/Scripts/python.exe AI/evaluate_retrieval.py --dataset docs/review/benchmark-candidates.csv --mode hybrid --output .cache/eval-hybrid.json
```

Evaluator chỉ đọc APPROVED có reviewer; thiếu đáp án bắt buộc là lỗi. Không có case được
duyệt thì exit 2, summary=null, không khởi tạo model/databases. `--inspect-only` exit 0
và chỉ báo coverage. Giữ hash dataset/catalog, model, representation version, collection,
sources enabled, degraded cases và latency. Precision@K có mẫu số K; Recall@K/MRR/nDCG
dùng relevant IDs người duyệt; entity-linking accuracy là exact canonical set match,
kèm entity precision/recall/F1. Top-K overflow được ghi riêng.

Chạy năm mode `lexical`, `dense`, `dense_lexical`, `dense_graph`, `hybrid` trên cùng
snapshot/approved cases để ablation. Reranker hiện là RRF + exact SKU boost/tie-break,
không phải cross-encoder được huấn luyện. Chưa có điểm chất lượng hoặc kết luận mode
nào tốt hơn khi chưa có tập đủ >=100 câu được người duyệt xác nhận.

Đối với auth/order/policy/analytics, evaluator retrieval đánh dấu UNSUPPORTED_TASK.
Kiểm tra bằng backend role/owner tests và HTTP thật có principal, không dùng câu hỏi
"tôi là admin" để xác định quyền. Có thể truyền `--predictions <captured.jsonl>` để
đánh giá output đã thu thật: mỗi dòng gồm query_id, product_ids, entities, intent,
degraded_sources. Hash file được ghi lại; không tạo predictions giả. Intent accuracy
không thay thế chứng cứ HTTP 401/403/owner isolation. Missing predictions được báo riêng.

Generator `scripts/prepare_review_data.py` từ chối ghi đè review CSV đang có. Muốn
regenerate, dùng `--output-dir` mới và review diff để giữ công sức người duyệt.
