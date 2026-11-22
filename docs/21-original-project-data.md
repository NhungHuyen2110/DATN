# Dữ liệu dự án cũ đang phục vụ local

Theo yêu cầu dùng dữ liệu dự án đầy đủ, website http://127.0.0.1:18080 chuyển từ fixture 5 sản phẩm sang bản sao database cũ. Không dùng DB chỉ seed CSV làm nguồn cuối.

## Nguồn và bảo toàn

- Nguồn: PostgreSQL 17, container `lumiere-postgres` đã dừng sạch, volume `jewelrydatasetgenerator_lumiere_postgres_data`, database `lumiere_backend_test`. Database mặc định `lumiere_db` chỉ có tài khoản nền, không phải bản đầy đủ.
- Mount volume nguồn read-only, tạo volume bản sao mới và so SHA-256 manifest toàn bộ file trước/sau. Không khởi động hoặc ghi nguồn. Container audit bản sao không có mạng/TCP, bật `default_transaction_read_only`.
- Dump đầy đủ vào thư mục riêng trên D, ACL chỉ tài khoản hiện tại/SYSTEM/Administrators. Không commit dump, session, password hash, địa chỉ khách hàng hoặc thông tin thanh toán. Không công khai dữ liệu lên hosting trong bước này.
- Restore vào DB mới `lumiere_test_original_data` trên PostgreSQL riêng của project `lumiere-rebuild-test`; không ghi đè DB có sẵn. Chạy migration additive tới `20261121_0009`; digest từng dòng của 20 bảng nghiệp vụ khớp trước/sau migration và sau chuyển ứng dụng. `alembic_version` thay đổi có chủ đích.
- Giữ nguyên ID, SKU, password hash, giỏ hàng, coupon, đơn, thanh toán, phiên và các khóa ngoại. Không reset tài khoản. Số 11 là tổng tài khoản mọi vai trò, không phải 11 khách hàng.

| Dữ liệu gốc | Số lượng giữ lại |
|---|---:|
| Sản phẩm / ảnh theo SKU | 500 / 500 |
| Tài khoản / vai trò | 11 / 3 |
| Đơn / dòng đơn | 12 / 15 |
| Giao dịch thanh toán | 9 |
| Giỏ / dòng giỏ | 4 / 1 |
| Coupon / lượt dùng | 2 / 2 |
| Yêu thích / đánh giá / liên hệ | 1 / 1 / 5 |

## Kích hoạt và kiểm tra

`compose.original-data.yaml` trỏ Business/worker tới bản sao; Neo4j/Qdrant dùng volume mới, giữ chỉ mục 5 sản phẩm cũ để rollback. Model MiniLM giữ đúng revision và collection 384 chiều. Worker chỉ đưa trường sản phẩm công khai vào AI, không index khách hàng/đơn/phiên. Giới hạn OMP/MKL hai luồng cho CPU máy local, không đổi model hoặc thuật toán ranking.

Đã kiểm API phân trang đủ 500 ID riêng biệt; 500 ảnh HTTP đúng MIME và khớp từng byte với file local; Chrome thật tải catalog và ảnh chi tiết, gồm ID 500. Danh sách yêu thích sửa dùng resolver SKU đã có thay ảnh chung theo danh mục. Kiểm browser guest không đăng nhập hoặc ghi dữ liệu.

Bằng chứng công khai chỉ có số lượng và kết quả: `original-project-data-readonly-20261122.json`, `original-project-browser-20261122.json`. Báo cáo backup/restore/digest đầy đủ nằm trong `.local-tmp/original-db-20261122-014434`, backup trước kích hoạt nằm trong `.local-tmp/recovery/original-data-20261122`; cả hai bị loại khỏi Git/Docker build. Không xóa `.local-tmp` vì còn chứa Docker data đang dùng.

Kiểm lại read-only, chọn tên báo cáo mới:

```powershell
python -B scripts/verify_original_project_data.py --audit .local-tmp/original-db-20261122-014434/audit.json --report .local-tmp/original-data-recheck.json
```

Chỉ thêm `--semantic` sau khi đủ 500 job `done`; khi đó script kiểm ba nguồn lexical/dense/graph, giá/tồn kho sống, 500 Product/2.500 cạnh/500 vector. Không dùng báo cáo semantic 5 fixture làm chứng cứ cho 500.

**Lượt cuối đã đạt:** `original-project-semantic-20261122.json`, 500 job done, 500 Product/2.500 quan hệ/500 vector, Top 3 trả ID 2/79/114 với cả ba nguồn, giá/tồn kho và graph paths khớp. Model revision giữ nguyên. HTTP không cần retry ở lượt này; retrieval cần 5 lần chờ sẵn sàng. Kiểm thêm 13 bộ đếm ID và 19 bảng không đổi; vòng đời phiên được đối chiếu riêng (13 phiên cũ còn nguyên, 1 phiên bỏ/1 phiên mới). Chưa coi đây là nghiệm thu tải, SLA hoặc quality benchmark.

Sau khi website được dùng để đăng nhập/đăng xuất, có thể thêm `--allow-session-lifecycle`: kiểm riêng số phiên thêm/bớt và buộc các phiên cũ còn tồn tại khớp hash. Không restore đè phiên mới để làm số liệu khớp. Các bảng nghiệp vụ và bộ đếm ID khác vẫn phải khớp; chỉ loại bộ đếm session khỏi phép so sau hoạt động login/logout. Bản restore ban đầu đã giữ nguyên đủ mọi phiên. Một lượt kiểm sau kích hoạt đã gặp HTTP 504; probe trong Docker sau đó trả catalog 500 với Business/proxy khoảng 0,16/0,12 giây. Các số này chỉ là hai mẫu chẩn đoán; kiểm tải/cold-start/SLA vẫn chưa hoàn tất. Nếu script phải retry gateway 502/503/504, mã lỗi được lưu rõ trong report.

Giới hạn: chưa kiểm lại full role/write suite trên các tài khoản cũ; chưa gửi mail/thanh toán thật; không suy ra relevance benchmark hoặc SLA. Bộ 18 ca trước vẫn là bằng chứng hồi quy riêng trên DB giả. Public hosting còn cần VPS/hostname được duyệt và rà soát dữ liệu tài khoản/phiên trước restore; không dùng lệnh bootstrap CSV thay dữ liệu cũ.

Khởi động lạnh: model có thể chưa sẵn sàng trong ngân sách 3 giây của nguồn dense, khi đó lexical/graph tiếp tục phục vụ. Đã kiểm endpoint nội bộ sau làm nóng trả đủ cả ba nguồn và `status=ok`; không coi thời gian làm nóng là latency benchmark. Chẩn đoán nội bộ nay có `source_errors` với loại lỗi/mã timeout/cooldown/in_flight đã lọc; không trả raw exception, URL credential hoặc query trong chi tiết lỗi. Bộ AI offline sau thay đổi đạt 85 test, 1 skip (`ai-source-diagnostics-tests-20261122.json`). Full cold-start/concurrency matrix vẫn chưa nghiệm thu.

## Rollback local

Nếu cần quay lại demo giả, dừng worker trước rồi dùng đúng override cũ. Lệnh giữ toàn bộ DB/volume, không cần `down`:

```powershell
docker compose --env-file .env.example -f compose.yaml -f compose.original-data.yaml stop index-worker
docker compose --env-file .env.example -f compose.yaml -f compose.demo.yaml --profile sync up -d --no-build neo4j qdrant business-api ai-api index-worker
docker compose --env-file .env.example -f compose.yaml -f compose.demo.yaml restart ai-api
```

Muốn quay lại dữ liệu cũ đầy đủ thì dừng worker demo, dùng `compose.original-data.yaml` tương ứng và restart AI để làm mới kết nối. Không chạy lại script restore vì nó chủ động từ chối khi đích đã tồn tại. Database nguồn, dump riêng và dữ liệu local đã phát sinh phải được giữ lại.
