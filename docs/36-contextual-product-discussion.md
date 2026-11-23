# Customer AI: hỏi tiếp, so sánh mẫu và giữ điều kiện — 24/11/2026

Phạm vi chỉ source `AI/`, kiểm thử và tài liệu. Không đổi Frontend, Backend nghiệp vụ, shared conversation, database, graph/vector schema, VNPAY, mã giảm giá hoặc ảnh. Giữ nguyên model nhỏ đã nghiệm thu hôm trước, không tải hoặc tăng kích thước model.

## Hành vi mới

- “So sánh 2 mẫu đầu” hoặc “so sánh mẫu thứ nhất và mẫu thứ hai” lấy đúng vị trí trong danh sách server vừa trả, không nhầm số thứ tự với ProductID. Không tìm bộ sản phẩm khác, không sửa thứ hạng và không thêm thẻ mới.
- “Mẫu thứ hai có chất liệu gì?” chỉ nói về mẫu đó. Giá, chất liệu, đá và tồn kho được đọc lại Business API trước khi trả lời; không lấy giá cũ trong lịch sử giả làm giá hiện tại. Chênh lệch giá được tính bằng Decimal từ dữ liệu đọc lại.
- “Mẫu này” khi có nhiều kết quả hoặc vị trí không có trong danh sách sẽ được hỏi lại. Khi catalog lỗi/timeout, giữ đúng các mã tham chiếu, thông báo chưa kiểm tra được và không bịa thông tin.
- Sau tư vấn ngân sách, hỏi xen kiến thức thuộc bộ chủ đề đã duyệt như “Moissanite là gì?” vẫn giữ điều kiện mua sắm. Đổi sang câu hỏi không liên quan hoặc đính chính không cần gợi ý sẽ bỏ ngữ cảnh mua sắm. Không tuyên bố hiểu mọi chủ đề xen ngang.
- “Đổi sang bông tai dưới 2tr” thay đồng thời danh mục và ngân sách, giữ gu thanh lịch đã nêu. Không ghép nguyên câu mới vào bộ lọc cũ gây hai ngân sách/danh mục trái nhau. Câu có nội dung khác như “giá vốn” hoặc phủ định danh mục không được tự ghép bằng quy tắc này.

`rag/product_dialogue.py` không dùng model để so sánh dữ liệu hoặc tạo lý do phong cách; mọi giá trị lấy từ catalog hiện tại. SourceGate chỉ cho một lần đọc đang chạy, caller chờ tối đa bốn giây và cooldown mười giây khi lỗi. Không retry từ request. API shutdown đóng gate. Không tạo công cụ SQL/Cypher cho model.

Coordinator Customer tái sử dụng ConversationStore có scope/TTL/lock hiện tại; không đụng flow Staff/Admin. Sau so sánh, danh sách xếp hạng trước vẫn là `last_result`, nên câu hỏi tiếp không mất liên kết. Các nhãn Audience/Style chưa được xác minh vẫn không được tuyên bố đúng cho sản phẩm.

## Kiểm thử

- `ai-contextual-dialogue-tests-20261124.json`: lần đầu chưa đạt ba ca có cùng nguyên nhân: “2 mẫu đầu” bị nhận riêng thành vị trí đầu trước khi nhận cụm hai mẫu. Giữ báo cáo lỗi, đã sửa thứ tự xử lý.
- `ai-contextual-dialogue-tests-final-20261124.json`: **172 chạy, 171 đạt/1 skip** cần graph server riêng. Không gọi model/DB/server thật. Các ca mới kiểm giá thay đổi từ nguồn live giả lập, không dùng giá lịch sử; vị trí không hợp lệ; timeout; guard nghiệp vụ; giữ gu khi đổi hai điều kiện; giữ context sau kiến thức và xóa khi đổi chủ đề; không gọi model/retrieval khi so sánh.
- `AI/evaluation/contextual_dialogue_smoke.py`: một chuỗi local năm lượt, deadline từng request, không retry, không ghi DB. Chỉ báo cáo `successful=true` mới tính đạt, không suy ra quality benchmark từ unit tests.
- `ai-contextual-dialogue-live-20261124.json`: **5/5 đạt** ngay lần chạy live này. Tư vấn đầu 17,062 giây; so sánh đúng #24/#75 trong 0,766 giây; thông tin mẫu thứ hai #75 trong 0,563 giây; kiến thức `local_llm_dialogue` 18,187 giây; đổi sang bông tai dưới 2 triệu trả #275/#448 trong 6,735 giây. Đã đối chiếu tên/giá và điều kiện danh mục/giá/tồn kho với Business API. Search vẫn `degraded`, không xem đây là nghiệm thu toàn bộ dense+graph.
- `ai-contextual-dialogue-unchanged-services-20261124.json`: ID và thời điểm khởi động Backend, Frontend, PostgreSQL, worker không đổi. Bài live cũng đối chiếu hash Frontend và trạng thái VNPAY, catalog vẫn 500 sản phẩm. Không coi đó là full regression mọi nghiệp vụ.

## Rollback và giới hạn

Image trước sửa giữ riêng ở `lumiere-ai-before-contextual:20261124`. Pin image này cho `ai-api` qua Compose override và dùng `up -d --no-build --no-deps ai-api`; giữ các overlay commerce/model đang dùng, reload nginx khi IP AI đổi. Không restart Backend/Frontend/database/worker và không xóa volumes. Khởi động lại AI làm mất lịch sử trong RAM nhưng không đổi dữ liệu nghiệp vụ.

Không gọi toàn bộ AI hoàn thiện như ChatGPT/Gemini. Model 0.6B còn hạn chế văn phong/tuân thủ chỉ dẫn; chưa có đánh giá tiếng Việt có người chấm hoặc nghiệm thu tải/hosting. Các truy vấn ordinal chỉ là hỗ trợ tham chiếu có cấu trúc, không thay thế semantic retrieval. Qdrant/Neo4j, Top-K, embedding và quyền truy cập giữ nguyên. Staff/Admin chưa bật model mới; public staging chưa có VPS.
