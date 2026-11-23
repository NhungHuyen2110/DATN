# Customer: hội thoại model thật đã chạy qua website — 23/11/2026

Customer AI trên `http://127.0.0.1:18080` hiện bật **Qwen3 0.6B Q4_K_M** qua Ollama Windows riêng, loopback `127.0.0.1:11435`. Đây là thay đổi AI; không chỉnh nghiệp vụ, Frontend, database, ảnh, mã giảm giá, đăng nhập hoặc VNPAY. Staff/Admin chưa bật model mới và chưa được nghiệm thu hội thoại LLM trong lượt này.

## Vì sao đổi profile model

Qwen 2.5 3B ở lượt trước sinh được câu riêng nhưng timeout qua website, Windows chỉ còn khoảng 60–75 MiB RAM. Bản nhỏ được thử riêng trước: ba câu hoàn tất trong 6,015; 2,297; 2,594 giây (`ai-small-dialogue-probe-20261123.json`). Cùng câu sinh nhật đầu đã dùng với 3B trước đó, nhưng độ dài output/cấu hình khác nhau; không dùng số này để khẳng định model nhỏ thông minh hơn hay tính tốc độ tăng chuẩn hóa.

Model nhỏ được tải một lần vào `.local-tmp/dialogue-small-models` trên D. Cache cũ trên C, embedding model, graph và dữ liệu sản phẩm không thay đổi. [Ollama công bố bản Q4 khoảng 523 MB](https://ollama.com/library/qwen3:0.6b-q4_K_M); resident model trong phép thử thực tế là 665.174.669 byte. Chỉ lưu weights local, không gửi hội thoại tới cloud. Không tải model từ request chat.

## Luồng và giới hạn thời gian

- Câu hội thoại/viết lời chúc/kiến thức gọi model thật, tối đa hai lượt lịch sử. Câu viết lại dùng ngữ cảnh trước đó.
- Kiến thức chọn lọc nếu có được đưa làm nội dung tham khảo cho model; khi model lỗi vẫn dùng fallback đã duyệt. Không gắn nguồn kiến thức vào văn bản model như thể toàn bộ output đã được xác minh.
- Tắt thinking cho profile Qwen3; context 1024, output tối đa 96 token, hai CPU threads. Deadline source 24 giây, HTTP timeout 25 giây, một request đang chạy, cooldown 15 giây. Không tự retry hoặc xếp hàng nhiều request model.
- Giữ model tối đa năm phút sau lượt chat rồi Ollama có thể giải phóng RAM. Lượt sau có thể cần nạp lại; không cam kết mọi lượt đạt thời gian warm-cache đã đo.
- Công cụ tìm kiếm/giá/tồn kho vẫn tính kết quả có cấu trúc trước; model hội thoại không được chọn lại sản phẩm hoặc tự tạo giá. Yêu cầu riêng “không cần tìm sản phẩm” không tạo thẻ sản phẩm và không bỏ qua guard dữ liệu riêng tư.

## Kết quả cuối

`ai-small-dialogue-live-20261123.json`: **3/3 kiểm tra kỹ thuật qua website đạt ngay lần chạy này**, không retry:

| Ca | Kết quả | Thời gian |
|---|---|---|
| Viết lời chúc tốt nghiệp | `local_llm_dialogue`, không sản phẩm | 8,313 giây |
| Viết lại theo ngữ cảnh | `local_llm_dialogue`, giữ chủ đề tốt nghiệp | 3,718 giây |
| Nữ thanh lịch dưới 3 triệu | 3 mẫu thật #24, #75, #96; giá dưới mức yêu cầu, còn hàng | 4,907 giây |

Kiểm tra provider `/api/ps` sau hội thoại xác nhận đúng model nhỏ đang loaded. **Nội dung chưa đạt mọi yêu cầu văn phong:** lượt viết lại vẫn có hai câu và emoji dù người dùng yêu cầu một câu trang trọng. Không coi kiểm tra kỹ thuật 3/3 là chấm điểm chất lượng hoặc chứng minh khả năng hiểu mọi câu hỏi.

`ai-small-dialogue-unchanged-services-20261123.json`: ID/thời điểm khởi động Backend, Frontend, PostgreSQL, worker không đổi; vẫn 500 sản phẩm, VNPAY vẫn enabled. Không dùng điều này để khẳng định đã chạy lại toàn bộ nghiệp vụ.

`ai-small-dialogue-tests-20261123.json`: 163 chạy, 162 đạt/1 skip cần graph server riêng, trước chỉnh guard cuối. `ai-small-dialogue-final-unit-20261123.json`: 10 ca lớp hội thoại cuối đều đạt, gồm source tham khảo, tắt thinking, timeout, request trùng, bảo vệ dữ liệu riêng tư và nhận diện giá với ký hiệu ₫. Không tải/gọi model trong unit tests.

## Bật lại sau khi tắt máy

Chạy `AI/start-local-dialogue.ps1` trong PowerShell để mở provider ẩn với cache D đã chuẩn bị. Script không tải model, không tự thêm process nếu port đã có Ollama và không cấu hình tự khởi động Windows. Nếu cache chưa có model cần chuẩn bị riêng, không download trong API.

Compose phục vụ Customer cần thêm overlay `compose.customer-dialogue-host.yaml` vào chuỗi file hiện có; giữ cả `compose.payments-local.yaml` khi dùng cấu hình commerce hiện tại. Chỉ `up -d --no-deps ai-api` nếu cần cập nhật AI; không recreate các service khác. Không chạy lại image 3B hoặc bật `compose.dialogue.yaml` cho toàn stack trên máy 8 GB này.

## Chưa hoàn thành và rollback

Model 0.6B có giới hạn ngôn ngữ và khả năng làm theo hướng dẫn; chưa tương đương ChatGPT, chưa có benchmark tiếng Việt/faithfulness có người chấm. Search smoke vẫn `degraded`, chưa chứng minh dense+graph hoạt động đầy đủ. Dữ liệu chưa có nhãn phong cách/đối tượng đã xác nhận cho mỗi sản phẩm nên không khẳng định các mẫu tham khảo đã đạt nhãn. Staff/Admin LLM và public staging/hosting vẫn chưa nghiệm thu.

Rollback: giữ image `lumiere-ai-before-small-dialogue:20261123` (bản ổn định d4a1d6f). Tắt `LUMIERE_CUSTOMER_DIALOGUE_ENABLED`, pin riêng `ai-api.image` về image này bằng override, chạy `up -d --no-build --no-deps ai-api` và reload nginx. Chỉ dừng PID provider do chính helper khởi động sau khi đối chiếu path/process; không dừng Ollama hoặc ứng dụng khác của người dùng, không xóa cache/volumes. Không rollback database.
