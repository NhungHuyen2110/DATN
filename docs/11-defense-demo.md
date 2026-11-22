# Kịch bản demo và trả lời phản biện

Chỉ dùng môi trường test đã khởi động/seed/index và đối soát. Báo cáo test không chứng minh browser hiện tại đã nạp source mới. Không mở `.env`, password/token thật, Customer/Order dump trước hội đồng.

## Demo 10–15 phút

1. Giới thiệu vấn đề và AS-IS/TO-BE từ `00-audit-as-is.md` (2 phút). Phân biệt cấu hình mục tiêu với dịch vụ đã chạy được.
2. Chạy dry-run importer CSV, xem kiểm tra 500 bản ghi và báo cáo hai lần import Neo4j (2 phút). Không chạy lại import vào graph đang dùng. Chỉ ra node Product, năm loại taxonomy và cạnh có nguồn, stable ID và constraints.
3. Tìm `Top 3 nhẫn dưới 8 triệu`; xem số lượng, thứ tự, giá/tồn kho nguồn bán hàng (2 phút). Xem `live-business-model-graph-retrieval-20261121.json`: Business HTTP/PostgreSQL test 500 CSV-seeded products, model thật và graph thật, thay giá/tồn kho giữa query vẫn loại candidate cũ. Không gọi là accuracy benchmark.
4. Cho xem alias linking `nhẫn cho phái nữ`, `nhẫn cho con gái`, `mua nhẫn tặng con gái 8 tuổi` (2 phút). Giải thích canonical Audience nhận diện từ query khác với quan hệ Audience của sản phẩm. Hiện thiếu fact Audience/Style nên trả clarification/missing attributes; không diễn kết quả giả cho ba demo bắt buộc chưa nghiệm thu.
5. Recommendation: xem path shared Category/Material/Gemstone và kiểm tra endpoint/giá/tồn kho live (2 phút). Không tuyên bố có path “cùng phong cách” khi chưa có fact Style.
6. Xem native fault report: dừng đúng AI test process thật, Business catalog/login/COD vẫn đạt rồi AI phục hồi (2 phút). Docker chưa chạy được, không gọi đây là container fault test. Chỉ chạy container fault script sau khi xác nhận project test.
7. Xem screenshot Grafana từ Prometheus scrape 2 source API thật, queue exporter và backup/restore report; chỉ ra checklist còn thiếu (1 phút). Không suy diễn ảnh native thành monitoring container đã deploy.

## Câu hỏi thường gặp

**RAG có phải database?** Không. Đây là luồng truy xuất bằng chứng rồi tạo câu trả lời. PostgreSQL là nguồn nghiệp vụ, Qdrant là index vector, Neo4j là projection quan hệ. Luồng mới tạo narrative deterministic từ sản phẩm đã xác minh; Ollama/CrewAI chỉ còn nhánh tương thích legacy, không tuyên bố LLM generation đã được benchmark.

**Vector 384 chiều có phải cosine?** 384 là số thành phần của embedding đã dùng; cosine là thước đo hướng giữa vector. Collection phải khớp model/revision/dimension/distance; thay model phải index collection theo version, không trộn vector.

**Hybrid xếp hạng thế nào?** Các danh sách dense/lexical/graph được hợp nhất bằng reciprocal rank fusion `sum(1/(60+rank))`, không cộng raw cosine với điểm graph khác thang. Bước cuối xác minh lại source bán hàng và ràng buộc. Score là điểm thuật toán, không phải xác suất người dùng thích sản phẩm. Cross-encoder chưa được triển khai/đánh giá.

**Vì sao không trả đủ K trong mọi câu?** Chỉ trả tối đa K sản phẩm còn hợp lệ. Nếu không đủ hoặc thiếu thuộc tính có bằng chứng, phải báo rõ thay vì thêm sản phẩm sai điều kiện. Chất lượng relevance cần đánh giá riêng bằng nhãn người review.

**Node khác relationship?** Product/Category/Material/Gemstone/Brand/Collection là thực thể có ID ổn định; cạnh mang ý nghĩa và chiều liên kết. Import bằng parameterized UNWIND/MERGE, không nhập thủ công hay dùng tên hiển thị làm định danh.

**Dữ liệu đồng bộ có nhất quán tức thì?** Transaction nghiệp vụ và outbox là một transaction PostgreSQL. Delivery sang graph/vector là at-least-once có retry, lease, generation, repair và reconciliation; không có transaction phân tán hoặc exactly-once. Giá/tồn kho phải xác minh lại từ Business API.

**Tách container có hết phụ thuộc?** Không. AI chết có thể giữ business, nhưng PostgreSQL chết thì các thao tác cần DB phải lỗi an toàn. Cô lập service chỉ là cấu trúc; cần fault test và báo cáo phục hồi thực tế.

**Có chứng minh cải thiện chất lượng chưa?** Chưa. Đã chạy 5-mode smoke 525 predictions, có latency chart nhưng chưa kiểm soát tải. 105 câu nháp chưa human review, chưa có quality metrics đủ kết luận cải thiện. Reranker graph-feature chỉ opt-in, chưa tuning; không gọi là cross-encoder.

**Có hoàn tất bảo mật/hosting chưa?** Chưa public deploy. Role tests và Chrome đã chạy, metrics protected. Restore synthetic fixtures đã đạt; HTTPS, production backup/secrets, rate limits theo tải và approval vẫn là gate trước vận hành.
