# Cô lập startup và nghiệm thu lại AI — 24/11/2026

**Trạng thái bàn giao lượt này: code checkpoint `698bd33`, 204/205 test đạt, 1 skip. Chưa đạt nghiệm thu tổng thể. AI container đang cố ý dừng để bảo vệ nghiệp vụ trong lúc thiếu RAM; không phải bản AI mới đã được bật thành công.** Website/catalog/VNPAY đã phục hồi sau khi dừng riêng AI; xem báo cáo recovery bên dưới. Chờ người dùng xác nhận xử lý dịch vụ Windows ngoài dự án trước khi thử inference tiếp; không chạy lại cold-start liên tục.

## Vấn đề và phạm vi sửa

Bản ontology/context trước đạt unit tests nhưng bị ReadTimeout khi gọi chat, trong khi semantic_intent_ready vẫn false. Snapshot đầu lượt này: Windows còn 867.760 KiB RAM trống, Docker khoảng 4 GB, AI khoảng 740 MB; Ollama không có model đang giữ. Đây là snapshot tài nguyên, chưa chứng minh mọi timeout đều do RAM.

Đọc code cho thấy một tình huống cạnh tranh model: warmup embedding chạy trong worker SourceGate; khi caller timeout, worker vẫn tiếp tục. Nếu gửi câu chưa có alias lúc ấy, intent embedding có thể không sẵn sàng và hội thoại rơi sang LLM. Qwen khi đó được nạp trong lúc embedding đang nạp. Không tăng timeout của câu trả lời hoặc nới điều kiện test để che lỗi.

Thay đổi chỉ ở AI và script kiểm thử AI:

- Worker warmup giữ cờ warming đến khi công việc thực sự kết thúc, kể cả caller đã timeout. Cờ không được xóa ở nhánh caller timeout.
- Không nạp Qwen khi cờ warming còn bật. Tránh cạnh tranh hai model trong giai đoạn cold start. Không dừng database hoặc các dịch vụ khác để làm test đạt.
- `GET /health/semantic` chỉ đọc trạng thái in-memory, không load model hoặc gọi catalog. HTTP 503 nếu chưa sẵn sàng, 200 khi ready. Không đổi ý nghĩa `/health/live` hoặc readiness nghiệp vụ hiện có.
- Ghi stage và thời gian startup, không ghi câu hỏi, token hay credential vào log.
- Bài nghiệm thu chờ trạng thái semantic tối đa 180 giây rồi chạy hữu hạn các turn. Turn chat không retry. Kiểm tra thật category, giá/tồn kho từ Business API, quan hệ HAS_GEMSTONE từ Neo4j và response_mode của LLM; fallback không được tính là natural generation thành công.

## Kiểm thử

`ai-startup-isolation-tests-20261124.json`: 198 chạy, 197 đạt, 1 skip yêu cầu graph server riêng. Test mới mô phỏng caller timeout nhưng worker còn sống, xác nhận không gửi HTTP tới Ollama; khi worker thực sự xong mới clear warming. Endpoint semantic không tải model/catalog. Không gọi model/server thật trong unit tests.

Lệnh PowerShell nghiệm thu bản candidate local:

```powershell
D:\JewelryDatasetGenerator\.venv\Scripts\python.exe -B AI/evaluation/semantic_rag_smoke.py --startup-wait-seconds 180 --require-natural --report docs/ai-startup-isolation-live-20261124.json
```

Image candidate `lumiere-ai-startup-isolation:20261124`; chỉ `ai-api` được build/recreate và nginx reload. Candidate bật narrative để nghiệm thu. Image rollback `lumiere-ai-before-ontology:20261124` giữ nguyên. Kết quả live và đối chiếu dịch vụ được bổ sung sau khi lệnh kết thúc; không tính unit tests là điểm thông minh.

Lượt đầu `ai-startup-isolation-live-20261124.json` đã hết ReadTimeout: startup 46,315 giây; làm rõ 0,375 giây; trả đúng loại nhẫn sau lựa chọn trong 6,86 giây. Chưa đạt vì graph expansion timeout và chỉ dùng dense/lexical. Dừng ở assertion đó, chưa chạy các ca sau. Chẩn đoán riêng `ai-startup-graph-diagnostic-20261124.json` xác nhận graph taxonomy có trả kết quả nhưng expansion timeout, tổng graph 4,262 giây; không đổi báo cáo lỗi thành đạt.

Sửa tiếp đúng lỗi này: nếu đã có dense anchors thì chạy expansion trực tiếp, không gọi taxonomy lookup dư thừa trước đó. Khi không có anchors hoặc truy vấn reference rõ ràng, giữ adapter graph lookup tương ứng. Startup chuẩn bị kết nối và câu traversal tham số hóa bằng một lần đọc graph, với anchor thật và candidate chỉ là chính anchor (bị loại bởi điều kiện khác ID), không ghi graph hoặc dùng kết quả warmup như đáp án. Ngân sách nguồn graph trong request vẫn giữ nguyên.

Lượt `ai-startup-graph-live-20261124.json`: startup 96,544 giây, hỏi làm rõ 4,797 giây; lượt chọn loại gặp catalog_unavailable sau 5,11 giây. Chưa đạt, không có bằng chứng natural từ lượt này. Cả hai lần smoke dừng ở lỗi đầu tiên và không retry turn.

Sửa tiếp catalog: 500 sản phẩm được chia 5 trang100; sau trang đầu biết tổng số, AI đọc phần còn lại với tối đa 2 HTTP GET đồng thời bằng session riêng. Không đổi Business API, không tăng timeout nguồn 4 giây, không dùng cache cũ hay kết quả không đủ trang. Kiểm tra tổng số nhất quán, IDs duy nhất và số bản ghi từng trang; vẫn đọc lại dữ liệu nghiệp vụ ở bước final verification. Khi nguồn đổi hoặc lỗi, từ chối snapshot. `ai-startup-catalog-verified-tests-20261124.json`: **201 chạy, 200 đạt/1 skip**; gồm test giới hạn concurrency=2, đủ500 IDs, không retry trang, từ chối trang thiếu/trùng/tổng số thay đổi.

Lượt `ai-startup-catalog-live-20261124.json` chưa đạt: model nạp xong ở 62,152 giây nhưng startup caller timeout60 đã mở circuit cooldown15. Cờ encoder-ready chưa phản ánh admission của nguồn, nên lượt chat sớm chỉ dùng lexical và chọn sai loại. Không tính sản phẩm sai loại là semantic thành công. Đây là lỗi readiness có thể tái hiện từ trạng thái worker, không chỉ là giả thuyết thiếu RAM.

Bản cuối thêm `SourceGate.availability()` đọc trạng thái busy/cooldown, không thay hành vi của nguồn hoặc backend; `/health/semantic` và semantic_intent_ready chỉ báo ready khi embedding worker hoàn tất và nguồn được phép nhận truy vấn. Script chờ cả admission graph, không coi admission là kiểm tra kết nối database. Startup background có ngân sách120 giây theo thời gian cold start đã đo; timeout chat/retrieval không tăng. Khi model còn nạp, câu chưa xác định loại không được rơi xuống danh sách lexical tùy ý. `ai-startup-final-verified-tests-20261124.json`: **204 chạy, 203 đạt/1 skip**, gồm kiểm tra lỗi báo ready sớm và chặn chọn sai sản phẩm trong startup.

Build Dockerfile bình thường của lượt catalog bị Docker Hub TLS handshake timeout. Đã dùng image dependency local đã build cùng lượt này, COPY source AI/shared để tạo `lumiere-ai-startup-catalog:20261124`, không đổi thư viện/model. Các image checkpoint vẫn giữ; chỉ AI được recreate. Kết quả cuối nằm ở `ai-startup-final-live-20261124.json`, không ghi đè các lần lỗi.

Lượt `ai-startup-final-live-20261124.json` chứng minh readiness không báo sớm dù worker xong sau120 giây: chờ nguồn ra cooldown rồi mới chat. Câu lạ được làm rõ trong1,375 giây; sau lựa chọn, trả đúng 3 nhẫn dưới3 triệu có dense/graph/lexical và quan hệ thật trong18,547 giây (gồm thử narrative nhưng fallback). Phần graph-reference chưa đạt vì `product_dialogue` nhận nhầm ID catalog là số thứ tự thẻ. Không tính smoke tổng thể này là thành công.

Đã sửa lỗi định tuyến đó bằng `reference_request()` hiện có, trước xử lý hội thoại về thẻ; truy vấn “cùng loại đá/chất liệu/danh mục” phải đi tới graph kể cả chưa có lịch sử chat. Kiểm thử lịch sử có/không có thẻ, cùng các guard riêng tư vẫn đạt. Rút phần bằng chứng gửi model xuống1 path thật/mẫu (không đổi metadata trả cho ứng dụng); giảm microbatch prefill xuống32. Narrative dùng cùng trần24 giây như hội thoại, vẫn trong ngân sách tổng35 giây, không đổi HTTP timeout hay retry. `ai-graph-reference-release-tests-20261124.json`: **205 chạy, 204 đạt/1 skip**. Kết quả lượt nghiệm thu sau sửa được giữ riêng ở `ai-graph-reference-release-live-20261124.json`.

Lượt `ai-graph-reference-release-live-20261124.json` dừng đúng180 giây chờ startup, không gửi turn chat nào: nguồn chưa ready, không giả vờ semantic hoạt động. Một lần đọc sau đó ở `ai-graph-reference-serving-state-20261124.json` ghi nhận load_encoder mất357,841 giây trước khi vào intent_vectors. Đây là thất bại nghiệm thu resource/startup, không phải bằng chứng câu trả lời graph/natural đã đạt.

Đo Windows lúc điều tra tiếp: RAM tổng8.077.608 KiB, RAM trống152.784 KiB (~149 MiB); Memory Compression resident khoảng3.580 MiB. Dịch vụ ngoài dự án DtsApo4Service giữ private khoảng1.585 MiB, hai SQL Server tổng khoảng944 MiB và MongoDB365 MiB. Private memory không đồng nghĩa toàn bộ là RAM vật lý có thể thu hồi ngay. Chưa tự dừng những dịch vụ này. Đã yêu cầu người dùng xác nhận riêng nếu muốn khởi động lại DTS vì ngoài phạm vi ứng dụng. Không tự tăng giới hạn kiểm thử, không restart AI thêm để lặp cold start trong lúc thiếu tài nguyên.

## Bảo toàn nghiệp vụ khi thiếu tài nguyên

`ai-startup-business-compatibility-20261124.json` chưa đạt: catalog HTTP503; VNPAY và frontend200, Admin/Staff vẫn từ chối ẩn danh. Không khẳng định không có ảnh hưởng runtime chỉ vì không sửa code nghiệp vụ.

`ai-resource-pressure-containers-20261124.json`: Frontend/Business/PostgreSQL giữ nguyên ID, thời điểm khởi động, restart_count0. Worker đồng bộ cùng ID nhưng tự restart3 lần; không có bằng chứng OOMKilled trong snapshot này, không tự quy toàn bộ sự cố cho OOM. Chưa chứng minh nguyên nhân chi tiết từng lần worker thoát.

Đã tạm dừng đúng `lumiere-rebuild-test-ai-api-1`, không dừng hay xóa database/volume. `ai-resource-isolation-recovery-20261124.json` đạt: frontend200, catalog200/500 sản phẩm, payment-methods200/VNPAY enabled. Đây là smoke read-only, không thay full checkout/payment UAT. Không stop dịch vụ SQL Server/MongoDB/DTS ngoài dự án khi chưa được người dùng cho phép.

Sau khi đủ tài nguyên, có thể start lại chính container AI hiện có (source đã kiểm thử), không rebuild toàn stack. Reload proxy nếu cần, kiểm tra `/ai/health/semantic` rồi chạy một smoke mới với đường dẫn report chưa tồn tại. Không đổi các báo cáo thất bại thành đạt; giữ narrative mặc định trong source tắt cho đến khi có live acceptance. Profile candidate local hiện có narrative bật để nghiệm thu, nhưng container đang dừng.

## Giới hạn nghiệm thu

Một luồng smoke thành công không chứng minh tất cả câu hỏi tiếng Việt, độ đúng mọi lời tư vấn, Staff/Admin LLM hoặc tải nhiều người dùng. Nhãn đối tượng/phong cách có căn cứ, benchmark người chấm và VPS/staging vẫn là các gate độc lập. Không thay model/collection, không tải model mới, không đổi auth/checkout/thanh toán hoặc dữ liệu.
