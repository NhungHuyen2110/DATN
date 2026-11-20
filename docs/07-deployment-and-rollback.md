# Staging deployment và rollback

**Trạng thái:** cấu hình đã validate; Docker images/containers, migrations online,
monitoring scrape và restore chưa được chạy trên host này. Không có production deployment.

Giữ `docker-compose.yml` cũ và volume `lumiere_postgres_data`. File mới
`compose.rebuild.yaml` có project `lumiere-rebuild` và volumes staging riêng.
Không đổi tên project thành project cũ, không trỏ DSN đến production, không dùng `down -v`.

## Chuẩn bị staging riêng

1. Bật Docker engine, kiểm tra tài nguyên cho multilingual model. Dùng environment staging
   hoặc `.env.staging` riêng với values trong `.env.example`; secret/DSN không commit.
2. Provision PostgreSQL role `ai_catalog_reader` chỉ CONNECT/USAGE/SELECT trên catalog tables.
   `AI_DATABASE_URL` cần hostname `postgres` và password URL-encoded. Không dùng DB owner cho AI.
3. Validate và review cấu hình, sau đó build/start data services của staging:

```powershell
docker compose --env-file .env.staging -f compose.rebuild.yaml config --quiet
docker compose --env-file .env.staging -f compose.rebuild.yaml build
docker compose --env-file .env.staging -f compose.rebuild.yaml up -d postgres neo4j qdrant
```

4. Chỉ với **database staging mới**, áp dụng Alembic hiện có và import catalog bằng CLI có
   validate/dry-run trước. Các lệnh sau là runbook chưa được thực thi:

```powershell
docker compose --env-file .env.staging -f compose.rebuild.yaml run --rm backend python -m alembic current
docker compose --env-file .env.staging -f compose.rebuild.yaml run --rm backend python -m alembic upgrade head
docker compose --env-file .env.staging -f compose.rebuild.yaml run --rm backend python -m app.import_catalog --validate-only
docker compose --env-file .env.staging -f compose.rebuild.yaml run --rm backend python -m app.import_catalog --dry-run
docker compose --env-file .env.staging -f compose.rebuild.yaml run --rm backend python -m app.import_catalog --apply
```

App migrations không tự seed roles. Dùng quy trình quản trị hiện có để provision
customer/staff/admin roles và tài khoản staging; `backend/create_admin.py` cần role tồn tại.
Không chạy `app.init_db` thay migration. Không replay migration từ đầu vào DB hiện hữu.

5. Chạy validate AI catalog trước, sync derived stores rồi sync lại để kiểm tra idempotency:

```powershell
docker compose --env-file .env.staging -f compose.rebuild.yaml run --rm ai python sync_catalog.py
docker compose --env-file .env.staging -f compose.rebuild.yaml run --rm ai python sync_catalog.py --apply --environment staging --neo4j-uri bolt://neo4j:7687 --qdrant-url http://qdrant:6333
docker compose --env-file .env.staging -f compose.rebuild.yaml run --rm ai python sync_catalog.py --verify-only --environment staging --neo4j-uri bolt://neo4j:7687 --qdrant-url http://qdrant:6333
docker compose --env-file .env.staging -f compose.rebuild.yaml up -d backend ai frontend
docker compose --env-file .env.staging -f compose.rebuild.yaml --profile monitoring up -d prometheus grafana
```

First model download cần network/model cache; images không embed secret/model weights.
Provider modular hiện mặc định local-only: cần mount cache đã provision; download chỉ
được bật rõ ràng sau khi có phép. Không tự pull model khi request đầu tiên thiếu cache.
Qdrant TCP healthcheck chưa chứng minh collection/model readiness. AI `/health` và
`/health/live` chỉ liveness. `/health/ready` kiểm catalog, model đã warm, cosine collection
đúng dimension/có points và graph có products; trả 503 khi thiếu dependency. Probe không
tự tải model: gửi controlled warm-up request trước readiness gate. Probe này chưa chứng minh
toàn bộ payload/index freshness; CLI verify và runtime content hashes kiểm thêm.
Backend `/health` kiểm tra DB connectivity,
không chứng minh mọi bảng/migrations có đủ. Kiểm tra `/chat` response degraded_sources,
`/products`, cookie login và các role flows trước khi chấp nhận staging.

Frontend tại `http://localhost:8080`; Nginx proxy cùng origin `/api` và `/ai`, không đổi
auth cookies. Business Docker image không serve frontend. External payment integrations
có thể cần network riêng; staging hiện không công bố DB/graph/vector ports ra host.
Ollama profile `generation` là optional cho các paths cũ và cần pull model thủ công;
modular answer hiện dùng deterministic template.

Image AI giữ ba CSV đầu vào của personalized recommendations cũ. Legacy recommender đã
được cấu hình hóa paths/Qdrant URL/collection, default ngoài staging vẫn giữ collection
`jewelry_products`. Staging dùng `LEGACY_QDRANT_COLLECTION=lumiere_products_v2`; cần kiểm
tra thực tế personalized recommendations trước acceptance, vì đường cũ vẫn dựa trên CSV
snapshot và chưa dùng authoritative PostgreSQL verification như modular chat.

## Metrics và logs

Backend `/metrics`: request count và duration sum theo route template/method/status;
structured JSON logs không ghi cookie/body/query. AI `/metrics`: chat count, product count,
source failure counts. Counters process-local, phù hợp default một worker; chưa có histogram,
multiworker aggregation, alerts hoặc dashboard được kiểm chứng. Prometheus scrape configs
và Grafana datasource đã có; cần xác minh targets UP và dashboard queries trên staging.

## Rollback

Nếu chỉ thử modular ở môi trường cũ, đặt `AI_PIPELINE=legacy` và restart service.
Isolated AI image mới không bao gồm toàn bộ CrewAI dependencies cũ: rollback staging
runtime bằng **image/ref cũ đã lưu**, không chỉ đổi flag rồi giả định dependencies có sẵn.

Trước migration production trong tương lai phải lưu image digests, source ref và backup
PostgreSQL/graph/vector, kiểm tra restore trên môi trường khác. Chưa có production overlay
được nghiệm thu; TLS, secrets provisioning, resource limits và deployment approval còn cần làm.

Code rollback theo module có thể restore các file facade từ checkpoint sau khi review diff:

```powershell
git diff -- backend/app/routers/cart.py AI/api.py frontend/assets/js/api.js
git restore --source checkpoint/pre-architectural-refactor-20261118 -- backend/app/routers/cart.py
# AI và frontend: restore riêng facade tương ứng nếu rollback module đó.
```

Lệnh restore ghi đè thay đổi trong file được chỉ định; không chạy khi chưa lưu công việc cần giữ.
Các modules thêm mới có thể để lại vì facade cũ không import chúng. Không dùng reset --hard,
không xóa DB volumes, không downgrade schema nghiệp vụ (migration này không thay SQL schema).
Staging có thể dừng bằng `docker compose ... stop`; giữ volumes cho điều tra/replay.
