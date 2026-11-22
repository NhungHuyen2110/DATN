# Chạy lại các kết quả đã kiểm chứng

Các lệnh dưới đây dùng workspace trên D, Python/dependencies đã có trên máy hiện tại. Không gọi DB đang dùng, không đọc `.env`, không thay website đang phục vụ. Native labs chỉ chấp nhận PostgreSQL test `127.0.0.1:15439`, graph test `127.0.0.1:17687`, source API test `18001/18000`. DB test/report/artifact mới phải dùng số attempt và tên chưa tồn tại; không xóa kết quả cũ để chạy lại.

## Kiểm tra offline

```powershell
Set-Location D:\LUMIERE-FINAL-TEST
$env:TEMP='D:\LUMIERE-FINAL-TEST\.local-tmp'
$env:TMP=$env:TEMP
$env:PYTHONPATH='D:\LUMIERE-FINAL-TEST\.local-tmp\testdeps'
& 'D:\JewelryDatasetGenerator\.venv\Scripts\python.exe' -B scripts/run_ai_tests.py --report docs/ai-rerun-NEW.json
& 'D:\JewelryDatasetGenerator\.venv\Scripts\python.exe' -B scripts/run_backend_tests.py
& 'D:\JewelryDatasetGenerator\.venv\Scripts\python.exe' -B scripts/validate_release_artifacts.py
& 'D:\JewelryDatasetGenerator\.venv\Scripts\python.exe' -B scripts/validate_deployment.py
docker compose --env-file .env.example -f compose.yaml --profile monitoring --profile sync config --quiet
```

Expected: không failure; AI runner skip 1 test Neo4j vì tách live integration. Backend chặn DB file/mạng và có canary xác minh guard. Counts mới nhất trong `current-implementation.json`; pytest items/subtests không đồng nghĩa số kịch bản duy nhất. Compose config chỉ parse, không chứng minh Engine/build/runtime.

## PostgreSQL native và browser thật

Cluster riêng đã khởi tạo trong `.local-tmp/postgres-sync-20261121/data`; không dùng tùy chọn resume cho cluster khác. Runner kiểm tra marker/version/control file, tạo DB test mới và dừng đúng cluster trong `finally`. Binary PostgreSQL cài sẵn trên C chỉ đọc; data/log trên D.

```powershell
# Chọn số mới chưa có: ví dụ 20; KHÔNG xóa DB/report cũ.
& 'D:\JewelryDatasetGenerator\.venv\Scripts\python.exe' -B scripts/run_native_postgres_sync.py --confirm-isolated --resume-initialized-test-cluster --sync-attempt 20 --report docs/postgres-sync-rerun-20.json
& 'D:\JewelryDatasetGenerator\.venv\Scripts\python.exe' -B scripts/run_native_postgres_sync.py --confirm-isolated --resume-initialized-test-cluster --browser-test --browser-attempt 20 --browser-with-ai --browser-with-monitoring --browser-native-fault --browser-use-migrations --report docs/browser-rerun-20.json
```

Browser lab cần Node, `.local-tmp/browser-tools/node_modules/@playwright/test`, Chrome cài sẵn và binary native Prometheus/Grafana đã xác minh checksum. Không tải Chromium lên C. Fixtures tài khoản/đơn hàng đều giả. Browser chặn request Internet. Expected: 18 ca đạt, public recommendation cards, metrics thực, AI process outage giữ login/catalog/COD; source API/monitoring/PG test dừng khi xong. Báo cáo cuối: `native-public-recommendation-browser-final-20261121.json`.

## Model thật, live catalog và graph thật

Chỉ chạy khi **đúng graph test** đã được seed bằng importer có guard; chưa đủ điều kiện thì dừng, không đổi sang graph đang dùng. Model cache pinned revision trên D, không tự download.

```powershell
$env:LUMIERE_SYNC_TEST_GRAPH_URI='bolt://127.0.0.1:17687'
# Password fixture của graph test, không lấy mật khẩu graph production:
$env:LUMIERE_SYNC_TEST_GRAPH_PASSWORD='test-only-lumiere-2026'
& 'D:\JewelryDatasetGenerator\.venv\Scripts\python.exe' -B scripts/run_native_postgres_sync.py --confirm-isolated --resume-initialized-test-cluster --live-catalog-test --sync-attempt 20 --report docs/live-catalog-rerun-20.json
```

Expected: 500 CSV-seeded products qua HTTP Business/PG, Top 3 có source/path; thay giá và stock giữa query làm candidate cũ bị loại. Qdrant là memory engine, không phải Qdrant server/container. Không suy ra chất lượng relevance từ bài này. Báo cáo sau sửa bạc/bạch kim và material-reference: `live-business-model-graph-retrieval-final-20261121.json`.

## Backup/restore và worker

`scripts/test_backup_restore.py` chỉ dump synthetic browser database được chỉ định trong script, restore sang database test trống, không `--clean`/DROP. Orchestrator dùng `--backup-restore-test --sync-attempt NEW --report NEW.json`. Kiểm tra nguồn fixture còn đúng trước khi chạy. Report chứa checksum, 22 bảng và invariants. Backup nằm trong `.local-tmp/recovery/`, không đưa Git.

Worker write yêu cầu **backup-reference.json**, không chấp nhận file bất kỳ. Schema version 1 gồm `environment`, `database_host`, `database_port`, `database_name`, `format: pg_dump_custom`, `backup_file` tương đối trong cùng thư mục, `backup_sha256`. Phải khớp đúng DB dev/test và có file PGDMP/checksum hợp lệ. Backup của browser fixture không phải giấy phép ghi DB khác. `--status` chỉ đọc. Không bật worker lên hệ thống hiện có.

## Rollback

- Source: đối chiếu diff và checkpoint trên D, khôi phục có chọn lọc phần agent sửa. Không ghi đè thay đổi có sẵn của người dùng; không reset/clean cả tree.
- Feature flags: tắt `PRODUCT_INDEX_SYNC_ENABLED` và `LUMIERE_METRICS_ENABLED`; retrieval cũ có `LUMIERE_RETRIEVAL_V2_ENABLED=false` để tương thích, nhưng legacy chưa được nghiệm thu toàn deployment.
- Migration: `0008` thêm outbox, `0009` bổ sung password-reset feature hiện có; giữ bảng/security records/job. Không downgrade xóa data. Chưa migration DB đang phục vụ.
- Chỉ dừng đúng process/project test đã tạo; giữ volumes/backups/model. Không `down -v`, DROP, reset Docker/WSL.

Checkpoint chính: `csv-preflight-20261118`, `graph-writer-20261118`, `sync-outbox-20261118`, `deployment-20261121`, `observability-20261121`, `retrieval-ablation-20261121`, `diagnostics-20261121`, `password-reset-compat-20261121`, `material-verification-20261121`, `public-recommendation-20261121` dưới `.local-tmp/checkpoints/`.

Docker còn lỗi Engine và data VHD trên C. Chỉ chạy config parse hiện tại; build/pull/runtime cần sửa Engine và xác nhận storage D trước. Hosting/HTTPS, secrets thật và production migration/deploy cần phê duyệt riêng.
