# Đồng bộ sản phẩm sang Neo4j và Qdrant — PHASE 6

Trạng thái: đã viết cơ chế và kiểm thử cách ly; **chưa bật trên Business API đang chạy**, chưa áp dụng migration vào PostgreSQL hiện có. Không thay đổi `.env`, không sao chép Customer/Order vào AI.

Worker integration 21/11 đã đạt PostgreSQL thật + Neo4j thật + Qdrant in-memory với vector tổng hợp 3 chiều: retry sau graph commit, update giá/tồn kho, xóa Product và tombstone/vector removal. Fixture Product900021/taxonomy990021 riêng, không sửa catalog500. Xem `postgres-graph-vector-integration.json`. Chưa phải integration qua container/network Qdrant server/model thật. Lần đầu test dùng clock giả bị lệch thời gian sau graph import; đã giữ fixture cũ900020 và chạy lại trên database/fixture mới với clock thực cho update/delete.

Cập nhật cuối 21/11: PostgreSQL 17.9 thật đạt 7 kiểm tra rollback, 12 concurrent upserts, SKIP LOCKED, worker delivery/update/delete và exporter queue có xác thực. Dữ liệu giả ở cluster riêng trên D, cổng 15439; cluster đã dừng sau test. Xem `postgres-worker-metrics-integration.json`. Full-service integration vẫn là gate riêng.

## Cách hoạt động

Khi cờ `PRODUCT_INDEX_SYNC_ENABLED=true`, thay đổi Product qua ORM và đổi tên taxonomy tạo một job ngay trong transaction nghiệp vụ. Rollback nghiệp vụ cũng rollback job. Job chỉ lưu ProductID và trạng thái, không lưu giá vốn hay dữ liệu khách hàng. Khi cờ tắt (mặc định), lưu sản phẩm không truy vấn bảng mới.

Worker nhận lease trong transaction ngắn, đọc lại sản phẩm, đóng session rồi mới ghi Neo4j/Qdrant. Xử lý thành công mới xác nhận job. Cập nhật phát sinh trong lúc worker chạy sẽ được xử lý tiếp; lỗi có backoff và giới hạn retry. Chỉ lưu loại lỗi, không lưu chuỗi lỗi có thể chứa credential. Admin xem trạng thái tại `GET /admin/ai/sync-status`; Customer và Staff không được truy cập.

Xóa sản phẩm đánh dấu node graph `is_deleted=true, stock=0`, xóa đúng point Qdrant theo ProductID và giữ collection. Tạo lại cùng ID khôi phục projection. Job không có FK tới Product để giữ được yêu cầu xử lý xóa. Đối soát chủ động so sánh toàn bộ ProductID nguồn với projection để phát hiện thao tác SQL bulk bỏ qua ORM.

## Giới hạn còn phải kiểm chứng

- SQLite không chứng minh được concurrent locking / `SKIP LOCKED` của PostgreSQL. Chưa cho phép coi đây là đồng bộ production đã nghiệm thu.
- Graph và vector được ghi tuần tự, không có transaction phân tán. Bảo đảm hướng tới hội tụ nhờ retry/repair/reconciliation; không tuyên bố exactly-once hay snapshot đồng nhất tức thời. Khuyến nghị một worker trước khi kiểm thử nhiều worker trên PostgreSQL cách ly.
- Unit tests dùng adapter giả; integration riêng đã dùng PostgreSQL và Neo4j thật, Qdrant memory với vector tổng hợp 3 chiều. Chưa thay thế worker end-to-end với model thật và Qdrant server.
- Đồng bộ chỉ bắt thay đổi ORM khi cờ đã bật; phải chạy đối soát đầy đủ khi bắt đầu và định kỳ. Không chạy reconcile với catalog nguồn bị thiếu một phần.
- Bản đang phục vụ chưa được restart. Chưa chạy worker trên database hiện có.

## Chạy kiểm thử an toàn trên Windows

```powershell
$env:TEMP='D:\LUMIERE-FINAL-TEST\.local-tmp'
$env:TMP=$env:TEMP
$env:PYTHONPATH='D:\LUMIERE-FINAL-TEST\.local-tmp\testdeps'
& 'D:\JewelryDatasetGenerator\.venv\Scripts\python.exe' -B scripts/run_backend_tests.py -x -k 'ProductIndexJobTests or ProductIndexMigrationTests'
& 'D:\JewelryDatasetGenerator\.venv\Scripts\python.exe' -B scripts/run_ai_tests.py
```

Runner backend chặn kết nối network/database file và chỉ cho SQLite memory; runner AI không tải model, không kết nối graph hay HTTP thật. Kết quả lần chạy nằm trong `product-index-sync-results.json`, `ai-projection-regression.json` và log dưới `.local-tmp`.

## Chuẩn bị môi trường tích hợp riêng

Compose có worker riêng dưới profile `sync`, mặc định không chạy. Worker yêu cầu backup-reference JSON khớp host/port/database/environment, file PGDMP và SHA256 đúng; file phải nằm trong thư mục reference. Mount thư mục bằng `SYNC_BACKUP_DIRECTORY`, read-only tại `/recovery`, chứa `backup-reference.json` và backup. Không dùng file text bất kỳ làm bằng chứng backup. Xem `shared/recovery.py` và `13-reproduce-verified-results.md`.

Bảng outbox phải migrate trên test DB, model cache đúng revision. `PRODUCT_INDEX_SYNC_ENABLED` ở Business API test vẫn tắt; chưa kích hoạt đồng bộ cho website. `.env.example` hiện chọn collection `jewelry_products_v_c0efd814ee4f` và revision MiniLM đã pin; vẫn phải index versioned thực tế trước khi query. Không bật profile trên database đang dùng.

Outbox migration là `20261118_0008`; head hiện tại `20261121_0009` bổ sung bảng cho password-reset feature đã có, có kiểm tra schema trước khi giữ bảng sẵn có. Không tự sửa/thay bảng không tương thích. Native browser đã chạy toàn chain trên DB test trống. Worker yêu cầu URL riêng qua `LUMIERE_SYNC_DATABASE_URL`, `LUMIERE_SYNC_NEO4J_URI`, `LUMIERE_SYNC_QDRANT_URL`, password graph riêng, model cache/revision pin. Không đọc `.env` gốc. Tên DB phải bắt đầu đúng `lumiere_dev` hoặc `lumiere_test` theo `--environment`, loopback/service DNS được phép.

Không tự chạy migration/import lên database đang dùng. Trước khi kích hoạt phải có PostgreSQL riêng, checkpoint/backup, kiểm thử tích hợp và đối soát. Đây là điều kiện còn thiếu, không phải bước đã thực hiện.

## Rollback

Tắt `PRODUCT_INDEX_SYNC_ENABLED`, dừng đúng worker vừa khởi tạo; website tiếp tục dùng đường lưu sản phẩm cũ. Giữ bảng và job để không mất yêu cầu đồng bộ, không chạy downgrade xóa bảng. Bản nguồn trước thay đổi nằm tại `.local-tmp/checkpoints/sync-outbox-20261118/`; khôi phục có chọn lọc theo diff, không ghi đè thay đổi của người dùng. Những file mới có thể để nguyên khi cờ tắt. Rollback AI retrieval có cờ riêng trong tài liệu PHASE 4.
