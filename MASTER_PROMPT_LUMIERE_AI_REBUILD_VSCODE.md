# MASTER PROMPT — TÁI KIẾN TRÚC DATN LUMIÈRE
## Dành cho AI coding agent trong Visual Studio Code (Codex/Cursor/Claude Code)

> **HÃY ĐỌC TOÀN BỘ TỆP NÀY TRƯỚC KHI THỰC HIỆN.** Bạn là AI coding agent có quyền đọc repository và, ở các giai đoạn thích hợp, sửa mã, chạy lệnh, viết kiểm thử. Đây là đặc tả thực thi dự án, KHÔNG phải yêu cầu chỉ viết tư vấn hay dựng mockup. Phải tạo ra mã thật, kiểm thử thật, sơ đồ thật và bằng chứng có thể tái lập. Không được tuyên bố hoàn thành hạng mục nếu chưa kiểm chứng.

## 0. VAI TRÒ, MỤC TIÊU VÀ BỐI CẢNH

Bạn đóng vai trò nhóm kỹ thuật phối hợp: Software Architect, Senior FastAPI Developer, NLP/RAG Engineer, Knowledge Graph Engineer, Search/Recommender Engineer, Data Engineer, DevOps/SRE, Security Engineer, QA/Evaluation Engineer và Technical Writer.

Dự án: **LUMIÈRE — website thương mại điện tử trang sức có AI cho Customer, Staff, Admin**, là đồ án tốt nghiệp. Mục tiêu là nâng chất lượng kỹ thuật và thực nghiệm để có cơ sở bảo vệ ở mức điểm cao, **không được hứa hẹn điểm số**.

- Workspace Windows được dự kiến tại `D:\LUMIERE-FINAL-TEST` (chỉ là đường dẫn tham khảo, phải kiểm tra).
- Repo tham khảo: `https://github.com/NhungHuyen2110/DATN` và các nhánh local hiện có. Không coi nhánh từ hội thoại cũ là trạng thái hiện tại.
- Công nghệ đã được người dùng báo cáo: frontend HTML/CSS/JavaScript; Business API FastAPI; Customer AI FastAPI; PostgreSQL; Qdrant; Neo4j; Sentence Transformers; Ollama/Qwen; CrewAI; xác thực và phân quyền Customer/Staff/Admin. Các thư mục, tên module và phiên bản chỉ được xác nhận sau khi đọc source.
- Backend nghiệp vụ từng chạy cổng 8001, AI từng chạy cổng 8000, PostgreSQL từng dùng 5433. Không hardcode theo các thông tin lịch sử.
- Tài liệu tham khảo về prompting: `https://www.promptingguide.ai/` (RAG, prompt chaining, graph prompting, structured outputs, few-shot, tool use). Chọn kỹ thuật có lý do và kết quả đánh giá, không đưa vào chỉ để tạo vẻ phức tạp.

**TRỌNG TÂM TUYỆT ĐỐI:** Semantic understanding tiếng Việt, Knowledge Graph thật với node/relationship, **import CSV → graph bằng CODE tự động**, semantic-first hybrid retrieval, top-K relevance ranking chính xác, explainable graph-based recommendation, chỉ số thực nghiệm. Bổ sung đầy đủ kiến trúc triển khai Docker tách dịch vụ, hạ tầng công khai, Grafana/Prometheus, CI/CD. Không được chỉ thêm vài script hoặc màn hình trình diễn không kết nối hệ thống.

## 1. NGUYÊN TẮC AN TOÀN — KHÔNG ĐƯỢC PHÁ HỎNG BẢN CŨ

1. **Bước đầu tiên chỉ AUDIT READ-ONLY**: kiểm tra tệp, `git status`, cấu trúc package, API, migration, Docker, database schema nếu có quyền read-only, test hiện tại, tài liệu. Không chỉnh sửa hay xóa gì trong giai đoạn audit.
2. Báo cáo AS-IS + GAP + TO-BE trước khi bắt đầu thay đổi. Khi đã có baseline, tiến hành nâng cấp **theo từng giai đoạn**, không viết lại tất cả cùng lúc. Đây là yêu cầu xây dựng lại **kiến trúc và thành phần không đạt**, không phải lệnh xóa tất cả logic đang chạy.
3. Tạo nhánh làm việc hoặc worktree riêng khi trạng thái Git cho phép, sao lưu an toàn và checkpoint trước mỗi thay đổi rủi ro. Không được ghi đè working tree đang có thay đổi của người dùng. Không tự `git reset --hard`, `git clean -fd`, `DROP`, `TRUNCATE`, `docker compose down -v` hoặc xóa volume.
4. Không đọc rồi in ra màn hình secret đầy đủ; không commit `.env`, token, mật khẩu, private key, backup chứa dữ liệu nhạy cảm. Tạo `.env.example` dùng giá trị giả. Không gửi mã nguồn, dữ liệu khách hàng hoặc credential tới công cụ/dịch vụ ngoài khi chưa được phép.
5. Không sửa phá các chức năng hiện hữu: tài khoản, đăng ký/đăng nhập/quên mật khẩu, catalog, giỏ hàng, đặt hàng, thanh toán, quản lý Staff/Admin, API và Customer AI hiện có. Nếu cần thay giao diện/API, tạo adapter tương thích, feature flag và migration an toàn.
6. Với database và CSV, **không tự chạy import có khả năng ghi dữ liệu production** khi chưa xác định đúng môi trường và backup. Hãy thiết lập môi trường dev/staging trước, dry-run, rồi import và đối soát ở dev. Thao tác production cần phê duyệt riêng.
7. Những lệnh có tác động dữ liệu, mua host/domain, triển khai công khai hoặc thay đổi secrets phải dừng xin chấp thuận. Những thay đổi nội bộ an toàn sau khi có checkpoint có thể làm tuần tự và báo kết quả.
8. Không phát minh kết quả thí nghiệm, độ chính xác, thời gian phản hồi, dữ liệu sản phẩm hoặc điểm xếp hạng. Mọi chứng cứ cần log/test/script tái lập.
9. Nếu một thư viện/model/nguồn dữ liệu không có hoặc không tương thích, nêu rõ, đề xuất phương án tương thích và tiếp tục những việc khả thi; không lặng lẽ thay stack.
10. Mỗi phase cần có: mã đã sửa + lệnh chạy PowerShell/Windows hoặc Docker + kiểm thử + expected/actual + lưu ý rủi ro + cách rollback + bằng chứng phục vụ DATN.

## 2. PHASE 0 — READ-ONLY CODEBASE AUDIT (PHẢI LÀM ĐẦU TIÊN)

Khám phá workspace thực tế. Kiểm tra:
- `git status --short`, branch, tracked/untracked changes, `.gitignore`, dependencies, phiên bản Python/Node, cấu trúc `backend/`, `frontend/`, `AI/`.
- Business API, Customer AI API, các router FastAPI, endpoint AI Admin/Staff, module JWT/session/role guard, CORS, password reset, DB migrations.
- PostgreSQL schema: Products, Users, Orders, Payments, Inventory, Categories, Attributes; khóa chính/ngoại, nguồn sự thật về giá và tồn kho.
- Qdrant collections, vector dimensions, distance metric, embedding model, metadata/payload, search API, indexing/update flow.
- Neo4j node labels, relationship types, indexes, constraints, bằng chứng graph được sử dụng như thế nào khi trả lời; script CSV/ETL đang tồn tại chưa.
- Ollama/Qwen, prompts, CrewAI, RAG/agent orchestration; query understanding, entity linking, graph search, lexical/dense search, ranking, fallback, citations/grounding.
- Dockerfile/compose, healthchecks, environments, logging, tests, CI/CD, domain/hosting.
- Tài liệu giảng viên được cung cấp trong workspace (nếu có). Không giả định đã đọc được video hoặc nội dung Drive nếu file chưa truy cập được.

Xuất tài liệu `docs/00-audit-as-is.md` (sau khi giai đoạn read-only đã kết thúc và chuyển sang giai đoạn tài liệu) với:
1. File-tree thực tế và sơ đồ AS-IS (Mermaid).
2. Bảng Requirement → Source file/function → trạng thái: verified / exists-not-tested / missing / unclear.
3. Các bug và điểm yếu quan trọng, đặc biệt CSV-to-Neo4j, aliases, Top-K, cosine similarity và lỗi phân quyền.
4. Kiến trúc TO-BE, phương án migration, dependency map, ước lượng tài nguyên.
5. Baseline regression tests hiện tại; ưu tiên giải quyết theo tác động tới chất lượng AI và nguy cơ vỡ hệ thống.
6. Kế hoạch phase bằng checklist. **Không được giả định audit đã hoàn thành nếu chưa đọc file thực tế.**

## 3. KIẾN TRÚC ĐÍCH — SEMANTIC-FIRST + GRAPH-ENHANCED HYBRID RETRIEVAL

Luồng đích:

```text
Customer / Staff / Admin
  → Frontend (riêng)
  → HTTPS Reverse Proxy / API routing
  → Business API (riêng) ─── PostgreSQL (system of record)
  → AI API (riêng)
       → Authentication / RBAC / Intent router
       → Vietnamese query normalization + entity extraction
       → Canonical Entity Linking (aliases + embedding + context)
       → Query planner (structured constraints, Top K)
       ├→ Dense semantic search (Qdrant)
       ├→ Lexical/BM25/sparse search (khi cần chính xác tên/mã)
       └→ Graph traversal/recommendation (Neo4j)
       → Candidate union + deduplication + filtering
       → Rank fusion + optional cross-encoder/graph-feature reranking
       → Verify price/stock/visibility against Business API/PostgreSQL
       → Return exact requested Top K if enough valid results
       → Grounded RAG response via Ollama/Qwen; no invented products
       → Frontend result cards + explanations + diagnostics (admin-only)

Business product changes
  → Transactional outbox or reliable sync job
  → Worker ingest/normalize → Qdrant upsert + Neo4j upsert
  → sync logs + retry + reconciliation
```

**ĐỊNH NGHĨA CHO ĐÚNG:** RAG là kiến trúc truy xuất + sinh câu trả lời, không phải database; PostgreSQL là hệ quan hệ và nguồn nghiệp vụ; Qdrant là công cụ truy xuất vector/sparse; Neo4j tối ưu liên kết/truy vấn đồ thị. Semantic Search là so sánh ý nghĩa trong embedding; Hybrid Retrieval thường phối hợp dense và lexical/sparse (có thể bổ sung graph). Không gọi hai khái niệm là hoàn toàn đồng nghĩa.

## 4. KIẾN TRÚC VÀ LUẬT KNOWLEDGE GRAPH — ƯU TIÊN SỐ 1

### 4.1 Graph schema có kiểm soát

Khảo sát dữ liệu thật trước khi định schema. Đề xuất node:
`Product`, `Category`, `Brand`, `Material`, `Gemstone`, `Style`, `Occasion`, `Audience`, `Collection`, có thể bổ sung `Color`, `DesignFeature` khi dữ liệu chứng minh.

Quan hệ có hướng, whitelist rõ: `BELONGS_TO`, `MADE_OF`, `HAS_GEMSTONE`, `HAS_STYLE`, `SUITABLE_FOR`, `PART_OF_COLLECTION`, `PRODUCED_BY`, `HAS_COLOR` nếu hợp lệ. Không tạo node/relation ngoài schema tùy hứng. Bắt buộc tài liệu `docs/knowledge-graph-schema.md`: ID, tên, thuộc tính, nguồn gốc, ý nghĩa, chiều quan hệ, constraints/indexes, ví dụ Cypher và cách đối soát từ PostgreSQL.

Ví dụ:
```
(:Product {product_id:"P123"})-[:SUITABLE_FOR]->(:Audience {canonical_id:"female", name:"Phái nữ"})
(:Product {product_id:"P123"})-[:HAS_GEMSTONE]->(:Gemstone {canonical_id:"cz"})
```
Chỉ gắn `SUITABLE_FOR female` nếu dữ liệu hoặc quy tắc nghiệp vụ có bằng chứng. Không suy diễn giới tính dựa trên hình ảnh/định kiến.

### 4.2 Semantic Entity Resolution tiếng Việt

Ví dụ `Audience {canonical_id: female, name: "Phái nữ"}` có alias từ vựng trong ngữ cảnh phù hợp như: `phụ nữ`, `nữ giới`, `con gái`, `đàn bà`, `dành cho nữ`, `phái nữ`. Nhưng `con gái` có thể là trẻ em hoặc quan hệ gia đình tùy câu hỏi; không luôn gộp vào `female adult`.

Thiết kế:
- Vietnamese Unicode normalization (NFC), xử lý lỗi dấu thông thường, punctuation, từ ghép, viết không dấu; không làm mất thông tin quan trọng.
- Alias dictionary **lưu bằng dữ liệu có thể cập nhật/phiên bản**, không hardcode rải rác; `aliases_vi.yaml`/bảng `EntityAlias`/node Alias là gợi ý, chọn theo hiện trạng.
- Entity detection theo ngữ cảnh: danh mục, đối tượng, đá, chất liệu, phong cách, dịp, ngân sách.
- Entity linking: exact normalized alias → candidate alias/embedding → kiểm tra context/schema → confidence threshold/ambiguity handling. Không chỉ dùng so khớp `name` của node; không tự gộp node chỉ vì cosine cao.
- Với câu "nhẫn cho con gái", hiểu truy vấn có thể trỏ Audience nữ, đồng thời ràng buộc Category nhẫn. Với "mua nhẫn tặng con gái 8 tuổi", phải xử lý khác hoặc hỏi rõ.
- Test câu paraphrase và unseen synonyms: "phái nữ" / "nữ giới" / "phụ nữ" / "con gái"; "nhẫn tinh tế" / "nhẫn tối giản" có semantic gần nhưng không tuyệt đối đồng nghĩa.
- Bảo đảm liên kết có explainable evidence: alias nào match, similarity có được tính không, quan hệ nào đã truy vấn.

### 4.3 LLM dùng để bóc tách node/cạnh CÓ KIỂM CHỨNG

Dữ liệu cấu trúc (product_id, category_id, material_id, gemstone) phải lấy trực tiếp từ CSV/PostgreSQL thay vì nhờ LLM đoán. Chỉ dùng LLM tạo ứng viên quan hệ từ văn bản mô tả chưa có cấu trúc; structured JSON output theo schema Pydantic/JSON Schema, whitelist labels và rel types, validate evidence span thực sự có trong input, normalize entity, đối soát với catalog, lưu provenance và review flag. Không tin LLM tạo đúng nếu không kiểm chứng. Không trực tiếp chạy Cypher do LLM sinh; sử dụng Cypher có tham số đã kiểm soát.

Đề xuất hai graph layers: (1) **fact relationships** đã kiểm chứng, dùng cho truy vấn; (2) **candidate relationships** từ LLM chưa duyệt, không tự dùng như sự thật. Viết test cho dữ liệu sai, mô tả gây nhầm, dấu tiếng Việt, thiếu thông tin, trùng thực thể.

## 5. BẮT BUỘC: ĐỔ CSV THÀNH NODE/RELATIONSHIP BẰNG PYTHON CODE — KHÔNG THỦ CÔNG

**ĐÂY LÀ TIÊU CHÍ CHẤM VÀ ACCEPTANCE GATE CỨNG.** Không được tạo sản phẩm/node/cạnh bằng cách ngồi nhập từng lệnh trên Neo4j Browser. Không dùng tay kéo/thả node. Không chấp nhận "đã import thủ công". Cần pipeline tự động, lưu trong Git, có lệnh tái lập được trên máy sạch/CI (với dữ liệu mẫu phù hợp).

Tạo hoặc tái sử dụng các thành phần mã tương đương:
- `scripts/ingest_csv.py` — parse, validate, normalize và map schema.
- `scripts/import_graph.py` — create constraints/indexes idempotent, upsert node/cạnh qua Neo4j Python driver.
- `scripts/index_qdrant.py` — xây embeddings, upsert collection bằng product_id ổn định.
- `scripts/sync_products.py` — cập nhật sau CREATE/UPDATE/DELETE.
- `scripts/verify_import.py` — thống kê, đối soát node, cạnh, trùng lặp, null/missing, orphan.
- `config/knowledge_graph_schema.yaml` hoặc JSON — labels, properties, rel rules.
- `config/aliases_vi.yaml` — canonical ID và synonyms.
- `tests/test_csv_to_graph.py` — bài test import, idempotency, normalization.
- `docs/csv-to-knowledge-graph.md` — hướng dẫn vận hành và giải thích thuật toán.

Tên file là đề xuất; phải khớp cấu trúc thật và tránh tạo hai pipeline trùng chức năng.

Đặc tả pipeline:
1. **Discover input**: tìm CSV thực tế trong repo hoặc xác định phải export từ PostgreSQL qua một script; không đoán cột. Ghi rõ CSV sample schema và cách map.
2. **Parse bằng code** (`csv.DictReader` hoặc Pandas/PyArrow tùy dữ liệu). Hỗ trợ UTF-8/UTF-8-SIG, BOM, tiếng Việt, null, separator, ngày, giá kiểu số, field quoted, dữ liệu lặp. Không sửa giá và mã sản phẩm tùy tiện.
3. **Validate**: product_id không rỗng, uniqueness, foreign keys/category references, format và dải giá; đưa record không hợp lệ vào error report, không im lặng bỏ qua.
4. **Normalize**: chuẩn hóa tên node/entity, canonical IDs ổn định, taxonomy, alias. Lưu lineage: source filename, source row/record ID, last update, extraction method và evidence nếu cần.
5. **Schema & constraints**: tạo `IF NOT EXISTS` uniqueness constraints/indexes phù hợp Neo4j version; tránh `MERGE` bằng trường thay đổi như display name. Sử dụng stable IDs từ database.
6. **Write in batches**: Python Neo4j driver truyền list records dưới dạng parameter, sử dụng `UNWIND $rows AS row`, `MERGE` theo ID ổn định, `SET` thuộc tính phù hợp và `MERGE` relationship theo hai endpoint đã match; transaction retry có giới hạn cho lỗi retryable. Không nối thẳng dữ liệu CSV vào chuỗi Cypher, không dùng CREATE lặp không kiểm soát.
7. **Idempotency**: chạy import cùng CSV hai lần → số node/cạnh và ID không tăng không hợp lệ. Thay đổi một bản ghi → chỉ những node/cạnh liên quan được cập nhật; xử lý xóa cẩn thận qua soft-delete/tombstone hoặc đồng bộ có kiểm soát.
8. **CLI**: có `--file`, `--dry-run`, `--batch-size`, `--limit`, `--report`, `--resume` khi khả thi; trả nonzero exit code nếu lỗi, log tiến độ và thời gian.
9. **Verification**: kiểm tra số product IDs, số node mỗi label, số relationship mỗi type, orphan IDs, duplicate IDs, graph invariants, ngữ nghĩa của Alias/Audience. Xuất báo cáo CSV/JSON.
10. **Sample fixtures**: có CSV giả lập an toàn đủ gồm đủ trường hợp tiếng Việt và ít nhất 1 ví dụ "Phái nữ"/"con gái"; test được dù không có DB production.
11. **Source of truth**: PostgreSQL nắm giá, tồn kho và thông tin giao dịch; nếu CSV là dữ liệu seed, phải làm rõ provenance và không dùng CSV cũ ghi đè giá mới.
12. **Replayability**: ghi lệnh PowerShell và Docker cho developer: import CSV, build graph, index vectors, verify, query sample. Toàn bộ graph phải tái tạo được từ nguồn dữ liệu + code + config + migration, không yêu cầu thao tác Neo4j Browser.

Ví dụ kỹ thuật tham khảo (chỉ là pattern, phải điều chỉnh schema thật):
```cypher
UNWIND $rows AS row
MERGE (p:Product {product_id: row.product_id})
SET p.name = row.name, p.source = row.source
WITH p, row
MATCH (a:Audience {canonical_id: row.audience_id})
MERGE (p)-[:SUITABLE_FOR]->(a)
```
**Nếu `audience_id` không có bằng chứng, không sinh relation trên.** Script phải tạo/kiểm tra Audience chính xác và không làm mất những relationship khác.

Definition of Done CSV → Knowledge Graph:
- Không có bước nhập node/cạnh bằng tay.
- Đã thực thi script trên dữ liệu mẫu và dataset được phép dùng.
- Chạy 2 lần không phát sinh duplicate.
- Có logs/report + tests + tài liệu và screenshot Neo4j cho minh họa (screenshot chỉ là bằng chứng, không phải phương pháp nhập).
- Có script để dựng lại graph từ đầu trong **môi trường kiểm thử trống có xác nhận**, không xóa graph thật.

## 6. SEMANTIC VECTOR SEARCH — TOP-K PHẢI THẬT SỰ ĐÚNG

Mô hình embedding phải được xác định từ code hiện tại; kiểm thử chất lượng tiếng Việt trước khi thay. Nếu muốn đổi embedding, **phải reindex toàn collection có version**, không trộn vector khác chiều/model.

Mỗi product searchable representation cần gồm các trường thật: product_id, name, category, material, gemstone, style, audience, occasion, mô tả có kiểm chứng. Có thể bổ sung graph-enhanced description nhưng chỉ từ relationships đã được xác thực.

Phân biệt:
- Embedding dimension = số chiều vector, **không phải chiều dài lớn hơn thì sản phẩm gần hơn**.
- Nếu dùng Cosine Similarity, độ tương đồng `cos(q,p)=dot(q,p)/(norm(q)*norm(p))`, không phải độ lớn vector.
- Dot product chỉ tương đương cosine trong các điều kiện chuẩn hóa vector phù hợp; phải xác định đúng distance metric cấu hình Qdrant.
- Top K phải xếp theo score đã định nghĩa, không lấy K record đầu tiên hay xếp theo ID/giá.

Ví dụ truy vấn:
"Cho tôi **top 3 nhẫn** dành cho **con gái**, phong cách **thanh lịch**, **dưới 8 triệu**".
Expected parsed query:
```json
{"intent":"product_recommendation","category":"ring","audience":"female","style":"elegant","max_price":8000000,"top_k":3}
```
Đây là JSON mong đợi của bước hiểu câu hỏi, không khẳng định sản phẩm nào có thật.

Yêu cầu thuật toán:
1. Vietnamese normalization / entity extraction / semantic query representation.
2. Áp dụng **hard filters**: category, giá tối đa, availability, published status và điều kiện không được suy diễn (nếu user nói bắt buộc loại đá cụ thể thì không đề xuất đá khác).
3. Candidate pool **lớn hơn requested K** (có cấu hình `candidate_k`, điều chỉnh theo dataset và performance), dense top N + lexical/sparse top N + graph top N.
4. Union & dedup bởi canonical product_id.
5. Graph features: shared attributes, relevant relationships, độ dài/loại path, evidence. Graph paths không tự thay thế hoàn toàn semantic score.
6. Rank fusion (ví dụ Reciprocal Rank Fusion) **không cộng thẳng điểm cosine và BM25** khi chưa chuẩn hóa/cân chỉnh.
7. Optional rerank bằng cross-encoder phù hợp tiếng Việt hoặc thuật toán learning-to-rank nếu có bộ dữ liệu; đánh giá trade-off latency/chất lượng.
8. Re-validate giá/tồn kho/live status bằng API nghiệp vụ trước khi trả kết quả. Kết quả đúng yêu cầu phải ưu tiên hơn score embedding cao.
9. Sort giảm dần final score, deterministic tie-breaking, giới hạn số trả về **không vượt quá K**, nếu dưới K thì báo rõ chỉ có N phù hợp; không "độn" sản phẩm sai.
10. Response có product_id, rank, matched_entities, matched_relationships, reason, score thực tế ở phần debug/admin. Không bịa numeric scores.
11. LLM chỉ diễn đạt lời giải thích; không được tùy ý reorder/thêm/xóa sản phẩm đã rank.
12. Query "giống sản phẩm A", "cùng đá", "cùng chất liệu", "phong cách tương tự" phải tận dụng graph edges; có minh họa path có thật.

**Ablation bắt buộc:** lexical baseline vs dense semantic vs dense+lexical vs dense+graph vs dense+lexical+graph+reranker. Nêu rõ tương đồng ý nghĩa là mục tiêu chính, lexical chỉ hỗ trợ các mã/tên riêng/thuật ngữ; giải thích thuật ngữ Hybrid Retrieval cho giảng viên đúng kỹ thuật.

## 7. RAG VÀ AI NHIỀU VAI TRÒ (CUSTOMER / STAFF / ADMIN)

### Customer
- Product discovery, recommend, compare, FAQ, bảo hành/chính sách đã có nguồn; order lookup chỉ đơn của người dùng được xác thực.
- Câu trả lời dựa trên product_ids từ retriever và dữ liệu nghiệp vụ. Trả kèm product cards/links nếu phù hợp.
- Nếu Neo4j/Qdrant/Ollama lỗi, fallback theo policy; không trả lời bịa.
- No-result và uncertainty được xử lý rõ ràng.

### Staff
- Hỏi trạng thái đơn, việc cần xử lý, kho theo quyền Staff. Không được truy vấn dữ liệu ngoài quyền. Tái sử dụng các role guards hiện hữu, không dựa vào câu "tôi là admin".

### Admin
- Ví dụ: "Top 5 sản phẩm bán chạy tháng 10/2026", "doanh thu đã thanh toán", "tình trạng kho". Dữ liệu phân tích lấy từ Business API/PostgreSQL bằng SQL/service có kiểm chứng, **không dùng semantic similarity để tính số lượng bán hay doanh thu**.
- Định nghĩa rõ đơn hợp lệ, timezone, chính sách hoàn tiền, hủy đơn và số liệu Dashboard. Có unit/integration tests cho analytics.

### Intent + tool orchestration
- Phân biệt: product retrieval, recommendation, customer-owned order status, business analytics, policies, greeting, out-of-scope.
- Structured intent schema, deterministic tool routing, backend RBAC, validate argument, giới hạn quyền, có audit logs.
- Không gọi LLM tùy ý sinh SQL/Cypher ghi database. Không để nội dung sản phẩm/CSV hoặc prompt injection ghi đè system instruction.
- Phân tích cần giữ hay giản lược CrewAI: agent orchestration chỉ tồn tại khi có mục đích, performance chấp nhận được và kiểm thử được; không bắt buộc multi-agent để lấy điểm.

## 8. ĐỒNG BỘ POSTGRESQL ↔ QDRANT ↔ NEO4J

PostgreSQL là **source of truth**. Qdrant là search index, Neo4j là relationship projection. Thiết kế:
- Product create/update/delete → event/outbox hoặc durable job → ETL/embedding + graph upsert → đồng bộ trạng thái.
- Idempotency keys, retries với exponential backoff, dead-letter/error report, reconciliation job, embedding/index versioning.
- Không để Qdrant/Neo4j stale cập nhật ngược giá hoặc tồn kho vào PostgreSQL.
- Data contract & migration cho thay đổi taxonomy/schema.
- Test đồng bộ khi thêm sản phẩm, sửa giá, sửa chất liệu, xóa/ẩn sản phẩm, worker chết giữa chừng.
- Công cụ `sync status` báo last_success, failed records, lag, Qdrant/Neo4j entity counts.

## 9. DOCKER RIÊNG BIỆT TỪNG KHỐI — BẮT BUỘC

Thiết kế Dockerized architecture cho môi trường Windows Docker Desktop (dev) và Linux VPS (staging/prod). **Frontend, Backend và AI phải có Dockerfile, image, container, build path và deployment lifecycle độc lập**. Không gom chung `frontend + backend + AI` trong 1 Dockerfile/container. Các dịch vụ dữ liệu cũng tách thành container/service hoặc managed equivalents.

Các service đích (điều chỉnh theo tài nguyên thực):
- `reverse-proxy` (Nginx/Caddy/Traefik; HTTPS)
- `frontend` (serve static/build site)
- `business-api` (FastAPI)
- `ai-api` (FastAPI; semantic/graph/RAG)
- `index-worker` (CSV/ETL/sync/outbox)
- `postgres` (volume riêng)
- `qdrant` (volume riêng)
- `neo4j` (data/log volume riêng)
- `ollama` (model volume riêng; local GPU tùy điều kiện hoặc endpoint riêng)
- `prometheus` (metrics)
- `grafana` (dashboard)

Yêu cầu file:
- `frontend/Dockerfile`, `backend/Dockerfile`, `AI/Dockerfile` hoặc paths phù hợp thật.
- `compose.yaml` (dev), `compose.prod.yaml`/profiles hoặc cấu hình deployment tương đương.
- `.dockerignore`, `.env.example`, `infra/` chứa proxy/monitoring.
- Services có tên/ports/healthchecks đúng, `restart: unless-stopped` hoặc chính sách được giải thích, `depends_on: condition: service_healthy` khi phù hợp, networks nội bộ phân tách frontend/proxy, business/data, AI/data, volumes theo service, read-only mounts/non-root khi khả thi, resource limits, log rotation.
- Không public cổng quản trị Postgres/Qdrant/Neo4j/Grafana/Ollama ra Internet một cách không bảo vệ.
- Không hardcode localhost để container gọi container khác; sử dụng service DNS.
- API route `/health/live` và `/health/ready`: liveness không nên liên kết mọi phụ thuộc để gây restart dây chuyền; readiness báo đúng tình trạng phụ thuộc.
- Graceful shutdown, request timeout, retry có giới hạn, circuit breaker, queues hoặc bulkhead khi cần. Không retry vô hạn.
- Independent CI build/versioned Docker images; sửa AI không bắt build lại business/frontend.

### Cô lập lỗi đúng nghĩa (Fault Isolation & Graceful Degradation)

**Tách container không bảo đảm mọi chức năng độc lập tuyệt đối; phải thực hiện bài kiểm thử lỗi như sau:**

| Dịch vụ bị dừng | Hành vi mong đợi / giới hạn thực tế |
|---|---|
| `ai-api` | Các nghiệp vụ website như xem catalog, login, checkout vẫn hoạt động khi business-api và DB khỏe; chatbot báo tạm không sẵn sàng, không làm sập site. |
| `neo4j` | AI ưu tiên fallback Qdrant/SQL theo policy; không khẳng định graph explanation khi graph không truy cập được. |
| `qdrant` | AI fallback lexical/structured SQL hoặc thông báo phù hợp; không giả vờ semantic retrieval vẫn chạy. |
| `ollama` | Search có thể trả product cards deterministic không có LLM narrative; không bịa câu trả lời. |
| `grafana` hoặc `prometheus` | Website/API/AI vẫn chạy; mất quan sát tạm thời, cần cảnh báo bằng kênh độc lập khi có. |
| `frontend` | Business API và AI API có thể còn healthy nhưng giao diện web bị mất; không khẳng định frontend vẫn hoạt động. |
| `business-api` | Giao diện tĩnh vẫn có thể tải nhưng nghiệp vụ liên quan bị lỗi; báo lỗi phù hợp. |
| `postgres` | Giao dịch nghiệp vụ cần DB sẽ không hoạt động; yêu cầu fail safely, không ghi dữ liệu sai, không hứa không ảnh hưởng. |

Viết `tests/fault-injection/` hoặc script kiểm thử dừng/tái khởi động **một container trong môi trường dev**, kiểm tra các endpoint còn lại, thu logs, xác minh restart và phục hồi; không chạy dừng production. Docker compose `up -d --build`, `ps`, `logs`, `stop`, `start`, `restart` phải được tài liệu hóa cho PowerShell và Linux. **Không dùng `docker compose down -v`** trong hoạt động thông thường.

## 10. HOSTING, DOMAIN, HTTPS, BẢO MẬT TRIỂN KHAI

Tạo runbook triển khai VPS/Cloud thật (chưa tự mua host). Đánh giá resource sizing của model Qwen/Ollama, Neo4j, Qdrant, PostgreSQL và RAM/CPU/GPU, vRAM/cold start. Không giả định VPS rẻ chạy toàn bộ inference nhanh.

Đề xuất 2–3 phương án có trade-offs: 1 VPS đủ tài nguyên; web/API/DB trên VPS và AI inference riêng; managed services khi ngân sách cho phép. Ấn định lựa chọn dựa trên ngân sách người dùng xác nhận, **không tự mua domain/host và không tự tạo dịch vụ trả phí**.

Triển khai: HTTPS, DNS, reverse proxy, firewall, private network, secrets, CORS, cookies secure, DB backups & restore rehearsal, deployment staging → production approval, uptime/health endpoints, log & metrics retention, rate limit, least privilege, CI deploy keys, security scans.

## 11. PROMETHEUS + GRAFANA — GIÁM SÁT THẬT

Instrumentation thật:
- HTTP throughput, error rate, status codes, p50/p95/p99 latency theo route template.
- AI request count by intent (không làm lộ query), time spent parse/embedding/retrieval/graph/rerank/LLM, fallback/error counts, total latency.
- DB connection health, slow queries, graph import status, index sync lag, queue depth, resource CPU/RAM/disk, container restart count.
- Dashboard JSON/ provisioning code versioned trong repo, dashboard chỉ truy cập có auth; alert threshold theo baseline, không bịa metric.
- Structured correlation_id/trace_id xuyên frontend → backend → AI → retrievers nếu khả thi; không log reset token, PII, mật khẩu hoặc user queries nguyên văn nếu không có lý do/consent.
- Có ảnh chụp dashboard **từ dữ liệu thật** và hướng dẫn tái tạo tải để đo; Grafana chỉ visualization, metrics phải do Prometheus/exporter thu thập.

## 12. CI/CD — GITHUB ACTIONS RIÊNG THEO KHỐI

Xây dựng workflows sử dụng `paths` filters để Frontend, Backend, AI có thể test/build độc lập khi thay đổi. Pipeline:

```
PR/Push → static check/lint → unit tests → integration tests → image build
→ dependency/security scan → publish versioned images → deploy staging
→ smoke/fault tests → manual approval for production → deploy → health verify
```

- GitHub Actions YAML trong `.github/workflows/`.
- Chạy type/lint/test tương ứng stack đã xác minh (pytest, ruff, JavaScript tests...).
- Integration tests có containers tạm, không dùng DB thật.
- Không deploy khi test fail; không push secret hoặc `.env`.
- Image tag commit SHA, immutable release, staged rollback; có tài liệu release notes và rollback procedure.
- Không tự bật deployment tới domain thật chưa có quyền/approval.

## 13. EVALUATION KHOA HỌC — YẾU TỐ PHÂN BIỆT ĐỒ ÁN

Tạo bộ benchmark có người gán nhãn, mục tiêu ban đầu **>= 100 queries**, đủ nhóm:
- Synonym: `phái nữ`, `con gái`, `nữ giới`, `phụ nữ` theo ngữ cảnh.
- Paraphrases tiếng Việt, không dấu, lỗi chính tả thường gặp.
- Multi-constraint (loại trang sức, giá, đá, chất liệu, phong cách, người nhận).
- Similar product / graph multi-hop / relationship-reasoned recommendation.
- Exact SKU, proper names (lexical cần thiết).
- Top 1/Top 3/Top 5; thiếu kết quả; mặt hàng hết hàng; giá đã thay đổi.
- Out-of-scope, ambiguous intent, role unauthorized, prompt injection.

Mỗi benchmark record: query_id, query, expected intent/entities, expected relevant product IDs, expected hard constraints, expected graph evidence, reviewer, phiên bản dataset. Không lấy chính model đang đánh giá để tự gán truth mà không kiểm tra thủ công.

**Baselines và ablation:**
1. PostgreSQL keyword/ILIKE/full-text baseline (nếu dữ liệu có thể hỗ trợ).
2. Qdrant dense semantic only.
3. Dense + lexical/sparse.
4. Dense + graph.
5. Dense + lexical + graph + reranker.

**Metrics:** Precision@3, Recall@K, MRR, nDCG@3, entity-linking accuracy, graph relation precision/recall từ sample labeled, hard-filter violation rate, Top-K count compliance, groundedness/hallucination, latency p50/p95, fallback success, fault-recovery duration, CPU/RAM.

Split train/validation/test cho tuning model/weights, không tối ưu trên test cuối. Tạo scripts có lệnh tái lập, báo cáo CSV/JSON, biểu đồ, cấu hình môi trường & git commit SHA. Không đo tốc độ trên môi trường tải không tương đương rồi kết luận phương án hơn tuyệt đối. Nếu không đủ data để kết luận, ghi rõ giới hạn.

**Mục tiêu đồ án:** chứng minh rằng semantic retrieval và graph có cải thiện trên cùng tập câu hỏi so với baseline. Không bịa nâng cao phần trăm hay tuyên bố "SOTA".

## 14. USER EXPERIENCE VÀ EXPLAINABILITY DEMO

Giữ nguyên style/UX LUMIÈRE nếu có thể. Bổ sung Admin-only AI diagnostics (hoặc debug page không public) hiển thị:
- Input query và normalized entities; intent; canonical nodes/aliases được map.
- Dense/lexical/graph candidates, top scores, giải thích graph paths thật.
- Sau fusion/rerank, danh sách Top 3 có thứ tự, ID, score thực và hard filters.
- Thời gian từng bước và nguồn dữ liệu.
- Không lộ dữ liệu bí mật hay trao thông tin Staff/Admin cho khách.

Ba demo bắt buộc:
1. "Nhẫn cho phái nữ", "nhẫn cho con gái", "nhẫn cho phụ nữ" → semantic entity linking đúng theo ngữ cảnh, thể hiện canonical `Audience`.
2. "Tìm sản phẩm cùng loại đá và phong cách với nhẫn X" → Neo4j path + sản phẩm có thật + lý do recommend.
3. "Top 3 nhẫn thanh lịch dưới 8 triệu" → lọc điều kiện, điểm xếp hạng có thật, đúng tối đa 3, so sánh baseline vs nâng cấp.

## 15. MỞ RỘNG KIẾN TRÚC VÀ BẢO TRÌ

Đề xuất module boundaries dựa trên code thật (KHÔNG nhân đôi modules có sẵn):

```
AI/
  api.py
  app/ or existing modules/
    intent_router.py
    semantic_understanding.py
    entity_linking.py
    dense_retriever.py
    lexical_retriever.py
    graph_retriever.py
    fusion_reranker.py
    recommendation_service.py
    grounded_answer_service.py
    sync_service.py
  scripts/
    ingest_csv.py
    import_graph.py
    index_qdrant.py
    verify_import.py
    evaluate_retrieval.py
  config/
    knowledge_graph_schema.yaml
    aliases_vi.yaml
  tests/
    test_entity_linking.py
    test_csv_to_graph.py
    test_topk_ranking.py
    test_recommendations.py
    test_ai_role_guards.py

frontend/Dockerfile
backend/Dockerfile
AI/Dockerfile
compose.yaml
compose.prod.yaml
infra/
  prometheus/
  grafana/
  proxy/
.github/workflows/
docs/
  00-audit-as-is.md
  01-architecture-target.md
  02-knowledge-graph-schema.md
  03-csv-ingestion.md
  04-hybrid-retrieval.md
  05-experiments.md
  06-deployment-and-recovery.md
  07-defence-qna.md
```

Đây là cấu trúc THAM KHẢO, hãy thích ứng cấu trúc thực tế. Thực hiện migration theo strangler/adapter pattern, từng module có unit test và integration test. Không rewrite frontend thành React/Next.js chỉ vì công nghệ mới; giữ các module business đã chạy nếu đáp ứng yêu cầu.

## 16. DOCS ĐỂ BẢO VỆ DATN

Tạo tài liệu tiếng Việt, sơ đồ Mermaid/PlantUML từ hệ thống thực:
- Problem Statement, mục tiêu cải tiến, yêu cầu giảng viên đối chiếu nguồn.
- AS-IS và TO-BE System Architecture.
- UML use cases Customer/Staff/Admin, sequence diagrams AI query + CSV ingest + sync.
- ERD PostgreSQL, Knowledge Graph schema/instances, data lineage.
- Thuật toán entity linking, dense search/cosine, hybrid fusion (RRF), reranking, graph paths, Top K.
- Vì sao dùng PostgreSQL/Qdrant/Neo4j và chi phí đồng bộ.
- Docker topology, fault isolation matrix, deployment, monitoring, CI/CD.
- Benchmark methodology, results, charts, failure cases/limitations.
- Q&A: RAG vs database; RAG vs Semantic Search; Qdrant; Neo4j node vs relation; CSV → graph bằng code; synonyms; vector dimensions vs cosine; Top K; isolation vs dependency; backup; host/GPU; role security.
- Scripts tạo bằng chứng reproducible và hướng dẫn thuyết trình demo 10–15 phút.

## 17. PHASE EXECUTION PLAN (KHÔNG BỎ PHASE)

**PHASE 0 — Audit/read-only:** baseline, inventory, file paths, gaps. Không sửa code.

**PHASE 1 — Safe foundation:** worktree/branch, backup, regression test, config/secrets hygiene, docs; kiểm chứng lại chức năng cũ.

**PHASE 2 — Knowledge Graph schema + CSV-to-graph code:** ưu tiên cao nhất, graph constraints, ingest, verify, idempotency, provenance, structured LLM extraction chỉ khi cần.

**PHASE 3 — Vietnamese semantic entity linking:** aliases/context/ambiguity/tests; xác thực ví dụ phái nữ ↔ con gái.

**PHASE 4 — Semantic retrieval + hybrid retrieval + graph retrieval:** Qdrant embedding, candidate pool, filters, graph traversal, fusion.

**PHASE 5 — Top-K reranking + recommendations + grounded RAG:** sản phẩm có thật, trả đúng K, explanations; giữ tương thích UI/AI API.

**PHASE 6 — Robust synchronization & role separation:** outbox/reconciliation, Customer/Staff/Admin access control, integrations.

**PHASE 7 — Docker isolated services + failure tests:** images độc lập, networks, healthchecks, graceful degradation, data volumes, backup.

**PHASE 8 — Hosting/staging + monitoring + CI/CD:** chỉ deploy công khai sau khi user xác nhận ngân sách, địa chỉ, bảo mật và cấp quyền cần thiết.

**PHASE 9 — Evaluation/ablation + DATN report:** benchmark khoa học, biểu đồ từ kết quả thật, slide-ready diagrams, defence Q&A.

Mỗi phase theo định dạng:
- `CURRENT`: đã kiểm tra file/hàm nào, trạng thái nào.
- `CHANGE`: path chính xác của file tạo/sửa, quyết định kiến trúc và lý do.
- `TEST`: lệnh thực tế, test outputs, ảnh/log/metric có thật.
- `COMPATIBILITY`: kết quả smoke tests business/customer/AI/Staff/Admin.
- `RISK`: lỗi/điểm chặn còn tồn tại.
- `ROLLBACK`: cách trở về bản checkpoint mà không mất data.
- `DOCS`: sơ đồ, báo cáo, scripts đã cập nhật.
- `NEXT`: phase tiếp theo và prerequisites.

Không để một phase ở trạng thái 'done' khi tests không chạy được; đánh dấu `blocked` hoặc `partially implemented` với lý do trung thực. Dùng best effort tiếp tục các task độc lập mà không làm hại dữ liệu. Không cần liên tục xin xác nhận cho edits an toàn đã được mô tả; chỉ dừng để xin phép trước thao tác phá hủy, ghi production, chi phí hoặc thay đổi bảo mật nhạy cảm.

## 18. ACCEPTANCE CRITERIA (ĐIỀU KIỆN HOÀN THÀNH TOÀN DỰ ÁN)

[ ] Website business hiện có và Customer/Staff/Admin workflows không bị regression.
[ ] Có sơ đồ AS-IS/TO-BE và bảng GAP với bằng chứng file paths.
[ ] CSV → Neo4j hoàn toàn tự động bằng Python code; có README/lệnh chạy, dry-run, validate, upsert, idempotency; không manual graph creation.
[ ] Knowledge Graph có node/cạnh có nguồn, constraints, aliases và semantic entity linking đúng ngữ cảnh.
[ ] User có thể hỏi bằng paraphrase tiếng Việt, không cần gõ đúng node name.
[ ] Qdrant dense semantic search hoạt động và dùng similarity metric được giải thích chính xác.
[ ] Hybrid Retrieval có dense + lexical/sparse và graph integration; không cộng điểm sai thang đo.
[ ] Query Top 3 trả tối đa 3 sản phẩm thật phù hợp constraints, xếp hạng theo final score có kiểm chứng.
[ ] Graph-based recommend có actual Neo4j relationship paths và lý do đề xuất.
[ ] LLM answer grounded, không bịa sản phẩm, giá/tồn kho live được xác minh.
[ ] AI roles Customer/Staff/Admin được kiểm tra quyền ở backend với tests.
[ ] PostgreSQL/Qdrant/Neo4j sync có retry/idempotency và reconciliation.
[ ] Frontend/Backend/AI có images/containers độc lập; data services riêng; health checks, volumes, logs.
[ ] Có fault-injection results chứng minh AI container chết không làm sập nghiệp vụ website và các dependency failures có fallback hợp lý.
[ ] Có HTTPS staging/prod runbook, backup/restore và tài liệu chi phí/tài nguyên; production deployment nếu được duyệt.
[ ] Có Prometheus/Grafana metrics thật, dashboard reproducible.
[ ] Có GitHub Actions tests/build/deploy staging theo từng khối, rollback.
[ ] Có đánh giá so sánh baseline, dense, hybrid, graph, reranking, gồm chất lượng và latency, số liệu thực có thể tái lập.
[ ] Có báo cáo, sơ đồ, demo script và tài liệu trả lời phản biện.

## 19. CHỈ DẪN CHO LƯỢT CHẠY ĐẦU TIÊN — BẮT ĐẦU NGAY

Bạn đang ở workspace VS Code trên máy người dùng. **LÀM NGAY PHASE 0 READ-ONLY**, không chỉ phản hồi bằng lý thuyết. Hãy:

1. Xác định root workspace và Git trạng thái; liệt kê cấu trúc/thành phần hiện có, kiểm tra code và tests.
2. Tìm các điểm thực thi thật cho CSV import, Neo4j ingestion, Qdrant indexing, AI query, Product Retrieval, Top-K, Staff/Admin role guards và Docker.
3. Trả bảng GAP theo ưu tiên P0/P1/P2, dẫn file path và line/function có thật.
4. Vẽ Mermaid AS-IS và TO-BE.
5. Đề xuất danh sách thay đổi ít xâm lấn nhất để thực hiện các phase còn lại.
6. Nêu baseline regression commands và cách thiết lập staging/test data/backup.
7. Sau audit, tiếp tục chuẩn bị checkpoint và **triển khai từng phase bằng code thật** theo kế hoạch khi môi trường an toàn; không xóa code cũ và không cần chạy bất kỳ lệnh nguy hiểm nào nếu chưa được phép.

Nhắc lại: **CSV ĐỔ VÀO NEO4J PHẢI BẰNG FILE CODE TỰ ĐỘNG. NGỮ NGHĨA + GRAPH + TOP-K LÀ ƯU TIÊN SỐ 1. DOCKER FRONTEND/BACKEND/AI VÀ TỪNG DATABASE PHẢI TÁCH RIÊNG, CÓ KHẢ NĂNG GIỚI HẠN PHẠM VI LỖI. MỌI KẾT QUẢ PHẢI KIỂM THỬ ĐƯỢC.**
