# Sửa ngữ cảnh ngân sách và trả lời kiến thức — 23/11/2026

Chỉ sửa source trong `AI/`, bổ sung test và tài liệu. Không chỉnh `.env`, Compose, Frontend, Backend nghiệp vụ, shared conversation, database, thanh toán hoặc hình ảnh sản phẩm. Giữ image `lumiere-ai-before-budget-dialogue:20261123` để quay lui riêng AI.

## Lỗi và cách sửa

Ở bản trước, “thanh lịch” không có động từ tư vấn bị coi là bộ lọc bắt buộc thiếu nhãn. Câu này không tạo `shopping_context`; câu ngân sách tiếp theo không có entity hay động từ mua nên bị định tuyến sang `general_question`. Khắc phục hai phía: nhận câu sở thích ngắn thành tư vấn, và nhận ngân sách đứng riêng thành yêu cầu tìm trang sức. Ngữ cảnh tư vấn giữ động từ rõ ràng khi thêm giá, không trở về lọc nhãn bắt buộc.

`dưới 3tr`, `dưới 3 triệu`, `3 triệu` đều được kiểm tra. Khi có token còn hạn, giữ yêu cầu trước; khi token hết hạn hoặc không có token, chỉ tìm theo ngân sách mới, không suy đoán giới tính/phong cách trước đó. Ngân sách bare được hiểu là mức tối đa; “dưới” vẫn là giới hạn nghiêm ngặt. Giá/tồn kho phải đọc lại nguồn thật. Không biến 18K thành 18 nghìn.

`rag/conversation_service.py` sử dụng ConversationStore, phân quyền scope và các tiện ích của shared nhưng giữ toàn bộ lượt Customer trong lock. Chặn gửi trùng, giữ lịch sử sáu lượt, không tự tìm sản phẩm khi hỏi kiến thức hoặc viết lời chúc. Staff/Admin vẫn dùng coordinator cũ và không chịu thay đổi trong lượt này.

## Phần trả lời dùng được ngay

`rag/domain_dialogue.py` có nội dung kiến thức đã chọn lọc: CZ/Moissanite và kim cương, bảo quản, cách cân nhắc cỡ nhẫn, định hướng thanh lịch/tối giản, lời chúc sinh nhật/kỷ niệm. Có thể yêu cầu “nói ngắn gọn hơn” cho nội dung thuộc bộ này. Trả `response_mode=reviewed_domain_answer`, tách rõ khỏi output LLM. Không chèn sản phẩm, giá, số liệu hay chính sách cửa hàng vào câu trả lời kiến thức.

Thông tin loại đá tham khảo [GIA về đá mô phỏng](https://www.gia.edu/gem-imitation); bảo quản tham khảo [GIA về chăm sóc trang sức](https://www.gia.edu/articles/gia-news-research-tips-caring-jewelry). Các lời khuyên thẩm mỹ là hướng dẫn chọn chung, không phải nhãn chứng nhận cho sản phẩm trong catalog. Bộ này có phạm vi hữu hạn; không xem nó là model hiểu mọi câu hỏi hay semantic benchmark.

Adapter Qwen hiện có vẫn giữ nguyên và chỉ được gọi nếu bật cấu hình sẵn có. Lượt sửa này **không bật Qwen, không tải model, không thực hiện thêm warm-up** sau hai lần nghiệm thu cũ chưa đạt. Câu ngoài kiến thức có thể hỏi lại để làm rõ, không dùng thông báo kỹ thuật “lớp trả lời tự nhiên chưa sẵn sàng”. Khả năng LLM hội thoại tổng quát vẫn chưa hoàn tất; không đánh dấu toàn bộ AI đạt yêu cầu ban đầu.

## Kiểm chứng và rollback

- `ai-budget-dialogue-tests-20261123.json`: 18 ca tập trung đạt, chặn network.
- `ai-budget-dialogue-regression-20261123.json`: 154 chạy, 153 đạt/1 skip cần isolated graph server; không gọi model hoặc dịch vụ thật. Không phải đánh giá chất lượng Qwen.
- `AI/evaluation/budget_dialogue_smoke.py`: một lần chạy local hữu hạn, bảy lượt, timeout mỗi request, không retry. Kiểm tra giá/tồn kho, catalog, Frontend và trạng thái VNPAY. Chỉ báo cáo `successful=true` mới tính là đạt.
- `ai-budget-dialogue-live-20261123.json`: **7/7 đạt** ngay lần chạy này. “Dưới 3tr” mất 2,454 giây; “dưới 3 triệu” mất 5,578 giây; “3 triệu” mất 1,781 giây. Kiến thức và rút gọn mất 0,015–0,016 giây. Câu ngân sách không có conversation ID vẫn trả sản phẩm thật. Các lượt truy xuất vẫn mang trạng thái `degraded`; chưa nghiệm thu đầy đủ dense+graph hoặc Qwen.
- `ai-budget-unchanged-services-20261123.json`: ID và thời điểm khởi động Backend, Frontend, PostgreSQL, index-worker không đổi sau deploy. Catalog vẫn 500 sản phẩm; hash Frontend và trạng thái VNPAY giữ nguyên. Không dùng kiểm tra này để suy ra đã kiểm thử lại toàn bộ nghiệp vụ.

Rollback: pin image của riêng `ai-api` về `lumiere-ai-before-budget-dialogue:20261123` bằng Compose override, dùng `up -d --no-build --no-deps ai-api`, reload nginx để cập nhật DNS nếu cần. Không xóa volume, không restart các container nghiệp vụ. Restart AI làm mất lịch sử chat trong bộ nhớ; sản phẩm và đơn hàng không đổi.
