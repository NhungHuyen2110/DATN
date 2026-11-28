# LUMIÈRE AI Upgrade Phase 1

Ngày thực hiện: 27/11/2026, Asia/Bangkok. Workspace `D:\LUMIERE-FINAL-TEST`, branch `update-ai`, HEAD giữ nguyên `1a432c170164fa9eeb07a189d6c0edd306713f67`.

**PHASE 1 ĐÃ TRIỂN KHAI VÀ ĐẠT LIVE ACCEPTANCE ngày 27/11/2026.** Preflight và source manifest đạt; giữ rollback images, build tuần tự đúng `ai-api`/`business-api`, xác minh provenance/checksums, new-image guard tests đạt 4 AI + 65 Business. Customer, Staff, Admin và ma trận quyền qua proxy thật đều đạt; hai backend mới healthy, semantic ready. Frontend mới nhất giữ nguyên 574 file và container ID. Có một lượt rollback do request kiểm thử bị PowerShell làm mất dấu; kết luận lỗi ứng dụng ở lượt đó đã được thu hồi, sau đó nghiệm thu lại UTF-8 đúng trên chính hai image đã xác minh. Chi tiết thực tế và giới hạn bằng chứng tại mục 13. Không commit/push/merge hoặc chuyển Phase 2.

Các mục 1–10 ghi nhận công việc checkout và bằng chứng trước lần triển khai này; các nhận định “chưa build/recreate” ở đó là trạng thái lịch sử. Kết quả triển khai hiện hành được ưu tiên theo mục 13.

## 1 Phạm vi sửa

Đã đọc báo cáo `docs/AI-CHATBOT-AUDIT-20261127.md`; không lặp lại kiểm toán tổng thể. Công việc tập trung vào F03, F01, F02, kiểm tra F08 và kế hoạch triển khai cho F04.

- Enforce feature gate tại entrypoint price inference; bỏ đường ép `enabled=True` từ DST.
- Giữ MiniLM refinement hoạt động độc lập; giữ planner cũ và planner full-context có gate riêng. Siết override của planner full-context theo cùng nguyên tắc không vượt cấu hình.
- Dùng bộ phân tích trạng thái đơn/thanh toán và bộ kỳ báo cáo chung; không rơi về total/current month khi bỏ sót phạm vi.
- Cho Admin hỏi tổng đơn độc lập qua tool chỉ đọc hiện hữu.
- Hỗ trợ các trạng thái đơn hợp lệ cho AI order count, gồm packing/shipping/cancelled; mở whitelist của tool đếm theo thời gian theo schema OrderStatus hiện có.
- Hỗ trợ kỳ ngày/tháng/quý/năm và khoảng ngày rõ ràng trong giới hạn tool. Từ chối yêu cầu so sánh nhiều kỳ hoặc constraint không được hiểu đầy đủ.
- Bổ sung regression, công cụ manifest và metadata provenance trong hai Dockerfile. Không đổi base image, package/dependency, command, user hoặc model.

Không sửa Customer clarification policy rộng hơn, sync/index backlog, frontend, purchase/cart/payment/account logic, authorization, schema hoặc dữ liệu nghiệp vụ. Các phát hiện F05/F06/F07/F09 còn thuộc kế hoạch tiếp theo.

## 2 Nguyên nhân gốc được xác nhận

### 2.1 Feature flag Semantic Price

`prepare_semantic_refinement()` dùng DST flag để quyết định semantic refinement, rồi gọi hàm lồng `semantic_infer()` với `infer_price_preference(..., enabled=True, time_budget=18)`. Entry point cũ chỉ đọc `LUMIERE_SEMANTIC_PRICE_ENABLED` nếu `enabled is None`; do đó caller có thể vượt deployment flag.

Sau sửa, `infer_price_preference(query, *, time_budget=None)` luôn kiểm tra biến Price trước mọi gate/HTTP. Không còn tham số override. DST chỉ truyền budget; ontology/MiniLM branch vẫn chạy trước phần price. Flag DST không còn đồng nghĩa được quyền bật inference giá.

Planner full-context chia sẻ URL/model Semantic Price nhưng là tác vụ khác, được điều khiển bằng `LUMIERE_HYBRID_NLU_ENABLED`. `request_plan(..., enabled=False)` vẫn cho phép opt-out; `enabled=True` không vượt được gate môi trường. Planner cũ dùng `LUMIERE_SEMANTIC_PLANNER_ENABLED` và URL/model Customer Dialogue. Không dùng Price flag để vô hiệu hóa các planner riêng.

### 2.2 Staff và Admin order scope

Parser Staff cũ chọn total nếu thấy “đơn” mà không match vài trạng thái. Các nhánh multi-intent lại tự chọn trạng thái bằng một bộ if/elif khác. Shipping/cancelled/packing và trạng thái không hỗ trợ có thể bị bỏ qua.

Tool summary hiện có đã đọc đủ `order_status` và `payment_status`. Sửa nằm ở parser/dispatch/render, không thay cách cập nhật hay định nghĩa đơn hàng. `ai_order_scope` nhận diện enum và kiểm tra phần từ còn lại; nhiều trạng thái, phủ định chưa được hỗ trợ, filter địa lý/giá/nhân viên hoặc trạng thái không hiểu sẽ abstain. Hai loại order/payment scope được phân biệt; tổ hợp của chúng chưa được tool count hiện tại hỗ trợ nên không trả một phần.

Admin trước đây chỉ gọi order statistics qua multi-intent. Route mới tái sử dụng dispatcher/tool chỉ đọc cho câu order đơn nghiệp vụ, vẫn sau các dependencies xác thực hiện có.

### 2.3 Kỳ báo cáo và constraint coverage

Revenue parser cũ khởi tạo tháng hiện tại rồi chỉ ghi đè khi match vài dạng ngày/tháng. Không match quý/năm không tạo lỗi; nhiều kỳ chỉ lấy kỳ đầu. Orchestrator còn tự tách và dựng lại câu hỏi thời gian, có nguy cơ mất phần câu chưa hiểu.

`ai_reporting_period` parse một phạm vi duy nhất và trả phần chưa tiêu thụ cho coverage validation. Dùng chung cho revenue, top-selling, order theo kỳ và orchestrator. Các từ/ngữ nghĩa không nằm trong contract của tác vụ sẽ bị từ chối. Đây là grammar và lexicon theo slot/nghiệp vụ, không hardcode câu hỏi hoặc kết quả cụ thể.

### 2.4 Host process timeout

Đã giữ nguyên `shared/host_process.py`, `run_bounded()` và assertion của test gốc.

| Thử nghiệm | Quan sát |
| --- | --- |
| Test gốc trong sandbox | Failure tái hiện, 40,545s; timeout output không có `child:`. |
| Instrumentation sandbox | Popen khoảng0,016s; communicate timeout khoảng3,031s, partial output None; `taskkill /PID <PID vừa tạo> /T /F` trả code1, stderr `ERROR: Access denied`. Drain pipe không hoàn thành trong budget; toàn lượt khoảng40,219s. |
| Chính test gốc ngoài sandbox | PASS, 3,271s. |
| Targeted qua safe AI runner ngoài sandbox | PASS, 3,238s. |
| Full safe AI runner ngoài sandbox | Host test PASS trong suite285 test, không thay assertion/skip. |

Bằng chứng xác nhận môi trường sandbox chặn thao tác taskkill trên cây tiến trình thử nghiệm. Trong sandbox còn có hiện tượng output/drain chậm; chưa tách riêng hoàn toàn tác động khởi tạo process con và inherited pipe. Không đủ căn cứ để quy tất cả thời gian40s cho một lỗi implementation. Chưa sửa mã timeout hoặc nới assertion chỉ để PASS. **Việc chạy host-process test trong sandbox này vẫn là giới hạn môi trường; chạy ngoài sandbox đã được kiểm chứng.**

## 3 File và hàm thay đổi

| File | Thay đổi |
| --- | --- |
| `AI/jewelry_agents/dialogue_state_controller.py` | `prepare_semantic_refinement.semantic_infer`: bỏ `enabled=True`. |
| `AI/jewelry_agents/semantic_price_intent.py` | `infer_price_preference`: gate authoritative, bỏ override argument. |
| `AI/jewelry_agents/dialogue_plan.py` | `request_plan`: gate riêng không bị argument override. |
| `backend/app/services/ai_order_scope.py` mới | `parse_order_scope`, `order_clause`, `has_order_request`, `statistic_value`: enum/coverage/label chung. |
| `backend/app/services/ai_order_chat.py` mới | `answer_order_question`: dispatch read-only dùng chung, chặn list/identity và scope chưa hỗ trợ trước tool. |
| `backend/app/services/ai_reporting_period.py` mới | `parse_reporting_period`, `has_period`, `reporting_scope_supported`: grammar kỳ và coverage theo tác vụ. |
| `backend/app/services/ai_staff_intent.py` | `understand_staff_question`: delegate shared scope, không default khi còn modifier chưa hiểu. |
| `backend/app/services/ai_order_time_intent.py` | `understand_time_order_question`: dùng chung period/status; từ chối payment filter theo kỳ vì tool chưa có contract tương ứng. |
| `backend/app/services/ai_order_time_tools.py` | Whitelist lấy từ `OrderStatus` hiện hữu bằng `typing.get_args`; không đổi SQL count hoặc schema. |
| `backend/app/routers/ai_staff.py` | `_staff_ai_tools`: dùng dispatcher sau product/multi/inventory; giữ dependency quyền và tool imports để test được. |
| `backend/app/routers/ai_admin.py` | `_admin_ai_tools`: thêm order đơn nghiệp vụ, dùng tool hiện hữu. |
| `backend/app/services/ai_admin_revenue_intent.py` | `understand_revenue_question`: shared period, không bỏ constraint còn lại. |
| `backend/app/services/ai_admin_intent.py` | `understand_admin_question`: dùng shared period cho bán chạy; từ chối grouping chưa được top-selling tool hỗ trợ. |
| `backend/app/services/ai_admin_orchestrator.py` | `resolve_period`, `answer_admin_multi_intent`: parse nguyên câu, preflight trước tool, dùng shared order scope. |
| `backend/app/services/ai_staff_orchestrator.py` | `answer_staff_multi_intent`: preflight scope và shared order rendering. |
| `backend/app/services/ai_multi_intent.py` | `detect_requested_tools`: giữ câu có order noun dù status chưa hiểu, để validator từ chối thay vì chỉ trả phần inventory. |
| `AI/tests/test_phase1_price_gate.py` mới | Zero-provider-call, MiniLM independence, timeout/JSON, separate planner gate tests. |
| `AI/tests/test_shopping_state_updates.py` | Mocked price test dùng env gate trong test thay API override đã xóa. |
| `AI/tests/test_semantic_dialogue_plan.py` | Test endpoint/timeout đặt own gate trong process test có provider mock; không đổi runtime. |
| `backend/tests/test_ai_phase1_correctness.py` mới | Status/paraphrase/scope/period/routes/multi và tools trên SQLite memory. |
| `scripts/run_ai_tests.py` | Thêm `--pattern` để targeted test vẫn dùng cùng isolation guards; mặc định giữ full suite. |
| `scripts/ai_source_manifest.py` mới | `source_manifest`: SHA-256 của source/build inputs, HEAD và dirty paths; không đọc env/model/DB. |
| `AI/Dockerfile`, `backend/Dockerfile` | Thêm build args và labels commit/source SHA sau COPY; không thay dependency hoặc runtime command. |

`AI/api.py`, `AI/rag/conversation_service.py`, `AI/jewelry_agents/semantic_planner.py` không được sửa thêm trong Phase 1. Các refactor đã tồn tại ở baseline checkout được review như phần chênh với image, không revert hoặc coi là đã deploy.

## 4 Before và after behavior

“After” dưới đây là checkout test, chưa phải runtime mới.

| Trường hợp | Before | After trên checkout |
| --- | --- | --- |
| Price flag false, DST true | DST có thể ép inference giá | Entry point return neutral trước gate/provider; test chứng minh0 calls. |
| Semantic entity refinement, Price false | Có thể chạy nhưng bị trộn với price override | MiniLM branch vẫn hoạt động độc lập, không cần price provider. |
| Staff đang giao/đã hủy/đóng gói | Rơi về total | Chọn shipping/cancelled/packing; summary lấy đúng status map. |
| Order status không hiểu hoặc tổ hợp status/payment | Có thể trả tổng hoặc một phần | unsupported/invalid, không gọi count tool. |
| Order time filter | Một số trạng thái hỗ trợ, có nguy cơ mất scope khác | Shared period, đủ6 order statuses; payment-by-period rõ ràng unsupported. |
| Admin tổng đơn độc lập | unsupported | order_statistics từ tool summary hiện hữu. |
| Revenue quý3/2026 | Tháng11/2026 ở runtime baseline |01/07–30/09/2026, group month. |
| Revenue năm2025 | Có thể default tháng hiện tại |01/01–31/12/2025, group month. |
| Revenue ngày29/02/2024 | Chưa có explicit-date parser phù hợp | Đúng ngày hợp lệ;31/02 bị invalid. |
| Revenue từ01/09 đến15/10/2026 đầy đủ năm ở từng endpoint | Có thể default hoặc lấy một phần | Đúng inclusive range, group day mặc định. |
| So sánh9/10 hoặc nhiều kỳ | Chỉ trả kỳ đầu | Từ chối rõ; chưa triển khai comparison tool trong Phase1. |
| Filter khách hàng/chi nhánh/đơn hủy trong revenue | Có thể bị bỏ qua | Từ chối trước khi đọc số liệu. |
| Multi order + inventory có unknown status | Có thể chỉ trả inventory hoặc total | Giữ order intent và preflight, không gọi tool khi scope thiếu. |

Các phép thử route mới dùng fixture tổng31 đơn, shipping7/cancelled3/packing4 để chứng minh không trả nhầm tổng. Internal tool test dùng SQLite memory6 đơn, mỗi trạng thái1 đơn và kỳ không có dữ liệu0 đơn. Những số này là dữ liệu test tổng hợp, không phải số liệu kinh doanh mới hoặc số được hardcode vào ứng dụng.

Revenue tool vẫn là `get_revenue_statistics()` → `dashboard.revenue()`. Không đổi payment verification/time basis, Decimal, tiêu chí đơn hợp lệ, metric confirmed payments hoặc cách tính doanh thu. Không có SQL/Cypher do LLM tạo để thực thi.

## 5 Targeted regression

| Kiểm thử | Kết quả cuối |
| --- | --- |
| AI `test_phase1_price_gate.py` qua safe runner |4 passed,0 skip;0,047s thời gian test. |
| Backend `-k 'phase1 or ai_role_access'` qua safe runner |65 passed,682 deselected,0 failure/error/skip;2,60s. Gồm57 case Phase1 và8 role matrix hiện hữu. |
| Host timeout qua safe AI runner ngoài sandbox |1 passed,0 skip;3,238s. |

Coverage mới bao gồm diễn đạt đang giao/đang được vận chuyển, đã hủy/bị hủy, đóng gói/chuẩn bị hàng, giao thành công; paid/unpaid/refunded tách order status; constraint phủ định, nhiều trạng thái và địa lý/giá chưa hỗ trợ. Period tests có quý/năm/ngày leap day/range ISO và D/M/Y, invalid date/quarter/year, hai kỳ, fiscal year và filter theo khách hàng/chi nhánh.

Provider được mock trong toàn bộ test đặt gate true ở môi trường test. Không có live LLM inference hoặc đổi env của container. Invalid JSON và timeout trả abstain, không patch state ngoài ý muốn. Planner-sharing test chứng minh Price false không chặn planner có own gate true trong process test/mock, đồng thời own gate false không bị explicit argument vượt qua.

Artifact cục bộ:

- `.local-tmp/phase1/ai-targeted.json`.
- `.local-tmp/phase1/backend-targeted-final.xml`.
- `.local-tmp/phase1/host-outside-final.json`.

Các artifact trong `.local-tmp` là bằng chứng workspace, không được tự commit hoặc coi là artifact build đã phát hành.

## 6 Toàn bộ AI và Business Backend tests

| Suite | Kết quả cuối | Phạm vi |
| --- | --- | --- |
| AI checkout offline |285 tests,0 failure,0 error,1 skip;7,228s;284 test không skip thành công | Ngoài sandbox để host-process test được phép kết thúc process tree; guard model/network/graph vẫn giữ. |
| Business Backend checkout offline |747 passed,845 subtests passed,19 warnings;66,33s | SQLite memory, chặn network/file database; không dùng PostgreSQL thật. |

Lệnh đã chạy:

```powershell
.local-tmp/ai-test-venv/Scripts/python.exe -B scripts/run_ai_tests.py --pattern test_phase1_price_gate.py --report .local-tmp/phase1/ai-targeted.json
.local-tmp/backend-test-venv/Scripts/python.exe -B scripts/run_backend_tests.py -k 'phase1 or ai_role_access' --junitxml=D:/LUMIERE-FINAL-TEST/.local-tmp/phase1/backend-targeted-final.xml
.local-tmp/ai-test-venv/Scripts/python.exe -B scripts/run_ai_tests.py --pattern test_host_process.py --report .local-tmp/phase1/host-outside-final.json
.local-tmp/ai-test-venv/Scripts/python.exe -B scripts/run_ai_tests.py --report .local-tmp/phase1/ai-full-final.json
.local-tmp/backend-test-venv/Scripts/python.exe -B scripts/run_backend_tests.py --junitxml=D:/LUMIERE-FINAL-TEST/.local-tmp/phase1/backend-full-acceptance.xml
```

Full AI và targeted host được chạy ngoài sandbox. Hai runner vẫn giữ isolation guard của dự án. Không cài thêm package để lấy PASS.

Phân biệt các tầng xác minh:

| Tầng | Đã làm | Không được suy ra |
| --- | --- | --- |
| Checkout tests | Hai full suites và targeted tests ở trên | Không chứng minh process web hiện chạy mã mới. |
| Mock tests | Provider, route business tool, user dependency và scope assertions | Không phải model quality hoặc cookie-login acceptance. |
| Internal service tests | Tools mới qua SQLite memory; các kiểm tra read-only image cũ qua PostgreSQL thật | Không phải new-image HTTP acceptance. |
| Existing-image compatibility |9 file AI checkout được compile và import qua source loader trong RAM trên Python/dependencies image hiện có; socket connect bị chặn | Không sửa filesystem/process web của container, không tạo image mới. |
| Docker image tests cho bản mới | Chưa có image mới, chưa chạy | Không tuyên bố image đã pass. |
| Live HTTP acceptance cho bản mới | Chưa thực hiện | Không tuyên bố runtime đã sửa. |

## 7 Failure, giới hạn và công việc còn tồn tại

- Một graph integration test vẫn skip theo runner vì cần server test cô lập. Không đổi thành PASS và không chạy graph writes trên dữ liệu thật.
- Host-process test trong sandbox còn thất bại do giới hạn môi trường nêu ở phần2.4; test gốc pass ngoài sandbox, không sửa hoặc skip nó.
- Backend còn19 deprecation warnings liên quan Starlette/httpx/cookies; chưa nâng dependency ngoài phạm vi.
- Full run đầu tiên trong quá trình phát triển có2 lỗi fixture Mock thiếu context manager; đã đổi sang MagicMock. Targeted backend từng phát hiện routing làm rơi order clause và coverage làm từ chối từ vựng của nhánh LLM hiện hữu; đã sửa, giữ các assertion gốc và chạy lại full suites. Kết quả cuối là bảng phần6; không che giấu các lần thất bại trung gian.
- Grammar coverage ưu tiên abstain, chưa phải NLU tổng quát. Quarter/year được hỗ trợ khi biểu diễn rõ bằng số; quý La Mã, tuần, năm tài chính, range thiếu năm hoặc nhiều kỳ có thể bị từ chối. Không tự suy thêm kỳ.
- Comparison, grouping top-selling, order/payment conjunction, payment-filter-by-period và multi order có thời gian vẫn được từ chối khi chưa có contract tương ứng. Không trả một phần như thể đã xử lý đủ.
- Clarification loop Customer, hội thoại nghiệp vụ đa lượt đầy đủ, worker/index drift và bộ nhãn AI độc lập chưa xử lý trong Phase1.
- Runtime vẫn cũ: read-only checks sau sửa vẫn thấy Staff đang giao → total17; Admin quý3 → tháng11; Admin tổng đơn đơn lẻ → unsupported. Đây là xác nhận chưa deploy, không phải regression checkout.

## 8 Feature flags và các gate được giữ nguyên

Environment container trước/sau không đổi. Compose config được resolve với `.env.example` đúng label đang dùng, không xuất secrets; so sánh mọi key Compose environment với runtime của7 service đều không thấy khác biệt về giá trị. Không sửa bất kỳ Compose/env file nào.

| Gate | Runtime giữ nguyên | Contract checkout sau sửa |
| --- | --- | --- |
| Semantic DST |true | Điều khiển semantic refinement; không cấp quyền inference giá. |
| Compact Shopping |true | Giữ logic hiện có. |
| Semantic Price |false | Không price inference path nào được phép gọi provider qua entrypoint mới. |
| Grounded Narrative |false | Không bật. |
| Customer Dialogue |false | Không bật. |
| Semantic Planner cũ |false | Own gate hiện có, không đổi. |
| Hybrid NLU/planner mới |unset/default false | Own gate authoritative; không thể ép bật bằng argument. |
| Staff/Admin LLM, shared dialogue |unset/default false | Không bật hoặc thêm provider. |

Lưu ý: trên **image cũ**, lỗi override F03 vẫn có thể tồn tại. Cam kết zero-price-provider-call ở trên là contract đã test của checkout, chỉ trở thành hành vi runtime sau deploy và acceptance.

## 9 Bảo toàn frontend, dữ liệu và phạm vi nghiệp vụ

`git diff --exit-code` trên frontend, ba Compose đang dùng, models, schemas, auth router, order business service và `shared/host_process.py` không có thay đổi. Không thay MiniLM, Neo4j, Qdrant, RRF, Hybrid Retrieval hoặc quyền vai trò.

Mọi mutation fixture mới nằm trong SQLite `:memory:` do safe runner kiểm soát. Đối với PostgreSQL thật, chỉ chạy dispatcher image cũ trong process riêng với `connection.read_only=True` để xác nhận chưa deploy. Không tạo login session, không sửa khách hàng/sản phẩm/đơn/tồn kho, không chạy worker/import/reindex. Các thao tác metadata Docker là read-only.

Container IDs và image IDs của7 services trước/sau giữ nguyên, các biến AI được ghi nhận cũng giữ nguyên. Không build, recreate, restart, reset/prune, xóa volume, commit/push/merge. Chỉ tạo tài liệu, bằng chứng cục bộ và sửa source/test/metadata build trong phạm vi được yêu cầu.

## 10 Source runtime consistency và khả năng triển khai

### 10.1 Khác biệt chính xác giữa baseline checkout và image

Diff được lưu tại `.local-tmp/phase1/api.py.diff`, `conversation_service.py.diff`, `semantic_planner.py.diff`; source image đọc được lưu dưới `.local-tmp/phase1/runtime-source`.

- `AI/api.py`: image có `STORE.resolve`, callback cập nhật context/pending/state và hậu xử lý explanation; checkout giao quyền state cho coordinator và callback chỉ gọi RAG.
- `conversation_service.py`: checkout thêm `_remember_legacy_result()`, wrapper legacy callback, nhánh `LUMIERE_HYBRID_NLU_ENABLED` gọi `semantic_turn()`, và dời explanation hậu xử lý vào coordinator. Lock vẫn bao phủ state mutation.
- `semantic_planner.py`: checkout thêm wrapper `plan_dialogue()` import lazy `dialogue_plan.request_plan()`. `plan_query()` cũ được giữ riêng.
- Image thiếu `semantic_conversation.py`, `dialogue_plan.py`, `dialogue_plan_validator.py`, `dialogue_fast_path.py`. Dockerfile hiện `COPY AI/ /srv/AI/`; `.dockerignore` không loại4 module này, nên build từ checkout đầy đủ sẽ đưa chúng vào image. Không cần package/provider mới để import chúng.

Rủi ro regression trước deploy: callback ownership và lưu state đã thay vị trí; pending-category, empty/degraded response, lock, history và explanations cần kiểm tra tương thích. Full AI checkout285 test đã pass trừ skip tích hợp;9-file compile/import trên dependencies image hiện có thành công khi chặn network. Đây là bằng chứng giảm rủi ro, không thay live acceptance. Hybrid gate tiếp tục false nên coordinator mới không tự được kích hoạt.

### 10.2 Build context và cấu hình services

Hai build context đều là `D:\LUMIERE-FINAL-TEST`. AI Dockerfile dùng Python3.12 slim, CPU torch + requirements-runtime (include requirements-test), COPY AI/shared/data/products CSV, user10001, Uvicorn8000. Business dùng Python3.12 slim, requirements hiện có + requests pin hiện có, COPY backend/shared, user10001, Uvicorn8001. Phase1 không đổi các dependency này.

Compose project xác minh: `lumiere-rebuild-test`; env-file label: `D:\LUMIERE-FINAL-TEST\.env.example`. AI dùng `compose.yaml`, `compose.original-data.yaml`, `compose.semantic-dst.yaml`; Business hiện tạo bằng2 file đầu, overlay DST chỉ cấu hình AI. Resolve ba file cho kế hoạch chung không làm lệch các environment keys hiện có của Business.

| Service | Cấu hình cần giữ |
| --- | --- |
| ai-api |3GiB; edge/ai-data/monitoring; model bind `/models:ro`; không host port. |
| business-api |768MiB; edge/business-data/monitoring; product-image volume hiện tại; không host port. |
| frontend |128MiB, edge, không rebuild/recreate. |
| reverse-proxy |128MiB; `127.0.0.1:18080`; nginx config bind chỉ đọc, không đổi. |
| postgres |768MiB; business-data; volume `lumiere-rebuild-test_rebuild_postgres`, không đụng. |
| neo4j |1,5GiB; ai-data; original_neo4j và logs volumes, không đụng. |
| qdrant |1GiB; ai-data; original_qdrant volume, không đụng. |
| index-worker |Profile sync, không chạy trong Phase1. Ollama/monitoring profiles cũng không khởi động thêm. |

### 10.3 Dung lượng và provenance

Snapshot dung lượng host: C trống73.659.736.064 bytes, khoảng68,60GiB; D trống54.482.132.992 bytes, khoảng50,74GiB. Docker báo images4,928GB, build cache3,725GB, volumes1,117GB. Filesystem VM báo khoảng945GiB free nhưng không thay giới hạn vật lý host. Có headroom cho kế hoạch build giới hạn2 services ở thời điểm đo; phải kiểm tra lại trước build, không prune để lấy chỗ. Đề xuất dừng nếu C hoặc D còn dưới20GiB.

Provenance cho source checkout đã test:

```text
git_commit = 1a432c170164fa9eeb07a189d6c0edd306713f67
source_sha256 = d0b831eb7097c24b5ed17e32888e6e1383226d733a52bb27592358098f2e83a2
manifest = .local-tmp/phase1/source-manifest-final.json
manifest_files = 339
```

Manifest hash tên file và nội dung union AI/backend/shared/data COPY inputs cùng deployment recipes; không chứa env, model cache, database hoặc secrets. HEAD không đổi vì không được commit; source SHA phân biệt dirty checkout với commit baseline. Hai Dockerfile nhận `LUMIERE_GIT_COMMIT`, `LUMIERE_SOURCE_SHA256` và ghi labels `org.opencontainers.image.revision`, `io.lumiere.source.sha256`.

Image ID/config digest và RepoDigests phải được lưu riêng sau build, không tự suy image digest từ commit/source hash. Hai image hiện tại còn nguyên:

```text
ai-api: sha256:a8a8fb38c8ec0ad9a279a8d2269cec045b5557dccb6b9b4963de373695d565fd
business-api: sha256:a27f1c1b85a44a1e0480e79c2cdefa3b22a2bde53ef05ae8c1266f4f5a85b0fe
```

Docker image inspect cũng trả RepoDigests với repository names tương ứng. Chưa có digest image mới để báo. Snapshot metadata không bí mật nằm trong `.local-tmp/phase1/runtime-before.json`, `compose-preflight.json`, `runtime-unchanged.json` và `old-image-service-checks.json`.

Đánh giá: **checkout đủ điều kiện xem xét build có kiểm soát**, không đủ điều kiện tuyên bố triển khai thành công. Cần phê duyệt kế hoạch dưới trước mọi build/recreate và phải hoàn tất acceptance sau đó.

## 11 Kế hoạch Docker build recreate và rollback

**Đây là kế hoạch đã được người dùng phê duyệt và thực hiện ngày 27/11/2026; kết quả thực tế, điều chỉnh chạy tuần tự và rollback nằm tại mục 13.** YAML rollback đã được validate qua `docker compose config --quiet` bằng stdin (exit0); CLI help xác nhận các flags build/up được dùng. Các kiểm tra này không tag image, build hoặc thay đổi container. Chỉ thực hiện sau phê duyệt triển khai. Không dùng `down`, `down -v`, `prune`, `--remove-orphans`, profile sync hoặc lệnh import dữ liệu.

### 11.1 Preflight và giữ image rollback

```powershell
Set-Location -LiteralPath 'D:\LUMIERE-FINAL-TEST'
$composeArgs = @(
  '--project-name', 'lumiere-rebuild-test',
  '--env-file', '.env.example',
  '-f', 'compose.yaml',
  '-f', 'compose.original-data.yaml',
  '-f', 'compose.semantic-dst.yaml'
)

# Chỉ kiểm tra config, không in nội dung env/secrets.
docker compose @composeArgs config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose preflight failed' }

python -B scripts/ai_source_manifest.py --output .local-tmp/phase1/source-manifest-predeploy.json
if ($LASTEXITCODE -ne 0) { throw 'Source manifest failed' }
$manifest = Get-Content -LiteralPath '.local-tmp/phase1/source-manifest-predeploy.json' -Raw | ConvertFrom-Json
if ($manifest.source_sha256 -ne 'd0b831eb7097c24b5ed17e32888e6e1383226d733a52bb27592358098f2e83a2') {
  throw 'Source differs from tested inputs; review and rerun affected tests before build'
}

# Đo lại dung lượng thực; dừng nếu dưới headroom đã thống nhất.
python -B -c "import shutil; print({p: shutil.disk_usage(p).free for p in ('C:/','D:/')}); assert all(shutil.disk_usage(p).free >= 20*1024**3 for p in ('C:/','D:/'))"
if ($LASTEXITCODE -ne 0) { throw 'Insufficient disk headroom' }
docker system df
if ($LASTEXITCODE -ne 0) { throw 'Docker storage check failed' }

$oldAi = 'sha256:a8a8fb38c8ec0ad9a279a8d2269cec045b5557dccb6b9b4963de373695d565fd'
$oldBusiness = 'sha256:a27f1c1b85a44a1e0480e79c2cdefa3b22a2bde53ef05ae8c1266f4f5a85b0fe'
$runningAi = docker inspect --format '{{.Image}}' lumiere-rebuild-test-ai-api-1
if ($LASTEXITCODE -ne 0 -or $runningAi -ne $oldAi) { throw 'AI baseline changed; stop' }
$runningBusiness = docker inspect --format '{{.Image}}' lumiere-rebuild-test-business-api-1
if ($LASTEXITCODE -ne 0 -or $runningBusiness -ne $oldBusiness) { throw 'Business baseline changed; stop' }

docker image tag $oldAi 'lumiere-phase1-rollback-ai:20261127'
if ($LASTEXITCODE -ne 0) { throw 'Cannot retain AI rollback image' }
docker image tag $oldBusiness 'lumiere-phase1-rollback-business:20261127'
if ($LASTEXITCODE -ne 0) { throw 'Cannot retain Business rollback image' }
```

Manifest output dùng create-exclusive; nếu đã tồn tại, chọn tên mới và giữ artifact trước, không ghi đè bằng chứng. Trước build cũng phải đối chiếu config environment với container trong bộ nhớ như preflight đã làm; chỉ xuất tên biến khác, không in giá trị. Nếu env-file bị thay đổi từ lúc báo cáo, dừng để review.

### 11.2 Build đúng hai services

```powershell
docker compose @composeArgs build `
  --build-arg "LUMIERE_GIT_COMMIT=$($manifest.git_commit)" `
  --build-arg "LUMIERE_SOURCE_SHA256=$($manifest.source_sha256)" `
  ai-api business-api
if ($LASTEXITCODE -ne 0) { throw 'Build failed; do not recreate services' }

# Chỉ đọc image metadata, không đọc toàn bộ container environment.
docker image inspect lumiere-rebuild-test-ai-api lumiere-rebuild-test-business-api `
  --format '{{.Id}} {{json .RepoDigests}} {{json .Config.Labels}}'
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect built artifacts' }
```

Kiểm tra hai provenance labels bằng manifest, ghi image IDs/RepoDigests và checksum các file sửa trong image trước khi promote. Không coi chỉ có label là bằng chứng nội dung chắc chắn đúng. Nếu có thay đổi source trong lúc build, dừng và tạo lại manifest/test evidence.

### 11.3 Recreate có giới hạn và acceptance

```powershell
docker compose @composeArgs up -d --no-deps --no-build --force-recreate ai-api business-api
if ($LASTEXITCODE -ne 0) { throw 'Recreate failed; inspect status and use rollback plan' }

docker compose @composeArgs ps ai-api business-api
Invoke-RestMethod 'http://127.0.0.1:18080/ai/health/ready'
Invoke-RestMethod 'http://127.0.0.1:18080/ai/health/semantic'
Invoke-RestMethod 'http://127.0.0.1:18080/api/health/ready'
```

Chờ semantic ready với deadline hữu hạn trước Customer acceptance. Không đổi flag để làm health/model pass. Xác minh container mới dùng đúng2 image đã inspect, flag/env không đổi, frontend/proxy/datastores IDs giữ nguyên, worker vẫn không chạy.

Acceptance bắt buộc sau deploy:

- Chạy guard tests tương ứng trên nội dung image mới trong môi trường test cô lập; kiểm tra price false zero-provider-call và old/new planner gate contract.
- Customer phiên mới: tìm nhẫn dưới5 triệu, đổi rõ sang vòng tay, đổi budget, so sánh card; constraints/stock/price khớp Business API. Unknown followup không được gọi price provider khi false. Không kỳ vọng Phase1 đã sửa toàn bộ clarification loop.
- Staff bằng phiên xác thực sẵn có: shipping/cancelled/packing và paraphrase, total, payment status riêng; so với Business API/dashboard; scope unsupported không trả total.
- Admin bằng phiên xác thực sẵn có: tổng đơn đơn lẻ; revenue quý/năm/range; amount/count/date basis khớp `/admin/reports/revenue`; comparison phải abstain rõ.
- Anonymous/customer/staff/admin matrix; internal endpoint vẫn bị chặn ở public proxy; không tạo hoặc sửa dữ liệu nghiệp vụ để có ca PASS.
- Nếu chưa có phiên hợp lệ, phần authenticated live acceptance phải ghi chưa xác minh; không thay auth hoặc tự tạo tài khoản/session DB để vượt kiểm tra.

Chỉ health200 không đủ nghiệm thu. Mọi response/số liệu trong acceptance phải ghi lại với scope nguồn, không lộ cookie/token.

### 11.4 Rollback

Nếu gate/source mismatch, HTTP lỗi, sai scope, role regression hoặc constraints sai: quay về hai image đã giữ. Không rollback DB/index vì Phase1 không thay schema/dữ liệu/index.

```powershell
$rollbackContent = @'
services:
  ai-api:
    image: lumiere-phase1-rollback-ai:20261127
    pull_policy: never
  business-api:
    image: lumiere-phase1-rollback-business:20261127
    pull_policy: never
'@
$rollbackContent | Set-Content -LiteralPath '.local-tmp/phase1/rollback.yaml' -Encoding UTF8

docker compose @composeArgs -f .local-tmp/phase1/rollback.yaml `
  up -d --no-deps --no-build --force-recreate ai-api business-api
if ($LASTEXITCODE -ne 0) { throw 'Rollback failed; do not change data services' }
docker compose @composeArgs -f .local-tmp/phase1/rollback.yaml ps ai-api business-api
```

Sau rollback xác minh lại image IDs bằng `$oldAi`, `$oldBusiness`, health, frontend/proxy/datastore IDs và flags. Rollback sẽ khôi phục cả các hạn chế cũ; cần ghi rõ trạng thái đó. Giữ rollback images/artifacts, không prune. Lần triển khai tiếp theo phải dùng đúng compose file set đã thống nhất để tránh vô tình tiếp tục override rollback.

## 12 Điều kiện trước Phase 2

1. Kế hoạch build/recreate được phê duyệt; image mới có đúng provenance, source checksums, dependency/import compatibility và flags đã kiểm tra.
2. New-image guard tests và authenticated live HTTP acceptance hoàn tất; không có sai scope nghiệp vụ hoặc role regression. Nếu chưa deploy, giữ trạng thái “checkout validated, runtime pending”.
3. Các ca so sánh/constraint chưa hỗ trợ được abstain đúng; không quảng bá đầy đủ analytics chỉ vì có grammar mới.
4. Chốt hướng xử lý host test trong CI ngoài sandbox hoặc môi trường có quyền quản lý process tree, giữ test gốc.
5. Lập kế hoạch riêng cho Customer task/DST/clarification và BusinessState; không bật lại LLM flags để thay thế công việc kiến trúc còn thiếu.
6. Sync worker,5 pending và index drift chỉ được xử lý trong giai đoạn có quyền ghi và kế hoạch dữ liệu riêng. Phase1 không chạy worker thật.
7. Bộ nhãn human-reviewed, latency/grounding benchmarks và thử model thật là điều kiện đánh giá AI tiếp theo; kết quả unit tests ở đây không thay thế chúng.

Kết quả checkout và kế hoạch ở các mục trên đã được triển khai có phê duyệt; Phase 1 đạt live acceptance theo mục 13. Các điều kiện/nghiên cứu còn lại trước Phase 2 vẫn là công việc riêng, chưa tự thực hiện hoặc được phê duyệt bởi kết quả triển khai Phase 1 này.


## 13 Kết quả triển khai và live acceptance thực tế ngày 27/11/2026

**Kết luận cuối: DEPLOYED — LIVE ACCEPTANCE PASS; Phase 1 hoàn thành trong phạm vi được phê duyệt.** Hai backend hiện chạy images mới đã được kiểm thử; frontend mới nhất được bảo toàn. Kết luận chỉ được đưa ra sau khi nghiệm thu UTF-8 đúng, người dùng đăng nhập chính thức lần lượt Customer/Staff/Admin trong Chrome kiểm thử riêng và kiểm tra trạng thái cuối. Không tự chuyển Phase 2.

### 13.1 Preflight, phạm vi và tài nguyên

- Người dùng phê duyệt triển khai theo mục 11, yêu cầu chạy tuần tự do máy lag. Chỉ build/recreate `ai-api` và `business-api`; không chạy tác vụ nặng song song.
- Compose project `lumiere-rebuild-test`; env-file `.env.example`; dùng đúng `compose.yaml`, `compose.original-data.yaml`, `compose.semantic-dst.yaml`. `config --quiet` đạt. Đối chiếu toàn bộ environment keys do Compose cấu hình với container hiện hành trong bộ nhớ: không có drift; không ghi giá trị bí mật. SHA-256 env-file tại preflight: `c948e29d2b2e83747140fdf2a07cf3340b6f9dba05c69030e8a7f44872ae355a`; kiểm tra lại trước recreate vẫn khớp.
- HEAD vẫn `1a432c170164fa9eeb07a189d6c0edd306713f67`. Source manifest 339 file vẫn `d0b831eb7097c24b5ed17e32888e6e1383226d733a52bb27592358098f2e83a2`, khớp bộ inputs đã kiểm thử. Frontend sửa mới của người dùng nằm ngoài manifest backend; ghi riêng hash 574 file để kiểm tra bảo toàn. Không chạy lại các full/targeted checkout suites đã hoàn tất.
- Trước build C còn 73.595.654.144 bytes, D còn 54.481.240.064 bytes, đều trên ngưỡng 20 GiB. Docker: images 4,928 GB, build cache 3,725 GB, volumes 1,117 GB. Host RAM khả dụng khoảng 760 MiB / tổng khoảng 7,73 GiB; Docker VM khoảng 3,69 GiB. Vì headroom RAM hẹp, build và các container kiểm thử chạy lần lượt, dùng cache; container test giới hạn 1 CPU và 384–512 MiB. Không ghi nhận OOM ở hai backend sau promote hoặc rollback.
- Đối chiếu image đang chạy đúng hai baseline IDs mục 10.3 rồi giữ tags `lumiere-phase1-rollback-ai:20261127` và `lumiere-phase1-rollback-business:20261127`. Đây là giữ image trong local Docker image store bằng tag theo kế hoạch; không xuất tar archive.
- Docker CLI bị sandbox chặn named pipe ở lần preflight đầu; đã dùng quyền thực thi ngoài sandbox cho các lệnh Docker trong phạm vi được phê duyệt. Các lần lỗi preflight ban đầu chưa build/recreate; đã đối chiếu thêm các container QA cũ đang stopped, giữ nguyên chúng.

### 13.2 Build và kiểm thử nội dung image mới

Build `ai-api` trước, xong mới build `business-api`. Các lớp cài dependency đều `CACHED`; không dùng `--no-cache`, không sửa dependencies/base image/source. Hai build thành công. Recreate chỉ bắt đầu sau khi checksums và guard tests đạt.

| Image mới | Image ID / RepoDigest SHA-256 | Checksum file COPY |
| --- | --- | --- |
| `lumiere-rebuild-test-ai-api:latest` | `3b0af54884958d9adb0b41c047501245aa04fa7c2faf134604972d50623a62cc` | 158/158 khớp |
| `lumiere-rebuild-test-business-api:latest` | `0f1315e99652ff4624c5358ecda72f0bfd053c2654dce4119b06e6b6bbc66e68` | 186/186 khớp |

Hai labels `org.opencontainers.image.revision` và `io.lumiere.source.sha256` khớp HEAD/source manifest. Các ID trên lấy từ `docker image inspect`, là digest manifest list local; build logs còn ghi config digests AI `2d2121366fc475b2ee3f98e136a6756da354b40b34067c17272faa56df21217c`, Business `c34c390a72facf3dd59424c8020acff1d6814234ad2bdf1e06091d81d1d7359e`. Không suy digest từ labels. Số file checksum có overlap `shared/` và gồm Dockerfile/requirements đã COPY; không chỉ kiểm tra vài file sửa.

| New-image test | Kết quả |
| --- | --- |
| AI `test_phase1_price_gate.py` qua safe runner, source/dependencies trong image mới | 4 passed, 0 failure/error/skip; 0,061s |
| Business Phase 1 và `ai_role_access` qua safe runner trên image mới | 65 passed, 679 deselected, 0 failure/error/skip; 1 warning Starlette/httpx; 2,42s |

AI tests xác minh price=false/DST=true không gọi provider, MiniLM độc lập, timeout/JSON và hai planner gates. Các gate=true chỉ tồn tại trong test với provider mock. Business tests xác minh scope/period/dispatch và ma trận quyền với fixture trong SQLite memory. Đây là new-image tests, không thay cho live HTTP acceptance.

Container test dùng `--network none`, `--read-only`, tmpfs `/tmp`, không bind DB/model/volume nghiệp vụ; mount safe runner read-only. Business runtime image không đóng gói pytest/httpx test client: invocation đầu thất bại vì thiếu `pytest`; đã gắn read-only bộ công cụ Python test sẵn có từ venv vào container test, không cài vào image. Bổ sung shim `py.py` còn thiếu trong bộ công cụ; collection toàn bộ tests còn gặp `evaluation` ngoài runtime image, nên invocation cuối bỏ collection `test_evaluation_scoring.py` ngoài phạm vi. Toàn bộ 65 tests đích đã chạy và đạt. Các log thất bại của harness được giữ cùng log cuối, không tính thành lỗi ứng dụng đã được sửa. Source ứng dụng và dependencies runtime vẫn lấy từ image, không mount source checkout đè lên image. Manifest công cụ test cuối ghi riêng.

### 13.3 Sự cố harness, rollback an toàn và nghiệm thu lại

Lần recreate đầu chạy tuần tự Business rồi AI khoảng 16:09. Cả hai healthy; AI semantic ready sau 27,475s. Lượt probe Customer đầu qua PowerShell here-string pipe bị `$OutputEncoding` mặc định đổi tiếng Việt thành `T?m nh?n d??i 5 tri?u` trước khi Python gửi HTTP. Response `general_question`/không có card của request đó **không phải bằng chứng lỗi ứng dụng cho câu tiếng Việt dự định kiểm thử**. Ban đầu đã đánh giá nhầm là ca Customer fail và rollback đúng hai backend theo mục 11.4; rollback xác nhận đúng hai image cũ, healthy/semantic ready 200, các service khác giữ nguyên IDs. Đây là lỗi của harness kiểm thử; kết luận lỗi ứng dụng đã được thu hồi và thông báo đính chính cho người dùng.

Sau khi tái hiện rõ việc mất dấu, chuyển sang script lưu UTF-8 hoặc JSON Unicode escapes, lưu hex UTF-8 của query gửi thật. Probe UTF-8 đúng trên baseline trả 3 nhẫn; chỉ dùng để xác nhận lỗi harness, không tính thành acceptance của image mới. Không sửa source/dependencies/flags. Kiểm tra lại manifest, env-file, runtime env/mounts, frontend, dung lượng và image IDs; rồi recreate tuần tự Business/AI từ **chính hai images đã build và vượt guard tests**. Không build lại hoặc chạy lại các tests đã hoàn tất. Lần promote cuối khoảng 16:15; semantic warmup 12,031s, ba readiness endpoint 200 trước acceptance.

Artifacts lượt đầu được giữ nguyên để truy vết. `deploy-20261127/INVALIDATED-BY-ATTEMPT2.json` và `deploy-20261127-attempt2/harness-correction.json` thu hồi nhãn query/kết luận app fail trong `customer-first-probe.json` và kết luận overall trong `acceptance-summary.json` lượt đầu. Bằng chứng build, checksum, tests và rollback lượt đầu vẫn hợp lệ. Kết quả cuối có thẩm quyền là summary của `deploy-20261127-attempt2/`.

### 13.4 Customer live acceptance trên image mới

Gọi proxy thật `http://localhost:18080`, `POST /ai/chat`, hội thoại mới không truyền ID ban đầu; giữ ID trong bộ nhớ cho followup, không xuất token vào artifact. Mỗi request lưu hex UTF-8 của query để kiểm chứng dấu tiếng Việt. Đợi semantic ready trước khi bắt đầu.

| Lượt | Câu gửi thật | Kết quả live và đối chiếu |
| --- | --- | --- |
| 1 | Tìm nhẫn dưới 5 triệu | PASS; card IDs 87, 2, 203; tất cả category Nhẫn, giá <5.000.000, stock >0; từng giá/stock/category khớp `GET /api/products/{id}` |
| 2 | Đổi sang vòng tay | PASS; IDs 197, 74, 259; category Vòng tay, giữ budget <5.000.000; facts khớp Business API |
| 3 | Tăng ngân sách lên dưới 10 triệu | PASS; IDs 74, 18, 197; giữ category Vòng tay, budget <10.000.000; facts khớp Business API |
| 4 | So sánh mẫu thứ nhất và mẫu thứ hai | PASS; `product_discussion`, status ok; so đúng IDs 74/18 của lượt 3; tên/chất liệu/đá/giá/stock trong answer khớp Business API đọc lại sau so sánh |
| 5 | Mình đang cân nhắc lại | PASS trong phạm vi Phase 1; trả clarification, không crash; không coi đây là đã sửa toàn bộ clarification loop |

Conversation ID ổn định ở cả 5 lượt. Thời gian lần lượt 6,406s; 3,063s; 2,672s; 2,141s; 4,156s. Đây là các mẫu đo live acceptance, không phải benchmark latency tổng quát. Sau khi người dùng đăng nhập Customer qua UI chính thức, kiểm thử thêm `/ai/chat` trong context có cookie: HTTP 200, có card nhẫn; gọi Staff/Admin chat trong context Customer bị 403/403.

Price flag vẫn false, DST true; runtime checksum/image ID bằng image đã vượt zero-provider-call guard. Quan sát đúng provider cấu hình `host.docker.internal:11434/api/chat` qua local Ollama `server.log`: offset đầu/cuối đều 38.208, không thêm byte hoặc POST `/api/chat`/`/api/generate` trong cả luồng gồm unknown followup. Kết hợp runtime flag/source và new-image test đạt contract không gọi price provider khi false. Giới hạn: log provider là quan sát bên ngoài trong cửa sổ acceptance, không phải instrumentation từng function của live Python process; không patch process web hoặc bật provider để chứng minh. Không dùng số lượng model đang load thay cho số request.

### 13.5 Staff live acceptance với đăng nhập chính thức

Người dùng tự đăng nhập Staff bằng UI trong context Chrome riêng, không dùng dependency override. Tất cả probes qua proxy và cookie thực do browser quản lý; không đọc hoặc xuất cookie/token. Đọc toàn bộ trang `GET /api/staff/orders`, chỉ lưu aggregate status/payment, không lưu thông tin người nhận/tài khoản. Nguồn có 17 đơn; kiểm tra lại với dashboard khi đến lượt Admin.

| Phạm vi | Câu chính và paraphrase | Số live AI / nguồn Business |
| --- | --- | --- |
| shipping | đang giao; đang được vận chuyển | 1 / 1 |
| cancelled | đã hủy; bị hủy | 1 / 1 |
| packing | đang đóng gói; đang chuẩn bị hàng | 0 / 0 |
| total | Có bao nhiêu đơn hàng? | 17 / 17 |
| paid | Đếm đơn đã thanh toán | 7 / 7 |
| unpaid | Số đơn chưa thanh toán | 10 / 10 |
| refunded | Bao nhiêu đơn đã hoàn tiền? | 0 / 0 |

10 ca trả `order_statistics` với đúng field/value, không rơi về total khi hỏi status. Hai ca “Có bao nhiêu đơn ở Hà Nội?” và “Số đơn đang giao và đã thanh toán” trả unsupported/invalid, `data=null`, không trả tổng hoặc kết quả một phần. Staff gọi Admin chat nhận 403. Tổng 13 probes Staff đều PASS (chưa tính GET nguồn aggregate). Không tạo fixture hoặc sửa dữ liệu nghiệp vụ để có status không bằng 0; packing/refunded thực tế bằng 0 vẫn so đúng nguồn.

### 13.6 Admin live acceptance và nguồn báo cáo

Người dùng tự đăng nhập Admin bằng UI trong context riêng kế tiếp. Tổng đơn đơn lẻ trả `order_statistics`, field `total_orders`, value 17, khớp `/api/admin/dashboard`; các maps order/payment của dashboard khớp Staff orders API. Admin gọi Staff chat cũng HTTP 200 và total 17.

Mỗi câu revenue gọi Admin chat thật rồi gọi `GET /api/admin/reports/revenue` với start/end/group_by tương ứng. So cả amount Decimal, order_count, start/end/group_by và **toàn bộ bucket items**, không chỉ tổng tiền:

| Câu revenue | Phạm vi inclusive / group | Amount VND | Order count | Buckets / kết quả |
| --- | --- | --- | --- | --- |
| quý 3/2026 | 01/07–30/09/2026, month | 0,00 | 0 | 3/3 khớp, PASS |
| năm 2025 | 01/01–31/12/2025, month | 0,00 | 0 | 12/12 khớp, PASS |
| từ ngày 01/09/2026 đến ngày 15/10/2026 | 01/09–15/10/2026, day | 0,00 | 0 | 45/45 khớp, PASS |
| năm 2026 | 01/01–31/12/2026, month | 41.800.924,00 | 7 | 12/12 khớp, PASS |
| tháng 11/2026 | 01/11–30/11/2026, month | 27.986.633,00 | 4 | 1/1 khớp, PASS |

Nguồn report xác nhận `time_basis=payment_transaction.verified_at`, timezone `Asia/Ho_Chi_Minh` (cùng UTC+7 với ngữ cảnh ngày vận hành Asia/Bangkok). AI tiếp tục dùng tool/report hiện hữu, không thay ý nghĩa doanh thu thành lợi nhuận hoặc doanh thu thuần sau hoàn tiền. Các kỳ không có dữ liệu được kiểm cả biên ngày và bucket để không vô tình PASS do tổng 0; bổ sung năm 2026 và tháng 11 có số liệu để xác nhận amount/count.

“So sánh doanh thu tháng 9/2026 và tháng 10/2026” và “Doanh thu năm 2025 theo chi nhánh” đều trả `unsupported`, `data=null`, không trả một kỳ hoặc total sai scope. Tổng 15 probes Admin PASS, gồm dashboard, total, quyền Staff, 5 cặp chat/report, comparison và unsupported filter.

### 13.7 Ma trận quyền, bảo toàn và trạng thái cuối

| Phiên live qua public proxy | Staff chat | Admin chat |
| --- | --- | --- |
| Anonymous | 401 | 401 |
| Customer tự đăng nhập UI | 403 | 403 |
| Staff tự đăng nhập UI | 200 | 403 |
| Admin tự đăng nhập UI | 200 | 200 |

Public proxy trả 404 cho `POST /ai/internal/retrieval-diagnostics`, `GET /ai/internal/metrics`, `GET /api/internal/metrics`. Không bypass auth, không đọc profile/cookie trình duyệt cá nhân, không export storage state hoặc ghi credentials vào log. Việc đăng nhập UI chính thức và tạo session theo luồng ứng dụng được người dùng cho phép bổ sung trong phiên làm việc; không tạo/sửa session trực tiếp trong DB, không tạo tài khoản. Test browser dùng contexts không lưu profile, chạy từng vai trò và đã đóng sau nghiệm thu.

| Backend cuối | Image ID | Container ID |
| --- | --- | --- |
| AI | `sha256:3b0af54884958d9adb0b41c047501245aa04fa7c2faf134604972d50623a62cc` | `ba362ee70415611e3aa6a92d961b14bceaf7d808b832bda29a5f8d0f347adf0d` |
| Business | `sha256:0f1315e99652ff4624c5358ecda72f0bfd053c2654dce4119b06e6b6bbc66e68` | `553322d4a853e24bb97e52bc5ad961d1a56f38c69edeb36980a4700b88055d3e` |

Kiểm tra cuối khoảng 16:22, Asia/Bangkok: hai backend healthy, không OOM; `/ai/health/ready`, `/ai/health/semantic`, `/api/health/ready` đều 200; semantic ready=true, warming=false. Runtime env hashes/mounts và env-file bằng preflight. Price/Customer Dialogue/Semantic Planner false; Hybrid NLU false theo default, không bật thêm gate. Không khởi động index-worker hoặc Ollama/container profile mới. Việc health liệt kê Ollama trong optional_sources không đồng nghĩa đã bật LLM.

Frontend container ID `341d97461bdb92a555a05c1d38b5702b0c970af4486b1f82dcdc048c2da55f6f`, proxy/Postgres/Neo4j/Qdrant IDs giữ nguyên từ preflight, các QA container cũ vẫn stopped. Hash đủ 574 file frontend và 339 source/build inputs không đổi. C còn 73.584.488.448 bytes, D còn 54.471.335.936 bytes. Giữ cả hai tags rollback trỏ đúng image cũ và images mới, không prune. Runtime cuối **không còn dùng rollback overlay**; hai image mới từ ba Compose files đã thống nhất đang phục vụ.

Kiểm tra cuối `git diff --check` còn báo trailing whitespace tại `frontend/index.html:333` thuộc thay đổi frontend đã có trước triển khai; đối chiếu hash xác nhận không phát sinh thay đổi trong phiên này, giữ nguyên theo yêu cầu người dùng. Đây không phải failure của new-image/live acceptance.

Không sửa source frontend/backend trong lượt triển khai, dependencies, auth hay schema; không mutation dữ liệu nghiệp vụ, import/reindex, worker, xóa volume, prune, commit/push/merge. Các session do người dùng đăng nhập UI là hoạt động auth chính thức đã được cho phép, không phải fixture nghiệp vụ. Phase 1 hoàn thành theo acceptance trên; không suy ra đã sửa clarification policy rộng hơn, drift/index backlog, hay đã đạt điều kiện triển khai Phase 2.

### 13.8 Bằng chứng cục bộ

Build/test và lần rollback đầu: `.local-tmp/phase1/deploy-20261127/`:

- `source-manifest.json`, `preflight.json`, `runtime-before.json`, `frontend-hashes.json`.
- `build-ai.log`, `build-business.log`, `new-images.json` (IDs/RepoDigests/labels/checksums).
- `new-image-ai-tests.log`, `new-image-business-tests*.log`, `test-support-manifest-final.json`.
- `runtime-promoted.json`, `rollback.yaml`, `rollback.log`, `runtime-rollback-check.json`.
- `INVALIDATED-BY-ATTEMPT2.json`: xác định rõ kết luận app fail của probe encoding sai đã bị thu hồi.

Nghiệm thu hợp lệ và trạng thái cuối: `.local-tmp/phase1/deploy-20261127-attempt2/`:

- `source-manifest.json`, `preflight.json`, `preauth.json`, `harness-correction.json`.
- `customer-live.json`, `customer-comparison-verification.json`, `customer-provider-observation.json`.
- `staff-live-verification.json`, `admin-period-cases.json`, `admin-live-verification.json`.
- `browser-control/*.request.json`, `*.response.json`: probes qua cookie thật do browser quản lý; không chứa credentials hoặc cookie/token. Conversation ID được giữ trong bộ nhớ, bỏ khỏi response trước khi lưu.
- `runtime-final.json`, `acceptance-summary.json`: kết quả cuối có thẩm quyền; browser đã đóng, rollback tags còn nguyên.

Artifacts chỉ là bằng chứng local workspace, không tự commit. Không lưu trace/HAR/login screenshots hoặc nội dung field đăng nhập. Các command kiểm tra quyền và chat/report chỉ lưu query/response nghiệp vụ không chứa thông tin xác thực; order list chỉ lưu aggregate.
