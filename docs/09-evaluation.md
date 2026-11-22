# PHASE 9 — Đánh giá có kiểm chứng

CURRENT: `evaluation/queries.draft.jsonl` có 105 câu hỏi **chưa gán nhãn**, gắn SHA256 của catalog CSV thật. Đây là đầu vào cho người đánh giá, không phải benchmark đã nghiệm thu. Không gán người review giả, không tự coi nhãn của model là ground truth.

CHANGE: `evaluation/scoring.py` tính Precision@K (mẫu số luôn là K kể cả trả thiếu), Recall@K, MRR trên thứ tự trả về và nDCG@K dùng gain `2^grade-1` với grade 0..3. Latency p50/p95 dùng nearest-rank từ thời gian đo từng query. `scripts/evaluate_retrieval.py` từ chối nhãn chưa review, trùng query, thiếu dự đoán, khác dataset và latency không hợp lệ. Câu không có sản phẩm phù hợp cần bộ kiểm thử hành vi riêng; scorer ranking hiện chỉ chấp nhận nhãn có ít nhất một positive.

Người review điền `reviewed=true`, `reviewer`, `split=validation|test`, expected intent/entities/constraints/evidence và `relevance` dạng `{"79":3,"87":2}` sau khi kiểm tra catalog. Phải tách validation/test trước khi chỉnh trọng số. Các câu safety/ambiguous/unsupported dùng để kiểm tra hành vi, không ép vào metric ranking positive-only.

Prediction JSONL cần `query_id`, `dataset_sha256`, `product_ids` có thứ tự và `latency_seconds` đo thật. Cùng query set/dataset/environment cho keyword, dense-only, dense+lexical, dense+graph, full hybrid/reranker. Không loại query thất bại khỏi prediction để tăng điểm.

Đã có `scripts/run_retrieval_ablation.py`: 5 modes lexical, dense, dense_lexical, dense_graph, full_graph_reranked. Lượt smoke thực tế 105 câu/mode, tổng 525 predictions tại `ablation-smoke-20261121/`, dùng model cached trên D, Qdrant memory và Neo4j test read-only. GraphFeatureReranker là heuristic untuned opt-in, không phải cross-encoder, không là probability. Lexical baseline hiện là matcher Python, chưa phải SQL ILIKE/full-text baseline. Lượt này chạy trước reference-query enhancement; phải chạy lại khi tạo benchmark cuối.

Biểu đồ `figures/ablation-smoke-latency.png/.svg` do `scripts/plot_ablation_smoke.py` tạo từ thời gian thực. Chỉ SMOKE, modes chạy lần lượt và không kiểm soát tải, gồm cả abstentions; không kết luận mode nhanh/chính xác hơn. 0 nhãn human review, không tính Precision/MRR/nDCG hay tự tạo truth.

```powershell
python scripts/evaluate_retrieval.py --labels labels.reviewed.jsonl --predictions predictions.jsonl --k 3 --report results.new.json
```

TEST: 3 ca kiểm thử công thức với kết quả tính tay, thứ tự lý tưởng, trả thiếu K và guard nhãn/dataset. Không dùng kết quả fixture để tuyên bố chất lượng tìm kiếm thật. Chưa tạo biểu đồ chất lượng khi chưa có số liệu hợp lệ.

RISK: CSV seed khác dữ liệu Business đang chạy. Audience/Style chưa có fact đã xác minh; không thể nghiệm thu các demo này bằng cách tự gán giới tính/phong cách cho sản phẩm. Cần bổ sung annotation có provenance trước khi đánh giá các thuộc tính đó. Entity accuracy, graph precision/recall, hard-filter violations, groundedness và fault-recovery vẫn cần quy trình đánh giá riêng.

ROLLBACK: module đánh giá độc lập, không gọi database/model hoặc sửa dữ liệu. Giữ report và dataset fingerprint làm bằng chứng; không ghi đè file kết quả cũ.
