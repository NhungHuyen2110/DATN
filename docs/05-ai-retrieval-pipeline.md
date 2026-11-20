# Retrieval pipeline đang triển khai

```mermaid
sequenceDiagram
  actor User
  participant API as AI /chat
  participant Catalog as Authoritative catalog
  participant Understand as Query understanding
  participant Dense as SentenceTransformer + Qdrant
  participant Lexical as LexicalRetriever
  participant Graph as Neo4jGraphRetriever
  participant Fusion as RRF + verification
  participant Answer as GroundedAnswerService
  User->>API: query, top_k
  API->>Catalog: Read one public snapshot
  API->>Understand: Normalize; aliases; price bounds
  Understand-->>API: QueryContext
  API->>Lexical: Retrieve within hard filters
  API->>Dense: Real encode + filtered vector query
  API->>Graph: Shared-taxonomy 2-hop paths
  Note over Dense,Graph: Source failure is reported as degraded
  API->>Fusion: Candidate lists + canonical facts
  Fusion->>Fusion: Deduplicate; RRF; verify stock/price/entities
  Fusion->>Fusion: Deterministic order + eligible backfill
  Fusion-->>Answer: Up to requested K verified products
  Answer-->>User: Names, IDs and prices from catalog
```

## Hiểu truy vấn và hard filters

Normalizer hỗ trợ Unicode/không dấu/case, alias loại trang sức và đá; ví dụ hoa tai ↔
bông tai, kim cương ↔ Diamond, bạch kim ↔ Platinum. Material cụ thể như vàng trắng
18K ưu tiên hơn alias vàng chung. Giá dùng Decimal, hỗ trợ ngân sách, tầm giá, dưới/trên
và khoảng giá có đơn vị chung (`từ 3 đến 5 triệu`). Giới hạn giá inclusive như luồng cũ.

Linker dùng aliases versioned + semantic cosine resolver cho field context rõ ràng,
threshold/margin và ambiguity handling. Có negation, bác/bạc và ngữ cảnh con gái 8 tuổi;
không tự gộp node theo embedding. AND/OR phức tạp và price expressions ngoài grammar
hiện tại còn thiếu. API nhận `top N` từ câu khi body không truyền top_k; body explicit
ưu tiên và giữ bounds cũ 1..10. Direct SKU/ProductID lookup được phân biệt với seed recommendation.

Eligibility luôn loại hết hàng, giá ngoài khoảng hoặc taxonomy không khớp. Filter
được push down vào Qdrant qua allowed IDs và kiểm tra lại trước response. Catalog PostgreSQL
read-only được khuyến nghị cho staging; CSV có thể stale và chỉ dành offline/demo.

## Fusion, Top-K và fallback

Lexical xếp theo token overlap. Dense dùng model multilingual thật qua adapter; không
sinh vector giả trong runtime. Graph tính số peer chung Category/Material/Gemstone
trong tập hợp lệ; có seeded 2-hop cùng đá/chất liệu/phong cách và path IDs thật.
Chỉ truy vấn khi có entity hoặc seed. Optional facts bắt buộc có nguồn evidence.

RRF = tổng `weight/(60+rank)` theo từng source (dense=2, lexical/graph=1), mỗi ID tính một lần mỗi source. Sắp xếp
candidate theo score rồi ID để tie ổn định. Sau fusion, kiểm tra catalog facts và backfill
đủ K từ hàng hợp lệ khi retrieval có tín hiệu. Nếu ít hơn K hàng hợp lệ, trả ít hơn;
không nới hard filters. Truy vấn không nhận diện và không có tín hiệu không được gán
ngẫu nhiên các sản phẩm đầu catalog.

Candidate pool mặc định 100 hoặc ít nhất 5*K; reranker thêm exact SKU boost, không phải
cross-encoder. Sau retrieval đọc lại source để kiểm giá/stock/published. Graph paths
được đối soát lại cả source/target; seed đổi thuộc tính thì không trả recommendation cũ.

Nếu một source lỗi, ghi tên source vào `degraded_sources` và log không có secret/query;
các sources khác tiếp tục. Lỗi authoritative catalog trả 503, không dùng index thay
thế cho giá/tồn kho. Không được xem lexical-only response là bằng chứng semantic retrieval đã chạy.

## Grounding và giới hạn

Modular answer là template lấy tên/ID/giá từ facts đã verify, không dùng LLM để thêm
facts. Response giữ `success`, `answer`, `products`; thêm score/explanation và degraded sources.
Legacy CrewAI/Ollama vẫn ở nhánh legacy; service Ollama trong Compose là optional.

Đã chạy engineering live với model 384 chiều, Neo4j server, Qdrant local SDK và HTTP;
báo cáo có thời gian smoke query, không phải p95 production hay relevance quality.
136 benchmark candidates đều PENDING_REVIEW, chưa có Recall/nDCG/model quality để công bố. Full catalog
snapshot/backfill phù hợp dataset 500 sản phẩm, chưa tối ưu cho catalog lớn. Không có
cross-store snapshot/version guarantee. Xem tài liệu 06 và requirement matrix trước nghiệm thu.
