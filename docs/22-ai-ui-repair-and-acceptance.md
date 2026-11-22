# Sửa AI trên giao diện và kiểm chứng dữ liệu cũ — 22/11/2026

Nguồn dữ liệu local vẫn là bản sao đầy đủ database cũ; AI là retrieval V2 có model MiniLM cố định, Qdrant, Neo4j, RRF và kiểm giá/tồn kho từ Business API. Không quay lại pipeline CSV/AI cũ để xử lý lỗi UI.

## Lỗi có bằng chứng và thay đổi

`frontend/assets/js/management-ai.js` trước đây gọi `/admin/ai/chat` hoặc `/staff/ai/chat` trực tiếp. Tại cổng 18080, đường nghiệp vụ phải đi qua `/api`; URL cũ đi vào frontend. Đã dùng API base cấu hình sẵn của `api.js`, tương thích cả proxy và chạy Business trực tiếp.

Widget Customer ở trang sản phẩm trước đây chỉ vẽ 5 thẻ dù server có thể trả Top 10. Đã hiển thị tối đa 10 theo kết quả server, bổ sung ảnh SKU, liên kết chi tiết, tồn kho và lý do có nguồn. Chat trang chủ giữ giới hạn server, có liên kết chi tiết/lý do/tồn kho, chặn gửi trùng và timeout 50 giây. Lỗi mạng hướng dẫn thử lại mà vẫn mua sắm được; không yêu cầu khách kiểm cổng/CORS/log.

## Môi trường kiểm chứng

Đã dump website đang phục vụ vào thư mục private trên D, restore vào DB QA mới `lumiere_test_ai_acceptance`; giữ 500 sản phẩm/12 đơn và tài khoản cũ, thêm 3 tài khoản QA riêng. Không đặt lại mật khẩu hoặc thêm account test vào DB đang phục vụ. `compose.ai-acceptance.yaml` mở proxy QA **127.0.0.1:18081**, dùng frontend/AI thật và Business riêng trỏ đúng QA DB. Dump/fixture bị loại khỏi Git, thừa kế ACL riêng của bản backup cũ.

Chrome thực dùng cấu hình HTML được phục vụ, **không inject API base, không mock response thành công**. Chỉ fault case cuối chủ động chặn request chat trong browser.

- Lượt đầu 11 kiểm tra AI/role đạt: `original-ai-roles-browser-20261122.json`.
- Lượt mở rộng 13 kiểm tra đạt: `original-ai-roles-top10-browser-20261122.json`.
- Gồm đăng nhập UI Admin/Staff/Customer, chatbot management đúng `/api`, aggregate tồn kho 500 và số đơn pending khớp SQL, 401 guest/403 sai vai trò, chat trang chủ Top 3, widget đủ 10 ảnh/link/thẻ và lỗi chat không mất catalog.
- Không cộng 11+13 thành 24 ca khác nhau; đây không thay full business/COD/write suite trên bản sao dữ liệu cũ.
- Fixture QA ban đầu dùng `.invalid` bị EmailStr từ chối 422; đã sửa riêng QA sang domain `example.com`. Fault test đầu chưa chờ catalog-ready; đã đặt precondition trước khi chặn chat và chạy lại đạt. Không thay mật khẩu/tài khoản nguồn để làm test chạy.

Chạy lại với một tên report mới:

```powershell
$env:NODE_PATH="$PWD\.local-tmp\browser-tools\node_modules"
node scripts/browser/verify-original-ai.cjs .local-tmp/original-db-20261122-014434/ai-acceptance/fixture.json .local-tmp/ai-browser-recheck.json
```

QA account/fixture chỉ ở private artifact; không đưa vào README public. Nguồn và DB 18080 không bị ghi bởi các ca QA. Để giảm RAM sau test, dừng đúng `business-qa proxy-qa`; giữ DB/backup để tái lập. Không dùng remove-orphans hoặc xóa volume.

## Phần AI còn phải hoàn thiện

CI của `d67614e` đã đạt đủ 5 workflow; commit sửa UI tiếp theo phải theo dõi riêng. Máy có sẵn Qwen 2.5 3B/7B, Ollama native đang nghe, nhưng chỉ khoảng 1 GiB RAM Windows trống và Intel Iris Xe; chưa bật thêm model 3B vào full stack khi chưa kiểm ngân sách RAM. Không coi deterministic answer là đã nghiệm thu LLM narrative.

Các demo Audience/Style còn thiếu fact được xác minh trong catalog gốc. Không tự gán “nữ/thanh lịch” từ ảnh/tên để làm demo đạt. Cần bổ sung luồng ghi nhận/review fact có nguồn và nối vào graph/filter trước khi có thể nghiệm thu. Benchmark 105 câu vẫn cần người review; hosting vẫn cần VPS/hostname được duyệt. Những việc code/test độc lập tiếp tục theo đặc tả.
