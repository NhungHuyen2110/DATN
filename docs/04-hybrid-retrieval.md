# Luồng tìm kiếm mới đã nối vào chatbot

Đã có code tích hợp và test offline; chưa có benchmark chất lượng model do người gán nhãn. Unit test không phải Precision/Recall thực nghiệm.

## Hành vi hiện tại

| Bạn hỏi / tình huống | Code xử lý |
|---|---|
| `Top 1 nhẫn dưới 8 triệu` | Category=ring, K=1, giá <8.000.000; xác minh giá/tồn kho bằng Business API |
| `nhan duoi 8,5 trieu` | Nhận câu không dấu và ngân sách thập phân |
| `nhẫn cho phái nữ / phụ nữ / con gái` | Cùng canonical Audience=female; catalog chưa có Audience được xác minh nên thông báo thiếu thuộc tính, không tự gán giới tính cho sản phẩm |
| `nhẫn cho con gái 8 tuổi` | Nhận đối tượng trẻ em, không gộp thành nữ trưởng thành |
| `nhẫn tinh tế` và `nhẫn tối giản` | Không tự coi hai phong cách là cùng một fact |
| Qdrant hoặc Neo4j lỗi | Dùng nguồn còn hoạt động và báo giảm khả năng tìm kiếm; không bịa semantic score hoặc graph path |
| Business API lỗi | Không trả snapshot giá/kho cũ như thể vẫn bán được |
| Ollama lỗi | Luồng mới vẫn trả câu trả lời deterministic từ danh sách đã kiểm tra |

## Code thực thi

- `AI/config/aliases_vi.json`: alias/canonical ID có version; ID Category/Gemstone theo taxonomy thật.
- `jewelry_agents/entity_linking.py`: Unicode/không dấu/ranh giới từ/ngữ cảnh tuổi/ambiguity/evidence. Có đường nhận encoder sẵn có để tính cosine và threshold/margin; **semantic alias này chưa bật trong chat và chưa hiệu chỉnh trên model thật**. Không merge node bằng cosine.
- `jewelry_agents/search_service.py`: K trong câu hỏi, hard constraints, dense + lexical + graph. Tập ID hợp lệ từ catalog được truyền vào Qdrant filter **trước dense retrieval**, tránh lấy toàn ứng viên vượt ngân sách rồi mất semantic contribution. Catalog được đọc lại sau ranking trước khi trả kết quả. Lexical là token-overlap, **chưa phải BM25**.
- `jewelry_agents/ranking.py`: RRF `sum(1/(60+rank))`, dedup ID, deterministic tie-break, kiểm tra lại giá/tồn kho và Top-K. Không cộng trực tiếp cosine với lexical/graph score.
- `jewelry_agents/business_catalog.py`: GET public catalog có phân trang/timeout; giữ giá chính xác. Chưa có cache/outbox nên mỗi query cần đọc catalog.
- `jewelry_agents/retrieval.py`: khởi tạo dịch vụ khi cần, model chỉ dùng cache local; collection versioned phải khớp model revision/dimension. Graph candidates có evidence từ query thật.
- `rag/rag_service.py`: luồng mới bật mặc định, giữ `success/answer/products`; không trả score nội bộ ra Customer. Câu trả lời giữ nguyên danh sách, thứ tự và giá.
- `knowledge_graph/graph_recommendation.py`: shared Category/Material/Gemstone qua hai cạnh, trả source/candidate/shared-attribute evidence. Query còn cần integration recommendation trên server.
- `hybrid_recommendation_v2.py`: giữ nguồn score hiện hữu, tie-break ổn định, đối soát lại live name/price/stock, giữ GraphEvidence. Trọng số heuristic cũ chưa được tuning khoa học.
- `api.py`: load recommendation modules/CSV khi dùng; lỗi dependency trả 503; `/health/live` không gọi model/DB. `/health/ready` kiểm tra Business catalog, các nguồn AI khác optional.

## Smoke bằng model thật

`real-model-retrieval-filtered.json` và `real-model-filtered-verification.json`: model cached multilingual MiniLM, revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, **384 chiều**, COSINE; index 500 bản ghi vào Qdrant in-memory, đọc Neo4j test thật, không download model.

- `Top 3 nhẫn dưới 8 triệu`: IDs **79,87,114**, đúng K/Category/giá/kho của CSV seed và dense có contribution trong cả ba kết quả.
- `Top 1 bông tai moissanite`: ID **1**, đúng K/Category/Gemstone/kho của CSV seed, dense có contribution.

Catalog provider của bài smoke là **CSV seed fixture, không phải Business API live**; các test API/adapter/giá đổi giữa request được kiểm chứng riêng bằng TestClient/test doubles. Không coi hai câu này là benchmark relevance, không có kết luận Precision/Recall hoặc phần trăm cải thiện. Thời gian 119.92s trong report gồm load model + encode/index toàn 500 sản phẩm + hai query trên CPU giới hạn 2 thread; **không phải latency request p95**. Report cũ trước prefilter giữ lại để giải thích phát hiện mất dense contribution, không dùng làm ablation khoa học.

## Chạy và rollback

```powershell
$env:TEMP='D:\LUMIERE-FINAL-TEST\.local-tmp'
$env:TMP=$env:TEMP
python -B scripts/run_ai_tests.py

# Khởi động bằng interpreter đã cài đủ dependencies:
$env:BUSINESS_API_URL='http://127.0.0.1:8001'
$env:LUMIERE_RETRIEVAL_V2_ENABLED='true'
Set-Location AI
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Chưa tự restart AI service đang phục vụ người dùng. Code mới có hiệu lực khi tiến trình nạp source mới. Khi container hóa, BUSINESS_API_URL phải dùng service DNS.

Rollback chat tạm bằng `LUMIERE_RETRIEVAL_V2_ENABLED=false` và restart AI. Đường legacy còn lỗi trong audit, nên không coi đó là đường đã sửa hoàn toàn. Checkpoint source: `.local-tmp/checkpoints/graph-writer-20261118/`; chỉ restore đúng file AI sau khi so diff. Không rollback thay đổi backend/frontend của người dùng hoặc xóa DB/volume.

## Chưa hoàn thành

Nhận diện Audience/Style intent chưa đồng nghĩa có fact Product→Audience/Style. Cần nguồn thuộc tính có bằng chứng trước khi đáp ứng demo đó. Có graph-feature reranker opt-in, outbox và 5-mode ablation smoke; chưa cross-encoder/human quality benchmark hoặc container fault evidence. Xem trạng thái hiện tại tại `12-acceptance-status.md`; chưa đóng toàn bộ gate PHASE 3–5.

## Public recommendation và quyền riêng tư

Mặc định `/recommendations` và `/recommendations/v2` dùng `jewelry_agents/public_recommendation.py`, gợi ý item-to-item từ public catalog, dense, actual graph paths và RRF. Không import module cũ đọc Order/Customer CSV; `customer_id` giữ trong contract nhưng không dùng làm quyền truy cập hoặc cá nhân hóa. Response thêm `personalized:false`. Cả hai endpoint giữ `data` và các field ProductID/ProductName/SalePrice/Stock cho frontend, tối đa 20 khi có đủ candidates.

Giá/tồn kho và reference taxonomy được re-read sau retrieval; paths stale bị loại. Dense/graph lỗi fallback structured public attributes, không giả semantic/graph evidence. Thay `LUMIERE_PUBLIC_RECOMMENDATIONS_V2_ENABLED=false` chỉ dùng cho legacy compatibility đã review, không khuyến nghị vì nhánh cũ thiếu ownership guard và cần CSV orders/model eager load. Chưa xây authenticated personalization dựa trên lịch sử người dùng thật.
