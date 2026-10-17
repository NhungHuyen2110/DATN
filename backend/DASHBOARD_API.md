# Admin Dashboard — tiền thanh toán được hệ thống xác nhận

Hai API chỉ đọc, chỉ Admin đang hoạt động. Dùng session cookie hiện có;
Staff/Customer nhận 403, chưa đăng nhập/session hết hạn/tài khoản khóa nhận 401.
Không cần migration. Không thay đổi Orders, COD, VNPay hoặc ProductID.

## Quy tắc số liệu dùng chung

Một đơn được tính đúng một lần khi:

- `payment_status = paid`, trạng thái đơn khác `cancelled`.
- Có đúng một giao dịch `succeeded`, không `review_required`, có `verified_at`.
- Provider trùng phương thức thanh toán; số tiền trùng `Order.total_vnd`.
- Không có dấu hiệu mâu thuẫn ở các giao dịch của đơn.

Tiền bao gồm phí giao hàng sau giảm giá theo `Order.total_vnd`, không phải lợi nhuận
hay doanh thu thuần sau hoàn tiền. Không dùng giá Product hiện tại hoặc cộng OrderItem.
Mọi số tiền dùng Decimal và được trả dưới dạng chuỗi có hai chữ số thập phân.
Đơn refunded bị loại; không suy diễn số tiền/ngày hoàn tiền.
Giao dịch pending/failed bình thường không tính tiền và không tự coi là mâu thuẫn.

## GET /admin/dashboard

Không có bộ lọc thời gian: đếm toàn bộ đơn theo trạng thái hiện tại và tồn kho hiện tại.

```json
{
  "total_orders": 0,
  "orders_by_status": {"pending": 0, "confirmed": 0, "packing": 0, "shipping": 0, "delivered": 0, "cancelled": 0},
  "orders_by_payment_status": {"unpaid": 0, "paid": 0, "refunded": 0},
  "confirmed_payment_amount_vnd": "0.00",
  "reconciliation_order_count": 0,
  "reconciliation_order_value_vnd": "0.00",
  "reconciliation_reasons": [],
  "total_products": 0,
  "out_of_stock_products": 0
}
```

`reconciliation_order_value_vnd` là tổng **giá trị đơn cần đối soát**, mỗi đơn một lần.
Không phải số tiền chắc chắn đã thu, thất thoát hay phải hoàn; schema chưa đủ xác định
các đại lượng đó. Mỗi phần tử `reconciliation_reasons` có `reason`, `order_count`.
Một đơn có thể có nhiều lý do, nên không cộng các số đếm lý do để tính tổng số đơn.

Các mã lý do:

| Mã | Ý nghĩa |
| --- | --- |
| `transaction_requires_review` | Giao dịch bị đánh dấu cần đối soát |
| `transaction_amount_mismatch` | Số tiền giao dịch không khớp tổng đơn |
| `transaction_provider_mismatch` | Provider không khớp phương thức thanh toán |
| `successful_transaction_missing_verified_at` | Giao dịch thành công thiếu thời điểm xác nhận |
| `multiple_valid_transactions` | Nhiều giao dịch đáp ứng điều kiện cho cùng đơn |
| `multiple_successful_transactions` | Nhiều giao dịch thành công cho cùng đơn |
| `paid_order_without_single_valid_transaction` | Đơn paid không có đúng một bằng chứng hợp lệ |
| `unpaid_order_with_successful_transaction` | Đơn unpaid nhưng có giao dịch thành công |
| `cancelled_order_with_successful_transaction` | Đơn hủy nhưng có giao dịch thành công |

Schema hiện tại có UNIQUE(order_id, provider), vốn ngăn nhiều giao dịch cùng provider
cho một đơn; nhánh nhiều giao dịch hợp lệ vẫn được bảo vệ và có unit test phòng dữ liệu cũ.

## GET /admin/reports/revenue

Ví dụ: `/admin/reports/revenue?start_date=2026-10-01&end_date=2026-10-31&group_by=day`

- Hai ngày bắt buộc dạng YYYY-MM-DD; `group_by` là `day` (mặc định) hoặc `month`.
- Bao gồm toàn bộ ngày kết thúc, theo `Asia/Ho_Chi_Minh`.
- Ranh giới ngày được đổi sang UTC trước khi lọc `verified_at` trong truy vấn.
- Tối đa 3661 ngày trong một yêu cầu; dữ liệu ngày/khoảng sai trả 422.
- Ngày/tháng không có thanh toán trả 0. Nhóm tháng dùng ngày đầu tháng làm nhãn;
  tháng đầu/cuối chỉ tính các ngày nằm trong khoảng yêu cầu.

```json
{
  "start_date": "2026-10-01",
  "end_date": "2026-10-01",
  "group_by": "day",
  "timezone": "Asia/Ho_Chi_Minh",
  "time_basis": "payment_transaction.verified_at",
  "confirmed_payment_amount_vnd": "0.00",
  "confirmed_payment_order_count": 0,
  "items": [{"period_start": "2026-10-01", "confirmed_payment_amount_vnd": "0.00", "confirmed_payment_order_count": 0}]
}
```

`verified_at` là lúc Backend xác nhận, chưa phải ngày ngân hàng thực thu.
Số liệu phản ánh trạng thái hợp lệ hiện tại: một giao dịch bị gắn cờ sau này có thể làm
số liệu kỳ cũ thay đổi. Chưa có sổ hoàn tiền để báo cáo dòng tiền hoàn trả theo kỳ.

## Swagger và kiểm thử

Backend local dùng cổng 8001. Từ D:\DATN\backend chạy:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Mở http://localhost:8001/docs, đăng nhập Admin bằng `/auth/login`
trong cùng trình duyệt rồi gọi hai API trên. Đổi tài khoản Staff/Customer để kiểm tra 403.
Không cần tạo đơn hoặc xác nhận thanh toán trên PostgreSQL chính để thử API đọc.

Từ D:\DATN chạy test riêng (có chặn mọi kết nối ngoài SQLite in-memory):

```powershell
.\.venv\Scripts\python.exe backend/tests/test_dashboard_api.py
```

Chạy toàn bộ regression với cùng cơ chế chặn PostgreSQL và không đọc .env:

```powershell
@'
import sys, unittest
from unittest.mock import patch
import sqlalchemy as sa
sys.path.insert(0, 'backend/tests')
original = sa.engine.Engine.connect
def memory_only(engine, *args, **kwargs):
    if engine.dialect.name != 'sqlite' or engine.url.database != ':memory:':
        raise AssertionError('Only SQLite memory allowed')
    return original(engine, *args, **kwargs)
with patch.object(sa.engine.Engine, 'connect', memory_only), patch('dotenv.load_dotenv'):
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.discover('backend/tests'))
sys.exit(not result.wasSuccessful())
'@ | .\.venv\Scripts\python.exe -
```

SQLite không xác minh được đầy đủ hành vi timezone/độ chính xác Numeric của PostgreSQL.
Tests kiểm tra biên giờ Việt Nam, Decimal serialization và biên dịch SQL PostgreSQL offline;
không kết nối PostgreSQL thật.
