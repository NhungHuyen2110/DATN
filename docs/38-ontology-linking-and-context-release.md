# Semantic entity linking và hội thoại có ngữ cảnh — 24/11/2026

Phạm vi: chỉ AI, profile Docker của AI, kiểm thử và tài liệu. Không chỉnh nghiệp vụ, thanh toán, đăng nhập hay dữ liệu sản phẩm. Đây là bản nâng cấp có giới hạn; chưa nghiệm thu toàn bộ đặc tả hoặc chất lượng tương đương ChatGPT/Gemini.

## Thay đổi

- Dùng chính embedding MiniLM đa ngôn ngữ hiện có để đối chiếu câu hỏi với định nghĩa Category trong ontology. Không thêm bảng câu hỏi/trả lời mẫu, không thay model hoặc collection. Vector định nghĩa công khai được cache; vector câu hỏi chỉ dùng cho đúng request rồi chuyển tiếp sang Qdrant.
- Link tự động cần cosine tối thiểu 0,60 và khoảng cách hai lựa chọn tối thiểu 0,10. Khi điểm cao nhưng hai loại gần nhau, hỏi làm rõ bằng các lựa chọn tính từ điểm thực tế. Giữ ngân sách qua lượt chọn; hỗ trợ chọn thứ tự, tên loại hoặc mô tả ngữ nghĩa. Không hạ ngưỡng để ép một ca kiểm thử đạt.
- Neo4j lọc danh sách ID hợp điều kiện trước LIMIT của graph expansion. Trước đó 35 ứng viên graph có thể đều bị loại sau truy vấn, dù tồn tại sản phẩm hợp điều kiện khác.
- Kết quả công khai có semantic score thật nếu có dense hit, graph score theo đóng góp RRF và final score dùng để xếp hạng. Các điểm không phải xác suất; không cộng trực tiếp cosine với RRF. Quan hệ giải thích giữ nguồn anchor thực tế.
- Lưu kết quả sau lượt làm rõ để câu hỏi “tại sao” tham chiếu đúng sản phẩm. Câu hỏi ngoài miền không tự đẻ danh sách sản phẩm, lời mời quay lại nhu cầu trang sức chỉ thêm một lần trong cuộc trò chuyện.
- Narrative tùy chọn nhận thuộc tính/quan hệ đã truy xuất dưới dạng dữ liệu, không nhận quyền ghi hay SQL/Cypher. Danh sách, giá, tồn kho và thứ hạng do code quyết định. Model có tối đa 16 giây trong ngân sách hội thoại 35 giây; lỗi thì giữ câu trả lời có căn cứ, không retry. Qwen nhỏ được giải phóng sau câu trả lời trong profile Windows để nhường RAM.

## Bằng chứng

- `ai-ontology-dialogue-final-tests-20261124.json`: 196 test chạy, 195 đạt, 1 skip cần graph server riêng. Đây là kiểm thử phần mềm, không phải benchmark chất lượng model.
- `graph-eligibility-before-after-20261124.json`: truy vấn read-only trên cùng anchors/catalog; bản trước trả 35 ứng viên nhưng 0 hợp điều kiện, bản mới trả 35/35 hợp điều kiện. Không ghi graph.
- `ai-ontology-semantic-proof-20261124.json`: embedding thật cho mô tả đeo ngón tay xếp nhẫn 0,6008697, vòng tay 0,5058116. Margin khoảng 0,095 chưa đạt 0,10, nên cần hỏi lại. Báo cáo này thuộc bản trước khi thêm làm rõ; các sản phẩm vòng tay trong đó không được tính là tìm đúng nhẫn.
- `ai-ontology-dialogue-live-20261124.json`: **không đạt**, ReadTimeout ở câu đầu, chưa có turn hoàn tất; không retry. Không suy ra chất lượng câu trả lời từ bài này. Lượt startup trước đó ghi nhận warmup SourceUnavailable và semantic_intent_ready=false.
- `ai-ontology-dialogue-unchanged-services-20261124.json`: container nghiệp vụ, frontend, PostgreSQL và index-worker giữ nguyên ID/thời điểm khởi động; 500 sản phẩm, frontend HTTP 200. Không phải full nghiệp vụ UAT.
- Source mới giữ để review, narrative mới tắt mặc định. Runtime được phục hồi về image checkpoint trước lượt ontology vì chưa đạt nghiệm thu; không tuyên bố người dùng đang sử dụng thành công các tính năng mới. Health không thay thế nghiệm thu retrieval hoặc LLM.
- `ai-ontology-dialogue-rollback-result-20261124.json`: image `lumiere-ai-before-ontology:20261124` running/healthy; website, API catalog và AI live đều HTTP 200 sau phục hồi. Không gọi thêm chat/model để lặp nghiệm thu.

## Còn thiếu để nghiệm thu toàn bộ

1. Dữ liệu nhãn Audience/Style/Occasion được người có trách nhiệm xác nhận; không suy diễn quan hệ “cho nữ/thanh lịch” từ tên mẫu hoặc ảnh.
2. Bộ ground truth đủ rộng và người chấm độc lập; Precision/Recall/MRR/nDCG, so sánh ablation và faithfulness trên cùng dữ liệu. Vài câu smoke không chứng minh hiểu mọi cách diễn đạt.
3. Model tự nhiên đủ năng lực cho cả ba role. Customer đang dùng Qwen 0,6B giới hạn tài nguyên; Staff/Admin giữ công cụ nghiệp vụ đã có, chưa nghiệm thu LLM tự nhiên mới cho hai role.
4. VPS/domain, staging/HTTPS, backup/restore và kiểm thử tải/fault đầy đủ. Người dùng chưa thuê VPS. Không thể xác nhận hosting ổn định hoặc triển khai công khai khi chưa có hạ tầng.

## Rollback

Checkpoint nguồn trước lượt này: `161d77e`. Image local trước nâng cấp: `lumiere-ai-before-ontology:20261124`; không ghi đè tag này. Nếu cần phục hồi, tạo overlay riêng chọn image checkpoint, tắt narrative mới rồi chỉ recreate `ai-api` bằng `--no-deps --no-build`; reload nginx sau khi AI healthy. Không restore database vì lượt này không thay dữ liệu. Không dùng reset hard, xóa volume hoặc recreate các dịch vụ nghiệp vụ.
