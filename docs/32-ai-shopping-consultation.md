# AI tư vấn phong cách và giữ ngữ cảnh — 23/11/2026

Chỉ thay source trong `AI/`. Không sửa Frontend, Backend nghiệp vụ, thanh toán/VNPAY, ảnh sản phẩm, database hoặc cấu hình Compose. Image AI trước sửa còn giữ ở `lumiere-ai-before-consultation:20261123` để rollback riêng service.

## Thay đổi cho người sử dụng

- “Nữ thanh lịch chọn gì” được hiểu là một cuộc tư vấn. AI nêu hướng chọn, đưa sản phẩm thật để tham khảo và hỏi ngân sách, thay vì dừng ở thông báo thiếu nhãn.
- “Dưới 3 triệu”, “duoi3tr”, “em chỉ có 3tr” ở lượt tiếp giữ phong cách trước và thay ngân sách; không nhầm vàng 18K với giá 18 nghìn.
- Trả lời “mình thích bông tai” giữ giới hạn giá và chuyển danh mục. Không hỏi lại loại đã chọn.
- Hỏi vì sao gợi ý giữ nguyên các ID vừa trả, giải thích bằng lý do có trong kết quả và không tạo bộ sản phẩm khác.
- Nếu người dùng đính chính rằng không hỏi sản phẩm, ngữ cảnh mua sắm riêng của AI được bỏ. Không dùng thông tin đó để lôi câu hỏi khác trở lại product search.

## Không bịa nhãn hoặc bỏ điều kiện bắt buộc

Tách **định hướng tư vấn** khỏi **bộ lọc đã xác nhận**. Câu hỏi kiểu “chọn gì”, “tư vấn”, “gợi ý” có thể nhận mẫu tham khảo khi chưa có nhãn Audience/Style; câu trả lời nói rõ giới hạn này. Không ghi thêm node/edge/facts vào database.

`search()` vẫn mặc định strict. Top-K yêu cầu đúng nhãn, “chỉ chọn”, lọc bắt buộc và truy vấn cùng phong cách với sản phẩm tham chiếu giữ kiểm chứng cũ. Trẻ em không được tự thay bằng mẫu người lớn. Giá, tồn kho, danh mục, đá và chất liệu luôn giữ điều kiện đã nhận diện.

Khi có nhãn đúng đã được xác nhận, vẫn bắt buộc dùng nhãn đó. Khi chưa có, không đưa nhãn chưa xác minh vào `matched_entities`; cũng không lấy sản phẩm có nhãn trái với yêu cầu làm mẫu tham khảo. Giá/tồn kho được đọc lại từ Business API trước Top-K.

## Truy xuất và thời gian xử lý

Giữ embedding model, Qdrant, Neo4j anchor expansion, RRF và kiểm tra live. Query phong cách gốc vẫn được chuyển cho dense retrieval; không thay bằng tên sản phẩm tự đoán. Không gọi thêm bộ phân loại quà tặng cho câu tư vấn đã nhận diện, tránh encode lặp.

Nếu dense chưa sẵn sàng, tư vấn có thể dùng danh mục dây chuyền/bông tai làm điểm bắt đầu tham khảo; đây là lexical/category reference, không phải điểm semantic giả hoặc chứng nhận phong cách. Giá/tồn kho và giới hạn tiền vẫn kiểm tra. Nếu không kiểm tra được catalog, chỉ tư vấn cách chọn, không bịa tên/giá/mẫu.

Không tải model mới, không gọi Qwen, không warm-up/retry loop trong bài smoke. Không coi thay đổi này là nghiệm thu LLM hội thoại tổng quát hoặc benchmark chất lượng.

## Chứng cứ và thử lại

- `ai-consultation-tests-final-20261123.json`: bộ AI 150 ca, 149 đạt/1 skip cần isolated graph server, trước bổ sung cuối về lựa chọn danh mục.
- `ai-consultation-flow-final-20261123.json`: 15 ca tập trung của luồng cuối đều đạt; chặn network và không tải model.
- `AI/evaluation/consultation_smoke.py`: đúng một cuộc hội thoại 4 lượt, có timeout, không retry. Đối chiếu giá/tồn kho với API thật; kiểm tra Frontend/VNPAY và ID/thời điểm khởi động của các container ngoài AI không đổi. Kết quả live nằm ở `ai-consultation-live-20261123.json`; chỉ `successful: true` mới được tính đạt.

### Kết quả chạy local cuối

`ai-consultation-live-final-20261123.json`: **4/4 lượt đạt**, không retry trong bài kiểm tra. Câu đầu trả ba sản phẩm thật sau 7,921 giây; giải thích giữ nguyên ID sau 0,016 giây; thêm ngân sách mất 5,781 giây; chọn bông tai giữ ngân sách mất 0,890 giây. Giá/tồn kho được đối chiếu API hiện tại. Catalog vẫn 500 sản phẩm; mã Frontend, trạng thái VNPAY và ID/thời điểm khởi động Backend, Frontend, PostgreSQL, index-worker không đổi.

Các lượt tìm kiếm mang trạng thái `degraded`: bài này xác minh tư vấn có phương án dự phòng và sản phẩm có căn cứ, **chưa chứng minh dense/graph hoạt động đầy đủ hoặc chất lượng xếp hạng phong cách**. Không có nhãn phong cách/đối tượng đã xác minh nên sản phẩm được giới thiệu để tham khảo. Qwen hội thoại vẫn chưa được kích hoạt; bản sửa này không đạt khả năng hội thoại tổng quát như ChatGPT.

Giữ nguyên báo cáo lần đầu `ai-consultation-live-20261123.json` bị `catalog_unavailable`, không tính là đạt. Chẩn đoán đọc catalog sau đó thành công với 500 sản phẩm trong 0,53 giây; không thay timeout hoặc sửa Business API để che lỗi. Khi nguồn dữ liệu chậm trở lại, AI vẫn chỉ tư vấn cách chọn và không bịa sản phẩm.

Trên `http://127.0.0.1:18080`, bắt đầu cuộc chat bằng “nữ thanh lịch chọn gì”, hỏi lý do, rồi “duoi3tr” và “mình thích bông tai”. Khởi động lại riêng AI sẽ làm mất ngữ cảnh chat trong bộ nhớ; dữ liệu sản phẩm/đơn hàng không đổi.

Rollback dùng Compose override pin riêng `ai-api.image` về `lumiere-ai-before-consultation:20261123` rồi `up -d --no-build --no-deps ai-api`; không restart Backend/Frontend/database và không xóa volumes/dữ liệu.
