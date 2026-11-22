# PHASE 8 — Giám sát và CI

CURRENT: instrumentation đã nối vào Business API và AI API qua `shared/observability.py`. Mặc định tắt khi chạy source cũ; Compose test bật bằng `LUMIERE_METRICS_ENABLED=true`. Không đổi `.env` đang dùng. Cần cài dependency mới từ requirements trước khi bật.

Mốc mới 22/11: Prometheus/Grafana đã chạy trong Compose thật; scrape Business/AI/worker đều up và Chrome dashboard đạt trong full suite 18/18. Ảnh `figures/grafana-compose-20261122.png`, báo cáo `compose-demo-operations-20261122.json`. GitHub nhánh demo đã chạy 5 workflow thành công ở commit `2ad4a93`; commit sau cần đối chiếu CI riêng. Còn security scans, image publish/staging, host/container metrics và alert baseline. Kết quả native bên dưới là lịch sử riêng, không thay thế kết quả Compose mới.

CHANGE: counter HTTP theo service/method/route template/status, histogram thời gian HTTP và các bước parse/catalog/dense/graph/fusion/verification. Correlation UUID đi từ request AI sang request catalog; context được reset sau request. Log chỉ chứa UUID, method, route template, status và thời gian. Không log body/query string/token/ID người dùng. Nginx access log cũng không chứa URI/query string. Dữ liệu metrics không chứa request_id để tránh cardinality tăng theo request.

Endpoint `/internal/metrics` yêu cầu bearer token; thiếu hoặc sai token trả 404. Proxy chặn `/api/internal/` và `/ai/internal/`. Prometheus scrape trực tiếp qua network riêng. Token trong `infra/prometheus/prometheus.yml` và `.env.example` là cùng một giá trị giả cho LOCAL test; khi thay token phải thay cả config scrape riêng, không dùng token giả để hosting. Grafana yêu cầu đăng nhập, signup/anonymous bị tắt; dashboard tại `/grafana/` chỉ có khi profile monitoring hoạt động.

TEST mới nhất: Prometheus 3.7.3 và Grafana OSS 12.2.1 native chạy từ D, binary checksum verified, scrape source Business/AI API thật ở loopback 18001/18000. Datasource/dashboard API và Chrome render thành công; ảnh `figures/grafana-native-20261121.png`. Report `native-migrations-browser-fault-20261121.json`. Đây chưa phải container deployment. Metrics ASGI synthetic cũ vẫn giữ trong `monitoring-smoke-20261121.json`.

`shared/worker_metrics.py` xuất queue depth/state, lag, last-success, delivery duration/outcome và lease-lost. Endpoint token-protected, scrapes đọc cached state, không query DB mỗi scrape. PostgreSQL thật đã kiểm tra exporter/auth (`postgres-worker-metrics-integration.json`). Compose scrape worker:9101 khi sync profile chạy. Có counter AI intent bounded; không đưa raw query/request ID vào metric labels.

```powershell
docker compose --env-file .env.example -f compose.yaml --profile monitoring config --quiet
# Chỉ chạy sau khi Engine hoạt động và môi trường test đã được chuẩn bị:
docker compose --env-file .env.example -f compose.yaml --profile monitoring up -d
```

CI: workflows backend có guard, AI offline, Neo4j, PostgreSQL, image builds và browser Chrome với PostgreSQL service/migration thật. Browser CI không tải native monitoring; local lab đã kiểm tra riêng. `scripts/changed_services.py` chọn image theo path; AI-only không build business/frontend. Worker có image riêng. Chưa push/chạy GitHub, chưa publish/staging/scan hoàn chỉnh; CI/CD chưa nghiệm thu.

RISK: counters reset khi process restart; cấu hình hiện tại 1 Uvicorn worker. Histogram là ước lượng bucket, không phải benchmark. ProcessCollector CPU/RAM chỉ xuất nơi platform hỗ trợ; Windows lab không có Linux process samples. Chưa host/container disk/restart exporters, alert baseline hoặc DB slow-query instrumentation. Không mount docker socket. Dashboard 5xx không có series có thể hiện No data; không giả thành số 0. Compose parse không chứng minh build/runtime.

ROLLBACK: tắt `LUMIERE_METRICS_ENABLED`; dừng đúng service monitoring trong project test, giữ volumes. Source trước thay đổi trong `.local-tmp/checkpoints/observability-20261121/`. Không downgrade database.

Nguồn định dạng: [Prometheus exposition formats](https://prometheus.io/docs/instrumenting/exposition_formats/). Profile tùy chọn theo [Docker Compose profiles](https://docs.docker.com/compose/how-tos/profiles/).
