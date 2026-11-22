# Rà code bổ sung — 22/11/2026

Đã đọc toàn văn bốn file dưới đây ở trạng thái workspace hiện tại. Đây là review source; không thay thế acceptance với database/container. Chưa đóng gate đọc toàn bộ repository.

| File | Đường chạy đã đối chiếu | Hạn chế cần giữ trong acceptance |
|---|---|---|
| backend/app/routers/ai_staff.py | Depends(staff_or_admin); product lookup → multi-intent → inventory → order-time → rule/LLM tùy cờ → order SQL tool | Chỉ đọc; intent ngoài phạm vi trả unsupported. STAFF_AI_LLM_ENABLED mặc định false. Cần role/intent acceptance đầy đủ trên deployment |
| backend/app/routers/ai_admin.py | Depends(admin); diagnostics relay, sync-status, top-selling endpoint và chat product/multi/inventory/revenue/top-selling | Không cho LLM tự chạy SQL. Kiểm ngày/limit trước top-selling. ADMIN_AI_LLM_ENABLED mặc định false. Chưa chứng nhận toàn analytics bằng container tests |
| backend/app/services/ai_staff_orchestrator.py | analyze_multi_intent(staff), thống kê order + inventory, tách out-of-stock với low-stock; ghi rõ tổng/list bị giới hạn | Multi-intent kèm thời gian chủ động từ chối; không được quảng cáo hỗ trợ đầy đủ bộ lọc thời gian |
| backend/app/services/ai_admin_orchestrator.py | resolve_period, từ chối nhiều mốc/thời gian ngoài hỗ trợ; revenue + top-selling cùng kỳ; order statistics toàn lịch sử; inventory hiện tại | Có thể trả unsupported cho kết hợp order/time; SQL tools cần kiểm độc lập totals/refund/date semantics. Không chuyển doanh thu sang vector/graph ranking |

Không sửa bốn file trong lượt review này. Giữ nguyên luồng Customer/Staff/Admin hiện có. Source SQL tools/intent/LLM và các file khác cần được theo dõi riêng; đọc bốn file không chứng minh audit toàn bộ hoàn tất. Baseline và kiến trúc nằm tại [00-audit-as-is.md](00-audit-as-is.md), trạng thái nghiệm thu tại [12-acceptance-status.md](12-acceptance-status.md).
