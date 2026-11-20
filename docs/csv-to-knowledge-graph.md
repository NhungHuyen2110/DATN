# Vận hành CSV → Neo4j → Qdrant

Pipeline thực tế: `AI/sync_catalog.py`, `lumiere/catalog.py`, `ingestion.py`, `adapters.py`.
Không yêu cầu nhập node/cạnh bằng Neo4j Browser. CLI mặc định chỉ validate.

Input thật `output/products_ai.csv`: 500 dòng, 19 cột. Chỉ đọc public product facts
để index; không index giá vốn/giá sỉ/barcode hoặc dữ liệu khách hàng. Báo cáo
[catalog-evidence-audit.json](review/catalog-evidence-audit.json) có hash/cột/FK đối chiếu.
Parser hỗ trợ UTF-8/BOM, quoted fields, delimiter tùy chọn, Decimal giá Việt/Anh,
null/missing/duplicate header và lỗi theo dòng. Không có cột ngày trong input hiện tại;
không tuyên bố đã kiểm thử date formats chưa tồn tại.

Toàn bộ input được validate trước mutation. Neo4j sử dụng stable IDs, constraints,
UNWIND parameters, MERGE và batch transactions. Chỉ thay stale edge cùng facet khi
có fact mới rõ ràng; không xóa Product hoặc cạnh nghiệp vụ khác. Qdrant sử dụng cosine,
model ID, representation version, content hash và readback payload; không xóa collection.
Đổi representation/model cần reindex collection/path riêng. Snapshot SQL được đọc-only.

PowerShell từ root, chỉ định rõ target test/staging:

```powershell
.venv/Scripts/python.exe AI/sync_catalog.py --file output/products_ai.csv --dry-run --report .cache/catalog-dry-run.json
# Bản Neo4j test riêng; không dùng URI production.
$env:NEO4J_TEST_PASSWORD='lumiere-test-only-password'
.venv/Scripts/python.exe AI/sync_catalog.py --file output/products_ai.csv --apply --environment test --target graph --neo4j-uri bolt://127.0.0.1:17687 --batch-size 100 --report .cache/graph-import.json
.venv/Scripts/python.exe AI/sync_catalog.py --file output/products_ai.csv --verify-only --environment test --target graph --neo4j-uri bolt://127.0.0.1:17687 --report .cache/graph-verify.json
# Khi cần tiếp tục batch, thêm --resume .cache/graph-import.json vào lệnh apply.
.venv/Scripts/python.exe AI/sync_catalog.py --file output/products_ai.csv --apply --environment test --target vectors --qdrant-local .cache/qdrant-manual-v3 --report .cache/vector-import.json
```

Password trên là fixture công khai, chỉ dành loopback instance của script test.
Model cache thiết lập qua `AI_MODEL_CACHE`; cài `AI/requirements-semantic.txt` trước
index. Production writes không có mode trong CLI; tên environment không tự chứng minh
URI an toàn, operator vẫn phải chọn đúng isolated target.

Rebuild test không phá graph khác: chuẩn bị Neo4j 5.26.x + Java 21 dưới `.cache/runtime`,
chạy `scripts/start_test_neo4j.ps1`. Script chỉ dùng thư mục có marker riêng, không reset
hoặc xóa data. Nó mở Bolt 17687/HTTP 17474 trên loopback. Nếu cần graph hoàn toàn trống,
dùng instance/volume test **mới**, không xóa instance hiện tại để chạy lại bài test trống.

```powershell
$env:AI_MODEL_CACHE=(Join-Path (Get-Location) '.cache/hf/models')
$env:NEO4J_TEST_PASSWORD='lumiere-test-only-password'
.venv/Scripts/python.exe scripts/run_ai_evidence.py
```

Script acceptance kiểm tra Neo4j data directory phải là `.cache/neo4j-test/data`,
import 500 nguồn + 8 fixture hai lần, kiểm tra counts/edges/resume, index model thật,
query hybrid và HTTP. Mỗi lần tạo Qdrant path riêng, không xóa path trước.
Evidence JSON là engineering acceptance, không phải benchmark relevance có người duyệt.

Docker staging sau khi engine hoạt động và DSN staging được provision:

```powershell
docker compose --env-file .env.staging -f compose.rebuild.yaml run --rm ai python sync_catalog.py --dry-run
docker compose --env-file .env.staging -f compose.rebuild.yaml run --rm ai python sync_catalog.py --apply --environment staging --neo4j-uri bolt://neo4j:7687 --qdrant-url http://qdrant:6333 --report /tmp/sync-report.json
```

Lệnh Docker là runbook, chưa có container execution evidence trên host này.
Sync hiện manual/replayable, chưa phải durable outbox/CDC: worker retry/dead-letter,
delete/tombstone, lag/reconciliation chưa hoàn tất. Không dùng CSV seed ghi đè PostgreSQL.
Readiness không thay thế verification nội dung hoặc benchmark. Screenshot Neo4j Browser
chưa thu; có path JSON và truy vấn trên để người bảo vệ minh họa bằng graph test.
