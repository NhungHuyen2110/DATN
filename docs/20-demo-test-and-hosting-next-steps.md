# Test demo và bước triển khai tiếp theo — 22/11/2026

## Bản bạn có thể test ngay

Mở http://127.0.0.1:18080 trên máy này. Website đã chuyển sang **bản sao đầy đủ database cũ `lumiere_backend_test`**, tên bản sao chạy local là `lumiere_test_original_data`. Có **500 sản phẩm/500 ảnh đúng SKU, 11 tài khoản, 12 đơn, 15 dòng đơn và 9 giao dịch**; giữ cả giỏ hàng, yêu thích, đánh giá, coupon và liên hệ. Dùng tài khoản/mật khẩu cũ của bạn; không reset hoặc thay bằng tài khoản giả. Xóa cookie cũ hoặc mở cửa sổ riêng tư nếu trình duyệt vẫn giữ phiên thử nghiệm trước.

Digest toàn bộ dòng ở 20 bảng nghiệp vụ khớp sau chuyển ứng dụng; migration chỉ bổ sung schema/outbox. Cả 500 ảnh qua HTTP khớp từng byte với file gốc; Chrome thật tải đủ catalog và giải mã được ảnh catalog/chi tiết, gồm sản phẩm ID 500. Bằng chứng: `original-project-data-readonly-20261122.json`, `original-project-browser-20261122.json`. Đây là kiểm tra guest/read-only; chưa chạy lại toàn bộ 18 ca có ghi dữ liệu trên các tài khoản cũ.

Có 10 service ứng dụng chạy độc lập; Neo4j/Qdrant dùng volume mới cho catalog cũ. **Kiểm semantic 500 đã đạt:** 500 job done, 500 Product/2.500 quan hệ/500 vector 384 chiều, ba nguồn lexical/dense/graph, Top 3 có giá/tồn kho và graph paths được đối chiếu (`original-project-semantic-20261122.json`). Lượt cuối không retry HTTP; có chờ sẵn sàng retrieval 5 lần, không coi là SLA. Sau hoạt động login/logout, 13 phiên cũ còn nguyên, 1 phiên bị bỏ và 1 phiên mới; 19 bảng còn lại và 13 bộ đếm ID không đổi. Bản restore ban đầu giữ đủ toàn bộ phiên. Ollama chưa bật; chưa nhận LLM narrative đã hoàn tất.

Bạn thử Customer: đăng nhập tài khoản cũ → sản phẩm → yêu thích → giỏ hàng → COD → xem đơn. Staff/Admin dùng tài khoản cũ đúng vai trò để kiểm tra đơn và tồn kho; thao tác đổi trạng thái sẽ ghi vào bản sao local. Câu mẫu: “Top 3 nhẫn dưới 8 triệu”. Database gốc vẫn dừng, không bị ghi; bản 5 sản phẩm và volume AI cũ được giữ để rollback.

Grafana local: http://localhost:18080/grafana, tài khoản `admin`, mật khẩu test `test-only-change-before-hosting`. [Ảnh dashboard thật](figures/grafana-compose-20261122.png).

## Bằng chứng hồi quy trước khi chuyển dữ liệu (5 sản phẩm giả)

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
# DỪNG: chuẩn bị restore bản sao database cũ đã duyệt trước khi mở website.
# Không chạy bootstrap_demo_catalog.py cho lần triển khai dùng dữ liệu cũ.
```

Generator từ chối ghi đè cấu hình; mật khẩu ngẫu nhiên nằm trong `private/` đã loại khỏi Git/build context. Bootstrap CSV trước đây chỉ là diễn tập DB trống, không còn là nguồn cho lần triển khai theo yêu cầu mới. Phải chuẩn bị restore database cũ qua kênh riêng, giữ ID/quan hệ/ảnh, kiểm dữ liệu tài khoản/phiên trước công khai và tạo backup-reference khớp DB hosting. Không đưa dump hoặc dữ liệu khách hàng lên GitHub. Chưa chạy restore hosting vì chưa có server được duyệt.

Sau khi được duyệt tải public model trên VPS, có thể chuẩn bị cache đúng revision (không tải từ request của người dùng):

```bash
mkdir -p private/models
docker run --rm --user 0 -e HF_HUB_OFFLINE=0 -e TRANSFORMERS_OFFLINE=0 -v "$PWD/private/models:/models" --entrypoint python lumiere-demo-hosting-ai-api:latest -c 'from huggingface_hub import snapshot_download; snapshot_download(repo_id="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", revision="e8f8c211226b894fcb81acc59f3b34ba3efd5f42", cache_dir="/models/hub", token=False)'
```

**Dừng trước public activation:** cấu hình SMTP nếu muốn thử gửi email reset thật, kiểm hostname/HTTPS và private credentials, rồi phê duyệt mở staging. Không dùng template fake hoặc mật khẩu local cho hosting. Worker từ chối ghi nếu thiếu backup/reference hoặc model; không bỏ guard để chạy nhanh. Lệnh tải model trên chưa được chạy trên VPS vì chưa có server.

Rollback: dừng đúng project demo, giữ volumes/backup; quay lại image/source đã xác minh. Không `down -v`, không DROP, không xóa `.local-tmp`. Audit từng file, toàn fault matrix, security scans, human labels, Style/Audience có nguồn, LLM narrative và báo cáo đồ án vẫn chưa hoàn tất.
