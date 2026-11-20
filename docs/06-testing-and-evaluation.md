# Kết quả kiểm thử và giới hạn

Ngày cập nhật: 19/11/2026. Không kết nối database production. Không sửa tests cũ để
che lỗi implementation. Không xem mock/vector fixtures là kết quả semantic evaluation.

**Lượt kiểm dependencies mới nhất:** 640 backend tests + 827 subtests PASS; AI 52 tests,
51 PASS + 1 skip. Thêm live/ready backend và model cache policy, giữ nguyên OpenAPI.
Xem [dependency regression](evidence/dependency-regression.json) và
[environment audit](11-dependencies-and-environment.md). Bảng bên dưới giữ evidence lượt
continuation trước để không đánh đồng thời điểm/phiên bản source.

## Kết quả đã chạy

| Kiểm tra | Kết quả |
| --- | --- |
| Business suite với router cart checkpoint | 638 tests, 827 subtests PASS, 1 warning; 73.52s |
| Business suite với cart mới và shared auth/role dependencies | 638 tests, 827 subtests PASS, 1 warning; continuation 58.61s |
| Business OpenAPI | 60 paths, toàn bộ JSON schema bằng baseline |
| Modular core AI | 12 tests PASS |
| AI API contracts | 11 tests PASS, gồm schema 6 paths bằng checkpoint, query Top-K và live/ready |
| CSV/evidence/filter/revalidation/SKU | 8 tests PASS |
| Entity linking | 6 tests PASS; threshold decisions dùng vector fixtures, không phải quality metrics |
| Review workflow/evaluator gates | 6 tests PASS; reviewed unit examples không phải human benchmark |
| Qdrant local storage adapter | 3 tests PASS: replay/filtering, từ chối incompatible metric không xóa collection, loại stale representation |
| Evaluation metric arithmetic | 3 tests PASS; đây không phải điểm chất lượng retrieval |
| Neo4j live import idempotency | PASS: empty-instance test đã chạy trước khi import dataset; continuation report kiểm 508 products/replay/update/resume |
| Real model + local Qdrant + graph + HTTP | PASS: xem evidence/ai-live-acceptance.json; không phải benchmark relevance |
| Frontend HTTP transport | 5 tests PASS, Node v22.16.0 portable |
| Frontend syntax | Tất cả JS/MJS trong assets/js PASS |
| Python compile + diff whitespace | PASS |
| Compose config với cả profiles | PASS; không build/start containers |

Business suite gồm cookie auth/owner isolation, Cart/Orders/Payments, Customer/Staff/Admin,
AI scope/role matrix, rollback, Decimal và existing offline migration checks.
Baseline runner chỉ thay **cart router** bằng source checkpoint trong memory; không phải
full checkout của mọi file cũ. Suite cũng chứa 4 application tests mới và 1 observability test; chúng không chứng minh
behavior cũ của các services khác. Hai schema snapshots tạo từ app có cùng các module ngoài cart.

AI schema baseline capture bỏ eager SDK imports và CSV read bằng AST để lấy schema;
không gọi route handlers cũ. So sánh schema không chứng minh recommendations/LLM live.
Core tests dùng injected candidates/failures để kiểm tra rules, không giả vờ integration.
Qdrant unit adapter test dùng vectors fixture hai chiều. Acceptance script riêng đã dùng
model multilingual thật 384 chiều, cosine collection, 508 vectors và real retrieval/HTTP.
Hai loại evidence được giữ tách biệt để không nhầm unit vectors thành semantic quality.

## Chạy lại từ repository root (PowerShell)

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-test.txt -r AI/requirements-runtime.txt
.\.venv\Scripts\python.exe scripts/run_business_checks.py --sqlite-bootstrap --pytest --openapi docs/baseline/business-openapi-current.json
.\.venv\Scripts\python.exe scripts/run_business_checks.py --sqlite-bootstrap --baseline checkpoint/pre-architectural-refactor-20261118 --pytest
.\.venv\Scripts\python.exe -m unittest discover -s AI/tests -p test_modular_pipeline.py -v
.\.venv\Scripts\python.exe -m unittest discover -s AI/tests -p test_api_contract.py -v
.\.venv\Scripts\python.exe -m unittest discover -s AI/tests -p test_storage_integration.py -v
.\.venv\Scripts\python.exe -m unittest discover -s AI/tests -p test_evaluation.py -v
.\.venv\Scripts\python.exe scripts/run_ai_checks.py
.\.cache\node.exe --test frontend/tests/unit/http-client.test.mjs
```

Node portable trong `.cache` không được commit; máy khác dùng Node 22 hoặc `npm run test:unit`
trong frontend. Host này ban đầu thiếu Node/dependencies. Application Control chặn SQLAlchemy
wheel: cài cùng version 2.1.4 từ source tạo pure Python wheel. PostgreSQL binary driver cũng
bị chặn; `--sqlite-bootstrap` tạo engine memory chỉ trong test process để tránh import libpq.
Mọi actual DB connection trong suite đều bị guard chỉ cho SQLite `:memory:`; production
configuration không thay. Không dùng kết quả này để chứng minh PostgreSQL concurrency/live health.
Sau lượt Cart/observability, shared authentication/role dependencies được tách khỏi routers;
regression đầy đủ được chạy lại để kiểm tra cookie sessions và dependency overrides.

Workflow `architecture-quality.yml` chạy các quality gates trên Linux/Python 3.12/Node 22.
Chưa có kết quả GitHub Actions run. Test browser Playwright hiện có chưa chạy vì thiếu
business database/app/browser runtime. Docker daemon chưa hoạt động tại thời điểm kiểm tra.

## Live gates còn bắt buộc

Neo4j test yêu cầu instance **trống, riêng biệt** và explicit opt-in:

```powershell
$env:LUMIERE_EMPTY_GRAPH_TEST='1'
$env:NEO4J_TEST_URI='bolt://127.0.0.1:17687'
$env:NEO4J_TEST_PASSWORD='<dedicated-test-secret>'
.\.venv\Scripts\python.exe -m unittest discover -s AI/tests -p test_storage_integration.py -v
```

Test trống đã chạy PASS trước khi import catalog. Không bật lại test này trên graph 508 nodes;
maintained runner hiện skip đúng gate đó và dùng acceptance script cho populated owned graph.
Test từ chối graph có nodes, kiểm tra repeat import và relationship replacement rồi cleanup
nodes test. Không đặt các biến này đến production. Qdrant server tests và Postgres adapter
cần staging riêng; full model cần cài `AI/requirements-semantic.txt` và model cache thật.

Evaluation chưa có gold dataset/kết quả. Cần tách train/dev/test câu hỏi tiếng Việt có dấu,
không dấu, alias, ngân sách, negation và ambiguous entities; gán expected IDs/constraints.
Đo entity precision/recall, Recall@K, MRR/NDCG@K, hard-filter violation rate (mục tiêu 0),
Top-K fulfillment khi đủ hàng, grounding correctness, p50/p95 latency và degraded-source rate.
Chạy ablation dense/lexical/graph với cùng snapshot; lưu model/collection/version cùng report.
Chỉ chọn ngưỡng relevance và bật modular mặc định sau khi có số đo, không bịa điểm đánh giá.

Evaluator `AI/evaluate_retrieval.py` nhận CSV/JSONL qua human review gate. Schema hiện tại,
quy trình duyệt và năm ablation modes nằm trong [docs 09](09-data-review-and-benchmark.md).
Chỉ APPROVED có reviewer và đáp án hợp lệ được tính điểm. 136 candidates hiện đều pending;
report `evidence/benchmark-review-status.json` có summary=null. Không có chất lượng AI để công bố.

```powershell
.\.venv\Scripts\python.exe AI/evaluate_retrieval.py --dataset <gold-labels.jsonl> --output <evaluation-report.json>
```

Không có human gold nên chưa chạy quality evaluation. Unit test tạm thời tạo approved
fixture có tên UNIT_FIXTURE_NOT_A_HUMAN_BENCHMARK chỉ để kiểm evaluator arithmetic/real
lexical execution; nó không được lưu thành benchmark hoặc báo như quality results.

`scripts/run_ai_checks.py`: 50 tests, 49 PASS + 1 skip empty-graph gate. Log lưu tại
`evidence/ai-regression.txt`. Discovery toàn bộ `test_*.py` vẫn vướng test cũ
`test_price_intent`: import module khởi tạo external services ở top level và thiếu requests;
cài dependency đã không được chấp thuận trong lượt này. Không sửa test cũ để che vấn đề,
không tuyên bố toàn bộ legacy AI pipeline đã được kiểm chứng tương thích runtime.
