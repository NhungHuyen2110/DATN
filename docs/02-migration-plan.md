# Migration ledger và kế hoạch tiếp theo

Checkpoint local `checkpoint/pre-architectural-refactor-20261118` trỏ đến `cb64585`.
Chưa tạo commit triển khai; các thay đổi đang ở working tree để review theo module.

## M1 — Cart: DONE trong phạm vi kiểm thử local

**BEFORE:** `backend/app/routers/cart.py`: SQL, user/product locks, validation stock,
Decimal arithmetic, transaction và HTTP errors trộn trong router.

**DESIGN:** router → `CartService` → `CartRepository` → SQLAlchemy adapter.
Domain/Application không phụ thuộc FastAPI/SQLAlchemy.

**IMPLEMENTATION:** `app/domain/cart.py`, `application/cart.py`,
`infrastructure/cart.py`, router facade và `tests/test_cart_service.py`.

**TEST:** `scripts/run_business_checks.py --sqlite-bootstrap --pytest`:
638 tests + 827 subtests PASS. Cùng suite với router checkpoint cũng PASS.
OpenAPI 60 paths bằng nhau. Xem tài liệu 06 về phạm vi baseline và SQLite.

**COMPATIBILITY:** giữ cookie auth, owner isolation, Decimal response strings,
stock conflict status/details, tích lũy duplicate add, update thay quantity và delete trả cart.
PostgreSQL lock syntax/order đã có regression compile; concurrency thật chưa chạy.

**ROLLBACK:** restore riêng router cart từ checkpoint; module mới không được router cũ gọi.
Không có SQL migration cần rollback.

## M2 — AI: PARTIAL, chưa chuyển mặc định

**BEFORE:** eager imports, global clients/model, CSV path phụ thuộc cwd, giant retrieval
functions, filter sau dense retrieval và các pipeline trùng.

**DESIGN:** typed facts/ports, injected adapters, một request snapshot, deterministic RRF,
catalog verification và template grounding. Giữ API facade và legacy default.

**IMPLEMENTATION:** `AI/lumiere/*`, `sync_catalog.py`, runtime/semantic requirements,
lazy API imports và contract/core/storage tests.

**TEST:** core/API/adapter results trong tài liệu 06. Real semantic model, live Neo4j,
live Qdrant và PostgreSQL adapter chưa được nghiệm thu.

**COMPATIBILITY:** 6 AI route schemas khớp checkpoint; public product miss vẫn HTTP 200
với `success=false`. Legacy recommendation functions được gọi lazy; chưa khẳng định
personalized recommendations chạy live. Modular chat thêm `degraded_sources`/explanation.

**ROLLBACK:** đặt `AI_PIPELINE=legacy`, restart AI. Không đổi collection legacy;
`lumiere_products_v2` riêng. Không xóa derived indexes trong rollback.

## M3 — Frontend transport: DONE cho unit/syntax, browser PARTIAL

**BEFORE:** transport/error handling nằm trong `assets/js/api.js` cùng các methods.
**DESIGN:** global facade gọi ES module `shared/http-client.mjs` qua dynamic import.
**IMPLEMENTATION:** shared module, facade delegation, 5 Node tests, `test:unit` script.
**TEST:** 5 tests PASS; syntax toàn bộ JS/MJS PASS bằng Node portable v22.16.0.
**COMPATIBILITY:** credentials/include, JSON headers, 204, lỗi network và validation details giữ nguyên;
không sửa HTML/CSS hoặc methods gọi API. Browser E2E chưa kiểm chứng.
**ROLLBACK:** restore `frontend/assets/js/api.js` từ checkpoint.

## M4 — Operations: PARTIAL

Dockerfiles, isolated Compose, proxy, metrics/logging, Prometheus/Grafana config và
quality workflow đã có. Compose config PASS; Docker build/start, monitoring live và
GitHub workflow chưa chạy. Backend standalone frontend behavior giữ default như cũ.

## M5 — Shared authentication/authorization dependencies

**BEFORE:** catalog, taxonomy, payments, coupons, dashboard, contact, customer content,
staff/admin routers import guards/parameter aliases từ `routers/orders.py`; các router
còn import authentication dependency từ `routers/auth.py`.

**DESIGN:** `core/dependencies.py` sở hữu hash session token, get_current_user và role
guards; `core/api_parameters.py` sở hữu ID/pagination constraints. Không có import router
từ core. Không thêm class cho các pure dependency functions này.

**IMPLEMENTATION:** shared modules và import rewiring của các routers liên quan; auth/orders
re-export callable cũ để giữ tương thích dependency overrides và callers.

**TEST/STATUS: DONE trong regression local.** OpenAPI vẫn bằng baseline; regression
sau extraction PASS 638 tests và 827 subtests trong 65.17s. Chỉ chuyển vị trí, không đổi
cookie/hash/expiry/role rules.

**ROLLBACK:** restore các routers đã rewiring từ checkpoint như một nhóm; modules core
mới có thể giữ vì code checkpoint không import chúng. Không có database migration.

## Các bước còn lại, theo thứ tự

1. Bổ sung Master Prompt và đối chiếu lại requirement matrix trước khi nhận nghiệm thu toàn hệ thống.
2. Chạy storage integration trên instance test riêng; sync hai lần và kiểm tra taxonomy update.
3. Chạy multilingual model thật; test retrieval từ ba nguồn và đánh giá tập câu hỏi có nhãn.
4. Bổ sung semantic linking, negation/disambiguation và gold tests; không gọi alias lookup là semantic linker hoàn chỉnh.
5. Chạy staging runbook, browser Customer/Staff/Admin và payment sandbox E2E.
6. Chỉ bật modular trên môi trường cần giữ liên tục sau các quality gates này.
7. Migration catalog/auth/Staff/Admin orchestration từng module, với snapshot contract và regression riêng.
8. Thiết kế outbox/CDC, revision checks, delete/tombstone propagation sau review schema; không tự sửa database schema.
9. Production build digests, backup/restore drill, deployment approval và rollback rehearsal trước phát hành.

Không xóa modules legacy/backup cho đến khi có caller inventory và live acceptance tương ứng.
