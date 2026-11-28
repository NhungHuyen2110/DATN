# LUMIÈRE — Deployment & Live Acceptance Phase 3–5

**Kết quả cuối: triển khai thành công; Customer PASS core có giới hạn, Staff PASS sau sửa lỗi acceptance, Admin PASS. Các ca index consistency tiếp tục BLOCKED riêng.** Website được giữ hoạt động tại http://localhost:18080 để người dùng test cả ba chatbot. Không tuyên bố Phase 2B hoặc mọi khả năng hội thoại đã hoàn tất.

Chốt health/resource lúc **27/11/2026 21:42:52 UTC+7**. Workspace `D:\LUMIERE-FINAL-TEST`, branch `update-ai`, HEAD `1a432c170164fa9eeb07a189d6c0edd306713f67`. Đây là cập nhật báo cáo hiện có; kết quả cuối trong tài liệu này thay thế trạng thái BLOCKED_PREFLIGHT trước đó. Bằng chứng cũ vẫn được giữ trong artifacts.

## 1. Quyền triển khai, lịch sử preflight và đánh giá capacity

Đã đọc báo cáo Phase 1, Phase 2, Phase 3, Phase 4–5; ưu tiên Phase 1 mục 13, Phase 2 mục 13.6 và giới hạn cuối Phase 3/4–5. Các full suites PASS OFFLINE trước đó được tái sử dụng; không chạy lại full regression không liên quan.

Lần đầu tại 20:57 UTC+7: Docker pipe không tồn tại, host available 0,726–0,743 GiB; dừng trước workload. Lần tiếp theo Docker Desktop đã bật, engine 29.9.1 truy cập được, ba mẫu host 729.038.848 / 746.885.120 / 765.149.184 bytes; 10 containers dự án đều exited. Đã tái xác minh source manifest cũ khớp, chụp sanitized runtime và giữ rollback image tags. Chưa build trong lần kiểm tra đó.

Sau đó **người dùng phê duyệt bỏ ngưỡng host 1,5 GiB làm điều kiện chặn cố định**, yêu cầu đánh giá capacity thực tế theo từng công đoạn. Từ điểm này không tự BLOCKED chỉ vì dưới 1,5 GiB. Mọi build tuần tự, tận dụng cache, đo RAM/VM swap/disk từng bước. Ban đầu toàn bộ services dừng; ở các vòng sửa acceptance, tạm dừng đúng AI/Neo4j/Qdrant, giữ các service nhẹ rồi khôi phục tuần tự. Không đóng ứng dụng cá nhân hoặc thay cấu hình RAM/WSL/swap/container limits.

Guard của harness dừng build đang chạy nếu host <128 MiB đồng thời VM available <256 MiB kéo dài ba mẫu, hoặc VM swap tăng >512 MiB trong một build, hoặc disk <10 GiB. Startup/monitor báo nguy cấp nếu host <96 MiB đồng thời VM <192 MiB, OOM hoặc restart ngoài ý muốn. Đây là guard phản ứng với áp lực thực tế đã được user cho phép, không phải yêu cầu tối thiểu RAM thực nghiệm hay cam kết capacity. Không guard nào kích hoạt.

| Công đoạn | Số đo / quan sát | Kết quả |
| --- | --- | --- |
| Build đầu ai-api | Min host 764.461.056 bytes, VM 3.340.275.712 bytes; swap used 0 | PASS |
| Build đầu business-api | Min host 959.258.624 bytes, VM 3.320.373.248 bytes; swap used 0 | PASS |
| Build sau hai sửa acceptance | Hai API build lần lượt bằng cache, mỗi vòng 0 exit code; RUN cài dependencies đều CACHED | PASS |
| Live monitoring | 146 mẫu từ 21:12:29 đến 21:38:05 UTC+7; min host 167.74 MiB, min VM 1.367 GiB, max VM swap used 10.14 MiB / 1 GiB | 0 alert, 0 OOM, 0 restart ngoài ý muốn |
| Snapshot cuối | Host available 886,456,320 bytes; VM available 1,625,812,992 bytes; swap used 11.33 MiB | 7 services phục vụ đang chạy |
| Disk cuối | C free 67.77 GiB; D free 50.71 GiB | Đủ cho các bước đã thực hiện |

Snapshot CPU/RAM cuối, không phải số liệu peak hoặc load benchmark:

| Container | CPU | RAM usage / limit | RAM % |
| --- | --- | --- | --- |
| lumiere-rebuild-test-ai-api-1 | 0.30% | 737MiB / 3GiB | 23.99% |
| lumiere-rebuild-test-business-api-1 | 0.26% | 84.71MiB / 768MiB | 11.03% |
| lumiere-rebuild-test-frontend-1 | 0.00% | 88.16MiB / 128MiB | 68.88% |
| lumiere-rebuild-test-neo4j-1 | 1.35% | 661.3MiB / 1.5GiB | 43.05% |
| lumiere-rebuild-test-qdrant-1 | 0.52% | 53.46MiB / 1GiB | 5.22% |
| lumiere-rebuild-test-reverse-proxy-1 | 0.00% | 5.75MiB / 128MiB | 4.49% |
| lumiere-rebuild-test-postgres-1 | 0.86% | 67.04MiB / 768MiB | 8.73% |

Mẫu host thấp nhất không đi kèm cạn RAM VM hoặc tăng swap lớn, không OOM/daemon mất phản hồi. Bằng chứng hỗ trợ vận hành tuần tự trên máy này trong cửa sổ nghiệm thu; chưa chứng minh chịu tải nhiều người hoặc hosting SLA.

## 2. Deployment provenance và rollback

Compose project `lumiere-rebuild-test`; env file `.env.example`; overlays theo đúng thứ tự `compose.yaml`, `compose.original-data.yaml`, `compose.semantic-dst.yaml`. Compose environment so với runtime không có drift. Chỉ build/recreate `ai-api` và `business-api`, luôn `--no-deps --no-build` khi recreate; không chạy up toàn stack. Các datastore/frontend/proxy dùng `docker start` trên containers hiện có.

Manifest đầu: `f0cc2c30f10d9b53bf5af16cf1c6552471d923eec0fb3d576d32caddcb24f73b`. Manifest cuối sau hai sửa trực tiếp acceptance: **`1bf9fb55bb4bbbd44d5899fbe2bb9b03fd3df13aaab009f8ae5793a7e85da7bf`**, 342 source/build inputs. Working tree dirty được nhận diện bằng nội dung, không coi HEAD là đủ provenance. Không commit/push/merge. Giữ cả manifest đầu, correction trung gian và manifest cuối.

| Service mới đang phục vụ | Image ID | File checksums trong image |
| --- | --- | --- |
| ai-api | `sha256:a3f889f6cd39147b7ce848ef44c232f9986ac0fe99af5b44caaee86124e15e24` | 160 / 0 mismatch |
| business-api | `sha256:bbb5caec9a1ad86dca6bdc5b55fcd2bf06a1576cd506678a970955d811fe0b21` | 188 / 0 mismatch |

Hai image có labels `org.opencontainers.image.revision` bằng HEAD trên và `io.lumiere.source.sha256` bằng manifest cuối. Checksums được kiểm bằng containers nhỏ read-only, network none, không chạy model. Không chạy lại full offline suite chỉ để xác minh image. Runtime env hashes/mounts/flags khớp snapshot trước deployment.

Rollback images hiện tại đã được tag/inspect và giữ trong Docker image store, không xuất archive hoặc xóa images:

| Service | Rollback tag | Image ID đã xác minh |
| --- | --- | --- |
| ai-api | `lumiere-live-phase3-5-rollback-ai-api:20261127-resume1` | `sha256:3b0af54884958d9adb0b41c047501245aa04fa7c2faf134604972d50623a62cc` |
| business-api | `lumiere-live-phase3-5-rollback-business-api:20261127-resume1` | `sha256:0f1315e99652ff4624c5358ecda72f0bfd053c2654dce4119b06e6b6bbc66e68` |

Rollback overlay JSON hợp lệ dưới đuôi YAML tại `resume-1/rollback.yaml` chỉ dùng khi rollback service được chọn. Business API đã rollback hai lần trước khi promotion bản sửa; không rollback datastore hoặc frontend. Trạng thái cuối dùng ba Compose files chính, **không dùng rollback overlay**.

| Service cuối | Container ID prefix | State / health | OOM / RestartCount |
| --- | --- | --- | --- |
| ai-api | `d1797cd14694` | running / healthy | False / 0 |
| business-api | `1421e026d800` | running / healthy | False / 0 |
| frontend | `341d97461bdb` | running / healthy | False / 0 |
| neo4j | `9fb34799866b` | running / healthy | False / 0 |
| qdrant | `d5e9c04aeae5` | running / không có Docker healthcheck | False / 0 |
| reverse-proxy | `cffbe17faec5` | running / healthy | False / 0 |
| postgres | `13af61afecb8` | running / healthy | False / 0 |

PostgreSQL readiness xác nhận `database=connected`; Neo4j `RETURN 1` trong READ_ACCESS thành công; Qdrant collection green, 500 points đọc được. AI `/health/ready` và `/health/semantic` trả ready, warming=false; Business `/health/ready` healthy. Việc health liệt kê Ollama ở optional_sources không đồng nghĩa đã bật LLM.

Frontend container `341d97461bdb` và image cũ giữ nguyên. **574/574 file frontend trong container khớp workspace**; index/app.js/customer-ai.js qua HTTP khớp nội dung mong đợi. HTML có sub_filter sẵn của nginx chèn runtime-config.js; phép so HTTP đã tính đúng transform này. Không build/recreate/sửa frontend, không hoàn nguyên các chỉnh sửa của người dùng.

## 3. Lỗi acceptance, sửa giới hạn và kiểm chứng lại

Hai lỗi Staff thật được giữ bằng chứng FAIL, không dùng HTTP 200 để kết luận PASS:

| Trigger | Before live | Sửa trực tiếp | After live trên image cuối |
| --- | --- | --- | --- |
| Tra tên/SKU → “Tồn kho thì sao?” / “Giá thì sao?” | Câu tồn kho chuyển sang toàn kho; câu giá unsupported | Match product followup bằng câu đã bỏ discourse words, hỗ trợ `gia` ngắn khi có product context | Cả hai `product_lookup`, giữ đúng query/SKU và facts đọc lại |
| Sắp hết ngưỡng 3 → “Hàng hết” / “Còn hàng hết” | Giữ mode sắp hết hoặc hiểu còn hàng | Chuẩn hóa `hang het` → `het hang` trước metric routing | out_of_stock, giữ threshold 3, IDs 19/501 stock 0 |

Chỉ sửa source `backend/app/services/ai_business_dialogue.py` (hai thay đổi nhỏ) và thêm bảy parametrized regression cases trong `backend/tests/test_ai_phase1_correctness.py`. Không đổi SQL/business definitions/auth/schema/commerce. Đã rollback riêng Business API trước mỗi vòng sửa/redeploy; tạm dừng AI/Neo4j/Qdrant để nhường tài nguyên build. Không rollback database.

Targeted lần đầu 26 PASS. Lượt bổ sung out-of-stock có ba failure vì seed test dùng một câu chưa thuộc grammar; giữ log, sửa seed sang yêu cầu tồn kho đầy đủ, không bỏ assertion. Sau đó 29 PASS. **Kiểm chứng cuối phạm vi shared coordinator, Phase 1 correctness, role access và Phase 4–5 replay: 128 passed, 692 deselected, 1 deprecation warning; 3,36s.** Không tuyên bố full 820 tests đã được chạy. Full Backend 813 + AI 315 thành công/1 skip trước phiên vẫn là bằng chứng offline cũ; các source không liên quan được bảo toàn.

Các lỗi harness được tách khỏi lỗi ứng dụng:

- c01/c02 bị PowerShell pipe đổi dấu thành `?`; UTF-8 hex xác nhận. Loại khỏi acceptance, không rollback vì hai probes này. Các ca hợp lệ chạy từ file UTF-8.
- HTTP index.html ban đầu khác raw source vì nginx sub_filter có sẵn; 574 raw files vẫn khớp. Sửa expected HTTP bytes trong harness, không sửa frontend.
- API revenue có thêm timezone/time_basis mà AI metric data không lặp lại. Reconciliation đối chiếu toàn bộ trường amount/count/buckets và kiểm riêng metadata, không coi khác shape là sai tiền.
- Lần đo cold đầu assertion quá sớm khi service chưa ready, không đủ artifact response; loại khỏi số đo. Lượt đo hợp lệ sau lưu đầy đủ cả 502/degraded/ok. Tab Staff đã đóng gây TargetClosedError ở bring_to_front; context request còn authenticated, phép đo sau dùng chính context đó, không lấy cookie từ profile cá nhân.

## 4. Customer live acceptance

**PASS core với giới hạn availability/index bên dưới.** 43 lượt UTF-8 hợp lệ qua proxy và phiên Customer do người dùng đăng nhập UI chính thức. 174 checks phân tích responses/facts/hard constraints; không dùng synthetic expected product facts. Thêm ba public probes hai conversation độc lập và các lượt cold/warm tách riêng.

| Ca / expected | Actual đã kiểm | Kết quả |
| --- | --- | --- |
| Greeting đúng capabilities, không ép retrieval | `greeting`, giới thiệu search/advice/compare | PASS |
| Nhẫn bạc dưới 5 triệu; multi-attribute | ID 2, Nhẫn / Bạc 925, giá 2.619.639, stock 60; facts bằng Business API | PASS facts/constraints |
| “Còn vòng đeo tay”: đổi category, giữ material/budget | ID 42, Vòng tay / Bạc 925, giá <5 triệu, stock >0 | PASS |
| “Tôi muốn đổi sản phẩm” | Hỏi đổi mẫu đang tư vấn hay đổi/trả món đã mua; không tự thao tác commerce | PASS |
| “Đổi nhu cầu khác” → dưới 2 triệu → bông tai | Reset điều kiện cũ, IDs 275/448 là Bông tai <2 triệu, không ép giữ Bạc 925 | PASS |
| Ruby + material + khoảng giá, bỏ giá sàn, bỏ gemstone/material | Không tự nới khi rỗng; sau clear gemstone giữ max 4 triệu, sau clear material xuất hiện material khác | PASS constraints; completeness BLOCKED riêng |
| Bỏ ngân sách, rồi đổi vòng tay và bỏ material | Lượt kiểm lại có Nhẫn Bạc 925 giá >4 triệu; đổi vòng vẫn giữ Bạc; bỏ material cho phép chất liệu khác | PASS lượt kiểm lại |
| Clarification hai lần → hủy → task cụ thể | Một câu làm rõ rồi `clarification_escape`; cancel giữ hard slots; vòng tay tiếp tục được | PASS |
| Gift/style advice | Quà sinh nhật <2 triệu có cards grounded; style advice nêu advisory, không gán verified style cho cards | PASS trong contract hiện hữu |
| Compare hai card đầu | So đúng IDs 87/2; tên/material/gemstone/price/stock và chênh giá 1.231.152 khớp authority | PASS |
| “Mẫu thứ hai có chất liệu gì?” → “Mẫu đó giá bao nhiêu?” | Cùng referenced ID 2, đúng facts hiện tại | PASS |
| Similar sau chọn mẫu 2 | Cards 87/203/302, không trả reference 2, giữ Nhẫn / <5 triệu, facts khớp Business | PASS scope/facts; recall/ranking BLOCKED |
| Empty dưới 1 đồng → vòng tay | Không cards, không nới budget/material/gemstone; catalog authority không có món còn hàng giá <1 đồng | PASS |
| Business authority cho cards | Mọi card của 43 lượt hợp lệ so name/price Decimal/stock/category/material với catalog/API thật | PASS |
| Customer gọi Staff/Admin | 403 / 403 | PASS |
| Hai conversation public độc lập | Conversation thứ hai không kế thừa Bạc/<5 triệu, conversation đầu vẫn giữ constraints | PASS independent conversations |

**Hai transient không che giấu:** c15 bỏ budget trả `catalog_unavailable` sau 5,719s, c16 đổi category tiếp đó cũng unavailable (cooldown), không cards và không áp dụng state một phần. Các ca c43–c45 kiểm lại PASS khi hệ thống ổn định. Không khẳng định availability 100% hoặc đã xác định nguyên nhân gốc transient; SourceGate catalog deadline 4s/cooldown 10s có sẵn được giữ nguyên, không nới timeout để PASS.

Các câu chỉ “mẫu thứ hai”, “mẫu đó” sau compare đã dẫn đến clarification thay vì đoán; ghi nhận giới hạn câu rút gọn. Các câu hỏi ordinal/deictic đầy đủ và similar sau lựa chọn rõ đã PASS; không gắn nhãn mọi cách nói tiếng Việt đều được hiểu.

Customer endpoint vẫn public và conversation ID đại diện bearer conversation; phép kiểm ở đây chứng minh tách hai conversation độc lập, **không chứng minh binding Customer conversation với account/cookie đăng nhập**. Staff/Admin có binding role/account/hash auth session theo thiết kế Phase 4–5; không thay auth để mở rộng Customer trong phiên này.

Customer runtime/COPY inputs trong AI, shared, data/output không đổi giữa image đã chạy 43 lượt và image cuối; checksums 160 file trong image cuối đều khớp. Vì sửa chỉ Staff coordinator Backend, không chạy lại toàn bộ Customer suite trên cùng source. Cold/warm và isolation bổ sung được chạy trên AI image cuối.

## 5. Staff live acceptance

**PASS trên image cuối**, 27 lượt accepted; các lượt trước sửa vẫn giữ riêng và không tính là PASS cuối. Business API và PostgreSQL độc lập đối chiếu product facts, stock totals/IDs, status/payment và UTC+7 created_at scope.

| Ca / expected | Actual | Kết quả |
| --- | --- | --- |
| Greeting | Đúng capabilities Staff, read-only | PASS |
| Tra tên Nhẫn Golden Dream | 5 matches, has_more=true, không tự chọn một mẫu khi tên trùng | PASS |
| SKU SP000002 → giá/tồn followup | Đúng ID 2, stock 60, giá 2.619.639, giữ query; không chuyển toàn kho | PASS sau sửa |
| Inventory ngưỡng 3 → sắp hết | 501 tổng, 2 out, 0 low; followup giữ threshold 3 | PASS |
| “Hàng hết” sau low | IDs 19/501, stock 0; ngưỡng 3 giữ nguyên | PASS sau sửa |
| Ngưỡng 5, sắp hết, ngưỡng 0 | Low 5 = 4, IDs 214/313/451/458 stock 5; low 0 = 0 | PASS |
| Tổng / shipping / cancelled / packing / paid | 17 / 1 / 1 / 0 / 7, bằng API order summary và SQL | PASS |
| Shipping tháng 11 → tháng 10 | 1 → 0, giữ shipping; dates 01–30/11 và 01–31/10 | PASS |
| Bỏ thời gian; “chỉ đã thanh toán” | Về shipping all-time 1; sau exclusive paid =7 và clear shipping | PASS |
| Hà Nội chưa hỗ trợ → bỏ qua → inventory | Không trả sai total; reset thoát pending, task mới chạy | PASS |
| Revenue, mixed inventory+revenue, yêu cầu cập nhật stock | Unsupported, data=null, không trả partial Admin data hoặc thực hiện write | PASS |
| Reset → tháng 10 không metric | Clarify/unsupported, không đoán task cũ | PASS |
| Gọi Admin endpoint | 403 | PASS |

## 6. Admin live acceptance và business definitions

**PASS**, 27 lượt chính. Tổng đối chiếu Staff/Admin **310 checks** qua 12 nguồn API có scope rõ và PostgreSQL SELECT trong transactions read-only. Reconciliation có timestamp; không giả định nhiều HTTP requests dùng chung một transactional snapshot. Digest bảng nghiệp vụ trước/sau không đổi.

| Metric / expected scope | Actual đối chiếu API và SQL | Kết quả |
| --- | --- | --- |
| Revenue tháng 11/2026 | 27.986.633,00 VND / 4 eligible orders / 1 month bucket | PASS |
| Followup tháng 10 | 13.814.291,00 / 3 eligible orders / 1 month bucket | PASS |
| Nov so với tháng trước | Current Nov, baseline Oct; +14.172.342,00 VND; +102,59% Decimal | PASS |
| Shipping tháng 11 → tháng 10 | 1 → 0 theo created_at, giữ status | PASS |
| Orders Oct so với Sep | 0 → 0, difference 0, percentage null và giải thích baseline 0 | PASS |
| Top 3 sau revenue tháng 11 | Giữ tháng 11; ID 1, quantity 5, gross item value 27.986.633,00; metric confirmed_payment_sales | PASS |
| Purchase tháng 11 | 14 orders / 3 unique buyers / 2 repeat buyers / 22 units / 3 coupon orders; average 1,57 | PASS |
| Purchase tháng 10 sau task switch | 3 orders / 2 buyers / 1 repeat / 3 units / 0 coupons | PASS |
| Current inventory | 501 / out 2 / low 5 =4; period clear, snapshot hiện tại | PASS |
| Revenue + shipping Nov → Oct | Cả hai metrics giữ/đổi cùng kỳ, mỗi metric time basis riêng | PASS |
| Multi comparison Oct vs Sep | Revenue +13.814.291,00; shipping 0; cả percentages null vì baseline 0, không trả partial | PASS |
| Revenue quý 3/2026 | 0 / 0, đủ 3 month buckets | PASS |
| Revenue năm 2026 | 41.800.924,00 / 7, đủ 12 month buckets | PASS |
| Leap day 29/02/2024 | 0 / 0, đúng 1 day bucket | PASS |
| Range 01/09–15/10/2026 | 0 / 0, đủ 45 day buckets và đúng biên UTC+7 | PASS |
| Explicit Sep vs Aug zero | 0 → 0, percentage null | PASS |
| Branch filter, compare thiếu kỳ sau reset, delete order, historical inventory | Unsupported/clarify, data=null; không trả số một phần hoặc thực hiện write | PASS |

Revenue đã so **mọi bucket, amount, count, start/end/group**, không chỉ tổng. Top đã so ranked IDs/name/quantity/gross item amount với endpoint và SQL độc lập. Purchase so toàn bộ report fields với API, năm primary aggregates với SQL độc lập, sum daily counts và average tính lại. Inventory so tổng/ngưỡng và từng stock; orders so đúng status/payment/period bằng SQL và các API nguồn.

Business definitions không đổi: revenue/top chỉ tính eligible confirmed payments theo `payment_transaction.verified_at`, timezone `Asia/Ho_Chi_Minh` (UTC+7); giữ tất cả reconciliation/paid/verified/amount/provider exclusions. Order counts theo `created_at`; inventory hiện tại; purchase gồm mọi trạng thái orders/order_items, kể cả cancelled/unpaid, không phải web browsing/search events hoặc confirmed revenue. Không suy profit/forecast/causal behavior; không sinh SQL bằng LLM.

## 7. RBAC, isolation, read-only và provider gates

| Phiên qua proxy thật | Staff chat | Admin chat |
| --- | --- | --- |
| Anonymous | 401 | 401 |
| Customer UI login | 403 | 403 |
| Staff UI login | 200, dữ liệu đúng | 403 |
| Admin UI login | 200, dữ liệu đúng | 200, dữ liệu đúng |

Isolation live PASS: Staff account conversation ID đưa vào Admin account trên cùng Staff endpoint tạo conversation mới, không kế thừa state; cùng Admin chuyển Admin→Staff endpoint cũng tạo conversation mới; hai lần user đăng nhập cùng tài khoản Admin ở contexts riêng cũng không kế thừa metric/kỳ. User xác nhận đã dùng lại cùng Admin account; không xuất identity/cookie/token/ID để chứng minh. Conversation IDs chỉ ở bộ nhớ. `/ai/internal/metrics` và `/api/internal/metrics` qua public proxy đều 404.

User tự đăng nhập Customer, Staff, Admin và Admin session thứ hai trên Chrome test riêng; không đọc profile cá nhân, không export storage state/trace/HAR hoặc login screenshots. Không seed account/session trực tiếp. Read-only chat tools không đổi business tables; snapshot read-only xác nhận **22/22 bảng ngoài user_sessions giữ nguyên counts và digest**. user_sessions 23→27 do đúng bốn UI login chính thức; schema/alembic, products, orders, payments, index jobs và các bảng nghiệp vụ khác không đổi. Đây là proof trạng thái trước/sau cộng dispatch read-only, không phải instrumentation từng SQL statement trong live web process.

Các effective LLM gates Price, Customer Dialogue, Semantic Planner, Hybrid NLU, Grounded Narrative, shared Dialogue LLM, Staff classifier và Admin classifier đều false (environment hoặc source default false), runtime env hashes giữ nguyên. Semantic DST/MiniLM warmup vẫn bật như trước; không bật thêm LLM flags/provider hoặc tải model.

Provider observation: local Ollama server.log offset **2603→2603**, appended bytes **0**, observed POST `/api/chat` hoặc `/api/generate` **0** trong cửa sổ acceptance. Kết hợp gates false và source/COPY checksums đã xác minh, đạt kiểm zero observed provider calls theo phương pháp này. **Giới hạn:** không có instrumentation từng function/socket live hoặc bằng chứng log của mọi endpoint provider có thể tồn tại; không dùng số model đang load thay số calls.

## 8. Cold/warm response latency thực tế

Đo process-cold bằng restart cùng container, không clear Docker/OS cache, không đổi model/flags/auto-warmup. Functional acceptance dùng các phiên đúng role; timing Staff/Admin giữ các contexts đăng nhập chính thức; timing Customer bổ sung dùng public endpoint qua cùng proxy. Không suy P95/throughput/SLA từ ít mẫu.

| Chatbot / cùng query trong nhóm timing | Process-cold: HTTP 200 đầy đủ đầu tiên | 3 warm requests | Restart đến response đầy đủ |
| --- | --- | --- | --- |
| Customer: nhẫn <5 triệu | 2,3192s, dense+graph+lexical, facts/constraints đúng | 0,6071 / 0,3758 / 0,3992s | 20,2879s gồm restart, retries và nghỉ giữa probes |
| Staff: tổng đơn | 0,1247s, count 17 đúng | 0,0138 / 0,0220 / 0,0153s | 6,2313s gồm controller polling/retries |
| Admin: tổng đơn | 0,0972s, count 17 đúng | 0,0140 / 0,0139 / 0,0135s | 3,6072s gồm controller polling/retries |

Customer startup: hai response 502 (0,0212 / 0,0258s), ba HTTP 200 **degraded** chỉ graph+lexical (0,8313 / 0,6842 / 2,4509s), rồi response ok đủ ba nguồn. Không tính các 200 degraded là full-readiness PASS. Staff startup có hai 502; Admin có một 502, tất cả giữ trong artifacts. Website có gián đoạn ngắn chủ động trong các phép restart này, sau đó phục hồi healthy/semantic ready. “Cold” ở đây là process-cold với auto model warmup hiện hữu, không phải tải model mới hoặc cache lạnh từ disk.

Các latency của 43 Customer +27 Staff +27 Admin functional turns được lưu riêng trong responses. Transient catalog 5,719s và các 502 lúc restart không bị loại để làm đẹp thống kê; chúng là giới hạn reliability được báo rõ.

## 9. BLOCKED và giới hạn chưa nghiệm thu

- **BLOCKED_INDEX_CONSISTENCY riêng cho Customer retrieval:** freshness, complete recall/ranking, graph path consistency, SQL–Neo4j–Qdrant projection parity. Đọc được PostgreSQL 501 sản phẩm và Qdrant 500 points không chứng minh completeness. Drift lịch sử thiếu 501/stock 1/19/488 chưa sửa và chưa tái audit từng projection; không dùng facts của cards đã verify để tuyên bố index PASS.
- Không chạy worker, canary, reindex, index repair hoặc backlog processing; Phase 2B tiếp tục hoãn đến hosting. Digest `product_index_jobs` giữ nguyên, không claim/ack/enqueue jobs.
- Chưa chứng minh end-to-end deadline/cancellation của SQL thật, persistent/multi-replica conversation state, distributed transactional snapshot, concurrency/load/P95, held-out human quality hoặc mọi paraphrase tiếng Việt.
- Chưa live fault-test inactive/expired sessions và lỗi mọi datastore; không sửa auth/DB để tạo fixture các ca này. Ma trận active/missing-session và cross-role/account/session nêu trên đã live PASS.
- Payment-by-period, status+payment, order grouping, historical inventory, grouped top-selling/ranking comparison và profit/forecast/causal inference vẫn ngoài contract; phải clarify/refuse, không thay định nghĩa nghiệp vụ để đáp ứng.
- Hai transient catalog unavailable, bare ordinal/deictic clarification và startup 502/degraded là quan sát thật. Không tuyên bố zero-error availability hoặc final chatbot accuracy tổng quát.

## 10. Artifacts, bảo toàn và bàn giao

Artifacts tập trung `.local-tmp/live-phase3-5/`:

- `preflight.json`, `resume-1/`: bằng chứng hai điểm chặn cũ, runtime/config snapshot và rollback tags/overlay.
- `source-manifest.json`, `source-manifest-correction.json`, `source-manifest-final.json`, `deployment-inputs.json`, `acceptance-correction.json`: provenance đầu/trung gian/cuối; không chứa env values.
- `deployment/`, `deployment-correction/`, `deployment-final/`: build logs/resource samples, images/checksums/startup/runtime/frontend verification; targeted test logs/XML giữ cả failed seed.
- `browser-control/`, `customer-*.json`, `staff-*-accepted.json`, `admin-*.json`: queries và responses đã bỏ IDs; các lượt FAIL trước sửa giữ riêng, không ghi đè thành PASS.
- `customer-reconciliation.json` (174 checks), `business-reconciliation.json` (310 checks), `postgres-authority.json`, `catalog-authority.json`: expected/actual và nguồn đối chiếu read-only.
- `session-isolation-*.json`, `customer-session-isolation.json`, `customer-rbac.json`, `staff-business-authority.json`: ma trận quyền/isolation và authority aggregate, không PII đơn hàng.
- `cold-warm-latency.json`, `business-cold-warm-latency.json`, `deployment/live-resource-monitor.json`: số đo thực tế, gồm 502/degraded và các mẫu RAM/swap/OOM.
- `deployment/database-before.json`, `deployment/database-after.json`, `final-evidence.json`, `final-summary.json`: digest/count business preservation, flags/provider/health/resources và kết quả cuối.

Chỉ báo cáo Markdown này được tạo/cập nhật cho live phase. Không sửa frontend, schema, auth, commerce, business definitions hoặc báo cáo Phase 1–5 cũ. Không prune, xóa/reset database/volumes, commit/push/merge hay Phase 6/7. Test browser và monitor riêng đã đóng/dừng; **7 services website được giữ chạy tại http://localhost:18080**. Giữ rollback images và tất cả volumes.

**Điểm dừng: bàn giao deployment/live acceptance core ba chatbot, ghi BLOCKED riêng index consistency và các giới hạn trên; không tự chuyển phase.**
