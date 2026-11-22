# Nhánh demo và phạm vi kiểm thử — 22/11/2026

Người dùng đã chọn dữ liệu demo, repository public và yêu cầu nhánh mới, không merge vào nhánh cũ. Remote được xác minh là https://github.com/NhungHuyen2110/DATN (khớp URL trong MASTER_PROMPT). Nhánh local mới: `rebuild/lumiere-demo-20261122`. Dry-run push đã đạt; trạng thái push thực tế phải đối chiếu remote/commit khi hoàn tất, không coi dry-run là đã upload.

Chưa có hosting hoặc domain. Chưa xác định số tiền tối đa cho demo một tháng; không mua dịch vụ, không public deploy và không thay DNS. Các giá trị trong `.env.example` chỉ là credential test, không dùng trên hosting.

## Thay đổi của lượt này

- Worker Dockerfile dùng cùng prefix layer AI đã build rồi cài bổ sung dependencies backend, giữ image worker độc lập và CPU-only. Build thực đạt: `docker-worker-cached-image-20261122.json`. Dependency check trong container không mạng/read-only đạt; CLI `--help` chạy được. Chưa coi build là worker end-to-end full Compose.
- `compose-internal-reads-after-memory-relief-20261122.json`: 9 lượt đọc nội bộ catalog/chat/gợi ý đạt. Không nhận phép đo này là benchmark tải hoặc SLA.
- Bộ fixture mới sao lưu PostgreSQL trước khi thêm 1 user reset/4 đơn giả. Không xóa dữ liệu các lượt trước. Token mới chỉ lưu hash trong DB, bản dùng cho test ở thư mục ignored trên D; không đưa vào Git.
- Full Chrome lượt đầu: 16 đạt/1 skip Grafana/1 lỗi tiền điều kiện wishlist. Test được sửa để tài khoản test dùng lại vẫn thực hiện đúng thao tác thêm sản phẩm, không thay logic ứng dụng. Bằng chứng lỗi được giữ trong `compose-demo-full-browser-20261122.json`; kết quả chạy lại lưu riêng.
- Workflows backend/AI/graph/PostgreSQL/browser/build được thêm trigger push riêng cho `rebuild/lumiere-demo-*`, vẫn giữ pull_request. Không merge vào nhánh cũ, không publish image tự động.
- Trước commit/push chạy `scripts/check_staged_release.py`: kiểm artifact bị cấm và một số mẫu credential, không in giá trị. Đây là kiểm tra heuristic, không thay vulnerability/history scans. Dữ liệu khách hàng/đơn hàng đã có trong lịch sử remote không được chỉnh hoặc thêm vào staged changes của lượt này.

## Các gate còn mở

Mốc kiểm chứng mới: `compose-demo-full-browser-r2-20261122.json` đạt **17/1 skip Grafana, 0 unexpected/flaky** trên image hiện tại, gồm Customer/COD, Staff/Admin, reset, diagnostics và public recommendations. Lỗi wishlist lượt đầu là tiền điều kiện tài khoản test dùng lại; đã sửa và giữ report lỗi. Không tăng timeout API hoặc đổi logic wishlist.

Full graph/vector/worker/monitoring Compose, dependency fault matrix, ổn định cold-start lặp lại, CI remote thực chạy, hosting HTTPS/secrets/backup và kiểm thử staging còn phải hoàn tất. Fact Style/Audience có nguồn, human labels và quality benchmark chưa có. Không nhận nhánh demo là toàn bộ đồ án đã nghiệm thu.

Test local hiện tại dùng 5 sản phẩm giả. Catalog 500 sản phẩm đã có bằng chứng CSV/graph/model ở lab riêng, chưa đồng nhất thành full catalog trên Compose này. Không ghi đè 5 sản phẩm đang có đơn test bằng CSV khác cùng IDs.

Rollback source: checkpoint `.local-tmp/checkpoints/demo-release-20261122/`; giữ dirty source ban đầu và các backup riêng. Dừng đúng project test, giữ volume; không `down -v`. Không xóa `.local-tmp` vì có Docker VHD hoạt động.
