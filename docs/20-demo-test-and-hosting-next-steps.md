# Test demo và bước triển khai tiếp theo — 22/11/2026

## Bản bạn có thể test ngay

Mở http://127.0.0.1:18080 trên máy này. Ba tài khoản local:

| Vai trò | Email | Mật khẩu local giả |
|---|---|---|
| Customer | lumiere-e2e-customer@example.com | test-only-compose-password-2026! |
| Staff | lumiere-e2e-staff@example.com | test-only-compose-password-2026! |
| Admin | lumiere-e2e-admin@example.com | test-only-compose-password-2026! |

Đây là **5 sản phẩm giả**, không phải catalog 500 sản phẩm. Có 10 container chạy độc lập: frontend, proxy, Business, AI, PostgreSQL, Neo4j, Qdrant, worker, Prometheus, Grafana. Ollama chưa bật; câu trả lời sản phẩm hiện deterministic, không nhận LLM narrative đã hoàn tất.

Bạn thử Customer: đăng nhập → sản phẩm → yêu thích → giỏ hàng → COD → xem đơn. Với Staff/Admin: xem đơn, đổi trạng thái fixture phù hợp, tồn kho, quản trị theo quyền và chẩn đoán AI. Câu mẫu: “Top 3 nhẫn dưới 8 triệu”. Không dùng các tài khoản giả này cho hosting công khai.

Grafana local: http://localhost:18080/grafana, tài khoản `admin`, mật khẩu test `test-only-change-before-hosting`. [Ảnh dashboard thật](figures/grafana-compose-20261122.png).

## Đã kiểm chứng

- Full Chrome **18/18, 0 skip, 0 flaky** sau cập nhật backend/worker: `compose-release-full-browser-20261122.json`. Sau đó chỉ sửa câu mô tả gợi ý public để không nhận cá nhân hóa/lịch sử mua hàng; kiểm riêng cards/caption qua Chrome đạt (`compose-public-copy-browser-20261122.json`). Không cộng thành 19 ca full suite.
- Model pinned MiniLM thật + 3 nguồn lexical/dense/graph, giá/tồn kho đối chiếu Business, 5 Product/25 cạnh/5 vector 384 chiều: `compose-semantic-verified-r2-20261122.json`.
- Sau checkout: outbox product 1 generation 2 đã delivered, tồn kho graph khớp Business, Prometheus scrape 3 targets đều up: `compose-demo-operations-20261122.json`.
- GitHub nhánh [rebuild/lumiere-demo-20261122](https://github.com/NhungHuyen2110/DATN/tree/rebuild/lumiere-demo-20261122), không merge nhánh cũ. 5 workflow của commit nền `2ad4a93` đạt; các commit sau phải xem trạng thái CI riêng trên GitHub.
- Đã diễn tập bootstrap **500 CSV/3 tài khoản/0 đơn** ở DB mới riêng, backup trước/sau, kiểm SQL độc lập; từ chối seed lại DB có dữ liệu: `hosting-catalog-bootstrap-rehearsal-20261122.json`, `hosting-guards-preflight-20261122.json`. Chưa chuyển website local 5 sản phẩm sang DB này, chưa index catalog này vào graph/vector hosting.
- Compose hosting và Caddy 2.10.2 validate đạt trong container không mạng; chưa cấp chứng chỉ và chưa deploy Internet: `hosting-config-validation-20261122.json`.
- SMTP reset đã thêm context kiểm chứng chỉ/hostname trước login; 2 test mock xác nhận certificate lỗi không gửi mật khẩu/email. Full backend sau sửa: 673 test và 829 subtest đạt, không gọi mail thật; real SMTP delivery vẫn cần cấu hình và test trên staging.

## Hosting trong trần 300.000đ cho một tháng

Chỉ dùng dữ liệu demo. Cấu hình dự kiến để kiểm thử: Linux x86_64, full root/Docker, khoảng 6 GB RAM, 3 vCPU, ít nhất 50 GB disk; đây là dự kiến từ lab, chưa là cam kết tải trên VPS. Ollama/Qwen và quality benchmark chưa nằm trong kết quả 18 ca trên.

Ứng viên cần đối chiếu hóa đơn: [VPSRE VPS Rẻ 5](https://vpsre.vn/vps-gia-re/) niêm yết 3 vCPU/6 GB/70 GB, 250.000đ/tháng tại thời điểm tra cứu. Chưa xác minh VAT, phí setup, tồn kho, KVM/IPv4 riêng và hiệu năng thực. Chỉ chọn chu kỳ **1 tháng** và thanh toán khi tổng cuối không vượt **300.000đ**, sau khi cấu hình phù hợp được xác nhận. Chưa đăng ký/đặt mua thay bạn. [Điều khoản](https://vpsre.vn/dieu-khoan-su-dung/), [chính sách hoàn tiền](https://vpsre.vn/chinh-sach-hoan-tien/).

Có thể dùng subdomain [Duck DNS miễn phí](https://www.duckdns.org/) thay mua domain riêng cho tháng demo. Cần tài khoản do bạn giữ và hostname trỏ đúng IP máy chủ; chưa tạo hoặc đổi DNS. Không gửi token, mật khẩu hay private key qua chat.

**Việc cần bạn làm tiếp:** xác nhận gói/giá cuối từ nhà cung cấp trong mức trần; sau khi thống nhất mới mua VPS và tạo hostname. Phần cấu hình, migration, seed, model, TLS, test staging và rollback do agent tiếp tục thực hiện. Chưa thể triển khai khi chưa có server/hostname được duyệt.

## Bộ cấu hình đã chuẩn bị để review

`compose.hosting.yaml`, `infra/proxy/Caddyfile`, `scripts/prepare_demo_hosting.py`, `scripts/bootstrap_demo_catalog.py`. Chưa chạy các bước này trên Internet.

Trên VPS mới sau khi được duyệt, clone **đúng nhánh demo**; không upload toàn bộ `.local-tmp` hoặc Docker VHD. Các lệnh dưới chạy trong shell **root**, tại thư mục repository mới; nếu dùng tài khoản sudo phải cấp quyền tương ứng để đọc/ghi cấu hình private:

```bash
python3 scripts/prepare_demo_hosting.py --domain TEN-DA-DANG-KY.duckdns.org
docker compose --env-file private/demo.env -f compose.yaml -f compose.hosting.yaml build frontend business-api ai-api index-worker
# Chỉ PostgreSQL, chưa mở website công khai:
docker compose --env-file private/demo.env -f compose.yaml -f compose.hosting.yaml up -d postgres
python3 scripts/bootstrap_demo_catalog.py --apply --confirm-demo --report private/bootstrap-result.json
```

Generator từ chối ghi đè cấu hình; mật khẩu ngẫu nhiên nằm trong `private/` đã loại khỏi Git/build context. Bootstrap chỉ chấp nhận DB mới `lumiere_test_demo_hosting`, snapshot trước seed, không cập nhật dữ liệu cũ. Mật khẩu demo mới nằm tại `private/recovery/demo-accounts.json`; backup/reference có group read cho UID/GID 10001, tài khoản mật khẩu vẫn chỉ owner đọc.

Sau khi được duyệt tải public model trên VPS, có thể chuẩn bị cache đúng revision (không tải từ request của người dùng):

```bash
mkdir -p private/models
docker run --rm --user 0 -e HF_HUB_OFFLINE=0 -e TRANSFORMERS_OFFLINE=0 -v "$PWD/private/models:/models" --entrypoint python lumiere-demo-hosting-ai-api:latest -c 'from huggingface_hub import snapshot_download; snapshot_download(repo_id="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", revision="e8f8c211226b894fcb81acc59f3b34ba3efd5f42", cache_dir="/models/hub", token=False)'
```

**Dừng trước public activation:** cấu hình SMTP nếu muốn thử gửi email reset thật, kiểm hostname/HTTPS và private credentials, rồi phê duyệt mở staging. Không dùng template fake hoặc mật khẩu local cho hosting. Worker từ chối ghi nếu thiếu backup/reference hoặc model; không bỏ guard để chạy nhanh. Lệnh tải model trên chưa được chạy trên VPS vì chưa có server.

Rollback: dừng đúng project demo, giữ volumes/backup; quay lại image/source đã xác minh. Không `down -v`, không DROP, không xóa `.local-tmp`. Audit từng file, toàn fault matrix, security scans, human labels, Style/Audience có nguồn, LLM narrative và báo cáo đồ án vẫn chưa hoàn tất.
