# LUMIÈRE AI Upgrade — Phase 4 & 5

Ngày 27/11/2026, Asia/Bangkok. Workspace `D:\LUMIERE-FINAL-TEST`, branch `update-ai`, HEAD giữ nguyên `1a432c170164fa9eeb07a189d6c0edd306713f67`. Baseline là working tree có sẵn các thay đổi Phase 1–3, không phải checkout sạch. Không revert các thay đổi này.

**Trạng thái: đã triển khai source Staff/Admin và kiểm thử offline; CHƯA deploy, CHƯA live acceptance. Không tuyên bố Phase 4/5 hoàn thành toàn bộ.** Phase 1 PASS LIVE là bằng chứng lịch sử. Phase 2A và Phase 3 giữ trạng thái PASS OFFLINE; Phase 2B tiếp tục hoãn đến hosting.

Đã đọc audit và báo cáo Phase 1–3; ưu tiên mục 13 Phase 1 về acceptance đã thực hiện, mục 13.6 Phase 2 về resource gate, và giới hạn/contract Phase 3. Không chạy Docker, build/recreate, worker, sync/index hoặc thao tác datastore thật. Không sửa schema, auth, commerce, định nghĩa doanh thu hoặc frontend. Không thêm provider/dependency/model, tải model hoặc đổi flags triển khai. Không commit/push/merge hoặc chuyển Phase 6/7.

## 1. Shared components

Luồng mới: dependencies xác thực hiện hữu → `ConversationStore` → `business_turn` → typed plan/coverage → các dispatcher/tool chỉ đọc hiện hữu → evidence/renderer → commit state sau khi trả đủ kết quả.

- Tái sử dụng store có lock một lượt/conversation, TTL 1.800 giây, tối đa 256 conversation và history 6 lượt. Thêm callback opt-in `dialogue` vào `converse`; Customer tiếp tục đường cũ. Không sửa Customer coordinator/NLU/retrieval Phase 3.
- `BusinessState` chứa intent, metrics, period, order status, payment status, product query, threshold, inventory mode, hai limit độc lập, comparison period, pending clarification và typed operations. Order/payment dùng enum Literal theo contract hiện hữu.
- SET: giá trị có căn cứ mới; KEEP: giữ slot tương thích; CLEAR: bỏ bộ lọc được yêu cầu hoặc slot không còn tương thích khi đổi tác vụ; RESET: xóa task/result cũ; UNKNOWN: không áp dụng plan chưa rõ. Metadata phản ánh cả các slot tự xóa khi chuyển task.
- Chuyển tháng giữ trạng thái đơn; đổi trạng thái giữ kỳ; đổi metric giữ kỳ nếu phù hợp. Top N bán chạy và limit danh sách kho độc lập. Chuyển sang inventory xóa kỳ vì chỉ có snapshot hiện tại.
- Hỗ trợ bỏ lọc thời gian/trạng thái, bỏ ngưỡng, reset/hủy/bỏ qua, greeting/capability, task switch và giải thích kết quả trước. Clarification không ghi một phần bộ lọc; có chỉ dẫn thoát, greeting/reset hoặc câu nghiệp vụ hợp lệ thoát pending.
- Chuẩn hóa tiếng Việt có/không dấu; dùng grammar/lexicon cho slot, toán tử và speech act. Câu rút gọn được giải theo task hiện tại. Có phủ định thanh toán, giới hạn “không quá”, và sửa “không phải … mà …”; phủ định/phạm vi chưa hiểu phải clarify, không tự bỏ điều kiện.
- Multi-metric được preflight toàn bộ trước lần đọc đầu tiên. Một kỳ rõ ràng dùng chung cho các metric theo kỳ; inventory có time basis hiện tại riêng. Hai kỳ khác nhau trong một multi thông thường bị từ chối, phải dùng comparison rõ ràng.
- Khi tool timeout/lỗi nguồn, không trả dữ liệu một phần, không ghi state mới, không đưa chi tiết exception/SQL vào response. Unsupported khác source_error; `data_status` phân biệt scalar `zero`, danh sách `no_data` và dữ liệu `available`.
- Không nối local natural-dialogue fallback vào business callback để ép câu ngoài phạm vi thành truy vấn. Giới thiệu đúng capabilities theo role, không tự gọi model cho lời chào/câu chưa rõ.

Scope hội thoại được siết thành `(endpoint role, account id, hash phiên đăng nhập)` bằng cookie và hàm hash hiện hữu sau dependencies xác thực. Hai phiên cùng account cũng không dùng lại conversation của nhau. Không sửa cách cấp/xác thực/hủy session. Token/hash không xuất trong replay/report. Admin gọi endpoint Staff vẫn đi qua capability Staff.

## 2. Phase 4 — Staff AI

### Nguyên nhân và thay đổi

1. **Tồn kho lọc sau LIMIT:** SQL cũ lấy chung sản phẩm stock ≤ threshold, sắp stock tăng dần và LIMIT; lớp chat mới lọc low/out. Nếu nhiều hàng hết, low-stock list có thể rỗng dù summary > 0. Tool nhận `mode` whitelist và lọc SQL trước LIMIT. Giữ count toàn bộ theo từng loại, thứ tự stock/id ổn định và thông báo hiển thị bao nhiêu/tổng bao nhiêu. Hai orchestrator cũ cũng dùng mode trước LIMIT.
2. **Chat ngưỡng cố định:** parser/renderer chung hiểu threshold 0–1000, list limit 1–50; “dưới N/ít hơn N” dùng ngưỡng N−1, “không quá/tối đa N” inclusive. “Còn hàng dưới N” áp dụng cả stock > 0 và ngưỡng. Các loại đối nghịch/không rõ, số âm, ngoài giới hạn và kho lịch sử bị từ chối.
3. **Tra sản phẩm hẹp:** mở grammar tên có/không dấu và SKU ngoài dạng SP sáu chữ số. SKU so khớp case-insensitive chính xác, `_` không phải LIKE wildcard. Tên được so khớp literal sau chuẩn hóa dấu. Thuộc tính hỗ trợ: loại/category, chất liệu/material, đá/gemstone, thương hiệu/brand, bộ sưu tập/collection; tổ hợp giá trị taxonomy chính xác sau chuẩn hóa, không tự suy thuộc tính.
4. **Thiếu state:** followup kho giữ threshold/mode, order giữ kỳ và trạng thái. Tra sản phẩm giữ query cho câu hỏi tồn/giá tiếp theo. Đổi task xóa slot không tương thích. Dùng dispatcher order và reporting period Phase 1; không đổi service đếm đơn.
5. **Lời khuyên:** render số tồn/ngưỡng và gợi ý kiểm tra kế hoạch bổ sung khi có hàng hết/sắp hết. Không đề xuất số lượng nhập khi thiếu tốc độ bán/lead time; không ghi stock/đơn hàng.

Các giới hạn API giữ nguyên: order theo kỳ dựa `created_at`, chưa lọc payment theo kỳ, chưa ghép order status + payment, chưa liệt kê đơn/PII hoặc chia nhóm số đơn theo ngày/tháng. Khi đổi độc quyền bằng “chỉ …” hoặc sửa “không phải … mà …”, slot trạng thái đối nghịch được xóa rõ ràng; câu ghép constraint thông thường vẫn bị từ chối khi API chưa hỗ trợ.

### Kiểm thử tuần tự Phase 4

- Staff/shared lượt đầu: 188 passed, 1 failed, 141 subtests. Failure là test cũ kỳ vọng câu chung “Tình hình công việc thế nào?” thành pending orders khi classifier flag true. Theo yêu cầu không ép nghiệp vụ, cập nhật test để cả hai trạng thái flag đều abstain và không gọi classifier/data ở câu này.
- Staff/shared sau sửa: **189 passed, 583 deselected, 141 subtests passed**, 1 warning; `staff-final.xml/.log`.
- Bổ sung parser sản phẩm và smalltalk/write/out-of-scope: **8 passed**, `staff-product.xml/.log`. Hoàn tất các bước này trước khi bắt đầu thay đổi Admin.
- Fixture inventory độc lập có 25 sản phẩm hết hàng, stock `[1,3,5,6,12]`: threshold 5 cho 3 low-stock; limit 2 vẫn lấy đúng IDs 26/27, stock 1/3. Threshold 0 cho low list rỗng; in-stock 5; out count 25, list limit 20. Không dùng expected tính bằng cùng thuật toán SQL của tool.

## 3. Phase 5 — Admin AI

### Nguyên nhân và thay đổi

1. **Mất kỳ ở câu tiếp:** dùng BusinessState và reporting grammar chung cho doanh thu ngày/tháng/quý/năm/khoảng ngày. Bổ sung năm/quý hiện tại và trước đó. Revenue vẫn gọi `get_revenue_statistics` → Dashboard; chỉ group `day/month` được API hỗ trợ, kỳ quý/năm có thể trả buckets tháng. Không thêm định nghĩa group quý/năm mới.
2. **Comparison chưa có:** compile hai bộ tham số trước khi đọc, dùng cùng metric/filter/grouping. Kỳ gốc “tháng/quý/năm/ngày trước” được neo vào kỳ đang chọn; không neo mù vào ngày chạy. Chỉ suy kỳ trước từ một kỳ đầy đủ tương ứng, không đoán từ khoảng ngày lẻ.
3. **Tính thay đổi:** Decimal context riêng; chênh lệch = hiện tại − gốc; phần trăm = chênh lệch × 100 / gốc, hiển thị 2 chữ số. Gốc bằng 0 trả `null` và giải thích không xác định, kể cả 0→0. Reject số không hữu hạn/thiếu dữ liệu; không coi lỗi nguồn là 0. Comparison hỗ trợ doanh thu và số đơn theo kỳ; không so snapshot kho hoặc thứ hạng như một scalar.
4. **Top-selling:** hiểu có/không dấu, Top N sản phẩm và giữ kỳ khi đổi từ revenue sang top. Giữ metric `confirmed_payment_sales` và service eligibility/ranking hiện hữu. LLM tùy chọn không được thay kỳ/limit mà parser deterministic đã hiểu đầy đủ.
5. **Purchase-behavior:** nối report aggregate hiện hữu qua Admin dispatcher. Contract phù hợp vì không trả buyer ID/PII và endpoint report gốc cũng Admin-only. Giữ giới hạn tối đa 367 ngày. Renderer nêu số đơn tạo, unique/repeat buyers trong kỳ và số units; nêu rõ gồm mọi trạng thái đơn, kể cả hủy/chưa thanh toán. Không gán các chỉ số này thành doanh thu, event duyệt/tìm kiếm hoặc động cơ khách hàng.
6. **Nhiều chỉ số:** dispatcher đơn được dùng cho từng command đã validate; có thể trả revenue + orders + top + current inventory/purchase trong phạm vi từng contract. Không trả một phần khi clause chưa hiểu hoặc nguồn của một phần lỗi. Evidence tách verified payment time, order creation time và current snapshot.

Không sửa điều kiện paid/verified/reconciliation, Decimal authority hoặc thời điểm ghi nhận doanh thu Phase 1. Không sinh/thực thi SQL bằng LLM. Không suy lợi nhuận, forecast, quan hệ nhân quả, sở thích hoặc hành vi không có trong report.

### Kiểm thử Admin và fixture độc lập

- Admin targeted ban đầu phát hiện multi-period-only followup chưa gán đủ metric và comparison thiếu kỳ hiện tại có thể default. Sửa để followup kỳ áp dụng toàn bộ metric đã chọn, còn comparison không có kỳ hiện tại phải clarify. Một lỗi harness thiếu `import os` trong test replay được sửa; giữ logs thất bại.
- Parser bán chạy mở rộng hiểu “Mặt hàng nào được mua nhiều nhất”; test timeout cũ dùng câu nay đã thành fast path nên đổi input sang câu vẫn chưa hỗ trợ, giữ nguyên assertion timeout fallback unsupported.
- Targeted Admin + fixture rerun: **30 passed**, `admin-fixture-rerun.xml/.log`.
- Rà soát bổ sung: SKU `_` literal, stock lower bound, loại kho đối nghịch, independent limits, thay filter bằng phủ định, grouping comparison và model không override known period. Nhóm review: **14 passed**, `review-targeted.xml/.log`; các assertion bổ sung sau đó được chạy trong full suite.
- Fixture thanh toán có 12,34 được xác nhận `31/01 16:59:59 UTC` và 5,66 tại `17:00:00 UTC` (đổi ngày theo Việt Nam); đơn hủy 90, unpaid 99, mismatch 80/79 không được tính vào confirmed revenue. Expected tháng 1 = 12,34/1 đơn; tháng 2 = 5,66/1 đơn; chênh lệch −6,68, tỷ lệ −54,13%.
- Top tháng 2 chỉ có product 2, quantity 1; quantity 20 của đơn hủy không được vào ranking. Purchase report tháng 1 vẫn đúng contract riêng: 5 đơn tạo, 1 buyer, 1 repeat buyer, 23 units gồm cả đơn hủy.
- Fixture created_at riêng kiểm tra bốn điểm quanh biên đầu/cuối tháng tại UTC+7; tháng 2 có chính xác 2 shipping orders. Leap-day empty report có 0 orders/buyers/units và bucket ngày 29/02/2024 bằng 0.
- Theo dõi SQL của toàn bộ replay Staff/Admin, gồm auth và business queries: chỉ SELECT. RBAC, cross-role/account/conversation và hai auth session cùng Admin được kiểm tra; flags false có 0 calls tới Staff/Admin classifier và general dialogue entrypoint. Network/file-DB guard của runner giữ nguyên.

## 4. Regression cuối và artifacts

Tất cả suites chạy tuần tự, không chạy Docker/model/live PostgreSQL. SQLite memory là fixture; không dùng kết quả này làm bằng chứng accuracy, P95 hoặc live acceptance.

| Suite | Kết quả |
| --- | --- |
| Business Backend toàn bộ, source cuối | **813 passed, 856 subtests passed, 0 failures/errors/skips**, 19 warning deprecation; 57,27s; `backend-final.xml/.log` |
| AI toàn bộ, source cuối | **316 tests run, 0 failures/errors, 1 skip; 315 không skip thành công**; 5,685s ở lượt đầu, lượt xác nhận exit code Python 0; `ai-verified.json/.log`, `ai-process.json` |
| Offline replay HTTP/auth | PASS trong fixture; `offline-replay.json`, hai role, không lưu cookie/token/conversation ID |
| Source preservation/syntax/whitespace | **PASS**; `source-verification.json`, baseline hashes và scoped `git diff --check` |

Lệnh cuối:

```powershell
$env:PHASE45_REPLAY_ARTIFACTS='1'
.local-tmp/backend-test-venv/Scripts/python.exe -B scripts/run_backend_tests.py --junitxml=D:/LUMIERE-FINAL-TEST/.local-tmp/phase4-5/backend-final.xml
.local-tmp/ai-test-venv/Scripts/python.exe -B scripts/run_ai_tests.py --report .local-tmp/phase4-5/ai-verified.json
```

Env opt-in replay chỉ áp dụng process test. Các test gate=true hiện hữu/mới chỉ dùng provider mock trong process test; không đổi env/config triển khai. Logs chạy đầy đủ lưu trong `.local-tmp/phase4-5/`. Các lượt full Backend trung gian 806/813 tests được giữ để truy vết; kết quả source cuối ở dòng suite phía trên có ưu tiên.

AI runner chạy ngoài sandbox vì test host-process Windows gốc cần kết thúc cây process con; giữ nguyên test/assertions, `shared/host_process.py` và guards HTTP/graph/model. Lượt `ai-final` có 316 tests PASS nhưng PowerShell ghi NativeCommandError từ warning stderr và tool báo mã shell 1. Chạy xác nhận cùng runner qua `subprocess.run`, gom stdout/stderr vào log, ghi **Python return code 0** tại `ai-process.json`; không sửa test để đổi kết quả. Một skip yêu cầu isolated graph server vẫn giữ nguyên, không tính là PASS hoặc live integration.

Bản đối chiếu SHA-256 dùng baseline chụp trước sửa: mọi file frontend và AI runtime giữ nguyên; source Phase 2A, Customer Phase 3, auth/schema/commerce, các report cũ và test runner được bảo toàn. Chỉ những file trong bảng mục 6 thay đổi, cộng report này. Đây là bảo toàn file workspace, không phải fresh audit nội dung datastore đang dừng.

## 5. Hội thoại before/after

Before lấy từ audit/source đã đọc; không chạy lại image cũ hoặc gọi đây là live A/B. After là replay/fixtures offline có expected độc lập.

| Hội thoại/điều kiện | Before | After offline |
| --- | --- | --- |
| Staff: đơn đang giao tháng 1 → tháng 2 thì sao | Không có state kỳ/status | Shipping, tháng 1 có 1; tháng 2 có 0, giữ status |
| Staff: tồn kho ngưỡng 3 → còn hàng sắp hết | Ngưỡng cố định, followup thiếu task | Giữ ngưỡng 3, đúng sản phẩm stock 3 |
| Kho có 25 sản phẩm hết trước hàng low, limit 2 | Low list có thể rỗng | Hai hàng stock 1/3; low total 3; báo truncated |
| Staff: SKU → hỏi tồn/giá tiếp | Không giữ query | Dùng lại query đã xác minh; đọc authority lại |
| Staff hỏi doanh thu hoặc mixed inventory+revenue | Chưa có preflight state chung | Không gọi Admin tool, không trả riêng phần kho |
| Đơn theo địa lý/negation chưa rõ → bỏ qua → task mới | Dễ mất scope hoặc không có pending task | Không có data, state cũ giữ; reset thoát; task mới hợp lệ chạy |
| Admin revenue tháng 1 → tháng 2 → so với tháng trước | Followup/comparison unsupported | 12,34 → 5,66; neo gốc tháng 1, −6,68/−54,13% |
| Admin top 5 sản phẩm sau revenue tháng 2 | Thiếu kế thừa period | Metric đổi, kỳ tháng 2 giữ; chỉ product 2 quantity 1 |
| Admin doanh thu + đơn đang giao tháng 1 | Orchestrator cũ từ chối order+period | Revenue 12,34 theo verified time; shipping 1 theo created_at; evidence tách time basis |
| Admin hành vi mua hàng tháng 1 | Report chưa nối chat | Aggregate 5/1/1/23; ghi rõ khác confirmed revenue |
| Comparison gốc 0; source timeout | Chưa có comparison state/error atomicity | Tỷ lệ null có lý do; lỗi nguồn không trả 0/partial và không đổi scope |

## 6. File thêm/sửa trong phiên

Chỉ thêm một module source: `backend/app/services/ai_business_dialogue.py`. Các test bổ sung nằm trong file hiện hữu. Báo cáo Markdown mới duy nhất là tài liệu này; artifacts tập trung `.local-tmp/phase4-5/`.

| File | Thay đổi |
| --- | --- |
| `shared/conversation.py` | Business callback opt-in, dùng lại lock/history/result/store |
| `backend/app/routers/ai_staff.py`, `ai_admin.py` | Nối coordinator theo role server-side, scope hash auth session; dependencies giữ nguyên |
| `backend/app/services/ai_business_dialogue.py` (mới) | Typed state/operations, preflight coverage, followup, comparison, atomic dispatch/evidence |
| `backend/app/services/ai_inventory_tools.py` | Whitelist mode và stock predicate trước LIMIT |
| `backend/app/services/ai_inventory_chat.py` | Shared scope grammar, threshold/limit/mode validation, renderer grounded |
| `backend/app/services/ai_product_lookup.py` | Name/SKU/attribute grammar, exact SKU, normalized literal matching, bounded-memory catalog stream |
| `backend/app/services/ai_multi_intent.py` | Router thêm purchase-behavior Admin và Top N sản phẩm |
| `backend/app/services/ai_reporting_period.py` | Năm/quý hiện tại và trước đó, giữ grammar/coverage Phase 1 |
| `backend/app/services/ai_admin_intent.py` | Bán chạy không dấu, Top N sản phẩm |
| `backend/app/services/ai_admin_orchestrator.py` | Aggregate purchase report adapter, inventory mode trước LIMIT |
| `backend/app/services/ai_staff_orchestrator.py` | Inventory mode trước LIMIT |
| `backend/tests/test_ai_phase1_correctness.py` | Staff/Admin/shared state, constraints, comparisons, flags, metrics và inventory fixture |
| `backend/tests/test_dashboard_api.py` | Reuse fixture/auth/payment, HTTP replay và independent business expected, boundaries/isolation/SELECT-only |
| `backend/tests/test_ai_staff_feature_flag.py` | Không ép câu chung thành pending order khi flag=true |
| `backend/tests/test_ai_admin_llm.py` | Timeout test vẫn dùng input ngoài fast path mới |
| `backend/tests/test_ai_multi_orchestrator.py` | Fixture tool nhận parameter mode mới |
| `AI/tests/test_conversation.py` | Callback contract, locking và cross-auth-session isolation |

## 7. Giới hạn và kế hoạch live acceptance — chưa thực hiện

- Chưa build image, deploy, kiểm thử PostgreSQL thật, fault injection nguồn thật hoặc đo latency/accuracy thực tế. Một bộ grammar regression không phải đánh giá held-out/human-reviewed toàn bộ tiếng Việt. Câu ngoài grammar giữ nguyên scope và clarify, không dùng model để đoán.
- Business state vẫn process-local theo store hiện hữu; chưa có persistent/multi-replica state. Product name/attribute lookup stream catalog theo batch 128, giữ tối đa 6 matches và hiển thị tối đa 5; không thêm index/schema. Bounded memory không chứng minh latency tốt ở catalog lớn; cần đo trên hosting.
- Timeout test là exception fixture, không chứng minh hủy được SQL đang chạy hoặc end-to-end deadline trên môi trường thật. Không tạo thread dùng chung SQLAlchemy session để giả lập deadline.
- Không hỗ trợ mọi phép so sánh, phủ định hoặc filter tùy ý: payment-by-period, status+payment, order grouping, historical inventory, grouped top-selling, comparison ranking và causal/forecast/profit đều phải từ chối rõ. Report purchase là orders/order_items aggregate, không phải tracking hành vi web.
- Read-only nhiều metric/kỳ dùng các service hiện hữu; chưa cung cấp snapshot nhất quán xuyên nhiều request hoặc phân tán. Live reconciliation phải ghi thời điểm và kiểm soát thay đổi dữ liệu; không khẳng định transactional snapshot từ test fixture.

Live acceptance sau khi có hosting và bước triển khai được phép: chốt manifest/source image và flags; dùng phiên đăng nhập chính thức của Staff/Admin; replay bộ hội thoại trong artifact, so revenue với `/admin/reports/revenue`, top với endpoint AI tương ứng, purchase với `/admin/reports/purchase-behavior`, orders/inventory với Business API trong cùng scope. Kiểm tra UTC+7 boundary, empty/zero, gốc 0, data-source error, RBAC/customer/anonymous/inactive/expired session, cùng account khác session và role crossover. Đối chiếu từng amount/count/time basis, không chỉ HTTP 200; kiểm tra zero provider calls khi flags false. Đo cold/warm latency và tải riêng, không suy P95 từ thời gian unittest. Giữ Phase 2B/index worker ngoài phạm vi acceptance này.

Dừng tại source, offline regression và báo cáo; không tự triển khai hoặc chuyển phase.
