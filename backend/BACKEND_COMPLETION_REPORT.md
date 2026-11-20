# LUMIÈRE — Backend audit & completion

Ngày: 20/11/2026 (Asia/Bangkok). Phạm vi: Business Backend hiện có trong `.`.

## Audit trước khi sửa

Mốc là working tree tại đầu lượt này, không phải Git HEAD: repo đã có nhiều thay đổi và file untracked. Snapshot code nằm ở `.cache/backend-completion/before/`; OpenAPI ở `.cache/backend-completion/openapi-before.json`; checksum các đường dẫn được bảo vệ ở `initial-hashes.json` cùng thư mục. Không xóa hay ghi đè thay đổi có sẵn.

### Kiến trúc đọc từ code

- Toàn hệ thống giữ 3 tier: Frontend → FastAPI Business Backend / AI service → persistence. Backend không import runtime từ `AI/`. Các assistant nghiệp vụ trong `backend/app/services/ai_*` đọc cùng ORM, Ollama chỉ phân loại intent.
- `app/main.py` đăng ký 14 router. Router dùng Pydantic schemas và `core.dependencies` để xác thực cookie/session, kiểm tra customer/staff/admin; SQLAlchemy Session theo request qua `core.database.get_db`.
- Các router auth/catalog/taxonomy/contact/orders/payments/coupons/customer_content/dashboard/admin_* gọi services hiện hữu; services xử lý quy tắc và ORM trực tiếp. Đây là Modular Monolith + Layered Architecture, không phải Clean Architecture toàn phần.
- Riêng Cart: `routers/cart.py` → `application/cart.CartService` → protocol/rule `domain/cart.py` → `infrastructure/cart.SqlAlchemyCartRepository` → ORM. Adapter ánh xạ lỗi domain sang HTTP, mutation commit/rollback trong infrastructure. Giữ nguyên cấu trúc chọn lọc này.
- Orders dùng transaction chung và khóa user → cart items → products theo ID → coupon; hủy khóa actor → order → products → coupon. Payments khóa actor → order; IPN khóa order → payment. Stock update dùng user → product và expected_stock để chống ghi đè số liệu cũ.
- ORM ở `app/models/` dùng một Base/engine; không thêm database, schema hay migration.

### Phân loại và cách sửa tối thiểu

| ID | Mức | Bằng chứng trước sửa | Tác động và phương án |
|---|---|---|---|
| DB-01 | P1 | `app/core/database.py:25-28`: create_engine chỉ bật pool_pre_ping; không connect_timeout/statement_timeout/lock_timeout. Pool hữu hạn mặc định nhưng chờ pool mặc định 30 giây. | Query treo/chờ khóa có thể giữ connection và worker dùng chung. Thêm giới hạn chờ pool, kết nối và query/lock theo cấu hình; kiểm chứng cấu hình offline, không kết nối PostgreSQL. |
| LLM-01 | P1 | `app/services/ai_admin_llm.py:75-82`: JSON content được parse rồi gọi parsed.get không kiểm tra dict; wrapper không bắt AttributeError. | JSON list/null từ LLM làm endpoint 500. Kiểm tra kiểu trước khi dùng, trả unsupported theo contract hiện hữu. |
| LLM-02 | P1 | `app/services/ai_admin_llm.py:71` timeout 60 giây; `ai_staff_llm.py:107` timeout 20 giây; auth đã đọc DB trước khi router gọi LLM. | Dịch vụ chậm giữ request worker và có thể giữ connection đọc trong thời gian dài. Giảm socket timeout xuống 5 giây, giữ fallback; chưa bảo đảm cách ly khi tải lớn hay server gửi dữ liệu nhỏ liên tục. |
| MONEY-01 | P1 | `services/orders.py:102`, `services/coupons.py:201`: cộng shipping ngoài localcontext dù subtotal cho phép đến gần 10^36. Test exact Decimal với 5 sản phẩm giá 9999999999999999.99, quantity 2147483647 cho total .6 thay vì .65, kể cả khi shipping bằng 0. | Lệch tiền/vi phạm ck_orders_total ở giá trị hợp lệ lớn. Giữ precision 50 cho phép cộng cuối ở checkout và coupon preview; không đổi schema/giới hạn đầu vào. Log tái hiện ban đầu dùng shipping giả lập 30000; test cuối dùng shipping 0 đúng chính sách miễn phí ở giá trị này. |
| RETRY-01 | P1 / blocker contract | `application/cart.py:35-36`: POST cộng quantity hiện có. `services/orders.py:73-80`: checkout dùng giỏ hiện tại, không có request key. | Cart POST lặp tăng số lượng; checkout lặp trên giỏ rỗng trả 409, nhưng giỏ được thêm lại trước retry có thể tạo đơn mới. Không thể phân biệt retry và ý định mới một cách bền vững với contract/schema hiện tại. Không tự thêm idempotency header/cột; cần thống nhất riêng. |
| ARCH-01 | P2 | `routers/ai_admin.py:123` và `routers/ai_staff.py:74` còn orchestration, intent validation và định dạng câu trả lời. | Có nghiệp vụ trong router; chuyển xuống service hiện hữu khi có nhu cầu bảo trì. Không refactor cơ học trong lượt P0/P1. |
| ARCH-02 | P2 | `routers/admin_customers.py:11`, `routers/coupons.py:8-9` import Search/SafeValidationRoute từ router khác. | Coupling giữa router nhưng không thấy vòng import top-level. Giữ compatibility exports, chưa tạo abstraction mới. |
| ARCH-03 | P2 | `services/orders.py` local-import coupons/payments; hai service này import helper từ orders. | Vòng phụ thuộc logic tồn tại nhưng local import tránh lỗi khởi tạo module hiện tại. Không tách transaction framework chỉ để phân tầng. |
| OPS-01 | P2 | `services/orders.py:33-38` và `infrastructure/cart.py:26-31` sanitize lỗi SQL nhưng không ghi log nguyên nhân nội bộ; observability chỉ có status/duration. | Chẩn đoán lỗi DB hạn chế. Không log query/parameters/PII; cần chính sách log lỗi tập trung khi triển khai. |
| PERF-01 | P2 | `services/taxonomy.py:21-24` đếm product từng lookup; `services/orders.py:162-169` list chưa eager-load items. | N+1 queries; không phải bằng chứng sai nghiệp vụ hay lỗi P1 ở tải hiện tại. |

Không phát hiện P0 có bằng chứng trong phạm vi kiểm tra. Điều này không có nghĩa đã chứng minh hệ thống không còn P0.

### Code sinh thêm, demo và references

- AST audit 92 module backend: không có vòng import top-level trong graph đã phân giải import tuyệt đối, tương đối và import alias/submodule (`.cache/backend-completion/import-audit.json`). Vòng local import ghi riêng ở ARCH-03; kiểm tra tĩnh không bao phủ dynamic imports.
- Application/Domain/Infrastructure của Cart đều được router/adapter/tests tham chiếu; không phải code chết.
- `routers/auth.py` export lại dependency/hash token và `routers/catalog.py`, `routers/taxonomy.py` export lại helper để tương thích; tests còn dùng các export này. Không xóa chỉ vì import trông dư.
- `app/import_catalog.py` được regression tests/CLI và tài liệu import tham chiếu; `app/init_db.py`, `backend/create_admin.py` là công cụ vận hành, không phải module route. Không tự chạy vì có thể ghi DB.
- Không tìm thấy nhánh demo/mock/fake trong runtime backend qua tìm kiếm văn bản. Fixture ở tests là dữ liệu giả phục vụ kiểm thử; giữ nguyên. Không thể kết luận tác giả của file từ tên/Codex; chỉ đánh giá references và vai trò.
- Các helper transaction/role/serialize có lặp ở vài module nhưng thông báo và quy tắc khác nhau; giữ để tránh refactor vượt phạm vi. Không đủ bằng chứng xóa toàn bộ file nào.

## Thay đổi hoàn tất

DB-01, LLM-01, LLM-02 và MONEY-01 đã sửa. RETRY-01 giữ nguyên và là blocker nếu yêu cầu retry có cùng kết quả một cách bền vững. Không phát hiện nhu cầu migration hay thay contract để thực hiện các bản sửa đã chọn. Không thêm abstraction, repository, service hay file runtime.

### Danh sách GIỮ / SỬA / XÓA

Đường dẫn trong hai bảng dưới tính từ `backend/`. Số dòng so với snapshot đầu lượt, đã kiểm tra checksum; không tính thay đổi có sẵn của người dùng. Dòng thay thế được tính một lần thêm và một lần xóa.

| File SỬA | Thêm | Xóa | Lý do |
|---|---:|---:|---|
| `app/core/database.py` | 15 | 0 | Giới hạn chờ pool, connect và query/lock; cấu hình phải là số nguyên dương. |
| `app/services/ai_admin_llm.py` | 4 | 1 | Chặn JSON sai kiểu; socket timeout 5 giây. |
| `app/services/ai_staff_llm.py` | 1 | 1 | Socket timeout 5 giây, giữ fallback hiện hữu. |
| `app/services/orders.py` | 3 | 1 | Cộng shipping với Decimal precision 50. |
| `app/services/coupons.py` | 5 | 2 | Preview total dùng cùng precision; bao gồm chuẩn hóa newline cuối file. |
| `tests/test_ai_admin_llm.py` | 24 | 0 | Tái hiện JSON list/null/scalar và timeout. |
| `tests/test_ai_staff_llm.py` | 7 | 0 | Timeout injection vẫn fallback đúng. |
| `tests/test_health_probes.py` | 34 | 0 | Kiểm tra engine options offline; pool cạn với hai request đồng thời và phục hồi. |
| `tests/test_observability.py` | 19 | 0 | Endpoint ném exception rồi endpoint khác vẫn trả lời; metrics ghi 500. |
| `tests/test_orders_api.py` | 35 | 0 | Exact Decimal lớn cho checkout và coupon preview, tránh sai số SQLite Numeric. |

Tổng: **10 file Python sửa, +147/-5 dòng**, trong đó runtime **+28/-5**, tests **+119/-0**. Tăng code chủ yếu để tái hiện và kiểm chứng các lỗi có ảnh hưởng tài chính/khả dụng. Thêm đúng **1 file bàn giao** là `BACKEND_COMPLETION_REPORT.md` (151 dòng); tổng file sản phẩm/bàn giao thay đổi là **11**, tính cả báo cáo **+298/-5 dòng**, không xóa file nào.

| Nhóm GIỮ | Lý do |
|---|---|
| Toàn bộ router, schema và ORM | Giữ endpoint, quyền, request/response, constraints và database schema. |
| Cart Application/Domain/Infrastructure | Đang được sử dụng; transaction/khóa và tests hiện hữu hoạt động. |
| Services khác, công cụ import/init/admin và compatibility exports | Có references hoặc là entrypoint vận hành; không có bằng chứng đủ để xóa. |
| `backend/alembic/`, `AI/`, `frontend/` | Ngoài phạm vi sửa; không thay đổi migrations, AI hay UI. |
| Thay đổi/untracked/checkpoint/data có sẵn | Bảo toàn; không reset, clean, commit, push hay merge. |

**XÓA: không có.** Snapshot, logs, OpenAPI, bản sao runner smoke và profile trình duyệt thử nghiệm nằm riêng tại `.cache/backend-completion/`; không phải runtime mới. Baseline regression log nằm tại `.cache/backend-audit-baseline.log`.

## Kết quả verification

Các Python tests chạy qua `scripts/run_business_checks.py --sqlite-bootstrap --pytest`: vô hiệu đọc `.env` khi bootstrap, và chặn mọi `Engine.connect` trừ SQLite `:memory:`. Không chạy PostgreSQL thật, migration online hoặc gọi VNPay thật. Payment adapter hiện ký/kiểm chữ ký cục bộ, không gửi request tới gateway.

| Kiểm tra | Kết quả | Bằng chứng và giới hạn |
|---|---|---|
| Regression trước sửa | PASS | `640 passed, 827 subtests passed` trong `88.79s`; `.cache/backend-audit-baseline.log`. |
| Tái hiện trước sửa | FAIL có chủ đích | `repro-before.log`: 4 failed, 15 passed; gồm AttributeError của JSON list và thiếu giới hạn chờ. `precision-before.log`: 1 failed, 49 passed, chênh .05 ở tổng tiền. |
| Nhóm sửa LLM/DB/exception ban đầu | PASS | `targeted-after.log`: 19 passed. |
| Backend regression cuối | PASS | `647 passed, 827 subtests passed, 1 warning` trong `65.86s`; `.cache/backend-completion/regression-complete.log`. Bao gồm auth/profile, RBAC, orders/cart/payments/inventory, coupons và assistant nghiệp vụ. |
| OpenAPI trước/sau | PASS | So sánh toàn bộ JSON: bằng nhau, **60 paths / 74 operations**. Cả hai SHA-256: `a0628e08567b2e53a024036f385b32310d8cd6078a1b268b9bcf215762213f61`. `openapi-comparison.json`. |
| Auth và role permissions | PASS | Existing `test_auth_profile`, `test_admin_*`, `test_ai_role_access_matrix`, `test_ai_staff_scope_safety`, tests route Orders/Payments/Stock; browser Customer/Staff/Admin và 403 khi Customer đọc admin orders. |
| Rollback Cart/Orders/Payments/Inventory | PASS trên fixture | Existing tests inject commit/IntegrityError/SQLAlchemyError; kiểm tra cart, stock, order status và payment ledger không bị ghi một phần. Test IPN lỗi commit cho phép callback thử lại. Không thay thế kiểm chứng PostgreSQL. |
| Retry tuần tự | PASS trong phạm vi đã có | VNPay URL dùng lại transaction; duplicate IPN/COD không thu tiền lần hai; hủy đơn hoàn kho đúng một lần. Cart POST lặp cộng dồn theo contract hiện tại, không được đánh dấu idempotent. |
| Precision lớn | PASS ở service | `pool-precision-final.log`: 54 passed, 70 subtests. Kiểm tra Decimal exact với Session mock; persistence Numeric(38,2) trên PostgreSQL ở giá trị cực lớn chưa kiểm chứng. |
| Pool cạn / concurrent probes | PASS trên SQLite QueuePool | Giữ connection duy nhất, gửi readiness và liveness đồng thời: 503/200; thả connection rồi readiness 200. Không mô phỏng throughput thực tế. |
| Race checkout/cart/IPN/cancel/stock với row locks | NOT VERIFIED | Existing tests compile PostgreSQL SQL và kiểm tra thứ tự FOR UPDATE; SQLite không thực thi ngữ nghĩa row lock. Không chạy `pg_coupon_races.py` vì chưa có môi trường PostgreSQL test được xác nhận an toàn. |
| AI lỗi / dịch vụ ngoài timeout | PASS với injection | Ollama timeout và JSON sai kiểu vẫn fallback; browser chặn AI/recommendation, mua hàng vẫn hoạt động. Chưa gọi Ollama thật hay thử dịch vụ slow-stream. |
| Một endpoint lỗi | PASS với injection | Test exception 500 rồi GET khác 200; browser dashboard mất từng endpoint vẫn hiển thị phần độc lập. Không khẳng định fault isolation hoàn toàn. |
| Frontend unit | PASS | 14/14: `frontend-unit-direct.log`. Lệnh Node test mặc định gặp spawn EPERM do sandbox; chạy trực tiếp ba module test trong cùng tiến trình thành công. |
| Frontend browser smoke | PASS | 27 checks, `exceptions: []`; `browser/result.json`, `browser-smoke-final.log`. Chrome headless profile riêng, fixture SQLite in-memory, block AI/network lỗi theo script hiện hữu. Không sửa file Frontend. |
| AI/Frontend/routers/models/schemas/migrations giữ nguyên | PASS | `protected-paths.json`: 711 file hiện hữu đối chiếu checksum, `changed: []`. Không chứng minh các thay đổi vốn có trước lượt này là đúng. |

Lệnh tái chạy regression (PowerShell từ `.`):

```powershell
.venv\Scripts\python.exe scripts/run_business_checks.py --sqlite-bootstrap --pytest
```

Lệnh đã dùng để lưu OpenAPI là cùng runner với `--openapi .cache/backend-completion/openapi-before.json` hoặc `openapi-after.json`. Tests hiện có có thể làm chậm do hash mật khẩu; không khởi động DB thật để tăng tốc.

Frontend unit được chạy không tạo subprocess test workers:

```powershell
.cache\node.exe --input-type=module -e "await import('./frontend/tests/unit/asset-references.test.mjs'); await import('./frontend/tests/unit/dashboard.test.mjs'); await import('./frontend/tests/unit/http-client.test.mjs');"
```

Browser dùng `backend/tests/serve_browser_fixture.py` và bản sao `frontend/tests/browser-smoke.mjs` chỉ đổi đường dẫn evidence sang `.cache/backend-completion/browser/`. Chrome profile kiểm thử tách biệt, cổng debug bind localhost; không dùng phiên trình duyệt cá nhân.

## Rủi ro còn tồn tại và giới hạn bàn giao

- **P1 RETRY-01 chưa xử lý:** cần quyết định contract/idempotency và cơ chế lưu khóa bền vững trước khi có thể bảo đảm retry qua restart hoặc sau khi giỏ được bổ sung lại. Không thêm khóa tạm trong RAM vì không bảo đảm nhiều worker và không phân biệt ý định mới.
- DB timeouts mới được kiểm tra cấu hình offline; thực thi thật qua psycopg/PostgreSQL, proxy/pooler, rollback sau disconnect, deadlock và reconnect cần môi trường test riêng. Statement timeout 15s có thể cắt báo cáo chậm; điều chỉnh bằng biến môi trường dưới đây sau đo đạc.
- Engine/pool, process, threadpool và database vẫn dùng chung giữa module. LLM socket timeout 5s không phải deadline tổng của request; peer slow-stream và nhiều request đồng thời vẫn có thể giữ tài nguyên. Chưa load test hoặc thử restart worker.
- `get_db` cấp Session riêng theo request và `close()` trong finally; close trả connection/rollback transaction chưa commit. Các mutation trọng yếu có rollback riêng. Không có global exception handler tùy biến; lỗi ngoài các service được sanitize vẫn dùng response 500 mặc định, chi tiết chẩn đoán phụ thuộc logger Uvicorn.
- Các helper mutation sanitize lỗi SQL nhưng thiếu log nguyên nhân riêng (OPS-01). Request logs chỉ ghi route template, method, status, duration; không ghi cookie/body/query. `/metrics` công khai và chỉ giữ số liệu theo process, chưa có auth/aggregation; cần cấu hình mạng khi triển khai.
- Không có xác nhận VNPay end-to-end, IPN delivery/retry từ gateway, credential thực, HTTPS/reverse proxy hoặc hoàn tiền. Các trường hợp giao dịch không rõ/expired/review_required vẫn chặn tự hủy/tạo lại, cần đối soát thủ công theo logic hiện hữu.
- Các P2 ARCH/PERF giữ nguyên. Chưa xác minh dữ liệu production, dung lượng pool theo số worker, tải lớn, backup/restore hay schema drift giữa ORM/migrations/DB thật. Một warning của regression runner bị ẩn bởi `--disable-warnings`; chưa phân loại trong lượt này.

## Contract và cấu hình cần giữ ổn định cho Frontend / AI

Nguồn contract chính là OpenAPI snapshot và schemas hiện có; không suy luận response chỉ từ tên route. AI assistant nghiệp vụ trong backend đọc ORM theo quyền, không cung cấp công cụ ghi đơn/tồn kho tự do cho LLM.

| Nhóm | Điểm tích hợp giữ nguyên |
|---|---|
| Auth | `/auth/register`, `/auth/login`, `/auth/me`, `/auth/logout`; cookie HttpOnly `lumiere_session`, cùng Session dependency và role `customer/staff/admin`. Frontend phải gửi credentials. |
| Catalog | `/products`, `/products/{id}`, `/categories`, `/brands`; pagination/filter hiện hữu. Public response dùng `price_vnd` và Decimal serialize dạng chuỗi; không lộ cost/wholesale qua public schema. |
| Cart / checkout | `/cart`, `/cart/items`, `/cart/items/{id}`, `/checkout/coupon/validate`, `/orders`; giá/tồn kho do server đọc, không nhận total do AI/client tự tính. Cart không reserve kho; checkout trừ kho atomically. |
| Orders / inventory | `/orders/my`, `/orders/{id}`, `/admin/orders*`, `/staff/orders*`, `/staff/products/{id}/stock`; stock yêu cầu `expected_stock`; cập nhật giá yêu cầu `expected_sale_price`. Giữ state machine pending → confirmed → packing → shipping → delivered và nhánh cancelled hợp lệ. |
| Payments | `/checkout/payment-methods`, `/orders/{id}/payments/vnpay`, `/payments/vnpay/ipn`, `/payments/vnpay/return`, `/admin/orders/{id}/cod/confirm`, `/staff/orders/{id}/cod/confirm`; browser return chỉ đọc. IPN dùng `RspCode/Message`, không đổi thành schema error chung. |
| Analytics / assistants | `/admin/dashboard`, `/admin/reports/revenue`, `/admin/reports/purchase-behavior`, `/admin/ai/chat`, `/admin/ai/top-selling-products`, `/staff/ai/chat`, `/staff/ai/order-statistics`, `/staff/ai/inventory-statistics`; giữ payload message và response answer/intent/data hiện hữu. Báo cáo tiền là system-confirmed payments, không mặc định là lợi nhuận/net revenue. |
| Probe / metrics | `/health` và `/health/ready` kiểm tra DB; `/health/live` không phụ thuộc DB; `/metrics` không có trong OpenAPI. |

Cấu hình giữ nguyên: `POSTGRES_USER/PASSWORD/HOST/PORT/DB`, `CORS_ORIGINS`, `COOKIE_SECURE`, `SERVE_FRONTEND`, `ADMIN_AI_LLM_ENABLED`, `STAFF_AI_LLM_ENABLED`, `ADMIN_OLLAMA_URL/MODEL`, `STAFF_OLLAMA_URL/MODEL`, `VNPAY_ENABLED/TMN_CODE/HASH_SECRET/RETURN_URL`, `SHIPPING_FLAT_VND`, `SHIPPING_FREE_FROM_VND`. Không chép secrets vào report/log. CORS mặc định localhost:5500; cần cấu hình đúng origin khi tích hợp. Adapter VNPay hiện chỉ Sandbox, capability endpoint là nguồn xác định có bật được hay không.

Cấu hình bổ sung của DB (không đổi URL/schema):

| Biến | Mặc định | Ý nghĩa |
|---|---:|---|
| `DB_POOL_TIMEOUT_SECONDS` | 5 | Thời gian chờ lấy connection từ pool. |
| `DB_CONNECT_TIMEOUT_SECONDS` | 5 | Timeout libpq khi kết nối. |
| `DB_STATEMENT_TIMEOUT_MS` | 15000 | PostgreSQL statement timeout của connection ứng dụng. |
| `DB_LOCK_TIMEOUT_MS` | 5000 | PostgreSQL lock timeout của connection ứng dụng. |

Tất cả phải là số nguyên dương; cấu hình sai làm startup fail rõ ràng, không âm thầm vô hiệu timeout. Không thay pool_size/max_overflow; cần đánh giá theo số worker khi triển khai. Socket timeout Ollama hiện cố định 5 giây trong hai adapter nghiệp vụ backend; feature flags và kết quả fallback giữ nguyên.

## Bổ sung — Final dead code cleanup, 20/11/2026

Lượt cleanup riêng trên branch `refactor/business-frontend-20261119`; đã đọc báo cáo Frontend và Backend trước khi làm. Các thống kê ở phần trước thuộc lượt audit/sửa Backend trước đó; thống kê dưới đây chỉ tính phần cleanup mới, so với working tree đầu lượt này. Không đổi branch, không reset/clean/commit/push/merge.

### Checkpoint và bằng chứng trước khi xóa code

Checkpoint: `.cache/final-cleanup-20261120-133437/before.zip` gồm 734 file Frontend/Backend, kèm `manifest.json` SHA-256, `git-status-before.txt` và `git-diff-before.patch`. Loại trừ node_modules, caches và test-results. Đã đối chiếu checksum ba file sẽ sửa với bản trong ZIP trước khi sửa. `.cache/` được Git ignore. Khôi phục chọn lọc đúng file từ ZIP sau khi kiểm tra manifest; không giải nén đè toàn workspace vì có thể mất thay đổi sau checkpoint.

Evidence của lượt này đều nằm trong thư mục checkpoint trên. `cleanup-symbol-references-before.json` lưu references của symbol trước cleanup; `runtime-changes.patch` là diff riêng của lượt này, không lẫn thay đổi sẵn có từ HEAD.

### File/code đã xóa

**Không xóa nguyên file nào.** Chỉ sửa ba file tracked sau:

| File và dòng trước cleanup | Code bỏ | Bằng chứng an toàn |
|---|---|---|
| `app/routers/auth.py:9` | Import `SESSION_DAYS` | Không có Name load trong router hoặc consumer của export `auth.SESSION_DAYS` trong source đã rà. Logic tạo session tiếp tục dùng constant từ `core.security` trong `services/auth.py`. Giữ nguyên hai compatibility exports được dùng. |
| `app/services/payment_providers.py:4` | Import `datetime` | AST không có chỗ đọc symbol; không có import/patch/attribute consumer của symbol này. `timedelta`, `timezone` vẫn dùng và giữ nguyên. |
| `app/services/purchase_behavior.py:3`, `:5`, `:11` | Imports `defaultdict`, `Decimal`, `Product` | AST không có Name load; không có consumer import/patch các symbol này từ module. Vẫn import cùng package `app.models` qua Order/OrderItem, không mất đăng ký models. |
| `app/services/purchase_behavior.py:25` | `order_ids = [row.id for row in orders]` | Chỉ có phép gán, không có chỗ đọc. Bỏ việc tạo list ID dư; các query, phép đếm, response và thứ tự xử lý dữ liệu giữ nguyên. |

Tổng runtime: **3 file sửa, +4/-6 dòng vật lý, ròng -2**; bỏ 5 import bindings và 1 biến/list trung gian. Đây là thay thế dòng import, không thêm logic. Không sửa tests hoặc tạo module/layer mới. Hai báo cáo hiện có được bổ sung phần bàn giao; không thêm báo cáo standalone.

### File giữ lại, code nghi dư và duplicated implementations

| File/nhóm | Kết luận và lý do |
|---|---|
| `frontend/assets/js/site_1.js` | **Ứng viên, chưa xóa/sửa.** Không có incoming reference trong HTML/literal imports/computed loader đã rà; file untracked, nguồn gốc và mục đích giữ bản này chưa xác minh. Có duplicate declarations `adminPage` ở 388/390, `staffPage` ở 389/391, `checkout` ở 146/423 và code cũ. |
| 9 `admin-*.js` và 2 `staff-*.js` | **Ứng viên legacy, giữ nguyên.** HTML vẫn tải và các script đăng ký globals. `site.js:308-309` dùng Business console. Đính chính cách diễn đạt trong audit Frontend cũ: lời gọi demo ở `site_1.js:388-389` nằm trong hai định nghĩa bị định nghĩa 390-391 ghi đè trong cùng function scope; textual reference đó không chứng minh consumer đang chạy. Chưa xác minh nhu cầu preview/consumer ngoài cây source, nên không xóa script hoặc script tags. |
| `frontend/assets/js/backend-console.js` | **Đang dùng.** `site.js:550` computed import qua `new URL(...)`, đăng ký global đồng bộ rồi lazy-load management-console. Không được coi là orphan chỉ vì thiếu literal incoming import. |
| `api.js`, `site.js`, `app.js`, `home-auth.js`, pages/shared modules | **Đang dùng.** HTML entrypoints, dynamic imports, event handlers và module exports có consumer. `createManagementConsole/createOrdersController/createProductsController` được lazy-load; `init` của admin-customers là tên function expression gán cho global, không phải hàm bỏ quên. |
| `routers/auth.py` exports `get_current_user/hash_session_token`; `routers/catalog.py` export `public_product_query` | **Giữ.** Tests trực tiếp import và tài liệu refactor nêu compatibility; không xóa theo kết quả unused-import đơn thuần. |
| `models/*` TYPE_CHECKING imports, `models/__init__.py` exports, `app/init_db.py` import User | **Giữ.** Hỗ trợ annotation relationship dạng string, package exports/metadata registration và công cụ init; không suy diễn thành dead code khi AST không có Name load. Không sửa ORM/schema. |
| `app/init_db.py`, `app/import_catalog.py`, `backend/create_admin.py`, `tests/run_safe.py`, `tests/pg_coupon_races.py`, `tests/serve_browser_fixture.py`, scripts kiểm tra | **Giữ.** CLI, runner/test discovery hoặc công cụ vận hành/opt-in; không cần được app.main import. Không chạy init/import/migration ghi DB thật để kiểm tra reachability. |
| `services/coupons.py:17` và `services/payment_providers.py:108` — `aware()` | **Trùng body, giữ.** Cả hai có caller; không xóa một bản hoặc tạo helper chung chỉ để giảm duplication. |
| `products.js` storefront loader và `management-console.mjs` loadAllProducts | **Giữ hai implementation.** Khác endpoint/quyền và mapping dữ liệu; không chứng minh tương đương để hợp nhất. |
| `services/ai_admin_business.py:3` import Decimal | **Ứng viên import chưa dùng, giữ.** Thuộc adapter AI nghiệp vụ trong Backend; lượt này chủ động không chỉnh cả nhóm `ai_*` để giữ phạm vi không sửa AI. |

Đã rà AST imports và top-level functions của 92 module runtime Backend; nhiều route functions không có caller bằng tên vì FastAPI đăng ký qua decorator. Rà JS local declarations chỉ tạo danh sách ứng viên, sau đó đọc exports/handlers/loaders; không dùng số lần xuất hiện từ khóa làm bằng chứng duy nhất. Reference scan nội bộ không chứng minh được mọi consumer ngoài repo. Vì vẫn còn ứng viên chưa xác minh, **không kết luận đã dọn sạch hoàn toàn**.

### Verification sau cleanup

| Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| Backend regression | **PASS** | `647 passed, 827 subtests passed, 1 warning` trong 68.42s; `backend-regression.log`. Runner chặn Engine.connect ngoài SQLite :memory:, không đọc .env khi bootstrap. |
| OpenAPI | **PASS** | 60 paths / 74 operations, toàn bộ JSON bằng nhau; SHA-256 trước/sau `a0628e08567b2e53a024036f385b32310d8cd6078a1b268b9bcf215762213f61`; `openapi-comparison.json`. |
| Frontend unit tests | **PASS** | 14/14, không skip; `frontend-unit.log`. Chạy ba module node:test trực tiếp trong cùng process theo cách đã xác minh ở lượt trước. |
| Browser smoke | **PASS** | 27 checks, `exceptions: []`; `browser/result.json`, `browser-smoke.log`. Fixture SQLite in-memory mới, Chrome headless profile riêng; Customer/Staff/Admin, COD, inventory và các trường hợp AI/API/module offline. |
| JS/MJS syntax | **PASS** | 34 file kể cả site_1.js và tests; `js-syntax.json`. |
| References sau cleanup | **PASS trong phạm vi source** | 151 literal HTML script/module edges giữ nguyên, không thiếu target; computed imports backend-console ở site.js/site_1.js đọc riêng. `frontend-references.json`; unit asset-reference test kiểm tra thêm stylesheet paths. AST xác nhận không còn symbol đã bỏ trong ba module; `removed-symbols-after.json`. |
| Bảo toàn file | **PASS** | So manifest/checksum cuối lượt: chỉ ba file runtime và hai báo cáo dự kiến đổi; không xóa file, không sửa untracked runtime, Frontend runtime/HTML/CSS/ảnh, models/schemas/migrations hoặc AI. `preservation-final.json`. |
| Playwright suite / production / PostgreSQL / VNPay / AI thật | **NOT VERIFIED** | Không có môi trường thử nghiệm thực được xác nhận; không dùng smoke fixture để tuyên bố các môi trường này đã PASS. |

Không có test FAIL trong lượt verification này. Warning hiện hữu vẫn được runner đếm, không coi là lỗi cleanup và chưa phân loại. Không thêm test riêng để kiểm tra chính các dòng import đã bỏ; dùng regression, OpenAPI và reference checks hiện có.

Lệnh chính: `.venv\Scripts\python.exe scripts/run_business_checks.py --sqlite-bootstrap --openapi <evidence>/openapi-after.json --pytest`. Frontend unit chạy trực tiếp các file `tests/unit/asset-references.test.mjs`, `dashboard.test.mjs`, `http-client.test.mjs` bằng `.cache/node.exe`. Browser chạy bản sao runner hiện hữu chỉ đổi đường dẫn evidence sang checkpoint; không sửa Frontend để chạy smoke.

**Thay đổi ngoài phạm vi dự kiến: không có.** Bổ sung tài liệu vào đúng hai báo cáo người dùng yêu cầu đọc; checkpoint/log/screenshot/profile chỉ nằm trong .cache. Mọi thay đổi/untracked có sẵn được bảo toàn. Phần này không thay thế các rủi ro P1/P2 và giới hạn kiểm chứng của audit Backend trước đó.
