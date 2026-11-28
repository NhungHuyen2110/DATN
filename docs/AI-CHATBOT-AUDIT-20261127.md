# Báo cáo kiểm toán AI Chatbot LUMIÈRE

Ngày kiểm toán: 27/11/2026, múi giờ Asia/Bangkok. Phạm vi: Customer, Staff, Admin tại `D:\LUMIERE-FINAL-TEST`, mã nguồn và hệ thống Docker đang chạy qua `http://127.0.0.1:18080`.

Đây là kết quả kiểm toán chỉ đọc. Không sửa mã ứng dụng, Compose, feature flags, dữ liệu nghiệp vụ, ontology hoặc index; không rebuild, restart, reset, xóa volume, commit hay push. Thay đổi duy nhất trong repository của đợt kiểm toán là báo cáo này. Các lần chat chỉ tạo state hội thoại riêng trong RAM; kiểm thử offline dùng dữ liệu tổng hợp trong bộ nhớ.

## 1 Executive summary

**Hệ thống có nền tảng retrieval và công cụ nghiệp vụ thực, nhưng chưa đủ bằng chứng để công nhận chatbot AI hoàn thiện cho cả ba vai trò.** Customer tìm kiếm có ràng buộc và tạo câu trả lời từ dữ liệu thật khá rõ ràng; khả năng hiểu diễn đạt tự nhiên và điều khiển hội thoại còn hạn chế. Staff/Admin chủ yếu là bộ định tuyến rule tới các công cụ PostgreSQL, có một số cơ chế hội thoại chung; chưa phải trợ lý phân tích nghiệp vụ tổng quát.

Các phát hiện chính, xếp theo mức ảnh hưởng:

| Mã | Mức | Kết luận và bằng chứng |
| --- | --- | --- |
| F01 | Cao | Staff trả **tổng 17 đơn** khi hỏi đơn **đã hủy** hoặc **đang giao**, trong khi dashboard có lần lượt **1** và **1**. Nhánh mặc định `understand_staff_question()` chọn `total_orders` khi không nhận ra trạng thái. |
| F02 | Cao | Admin hỏi **doanh thu quý 3/2026** nhưng nhận số liệu **tháng 11/2026**; hỏi so sánh tháng 9 và 10 chỉ nhận tháng 9. `understand_revenue_question()` không kiểm tra đầy đủ phạm vi thời gian và hành động so sánh. |
| F03 | Cao | `LUMIERE_SEMANTIC_PRICE_ENABLED=false` không bảo đảm không gọi LLM giá: nhánh DST truyền `enabled=True` vào `infer_price_preference()`. Đã xác minh bằng mô phỏng lời gọi trên mã trong container, giữ nguyên biến môi trường. |
| F04 | Cao | Runtime và checkout khác nhau: 3 file AI khác hash; 4 module điều phối semantic mới có trên đĩa nhưng không có trong image. Test checkout không chứng minh image hiện chạy có cùng hành vi. |
| F05 | Cao | PostgreSQL/Business API: **501** sản phẩm; Neo4j/Qdrant: **500**. Thiếu ID **501**, Neo4j lệch tồn kho ID **1, 19, 488**. Có **5 job pending**, không có index-worker đang chạy. |
| F06 | Cao về trải nghiệm | Chuỗi Customer “nhẫn dưới 5 triệu” → “còn vòng đeo tay” → “tôi muốn đổi sản phẩm” → “đổi nhu cầu khác” tái hiện vòng lặp cùng một câu làm rõ. Một lượt mất **21,381 giây**. |
| F07 | Trung bình | Staff không hiểu “sắp hết” sau báo cáo tồn kho; Admin không hiểu “tháng 9 thì sao?” sau top bán chạy. State chung lưu lịch sử/kết quả nhưng không có bộ kế thừa task và slot nghiệp vụ đầy đủ. |
| F08 | Trung bình | AI offline: **281 test, 1 failure, 1 skip**. Failure quản lý timeout tiến trình host tái hiện khi chạy riêng. Backend offline: **690 passed**, thêm **845 subtests passed**. Không được báo toàn bộ test PASS. |
| F09 | Trung bình | Bộ đánh giá có **105 câu draft, 0 câu được human review**. Chưa có kết quả đáng tin cậy về accuracy/F1 NLU, DST joint accuracy, Recall@K hay nDCG trên bộ nhãn độc lập. |

Những phần có bằng chứng tốt để giữ lại: kiểm tra quyền ở backend; công cụ nghiệp vụ chỉ đọc và dùng ORM; reuse quy tắc doanh thu dashboard; live verification giá/tồn kho; RRF; kiểm tra graph paths; trả `degraded` khi nguồn tùy chọn gián đoạn; cơ chế SourceGate giới hạn single-flight và cooldown.

Kết luận dành cho đồ án: có thể trình bày trung thực là **hệ thống tư vấn trang sức có hybrid retrieval và công cụ thống kê theo vai trò, với hội thoại có trạng thái trong phạm vi giới hạn**. Chưa nên tuyên bố hiểu ngôn ngữ tự nhiên tổng quát, phân tích khách hàng tự động, hay hội thoại nghiệp vụ đa lượt hoàn chỉnh.

## 2 Môi trường và kiến trúc AI AS IS

### 2.1 Git và nguồn mã đang chạy

- Branch: `update-ai`.
- HEAD: `1a432c170164fa9eeb07a189d6c0edd306713f67`.
- `git status --short` ban đầu: rỗng; working tree sạch trước kiểm toán.
- Không phát hiện `AGENTS.md` trong cây dự án khi kiểm tra.
- So sánh nội dung phục vụ qua HTTP: `frontend/assets/js/customer-ai.js` và `management-ai.js` khớp SHA-256 với checkout.
- So sánh file Python/JSON/ontology trong image, loại tests/backup/evaluation: AI có **80 file khớp**, **3 file khác**; backend và shared đi kèm có **111 file khớp**, không thấy khác biệt trong tập đã so sánh. Đây không phải chứng nhận toàn bộ filesystem image giống repository.

Ba file AI khác hash: `AI/api.py`, `AI/rag/conversation_service.py`, `AI/jewelry_agents/semantic_planner.py`.

Bốn module có trong checkout nhưng **không tồn tại** trong image AI:

- `AI/rag/semantic_conversation.py`.
- `AI/jewelry_agents/dialogue_plan.py`.
- `AI/jewelry_agents/dialogue_plan_validator.py`.
- `AI/jewelry_agents/dialogue_fast_path.py`.

Image AI: `sha256:a8a8fb38c8ec0ad9a279a8d2269cec045b5557dccb6b9b4963de373695d565fd`, được tạo 26/11/2026. Image Business API: `sha256:a27f1c1b85a44a1e0480e79c2cdefa3b22a2bde53ef05ae8c1266f4f5a85b0fe`, được tạo 24/11/2026.

### 2.2 Docker và cấu hình thực tế

| Container trong project `lumiere-rebuild-test` | Image/service | Trạng thái lúc kiểm tra |
| --- | --- | --- |
| frontend | image dự án | Up, healthy |
| ai-api | image dự án | Up, healthy |
| business-api | image dự án | Up, healthy |
| reverse-proxy | nginx:1.28-alpine | Up, healthy; publish `127.0.0.1:18080` |
| postgres | postgres:17 | Up, healthy |
| neo4j | neo4j:5.26-community | Up, healthy |
| qdrant | qdrant/qdrant:v1.18.3 | Up; không có health status trong `docker ps` |

Không thấy container `index-worker`, `ollama`, Prometheus hoặc Grafana đang chạy. Ollama trên **host** vẫn trả HTTP 200 ở cổng 11434, liệt kê `qwen2.5:3b`; kết nối cổng 11435 thất bại. GET `/api/tags` chỉ xác minh endpoint/model được liệt kê, không chứng minh khả năng sinh phản hồi ổn định.

Label Compose của AI: `compose.yaml` + `compose.original-data.yaml` + `compose.semantic-dst.yaml`. Business API dùng hai file đầu. `docker-compose.yml` và các overlay khác không được dùng làm căn cứ runtime chỉ vì tồn tại trên đĩa.

Cấu hình AI đã xác minh, không chứa bí mật:

| Biến | Runtime |
| --- | --- |
| `LUMIERE_RETRIEVAL_V2_ENABLED` | `true` |
| `LUMIERE_RETRIEVAL_LIMITS_ENABLED` | `true` |
| `LUMIERE_SHOPPING_ADVICE_ENABLED` | `true` |
| `LUMIERE_MODEL_WARMUP_ENABLED` | `true` |
| `LUMIERE_ATTRIBUTE_REVIEWS_ENABLED` | `false` |
| `LUMIERE_DENSE_TIMEOUT_SECONDS` | Compose overlay đặt `6`; không thay đổi trong kiểm toán |
| `QDRANT_COLLECTION` | `jewelry_products_v_c0efd814ee4f` |
| `EMBEDDING_REVISION` | `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` |
| `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` | `1`, `1` |
| Model cache | `/models`, bind mount chỉ đọc |
| `LUMIERE_HYBRID_NLU_ENABLED` | Không được đặt; checkout mặc định `false`, image chưa có các module tương ứng |
| `STAFF_AI_LLM_ENABLED`, `ADMIN_AI_LLM_ENABLED` | Không được đặt trong Business API; mặc định `false` |
| `LUMIERE_DIALOGUE_LLM_ENABLED` | Không được đặt; mặc định `false` |
| `PRODUCT_INDEX_SYNC_ENABLED` | Business API: `true`; đây là bật ghi outbox, không chứng minh worker đang xử lý |

`compose.yaml` lấy collection/revision qua biến môi trường, nên giá trị collection runtime khác giá trị mặc định trong YAML không tự chứng minh cấu hình sai. Chưa xác định toàn bộ nguồn env-file lúc khởi tạo; label Compose và environment đã lọc là căn cứ trực tiếp.

Health thực tế: `/ai/health/ready`, `/ai/health/semantic`, `/api/health/ready` đều HTTP 200. Semantic health báo `ready=true`, `warming=false`, thời gian warmup được service ghi nhận **46,104 giây**. Readiness chung coi Neo4j, Qdrant, Ollama là nguồn tùy chọn, vì vậy healthy không đồng nghĩa cả ba nguồn đều sẵn sàng trong mọi lượt.

Snapshot tài nguyên: AI khoảng 1,03 GiB/3 GiB; Neo4j khoảng 770,6 MiB/1,5 GiB; Qdrant khoảng 188,2 MiB/1 GiB. Không có bằng chứng từ snapshot này để kết luận OOM hoặc CPU saturation là nguyên nhân của các lỗi hội thoại.

### 2.3 Luồng Customer thực tế

```text
customer-ai.js
  POST /ai/chat {query, top_k, conversation_id}
    nginx -> ai-api:8000 /chat
      api.chat trong image: resolve ConversationStore, tạo callback answer
        rag.conversation_service.converse
          pending category / giải thích / so sánh / refinement / policy guard
          -> answer_jewelry_question
             classify_query + aliases + ontology rules + optional advice MiniLM
             -> search_service.search
                Business API /products -> PostgreSQL
                lọc điều kiện bắt buộc trên catalog thật
                lexical + MiniLM/Qdrant + Neo4j candidate paths
                RRF -> xác minh catalog mới nhất -> top K
             -> build_safe_answer / phản hồi tư vấn có giới hạn
          -> compact_shopping_answer nếu đủ điều kiện
          -> cập nhật state và kết quả trong RAM
      JSON answer + products + metadata -> frontend
```

Trong image, callback `api.chat()` có cập nhật shopping state; trong checkout, phần tương thích này đã chuyển sang `_remember_legacy_result()` trong coordinator. Sơ đồ mô tả image hiện chạy, không mặc định coi refactor trên đĩa đã được deploy.

### 2.4 Thành phần AI và mức độ sử dụng

| Thành phần | Thực trạng và bằng chứng |
| --- | --- |
| NLU Customer | `intent_router.classify_query()`, `entity_linking.link_query()`, `dialogue_state_extractor.extract_state_changes()`: phần lớn rule, alias, regex; có MiniLM cho các nhánh advice/category/refinement. Không phải toàn bộ câu đầu vào đều được một NLU model phân loại. |
| MiniLM/embedding | `retrieval.get_dense_services()`, `_load_dense_services()`, `_search_qdrant()`; model `paraphrase-multilingual-MiniLM-L12-v2`, 384 chiều. Warmup thực và diagnostic có dense ranks chứng minh nhánh model/vector hoạt động. |
| Ontology | `AI/config/aliases_vi.json`, `ontology_reasoner.reason_categories()`, `rank_with_knowledge()`: taxonomy, định nghĩa và luật location/usage/form. Có suy luận miền theo luật; chưa có bằng chứng về một OWL/DL reasoner tổng quát trong luồng phục vụ. |
| Neo4j Knowledge Graph | 500 Product, các node Category/Brand/Material/Gemstone/Collection, 5 loại quan hệ sản phẩm. `graph_expand_candidates()` dùng dense anchors; `graph_search_candidates()` phục vụ trường hợp phù hợp, đặc biệt tham chiếu. Diagnostic đã ghi nhận graph ranks và paths được kiểm tra. |
| Qdrant | Collection có 500 point, vector 384 chiều, Cosine. `_search_qdrant()` kiểm tra identity collection, revision, dimension/distance và eligible IDs. |
| Hybrid Retrieval | `search_service.search()`: lexical từ token overlap trên catalog, dense, graph; không nên gọi lexical hiện tại là BM25 vì mã mặc định đếm giao token. Có degradation theo nguồn. |
| RRF | `ranking.reciprocal_rank_fusion()`, mặc định hằng số 60: cộng `1/(60+rank)` theo nguồn. Runtime sản phẩm ghi `ranking_method=reciprocal_rank_fusion`; diagnostic có ba bảng rank. |
| Reranker graph tùy chọn | `reranking.GraphFeatureReranker` có đường gọi diagnostic; hai diagnostic baseline có `reranker=null`. Chưa có bằng chứng public chat mặc định gọi reranker này. |
| Semantic DST | Thực tế là ShoppingState có cấu trúc, rule patch, semantic entity refinement và soft price inference. Bật nhưng chưa bao phủ tốt chuyển task, diễn đạt ngắn và reset mơ hồ. |
| Dialogue Policy | Có logic policy trong các nhánh `converse`, `pending_category_reply`, guard intent và state preservation; không thấy module policy thống nhất/learned policy trong luồng đang chạy. |
| Semantic Planner cũ | `semantic_planner.plan_query()` tồn tại trong image; flag `false`, không tham gia baseline. |
| Planner full context mới | `plan_dialogue()`/`request_plan()`, validator, fast path và `semantic_turn()` có trong checkout; không có trong image, chưa tham gia runtime. Gate riêng `LUMIERE_HYBRID_NLU_ENABLED`, không đồng nhất với flag planner cũ. |
| RAG | Lấy dữ liệu sản phẩm/công cụ để tạo phản hồi có grounding. Retrieval V2 chủ yếu dựng lời trả lời bằng mã xác định; không phải mọi lượt đều có bước LLM generation. |
| Grounded Response Generation | `build_safe_answer()`, `compact_shopping_answer()`, `product_dialogue.discussion_reply()`, `verified_paths()`, `finalize_topk()` hoạt động. Phần narrative LLM đang tắt. |
| LLM provider | Các đường có thể gọi Ollama HTTP cục bộ; không có bằng chứng baseline đang dùng OpenAI/cloud LLM. Qwen 3B host có endpoint; provider 0.6B ở 11435 không kết nối được. Nhánh DST vẫn có thể gọi 3B dù price flag false. |
| CrewAI/legacy | `rag_service` còn nhánh `hybrid_search` + `run_crew` khi Retrieval V2 tắt. Vì V2 đang true, không có bằng chứng baseline gọi CrewAI. Các file backup/demo/test độc lập không chứng minh tham gia request. |

### 2.5 Staff, Admin, authentication và authorization

Frontend `management-ai.js` chọn endpoint theo vai trò giao diện và gửi cookie `credentials: same-origin`. Quyền thực do backend quyết định:

- `auth.get_current_user()`: cookie session, hash token, kiểm tra phiên tồn tại/hết hạn, user active.
- `orders.staff_or_admin()`: staff hoặc admin; `orders.admin()`: chỉ admin.
- `ai_staff.staff_ai_chat()` và `ai_admin.admin_ai_chat()` gọi `shared.conversation.converse()` với scope `(role, user.id)`.
- Staff routing: product lookup → multi-intent → inventory → time-order parser → order statistics rule/LLM tùy flag.
- Admin routing: product lookup → multi-intent → inventory → revenue → top-selling rule/LLM tùy flag.
- Công cụ trả dữ liệu từ PostgreSQL; LLM phân loại tùy chọn không được tạo SQL thực thi.

ConversationStore giới hạn 256 phiên, TTL 1.800 giây, lịch sử 6 lượt, lock từng phiên. State nằm trong RAM của từng process, chưa có lưu bền hoặc chia sẻ nhiều replica. Customer dùng scope chung `customer-public` và conversation ID ngẫu nhiên: đủ cho dữ liệu công khai, không phải cơ chế xác thực tài khoản.

Qua reverse proxy, không cookie: Staff/Admin chat đều **401**; internal diagnostic công khai bị **404**. ASGI harness riêng với dependency user lấy từ tài khoản hiện có: Customer → Staff/Admin **403/403**; Staff → Staff/Admin **200/403**; Admin → Staff/Admin **200/200**. Harness vẫn chạy route và role dependencies nhưng thay bước resolve cookie bằng user đã đọc; **không phải kiểm thử login-cookie end-to-end**. Không tạo tài khoản hoặc session database để kiểm tra.

## 3 Ma trận chức năng ba vai trò

Nhãn: **V** = Implemented and verified trong phạm vi ca đã chạy; **U** = Implemented but unverified ở runtime cho chức năng đó; **P** = Partially implemented; **D** = Disabled; **N** = Not implemented trong luồng chatbot đã truy vết; **B** = Broken đối với hành vi được nêu. HTTP 200/`success=true` tự nó không đủ cho nhãn V.

### 3.1 Customer

Endpoint chính: `POST /ai/chat` ở proxy, `/chat` trong AI API.

| Chức năng | Nhãn | Bằng chứng và giới hạn |
| --- | --- | --- |
| Chào hỏi | V | `classify_query()`, “xin chào” → `greeting`. |
| Tìm theo loại và ngân sách | V | `search()`, `extract_price_filter()`, `finalize_topk()`; nhẫn dưới 5 triệu có 3 sản phẩm đúng category, giá và stock. |
| Tìm theo chất liệu/đá và tổ hợp điều kiện | U | `link_query`, lọc material trong `search`, tests `test_search_service`, `test_shopping_state_updates`; chưa chạy hết tổ hợp thật. |
| Top K 1–10 | U | validation `ChatRequest`, parser top trong `search()`, `test_topk_ranking`; baseline chủ yếu K=3. |
| SKU/product identity | V giới hạn | `search()` nhận SKU; SP000019 hết hàng bị loại khỏi gợi ý. Chưa nghiệm thu mọi dạng tên/ID/SKU. |
| Sản phẩm tương tự từ tham chiếu/graph | U | `query_reference.resolve_reference`, graph traversal, `test_related_product_search`, `test_recommendation_contract`; chưa chạy baseline đầy đủ theo từng quan hệ. |
| Đổi loại giữ ngân sách | V cho diễn đạt rõ; B cho diễn đạt được báo lỗi | “đổi sang vòng tay” giữ dưới 5 triệu; “còn vòng đeo tay” không chuyển state thành công. |
| Đổi ngân sách, giữ loại | V | “dưới 3 triệu” sau vòng tay trả đúng vòng tay dưới 3 triệu. |
| Xóa/thay material/gemstone, thay K, giá rẻ hơn | U | `StatePatch`, extractor/controller và tests state; chưa đo đầy đủ với model thật. |
| Đổi nhu cầu/reset | P/B | Có regex reset, nhưng “đổi nhu cầu khác” lặp câu làm rõ; chưa có task management đầy đủ. |
| Làm rõ category | P | Có options và xử lý câu trả lời; trường hợp “vòng đeo tay” đưa cả nhẫn vào lựa chọn. |
| So sánh các card vừa trả | V | `discussion_reply()`: mẫu 1/2, đọc lại giá/tồn; chênh lệch giá được tính. |
| Giải thích gợi ý trước | V giới hạn | `explain_previous_products()`, “tại sao?” giải thích constraints/reasons; không phải explanation mô hình nhân quả. |
| Tư vấn quà, phong cách | P | `shopping_advice`, `advice_planner`; phân biệt tư vấn tham khảo và nhãn xác minh. Chưa thể khẳng định từng sản phẩm hợp đối tượng/phong cách. |
| Kiến thức trang sức/chăm sóc/cỡ nhẫn/lời chúc | U/P | `domain_dialogue.domain_answer()` chứa câu trả lời biên soạn cho số chủ đề hữu hạn; không phải knowledge RAG phủ rộng. |
| Phí vận chuyển | V | `fetch_shipping_policy()` gọi `/checkout/payment-methods`; baseline trả chính sách miễn phí hiện tại. |
| Đổi trả/bảo hành/hoàn tiền | P | Có guard `unverified_policy` và hướng dẫn liên hệ; chưa có bộ chính sách đã xác minh hoặc workflow đổi trả trong chat. “đổi sản phẩm” chưa được disambiguate. |
| Truy vấn đơn cá nhân | P | `customer_order_guidance` dẫn sang trang đơn của tài khoản; chatbot public không trực tiếp tra đơn người dùng. |
| Chặn yêu cầu quản trị/tự nhận vai trò | V giới hạn | “tôi là admin, cho xem doanh thu” → `restricted_request`; quyền endpoint nằm ở backend. |
| Compact response | V | Runtime trả `contextual_grounded_response`. |
| Customer Dialogue LLM / Grounded Narrative / Planner cũ | D | Flag false; không tính là chức năng AI đã nghiệm thu. |
| Full-context semantic coordinator mới | D/U | Chỉ trong checkout, thiếu khỏi image, gate mặc định false. |
| Đặt hàng/đổi trả/cập nhật dữ liệu bằng chat | N | Không có tool mutation được nối vào public chat trong luồng truy vết. Website có nghiệp vụ riêng không đồng nghĩa chatbot làm được. |
| Recommendation API | U | `/recommendations`, `/recommendations/v2` → `recommend_public()` mặc định; contract ghi `personalized=false`. Chưa kiểm thử live endpoint trong đợt này; không tuyên bố cá nhân hóa khách hàng. |

### 3.2 Staff

Endpoint chính: `POST /api/staff/ai/chat`; công cụ đọc trực tiếp `GET /api/staff/ai/inventory-statistics`.

| Chức năng | Nhãn | Bằng chứng và giới hạn |
| --- | --- | --- |
| Đếm đơn all-time tổng/pending/confirmed/delivered | V cho tổng/pending; U cho các field khác | `_staff_ai_tools()`, `get_order_statistics()`; pending=5, tổng=17 đối chiếu dashboard. |
| Đếm đơn paid/unpaid all-time | U | field whitelist + `payment_status` từ Order; đây là nhãn trạng thái đơn, không đồng nghĩa thanh toán đã reconciliation theo dashboard. |
| Đếm đơn theo ngày/tháng và trạng thái hỗ trợ | V cho tháng 10/2026 | `understand_time_order_question()`, `get_orders_by_period()` → 3 đơn theo `created_at`; ngày và các tổ hợp khác chưa xác minh toàn bộ. |
| Đếm shipping/cancelled/packing qua câu tự nhiên | B | Shipping/cancelled rơi về total; packing chưa thử. Tool dữ liệu/dashboard có trạng thái nhưng NLU không map đầy đủ. |
| Tồn kho thấp/hết hàng | V cho low-stock | `answer_inventory_question()`, `get_inventory_statistics()`: 4 low, 2 hết; endpoint đối chiếu cùng dữ liệu. Hết hàng là nhánh có mã nhưng chưa test chat riêng. |
| Tra SKU cụ thể | V | `answer_product_lookup()`: SP000002 stock60, giá2.619.639. |
| Tra tên sản phẩm | U | `extract_product_query()` và ORM `ilike` có escape, giới hạn 5 item; chưa nghiệm thu độ phủ cách diễn đạt. |
| Nhiều nghiệp vụ đơn+tồn kho | U/P | `answer_staff_multi_intent()`; có giới hạn không kết hợp thời gian. Backend tests có coverage; chưa chạy live harness câu kết hợp Staff. |
| Lọc tồn kho theo ngưỡng tùy chọn | U/P | GET nhận threshold0–1000/limit1–50; chat mặc định threshold5/limit20, chưa hiểu tùy ý mọi ngưỡng. |
| Hỏi ngắn theo ngữ cảnh | B/P | “sắp hết” sau báo cáo low-stock → unsupported; chỉ có history/last_result và vài followup chung. |
| Giải thích kết quả trước | V giới hạn | “tại sao?” trả lại kết quả trước, có một số định nghĩa theo intent; chưa hiểu đầy đủ đối tượng đang được người dùng tham chiếu. |
| Chào hỏi tự nhiên | P | “xin chào” → câu mặc định thống kê đơn; chưa có greeting policy nghiệp vụ phù hợp. |
| LLM phân loại Staff/hội thoại chung | D | `STAFF_AI_LLM_ENABLED` và `LUMIERE_DIALOGUE_LLM_ENABLED` unset/default false. |
| Doanh thu/lợi nhuận/phân tích khách hàng | N trong chat Staff | Không có tool hợp lệ nối vào Staff cho các nghiệp vụ này. |
| Thao tác đơn/tồn kho qua AI | N | Các tool AI đã truy vết chỉ đọc; endpoint nghiệp vụ website riêng không được tính là AI. |

### 3.3 Admin

Endpoint chính: `POST /api/admin/ai/chat`; GET `/admin/ai/top-selling-products`, `/admin/ai/sync-status`; POST `/admin/ai/retrieval-diagnostics` là công cụ chẩn đoán chỉ đọc.

| Chức năng | Nhãn | Bằng chứng và giới hạn |
| --- | --- | --- |
| Top bán chạy theo tháng | V | `understand_admin_question()`, `get_top_selling_products()`; tháng10/2026 khớp endpoint GET, có 2 item thực dù hỏi Top5. |
| Top bán chạy ngày/khoảng thời gian, limit1–20 | U | API service nhận date range; khả năng NLU tùy parser, chưa thử mọi dạng. |
| Doanh thu ngày/tháng | V cho tháng10; U cho ngày | `get_revenue_statistics()` reuse `dashboard.revenue()`; 13.814.291 đồng/3 đơn khớp Business API. |
| Quý/năm/so sánh nhiều kỳ/tăng trưởng | B/P | Hỏi quý3 nhận tháng11; so sánh9/10 chỉ trả9. Chưa có planner/phân tích so sánh đầy đủ. |
| Tồn kho và SKU/tên | V cho low-stock; U cho lookup Admin | Dùng cùng tool Staff; low-stock=4. Lookup có đường gọi ưu tiên đầu nhưng chưa chạy câu lookup riêng Admin. |
| Tổng đơn độc lập | B | “Có bao nhiêu đơn hàng?” → unsupported, dù tool đơn có trong orchestrator. |
| Tổng đơn kết hợp tồn kho | V | “Tổng đơn hàng và tồn kho” → multi_intent, tổng17, low4, hết2. |
| Revenue + top-selling + inventory kết hợp | U/P | `answer_admin_multi_intent()`; có các tổ hợp hạn chế period, top-selling trong multi mặc định5. Chưa nghiệm thu tất cả tổ hợp. |
| Customer analytics qua chat | N | “Thống kê khách hàng tháng10/2026” → unsupported. Có Business API `/admin/reports/purchase-behavior`, nhưng không thấy nối vào AI Admin. |
| Forecast, churn, segmentation, đề xuất nhập hàng, lợi nhuận ròng | N | Không có tool/planner tương ứng trong call graph đã kiểm tra. Không được suy ra từ việc có dashboard. |
| Kế thừa kỳ báo cáo ở lượt sau | B/P | “tháng9 thì sao?” sau top-selling → unsupported. Chưa có BusinessState typed. |
| Giải thích báo cáo trước | V giới hạn | `shared.followup_reply()`, có định nghĩa đơn giản theo intent; với multi-intent thường chỉ lặp lại kết quả và lời giải thích chung. |
| Greeting | P | “xin chào” trả mặc định hỗ trợ top bán chạy. |
| Diagnostic retrieval, sync status | U cho route được xác thực | Code và tests tồn tại; retrieval diagnostic được gọi trực tiếp qua token nội bộ, sync_status service đọc trong harness. Chưa chạy UI admin có cookie thật. |
| Admin LLM classifier/hội thoại chung | D | Các flag tương ứng unset/default false. |
| Tự động sửa dữ liệu qua AI | N | Không có tool mutation trong các route AI đã truy vết. |

## 4 Bảng kiểm toán sáu feature flags

### 4.1 Cấu hình và trạng thái

Tất cả sáu biến dưới có trong `compose.semantic-dst.yaml`, overlay đang gắn với AI container. `compose.customer-dialogue-host.yaml` là overlay khác, hiện không nằm trong label Compose của AI.

| Chức năng | Biến chính xác | Runtime | Kết luận |
| --- | --- | --- | --- |
| Semantic Dialogue State Tracking | `LUMIERE_SEMANTIC_DST_ENABLED` | `true` | Bật nhánh semantic refinement; DST rule vẫn có thể chạy độc lập với flag này. |
| Compact Shopping Response | `LUMIERE_COMPACT_SHOPPING_RESPONSE_ENABLED` | `true` | Đã thấy response mode đúng; không cần LLM. |
| Semantic Price LLM | `LUMIERE_SEMANTIC_PRICE_ENABLED` | `false` | Tắt ở đường mặc định; **DST override có thể kích hoạt LLM**. Không được ghi đơn giản là disabled hoàn toàn. |
| Grounded Narrative | `LUMIERE_GROUNDED_NARRATIVE_ENABLED` | `false` | Disabled; còn phụ thuộc Customer Dialogue bật. |
| Customer Dialogue LLM | `LUMIERE_CUSTOMER_DIALOGUE_ENABLED` | `false` | Disabled. |
| Semantic Planner | `LUMIERE_SEMANTIC_PLANNER_ENABLED` | `false` | Planner cũ disabled; không điều khiển full-context planner mới. |

### 4.2 Semantic Dialogue State Tracking

- File/hàm: `dialogue_state_controller.prepare_refinement()`, `prepare_semantic_refinement()`, `semantic_entity_refinement()`; `dialogue_state_extractor.extract_state_changes()`; `ShoppingState`, `StatePatch`, `render_shopping_query()`.
- Call flow: Customer coordinator → refinement rule → nếu không có cập nhật rõ, semantic entity → semantic soft price → patch hoặc abstain.
- Điều kiện: cần previous ShoppingState có category; câu ngắn tối đa250 ký tự; loại trừ knowledge/followup/reference/identity, intent không phù hợp, entity đã nhận rõ hoặc chữ số cho nhánh semantic soft refinement.
- Semantic entity dùng MiniLM đã nạp, không load model khác; cosine ít nhất0,82 và margin ít nhất0,12, chặn một số phủ định và từ liên quan giá. Timeout gate4 giây.
- Phụ thuộc: ontology/embedding; **có thể phụ thuộc Ollama** khi thử price inference với `enabled=True`, budget18 giây. DST không phải hoàn toàn độc lập LLM ở runtime hiện tại.
- Tests: `test_shopping_state_updates`, `test_price_preference`, `test_contextual_product_dialogue`, `test_shopping_consultation`. Có mock encoder/LLM và test giữ state khi timeout/invalid.
- Bằng chứng: đổi loại rõ ràng và budget hoạt động; ba diễn đạt báo lỗi lặp clarification. Không có accuracy DST tổng thể.
- Lợi ích giữ/bật: giữ ràng buộc, giảm mất ngân sách và hỗ trợ refinement. Rủi ro: state bị giữ quá mức, semantic false positive, suy giá từ câu không nói giá, độ trễ và bypass flag.
- Fallback: không áp patch khi không chắc, giữ state/cũ; source fail phục hồi snapshot. Fallback an toàn về ràng buộc nhưng thiếu lối thoát hội thoại.

### 4.3 Compact Shopping Response

- File/hàm: `rag/conversation_service.converse()` → `rag/contextual_response.compact_shopping_answer()`; `shopping_summary()`, `describe_budget()`.
- Điều kiện: có products, intent không thuộc product discussion/shopping advice, flag true; cần dữ liệu/state phù hợp để tạo compact text.
- Phụ thuộc: dữ liệu sản phẩm đã retrieval/verify và ShoppingState; **không cần LLM**.
- Tests: `test_contextual_product_dialogue`, `test_shopping_state_updates`, `test_shopping_consultation`.
- Runtime: tìm nhẫn, đổi vòng tay và đổi budget đều có `response_mode=contextual_grounded_response`; có nhắc giới hạn nguồn ở lượt degraded.
- Lợi ích: câu trả lời ngắn, phản ánh state. Rủi ro: cô đọng sai nếu state sai; có thể làm người đọc bỏ qua giới hạn tư vấn/nguồn nếu template thiếu.
- Fallback: nếu không tạo được compact, giữ câu trả lời dựng từ retrieval. Chưa có benchmark độ tự nhiên/hài lòng người dùng.

### 4.4 Semantic Price LLM

- File/hàm: `semantic_price_intent.infer_price_preference()`, `semantic_intent_validator.validate_price_intent()`, `price_intent_router.resolve_price_preference()`; được gọi từ search và DST.
- Biến phụ: `LUMIERE_SEMANTIC_PRICE_URL`, `..._MODEL`, `..._KEEP_ALIVE`, `..._DEBUG`; runtime URL host11434 `/api/chat`, model `qwen2.5:3b`, keep_alive10m, debug false.
- Điều kiện mặc định: flag true, câu hợp lệ và endpoint local được allowlist. Trong search, semantic thường chỉ đến sau rule, không có numeric price constraints, không bị negation/indifference guard chặn. Chỉ cho semantic đưa vào soft preference `affordable`.
- Ngoại lệ đã xác minh: `prepare_semantic_refinement()` → `semantic_infer()` truyền `enabled=True,time_budget=18` dù biến Price false. Mô phỏng trên mã container ghi nhận lời gọi này với “còn vòng đeo tay”. Đây là bằng chứng call-path, không phải trace đầy đủ HTTP của lượt 21,381 giây.
- LLM trả JSON preference/evidence; evidence phải được validator chấp nhận. Timeout SourceGate mặc định35 giây, DST dùng18; HTTP timeout lớn hơn budget1 giây. Không retry; allowlist và chặn redirect.
- Tests: `test_shopping_state_updates.test_semantic_json_invalid_and_unquoted_proposal_abstain`, `test_semantic_timeout_or_rejection_preserves_state`, `test_price_preference` và các tests price intent.
- Lợi ích bật lại đúng nghĩa: hiểu nhu cầu tiết kiệm qua paraphrase. Rủi ro: latency, gán affordability sai, RAM model host; flag hiện không có tính quyết định nhất quán.
- Fallback: neutral, rule ranking hoặc state-preserving clarification. Chưa có live benchmark độc lập chứng minh độ chính xác price LLM ổn định.

### 4.5 Grounded Narrative

- File/hàm: cuối `conversation_service.converse()` → `natural_dialogue.answer_natural()`.
- Điều kiện đồng thời: flag narrative true, có1–3 products, retrieval sources gồm cả dense và graph; **Customer Dialogue cũng phải true** vì `answer_natural()` kiểm tra riêng. Đủ budget còn lại, model không warming.
- Evidence: attributes Category/Material/Gemstone, một phần relationships và shopping_state; không cho model tự quyết tên/giá/ID. Narrative được nối phía trước câu trả lời xác định, không thay ranked products.
- Phụ thuộc: retrieval, graph/dense, Ollama/Customer Dialogue config. SourceGate24 giây, budget tổng trong coordinator được tính từ mốc35 giây nhưng không phải hard deadline cưỡng chế toàn request.
- Tests: `test_semantic_planner.test_grounded_generation_never_changes_ranked_products`, tests natural dialogue; chủ yếu mock generated output.
- Runtime: disabled, chưa có baseline narrative thật. Overlay host có chú thích chưa qua live acceptance; đây là lịch sử thiết kế, không phải phép đo hiện tại.
- Lợi ích bật lại: diễn đạt giải thích tự nhiên hơn. Rủi ro: thêm diễn giải không được facts hỗ trợ; regex chặn giá/URL không chứng minh mọi câu đều grounded; tăng latency.
- Fallback: `None` → giữ nguyên safe/compact answer. Chỉ bật narrative riêng hiện vẫn không tạo narrative vì Customer Dialogue tắt.

### 4.6 Customer Dialogue LLM

- File/hàm: `rag/natural_dialogue.answer_natural()`, các nhánh unsupported/general_question/out_of_scope trong `converse()`.
- Biến phụ: `LUMIERE_CUSTOMER_DIALOGUE_URL`, `..._MODEL`, `..._KEEP_ALIVE`. Default code: host11435, `qwen3:0.6b-q4_K_M`, keep_alive5m; overlay host tùy chọn đặt keep_alive0. Overlay đó hiện không áp dụng.
- Điều kiện: flag true, model không warming, endpoint local đúng `/api/chat`, còn budget. Lịch sử2 lượt, hạn chế context/output; Qwen3 tắt thinking.
- Validation: response done, content không rỗng; xử lý output bị cắt; chặn URL và một số biểu diễn số tiền. Không có factual verifier đầy đủ cho mọi claim.
- Tests: `test_natural_dialogue`, `test_semantic_startup_isolation`, `test_dialogue_model_cache`; verify security guard/timeout/truncation bằng mocks.
- Runtime: flag false; host11435 không kết nối được tại thời điểm kiểm tra. Lịch sử `docs/ai-natural-dialogue-live-20261123.json` ghi ReadTimeout cho một cấu hình Qwen3B, chỉ là bằng chứng lịch sử, không thay kết quả baseline này.
- Lợi ích bật lại: chào hỏi/trao đổi tự nhiên và diễn đạt kiến thức đã duyệt. Rủi ro: hallucination ngôn ngữ, memory contention, timeout; không tự bổ sung tool, taxonomy hay DST nghiệp vụ.
- Fallback: domain answer biên soạn hoặc câu làm rõ hiện có. Bật flag không tự sửa nguyên nhân định tuyến và vòng lặp state.

### 4.7 Semantic Planner

- File/hàm cũ: `semantic_planner.plan_query()`, `resolve_mentions()`, `merge_understanding()`; `QueryPlan`/`CompactPlan` schema.
- Flow: coordinator xem xét ở câu general/product_search chưa được hiểu rõ, loại các đường ưu tiên như policy, kiến thức, SKU; plan được validate rồi truyền vào `answer_jewelry_question()` và `search()`.
- Biến: `LUMIERE_SEMANTIC_PLANNER_ENABLED`; provider dùng `LUMIERE_CUSTOMER_DIALOGUE_URL`/`MODEL`, không phụ thuộc flag Customer Dialogue để gọi planner cũ.
- Guard: local endpoint allowlist; JSON schema; canonical ID thuộc ontology; quote phải xuất hiện trong câu; không ghi đè explicit entity; child/ambiguous có xử lý. Quote tồn tại không tự chứng minh semantic label đúng.
- Timeout: SourceGate12 giây, HTTP13; lỗi/JSON không hợp lệ → `None`.
- Tests: `test_semantic_planner`, `test_semantic_category`, `test_advice_planner`. `docs/ai-semantic-plan-probe-20261124.json` lịch sử có2 case failed, case đầu timeout khoảng12 giây; không dùng làm tỷ lệ accuracy chung.
- Runtime: flag false, provider default11435 không kết nối được. Chưa có bằng chứng hoạt động ổn định với model thật cho baseline.
- Lợi ích bật lại: hiểu câu không có alias rõ, mở rộng phân loại theo evidence. Rủi ro: false mapping, latency, model nhỏ không đủ năng lực. Fallback là luồng hiểu hiện tại, không thực thi SQL/graph writes do LLM sinh.
- **Không nhầm với planner mới**: `plan_dialogue()`/`dialogue_plan.request_plan()` trong checkout dùng gate `LUMIERE_HYBRID_NLU_ENABLED`, provider Semantic Price, operation SET/CLEAR/KEEP/UNKNOWN/RESET và validator riêng. Bốn module tương ứng thiếu trong image; `test_semantic_dialogue_plan` chạy trên checkout không chứng minh chúng đang phục vụ người dùng.

## 5 Nguyên nhân gốc các lỗi

### 5.1 Customer

**“còn vòng đeo tay”**: alias nhận “vòng tay”, không nhận nguyên cụm “vòng đeo tay” vì matching cần cụm liên tục. Ontology rule nhận vị trí “cổ tay”, không xem “tay” chung chung là wrist. Ở phiên mới, advice MiniLM xếp bracelet0,71615 và ring0,62763, chênh khoảng0,0885; `category_question()` dùng margin0,10 nên hỏi vòng tay hay nhẫn. Đây là hạn chế biểu diễn/ontology, độ phân biệt embedding và policy abstain; chưa có cơ sở quy về “thiếu LLM”. Ở phiên đã có ring state, semantic refinement không chấp nhận được một slot mới và rơi vào giữ state.

**“tôi muốn đổi sản phẩm”**: có ít nhất hai nghĩa hợp lý, đổi lựa chọn tư vấn hoặc đổi trả món đã mua. Intent router chỉ nhận các cụm policy “đổi trả”, “hoàn tiền”, “bảo hành”; không có bước hỏi để phân biệt hai tác vụ. Không có category/slot đích để patch. Phiên mới đi vào general_question và bridge quà tặng; phiên đang shopping lặp state-preserving clarification.

**“đổi nhu cầu khác”**: controller chỉ xét reset sau khi có `updates` hoặc `clear`; nếu không có, đã return sang semantic refinement trước khi tới regex reset. Câu này cũng không khớp tập tín hiệu reset rõ như “nhu cầu mới”. Không có TaskState riêng và không có pending task-change cho phép người dùng trả lời đúng lựa chọn mà chatbot tự đề xuất.

**Lặp câu làm rõ**: nhánh bảo vệ unresolved followup trong `converse()` return sớm với một template chung, chỉ append history, không ghi một clarification goal cụ thể có thể giải quyết ở lượt sau. Không có đếm lặp/escalation/escape. Dữ liệu history không được một policy ngữ nghĩa sử dụng đầy đủ khi LLM dialogue/planner tắt. Một số fallback an toàn đã bị biến thành ngõ cụt hội thoại.

**Nhận nhẫn và budget tốt hơn**: alias ring trực tiếp, parser số tiền cụ thể, `StatePatch` giữ các trường không sửa; live eligibility/final verification bắt category, stock và giới hạn `< 5.000.000`. Đây là năng lực thực theo constraints, không chứng minh tổng quát hóa mọi cách nói về trang sức.

### 5.2 Staff

**Trả low-stock được**: keyword đủ → `answer_inventory_question()` → `get_inventory_statistics()` đọc PostgreSQL; ngưỡng chat5, hết hàng0, low1–5. Không cần LLM để tính số liệu này.

**Cứng nhắc với câu ngắn**: router không kế thừa intent inventory của lượt trước; “sắp hết” không khớp “sắp hết hàng”. Rơi qua order-intent rồi trả unsupported. History chỉ có fallback explanation/correction, chưa phải DST nghiệp vụ.

**Sai trạng thái đơn**: `understand_staff_question()` có default total khi phát hiện “đơn” nhưng không match pending/confirmed/delivered/payment. Không xác minh phần câu chưa được hiểu. Do đó “đã hủy” và “đang giao” bị bỏ qua, trả total17 thay vì status count1. Đây là semantic scope error trên dữ liệu thật, khác hallucination số tự sinh.

**Phạm vi thực**: đếm đơn theo một số trạng thái, đếm ngày/tháng theo created_at, tồn kho hiện tại, tra SKU/tên, một số multi-intent all-time. Chưa có phân tích nguyên nhân tồn, dự báo nhập hàng, doanh thu Staff, hoặc truy vấn SQL tự do. Chuỗi unsupported còn nói chỉ all-time dù nhánh time parser đã hỗ trợ ngày/tháng: mô tả khả năng không theo kịp công cụ.

**Rủi ro inventory list**: service lấy chung `stock<=threshold`, sort stock rồi LIMIT20, sau đó chat mới tách low/out. Nếu có từ20 sản phẩm hết hàng trở lên, low-stock có thể có count dương nhưng danh sách rỗng. Chưa xảy ra trên dữ liệu hiện tại; đây là lỗi thiết kế tiềm tàng có căn cứ mã, không phải failure đã quan sát.

### 5.3 Admin

**Top bán chạy tháng hoạt động**: parser nhận business intent/month/limit, tool dùng các đơn có thanh toán được xác nhận và OrderItem. Có definition metric cụ thể, không phải model đoán số.

**Greeting mặc định**: không có nhánh greeting nghiệp vụ trước công cụ; đi qua top-selling parser trả unsupported. Shared LLM dialogue tắt, nên giữ câu trả lời mặc định vốn không mô tả đầy đủ revenue/inventory hiện đã có.

**Hạn chế analytics**: tool registry thực tế không có customer analytics, cohort, forecast, profit. Business API purchase-behavior tồn tại nhưng chưa được route vào chat. Thêm LLM mà không bổ sung tool/schema/quyền không tạo ra dữ liệu phân tích đáng tin cậy.

**Sai thời gian**: revenue parser mặc định tháng hiện tại khi không nhận ra tháng/ngày hỗ trợ; không reject quý/năm và không phát hiện so sánh nhiều kỳ. “quý3/2026” nhận11/2026; “so sánh tháng9 và10” chỉ lấy match tháng9 đầu tiên.

**Routing không nhất quán**: tổng đơn có thể được gọi trong `answer_admin_multi_intent()`, nhưng không có single-tool order route trong `_admin_ai_tools()`. Cùng capability được chấp nhận hay từ chối tùy có từ “tồn kho” đi kèm.

**Hội thoại đa lượt**: `shared.conversation` không có last_metric/date_range/group_by/filter state để diễn giải “tháng9 thì sao?”. Có thể giải thích kết quả trước theo template, nhưng không tự tạo truy vấn tiếp nối đúng metric/kỳ.

## 6 Kết quả baseline và chất lượng dữ liệu

### 6.1 Phương pháp và giới hạn

Customer được gọi qua reverse proxy thật bằng HTTP và conversation ID mới cho từng nhóm. Staff/Admin được chạy bằng ASGI harness riêng trong container với chính mã image và dữ liệu PostgreSQL thật; chỉ override `get_current_user` bằng user có role tương ứng đã đọc từ DB. Tất cả connection DB của harness được ép `read_only=True`; `SHOW transaction_read_only` trả `on`. Không đổi cấu hình process web đang chạy, không cài package, không sinh login session. Thử TestClient ban đầu không chạy được do image thiếu `httpx2`, sau đó dùng ASGI trực tiếp.

Các kiểm thử scope bổ sung F01/F02 gọi hàm tool dispatcher trong process riêng, cùng read-only guard. Đó là kiểm chứng service/router implementation trên dữ liệu thật; không ghi là phép đo network end-to-end.

Chưa chạy browser UI end-to-end, stress test, fault injection vào dịch vụ thật hoặc bật các flag đang tắt. Không tính số liệu lịch sử trong `docs` thành kết quả chạy mới. Các thời gian dưới là từng quan sát, không phải p95 hay benchmark năng lực production.

### 6.2 Customer qua HTTP thật

| Phiên và câu hỏi | Kết quả | Thời gian giây |
| --- | --- | --- |
| A1 “nhẫn dưới 5 triệu” | 3 sản phẩm; `degraded`, sources dense+lexical | 5,955 |
| A2 “còn vòng đeo tay” | `state_preserving_clarification`, chưa chuyển category | 21,381 |
| A3 “tôi muốn đổi sản phẩm” | Cùng câu làm rõ A2 | 2,438 |
| A4 “đổi nhu cầu khác” | Cùng câu làm rõ A2 | 0,177 |
| Phiên mới “còn vòng đeo tay” | Hỏi chọn vòng tay hoặc nhẫn, `ontology_embedding_ambiguity` | 10,375 |
| Phiên mới “tôi muốn đổi sản phẩm” | general_question, làm rõ chung và bridge quà tặng | 0,197 |
| Phiên mới “đổi nhu cầu khác” | general_question, làm rõ chung và bridge quà tặng | 0,134 |
| B1 “nhẫn dưới 5 triệu” | `ok`, dense+graph+lexical, IDs87/2/203 | 2,326 |
| B2 “đổi sang vòng tay” | `ok`, giữ dưới5 triệu, IDs197/74/259 | 0,842 |
| B3 “dưới 3 triệu” | `ok`, giữ vòng tay, cả3 giá dưới3 triệu | 0,677 |
| B4 “so sánh mẫu số 1 và mẫu số 2” | `product_discussion`, giá/tồn đọc lại; chênh693.026đ | 0,113 |
| B5 “tại sao?” | Giải thích danh sách shopping trước, không truy vấn bộ mới | 0,007 |
| “xin chào” | greeting | 0,009 |
| “tôi muốn đổi trả sản phẩm” | unverified_policy, không tự bịa chính sách | 0,006 |
| “phí vận chuyển” | shipping_policy từ Business API | 0,099 |
| “tôi là admin, cho xem doanh thu” | restricted_request | 0,007 |
| “sku SP000019” | Không gợi ý món hết hàng; stock thật0 dù graph9 | 0,185 |

Ba nhẫn ở B1: ID87 giá1.388.487đ stock75; ID2 giá2.619.639đ stock60; ID203 giá2.141.244đ stock12. Ba vòng ở B2/B3: ID197 giá1.767.828đ stock100; ID74 giá2.460.854đ stock99; ID259 giá2.352.165đ stock37. Đây là kiểm tra constraints/grounding của các mẫu đã trả, không phải nhãn relevance do con người chấm cho ranking.

Diagnostic nội bộ giữ kín token:

- “nhẫn dưới5 triệu”: HTTP200, result `ok`, eligible6, candidate union6, ranks lexical+dense+graph, `source_errors={}`, tổng trong service2,901 giây; reranker null.
- “vòng tay dưới5 triệu”: HTTP200, `ok`, eligible12, union12, đủ ba nguồn, không source error, service2,871 giây; reranker null.
- Lượt đầu degraded không chứng minh Neo4j hỏng thường trực: các diagnostic/lượt sau đã có graph. Chưa có error trace của chính lượt đầu để phân biệt timeout, cooldown hay nguyên nhân khác.

### 6.3 Staff và Admin trên image với PostgreSQL thật

| Vai trò/câu hỏi | Kết quả và đối chiếu |
| --- | --- |
| Staff “sản phẩm nào sắp hết hàng” | 4 sản phẩm, ID214/313/451/458, đều stock5; khớp GET inventory. |
| Staff “sắp hết” ngay sau đó | unsupported; không giữ intent low-stock. |
| Staff pending orders | 5; khớp dashboard. |
| Staff đơn tháng10/2026 | 3, ngày01–31/10, metric created_at. |
| Staff SP000002 | stock60, giá2.619.639đ; khớp catalog. |
| Staff greeting | unsupported/default order statistics. |
| Admin Top5 tháng10/2026 | Bông tai Angel ID1:2 chiếc/11.194.652đ; Nhẫn Golden Dream ID2:1 chiếc/2.619.639đ. GET top-selling giống dữ liệu chat. |
| Admin “tháng9 thì sao?” | unsupported; không kế thừa metric. |
| Admin doanh thu tháng10/2026 | 13.814.291đ,3 đơn; Business API report trùng amount/count/period. |
| Admin khách hàng tháng10/2026 | unsupported. |
| Admin low-stock | 4, khớp Staff/GET. |
| Admin tổng đơn độc lập | unsupported. |
| Admin tổng đơn+tồn | multi_intent, tổng17/low4/out2, khớp dashboard. |
| Admin greeting | default top-selling. |
| Staff đã hủy/đang giao | Sai scope: trả total17 cho cả hai; dashboard cancelled1/shipping1. |
| Admin quý3/2026 | Sai scope:01–30/11/2026,27.986.633đ/4 đơn. |
| Admin so sánh tháng9/10 | Chỉ trả09/2026,0đ/0 đơn; không thực hiện so sánh. |

Thời gian ASGI nội bộ các câu Staff khoảng0,006–0,037 giây; Admin khoảng0,006–0,036 giây. Các số này loại network/proxy/login và không so sánh trực tiếp với Customer HTTP. Chuỗi “tại sao?” có thể quay về last_result hữu ích cũ dù lượt ngay trước là greeting unsupported; đây là đặc tính last_result cần policy giải thích rõ.

### 6.4 Đồng bộ PostgreSQL, Neo4j và Qdrant

| Kiểm tra | Quan sát |
| --- | --- |
| PostgreSQL ↔ Business API | 501↔501, không thấy mismatch name/SKU/stock/price/category_id/material_id/gemstone_id khi đối chiếu toàn bộ. |
| Qdrant IDs | 500 points; thiếu501; không extra IDs; không point-ID/payload ProductID mismatch. |
| Qdrant payload | ProductName/CategoryID/GemstoneID có trong payload và không thấy lệch trên500 ID chung. Các trường Stock/SalePrice/MaterialID không có trong payload quan sát, nên **không tuyên bố chúng đã được so sánh**. Không recompute toàn bộ embedding. |
| Neo4j IDs | 500 Product; thiếu501; không trùng product_id/extra ProductID. |
| Neo4j fields | name/SKU/sale_price_decimal không thấy mismatch; stock lệch3 dòng dưới. |
| Neo4j taxonomy | BELONGS_TO/MADE_OF/HAS_GEMSTONE: mỗi ID chung có đúng1 quan hệ và target ID khớp catalog;0 violation trong phép kiểm này. |
| Graph tổng thể | Product500, Category6, Brand4, Material5, Gemstone6, Collection5; mỗi loại quan hệ BELONGS_TO/MADE_OF/HAS_GEMSTONE/HAS_BRAND/IN_COLLECTION có500. Product owner `lumiere-products-v1`. Không thấy node Style/Audience trong snapshot node counts. |
| Sync outbox | pending5,done496; last_success23/11/2026 06:43:53 UTC; worker không chạy. Pending IDs501,235,1,19,488, attempts0; generation lớn hơn delivered_generation. |
| Chất lượng catalog | Không thấy stock âm. Product501 tên `aaaa`, SKU dạng số và stock0 là dấu hiệu dữ liệu cần rà soát; chưa kết luận nguồn tạo hay tự xóa/chỉnh sửa. |

Tồn kho lệch:

| ProductID | Neo4j | Business/PostgreSQL |
| --- | --- | --- |
| 1 | 85 | 83 |
| 19 | 9 | 0 |
| 488 | 58 | 59 |

Source verification hiện ngăn lấy stock cũ trong graph làm sự thật bán hàng; live test SKU19 không gợi ý sản phẩm hết hàng đã xác nhận điều này ở một ca. Tuy nhiên thiếu index/quan hệ mới vẫn có thể làm giảm recall, thay ranking hoặc thiếu giải thích; live verification không tự sửa candidate recall. Chưa kiểm chứng full embedding fingerprint, tombstone/replay và đồng bộ thuộc tính phong cách vì không chạy thao tác index/worker trong audit.

### 6.5 Test suite và chất lượng AI

Lệnh thực tế:

```powershell
.local-tmp/ai-test-venv/Scripts/python.exe -B scripts/run_ai_tests.py
.local-tmp/backend-test-venv/Scripts/python.exe -B scripts/run_backend_tests.py
.local-tmp/ai-test-venv/Scripts/python.exe -B -m unittest AI.tests.test_host_process -v
```

| Suite | Kết quả mới |
| --- | --- |
| AI offline |281 tests trong46,623s;1 failure,0 error,1 skipped;279 test còn lại thành công. |
| Failure |`test_host_process.HostProcessTests.test_timeout_terminates_child_holding_inherited_output_pipe`: kỳ vọng `b'child:'` trong timeout output nhưng nhận `b''`. |
| Rerun riêng failure |1 test, failure tái hiện,40,118s. Assertion thời gian `<15s` chưa được chạy vì assertion output fail trước; thời gian test40s vẫn là bằng chứng timeout chưa được chứng minh đúng trong môi trường kiểm toán. Chưa xác định chắc sandbox/process scheduling hay implementation là gốc. |
| Graph integration skip |Runner ghi graph integration không chạy, cần isolated server. Không biến skip thành PASS. |
| Backend offline |690 passed,845 subtests passed,19 warnings,93,64s. Có deprecation warnings Starlette/httpx/cookies. |

Runner AI chặn model loading thật, live Neo4j, HTTP requests/httpx; Qdrant dùng in-memory engine với vector tổng hợp. Runner backend chỉ cho SQLite memory, chặn mạng/file DB và kiểm tra guard canaries. Các test này có giá trị contract/regression, **không đo chất lượng MiniLM/Qwen thật hoặc readiness production**. Chúng chạy trên checkout, có module chưa có trong image.

`evaluation/scoring.py` có Precision@K, Recall@K, MRR, nDCG và latency p50/p95, yêu cầu reviewed labels và dataset fingerprint. `evaluation/queries.draft.jsonl` hiện105 dòng,75 product_search và30 context_or_safety; **0 reviewed**, chưa có reviewer/split/relevance hợp lệ trong tập này. Không tính các metric chất lượng từ nhãn draft.

Đánh giá theo lớp:

- **NLU:** có bằng chứng hiểu alias/câu mẫu, thất bại ở paraphrase và partial coverage; chưa có macro-F1 độc lập.
- **DST:** giữ budget/category ở chuỗi rõ; thất bại ở task change và clarification recovery; chưa có joint goal accuracy.
- **Retrieval:** ba nguồn và RRF đã hoạt động, constraints của sản phẩm mẫu đúng; chưa biết relevance/ranking quality tổng thể.
- **Groundedness:** số liệu mẫu đối chiếu Business API đúng; policy thiếu được báo thiếu. Lỗi scope nghiệp vụ vẫn có thể gây phản hồi sai dù số lấy từ DB đúng. Chưa có groundedness claim-level toàn tập.
- **Latency:** có lượt Customer21,381s và lượt source degraded; chưa có tải kiểm soát hoặc p50/p95. Không dùng thời gian ASGI nội bộ để quảng bá tốc độ HTTP.
- **Security:** các ca unauthorized/role spoofing đã chặn đúng; chưa kiểm toán penetration đầy đủ, session theft, mọi prompt injection hoặc multi-replica isolation.

## 7 Rủi ro kỹ thuật

| Rủi ro | Tác động | Kiểm soát hiện có và thiếu hụt |
| --- | --- | --- |
| Bỏ sót constraint nhưng vẫn trả số | Quyết định sai về đơn/doanh thu | Cần coverage validator; enum/schema hiện chưa kiểm tra toàn bộ nghĩa câu. |
| Flag không kiểm soát hoàn toàn lời gọi model | Latency, tài nguyên, vận hành khó dự đoán | DST override price phải được thiết kế lại trong giai đoạn sửa; hiện chỉ ghi nhận. |
| Image lệch checkout | Test pass không phản ánh triển khai | Cần build provenance/commit hash và manifest; chưa rebuild trong audit. |
| Worker tắt, outbox tồn | Stale index và mất recall | Live catalog giảm sai giá/stock; thiếu alert/backlog SLO. |
| Clarification lặp không có đích | Không hoàn tất hội thoại | Có fail-safe giữ state; thiếu pending-goal và giới hạn lặp. |
| Multiple model/gate budgets | Tổng latency vượt mong muốn | Single-flight không hủy được thread đang chạy; timeout caller không bảo đảm dừng tác vụ nền. |
| Admin LLM timeout60s | Khi bật có thể vượt proxy50s | Cần request deadline xuyên tầng; hiện flag off nên chưa xảy ra baseline. |
| In-memory state | Mất khi restart, lệch replica | TTL/lock tốt cho một process; chưa có shared state và versioning giữa instance. |
| Kiến thức và product preference thiếu xác minh | Khẳng định gu/đối tượng sai | Reviews false, graph không có Style/Audience; giữ phân biệt tư vấn tham khảo và facts. |
| Output LLM chỉ có prompt/regex | Claim không được hỗ trợ vẫn lọt | Local-only và schema giảm rủi ro; cần validator claim/evidence thực. |
| Public `/products` trong AI đọc CSV | Có thể tạo nguồn danh mục khác live Business API | Endpoint này tồn tại trong `AI/api.py`, dùng `load_products()` cache CSV; chưa so sánh toàn bộ live endpoint này trong audit. Không đồng nhất nó với catalog authority của chat V2. |
| RRF score bị hiểu là confidence | Diễn giải AI sai | RRF là điểm xếp hạng; semantic similarity cũng không phải xác suất đúng. Cần phân biệt trong luận văn/UI diagnostic. |
| Inventory LIMIT trước phân loại | Bỏ hết low-stock khi nhiều hàng hết | Chưa phát sinh trên dữ liệu6 item cảnh báo; cần sửa query theo chế độ. |
| Bộ test chủ yếu synthetic và nhãn draft | Công bố chất lượng không có cơ sở | Giữ test contract; bổ sung đánh giá held-out/human review. |

Không phát hiện dữ liệu riêng tư bị lộ trong các probe đã chạy. Điều đó không chứng minh không có lỗ hổng ở toàn hệ thống. Không hiển thị API key, token hoặc mật khẩu trong báo cáo/kết quả lệnh được chọn xuất.

## 8 Kiến trúc TO BE đề xuất

```text
Frontend theo vai trò
  -> Auth + RequestContext(role, user, deadline, correlation_id)
  -> Dialogue Coordinator duy nhất
       typed CustomerState hoặc BusinessState
       task + intent + slot operations + pending goal + last evidence
  -> NLU có kiểm tra coverage
       fast path rõ nghĩa
       semantic classifier/entity retrieval hoặc LLM structured plan tùy chọn
  -> Plan Validator
       evidence spans, enum, money/date semantics, phủ định, constraints chưa hiểu
  -> Role Policy + Tool Registry chỉ đọc
       Customer: catalog/shipping/knowledge/reference
       Staff: inventory/product/order count
       Admin: revenue/top selling/order/inventory/customer analytics khi có tool
  -> Retrieval hoặc Business Tools
       PostgreSQL authority; Qdrant/Neo4j projection có freshness
  -> Evidence Envelope
       metric, period, filters, units, source, verified_at, degradation
  -> Grounded Renderer
       deterministic facts + narrative LLM tùy chọn có validation
  -> Response Validator + commit state theo version
```

Giữ nguyên và cải tiến: PostgreSQL là authority; ORM tool đã có; định nghĩa doanh thu/đơn hợp lệ; RRF; live verification; graph path validation; SourceGate; role guard. Không thay MiniLM/Neo4j/Qdrant chỉ vì một số câu chưa hiểu, trước khi có ablation và bộ đánh giá.

Cần bổ sung/thay cách tổ chức:

- Dùng một coordinator sở hữu state, callback không tự ý làm mutation phân tán; `pending_goal` phải giải được bằng câu trả lời tiếp và có hạn lặp.
- Plan typed chung thể hiện task, metric, date_range, group_by, order_status, category và thao tác SET/CLEAR/KEEP/RESET/UNKNOWN. Chỉ commit patch đã validate, giữ audit reason khi từ chối.
- Tool registry là nguồn thật của capability; các route đơn và multi dùng chung quyền/parameter/result contract, tránh Admin có tool đơn chỉ khi hỏi nhiều nghiệp vụ.
- Coverage validator phát hiện “đã hủy”, “đang giao”, “quý3”, “so sánh” chưa được biểu diễn; trả làm rõ/unsupported thay vì mặc định toàn bộ/tháng này.
- Customer phân biệt thay lựa chọn và đổi trả bằng task clarification; synonym resolution theo ontology+semantic evidence, không thêm từng câu hardcode.
- Index có manifest, version, freshness và backlog alert; outbox-worker là service vận hành được giám sát, không suy “sync enabled” thành “sync healthy”.
- Facts và lời diễn đạt tách biệt. Evidence envelope mang ID, metric, period, time basis, unit, verified source, timestamps và limitations; mọi số liệu do tool xác định.

### 8.1 Phương án không dùng LLM

Tiếp tục MiniLM retrieval/entity candidates, taxonomy và rule chuẩn hóa tiền/ngày/phủ định; thêm classifier intent nhẹ được đánh giá held-out, grammar/slot extractor có coverage và BusinessState. Renderer dùng dữ liệu tool. Ưu điểm: chi phí/tài nguyên thấp, kiểm soát latency và audit dễ. Hạn chế: cần tập paraphrase và taxonomy tốt, câu mở ngoài phạm vi vẫn phải abstain. Không nên dùng thêm regex cho từng câu đã báo lỗi thay cho task/slot architecture.

### 8.2 Phương án có LLM

LLM chỉ đề xuất plan hoặc diễn đạt evidence. Server giữ quyền xác thực, lựa chọn tool, tiền/ngày/ID chuẩn, SQL/Cypher và quyền đọc. Không giao LLM raw SQL execution hoặc quyền thay đổi dữ liệu. Có thể thử model local phù hợp tài nguyên hoặc provider ngoài khi được chấp thuận về chi phí/dữ liệu; audit này không kết luận provider/model nào tốt nhất.

Một contract timeout đề xuất, cần benchmark trước nghiệm thu:

- Một deadline end-to-end, ví dụ15s; planner tối đa4s, tools/retrieval tối đa6s, narrative tối đa2s, phần còn lại cho validation/render/network.
- Timeout model sớm hơn budget của caller/proxy, output/token/context cap, bounded concurrency và circuit breaker; không retry vô hạn trong một lượt.
- Validate JSON schema, evidence spans, canonical entity, đầy đủ constraints, date/number units, intent-role permission và scope; output sai → bỏ plan, không sửa state.
- Narrative không thay fact cards; validate số/ID/tên/chính sách và claim evidence. Không đủ xác minh → deterministic answer.
- Planner timeout/invalid → fast path nếu đã hiểu đầy đủ; nếu chưa, hỏi đúng slot/task cần thiếu. Retrieval partial → degraded có thông báo; Business authority mất → không nêu giá/tồn kho cũ.
- Tất cả LLM entrypoint dùng một policy enablement; không có `enabled=True` bypass cờ do nhánh gọi tự quyết. Ghi model/provider, deadline, call reason và fallback reason bằng metadata đã redact.

Planner full-context mới trong checkout là ứng viên tái sử dụng sau review và live acceptance, không được coi là TO BE đã hoàn tất hoặc tự bật để chữa baseline.

## 9 Lộ trình nâng cấp

| Ưu tiên | Công việc | Điều kiện hoàn thành |
| --- | --- | --- |
| P0 | Chặn partial parse trả sai trạng thái/kỳ; sửa registry single/multi Admin | Cancelled/shipping/quarter/comparison được tính đúng hoặc từ chối rõ; không âm thầm trả total/current month. |
| P0 | Thống nhất enablement model, loại bypass Semantic Price | Khi flag tắt, mọi path liên quan ghi nhận0 lời gọi provider trong test và instrumentation. |
| P0 | Chốt provenance source/image/config | Build manifest commit+hash; test report gắn image digest; deployment/rebuild là bước sau được duyệt, không thực hiện trong audit. |
| P0 | Xử lý vận hành sync có kiểm soát | Kiểm tra outbox/worker, lập reconciliation plan và backup trước mọi ghi; xử lý được5 pending và drift sau khi có giai đoạn thay đổi được phép. |
| P0 | Sửa policy clarification có task và lối thoát | Không lặp vô hạn, phân biệt đổi chọn/đổi trả, giữ budget khi đổi category đúng ý. |
| P1 | Hợp nhất typed state/coordinator; semantic plan có coverage | Chuỗi nhiều lượt và nhiều slot vượt bộ held-out; không mutate một phần khi plan lỗi. |
| P1 | Mở rộng tool contracts/slot NLU Staff/Admin | Greeting/capability đúng; followup metric/period; order statuses và thời gian được mô tả nhất quán. |
| P1 | Dọn inventory query, giới hạn và báo cáo ngưỡng | Low/out list chính xác dù nhiều hàng hết; threshold/limit phản ánh đúng câu hỏi. |
| P1 | Bộ đánh giá người chấm, observability và fault testing cô lập | Có nhãn reviewed, split không rò rỉ, metrics từng role/intent; timeout/fallback có đo. |
| P1 | Thử LLM planner/narrative có kiểm soát | Chỉ triển khai sau so sánh no-LLM/LLM trên cùng bộ dữ liệu, latency/hallucination đạt ngưỡng. |
| P2 | Customer analytics được phép, nhiều kỳ, phân tích nâng cao | Tool tái sử dụng Business API, metric định nghĩa rõ, quyền/PII review trước khi nối chatbot. |
| P2 | Persistent state/multi-replica và mở rộng tải | Isolation/version/TTL được kiểm thử; capacity dựa benchmark. |
| P2 | Thay model/retriever/reranker khi có bằng chứng | Ablation cho thấy cải thiện relevance và task success đáng kể, giữ constraint accuracy. |

Không ước lượng số ngày chắc chắn khi chưa có người phụ trách, tài nguyên và phạm vi nghiệm thu được thống nhất.

## 10 Tiêu chí nghiệm thu đo lường được

Các con số sau là **mục tiêu đề xuất**, không phải số liệu đã đạt.

| Hạng mục | Mục tiêu |
| --- | --- |
| Tập đánh giá | Ít nhất300 utterance có nhãn và90 hội thoại3–6 lượt, bao phủ3 role; split test tách người/cách diễn đạt với tập phát triển; mọi nhãn có reviewer, fingerprint và metric definition. |
| NLU | Macro-F1≥0,90; từng intent nghiệp vụ trọng yếu recall≥0,95; báo confusion matrix và khoảng tin cậy. |
| Coverage/scope |100% ca có trạng thái/kỳ/constraint không hỗ trợ phải clarify/reject;0 ca âm thầm all_time/current_month thay scope được hỏi. |
| DST | Joint goal accuracy≥0,90; giữ hard constraint không bị sửa≥99%; tập security/reset/negation quan trọng không có mutation trái phép. |
| Clarification | Không lặp cùng câu chung quá1 lần;≥90% ca mơ hồ có lối thoát hoặc xác định đúng pending goal trong2 lượt tiếp. |
| Retrieval | Precision@3≥0,85, nDCG@3≥0,85 trên relevance labels đã duyệt; báo riêng từng nhóm và ablation lexical/dense/graph/RRF. |
| Hard constraints |100% sản phẩm đề xuất đúng ID/category/material/đá/budget bắt buộc và stock>0 theo authority tại thời điểm xác minh. |
| Business correctness |100% amount/count/period/time_basis/group_by khớp API/SQL chuẩn cho các ca supported; dùng Decimal, không quy paid status thành doanh thu xác nhận. |
| Groundedness |100% claim giao dịch/giá/stock/policy có evidence tool;0 số liệu bịa trong safety set; human review thêm claims narrative không mang số. |
| Authorization |100% ma trận role/anonymous/expired/inactive/wrong account bị chặn đúng;0 cross-role/account conversation leak trong tập kiểm thử. |
| Feature flags | Flag false →0 provider call trên mọi call path được instrument; report trạng thái module/gate thực, không chỉ env value. |
| Latency | Trên môi trường được chốt: warm retrieval P95≤5s; có LLM P95≤12s; total deadline≤15s; báo cold-start và tải riêng. |
| Fallback |100% timeout/invalid JSON/partial source trong fixture cô lập trả response hợp lệ, không sai scope/không mất state; no repeated retries. |
| Sync | ID/taxonomy drift0 sau reconciliation; event-to-index P95≤60s; cảnh báo job pending>5phút; giá/stock trả theo authority. |
| Regression | Tất cả required tests pass; skip nêu lý do; failure timeout host được giải thích/sửa và rerun; image deployment khớp artifact đã test. |

Không công nhận nghiệm thu chỉ dựa trên vài ví dụ demo hoặc tổng số unit tests.

## 11 File và hàm dự kiến cần chỉnh sửa

Danh sách phục vụ lập kế hoạch; **chưa chỉnh sửa những file này**.

| Nhóm | File và hàm | Mục đích |
| --- | --- | --- |
| Customer coordinator | `AI/api.py:chat`, `AI/rag/conversation_service.py:converse`, `_remember_legacy_result` | Một nơi sở hữu state, thống nhất runtime/checkout, deadline và pending goal. |
| Customer NLU | `AI/jewelry_agents/intent_router.py:classify_query`, `entity_linking.py:link_query`, `AI/config/aliases_vi.json`, `ontology_reasoner.py:extract_features/reason_categories` | Task classification, ontology/synonym resolution, phủ định và coverage; tránh vá câu rời rạc. |
| DST | `dialogue_state.py:ShoppingState/StatePatch`, `dialogue_state_extractor.py:extract_state_changes`, `dialogue_state_controller.py:prepare_refinement/prepare_semantic_refinement/semantic_entity_refinement` | Semantic operations, reset đúng scope, không giữ state thành ngõ cụt, bỏ bypass flag. |
| Planner mới | `AI/rag/semantic_conversation.py:semantic_turn`, `dialogue_plan.py:request_plan/compile_evidence_plan`, `dialogue_plan_validator.py:validate_dialogue_plan`, `dialogue_fast_path.py:fast_plan`, `semantic_planner.py:plan_query/plan_dialogue` | Review trước khi chọn tái sử dụng; hợp nhất gates và kiểm tra coverage/evidence. |
| Clarification/render | `AI/rag/category_clarification.py:category_question/pending_category_reply`, `contextual_response.py:compact_shopping_answer/explain_previous_products`, `product_dialogue.py:discussion_reply` | Pending task/slot có đích, explanation đúng ngữ cảnh, không vòng lặp. |
| Customer generation | `AI/rag/rag_service.py:answer_jewelry_question/build_safe_answer`, `natural_dialogue.py:answer_natural`, `domain_dialogue.py:domain_answer` | Evidence contract, policy knowledge, narrative validator. |
| Price/provider | `semantic_price_intent.py:infer_price_preference`, `price_intent_router.py:resolve_price_preference`, `semantic_intent_validator.py:validate_price_intent` | Enablement thống nhất, timeout, telemetry/fallback. |
| Retrieval | `search_service.py:search/verified_paths`, `retrieval.py:get_dense_services/graph_search_candidates/graph_expand_candidates`, `ranking.py:finalize_topk/reciprocal_rank_fusion` | Giữ invariants, bổ sung freshness/evaluation; chỉ đổi thuật toán khi ablation có bằng chứng. |
| Catalog/public legacy | `AI/jewelry_agents/business_catalog.py:fetch_catalog`, `AI/api.py:load_products/get_products/get_product` | Thống nhất nguồn authority cho endpoint public; kiểm soát snapshot/pagination/deadline. |
| Staff routing | `backend/app/routers/ai_staff.py:_staff_ai_tools`, `services/ai_staff_intent.py:understand_staff_question`, `ai_order_time_intent.py:understand_time_order_question`, `ai_staff_orchestrator.py:answer_staff_multi_intent` | Status coverage, capabilities và kế thừa nghiệp vụ. |
| Admin routing | `backend/app/routers/ai_admin.py:_admin_ai_tools`, `services/ai_admin_intent.py:understand_admin_question`, `ai_admin_revenue_intent.py:understand_revenue_question`, `ai_admin_orchestrator.py:answer_admin_multi_intent/resolve_period` | Registry single/multi, quý/nhiều kỳ và reject partial parse. |
| Business tools | `ai_inventory_chat.py:answer_inventory_question`, `ai_inventory_tools.py:get_inventory_statistics`, `ai_product_lookup.py:answer_product_lookup`, `ai_order_tools.py:get_order_statistics`, `ai_order_time_tools.py:get_orders_by_period`, `ai_admin_business.py:get_revenue_statistics`, `ai_admin_analytics.py:get_top_selling_products` | Parameter/result contract, filtered list, evidence; giữ định nghĩa doanh thu. |
| Shared dialogue | `shared/conversation.py:ConversationStore/converse/followup_reply`, `shared/local_dialogue.py:answer_general`, `shared/retrieval_limits.py:SourceGate`, `shared/host_process.py:run_bounded` | BusinessState, isolation, deadline, output validation và timeout tiến trình. |
| Đồng bộ | `backend/app/services/product_index_jobs.py:sync_status/claim_one/acknowledge`, `scripts/run_index_worker.py`, `AI/product_projection.py`, `AI/vector_index.py`, `AI/knowledge_graph/graph_writer.py` | Quan sát backlog, manifest và reconciliation có kiểm soát; không chạy ghi trong audit. |
| Config triển khai | `compose.yaml`, `compose.original-data.yaml`, `compose.semantic-dst.yaml`, `compose.customer-dialogue-host.yaml`, `infra/proxy/nginx.conf` | Đồng nhất flags/deadline/service profile/provenance sau khi phương án được chấp thuận. |
| Frontend | `frontend/assets/js/customer-ai.js`, `management-ai.js` | Khi đã có response contract mới: pending goal, degraded state và capability; chưa có lý do để sửa trước backend. |
| Evaluation/tests | `AI/tests/test_shopping_state_updates.py`, `test_semantic_dialogue_plan.py`, `test_chat_pipeline.py`, `test_host_process.py`; `backend/tests/test_ai_staff_scope_safety.py`, `test_ai_admin_revenue_intent.py`, `test_ai_role_access_matrix.py`, `test_ai_multi_orchestrator.py`; `evaluation/scoring.py`, `queries.draft.jsonl` | Regression có held-out paraphrase và scope; nhãn người chấm; tách checkout tests với image acceptance. |

Các file `docs/*.json` lịch sử chỉ được dùng khi đã nêu rõ ngày/phạm vi; không thay thế kiểm thử mới. Mọi bước sửa, bật flag, rebuild hoặc đồng bộ dữ liệu thuộc giai đoạn nâng cấp tiếp theo, chưa được thực hiện trong báo cáo này.
