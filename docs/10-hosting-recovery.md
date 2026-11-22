# Hosting, bảo mật và phục hồi

Trạng thái: runbook chuẩn bị, chưa triển khai Internet, chưa mua dịch vụ hoặc thay DNS/secrets. Cần người dùng xác nhận ngân sách, nơi hosting/domain và quyền triển khai trước bước public.

Ba topology để xem xét: (1) một máy chủ cho toàn hệ thống, vận hành đơn giản nhưng lỗi máy chủ ảnh hưởng tất cả; (2) web/business/data tách máy inference, dễ quản lý tài nguyên model và cô lập lỗi hơn nhưng cần bảo vệ kết nối giữa máy; (3) managed database/vector/graph khi có ngân sách, giảm công việc vận hành nhưng tăng chi phí và phụ thuộc dịch vụ. Chưa chọn nhà cung cấp/giá vì chưa có ngân sách và chưa đo tải. CPU-only embedding khác nhu cầu RAM/VRAM của Qwen/Ollama; không suy ra tốc độ inference từ số vCPU.

Trước staging: build image theo commit SHA, scan dependency/image, khóa phiên bản thực tế đã build, chuẩn bị database staging riêng và backup. Chỉ mở 80/443 ở proxy; DB/vector/graph/Ollama không public. Thiết lập HTTPS với domain thật, cookie Secure, CORS đúng origin, SMTP reset password; tắt password-reset demo mode. Giữ metrics nội bộ, Grafana có auth, log retention và token scrape riêng. Compose hiện tại chỉ bind loopback HTTP test, chưa phải cấu hình production HTTPS.

Backup PostgreSQL bằng `pg_dump` với quyền tối thiểu và secret qua file/private environment, lưu ngoài volume vận hành. Neo4j/Qdrant là projections có thể rebuild từ source đã kiểm chứng; lưu config/schema/model revision và lineage. Không dùng CSV seed cũ ghi đè giá/tồn kho mới. Backup cần được mã hóa/giới hạn quyền nếu chứa dữ liệu người dùng; không đưa vào Git.

Restore rehearsal đã chạy thật với synthetic browser fixtures, pg_dump custom → PostgreSQL test DB trống, 22 bảng/counts khớp, migration head `20261121_0009`, không orphan/order arithmetic/line total/payment violations. Source không đổi; report `backup-restore-rehearsal-20261121.json`, script `scripts/test_backup_restore.py`. Đây không phải backup/restore production và chưa chứng minh projection rebuild sau disaster. Không restore vào DB đang dùng.

Worker chỉ cho write khi `shared/recovery.py` kiểm tra backup-reference JSON version 1, environment/host/port/database chính xác, file tương đối nằm trong cùng recovery directory, header PGDMP và SHA256 khớp. Compose mount `SYNC_BACKUP_DIRECTORY` read-only tại `/recovery`. Không coi sự tồn tại của một file text là đủ backup.

Release: test → staging image SHA → migration additive đã review → smoke business/roles/AI → fault test trong staging → phê duyệt production riêng → đổi image → health/ready verify. Nếu lỗi: đổi lại image SHA trước, tắt feature flag mới, giữ bảng/outbox/volume; không tự downgrade xóa dữ liệu. Đối chiếu job tồn đọng trước khi bật lại sync. Không dùng `down -v` hoặc `DROP` để xử lý sự cố.

Để nghiệm thu còn cần Docker Engine/storage D, domain/host/budget được duyệt, HTTPS, production backup/restore, projection disaster rebuild, alert baseline và benchmark người review. PostgreSQL sync native đã có bằng chứng riêng, không thay container deployment.
