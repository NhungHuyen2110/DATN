# Semantic-first RAG và bằng chứng graph — 24/11/2026

**Chưa nghiệm thu luồng câu hỏi lạ. Bản local được đưa về checkpoint trước lượt này; không tuyên bố đã bật thành công bản GraphRAG mới.** JSON planner và narrative mới đều tắt trong overlay mặc định, chờ staging đủ điều kiện và kiểm thử đạt.

Yêu cầu người dùng là hiểu ngữ nghĩa và truy xuất dữ liệu, không tăng bộ câu hỏi/trả lời mẫu. Chỉ sửa AI, overlay AI, kiểm thử và tài liệu; không đổi chức năng bán hàng, tài khoản, thanh toán, hình ảnh hoặc dữ liệu.

## Lỗi định tuyến đã sửa

`rag_service.py` trước đây nhận phân loại embedding cho một câu chưa có alias, nhưng chỉ chuyển sang retrieval nếu nhãn là `gift_advice`. Nếu embedding nhận `product_search`, API vẫn giữ intent `general_question` và trả lời hội thoại. Đã sửa để cả hai intent được chấp nhận đi vào retrieval, vẫn giữ ngưỡng cosine 0,45 và margin 0,04; không ép câu có độ tin cậy thấp thành tìm kiếm.

Các vector đại diện intent được mô tả bằng định nghĩa nhu cầu/miền trang sức thay cho câu hỏi mẫu. Đây là embedding classifier có nhãn, không phải tra bảng câu hỏi giống chuỗi. Nội dung trả lời sản phẩm lấy từ dữ liệu truy xuất, không lấy từ các mô tả intent. Chỉ cache vector định nghĩa công khai theo encoder; không cache câu hỏi/vectors của người dùng. Embedding model và collection hiện có giữ nguyên.

Truy vấn tự nhiên sau chuẩn hóa tiền tệ đi nguyên vào dense Qdrant. Candidate IDs được dùng làm anchors cho Neo4j; các path phải đối soát với dữ liệu nghiệp vụ hiện tại. Fusion/ranking/Top-K giữ nguyên; model không được tự chọn lại ID, đổi thứ hạng hoặc tạo số liệu. Response thêm `retrieval_sources_used`, `resolved_entities`, và `matched_relationships` cho các path thật để kiểm chứng phương pháp. Trạng thái degraded tiếp tục phản ánh nguồn lỗi, không tự đổi thành thành công đầy đủ.

Narrative RAG tùy chọn chỉ gọi khi kết quả xác nhận có cả dense và graph. Model nhận dữ liệu thuộc tính/quan hệ đã chọn, không nhận quyền SQL/Cypher hoặc công cụ ghi. Giá/tồn kho/tên sản phẩm trong danh sách vẫn do code lấy nguồn thật. Nội dung công cụ được gửi dưới vai trò dữ liệu user, không ghép vào system prompt; không thực thi chỉ dẫn trong mô tả CSV. Lượt narrative chờ tối đa tám giây và chỉ được gọi nếu còn trong ngân sách tổng 35 giây. Khi timeout giữ phần kết quả có cấu trúc, không retry.

Catalog khi bật retrieval limits có SourceGate riêng bốn giây cho toàn lượt phân trang, chỉ một task đang chạy và không xếp hàng thêm khi nguồn chậm. Trước đó chỉ có HTTP timeout ba giây cho từng trang, nên tổng cả lượt không bị giới hạn tương ứng. Lượt gọi nguồn bị quá hạn không trả catalog một phần hoặc dữ liệu cũ. Phần hội thoại general cũng dùng thời gian còn lại trong ngân sách 35 giây, thay vì cộng thêm trọn 24 giây sau công đoạn trước. Đây là deadline caller, không phải SLA cho máy đang thiếu tài nguyên; các task nguồn hết hạn vẫn có thể kết thúc trong worker riêng nhưng không nhận thêm task hoặc được dùng làm kết quả muộn.

Với câu ngoài miền, phản hồi ngắn theo phạm vi trợ lý rồi mời người dùng trở lại nhu cầu trang sức. Code chỉ thêm lời mời một lần trong cuộc trò chuyện; không tự tạo thẻ sản phẩm cho câu ngoài miền. Model nhỏ vẫn có thể diễn đạt chưa tốt, không xem guard này là kiểm định mọi nội dung.

## Thử nghiệm JSON planner không đạt và không bật

Đã thử `semantic_planner.py`: Pydantic schema, quote phải thuộc câu gốc, canonical IDs do ontology server giải quyết, không nhận giá/SQL/Cypher do model tạo. Ràng buộc schema chỉ kiểm tính hợp lệ cấu trúc, **không chứng minh ý nghĩa suy luận đúng**.

- `ai-semantic-plan-probe-20261124.json`: bản nhiều trường vượt deadline 12 giây; câu kế tiếp gặp cooldown.
- `ai-semantic-plan-probe-compact-20261124.json`: bản rút gọn trả nhầm mô tả đeo ngón tay thành Moissanite; ca ngoài miền cũng không đạt. Không tăng timeout hoặc chạy lặp để tìm một kết quả đẹp.
- Vì vậy `LUMIERE_SEMANTIC_PLANNER_ENABLED=false` trên bản phục vụ. Không dùng model 0.6B để áp bộ lọc/ghi node theo những suy đoán này. Module được giữ như thử nghiệm có kiểm thử kỹ thuật và cảnh báo, **chưa được nghiệm thu semantic Entity Linking bằng LLM**. Luồng phục vụ dùng embedding retrieval, graph traversal và entity linker hiện có.

## Chứng cứ kiểm thử

Trước deploy, diagnostics thật trên runtime trước sửa với “Top 3 nhan duoi 3 trieu” đã trả `status=ok`, không degraded: dense sáu candidate, graph sáu candidate, candidate pool 35; dense 3,679 giây, graph 0,830 giây, tổng 6,146 giây. Đây là một snapshot chứng minh nguồn có hoạt động, không phải SLA hoặc giải thích duy nhất mọi lần degraded trước đó.

- `ai-semantic-plan-tests-20261124.json`: 181 chạy, 180 đạt/1 skip, mốc ban đầu.
- `ai-semantic-plan-tests-final-20261124.json`: 182 chạy, 181 đạt/1 skip trước chỉnh routing cuối.
- `ai-semantic-routing-final-tests-20261124.json`: 28 ca tập trung cuối đạt, gồm bug định tuyến semantic product, không đổi ranking khi tạo narrative, dữ liệu công cụ không thành system instructions, bridge không lặp, ontology/quote validation và giá sau chuẩn hóa.
- `ai-semantic-rag-release-tests-20261124.json`: **187 chạy, 186 đạt/1 skip** cần graph server riêng, sau bổ sung source deadline và budget hội thoại. Không gọi model/DB/server thật.
- `ai-semantic-rag-live-20261124.json`: lần chạy website trước sửa source deadline bị ReadTimeout, chưa có ca đạt; giữ báo cáo lỗi, không coi là đạt. Lần kiểm tra sau sửa deadline ghi ở file riêng, không thay số liệu lần lỗi.
- `ai-semantic-rag-live-final-20261124.json`: sau sửa deadline, request đầu trả lỗi catalog có kiểm soát trong 10,032 giây, không có sản phẩm; **chưa đạt** kiểm tra diễn đạt đeo ngón tay. Dừng bài, không chạy tiếp ca graph/reference và ngoài miền; không tự thêm dữ liệu để làm test đạt.
- `ai-semantic-rag-readiness-20261124.json`: sau CLI up vượt 70 giây, inspect vẫn ghi nhận image mới running/healthy và website, Business, AI health HTTP 200. Health không chứng minh retrieval thành công, như ca catalog lỗi nêu trên.
- `ai-semantic-rag-unchanged-services-20261124.json`: ID/thời điểm khởi động các container ngoài AI không đổi, catalog 500 sản phẩm và VNPAY vẫn enabled trước rollback. Kết quả phục hồi runtime được ghi riêng.
- **`ai-semantic-rag-restored-20261124.json`: phục hồi đạt**. Image trước lượt thử healthy; website/Business/AI health đều HTTP 200 và chat chào hỏi thành công. Không chạy lại benchmark sau phục hồi, không diễn giải health thành semantic acceptance.
- `AI/evaluation/semantic_rag_smoke.py`: ba yêu cầu thật không retry: diễn đạt đeo ngón tay không dùng từ nhẫn; related products cùng đá với anchor vừa tìm; chủ đề gieo hạt ngoài miền. Kiểm tra nguồn dense+graph, loại sản phẩm, giá/tồn kho, path HAS_GEMSTONE và phản hồi không tạo sản phẩm ngoài miền. Chỉ `successful=true` mới tính đạt.

## Phục hồi và phần chưa đạt

Image trước sửa: `lumiere-ai-before-semantic-rag:20261124`. Rollback pin image riêng AI qua override, `up -d --no-build --no-deps ai-api`, reload nginx nếu IP đổi; không xóa volume hoặc đổi dữ liệu. Có thể tắt riêng narrative bằng `LUMIERE_GROUNDED_NARRATIVE_ENABLED=false`; JSON planner phải tiếp tục tắt cho đến khi có đánh giá đủ tin cậy.

Chưa có benchmark held-out đủ rộng do người chấm, semantic Entity Linking LLM còn không đạt, chưa có production/staging load acceptance, model có thể timeout hoặc diễn đạt thiếu chính xác. Không tuyên bố xử lý đúng mọi câu lạ hoặc tương đương ChatGPT/Gemini. Nhãn Audience/Style chưa được xác nhận ở catalog không được bịa thành quan hệ sản phẩm. Staff/Admin không thay đổi trong lượt này.
