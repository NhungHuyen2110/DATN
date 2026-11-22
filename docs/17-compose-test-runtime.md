# Bản thử Docker — 22/11/2026

URL: http://127.0.0.1:18080. Đây là project `lumiere-rebuild-test`, chỉ mở loopback, dùng 5 sản phẩm giả. Website và database cũ chưa chuyển sang bản này.

Core đang chạy gồm reverse proxy, frontend, Business API, AI API và PostgreSQL. Neo4j/Qdrant trong Compose chưa được khởi động/index; chat/gợi ý đang kiểm chứng lexical fallback khi thiếu các nguồn này. Lab worker model thật dùng Qdrant container riêng và PostgreSQL/Neo4j native, không nhận là full Compose deployment.

Tài khoản fixture: `lumiere-e2e-customer@example.com`, `lumiere-e2e-staff@example.com`, `lumiere-e2e-admin@example.com`. Mật khẩu giả dùng chung: `test-only-compose-password-2026!`. Chỉ dành cho bản thử local; không dùng các giá trị này khi triển khai công khai. Fixture reset một lần đã được sử dụng, không chạy lại ca đó mà không tạo fixture mới.

## Bằng chứng và giới hạn

- `compose-core-runtime-20261122.json`: migration head `20261121_0009`, 5 sản phẩm giả, chat kiểm giá/tồn kho qua Business API.
- `compose-browser-integration-20261122.json`: full configured Chrome suite trên image trước đạt 17, skip 1 Grafana, không flaky. Native Grafana có bằng chứng riêng.
- `ai-limits-contract-final-20261122.json`: 84 AI tests đạt/1 skip. SKU chính xác, không nhầm số Top-K thành SKU; kiểm nguồn Qdrant trước tải model lạnh; giới hạn mỗi nguồn một tác vụ, caller timeout 3 giây và cooldown 15 giây, cờ bật trong Compose. Tác vụ read-only quá hạn có thể còn kết thúc trong worker; kết quả muộn bị bỏ, không xếp thêm hàng đợi.
- `compose-sku-limits-verified-20261122.json`: 3 truy vấn đạt trên image mới. Lượt đầu sau khởi động thiếu trường kết quả, được giữ là lỗi; chưa chứng minh cold-start ổn định mọi lần.
- `compose-browser-final-subset-20261122.json` và `compose-browser-limits-final-20261122.json`: giữ nguyên các lần timeout. Trace cho thấy login một lượt mất khoảng 20 giây, auth/me gần 5 giây. Hai ca có nhiều request được đổi ngân sách toàn kịch bản từ 45 thành 90 giây; timeout API/proxy không đổi. Kết quả chạy lại ghi riêng, không ghi đè lỗi cũ và không coi latency lab là SLA.
- `compose-ai-container-fault-final-20261122.json`: thực sự dừng AI container; đăng nhập, COD, đọc đơn của mình và guard Customer→Admin đạt. Khởi động lại AI, sản phẩm trả về khớp giá/tồn kho nguồn Business. Đây là một lab episode, chưa toàn ma trận dependency faults.

## Chạy lại và rollback

Các script có guard project/DB/fixture và yêu cầu report mới, không ghi đè bằng chứng:

```powershell
python -B scripts/run_compose_browser_lab.py --confirm-isolated --grep 'Admin sees actual lexical|public recommendations' --artifact-directory .local-tmp/compose-browser-NEW --report docs/compose-browser-NEW.json
python -B scripts/fault_injection.py --service ai-api --apply --confirm-isolated --business-transaction-probe --report docs/compose-fault-NEW.json
# Dừng đúng project test và giữ dữ liệu:
docker compose --env-file .env.example -f compose.yaml stop
```

Không chạy browser cùng lúc fault test. Không chạy `down -v`, không xóa `.local-tmp`: Docker VHD hoạt động và backup đang nằm trên D bên trong đó. [Runbook chuyển D và rollback](16-docker-storage-on-d.md).

Full worker image, graph/vector/model Compose, monitoring containers và các dependency fault tests còn phải triển khai/kiểm chứng. Không có quality metrics khi 105 câu vẫn chưa được người review.

Mốc tài nguyên: `runtime-memory-pressure-20261122.json` ghi RAM Windows khoảng 8 GB, trống khoảng 54 MB lúc đo. Docker server vẫn trả 28.5.1 trong `docker-during-worker-build-20261122.json`. Native Neo4j lab đã dừng để giảm tải, giữ nguyên file graph; các báo cáo native trước đó là bằng chứng lịch sử, không khẳng định server native đang chạy. Phải xác minh đúng cấu hình/port và khởi động lại lab trước khi chạy native graph tests. Không dùng PID cũ để restart/stop.
