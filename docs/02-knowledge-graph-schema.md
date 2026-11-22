# Knowledge Graph — hợp đồng projection hiện hữu và đích mở rộng

Trạng thái: **schema đã được kiểm chứng trên Neo4j Community 5.26.33 test độc lập**, chưa xác minh/thay đổi schema database website hiện tại. Chỉ Product và năm nhóm taxonomy được CSV/lookup chứng minh. Neo4j là projection; PostgreSQL là nguồn nghiệp vụ về giá/tồn kho/giao dịch.

| Node | Khóa ổn định | Nguồn | Thuộc tính hiển thị |
|---|---|---|---|
| Product | product_id | CSV ProductID / PostgreSQL products.id | name, sku, barcode, weight; giá/stock chỉ là snapshot |
| Category | category_id | CategoryID / categories.id | name từ categories.json |
| Brand | brand_id | BrandID / brands.id | name từ brands.json |
| Material | material_id | MaterialID / materials.id | name từ materials.json |
| Gemstone | gemstone_id | GemstoneID / gemstones.id | name từ gemstones.json |
| Collection | collection_id | CollectionID / collections.id | name từ collections.json |

ID là số nguyên nguồn, không hash tên hay tự cấp ProductID mới. Sáu uniqueness constraints trong `schema.cypher` đã được tạo và kiểm tra bằng `SHOW CONSTRAINTS` trên instance test; chưa áp dụng vào graph hiện tại của người dùng.

| Quan hệ có hướng | Từ → đến | Ý nghĩa và bằng chứng |
|---|---|---|
| BELONGS_TO | Product → Category | Product.CategoryID khớp Category.id |
| HAS_BRAND | Product → Brand | Product.BrandID khớp Brand.id |
| MADE_OF | Product → Material | Product.MaterialID khớp Material.id |
| HAS_GEMSTONE | Product → Gemstone | Product.GemstoneID khớp Gemstone.id |
| IN_COLLECTION | Product → Collection | Product.CollectionID khớp Collection.id |

Giữ tên `HAS_BRAND` và `IN_COLLECTION` để tương thích `graph_queries.py`, `retrieval.py` hiện hữu. Nếu đổi tên cạnh phải có adapter và migration riêng, không tạo hai cách biểu diễn khiến traversal đếm hai lần.

Audience/Style/Occasion/Color/DesignFeature là **đích thiết kế**, chưa được gán fact cho catalog thật. `Collection Minimal` không đương nhiên đồng nghĩa `Style minimalist`; `ProductName` có “Phái nữ” không tự chứng minh canonical Audience. Fixture Unicode dùng dữ liệu giả không được coi như business catalog. Customer/Order/PLACED/CONTAINS có trong legacy importer nhưng không nằm trong preflight product-only mới; cần audit ownership và provenance trước khi dùng để personalization.

Writer đã lưu `source_file`, `source_row`, `source_sha256`, `projection_owner=lumiere-products-v1`, `extraction_method=structured`, `indexed_at` trên Product; cạnh có owner/row/checksum/method. Metadata này đã được ghi trên graph test, không phải xác nhận graph production. Candidate edges từ LLM vẫn phải qua review riêng; hiện pipeline dùng dữ liệu cấu trúc, không gọi LLM sinh Cypher.

Cypher truy vấn chỉ đọc để minh họa hợp đồng hiện có:

```cypher
MATCH path = (p:Product {product_id: $product_id})-[:MADE_OF]->(m:Material)
RETURN p.product_id AS product_id, m.material_id AS material_id, m.name AS material, path;
```

```cypher
MATCH path = (source:Product {product_id: $product_id})-[:HAS_GEMSTONE]->(g:Gemstone)
             <-[:HAS_GEMSTONE]-(candidate:Product)
WHERE candidate.product_id <> source.product_id
RETURN candidate.product_id AS product_id, g.gemstone_id AS shared_gemstone_id, path
ORDER BY product_id
LIMIT $limit;
```

Những query trên chưa chạy trong đợt này. Query thứ hai minh họa shared attribute path, chưa là xếp hạng semantic hoặc xác nhận tồn kho. Kết quả cuối phải đối soát Business API trước khi hiển thị như sản phẩm có thể mua.

Verification cần thực hiện trong Neo4j dev: uniqueness ID, đúng endpoint/type whitelist, đúng một cạnh cho mỗi FK single-value hiện tại, không orphan, đối soát product IDs/FKs với PostgreSQL export được phép, drift names và managed edge replacement khi thay taxonomy. Chạy import hai lần phải giữ count/ID; đổi tên chỉ cập nhật display field; đổi FK phải không giữ fact cũ. Các acceptance checks này **chưa đạt** chỉ bằng dry-run CSV.
