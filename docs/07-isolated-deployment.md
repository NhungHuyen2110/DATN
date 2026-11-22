# PHASE 7 — Đóng gói triển khai cách ly

CURRENT 22/11: Engine 28.5.1 đã phục hồi; Docker VHD hoạt động trên D qua junction, có backup/checksum/rollback (`16-docker-storage-on-d.md`). Frontend, Business và AI image đã build; 5 core containers chạy qua loopback proxy 18080. Full Chrome trên image trước đạt 17/1 skip Grafana. AI container outage bản mới đạt login/COD/role guard và recovery có đối chiếu live (`compose-ai-container-fault-final-20261122.json`). Worker image/full graph/dense/monitoring Compose và dependency fault matrix còn thiếu; PHASE 7 chưa nghiệm thu.

CHANGE: `compose.yaml` dùng project `lumiere-rebuild-test`, volume riêng, không dùng tên container cố định, không mount `.env` hay source host vào container. Chỉ proxy mở cổng loopback 18080. PostgreSQL, Qdrant, Neo4j và Ollama không publish cổng. Business API không phụ thuộc AI/graph/vector trong startup. Ollama là profile tùy chọn; chat mới trả lời deterministic khi không dùng LLM.

Frontend giữ HTML/CSS/JS hiện có. Nginx chèn runtime config để request dùng `/api` và `/ai` cùng origin. Proxy resolve DNS động để AI dừng không ngăn các route business. Backend giữ static mount tương thích nhưng image backend không chứa frontend thật. Health live độc lập DB; health ready dùng kiểm tra DB cũ. Image AI chỉ chứa catalog CSV, không đóng gói Customer/Order seed. Legacy recommendation cần các nguồn cũ có thể trả 503; không coi nó đã tương thích hoàn toàn.

TEST:

```powershell
# Chỉ kiểm tra cấu trúc, không ghi database:
& 'D:\JewelryDatasetGenerator\.venv\Scripts\python.exe' -B scripts/validate_deployment.py
docker compose --env-file .env.example -f compose.yaml config --quiet
# Các lệnh sau chỉ thực hiện khi Docker đã sẵn sàng và xác nhận môi trường test:
docker compose --env-file .env.example -f compose.yaml build
docker compose --env-file .env.example -f compose.yaml up -d
docker compose --env-file .env.example -f compose.yaml ps
```

RISK: không auto migrate/seed trên startup; phải chuẩn bị DB test riêng trước nghiệm thu container. Native browser đã kiểm tra migration/fixtures thật, nhưng không chứng minh container/proxy. Model mount read-only cần cache; thiếu model fallback lexical/graph. `.env.example` đã chọn collection versioned/revision, vẫn phải index đúng môi trường. Worker và monitoring profiles đã thêm; HTTPS production chưa có. Tags/packages còn cần build để xác minh. Workflows chưa chạy GitHub, không publish/deploy; chưa scan/release/staging hoàn chỉnh.

COMPATIBILITY: chưa restart website/DB cũ, không thay `.env`. Frontend giữ style và business logic; thêm diagnostics Admin độc lập, sửa tối thiểu URL reset password hỗ trợ API base `/api`, có checkpoint. Native Chrome 18/18 và Docker core Chrome 17/1 skip là hai lượt riêng. Container core dùng 5 sản phẩm giả; Neo4j/Qdrant Compose chưa chạy, đang kiểm lexical fallback. Network real-model worker được kiểm ở lab kết hợp native/container riêng.

ROLLBACK: dừng đúng project test bằng `docker compose --env-file .env.example -f compose.yaml stop`; giữ volume. Không chạy `down -v`. Khôi phục có chọn lọc health route từ `.local-tmp/checkpoints/deployment-20261121/backend-main.py` nếu cần; giữ các chỉnh sửa cũ của người dùng. Xóa cấu hình triển khai khỏi luồng sử dụng không tác động hệ thống cũ.

NEXT: Docker daemon hoạt động → build → migration/seed test được xác nhận → smoke qua proxy → dừng từng service test và kiểm tra fallback/phục hồi; sau đó mới bật sync và triển khai monitoring. Chưa public hosting hoặc phát sinh chi phí.
