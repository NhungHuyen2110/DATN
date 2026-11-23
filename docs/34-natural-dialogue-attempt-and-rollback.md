# Lớp hội thoại model thật — chưa nghiệm thu, đã rollback local

Ngày 23/11/2026. Mục tiêu là bật hội thoại tự nhiên bằng model hiện có, không sửa chức năng bán hàng. **Chưa hoàn thành yêu cầu bật model qua website.** Không xem unit tests hoặc chạy model riêng là bằng chứng hoàn thành.

## Code đã bổ sung

- `AI/rag/natural_dialogue.py`: adapter Customer Qwen local, tối đa một lượt đang chạy, deadline 38 giây, HTTP timeout 39 giây, cooldown, không retry, không tải model, không URL cloud/proxy/redirect. Context 1024, output 80 token; output bị cắt chỉ dùng phần có câu hoàn chỉnh. Chặn URL và giá cửa hàng do model tự sinh. Đây không phải bộ xác minh sự thật tổng quát.
- Customer conversation gọi model cho hội thoại/kiến thức, giữ nguyên công cụ giá/tồn kho và budget followup. Có lịch sử giới hạn và yêu cầu viết lại theo ngữ cảnh. Lỗi model quay lại nội dung đã chọn lọc hoặc hỏi làm rõ; không sinh thẻ sản phẩm cho câu hỏi kiến thức.
- `AI/start-local-dialogue.ps1`: khởi động Ollama Windows đã cài bằng cửa sổ ẩn, chỉ nghe loopback 11435, log/TEMP trên D, dùng weights có sẵn. Không tải model hoặc tự chạy lại. Đây là helper tùy chọn, **không tự chạy khi khởi động máy**.
- `compose.customer-dialogue-host.yaml`: overlay tùy chọn cho riêng AI, không đổi Backend/Frontend. Mặc định không có overlay này thì adapter mới tắt. **Không bật overlay này trên máy hiện tại trước khi giải quyết tài nguyên và nghiệm thu lại.**

## Kết quả thật

1. Docker VM báo 4.021.063.680 byte RAM, Windows tổng khoảng 8 GB. Ollama container cũ giữ nguyên trạng thái dừng.
2. Chạy Qwen 2.5 3B đã có sẵn bằng Ollama Windows thành công: sinh 53 token trong tổng 37,437 giây, load khoảng 14 giây. Nội dung test được lưu riêng tại `.local-tmp/host-dialogue-probe-20261123.json`. Câu chữ chưa tốt; đây chỉ là kiểm chứng có generation thật, không phải đạt chất lượng tư vấn.
3. Kết nối từ AI container tới `host.docker.internal:11435/api/tags` thành công. Không tải model hoặc gửi dữ liệu tới bên ngoài.
4. Deploy AI gặp startup health timeout 55 giây; kiểm tra sau đó service báo healthy. Một startup provider với thông số mặc định bị timeout; sửa sang đúng profile hai luồng đã đo thì startup hoàn tất sau 29,859 giây. Giữ cả hai kết quả riêng, không che lần lỗi.
5. **`ai-natural-dialogue-live-20261123.json`: chưa đạt, ReadTimeout ngay request website đầu tiên, chưa có lượt trả lời thành công.** Dừng bài nghiệm thu, không retry cùng bài, không tự tăng timeout. Không chạy tiếp hai ca còn lại.
6. Snapshot Windows sau đó chỉ còn 76.292 KiB RAM vật lý khả dụng. Đây là bằng chứng thiếu tài nguyên tại thời điểm thử, chưa phải benchmark xác định duy nhất nguyên nhân lỗi.
7. Đã dừng cây tiến trình Ollama do lượt này khởi động, rollback riêng AI về image `lumiere-ai-before-natural:20261123` (bản sửa ngân sách d4a1d6f), tắt cờ Customer model và reload DNS nginx. Không restart Backend/Frontend/PostgreSQL/worker, không đổi database hay thanh toán. Code chuẩn bị còn ở source, model không được bật trên bản local bàn giao.

## Kiểm thử code

- `ai-natural-dialogue-tests-20261123.json`: 161 chạy, 160 đạt/1 skip cần graph server riêng; không dùng model/DB/server thật.
- `ai-natural-dialogue-final-unit-20261123.json`: 7 ca adapter/coordinator cuối đạt; bao gồm viết lại với context, timeout một lần, URL local, loại output không hợp lệ, không gắn nguồn GIA vào văn bản model chưa kiểm chứng, chặn lượt gửi trùng.
- `ai-natural-dialogue-unchanged-services-20261123.json`: trước rollback, ID và thời điểm khởi động các service ngoài AI không đổi. Kết quả kiểm tra phục hồi được ghi riêng khi thực hiện.
- `ai-natural-dialogue-recovery-20261123.json`: website/Business HTTP 200; AI proxy timeout trước reload, nhưng inspect xác nhận image rollback đã running/healthy. CLI Compose rollback vượt 75 giây; không xem CLI timeout là bằng chứng container chưa đổi.
- **`ai-natural-dialogue-restored-20261123.json`: phục hồi đạt**, reload nginx exit 0, AI health HTTP 200 và chat chào hỏi thành công. Không chạy lại bài model sau phục hồi. Các sửa ngân sách trước lượt này còn trên runtime rollback.

## Điều kiện còn thiếu

Cần môi trường đủ tài nguyên để chạy LLM đồng thời với stack hiện tại hoặc một provider được người dùng chọn và cấp quyền. Chưa có VPS/provider mới; không mua dịch vụ, không xin hoặc công khai API key trong chat. Trước khi bật: phải có câu trả lời model thật qua website, giữ ngữ cảnh, kiểm tra timeout/fallback, chất lượng tiếng Việt và việc không bịa dữ liệu. Staff/Admin không bị đổi trong lượt này; khả năng hội thoại model của hai role đó vẫn chưa nghiệm thu. Không gọi bản hiện tại là AI hoàn thiện hoặc tương đương ChatGPT.
