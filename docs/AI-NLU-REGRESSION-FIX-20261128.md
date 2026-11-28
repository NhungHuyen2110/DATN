# LUMIÈRE — NLU regression fix, 28/11/2026

Trạng thái cập nhật 28/11/2026: **đã triển khai source NLU được người dùng phê duyệt; website đang hoạt động tại http://localhost:18080**. Workspace `D:\LUMIERE-FINAL-TEST`, branch `update-ai`. Deployment/smoke và giới hạn được bổ sung ở cuối báo cáo. Chưa có nghiệm thu hội thoại của người dùng; không kết luận chatbot đạt chất lượng sử dụng thực tế.

## Phạm vi và bằng chứng tái sử dụng

Tái sử dụng source/typed state/semantic plan/coordinator hiện có, báo cáo audit 27/11 và live acceptance Phase 3–5, cùng `.local-tmp/live-phase3-5/`. Không audit lại toàn dự án. Replay đúng 54 câu Staff/Admin và 43 lượt Customer có trong các artifacts này. Không có transcript đầy đủ ngoài artifacts để chứng minh đã bao phủ mọi câu người dùng nói tối trước.

Không sửa auth/RBAC/session scope, SQL tools/business definitions, schema, frontend, commerce, retrieval/ranking, model/provider/dependency hoặc feature gates. Giai đoạn source/offline ban đầu không thực hiện deploy hoặc Docker build/restart; deployment được thực hiện sau phê duyệt riêng, như phần bổ sung cuối báo cáo. Không chạy worker/reindex/Phase 2B hoặc commit/push/merge. Phase 2A được giữ nguyên.

## Snapshot và rollback

Trước sửa đã copy và đối chiếu byte **196 file Python** trong phạm vi NLU/test, gồm file modified và untracked, cùng `reconcile_live.py`. Snapshot nằm ở `.local-tmp/nlu-fix/snapshot/`; `snapshot-manifest.json` chứa path, byte count, SHA-256 và git status ban đầu. Không dùng HEAD làm baseline vì workspace có thay đổi sẵn của người dùng.

`source-changes.json` liệt kê chính xác thay đổi của phiên này so với snapshot; `source-only.diff` tách khỏi thay đổi có sẵn. `rollback_nlu.py` mặc định chỉ kiểm tra/dry-run. Khi người dùng chủ động chạy với `--apply`, script kiểm tra hash hiện tại và snapshot trước khi khôi phục các file đã sửa, xóa đúng hai file source/test mới của phiên này. Dừng nếu có chỉnh sửa tiếp theo. Giữ báo cáo và artifacts để đối chiếu. Không dùng git reset/restore/checkout.

## Nguyên nhân và thay đổi source

| Nơi | Nguyên nhân | Thay đổi giới hạn |
| --- | --- | --- |
| `shared/conversation.py` | Framing hội thoại chưa tách khỏi task; normalization ở nhiều tầng thiếu nhất quán | Thêm helpers dùng chung cho accent folding, framing, speech act và residual coverage. Giữ dấu phân cách ngày, số và phủ định. Sửa lỗi đảo hai ký tự chỉ khi có lexical/domain evidence liền kề và một ứng viên; nhận `ko`. Không fuzzy-match entity hoặc thay ontology. |
| `ai_multi_intent.py` | Routing thiếu normalization có kiểm soát, lệch vocabulary của scope parser | Dùng normalization chung; dùng cùng grammar tồn kho/mua hàng giữa detector và coverage. Replay bắt được `Hàng sắp hết` trước đây bị detector bỏ sót. |
| `ai_business_dialogue.py` | Greeting fullmatch hẹp; không có metric mới thì luôn kế thừa metric cũ | Nhận greeting/capability/reset trước routing, nhưng greeting kèm task vẫn compile task. Chỉ kế thừa khi có period/slot/status followup được giải thích đầy đủ. Ghi `NEW_TASK/FOLLOWUP/REFINEMENT/RESET/UNKNOWN`; UNKNOWN giữ slot cũ, đặt pending và không đọc dữ liệu. |
| Cùng coordinator | Incompatible slots và precedence | Product task mới xóa period/metric periods/status/payment/inventory slots. Explicit business task đi trước giải thích kết quả cũ, kể cả yêu cầu vượt quyền Staff. Thao tác ghi bị từ chối rõ vì chat chỉ đọc. Validation vẫn atomic trước dispatch và commit state chỉ sau đủ kết quả. |
| `ai_order_scope.py` | `không` cuối câu hỏi có/không bị coi là filter | Tách terminal question operator có căn cứ khỏi phủ định trong predicate. `Có đơn đang giao không?` được hiểu; `đơn không bị hủy` vẫn từ chối vì chưa hỗ trợ phủ định filter. |
| `ai_inventory_chat.py`, `ai_reporting_period.py` | Whitelist token toàn câu từ chối cả `những`, từ giao tiếp | Coverage theo semantic grammar spans và residual content. Framing được xử lý riêng; địa điểm, phủ định, số/threshold sai và modifier chưa giải thích vẫn bị chặn. Không mở scope bằng cách bỏ constraint. |
| Purchase behavior | `phân tích` bị coi là filter; xóa `chỉ` toàn câu làm hỏng `chỉ số mua hàng` | Dùng cùng purchase grammar cho routing/coverage; nhận act phân tích aggregate. `chỉ` chỉ là exclusive operator trước scope phù hợp, không bị xóa khỏi `chỉ số`. Không thêm suy luận nhân quả hoặc analytics ngoài report contract. |
| Multi-metric | Date cuối câu bị gắn cứng vào inventory | Thêm `metric_periods` vào BusinessState hiện hữu. Giải kỳ từng metric trước validation; trailing common period áp vào metrics theo kỳ, inventory là snapshot. Hỗ trợ hai metric có kỳ riêng; followup kỳ chung cập nhật cả hai. Explicit historical inventory vẫn refuse toàn yêu cầu. Evidence thể hiện period từng metric/time basis. |
| `AI/jewelry_agents/intent_router.py`, `AI/rag/conversation_service.py` | Exact greeting và pending/reference early-return có thể nuốt task khác | Dùng chung framing/speech act. Greeting xóa pending nhưng giữ hard shopping slots. Explicit restricted/policy/order/out-of-scope request đi qua policy tool trước pending/reference handlers. Knowledge kèm lời chào không biến thành refinement. |

Đây là mở rộng grammar/typed state có giới hạn, không có hệ thống NLU song song hoặc bảng câu hỏi–trả lời. Ontology, MiniLM, Hybrid Retrieval, RRF, graph/vector retrieval và Business authority giữ nguyên. Không thay thuật toán retrieval để làm đẹp kết quả offline.

## Acceptance oracle

Thêm `scripts/ai_nlu_acceptance.py`, tái sử dụng từ `reconcile_live.py` và tests. Expected contracts được viết từ scenarios, không sinh từ response hay predictions của parser. Live reconciler phải kiểm tra expected intent/status/data/metric/period/status filter/payment trước khi đi vào nhánh reconciliation; không còn nhánh tự PASS mọi `unsupported/data=null`.

Positive cases phải có data và đúng intent/status; các assertions kiểm tra commands, filters, period, threshold, state transitions và dữ liệu fixture. Negative cases phải đúng reason, không data, không gọi tools; source failure không commit scope và không xuất partial facts. Mutation tests cố ý thay positive thành unsupported/clarification, null data, sai status hoặc sai filter: oracle đều từ chối.

Chạy lại oracle trên **54 response lịch sử**: 52 đáp ứng contract mới; hai ca **a25/s25 FAIL reason**. Chúng là yêu cầu ghi nhưng response cũ báo lỗi thời gian/bộ lọc. Giữ nguyên artifacts cũ và ghi FAIL trong `historical-oracle-adjudication.json`. Replay 54 câu qua source mới PASS, gồm refusal đúng lý do chỉ đọc. Không sửa response lịch sử thành PASS và không chạy lại live reconciler có HTTP/SQL thật trong phiên này.

## Expected/actual tiêu biểu

| Câu/nhóm | Expected | Actual offline |
| --- | --- | --- |
| `Xin chào bạn nhé`; capability sau lời chào | Greeting/capability, không đọc lại task cũ | PASS trong fresh, inventory, orders, revenue, product và pending |
| `Xin chào bạn, thống kê tồn kho` | Inventory task, không dừng ở greeting | Inventory metric, snapshot, data fixture |
| `Có đơn đang giao không?` | Shipping, không coi final `không` là constraint | Tool thật SQLite trả 1 shipping order; followup tháng 10 đúng 01–31/10/2026 |
| `Vui lòng liệt kê những sản phẩm sắp hết hàng` | Low stock, giữ threshold tương thích | SQLite: 3 sản phẩm, 1 hết, 1 low; chỉ ID 2/stock 2 trong low list |
| `Doahn thu tháng 11/2026`; `Thogn ke ton kho` | Controlled typo, không route sang task cũ | Đúng revenue November/inventory |
| `Phân tích hành vi mua hàng quý 3 năm 2026` | Purchase aggregate Q3 | Canonical command 01/07–30/09/2026 |
| `Phân tích chỉ số mua hàng tháng 8/2026` | Không mất cụm `chỉ số` | Purchase command 01–31/08/2026 |
| `doanh thu và tồn kho tháng 9/2026` | Revenue September, inventory hiện tại | Đúng scope riêng; inventory không có dated command |
| `doanh thu tháng 9/2026 và đơn tháng 10/2026` | Revenue September/orders October | Đúng hai period trong evidence và commands |
| `doanh thu tháng 9 và tồn kho cuối tháng 10` | Historical inventory unsupported, atomic | Không data, không gọi tool nào |
| `đơn không bị hủy`, địa điểm, giới tính, causal modifier | Unsupported đúng lý do; giữ scope đã commit | Không data/read, transition UNKNOWN |
| Greeting Customer kèm shopping/refinement/reference | Không mất task/hard constraints/ID | Facts so với catalog fixture; ordinal/deictic giữ đúng ID đã chọn |
| Customer policy/restricted request sau pending và card reference | Policy/security precedence | Không retrieval/fact lookup ngoài quyền, không card data, giữ hard slots |

Hai ca c11/c12 là **valid empty**, không phải positive cần có cards: catalog snapshot độc lập không có nhẫn bạc Ruby <=4 triệu còn hàng; artifacts cũ cũng không có cards. Chúng vẫn phải có status `ok`, đúng toàn bộ state/filter, không clarification thay thế. c34/c35 (<1 đồng) tương tự. c15/c16 lỗi nguồn tạm thời trong live cũ được giữ lại; offline replay dùng snapshot khả dụng nên expected là `ok`, không dùng lỗi nguồn cũ làm oracle cho NLU.

## Paraphrase/state matrix và kết quả riêng

**NLU correctness trong tập engineering có nhãn:**

- 11 positive paraphrases × 6 trạng thái = **66/66** cells; 10 negative queries × 6 = **60/60** cells. Trạng thái: fresh, sau inventory, sau orders, sau revenue, sau product lookup và pending clarification. Xem `business-state-matrix.json`.
- Greeting/capability/reset được parametrized qua cùng sáu trạng thái; reset rồi hỏi kỳ không được khôi phục metric cũ. Có kiểm tra transitions, compatible/incompatible slots và preflight multi-intent.
- Sau khi chốt parser, viết thêm **8 paraphrases khác × 6 = 48/48** cells, không dùng kết quả để sửa parser. Expected/actual ở `final-heldout-paraphrases.json`. Đây là holdout do cùng người thực hiện viết, không phải blind human evaluation; không suy F1/accuracy ngoài tập này.
- Replay **54/54** lượt Staff/Admin qua coordinator hiện tại với deterministic fixture dispatch; **43/43** lượt Customer qua pipeline/typed state hiện tại với archived catalog và synthetic candidates. Customer có cả shopping, refinement, cancel/reset, repeated clarification, gift/style, compare/ordinal/deictic/similar, valid-empty. Xem hai file `*-captured-replay.json`.
- Customer matrix bổ sung: 3 trạng thái fresh/shopping/pending × 3 cách greeting/capability; 3 × 2 greeting+shopping; policy/security precedence, knowledge và grounded references. Không áp business states inventory/revenue vào Customer public conversation: chúng thuộc role/session riêng và đã có isolation/RBAC regression.

**Functional correctness:**

- Vòng regression rộng ban đầu: **955 tests + 856 subtests PASS**, `backend-regression.xml`. Đây là intermediate source; không trình bày như toàn bộ final checkout đã chạy lại.
- Final source: **372 tests liên quan AI + 4 subtests PASS**, 620 không liên quan deselected, `backend-delivery-verified.xml`. Bao gồm scope, routes, RBAC, flags, atomicity, Decimal, periods/comparison và NLU mới.
- Customer: **162 tests PASS**, 0 failure/skip, từ 11 patterns. `test_shopping_state_updates.py` bản cuối có 49 tests (`customer-captured-verified.json`); 10 pattern còn lại dùng `customer-test_*.json`. Không cộng trùng những lần rerun trước đó.
- Dùng venv sẵn có, mỗi process/suite chạy tuần tự. Backend runner chặn mọi network và mọi DB ngoài SQLite `:memory:`; AI runner chặn HTTP/Neo4j live/model use. Không dùng ngưỡng host available 1,5 GiB. Có deprecation warnings sẵn có và cảnh báo Qdrant version probe bị chặn trong offline runner; không tải model hoặc đổi dependency để dẹp warning.

**Grounding:**

- Business: real inventory/order read tools trên SQLite trong bộ nhớ; expected independent từ fixture rows. Instrument SQL sau seed để chỉ cho phép SELECT; đúng stock/filter/period/status. Các metrics revenue/top/purchase trong NLU matrix dùng fixture dispatch, không phải live reconciliation mới.
- Customer: mọi card trong replay so exact name/Decimal price/stock/category/material/gemstone với archived Business catalog; stock >0 và budget được kiểm tra. Snapshot là dữ liệu lịch sử, không chứng minh facts live hiện tại. Dense/graph candidates được mock để kiểm tra contract và hard constraints, không dùng chúng làm bằng chứng recall/ranking/MiniLM quality.
- Reuse bằng chứng business definitions/API/SQL/RBAC cũ ở mức baseline; không nâng chúng thành chứng nhận live cho source chưa deploy.

Không lấy 372/162 tests hoặc số cells làm chatbot accuracy. Functional, NLU và grounding là ba kết luận với phạm vi khác nhau.

## Các vòng FAIL được giữ và xử lý

- `backend-initial.*`: hai expected negatives cũ không còn phù hợp yêu cầu mới về common trailing period và metric-specific periods. Thay chúng bằng explicit historical-inventory negatives; bổ sung positive tests assert chính xác từng period/command. Không nới expected thành chấp nhận unsupported cho positive.
- `backend-final.*`: fixture cancelled order thiếu `stock_restored=True`, vi phạm CHECK constraint. Sửa fixture theo schema sẵn có, không sửa schema/business rule.
- `backend-final-replay.*`: `s10 Hàng sắp hết` không route đúng. Sửa grammar dùng chung, không sửa expected inventory intent.
- `backend-delivery.*`: regression mới tìm thấy việc xóa `chỉ` khỏi `chỉ số mua hàng`. Sửa scoped operator và grammar purchase; expected vẫn giữ purchase August.
- `customer-captured-final.*`/`customer-captured-replay-initial.json`: fixture mock SourceGate nhận sai chữ ký; hai expected non-empty c11/c12 bị gán sai. Sửa chữ ký mock và kiểm tra empty bằng catalog độc lập. c32 theo contract cũ không có public intent; oracle kiểm tra clarification status, no cards và missing-reference reason, không tự giả định response có field mới. Không thay source retrieval/ranking để PASS.

## Giới hạn và điểm dừng

NLU vẫn là grammar có kiểm soát; chưa bao phủ mọi lỗi gõ/viết tắt, mọi cách nói tiếng Việt hoặc mọi modifier. Unknown content vẫn abstain. Quy tắc scope cuối câu multi-metric chỉ giải các trường hợp có căn cứ; yêu cầu tồn kho có local historical period/`cuối`/`tại thời điểm` không được chuyển thành snapshot. Nếu nhiều kỳ và thiếu metric-local period thì hỏi lại; comparison vẫn cần kỳ hiện tại/gốc phù hợp contract.

Chưa đo human conversation quality, real MiniLM relevance, live API/SQL mới, auth/session fault cases ngoài regression fixtures, distributed state/concurrency/load/P95 hoặc deadline cancellation thật. Index consistency/freshness/recall drift đã nêu trong Phase 2/live report vẫn chưa được giải quyết; không chạy worker hay Phase 2B. Không áp dụng vocabulary corrections vào ontology/product IDs hoặc thay hard constraints để tăng answer rate.

Hai module/file Python mới ngoài artifacts là `scripts/ai_nlu_acceptance.py` và `backend/tests/test_ai_nlu_regression.py`; runtime thay đổi trong các module có sẵn. Danh sách đầy đủ/hash/diff ở artifacts, không gán các thay đổi workspace có trước cho phiên này.

Điểm dừng của giai đoạn đầu là source và offline verification. Sau đó người dùng đã phê duyệt deployment; phần dưới ghi lại đúng công việc được phép tiếp tục. Chưa có xác nhận chất lượng hội thoại thực tế từ người dùng.

## Bổ sung triển khai theo phê duyệt — 28/11/2026

Hoàn tất xác minh lúc **09:54 (Asia/Bangkok, UTC+7)**. Website được giữ chạy tại **http://localhost:18080** để người dùng đăng nhập và thử ba chatbot. Không sửa thêm application source trong deployment; fingerprint trước build và sau smoke bằng nhau.

### Preflight, rollback và thứ tự triển khai

- Docker daemon chưa chạy khi bắt đầu; các containers đã dừng từ khoảng 12 giờ trước. Khởi động Docker Desktop đã cài sẵn trong tài khoản ADMIN, không đổi cấu hình. Không coi trạng thái website đang dừng ban đầu là downtime gây ra bởi deployment này.
- Xác minh byte/hash toàn bộ **196 snapshot files** và **13 path thay đổi** trong delivery manifest. Đối chiếu full build-input manifest với lần deploy trước: không có drift ngoài NLU/test đã duyệt. Source fingerprint lần triển khai: `e2bb50b70055b1e5692e8b5c92b711e466afe7968e5363bb8855246ece222546`.
- Giữ nguyên **4 rollback tags cũ**, đồng thời thêm `lumiere-nlu-rollback-ai-api:20261128` và `lumiere-nlu-rollback-business-api:20261128` trỏ tới chính hai image đang dùng trước phiên này. Không prune/xóa images, containers dữ liệu hoặc volumes. Rollback overlay JSON/YAML tại `.local-tmp/nlu-fix/deployment/rollback.yaml`; chưa áp dụng rollback.
- Build `ai-api` bằng cache → kiểm tra image/checksum → khởi động tuần tự các dịch vụ phụ thuộc hiện hữu → recreate riêng `ai-api`, đợi healthy → build `business-api` bằng cache → kiểm tra image/checksum → recreate riêng `business-api`, đợi healthy. Business image cũ được khởi động tạm trước AI để cung cấp catalog; chỉ sau AI healthy mới thay Business bằng image mới.
- Các dependency-install layers đều **CACHED**; không thay requirements, model hoặc provider. Không build frontend. Không chạy lại full offline regression. Chỉ chạy smoke giới hạn trên deployment.
- Không áp ngưỡng host RAM khả dụng 1,5 GiB. Giữ guard phản ứng với combined critical host+VM pressure kéo dài, swap tăng nhanh và disk pressure như lần triển khai trước. Không guard nào kích hoạt. Host minimum trong các mẫu build AI khoảng **814 MiB**, Business **689 MiB**; VM minimum tương ứng **3154 MiB / 1652 MiB**. Đây là samples vận hành, không phải chứng nhận capacity/load.

### Images, checksums, health và flags

| Service | Image ID mới | Checksum COPY inputs |
| --- | --- | --- |
| `ai-api` | `sha256:09b3bc8934a41f0e3636bb0910895e8c57dae544aa2244da6a51f1433eb5e586` | 160 file, 0 mismatch |
| `business-api` | `sha256:37e61fcebad8e2e8d33ae0c7a7b5c843c0b9da9b14b980bdfc14178489032b92` | 189 file, 0 mismatch |

Labels revision giữ commit `1a432c170164fa9eeb07a189d6c0edd306713f67`; dirty source được xác định bằng fingerprint riêng ở trên, không giả định HEAD chứa các thay đổi này. Container Image IDs khớp image mới đã kiểm tra. Environment hashes và mounts không đổi; frontend/proxy/PostgreSQL/Neo4j/Qdrant giữ container và image hiện hữu. Frontend files và ba nội dung HTTP tiêu biểu được so checksum, đều khớp; không rebuild frontend.

**7 services đang running**: reverse-proxy, frontend, ai-api, business-api, PostgreSQL, Neo4j, Qdrant. Các service có Docker healthcheck đều healthy. `/`, `/health/live`, `/ai/health/live`, `/ai/health/ready`, `/api/health/live`, `/api/health/ready` đều HTTP 200. Semantic readiness: `ready=true`, `warming=false`; Business readiness: database connected. Qdrant không có Docker healthcheck; smoke Customer kiểm tra retrieval thực tế, không suy rằng mọi projection/index đều nhất quán.

Tất cả LLM gates vẫn **false**: Semantic Price, Customer Dialogue, Semantic Planner, Hybrid NLU, Grounded Narrative, shared Dialogue LLM, Staff và Admin classifiers. Semantic DST/model warmup/Retrieval V2 và các flags hiện hữu khác được giữ nguyên. Ollama `server.log` offset **2604 → 2604**, appended bytes **0**, observed chat/generate calls **0** trong smoke window. Đây là log observation kết hợp false gates/source hashes; không phải instrumentation mọi socket/provider.

### Smoke NLU và grounding trên deployment

**Staff/Admin: 23/23 PASS** với acceptance oracle mới, gồm greeting/capability, greeting+inventory, `những`, UNKNOWN sau inventory/revenue, câu có/không, followup kỳ, phủ định filter, controlled typo, thoát pending bằng task mới, role refusal, read-only refusal, product/SKU followup, reset, purchase `phân tích`/`chỉ số`, shared trailing period, local metric periods và historical inventory atomic refusal.

Phương pháp: chạy coordinator + **actual read tools của image mới** trong một process kiểm tra riêng bên trong Business container, dùng PostgreSQL transaction **REPEATABLE READ READ ONLY**, không mock số liệu. Oracle kiểm tra intent/metric/status/filter/period/transition trước đối chiếu independent SELECT aggregates cho inventory, orders, confirmed-payment revenue, purchase và product facts. Ca negative/control không dispatch tool. Process kiểm tra có state nhiều lượt riêng; **không trình bày kết quả này như smoke authenticated HTTP Staff/Admin hoặc chứng minh session middleware của uvicorn**. HTTP Staff/Admin không cookie được kiểm tra riêng: **401/401**. Không tạo account, token, login fixture hoặc ghi user_sessions để vượt auth.

**Customer: 10 lượt qua HTTP proxy thật**, gồm capability, greeting+search, pending clarification, greeting thoát pending, yes/no material refinement giữ category/budget, security precedence với reference, reset, ordinal reference sau greeting và policy precedence. Cards được so trực tiếp với Business API về ID/name/Decimal price/stock/category/material; stock >0, Nhẫn và budget <5 triệu được giữ. Ví dụ:

- Greeting+shopping: ID 2, Nhẫn / Bạc 925 / <5 triệu, facts khớp authority; sources dense+lexical.
- Material refinement: IDs 87/203, Nhẫn / Vàng 18K / <5 triệu, facts khớp; sources dense+graph+lexical.
- Reference base: IDs 87/2/340; câu “Chào bạn, mẫu thứ hai có chất liệu gì?” tham chiếu đúng ID 2; không đổi thành bộ sản phẩm mới.

**Giữ minh bạch hai lỗi expected của smoke harness:** kết quả nguyên gốc là **8/10**, tại `smoke-customer.json`. Hai ca restricted/policy bị harness kỳ vọng status chung `unsupported`. Contract Customer hiện hữu ở `AI/rag/rag_service.py` trả `status=intent`, tức `restricted_request` và `unverified_policy`. File contract này byte-identical với snapshot trước sửa, không có application source fix trong deployment. Hai response thực tế có đúng intent, lý do từ chối và không cards/data; đối chiếu lại bằng oracle với contract có sẵn đều PASS. `customer-status-adjudication.json` lưu expected ban đầu, expected theo contract độc lập, actual và classification `HARNESS_EXPECTATION_ERROR`. Không ghi đè initial failures thành PASS, không đổi positive thành unsupported/clarification, không nới constraints hoặc sửa application để đạt smoke. Kết luận: **10/10 đáp ứng existing Customer contract**, với hai lỗi nhãn status ban đầu của harness được giữ riêng.

### Bảo toàn và bàn giao

- Digest/count **23/23 bảng PostgreSQL không đổi** giữa trước và sau deploy/smoke, kể cả `user_sessions` và `product_index_jobs`. Việc chụp digest dùng READ ONLY transaction; không export dữ liệu hàng/PII. Không migration/seed/update/reindex/worker/Phase 2B.
- Không application source/config/flags/frontend/database changes trong deployment; không commit/push/merge. Hash source vẫn khớp delivery manifest đã duyệt. Không khởi động QA containers, index-worker hoặc LLM service.
- Artifacts bổ sung trong **`.local-tmp/nlu-fix/deployment/`**: `preflight.json`, `source-manifest.json`, `rollback-images.json`, `rollback.yaml`, `build-*.log`, `build-*-resources.json`, `image-*.json`, `runtime-before/after.json`, `runtime-flags.json`, `http-health.json`, `semantic-health.json`, `smoke-business.json`, `smoke-customer.json`, `customer-status-adjudication.json`, `database-before/after.json`, `database-preservation.json`, `frontend-preservation.json`, `provider-*.json`, `final-evidence.json`.
- Những giới hạn trước đó vẫn còn: chưa có authenticated HTTP smoke Staff/Admin bằng phiên đăng nhập của người dùng trong lần này; chưa chứng minh index consistency/recall/ranking/freshness, human conversation quality, load/P95 hoặc mọi paraphrase. Không mở rộng nghiệm thu bằng số smoke cases.

**Điểm dừng cuối: deployment và smoke đã bàn giao, giữ website cùng 7 services hoạt động tại http://localhost:18080. Người dùng tự test cả ba chatbot; không tự sửa thêm source hoặc chuyển phase.**
