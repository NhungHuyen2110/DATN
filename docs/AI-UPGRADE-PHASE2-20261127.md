# LUMIÈRE AI Upgrade Phase 2 — Data consistency và incremental synchronization

Ngày 27/11/2026, Asia/Bangkok. Workspace `D:\LUMIERE-FINAL-TEST`, branch `update-ai`, HEAD giữ nguyên `1a432c170164fa9eeb07a189d6c0edd306713f67`. Đã đọc audit và ưu tiên mục 13 báo cáo Phase 1: hai API mới của Phase 1 đang phục vụ, acceptance Phase 1 đã đạt. Không thực hiện lại Phase 0/1.

**Trạng thái mới nhất — Phase 2B: BLOCKED_RESOURCE_GATE sau restart, kiểm tra lại 27/11/2026 lúc 18:10 UTC+7. Phase 2 CHƯA hoàn thành, worker CHƯA triển khai.** Host còn 0,47–0,63 GiB RAM khả dụng dù toàn bộ container đang dừng; VM còn khoảng 3,11 GiB. Không khởi động container hoặc tiếp tục công đoạn nặng. Cả bảy services phục vụ đã dừng từ trước lần kiểm tra sau restart và vẫn dừng khi bàn giao lần này; kết quả khôi phục services ở mục 13.4 chỉ thuộc lần thực hiện trước restart. Xem **mục 13.6** cho bằng chứng mới nhất. Người dùng đã phê duyệt Phase 2B và maintenance luân phiên; trở ngại hiện tại là tài nguyên, không phải thiếu phê duyệt. Không thay dữ liệu nghiệp vụ/schema/frontend/model/flags, không commit/push/merge hoặc chuyển Phase 3.

## 1. Baseline hiện tại đã xác minh

Collector `.local-tmp/phase2/collect_baseline.py` chỉ dùng PostgreSQL `REPEATABLE READ, READ ONLY` (kiểm tra `transaction_read_only=on`), Neo4j read session với MATCH/SHOW, Qdrant collection/scroll/snapshot-list và Business API GET. Không import hoặc chạy importer/worker/model thật. Credentials chỉ dùng trong container, không dump env. Đo đầu/cuối và so nội dung để phát hiện thay đổi trong lúc thực hiện.

| Thành phần | Kết quả thực đo |
| --- | --- |
| PostgreSQL và Business API | 501/501 sản phẩm; đối chiếu toàn bộ ID, SKU, tên, giá Decimal, stock, ID/tên của category/brand/material/gemstone/collection: khớp |
| Neo4j | 500 Product active, không dư ProductID hoặc duplicate ProductID/SKU; 2.500 quan hệ taxonomy; 0 orphan taxonomy; 8 uniqueness constraints đúng contract |
| Qdrant | 500 points, không dư ID, không lệch point-ID/payload ProductID, không duplicate SKU; không lệch các trường business có trong payload |
| Missing | ProductID 501 thiếu ở cả Neo4j và Qdrant |
| Graph stock drift | ID 1: graph 85, Business 83; ID 19: graph 9, Business 0; ID 488: graph 58, Business 59 |
| Các thuộc tính khác | Tên/SKU/barcode/weight/price decimal/minor và năm taxonomy endpoints/names/owners của 500 Product hiện có: không thấy lệch |
| Outbox | pending 5, done 496; processing 0, dead 0. Schema dùng `dead`, không có state tên `failed` |
| Last success | `2026-11-23T06:43:53.339101+00:00` (13:43:53 UTC+7) |
| Tuổi backlog | Job cũ nhất dirty từ `2026-11-26T11:15:57.109633+00:00`; tại kiểm tra cuối 17:12:31 UTC+7, khoảng 82.594,56 giây, tức 22,94 giờ |
| Worker | Không có index-worker chạy. Hai API, frontend, proxy và datastores hiện hành vẫn chạy |

Các job chính xác cần xem xét, không có lease đang hoạt động và tất cả attempts=0:

| ProductID | generation / delivered_generation | dirty_since UTC | Ý nghĩa đối chiếu |
| --- | --- | --- | --- |
| 1 | 17 / 4 | 26/11 11:15:57.109633 | Graph stock cũ |
| 19 | 4 / 3 | 27/11 04:41:18.369234 | Graph vẫn stock 9 trong khi Business đã hết hàng |
| 235 | 5 / 3 | 27/11 03:26:08.706284 | Chưa thấy lệch các thuộc tính quan sát được; vẫn phải xử lý job, không tự đánh dấu done |
| 488 | 7 / 4 | 27/11 03:21:28.643784 | Graph stock cũ |
| 501 | 2 / 0 | 27/11 03:47:39.829322 | Chưa từng được acknowledge, thiếu cả hai projections |

ID 501 thực tế: tên `aaaa`, SKU `111111111111`, barcode `WHSTOCK`, category Nhẫn, material Vàng trắng 18K, gemstone Moissanite, stock 0, giá 234.567 VND, weight 0,03. Đây là record hợp lệ theo schema hiện tại; không mặc định là rác, không xóa/sửa. Có 2 sản phẩm stock=0 trong nguồn. Không tạo dữ liệu giả để nghiệm thu.

`products` không có timestamp cập nhật hoặc lịch sử event payload cho từng thay đổi. Có thể xác minh snapshot hiện tại và các generation chưa giao; không thể tái dựng chính xác ai sửa từng trường, giá trị trung gian hoặc toàn bộ thay đổi kể từ audit chỉ từ outbox coalescing. Số lượng/drift hiện tại vẫn giống audit lịch sử; không lấy đó làm bằng chứng chưa từng có thay đổi trung gian.

## 2. Kiến trúc đồng bộ AS-IS

1. Admin tạo/sửa sản phẩm ở `routers/catalog.py`; Staff cập nhật stock cũng tại đây. Orders giảm stock khi tạo đơn và khôi phục stock khi hủy qua ORM trong `services/orders.py`. Không sửa các logic này.
2. Hook `before_flush` của `product_index_jobs.py` nhận Product new/dirty/deleted và taxonomy rename. `enqueue` UPSERT một row/product, tăng generation và nằm trong **cùng transaction** nghiệp vụ, không tự commit. Nhiều flush cùng transaction được coalesce; rollback/savepoint có cleanup markers. API hiện hữu không dùng bulk UPDATE Product để vượt hook. SQL trực tiếp ngoài ORM không tạo event và cần reconciliation riêng.
3. Worker CLI yêu cầu URL `postgresql+psycopg` thuộc `lumiere_dev*`/`lumiere_test*`, endpoints local/container được phép, backup reference, cached model/revision. Không đọc root `.env`, không tự migrate.
4. `claim_one` dùng `FOR UPDATE SKIP LOCKED`, commit lease/token/generation trước external I/O. Mặc định lease 120s, retry budget 5; pending đến hạn và processing hết lease có thể được claim. Lease hết retry chuyển dead. Lỗi chỉ lưu type, không lưu raw errors/credentials.
5. `current_product` đọc snapshot mới nhất từ PostgreSQL và năm taxonomy, không lấy payload cũ từ event. Product không còn tồn tại → tombstone. `ProductProjection` graph trước, vector sau; bắt lỗi thì không acknowledge success.
6. `acknowledge` kiểm tra token: generation đổi trong lúc giao → pending generation mới; success đúng generation → done/delivered_generation; lỗi → backoff (2/4/8/16… giây), tối đa budget rồi dead. Claim mất lease không được acknowledge lease khác; worker cũ enqueue repair nếu có khả năng đã chạm index.
7. Compose original-data có `sync` profile, worker mặc định watch, RAM 3 GiB, 2 CPU threads, backup mount cũ. Profile hiện không được bật. Idle worker chưa load model, nhưng khi có backlog sẽ load MiniLM trước claim.

AS-IS có eventual repair sau lease lost, không có distributed transaction giữa ba stores hoặc strict fencing/CAS trên Qdrant. Không suy ra tính đúng của mọi crash/partition từ lease token ở PostgreSQL.

## 3. Nguyên nhân drift và backlog

Nguyên nhân vận hành được chứng minh: producer đang tạo generation mới (`PRODUCT_INDEX_SYNC_ENABLED=true`) nhưng consumer không chạy; cả 5 pending jobs chưa có attempt. Không có dấu hiệu năm job này đã thử và lỗi provider/index rồi mới bị tồn. Đọc source và so snapshot xác nhận pending IDs bao phủ cả missing 501 và stock drift 1/19/488.

Job 235 không được bỏ vì public snapshot đang khớp: outbox không giữ event payload/historical embedding document; thay đổi trung gian hoặc private metadata có thể đã quay về giá trị hiện tại. Xử lý idempotent từ snapshot mới là cách hoàn tất đúng, không phải gán done bằng SQL.

Giá/stock trong graph không phải authority bán hàng. Business verification hiện vẫn bảo vệ hard constraints; tuy nhiên index thiếu hoặc stock cũ có thể làm sai candidate recall/ranking/giải thích. Verification không tự sửa graph/vector.

## 4. Projection contracts và index eligibility

### 4.1 Nguồn và lifecycle

Schema Product bắt buộc ID rõ, SKU/barcode/name không rỗng, taxonomy FK hợp lệ, weight>0, price/stock không âm. Không có trường Product active/inactive/hidden/description hoặc soft-delete. Vì vậy:

- Tất cả Product tồn tại và có snapshot hợp lệ đều được lập index, gồm stock=0. Stock=0 không đồng nghĩa xóa vector hoặc product.
- Product không còn trong PostgreSQL: tombstone graph (`is_deleted=true`, stock=0), giữ node/relationships để không đụng cấu trúc khác; xóa đúng point-ID khỏi collection hiện hữu. Tombstone không tính là active Product trong drift set.
- Snapshot thiếu/không hợp lệ hoặc FK không resolve: job phải lỗi/retry/dead, không giả làm deletion hoặc silently skip. Không tự làm sạch dữ liệu thật.
- “Ẩn”, “inactive” và sửa description chưa có API/schema tương ứng để kiểm thử. Nếu muốn thêm lifecycle này phải có thiết kế/phê duyệt schema riêng, không gán nghĩa mới cho stock=0 hoặc dùng một thuộc tính khác làm cờ ẩn.

### 4.2 Neo4j

Owner `lumiere-products-v1`; Product ID/SKU/name/barcode/weight, sale_price legacy numeric, sale_price_decimal, sale_price_minor, stock, is_deleted và provenance. Mỗi Product có đúng một `BELONGS_TO`, `HAS_BRAND`, `MADE_OF`, `HAS_GEMSTONE`, `IN_COLLECTION`, đúng ID/name/owner của endpoint. Product và taxonomy uniqueness constraints ngăn duplicate identity; không tự xóa entity orphan hoặc đổi ownership. Reviewed attributes giữ contract/flag hiện hữu; flag đang false, không bật thêm.

### 4.3 Qdrant và embedding

- Collection duy nhất: `jewelry_products_v_c0efd814ee4f`, dimension **384**, metric **Cosine**. Toàn bộ vectors được kiểm tra dimension, hữu hạn, khác vector 0; payload fingerprint/model/revision khớp profile cấu hình.
- Model `paraphrase-multilingual-MiniLM-L12-v2`, revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`; fingerprint `c0efd814ee4f6a77e5298a9b53ad6d3235f5369756a33640408cfcddad4f60a1`. Cache model có sẵn, không load model/download hoặc đánh giá chất lượng embedding thật trong đợt này.
- Payload business hiện có: ProductID, ProductName, SKU, Category/CategoryID, Material name, Gemstone/GemstoneID, Collection name; cộng model/revision/fingerprint/source lineage, reviewed attributes khi được bật. Không lưu price, stock, Brand, MaterialID, CollectionID, barcode hoặc weight như business payload. **Không coi việc thiếu các trường này là drift.** Brand vẫn có trong embedding document dù không có trong payload.
- Embedding document giữ nguyên phép nối tên sản phẩm + category + brand + material + gemstone + collection và tên facts đã được duyệt. Không thêm stock/price vào text, không thay model/revision/dimension/collection/RRF/ontology.
- Metadata mới `embedding_document_sha256` hash chính UTF-8 document, không phải toàn bộ snapshot. Với vector có metadata hợp lệ: stock/price/SKU/barcode/weight/lineage hoặc review-version không đổi text chỉ refresh payload bằng vector cũ; thay tên/brand/taxonomy/fact text phải encode lại.
- 500 vectors hiện tại chưa có document digest mới. Không thể chứng minh text cũ từ payload thiếu Brand chỉ bằng source digest của snapshot khác. Mỗi point legacy được chạm sẽ encode lại một lần rồi mới dùng cache mới; không re-embed toàn bộ 500. Kế hoạch năm job cần tối đa năm point embeddings ban đầu (gồm tạo mới 501); 495 points chưa chạm giữ nguyên và vẫn tương thích consumer.

## 5. Lỗi/giới hạn phát hiện và trạng thái xử lý

| ID | Phát hiện | Xử lý trên checkout / giới hạn |
| --- | --- | --- |
| P2-01 | Chỉ đổi stock/price cũng đổi source digest, cache vector yêu cầu payload toàn bộ bằng nhau → re-embed không cần thiết | Đổi cache key theo document + embedding identity, refresh payload mà giữ vector; legacy fallback encode một lần |
| P2-02 | Graph verify chỉ kiểm ID/relationships; vector verify chỉ count/fingerprint | Verify graph properties/provenance; vector đủ ID set và toàn bộ expected payload. Sai readback không báo success |
| P2-03 | Delete chưa kiểm readback; worker có thể tạo collection/constraint khi target sai hoặc thiếu | Readback graph tombstone/vector absence. Incremental adapter yêu cầu collection/config sẵn và không cho tạo graph constraints; schema thiếu → fail trước graph import |
| P2-04 | Claim/ack token không ngăn worker hết lease ghi index cũ sau writer mới; repair chỉ eventual | Thêm PostgreSQL session advisory lock/product cho cooperating workers, kiểm lại lease/token trước snapshot/delivery. Không giữ business transaction/row lock qua external I/O; lock contention không ghi index/không ACK success |
| P2-05 | Reconcile mặc định enqueue toàn bộ union IDs, worker không chọn được phạm vi canary | Thêm targeted reconciliation/claim/status qua product IDs; CLI `--product-id` lặp được; one-shot không completed trả exit 2, dừng tại failure/supersession |
| P2-06 | Chỉ có attempt duration, không có event-to-index histogram | Thêm metric event-to-index từ dirty_since đến generation acknowledged hoàn tất. Coalesced/pending/lost-lease không đóng góp sample thành công |
| P2-07 | Worker recipe/entrypoint không thuộc manifest Phase 1; worker image không có provenance labels | Optional `--include-worker`, thêm hai COPY/build inputs và labels vào worker Dockerfile; không đổi layer dependency |
| P2-R1 | Qdrant không cung cấp CAS/fencing generation trong adapter này | Advisory lock không phải strict distributed fence nếu mất PG lock connection khi external request còn in-flight, hoặc có writer không tham gia lock. Chưa chứng minh invariant dưới lỗi này; bắt buộc một worker, không writer khác, có fault test/đánh giá trước triển khai. Nếu yêu cầu linearizability qua partition cần thiết kế riêng, không che bằng generation trong payload + read-before-write |
| P2-R2 | Chưa có proof restore mới cho cả ba stores; old backup chỉ kiểm PG checksum/TOC | Chưa đủ điều kiện ghi thật; cần snapshot/archive mới và restore drill cô lập trước canary |
| P2-R3 | Máy thiếu headroom cho worker/model thứ hai | Không cố chạy. Cần giải phóng RAM hoặc phê duyệt maintenance riêng; không tự dừng AI/datastore để lấy tài nguyên |

Không sửa schema, không thêm cột generation vào index business, không quảng bá atomic cross-store commit. Source mới giảm rủi ro và cung cấp recovery có kiểm soát, không thay thế kiểm thử server/fault injection còn thiếu.

## 6. Kiến trúc TO-BE và thao tác sau từng failure

Producer/outbox transaction giữ nguyên. Worker đọc latest snapshot, nhận session advisory lock theo ProductID, xác nhận lease vẫn thuộc mình, rồi mới ghi graph → Qdrant và verify; release lock, ACK generation đúng token. Model cold start vẫn trước claim. Khi cập nhật mới xuất hiện giữa delivery, generation mới còn pending; không gán completed/latency sample cho generation chưa hội tụ.

| Failure | Kết quả bắt buộc |
| --- | --- |
| Graph fail/verify fail | Không gọi vector write; job không done |
| Graph success, vector fail/verify fail | Không ACK success; retry từ latest SQL, graph replay cùng identity, không duplicate vector |
| Kill process sau một index hoặc sau hai index nhưng trước ACK | Processing được reclaim sau lease; idempotent retry, không giả completed |
| Update liên tiếp/notification cũ | Coalesce generation nhưng luôn đọc latest SQL; không áp payload event cũ |
| Advisory lock busy | Không chạm index; bounded retry, không giả đã giao |
| Lost lease | Không ACK token khác; repair generation pending, review nếu có khả năng đã chạm index |
| Missing schema/collection, embedding mismatch, unmanaged data | Dừng và điều tra; không tự migrate/full rebuild/take over |

Reconciliation thuần đọc dùng `shared/product_index_contract.py:compare_indexes` trên snapshot collector, trả issue list + affected ProductIDs. Phát hiện data drift theo từng contract, không dùng global count làm PASS. Không có chức năng auto-delete hoặc tự enqueue trong comparator.

## 7. File thêm/sửa và lý do

**3 file mới so với workspace sau Phase 1**, không phải so với HEAD chưa commit:

| File mới | Lý do |
| --- | --- |
| `shared/product_index_contract.py` | Document/cache contract dùng chung với writer và comparator drift thuần đọc |
| `AI/tests/test_index_consistency.py` | Fixture tests cho exact contract, zero-stock eligibility, drift, duplicate, revision và tombstone |
| `docs/AI-UPGRADE-PHASE2-20261127.md` | Báo cáo chính duy nhất |

17 file hiện có được sửa trong Phase 2:

| File | Nội dung |
| --- | --- |
| `AI/vector_index.py` | Cache document, payload refresh, exact ID/payload verification |
| `AI/product_projection.py` | Identity/config preflight, không đổi collection/schema, verify deletion |
| `AI/knowledge_graph/graph_writer.py` | Verify properties/tombstone, incremental không DDL |
| `backend/app/services/product_index_jobs.py` | Scope claim/status, dirty_since trong Claim; enqueue transaction giữ nguyên |
| `backend/app/services/product_index_worker.py` | Advisory lock, lease recheck, targeted reconciliation, completion/latency metadata |
| `scripts/run_index_worker.py` | Target ProductID, bounded run fail-stop, không khởi model khi scope không có job |
| `shared/worker_metrics.py` | Histogram event-to-index chỉ cho completed generation |
| `scripts/ai_source_manifest.py` | Optional worker input scope, giữ default API tương thích |
| `infra/index-worker.Dockerfile` | Hai provenance labels/build args, không thay base/requirements/model |
| `AI/tests/test_graph_constraints_replay.py` | Không DDL trong incremental mode |
| `AI/tests/test_graph_writer.py` | Sai properties/tombstone readback phải fail |
| `AI/tests/test_product_projection.py` | Lifecycle/replay, missing collection, identity, partial vector failure |
| `AI/tests/test_vector_replay_cache.py` | Nontext refresh, text changes, legacy migration, corrupt vector, review metadata |
| `backend/tests/test_product_index_jobs.py` | Scope, out-of-order/latest read, locks, lease lost, savepoint, CLI safety, 11 mutation fields |
| `backend/tests/test_worker_metrics.py` | Không tính coalesced/lost generation như event latency thành công |
| `scripts/test_postgres_sync.py` | Chuẩn bị real PG advisory exclusion/release trên target test riêng; chưa chạy |
| `scripts/test_projection_integration.py` | Bootstrap schema/collection fixture rõ ràng ở target test riêng, không để incremental adapter tạo ngầm; chưa chạy |

Không thay frontend, ba Compose recipes đang chạy, models/migrations, auth, cart/checkout/payment/account hoặc dialogue. Chênh với manifest Phase 1 chỉ nằm trong danh sách Phase 2 được phép; source fixes Phase 1 giữ nguyên. Artifacts cần thiết tập trung `.local-tmp/phase2/`; không tạo source backup.

## 8. Kiểm thử và bằng chứng

Chạy tuần tự, không cài package, không tải model, không network/database thật từ test runners. Backend safe runner ép SQLite `:memory:` và chặn sockets/file DB; AI safe runner chặn graph/network/model. Qdrant tests dùng engine in-memory thật và vectors tổng hợp; graph transaction/PG advisory adapter hiện dùng stubs cho isolated unit tests.

| Kiểm tra | Kết quả cuối / phạm vi |
| --- | --- |
| Backend initial targeted | 25 passed, 727 deselected; bằng chứng bước đầu, không cộng lại vào tổng regression |
| Backend related regression | **199 passed, 554 deselected, 191 subtests passed, 19 warnings**, 18,79s; jobs/metrics/migration, product mutation/review, Phase 1 correctness và role matrix có liên quan import/hooks |
| Bổ sung field-mutation contract sau đó | **1 passed, 753 deselected, 11 subtests passed**, 2,56s; name/SKU/barcode/weight/price/stock và năm taxonomy IDs đều sinh generation và đọc latest snapshot/name đúng |
| AI targeted + consumer regression | **58 tests khác nhau, 0 failure/error/skip**, 10 patterns; chọn kết quả mới nhất cho pattern đã sửa tiếp, không cộng lượt lặp |
| Python syntax | AST parse 18 file Python thêm/sửa: PASS |
| Compose plan | Resolve `--profile sync` + overlay: PASS; worker 1 CPU/1536 MiB/128 PIDs; model/recovery mounts read-only; configs services khác không đổi; chỉ config, không chạy service |
| Baseline/preservation | PASS: SQL/API toàn bộ khớp, graph/vector audit toàn bộ, đầu/cuối raw data/jobs/vectors/runtime/frontend không đổi |
| Old backup readability | Checksum + PGDMP + `pg_restore --list`: PASS; có products/outbox trong TOC. Không phải proof restore và không đủ mới cho Phase 2 |
| Real isolated PostgreSQL advisory/concurrency/crash test | **BLOCKED**, chưa có target PostgreSQL riêng đang chạy; không mượn DB nghiệp vụ hoặc khởi thêm Docker trước phê duyệt |
| Real isolated Neo4j write/Cypher/readback và partial-failure integration | **BLOCKED**, không chạy write test trên graph nghiệp vụ; cần test server riêng và RAM |
| Real model embedding compatibility/latency | Chưa đo encode trên model thật trong Phase 2; dimension/revision/payload và search consumer đã kiểm, unit tests dùng synthetic vectors |
| New worker image tests và live reconciliation/acceptance | **BLOCKED bởi điểm dừng phê duyệt**, không có image Phase 2 được build hoặc write acceptance thật |
| Full AI/backend suites không liên quan, host-process test, Phase 1 live suite | **SKIP theo scope**, không chạy lại chỉ để tăng số PASS; không sửa assertion/skip của test gốc |

58 AI tests: projection 4, vector replay/cache 4, graph writer 6, constraints 4, comparator 5, versioned Qdrant/search 3, search service 19, Business catalog verification 5, related graph search 5, reviewed-attribute search 3. Backend có 200 test cases khác nhau nếu gộp 199 regression và 1 case thêm, không cộng 25 targeted lặp; tổng subtests tương ứng 202.

Lệnh đã chạy (các pattern AI chạy lần lượt, report riêng):

```powershell
.local-tmp/backend-test-venv/Scripts/python.exe -B scripts/run_backend_tests.py --ignore=tests/test_evaluation_scoring.py -k 'product_index or worker_metrics or admin_products or product_attribute_reviews or ai_phase1_correctness or ai_role_access' --junitxml=D:/LUMIERE-FINAL-TEST/.local-tmp/phase2/backend-regression.xml
.local-tmp/backend-test-venv/Scripts/python.exe -B scripts/run_backend_tests.py --ignore=tests/test_evaluation_scoring.py -k all_mutable_projection_fields_emit_jobs --junitxml=D:/LUMIERE-FINAL-TEST/.local-tmp/phase2/backend-mutation-contract.xml
.local-tmp/ai-test-venv/Scripts/python.exe -B scripts/run_ai_tests.py --pattern <pattern-trong-bảng> --report <JSON-mới>
python -B scripts/ai_source_manifest.py --include-worker --output .local-tmp/phase2/source-manifest-final.json
```

`evaluation/scoring` không nằm trong scope; bỏ collection test đó, không đổi test/assertions. Warning hiện hữu Starlette/httpx/cookie deprecation được giữ nguyên. Errors thiết lập collector ban đầu (Qdrant client không hỗ trợ context-manager; dùng closing) và kiểu chuỗi `mem_limit` khi validate Compose đã được sửa trong helper, retry chỉ đọc; không coi đó là lỗi ứng dụng hoặc acceptance PASS/FAIL của image chưa build.

## 9. Kế hoạch backup, reconciliation và rollback — chưa thực hiện

### 9.1 Điều kiện bắt buộc trước mọi write thật

1. Người dùng phê duyệt cụ thể giai đoạn triển khai này, phương án backup và maintenance nếu cần. Đo lại toàn bộ diff/job generations/eligibility; không dùng snapshot đã cũ nếu Business vừa thay đổi.
2. Chạy PostgreSQL locking/advisory và Neo4j/Cypher/partial failure trên **server test riêng**, không tạo fixtures trên DB/index nghiệp vụ. Server/test resources cũng cần được cho phép nếu phải tạo/khởi động. Kiểm chứng P2-R1; nếu chưa đạt, dừng ở tests/thiết kế, không tiến tới write thật.
3. Xác nhận chỉ có một worker mới, không worker legacy/manual importer/writer khác. Không tăng concurrency để bù backlog. Đặt điều kiện fail-stop ở mục 11.
4. Disk C/D còn ≥20 GiB. Đề xuất headroom **host RAM available ≥1,5 GiB**, VM MemAvailable ≥1,75 GiB trước worker. Đây là ngưỡng vận hành bảo thủ được đề xuất, chưa phải mức RAM benchmark của worker. Nếu không đạt: dừng, không tự stop API hoặc bật swap/prune để vượt.
5. Tạo/kiểm đủ backup mới và restore proof, sau đó mới mount recovery reference và chạy canary. Reference PG của CLI chỉ kiểm file/target/checksum, **không chứng minh freshness hay restore của Neo4j/Qdrant**; gate thủ tục này không được bỏ qua.

### 9.2 Backup/restore cụ thể cần phê duyệt

- **PostgreSQL:** custom-format pg_dump mới của `lumiere_test_original_data`, có products/taxonomies/jobs cùng snapshot; hash SHA-256 và TOC. Tạo reference version 1 theo `shared/recovery.py`, host `postgres`, port 5432, environment test; file tương đối dưới `.local-tmp/phase2/recovery/`. Restore drill vào database/server test riêng, kiểm counts/IDs/jobs/generations và readonly diff. Không restore dump toàn bộ lên DB nghiệp vụ để rollback index.
- **Qdrant:** tạo snapshot đúng collection hiện hành qua API sau phê duyệt, copy ra recovery directory, hash và verify download/file. Snapshot-list hiện rỗng. Restore vào Qdrant test riêng cùng version/dimension, so point ID/payload/vector checksums. Không đổi collection hoặc restore đè môi trường thật trước khi drill đạt.
- **Neo4j:** Community không được giả định có hot backup đầy đủ. Phương án an toàn là maintenance đã phê duyệt: stop Neo4j tạm thời, cold archive cả volumes data/logs đã xác minh trong baseline, với helper từ image sẵn có và source mounts read-only; start lại **cùng container**, không recreate, rồi kiểm health. Restore archive trên volumes/server test riêng, kiểm 500 Product/2.500 edges/constraints/provenance và raw snapshot. Việc stop/start datastore và helper container **chưa được thực hiện và cần phê duyệt rõ**; không tự làm trong bước chuẩn bị.
- **Theo target:** giữ before-images của graph subgraph/edges/owners cho năm ProductIDs, vectors/payloads và năm job rows; bản baseline hiện tại chỉ là dữ liệu đọc, không thay thế backup/restore drill. Archive và restore phải bảo toàn taxonomy shared entities và các owner, không xóa toàn graph.

Backup cũ ngày 22/11 có SHA `78c9ecb9da04ea209d7164d34dccb943f14ba8f9cfe30f946232556062c21a48`, 90.668 bytes; validator và TOC đọc được nhưng trước nhiều thay đổi sản phẩm/jobs, không được dùng làm recovery proof mới. Không tạo backup/snapshot thật trong phiên này; old backup giữ nguyên.

### 9.3 Targeted reconciliation

Danh sách runtime dự kiến xử lý đúng **năm job 235, 1, 488, 19, 501**, mỗi lượt một ProductID, batch=1. Các records business không được thay đổi. Bốn ProductIDs có data drift/missing, nhưng job 235 cũng là pending hợp lệ. Không dùng `--reconcile` toàn bộ 501 hoặc full rebuild graph/vector.

1. Canary 235: claim job hiện có, không enqueue thêm generation chỉ để tạo canary; verify cả graph/vector/contracts rồi ACK. Vì legacy vector không có document digest, cho phép một embedding đầu tiên của point này.
2. Đọc lại diff/jobs. Nếu canary đạt, chạy lần lượt 1 → 488 → 19 → 501, mỗi run `--max-jobs 1 --product-id <ID>`, không `--watch`. Nếu jobs/generations khác baseline thì review lại, không gán delivered_generation theo số cũ trong bảng.
3. 501 phải có cả projection dù stock=0; Business verification phải tiếp tục chặn gợi ý in-stock sai. Không sửa tên/SKU/stock của 501 để có PASS.
4. So toàn bộ eligible ID set, payload fields/taxonomy/stock, duplicates và owner lại. Chỉ targeted enqueue với `reconcile(..., product_ids=[...])` nếu còn drift thật hoặc orphan active projection có review/approval; không mặc định enqueue lại tất cả. Job đã done nhưng mismatch phải báo lỗi, không coi done là proof.
5. Replay một selected job để chứng minh idempotent và không re-embed khi text/digest đã tương thích, **chỉ sau phê duyệt thay đổi job state**. Không replay bằng sửa trực tiếp status/generation SQL.

### 9.4 Rollback/failure giữa chừng

Stop worker và lưu phase/result/target IDs/attempts/lease/error type; không reset jobs hoặc rollback dữ liệu nghiệp vụ. Nếu graph đã mới và vector chưa mới, retry latest snapshot sau backoff là phương án ưu tiên, không ACK một phần. Không chạy worker cũ song song để “sửa nhanh”. Process chết: xác nhận process/container cũ đã dừng, chờ lease/reclaim bằng code mới; kiểm token và generation mới nhất.

Nếu cần restore: chỉ sau xác nhận không có writer cạnh tranh và đã quiesce các thay đổi sản phẩm liên quan, dùng before-images/snapshot đã drill, rồi reconcile lại từ SQL hiện tại. Không restore PG toàn bộ vì có thể làm mất giao dịch thật sau backup. Không hạ generation, không reset done496, không overwrite job mới phát sinh; thay đổi job state cần điều kiện compare-generation/token đã review. Mất PG lock connection khi index request còn in-flight: cô lập/dừng worker, không start bản khác cho đến khi biết writer cũ đã kết thúc; kiểm lại cả hai index trước retry. Nếu không chứng minh được an toàn theo P2-R1, dừng và xin quyết định thiết kế.

Chưa có worker runtime cũ đang chạy để rollback image. Rollback deploy worker là stop/remove **chính worker mới**, giữ API Phase 1 và frontend. Snapshot restore không được tuyên bố khả dụng cho đến khi drill PASS. Giữ images/artifacts/volumes; không down -v, prune hoặc remove-orphans.

## 10. Kế hoạch Docker deployment giới hạn tài nguyên — chờ phê duyệt

Chỉ cần **build `index-worker`**, vì consumer CLI/image đóng gói `AI/`, `backend/`, `shared/` và worker entrypoint. Producer `enqueue`/business mutation hooks, API response, retrieval consumer runtime không đổi; không cần rebuild/recreate ai-api/business-api/frontend/proxy/datastores để áp dụng các sửa consumer này. Hai API giữ images Phase 1. Nếu review sau đó yêu cầu deploy thay đổi web API mới, phải nêu lại phạm vi thay vì tự build thêm.

Chuẩn bị `.local-tmp/phase2/worker-limited.yaml`: 1 CPU, 1536 MiB, 128 PIDs, threads=1, restart=no, model/recovery mounts read-only, default canary235/max-jobs1. Profile sync chỉ resolve/config trong phiên này. Overlay không đổi env/config các service khác.

Source manifest build dự kiến: `5a71ccaf0bcb9e8b4bac12858d9d96acd0e07f96e09877d8e2340ddef30fcce8`, 343 file; gồm worker Dockerfile/entrypoint, không có env/model/DB. Trước build phải tạo manifest mới bằng create-exclusive path rồi so files/hash với evidence này; source đổi thì review và chạy affected tests, không dùng labels để che dirty checkout.

```powershell
# KẾ HOẠCH, CHƯA CHẠY build/run. Chỉ thực hiện khi các gates mục 9 đã đạt và được phê duyệt.
$phase2Compose = @(
  '--project-name', 'lumiere-rebuild-test', '--env-file', '.env.example', '--profile', 'sync',
  '-f', 'compose.yaml', '-f', 'compose.original-data.yaml', '-f', 'compose.semantic-dst.yaml',
  '-f', '.local-tmp/phase2/worker-limited.yaml'
)
$phase2Manifest = Get-Content -Raw .local-tmp/phase2/source-manifest-final.json | ConvertFrom-Json
docker compose @phase2Compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Stop: compose validation failed' }
docker compose @phase2Compose build --build-arg "LUMIERE_GIT_COMMIT=$($phase2Manifest.git_commit)" --build-arg "LUMIERE_SOURCE_SHA256=$($phase2Manifest.source_sha256)" index-worker
if ($LASTEXITCODE -ne 0) { throw 'Stop: build failed, do not start worker' }

# Inspect ID/digest/labels + COPY checksums; run isolated new-image tests and backup verification BEFORE this:
docker compose @phase2Compose run --rm --no-deps --pull never --name lumiere-phase2-canary-235 index-worker
if ($LASTEXITCODE -ne 0) { throw 'Stop: canary incomplete/failed; inspect, do not process other targets' }
```

`config`/CLI flags đã được kiểm, đoạn build/run trên chưa chạy. Tận dụng cache, không `--no-cache`, không bật service dependency/profile khác. Recovery path trong overlay phải có reference/backup **mới và đã drill**, không dùng reference cũ chỉ vì CLI chấp nhận checksum. Sau canary cần checklist mục 11 trước khi đổi command sang từng ID còn lại.

Tài nguyên đo: C ban đầu 73.571.475.456 bytes, D 54.471.241.728 bytes; cuối C 73.563.598.848, D 54.468.026.368, đều >20 GiB. Host RAM đo khoảng 856.223.744 bytes available (0,80 GiB), tổng 8.303.452.160 bytes; VM MemAvailable 1.481.316 KiB (khoảng 1,41 GiB). **Chưa đạt ngưỡng headroom đề xuất**. Không khởi model/worker thật để thử xem có OOM. Không tự stop AI để lấy RAM; nếu cần maintenance AI phải xin phê duyệt riêng.

Muốn bảo đảm incremental synchronization tương lai phải có consumer chạy lâu dài, không chỉ drain năm job. Chỉ sau bounded acceptance, fault tests và headroom ổn định, người dùng mới quyết định cho **một** worker watch không giới hạn ProductID chạy liên tục. Không bật watch tự động trong canary, không tự thêm restart policy để che lỗi. Cùng CLI/code đã có retry/recovery; cần capacity và vận hành/giám sát đã được nghiệm thu. Nếu máy không đủ RAM để vừa giữ AI vừa watch, dừng ở bounded reconciliation và ghi rõ chưa đạt mục tiêu đồng bộ liên tục; không công nhận Phase 2 hoàn thành.

## 11. Live acceptance checklist và điều kiện dừng

Chưa mục nào cần write trong checklist này được thực hiện. Chỉ công nhận Phase 2 hoàn thành khi các gates/acceptance sau có bằng chứng thật:

- [ ] New worker image ID/digest/labels/COPY hashes khớp manifest; imports/dependencies tương thích. New-image tests trong container network-none, SQLite/Qdrant memory/stub graph, không mount dữ liệu thật.
- [ ] Isolated PostgreSQL session-lock exclusion, lease expiry, process kill, out-of-order và connection-loss fault scenarios đạt; isolated Neo4j query/properties/tombstone và Qdrant server partial-failure/retry đạt. Không dùng business indices để chạy fixture writes.
- [ ] Ba backup mới, checksum/target và restore drill đạt; operator xác nhận chỉ một writer và đủ tài nguyên.
- [ ] Canary235 rồi các target1/488/19/501 completed đúng generation hiện hành, không done khi thiếu một store. Failure/supersession exit2 được nhận diện; không chạy tiếp tự động.
- [ ] Active graph IDs và vector IDs bằng đúng 501 eligible source IDs nếu nguồn vẫn giữ baseline; không extra active projection/duplicate; năm taxonomy và các thuộc tính theo contract drift=0. Legacy document-cache metadata ngoài các point đã chạm không bị tính nhầm là business drift.
- [ ] Graph stock1=83, 19=0, 488=59 nếu SQL chưa đổi; ID501 có projection, stock0 và không gợi ý sai in-stock. Không hardcode các số này trong code/tests, luôn so SQL/API tại thời điểm acceptance.
- [ ] Năm pending được giải thích/hoàn tất, không processing hết lease hoặc dead bất thường; jobs phát sinh mới trong quá trình được đối chiếu riêng, không đặt mục tiêu sai “done501” bất kể generation nguồn.
- [ ] Replay idempotent: node/point/relationship counts không tăng; document không đổi không encode lại sau initial legacy upgrade; lỗi một store không ACK success và retry hồi phục.
- [ ] Retrieval vẫn dùng dense Qdrant + graph Neo4j + Business authority, RRF/ontology không đổi. Đối chiếu category/price/stock/card; không lấy facts cũ làm authority.
- [ ] Phase 1 Customer/refinement/compare, Staff status, Admin scoped revenue và live role matrix anonymous/customer/staff/admin không regression. Dùng phiên đăng nhập hợp lệ qua UI chính thức nếu cần; không bypass/auth override cho live claims. Public internal endpoints vẫn 404; worker metrics không public.
- [ ] Đo event-to-index P95 từ generations mới trong một cửa sổ đủ mẫu, tách backlog lịch sử. Mục tiêu ≤60s khi tài nguyên phù hợp; có histogram source nhưng chưa có mẫu live Phase 2, không suy từ attempt duration hoặc unit tests.
- [ ] Có kiểm tra ngoài worker tối thiểu mỗi 60s để phát hiện worker unavailable hoặc `oldest_pending_seconds>300`. Existing status API/private gauges cung cấp số liệu; Prometheus hiện không chạy và chưa có alert rule hoạt động. Không bật thêm monitoring stack trên máy thiếu RAM; chọn/duyệt cách giám sát nhẹ trước vận hành watch.

Dừng ngay nếu disk/RAM dưới ngưỡng, OOM, source/config/model/schema/ownership lệch, canary không completed, wrong scope/hard constraints, backlog tăng không giải thích, lock connection mất hoặc writer khác xuất hiện. Stop worker, bảo toàn diagnostics/jobs; retry/restore chỉ theo mục 9 và approval, không sửa dữ liệu nghiệp vụ để làm ca PASS.

## 12. Rủi ro còn lại, bằng chứng cuối và phạm vi cần phê duyệt

Chưa có real PG advisory/Cypher write fault tests, backup restore drill mới, worker image, real encode measurements, reconciliation/live acceptance hoặc P95 live. Đặc biệt P2-R1 chưa được chứng minh dưới partition/in-flight writes; một session lock không tự tạo CAS xuyên stores. Nếu isolated tests không đáp ứng semantics cần thiết, phải chốt thiết kế/giới hạn vận hành trước, không tiến hành canary dựa trên mock PASS. Không đổi collection/dimension/schema hoặc thêm cột để lách giới hạn khi chưa được phê duyệt.

Drift/backlog vẫn giữ nguyên ở môi trường thật. Đối chiếu đầu/cuối chứng minh products/jobs, graph properties/relationships, Qdrant payloads và vector hashes, container IDs/images/env/mounts đều không đổi; 574 file frontend giữ nguyên. Hai API image IDs vẫn là `3b0af54884958d9adb0b41c047501245aa04fa7c2faf134604972d50623a62cc` và `0f1315e99652ff4624c5358ecda72f0bfd053c2654dce4119b06e6b6bbc66e68`. Không khởi index-worker hoặc bật LLM flags, không Phase 3.

Artifacts chính dưới `.local-tmp/phase2/`:

- `baseline.json`, `baseline-after.json`, `baseline-drift-final.json`, `preservation-check.json`: raw evidence và invariants, không chỉ counts.
- `backend-targeted.xml`, `backend-regression.xml`, `backend-mutation-contract.xml`, các log tương ứng; AI `test_*.json`, `regression-test_*.json` và logs. Với pattern lặp chọn `regression-*` cuối, không cộng trùng.
- `changed-files.json`, `source-manifest-final.json`: scope nguồn, provenance/343 inputs và syntax review.
- `worker-limited.yaml`, `recovery-preflight.json`: cấu hình kế hoạch đã validate, RAM/model/snapshot metadata/old-backup TOC; không chứa env secrets hoặc recovery proof giả.
- `collect_baseline.py`, `prepare_plan.py`: hai helper phục vụ lấy bằng chứng và validate kế hoạch, không phải scripts thử nghiệm ghi index. `--output` của collector không ghi đè artifact cũ.

**Phạm vi phê duyệt tại thời điểm bàn giao chuẩn bị (lịch sử):** môi trường/test server cô lập và tài nguyên cần thiết; maintenance backup/restore drill (gồm stop/start Neo4j nếu chọn cold archive); build/new-image tests đúng worker; quyền xử lý đúng năm job và ghi projections/replay có mục tiêu sau khi gates đạt; rồi mới xem xét một worker watch và giám sát liên tục nếu máy đủ RAM. Người dùng đã phê duyệt bước Phase 2B tương ứng; mục 13 ghi kết quả thực hiện. Phê duyệt không cho phép sửa business data/schema, xóa501, full rebuild, đổi model/flags, prune hoặc bỏ qua các gate.

## 13. Phase 2B — thực hiện sau phê duyệt, dừng tại gate tài nguyên

### 13.1 Kết luận và phạm vi thực tế

Ngày 27/11/2026, khoảng 17:48–17:53 UTC+7: **BLOCKED_RESOURCE_GATE, không PASS toàn bộ và chưa đạt cả bounded synchronization.** Phần chuẩn bị source/tests trước đây và kiểm tra phục hồi sau maintenance đã có bằng chứng; phần triển khai/synchronization vẫn chưa nghiệm thu. Không được diễn giải kết quả bảo toàn dữ liệu `preservation-final.json: pass=true` thành Phase 2 PASS: chính artifact đó có `projection_contract_pass=false`.

Đã ghi toàn bộ inventory container IDs/images/states/mounts/limits, images/digests, volume metadata, environment hashes và allowlist feature flags trước maintenance. Không xuất credentials. Manifest mới khớp toàn bộ 343 file với bản cuối đợt chuẩn bị: `5a71ccaf0bcb9e8b4bac12858d9d96acd0e07f96e09877d8e2340ddef30fcce8`; HEAD vẫn `1a432c170164fa9eeb07a189d6c0edd306713f67`. Build inputs không đổi nên không chạy lại các bộ unit/regression đã hoàn thành. Các probe dưới đây phục vụ kiểm tra sau stop/start, không phải chạy lại bộ test cũ.

### 13.2 Maintenance và số đo tài nguyên

Tạm dừng tuần tự `ai-api`, `neo4j`, `qdrant` bằng đúng IDs đã lưu trước thao tác. PostgreSQL, Business API, frontend và reverse-proxy vẫn chạy. Không thay WSL/Docker memory settings hoặc swap. Neo4j được stop/start sạch nhưng **không tạo cold backup** trong lần này.

| Thời điểm UTC+7 | Host RAM available | VM MemAvailable | C/D free | Kết quả |
| --- | --- | --- | --- | --- |
| 17:48:58, trước maintenance | 784.261.120 bytes ≈0,730 GiB | 1.434.865.664 bytes ≈1,336 GiB | ≈68,51/50,72 GiB | Chưa đủ headroom worker |
| 17:49:49, sau stop ba services | 1.012.609.024 bytes ≈0,943 GiB | 3.092.717.568 bytes ≈2,880 GiB | ≈68,51/50,72 GiB | Host vẫn dưới 1,5 GiB |
| 17:50:44, ngay trước dự kiến tạo PG test | 767.971.328 bytes ≈0,715 GiB | 3.064.213.504 bytes ≈2,854 GiB | ≈68,51/50,72 GiB | Dừng trước mọi tạo test resource |
| 17:52:59, sau khôi phục | 891.678.720 bytes ≈0,830 GiB | 1.583.296.512 bytes ≈1,475 GiB | ≈68,51/50,72 GiB | Chỉ vận hành services cũ; không thêm worker |

Tổng RAM host 8.303.452.160 bytes ≈7,73 GiB; VM 3.965.362.176 bytes ≈3,69 GiB. RAM VM được giải phóng nhưng host không lấy lại đủ headroom trong các mẫu đo; chưa xác định nguyên nhân phân bổ bộ nhớ phía host. Không suy luận VM còn RAM đồng nghĩa host đủ RAM để build/load model.

Guard trước môi trường fixture PG nhẹ cũng dừng: phương án giới hạn server 256 MiB, không model, kiểm tra host tối thiểu 768 MiB và VM 1,75 GiB; host lúc đó thấp hơn cả mức này. Đây **không phải** thay ngưỡng worker 1,5 GiB thành 768 MiB. Guard chạy trước tạo env credentials, network, volume hoặc container; inventory trước/sau xác nhận không có container/image/volume mới. Không thử OOM, không hạ ngưỡng để tiếp tục. Sau điểm dừng chỉ thực hiện khôi phục và kiểm tra nhẹ, không chạy công đoạn nặng khác.

Sau khôi phục, Docker stats: AI ≈740,2 MiB; Neo4j ≈674,5 MiB; Qdrant ≈132,8 MiB; Business API ≈98,29 MiB; PostgreSQL ≈72,24 MiB; frontend ≈9,61 MiB; proxy ≈7,77 MiB. Đây là mẫu đo, không phải peak benchmark hay bằng chứng capacity của worker. Không có OOM ở các container đang phục vụ.

### 13.3 Các gate đã thực hiện và còn BLOCKED

| Công đoạn | Trạng thái thực tế |
| --- | --- |
| Preflight inventory, fresh read-only baseline, manifest | PASS trong phạm vi kiểm tra |
| Maintenance có ghi IDs và khôi phục cùng container | PASS |
| RAM cho triển khai | BLOCKED; thiếu host headroom ngay cả khi ba dịch vụ lớn đã tạm dừng |
| Real-server concurrency/advisory/lease/process-kill/connection-loss/out-of-order | NOT RUN / BLOCKED tài nguyên; không có fault-test PASS hoặc FAIL mới |
| Neo4j query/tombstone và partial failure/recovery qua server thật | NOT RUN / BLOCKED tài nguyên; P2-R1 vẫn chưa được chứng minh |
| Ba backup mới, checksums và restore drill cô lập | NOT RUN / BLOCKED tại gate trước đó; không dùng backup cũ làm proof, không bỏ gate để deploy |
| Build index-worker, image provenance/COPY checksums, new-image tests | NOT RUN / BLOCKED; chưa có new image để kiểm thử |
| Canary235 → 1 → 488 → 19 → 501, batch1/CPU1 | NOT RUN / BLOCKED; không claim/ack/enqueue job thật |
| Targeted replay/idempotency/embedding-cache live | NOT RUN / BLOCKED |
| Continuous watch, live P95 và external queue alerting | Chưa nghiệm thu; không bật watch hoặc monitoring stack |

Không rebuild/recreate hai API hoặc frontend; không sửa nguồn triển khai trong lần Phase 2B này. Không chạy fixture write trên dữ liệu thật, đổi model/collection/flags, sửa business data/schema, xóa501, full reindex, prune hoặc xóa volume. Không commit/push/merge hoặc chuyển Phase 3. Những quyền Phase 2B đã cấp không bị coi là chưa phê duyệt; điều kiện cần giải quyết trước khi tiếp tục là tài nguyên và các gate kỹ thuật, không phải xin lại cùng phạm vi.

### 13.4 Trạng thái services, bảo toàn dữ liệu và kiểm tra phục hồi

Cả bảy services phục vụ đã chạy lại, đúng container IDs/images/env hashes/mounts/flags ban đầu; các QA containers và `lumiere-postgres17` vốn dừng tiếp tục được giữ nguyên trạng thái dừng. Docker health: AI, Business API, frontend, reverse-proxy, PostgreSQL, Neo4j đều `healthy`. Qdrant không có Docker healthcheck; collection read/scroll thành công và semantic readiness trả 200. Không có index-worker hoặc Ollama container mới chạy.

| Service có maintenance | Container ID giữ nguyên (prefix) | Kết quả cuối |
| --- | --- | --- |
| ai-api | `ba362ee70415` | running/healthy; image Phase 1 `3b0af54884958d9adb0b41c047501245aa04fa7c2faf134604972d50623a62cc` |
| neo4j | `9fb34799866b` | running/healthy |
| qdrant | `d5e9c04aeae5` | running; collection đọc được |

Business API giữ container `553322d4a853`, image Phase 1 `0f1315e99652ff4624c5358ecda72f0bfd053c2654dce4119b06e6b6bbc66e68`. Frontend giữ `341d97461bdb`; SHA-256 của **574 file** không đổi. Tất cả images và volume metadata trước/sau bằng nhau; không phát sinh test volume/container.

Đối chiếu raw baseline trước/sau: SQL products/jobs/schema, toàn bộ Business API products, graph properties/edges/constraints/orphan entities, Qdrant payloads/vector hashes/config đều giữ nguyên. Chạy lại toàn bộ projection comparator trên snapshot sau khôi phục cho đúng **năm issues cũ**: thiếu501 ở graph/vector và graph stock lệch1/19/488. Các contract còn lại không phát sinh drift mới. 501 còn nguyên trong SQL/API, stock0; chưa có projection. Không công nhận projection contract PASS khi các lỗi cũ chưa được xử lý.

Backlog giữ **pending5, done496, processing0, dead0**, attempts0, không lease hoạt động. Các cặp generation/delivered_generation giữ nguyên: 235=5/3, 1=17/4, 488=7/4, 19=4/3, 501=2/0. Last success vẫn `2026-11-23T06:43:53.339101+00:00`; backlog già tiếp tục là vấn đề vận hành, không được che bằng reset jobs.

Kiểm tra phục hồi live tuần tự:

- `/ai/health/ready`, `/ai/health/semantic`, `/api/health/ready`: HTTP200; semantic `ready=true`.
- Customer qua `/ai/chat`: tìm nhẫn dưới5 triệu → đổi vòng tay → tăng ngân sách dưới10 triệu → so sánh hai mẫu; cả bốn HTTP200/PASS, giữ conversation. Mỗi card được đối chiếu category/giá/stock với Business API; stock>0 và giá đúng hard constraint; compare tham chiếu đúng hai IDs vừa hiển thị. Model đã nạp trong service cũ; không bật LLM.
- Anonymous POST `/api/staff/ai/chat` và `/api/admin/ai/chat`: HTTP401; `/internal/metrics` và `/ai/internal/metrics`: HTTP404.
- Hai GET ban đầu dùng sai đường dẫn Staff/Admin trả404: **invalid probe**, loại khỏi nghiệm thu và thay bằng đúng POST endpoints ở trên. Giữ raw record để truy vết; không coi404 của route sai là RBAC proof.
- Ma trận đăng nhập Customer/Staff/Admin và các truy vấn Staff/Admin có xác thực: **NOT RUN trong Phase 2B**, vì đã dừng tại resource gate, không dùng phiên đăng nhập nào. Acceptance Phase 1 trước đây vẫn là bằng chứng lịch sử; không tái gắn nhãn thành live Phase 2B PASS. Không tạo session/account, lấy cookie trình duyệt cá nhân hoặc bypass auth.

### 13.5 Artifacts và điều kiện tiếp tục

Artifacts lần thực hiện tập trung tại `.local-tmp/phase2/phase2b-20261127/`:

- `runtime-before.json`, `runtime-after.json`, `stopped-container-ids.txt`, `resources-after-maintenance.json`, `resources-before-isolated-postgres.json`: inventory, kế hoạch phục hồi bằng ID và số đo thật.
- `source-manifest.json`, `baseline-before.json`, `baseline-after.json`, `preservation-final.json`: provenance và so sánh bảo toàn toàn bộ dữ liệu/frontend/runtime. `preservation-final.pass=true` chỉ nói phục hồi/bảo toàn, không nói đồng bộ đã thành công.
- `projection-contracts-after.json`, `backlog-after.json`: năm issues và năm pending jobs còn nguyên, không giấu BLOCKED.
- `restoration-live.json`: raw probes; `restoration-final.json`: kết quả hợp lệ cuối, tách invalid route probes và giới hạn anonymous/authenticated.
- `maintenance.py`, `isolated_servers.py`, `restoration_checks.py`, `verify_preservation.py`: helpers tái hiện phép đo/guard/so sánh. Nhánh tạo server trong helper chưa chạy qua resource guard nên không được coi đã kiểm chứng; không có artifact fault tests/backup/image/canary vì các bước đó chưa được thực hiện.

Chỉ tiếp tục công đoạn nặng khi có headroom ổn định đáp ứng kế hoạch, đo lại fresh baseline và xác nhận không có writer khác. Khi đó vẫn phải lần lượt hoàn thành real-server fault tests (đặc biệt P2-R1), ba backup/restore drills, worker-only build/provenance/new-image tests rồi mới canary/replay/live acceptance. Không đề xuất bỏ bước nào vì thiếu RAM. Với số đo hiện tại, chưa đủ căn cứ vận hành thêm continuous worker đồng thời với stack hiện hành; cần giải quyết capacity và cơ chế giám sát trước khi đánh giá lại.

### 13.6 Tiếp tục sau restart — 27/11/2026, 18:10 UTC+7

**Kết quả: BLOCKED_RESOURCE_GATE; dừng an toàn trước mọi khởi động container.** Người dùng xác nhận máy đã restart và yêu cầu tiếp tục mục 9–13 với maintenance luân phiên đã được phê duyệt. Docker daemon truy cập được sau khi dùng quyền đọc Docker ngoài sandbox; không có automatic approval rejection. Lệnh đọc ban đầu trong sandbox không truy cập được named pipe; helper cũ cũng không đo được VM qua `docker exec` vì PostgreSQL đang dừng. Đã chuyển sang đọc `/proc/meminfo` bằng `wsl -d docker-desktop`, không khởi động container để lấy số đo.

| Thời điểm UTC+7 | Host available (bytes / GiB) | VM MemAvailable (bytes / GiB) | C/D free GiB | Gate worker |
| --- | --- | --- | --- | --- |
| 18:10:05 | 509.173.760 / 0,474 | 3.345.371.136 / 3,116 | 67,85 / 50,72 | FAIL host |
| 18:10:11 | 659.890.176 / 0,615 | 3.344.093.184 / 3,114 | 68,18 / 50,72 | FAIL host |
| 18:10:16 | 677.474.304 / 0,631 | 3.343.867.904 / 3,114 | 68,18 / 50,72 | FAIL host |

Tổng RAM host 8.303.452.160 bytes (7,73 GiB), VM 3.965.353.984 bytes (3,69 GiB). VM có swap 1 GiB, toàn bộ còn trống tại các mẫu; không thay cấu hình swap/WSL/Docker. Mẫu thăm dò trước đó ghi host 858.996 KiB (0,819 GiB), VM 3.269.056 KiB (3,118 GiB): cũng không đạt host ≥1,5 GiB. Ba mẫu chính đều thấp hơn cả guard fixture nhẹ 768 MiB của helper trước đây; không tạo fixture/server/network/volume/credentials. Maintenance không thể giải phóng thêm RAM từ services vì chúng đã dừng hết.

**Trạng thái vận hành khi bàn giao:** PostgreSQL, Neo4j, Qdrant, Business API, AI API, frontend và reverse-proxy đều `exited`, giống đầu lần kiểm tra này; ba QA containers cũng dừng. Không có worker đang chạy. AI/Neo4j có exit137 nhưng `OOMKilled=false`; không kết luận OOM từ exit code sau restart. Không thực hiện start/stop/recreate trong lần này. Việc khôi phục services cũ cũng chưa thực hiện do headroom thấp; đây là outage hiện hữu sau restart, không phải trạng thái running/healthy của lần trước.

10 container hiện còn giữ image IDs, mounts, environment hashes và feature flags khớp inventory cuối lần trước. Tập container **không hoàn toàn bằng lần trước**: `lumiere-postgres17` (`cc75526185d5`, vốn dừng) đã không còn trước lần kiểm tra này; không xác định nguyên nhân và không tái tạo/xóa gì. Inventory đầu/cuối lần kiểm tra mới bằng nhau. Manifest vẫn khớp cả 343 file và SHA-256 `5a71ccaf0bcb9e8b4bac12858d9d96acd0e07f96e09877d8e2340ddef30fcce8`; branch `update-ai`, HEAD `1a432c170164fa9eeb07a189d6c0edd306713f67`. Không chạy lại Phase 2A/unit/regression đã có bằng chứng hợp lệ.

Không đọc được fresh baseline SQL/API/graph/vector vì services đang dừng; **không tái khẳng định** số liệu pending5/done496 hoặc drift lịch sử là số đo sau restart. Không có fresh health/live acceptance hoặc proof bảo toàn nội dung datastore trong lần này. Fault tests, ba backup/restore drills, worker build/new-image tests, canary/replay và live acceptance đều **NOT RUN / BLOCKED**, không có PASS mới. P2-R1 vẫn chưa được chứng minh; không bỏ safety gates để triển khai.

Bằng chứng bổ sung nằm cùng thư mục hiện có `.local-tmp/phase2/phase2b-20261127/`: `post-restart-preflight.json` chứa ba mẫu timestamp, sanitized inventory đầu/cuối, đối chiếu runtime/source và working sets của 10 process lớn nhất; `post_restart_preflight.py` là collector chỉ đọc, ghi artifact bằng create-exclusive. Không tạo báo cáo Phase 2 mới.

**Phương án tiếp tục:** giải phóng RAM ứng dụng host do người dùng quản lý (snapshot thấy Chrome khoảng 495 MiB và nhiều process VS Code khoảng 215–350 MiB mỗi process; working sets không được cộng như RAM chắc chắn thu hồi được), hoặc tăng RAM vật lý/chuyển công đoạn test/build sang máy riêng đủ tài nguyên. Không tự đóng ứng dụng cá nhân, thay memory settings hoặc di chuyển dữ liệu. Với mẫu cuối cần thêm ít nhất khoảng 0,87 GiB available chỉ để chạm gate host khi stack vẫn dừng; đây không phải ước lượng đủ capacity khi khôi phục stack/load model. Sau khi giải phóng RAM, đo lại host/VM/disk trước và trong khôi phục tuần tự đúng container IDs, kiểm health và fresh baseline; chỉ tiếp tục khi headroom ổn định. Máy riêng có thể phục vụ isolated fault tests/build nhưng không thay gate backup/restore mới và canary/live acceptance tại môi trường đích. Phê duyệt Phase 2B/maintenance đã có vẫn được giữ; không tự bật watch hoặc chuyển Phase 3.
