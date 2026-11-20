# Schema Knowledge Graph đã triển khai

Nguồn cấu hình: `AI/config/knowledge_graph_schema.json` version `2026-11-19.1`.
Chi tiết nền tảng: [schema và ingestion contract](04-knowledge-graph-schema.md).

| Label | ID ổn định | Nguồn | Cạnh từ Product |
| --- | --- | --- | --- |
| Product | `product_id` integer, đúng PostgreSQL/CSV | ProductID | — |
| Category | `category_id` integer | CategoryID/Name | BELONGS_TO |
| Brand | `brand_id` integer | BrandID/Name | HAS_BRAND |
| Material | `material_id` integer | MaterialID/Name | MADE_OF |
| Gemstone | `gemstone_id` integer | GemstoneID/Name | HAS_GEMSTONE |
| Collection | `collection_id` integer | CollectionID/Name | IN_COLLECTION |
| Audience | `canonical_id` string | AudienceID/Name/Evidence đã xác minh | SUITABLE_FOR |
| Style | `canonical_id` string | StyleID/Name/Evidence đã xác minh | HAS_STYLE |
| Occasion | `canonical_id` string | OccasionID/Name/Evidence đã xác minh | FOR_OCCASION |

Mỗi key có uniqueness constraint `IF NOT EXISTS`. ID/tên taxonomy được đối soát
toàn snapshot; không MERGE theo tên. Giữ `HAS_BRAND`/`IN_COLLECTION` đang có để
tương thích pipeline cũ, tương ứng ngữ nghĩa PRODUCED_BY/PART_OF_COLLECTION của đặc tả.
Không tạo hai bộ cạnh trùng ý nghĩa hoặc tự đổi stable IDs sang chuỗi.

Product lưu SKU, tên, giá số và `price_exact`, tồn kho, published, source filename,
source row và SHA256. Giá/tồn kho authoritative thuộc PostgreSQL; graph là projection.
Cạnh optional lưu evidence, source_field, source_record_id và extraction_method.
Aliases nằm trong `AI/config/aliases_vi.json`, có version, không tự gộp node theo cosine.

500 sản phẩm gốc hiện không có Audience/Style/Occasion. Những cạnh này chỉ có trên
8 fixture riêng hoặc CSV chứa fact đã được duyệt. Collection Minimal/Wedding/Office
không được tự đổi thành Style/Occasion. Candidate `PENDING_REVIEW` chỉ nằm trong
CSV review; không được import thành fact. Chưa triển khai LLM candidate extractor.

Ví dụ Cypher chỉ đọc:

```cypher
MATCH (p:Product {product_id:900101})-[r]->(e)
RETURN p.product_id, type(r), labels(e), properties(e), r.evidence;

MATCH (a:Product {product_id:900101})-[:HAS_GEMSTONE]->(g)<-[:HAS_GEMSTONE]-(b:Product)
MATCH (a)-[:HAS_STYLE]->(s)<-[:HAS_STYLE]-(b)
RETURN a.product_id, b.product_id, g.name, s.name;
```

Live test trả hai candidate 900102 và 900107 qua Diamond + Thanh lịch; dữ liệu này
được đánh dấu **synthetic fixture**, không phải thuộc tính của catalog gốc.
`Neo4jProductWriter.verify()` đối soát từng product/5 taxonomy edges, optional
evidence, node counts, relationship counts và orphan IDs; uniqueness constraints
chặn duplicate IDs. Resume cũng kiểm tra lại facts, không tin report cũ một cách mù quáng.

Runtime chỉ công bố path nếu ID/tên/loại quan hệ vẫn khớp catalog hiện hành cho cả
seed và candidate. Nếu seed đổi thuộc tính giữa retrieval và revalidation, trả kết quả
rỗng có trạng thái `seed_changed_during_search`. Báo cáo thực thi ở
[ai-live-acceptance.json](evidence/ai-live-acceptance.json).
