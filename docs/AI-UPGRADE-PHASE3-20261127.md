# LUMIÈRE AI Upgrade — Phase 3: Customer AI

Ngày 27/11/2026, Asia/Bangkok. Workspace `D:\LUMIERE-FINAL-TEST`, branch `update-ai`, HEAD giữ nguyên `1a432c170164fa9eeb07a189d6c0edd306713f67`.

**Trạng thái bàn giao: source đã sửa, regression cô lập PASS; CHƯA triển khai, CHƯA live acceptance, không công bố Phase 3 hoàn thành toàn bộ.** Phase 1 live acceptance là bằng chứng lịch sử của Phase 1. Phase 2A được bảo toàn; Phase 2B tiếp tục tạm hoãn theo quyết định người dùng, không chạy worker hoặc xử lý drift trong phiên này.

## 1. Baseline và phạm vi

Đã đọc ba báo cáo audit/Phase 1/Phase 2; ưu tiên trạng thái cuối mục 13 Phase 1 và mục 13.6 Phase 2. Containers được báo cáo đang dừng sau restart. Phiên Phase 3 không gọi Docker, không khởi động service để đo lại trạng thái, không dùng các số pending/drift lịch sử làm số đo mới.

Checkout đầu phiên có nhiều thay đổi Phase 1/2 và frontend chưa commit. Đã lưu SHA-256 các file dirty/untracked đầu phiên trong `.local-tmp/phase3/baseline.json`. Cuối phiên, 45 file baseline không thuộc ba file Customer cần sửa tiếp vẫn khớp hash; toàn bộ source Phase 2A, frontend, Staff/Admin, Dockerfiles và scripts worker được bảo toàn. Ba file baseline sửa tiếp là `dialogue_state_controller.py`, `test_shopping_state_updates.py`, `test_phase1_price_gate.py`; thay đổi Phase 1 về gate price không bị hoàn nguyên.

Không đổi Hybrid Retrieval, embedding model/revision, Neo4j, Qdrant, RRF, graph schema, Business API authority hoặc facts sản phẩm. Chỉ mở rộng synonym trong ontology alias hiện có, không đổi category IDs hay taxonomy. Không thay config/LLM flags, tải model, tạo dữ liệu nghiệp vụ, sửa frontend/auth/commerce hoặc Staff/Admin. Không commit/push/merge/chuyển branch hoặc Phase 4.

## 2. Kiến trúc trước và sau

Trước: `/chat` → Customer `conversation_service.converse` với ConversationStore có scope/TTL/lock → pending category / discussion / shared followup → DST hoặc planner tùy gate → RAG → hybrid search → Business verification → renderer. Nhánh full-context `semantic_turn` đã tồn tại nhưng opt-in; deterministic coordinator vẫn là đường hoạt động khi gate tắt.

`ShoppingState`/`StatePatch`, entity linker, ontology reasoner, numeric parser, typed `DialoguePlan`/validator và SourceGate đã có sẵn. Vấn đề nằm ở chuyển tác vụ, biểu diễn alias, pending goal và những nhánh return sớm; không cần thay retriever hay dựng hệ thống mới.

Sau:

```text
/chat → ConversationStore scope + per-conversation lock
      → cheap Customer control policy
          greeting / capabilities / cancel / reset / exchange disambiguation
          entity-negation + incompatible-material validation
      → existing deterministic coordinator
          typed slot patch + pending clarification/refinement
          previous ranked cards + last selected product ID
          ontology category clarification with bounded reminder
      → existing RAG / hybrid retrieval / final Business authority checks
      → existing grounded renderer + coordinator state/result commit

Optional full-context planner remains separately gated.
Control policy runs before that branch; no new LLM enablement.
```

Một coordinator tiếp tục sở hữu state. Hard slots nằm trong `ShoppingState`; preference phong cách/đối tượng trong tư vấn được giữ ở advisory context, không biến thành facts đã xác minh. Giữ nguyên snapshot của danh sách trước để giải thích/tham chiếu, không thay bằng danh sách mới khi search rỗng hoặc nguồn lỗi.

## 3. Nguyên nhân lỗi và sửa source

| Vấn đề | Nguyên nhân trước | Thay đổi |
| --- | --- | --- |
| “Còn vòng đeo tay” | Alias cần cụm liên tục; “vòng tay” không match “vòng đeo tay” | Thêm synonym cấp entity `bracelet` vào cấu hình hiện hữu, version 4; category refinement dùng lại DST, không thêm nhánh câu đặc biệt |
| “Tôi muốn đổi sản phẩm” | Không biết đang đổi lựa chọn hay đổi trả món đã mua | Task speech acts theo động từ, phạm vi sản phẩm/slot và ngữ cảnh mua; lưu pending goal `exchange`, nhận câu tiếp theo hoặc hỏi đúng tác vụ |
| “Đổi nhu cầu khác” | Reset chỉ chạy sau khi có slot update; câu không có slot rơi vào semantic/fallback | Reset task độc lập trước NLU/retrieval; bỏ state, pending goals, result/reference cũ; có thể nhận ngân sách trước category |
| Lặp câu làm rõ | Generic early return chỉ ghi history, không goal/attempts | `PendingClarification(goal, attempts)`; lần unresolved tiếp chuyển sang thông báo tạm dừng, nêu cách tiếp tục/reset/hủy thay vì hỏi lại chung chung |
| Pending category lặp | Không giới hạn reminder, có thể khởi tạo dense services cho câu ngắn chưa rõ | Một reminder rồi suspend; dùng encoder đã nạp và SourceGate budget 4 giây, không load model vì clarification |
| Budget bị mất khi chưa có category | `prepare_state` yêu cầu category nên gift/budget-only không có typed state | Cho coordinator tạo partial state; câu category tiếp theo giữ budget/material/gemstone đã biết |
| Áp một phần khi thiếu slot | Câu đổi material + budget có thể chỉ áp budget | Defer toàn bộ lượt vào pending refinement; trả lời material sẽ ghép yêu cầu trước và validate rồi mới truy xuất/commit |
| “Bỏ giá sàn” bỏ cả budget | Grammar “bỏ giá” match prefix của “bỏ giá sàn” | CLEAR có scope floor/ceiling; chỉ bỏ cận được nêu, reset exclusive của cận đó |
| Phủ định/multiple materials | Entity dương có thể được trích từ câu phủ định; material parser chọn giá trị đầu | Reuse positive-entity validation, reject material alternatives chưa xác định; chưa hiểu thì giữ state và làm rõ |
| Negated price bị xem là negated entity | Validator thấy “đừng quá” và loại cả category từ mô tả đeo | Tách numeric boundary negation khỏi entity negation, bảo toàn đường ontology/planner cũ |
| Similar theo ordinal | Related retrieval cần catalog ID, discussion biết ordinal nhưng chưa nối hai contract | Compile vị trí thẻ → ProductID thật → existing related retrieval; ghép hard constraints hiện tại |
| “Mẫu đó” sau chọn mẫu thứ hai | Chỉ có last ranked list, thiếu last selection | Lưu selected ID từ discussion, resolve deictic trên đúng danh sách cũ; danh sách mới/reset xóa selection |
| Style context lỗi thời sau đổi tác vụ | Advisory text có thể đi theo tác vụ viết | Tác vụ viết kết thúc advisory/pending context; giữ hard slots để người dùng chủ động tiếp tục refinement |

Không có câu mẫu audit nào được hardcode làm kết quả trong runtime. Alias là primitive miền trang sức; task/slot grammar là quy tắc thao tác có phạm vi, không phải bảng câu hỏi/trả lời mẫu. Cách diễn đạt ngoài grammar vẫn có thể abstain.

## 4. Typed transitions và contract Phase 6

| Operation | Hành vi |
| --- | --- |
| SET | Cập nhật field được hiểu; các field không nêu giữ nguyên |
| KEEP | Giữ field cũ; không suy việc đổi category thành đổi budget/material/gemstone |
| CLEAR | Chỉ bỏ field có yêu cầu rõ; giá sàn/trần độc lập, clear cận cũng clear exclusive flag |
| RESET | Chỉ reset toàn task có dấu hiệu rõ; dọn pending và tham chiếu, không xóa lịch sử scope/lock |
| UNKNOWN | Biểu diễn slot chưa rõ, không tự clear; pending material/gemstone defer phần đã biết của cùng lượt |

`StatePatch` kiểm tra field/operation conflict ngay lúc khởi tạo; `operations()` biểu diễn cả UNKNOWN và task RESET. Giữ nguyên wire schema `DialoguePlan` với evidence quotes, typed enum, numeric grounding, atomic validator và provider gate độc lập để Phase 6 có thể tái sử dụng. Deterministic Customer không phụ thuộc việc có provider/planner trả lời.

Khi retrieval thành công nhưng rỗng: commit constraint mới hợp lệ, không tự nới. Khi refinement lỗi authority/timeout: giữ state và card snapshot trước, thông báo điều chỉnh chưa áp dụng; không coi timeout là “catalog không có mẫu”. Reset đã được yêu cầu thì có hiệu lực riêng, không phục hồi task cũ chỉ vì lượt search sau đó lỗi.

Chưa hợp nhất hai coordinator deterministic/full-context thành một state machine mới. Full-context planner vẫn là đường opt-in hiện hữu; kiểm thử mock contract không phải nghiệm thu model thật hay cam kết toàn bộ paraphrase.

## 5. Nhóm chức năng Customer

| Nhóm | Kết quả trong source/kiểm thử cô lập |
| --- | --- |
| Greeting/điều hướng | Greeting primitives có dấu/không dấu, capability, cancel/reset trả lời không retrieval/planner; cả hai trạng thái hybrid gate được mock kiểm tra |
| Multi-attribute search | Category/material/gemstone/budget/count tiếp tục dùng parser, renderer và eligibility hiện hữu; đổi category giữ các hard slots còn phù hợp |
| Quà tặng/phong cách | Dùng lại advice planner/intro/knowledge và advisory retrieval; giữ partial budget và context qua refinement; không gán style/audience chưa verified cho sản phẩm |
| So sánh/giải thích | Reuse discussion/contextual renderer; so giá/material/đá/stock từ Business catalog được kiểm tra lại, không dùng giá cũ khi timeout |
| Similar/reference | Reuse graph relations và catalog ID resolver; ordinal/deictic được compile đúng ID, không lấy vị trí 2 làm ProductID 2 nếu card thực tế khác |
| No results/ambiguous/out of scope | Rỗng giữ hard slots; ambiguous/negative không hiểu không search rộng; clarification có lối thoát; policy/nội bộ tiếp tục guard hiện hữu |

Tư vấn phù hợp quà/phong cách vẫn là định hướng chọn lựa, không chứng minh sản phẩm có nhãn phong cách, hợp một người cụ thể hoặc có đặc tính chưa được nguồn xác nhận. Không tạo chính sách đổi trả; chỉ hướng dẫn liên hệ khi chính sách chưa được xác minh. Không thực hiện đổi trả/đặt hàng trong chat.

## 6. Files thêm/sửa của Phase 3

Không thêm module source hoặc test file mới. Sửa 13 file hiện hữu:

| File | Nội dung chính |
| --- | --- |
| `AI/config/aliases_vi.json` | Entity synonym và alias version |
| `AI/jewelry_agents/dialogue_state.py` | UNKNOWN/RESET operation metadata, conflict validation, typed pending goal |
| `AI/jewelry_agents/dialogue_state_controller.py` | Partial state, task speech acts, missing-slot atomicity, positive-entity check |
| `AI/jewelry_agents/dialogue_state_extractor.py` | Material ambiguity, bare budget normalization, floor/ceiling clear |
| `AI/jewelry_agents/dialogue_plan_validator.py` | Numeric negation scope không loại ontology entity |
| `AI/jewelry_agents/intent_router.py` | Greeting grammar |
| `AI/rag/conversation_service.py` | Control/pending/state/reference/advisory coordination |
| `AI/rag/category_clarification.py` | Bounded reminder, loaded encoder only, bounded semantic call |
| `AI/rag/product_dialogue.py` | Related-card reference → existing ProductID contract |
| `AI/tests/test_shopping_state_updates.py` | Thêm 17 test methods Customer, nhiều paraphrase/subtests và hội thoại nhiều lượt |
| `AI/tests/test_category_clarification.py` | Thêm 1 test bounded clarification/no-load; mock đúng bounded gate API |
| `AI/tests/test_phase1_price_gate.py` | Giữ zero-provider assertions; cập nhật expectation alias đã được nhận diện |
| `AI/tests/test_shopping_consultation.py` | Assertion budget theo giá trị parser thay literal “3 triệu” khi query được canonicalize |

File báo cáo mới duy nhất: tài liệu này. Harness và bằng chứng nằm `.local-tmp/phase3/`, không tạo báo cáo Markdown phụ hoặc source backup.

## 7. Regression và bằng chứng

Các lượt test chạy tuần tự bằng venv hiện có; không cài dependency/model. Safe runner chặn model construction, HTTP requests/httpx, graph driver và dotenv; Qdrant contract tests dùng engine in-memory với synthetic vectors, không dùng index thật. Các case gate=true chỉ bật trong process test với provider mock.

| Kiểm tra cuối | Kết quả / artifact |
| --- | --- |
| Toàn bộ AI suite | **315 tests run, 0 failures, 0 errors, 1 skip; 314 không skip PASS**. `.local-tmp/phase3/ai-regression-final.json` và `.log` |
| Host timeout gốc trong full suite | PASS ngoài sandbox với guard runner giữ nguyên; không sửa `shared/host_process.py` hoặc assertion |
| Customer DST mới | 17 test methods thêm, gồm paraphrase/có dấu/không dấu/câu rút gọn/negation, reset, support, pending atomicity, references, zero retrieval navigation, no-result retention và timeout |
| Category clarification | 1 test mới: một reminder rồi suspend, không load encoder mới |
| Replay hội thoại | **7 scenarios, 28 lượt**; `.local-tmp/phase3/customer-replay.json`, harness `replay_customer.py`; fixture 3 sản phẩm, catalog/retrieval mocked, không phải catalog thật |
| Syntax/JSON/check whitespace | AST/JSON parse 13 file PASS; scoped `git diff --check` exit 0, chỉ warning CRLF normalization |
| Source preservation | `.local-tmp/phase3/source-validation.json`: hash source cuối, HEAD/branch, file baseline giữ nguyên; source Phase 2A không đổi |
| Business Backend suite | Không chạy lại: không sửa backend/shared/auth/commerce; không lấy kết quả backend lịch sử làm kết quả Phase 3 |

Full suite cuối bao gồm regression Customer trước đây, consultation, contextual discussion, ontology/entity linking, public intent guards, Phase 1 feature gates, typed semantic planner validation/timeout và contract retrieval/grounding. Không cộng các lần chạy lặp thành số lượng test độc lập.

Lịch sử lỗi trong artifacts được giữ: lượt full sandbox đầu chạy 309 tests có host timeout môi trường và expectation Phase 1 cũ rằng alias wrist chưa hiểu. Lượt sau phát hiện numeric negation scope và advisory task context; đã sửa source, chạy lại các test liên quan và full suite cuối PASS. Không hạ assertion timeout, nới provider gate hoặc skip để đạt PASS. Một assertion consultation đổi từ chuỗi đơn vị tiền sang cùng giá trị tiền được parse; assertion provider zero-call vẫn giữ nguyên.

Thời gian `6,586s` trong log cuối là thời gian chạy unit/mock suite trên host, **không phải latency của chatbot**. Không có accuracy/F1, retrieval relevance score, hallucination rate hoặc P95 live được đo trong phiên này.

## 8. Hội thoại before/after

Before lấy từ audit live ngày 27/11; after dưới đây là source với fixture offline, không phải live acceptance.

| Chuỗi / lượt | Before | After trong replay/test |
| --- | --- | --- |
| Nhẫn bạc dưới 5 triệu → “Còn vòng đeo tay” | Clarification chung, có lúc chờ semantic dài | State bracelet + silver + max 5 triệu; fixture không có vòng nên trả rỗng đúng constraints |
| Tiếp “Tôi muốn đổi sản phẩm” | Lặp cùng câu chung | Hỏi đổi mẫu tư vấn hay đổi sản phẩm đã mua; không retrieval/model |
| Tiếp “Đổi nhu cầu khác” | Không thoát generic clarification | Reset, hỏi category cho task mới; ngân sách/chất liệu cũ và reference cũ được dọn |
| Tiếp “dưới 2 triệu” → “bông tai” | Dễ mất phạm vi đã nói | Partial max 2 triệu rồi category earring, không tái nhập bạc/5 triệu cũ |
| “đổi món khác” → “món đã mua rồi” | Không phân biệt tác vụ | Support guard, không khẳng định chính sách, giữ shopping constraints nhưng không tìm món thay thế |
| “đổi chất liệu và ngân sách dưới 3 triệu” → “vàng 18K” | Có thể áp budget trước khi rõ material | Hỏi material, giữ state trước; câu đáp hoàn tất cả material và max 3 triệu |
| “chưa chắc lắm” → “vẫn chưa rõ” → “hủy” → category | Generic question lặp | Một câu hỏi, rồi thông báo tạm dừng với lối thoát; cancel giữ hard slots, category tiếp nối được |
| Mẫu thứ hai → “mẫu đó” → tìm tương tự | Ordinal/deictic chưa nối related ID contract | Đúng selected ID, giữ nguyên thứ tự card; related query kèm budget/material hiện tại |
| Ruby từ 1–4 triệu → “bỏ giá sàn” | Prefix clear có thể xóa hai cận | Chỉ min_price=None, max_price=4 triệu, gemstone vẫn ruby |

Giá/tên/tồn kho trong replay là fixture; không sử dụng làm thông tin tư vấn bán hàng thực tế.

## 9. BLOCKED và giới hạn

- **BLOCKED — live acceptance**: containers đang được để dừng theo giới hạn tài nguyên; không build/recreate hoặc bật stack trong Phase 3.
- **BLOCKED — index consistency/relevance**: không đối chiếu SQL–Neo4j–Qdrant thật, không sửa drift, không xử lý backlog/worker. Những ca freshness, recall/ranking trên index thật, graph paths thật và thay đổi authority trong lúc retrieval phải chờ điều kiện môi trường/index consistency; unit fixtures không chứng minh chúng.
- **BLOCKED — real-server graph integration**: 1 skip yêu cầu isolated server, không coi skip là PASS.
- **NOT EVALUATED — model thật và chất lượng hội thoại tổng quát**: không load MiniLM/LLM hoặc đánh giá held-out human-reviewed. Grammar/alias có phạm vi hữu hạn; negative exclusion phức tạp và các lựa chọn nhiều vật liệu chưa được biểu diễn thành filter sẽ làm rõ thay vì tự chọn/nới.
- **NOT EVALUATED — end-to-end latency/capacity/cold start**: chỉ kiểm tra call suppression và mock timeout contracts; không suy latency từ unit duration hoặc đặt benchmark chưa có bằng chứng.
- Full-context planner vẫn có policy riêng hiện hữu, không được bật/triển khai/đánh giá bằng model trong phiên này. Shared store vẫn process-local, TTL/bounded; chưa có persistent/multi-replica dialogue state.
- Source policy không có văn bản đổi trả đã xác minh; không thêm workflow thực hiện đổi trả. Tư vấn phong cách giữ advisory scope, không suy facts cá nhân hóa từ thuộc tính bán hàng.

## 10. Kế hoạch triển khai — chưa thực hiện

1. Review source diff theo 13 file và artifact cuối; kiểm tra hash baseline Phase 2A/frontend và gates giữ nguyên. Không đưa thay đổi worker vào runtime chỉ vì source cùng checkout.
2. Trước mọi build/recreate phải có phê duyệt riêng và đủ RAM/disk. Giữ rollback image AI Phase 1, ghi source manifest/provenance mới và so checksum nội dung image; build tuần tự đúng phạm vi AI service được duyệt, không khởi động toàn stack hoặc index-worker.
3. Chạy offline guard tests trên nội dung image mới; xác minh gate=false có zero provider calls, dependencies/imports, policy và scope. Không bật thêm LLM flags để làm demo PASS.
4. Khi môi trường phục vụ được phép khôi phục, đối chiếu Business authority bằng read-only, đánh dấu rõ các ca index-dependent còn BLOCKED nếu Phase 2B chưa giải quyết consistency. Không gộp quyền triển khai Customer với quyền sửa index/dữ liệu.
5. Live Customer acceptance qua proxy thật: chuỗi audit và paraphrases, cả phiên mới/đang shopping; category/budget/material/gemstone CLEAR/KEEP; reset/cancel; đổi trả đã mua; clarification escape; gift/style advisory; comparison/reference/similar; empty/outage/timeouts; kiểm tra facts/stock/giá theo authority và Phase 1 gates. Ghi call counts và latency thật nếu có instrumentation phù hợp, không lấy suite duration thay thế.
6. Nếu sai hard constraints/facts/permissions, lặp clarification hoặc provenance lệch: dừng promotion, rollback đúng AI image đã giữ, không rollback DB/index vì Phase 3 không ghi dữ liệu. Chỉ kết luận hoàn thành Phase 3 sau live acceptance được ghi bằng chứng riêng vào báo cáo chính này.

Điểm dừng phiên này: bàn giao source, regression cô lập và báo cáo; không có deployment, không Phase 2B và không Phase 4.
