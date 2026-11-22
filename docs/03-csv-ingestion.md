# CSV → Knowledge Graph — pipeline đang triển khai

Trạng thái: **CSV → graph phần lõi đã chạy và đối soát trên instance test độc lập**. Neo4j Community 5.26.33: CLI import đủ 500 bản ghi, 2.500 cạnh hai lần; cả hai lần verification pass, không duplicate ProductID/endpoint sai. Không ghi database hiện tại của người dùng. Báo cáo `csv-preflight-baseline.json` vẫn là dry-run lịch sử.

## CURRENT

CSV thật `output/products_ai.csv`: 19 cột gồm ProductID/SKU/Barcode/ProductName, CategoryID/BrandID/MaterialID/GemstoneID/CollectionID, Weight/SalePrice/WholesalePrice/CostPrice/Stock và 5 tên lookup. Taxonomy nguồn ở `data/{categories,brands,materials,gemstones,collections}.json`.

Source graph hiện dùng `HAS_BRAND`, `IN_COLLECTION`; giữ nguyên hợp đồng này để không phá các retriever. Không tự đổi sang `PRODUCED_BY` hoặc `PART_OF_COLLECTION`. Product và 5 loại lookup định danh bằng ID số nguyên nguồn. Không MERGE theo display name.

## CHANGE

- `AI/knowledge_graph/csv_validation.py`: parser stdlib, UTF-8-SIG/BOM, CSV quoting/separator, NFC tên, kiểm tra cột, ProductID/SKU/barcode trùng, FK/name drift với lookup JSON, giá hữu hạn/không âm/không quá hai chữ số thập phân, Weight>0, Stock nguyên không âm và bounds PostgreSQL. Giữ SKU/barcode có số 0 đầu và giá dạng chuỗi Decimal chính xác.
- `AI/knowledge_graph/import_data.py`: mặc định dry-run; chỉ import driver khi `--apply` hợp lệ. Không đọc `.env`, không import Customer/Order. Importer cũ được lưu trong checkpoint; đây là refactor pipeline, không thay API nghiệp vụ.
- `AI/knowledge_graph/graph_writer.py`: constraints, batch UNWIND/MERGE, retry có giới hạn, metadata nguồn/dòng/checksum và số record đã commit. Từ chối Product không thuộc pipeline hoặc graph chứa dữ liệu ngoài catalog. Chỉ thay taxonomy edge có ownership của pipeline; không xóa graph/Product/Customer/Order. Đối soát ID/cạnh/trùng/endpoint sau import.
- `AI/knowledge_graph/schema.cypher`: sáu uniqueness constraints `IF NOT EXISTS`, tương thích ID và label hiện có; chưa thực thi, chưa xác minh version Neo4j server. Constraints không tự giải quyết duplicate đang có.
- `AI/tests/test_csv_validation.py`: fixture sinh trong thư mục tạm, không dùng PII hoặc sản phẩm giả như dữ liệu thật. Tên fixture có “Phái nữ” để kiểm tra Unicode; **không suy luận cạnh Audience** từ tên.

CLI:

```powershell
$env:TEMP='D:\LUMIERE-FINAL-TEST\.local-tmp'
$env:TMP=$env:TEMP
python -B AI/knowledge_graph/import_data.py --file output/products_ai.csv --dry-run
python -B AI/knowledge_graph/import_data.py --file output/products_ai.csv --dry-run --limit 10
python -B AI/knowledge_graph/import_data.py --file output/products_ai.csv --dry-run --report docs/csv-preflight-new.json
python -B -m unittest discover -s AI/tests -p test_csv_validation.py -v
```

`--limit` báo `prefix_only`, không chứng nhận toàn file. Report có sẵn không bị ghi đè. Exit 0: validation/verification đạt; 1: validation/verification lỗi; 2: lỗi nguồn/cấu hình/driver. `--apply` bắt buộc environment dev/test, confirm-isolated, backup-reference là file có thật, URI loopback rõ ràng và mật khẩu riêng `LUMIERE_GRAPH_PASSWORD`. Lỗi CSV chặn toàn bộ import trước khi tạo driver. Không đọc credential từ `.env` hiện tại.

Các batch đã commit không tự bị xóa nếu batch sau lỗi; report ghi committed_records/completed/partial_write_possible. Rerun toàn file qua MERGE là phương án phục hồi dự kiến, chưa có resume theo offset. Không coi import nhiều batch là một transaction duy nhất.

## TEST

Ngày 18/11/2026: 10 unittest pass, gồm kiểm chứng importer chặn việc import dotenv/Neo4j/pandas trong dry-run. Dry-run toàn bộ CSV: 500/500 record hợp lệ, không lỗi; 500 Product, 6 Category, 4 Brand, 5 Material, 6 Gemstone, 5 Collection; 500 cạnh cho mỗi loại trong năm loại quan hệ. Report: `docs/csv-preflight-baseline.json`, source SHA-256 ghi trong report. Tổng 2.500 cạnh **dự kiến**; không phải count database.

Kết quả thực thi sau đó:

- `neo4j-integration-results.json`: graph trống riêng, 3 fixture; import lặp không trùng, đổi FK thay đúng cạnh, lỗi sau Product SET rollback toàn batch, recommendation có paths thực.
- `neo4j-catalog-import-first.json` và `neo4j-catalog-import-second.json`: **500 Product và 500 cạnh mỗi loại**, violations=0, duplicate_products=0, committed_records=500, completed=true cho cả hai lần.
- `neo4j-final-counts.json`: sáu uniqueness constraints đã tồn tại. Toàn instance có **503 Product và 2.515 cạnh** vì giữ thêm 3 fixture và 15 cạnh của bài test trước; 26 node taxonomy. Không nhầm tổng này thành 503 bản ghi catalog.
- `neo4j-recommendation-evidence.json`: Top 3 graph cho ProductID=1 trả IDs 469,479,486, cùng Category/Material/Gemstone trong CSV projection; đây là evidence graph test, chưa phải xác minh live Business API.

Server/binaries/data/log mới đều ở `.local-tmp/neo4j-community-test/` trên D, Bolt localhost:17687. Không dùng data/conf/credential instance cũ. Bản Community được lấy từ [nguồn chính thức](https://neo4j.com/deployment-center/), đối chiếu SHA-256 `380a4cfd26ea23ece35922ed1ab27c33503eebda634e4e58cdd6f908bd0166ff` trước giải nén. Java tương thích đối chiếu [system requirements](https://neo4j.com/docs/operations-manual/current/installation/requirements/). Docker không phản hồi nên bài test này chạy server native, **không phải bằng chứng Docker fault isolation**.

Validation lặp hai lần không đổi source. Idempotency Neo4j được kiểm chứng riêng bằng hai lần CLI thực thi nêu trên, không suy ra từ parser.

## COMPATIBILITY / RISK

Backend/frontend nghiệp vụ không sửa. Importer mới chỉ product catalog và không có side effect kết nối khi import module; legacy source nằm trong checkpoint. Customer AI đã có thay đổi riêng được ghi trong `04-hybrid-retrieval.md`.

Report không chứa records/name/price đầy đủ, chỉ count/checksum/error row và field. Không kết nối PostgreSQL hoặc ghi ngược giá CSV vào business DB. Chưa có nguồn Audience, Style, Occasion; không tự phát sinh fact cho các nhóm này.

## ROLLBACK

Checkpoint source ở `.local-tmp/checkpoints/csv-preflight-20261118/`, có `manifest.json` và đã đối chiếu SHA-256 từng bản sao của 7 file. Không có `.env` hoặc DB backup trong checkpoint. Đây là bản sao source liên quan, không phải snapshot toàn repository.

Chỉ khôi phục `AI/knowledge_graph/import_data.py` và `schema.cypher` từ checkpoint sau khi so sánh diff/checksum và chắc chắn không ghi đè thay đổi mới của người dùng. Giữ nguyên các file business đã dirty trước đó. Không dùng reset/clean hay database rollback. Khôi phục importer cũ đồng nghĩa lấy lại đường CLI cũ có thể ghi dữ liệu, nên vẫn không chạy khi môi trường chưa được xác nhận.

## NEXT

Đã kiểm chứng replay/đổi FK/rollback batch trên server test. Còn review đầy đủ phase audit, resume nếu cần, reconciliation/delete policy, nguồn Audience/Style có bằng chứng và vận hành Docker. Không suy rộng kết quả catalog import thành hoàn tất toàn bộ đồ án.
