# COD và VNPay Sandbox

## Phạm vi

Tận dụng get_current_user, role từ database và Orders hiện có. Không tạo merchant,
không gọi gateway/network, không nhập thông tin xác thực thật, không sửa .env và
không áp dụng migration trong lần cập nhật tài liệu này. PostgreSQL thật đã ở
`20261017_0005` theo xác nhận ngày 17/10/2026, bao gồm migration Payments.
Test tự động chỉ dùng mock merchant và SQLite
trong bộ nhớ; chưa có kết quả end-to-end với hệ thống VNPay.

Tham khảo tài liệu chính thức:

- https://sandbox.vnpayment.vn/apis/docs/thanh-toan-pay/pay.html
- https://sandbox.vnpayment.vn/apis/docs/bang-ma-loi/

Adapter dùng API 2.1.0, HMAC-SHA512, tham số sort theo tên rồi URL encode dạng
form (space thành +). Số tiền gửi VNPay bằng Decimal nhân 100, không float;
giới hạn theo vnp_Amount 12 chữ số của tài liệu. Thời gian theo GMT+7.
Endpoint thanh toán được cố định ở Sandbox, không hỗ trợ production trong code này.

## API

POST /orders nhận thêm payment_method là cod hoặc vnpay (mặc định cod để tương
thích request cũ). payment_status luôn bắt đầu unpaid. Không nhận tổng tiền,
trạng thái paid, role hoặc user_id từ client. Checkout vẫn trừ kho đúng một lần.
VNPay thiếu cấu hình hoặc tiền ngoài giới hạn sẽ dừng checkout trước khi ghi đơn.

### COD

POST /admin/orders/{id}/cod/confirm, body:

Hoặc POST /staff/orders/{id}/cod/confirm dành cho Staff và Admin. API /admin/
vẫn chỉ cho Admin; cả hai route dùng cùng service và quy tắc xác nhận COD.

```json
{"collection_reference": "MA-CHUNG-TU-THU-TIEN-THUC-TE"}
```

Chỉ người có quyền theo route, chỉ đơn COD đã delivered và chưa thu tiền. Lấy đúng total_vnd từ đơn,
ghi payment transaction succeeded cùng confirmed_by và verified_at rồi cập nhật
order.payment_status=paid trong cùng transaction. Mã chứng từ bắt buộc, không
phải client tự chọn số tiền. Gọi lại cùng chứng từ trả transaction cũ; chứng từ
khác cho cùng đơn hoặc chứng từ trùng đơn khác báo 409. Không thay đổi tồn kho.
Đây là xác nhận thu tiền thủ công có audit người xác nhận, chưa tích hợp đối soát
đơn vị giao hàng. Staff/Admin phải thực sự nhận tiền và kiểm tra chứng từ trước
khi gọi API; mã chứng từ do người thao tác nhập không tự chứng minh tiền đã thu.
Không nhận amount/payment_status/confirmed_by từ client. Gọi lại cùng chứng từ
giữ nguyên người và thời điểm xác nhận đầu tiên; không tạo bản ghi thu tiền thứ
hai. Schema hiện có đủ confirmed_by, verified_at và provider_transaction_id,
không cần migration. Đây là lịch sử xác nhận thành công, không phải log mọi
lần gọi API; bước này không bổ sung nhật ký request/audit event riêng.

### VNPay

POST /orders/{id}/payments/vnpay: customer, chỉ đơn của mình, pending/unpaid và
payment_method=vnpay. Không nhận số tiền từ request. Response:

```text
{
  transaction: {id, order_id, provider, reference, amount_vnd, status, review_required, expires_at},
  payment_url: "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html?..."
}
```

Thời hạn URL là 15 phút. Gọi lại trước hết hạn trả cùng tham chiếu và URL; không
tạo transaction mới. Chỉ một attempt mỗi order/provider, kể cả sau khi failed.
Sau failure đã xác thực, admin có thể hủy đơn, khách đặt lại đơn mới. Không đổi
payment_method sau checkout, không tự đổi COD sang VNPay hoặc ngược lại.

GET /payments/vnpay/return: public, kiểm tra chữ ký/merchant/ref/amount/order rồi
trả trạng thái đang lưu tại server. Luôn chỉ đọc; không đánh dấu paid kể cả
redirect có mã 00. Không trả thông tin giao hàng hoặc token người dùng.

GET /payments/vnpay/ipn: public server callback, không cần session vì VNPay gọi
trực tiếp. Xác thực HMAC constant-time trước truy vấn DB, từ chối tham số lặp,
tham số ngoài vnp_, sai định dạng hoặc thiếu thông tin bắt buộc. Khóa order trước
payment transaction; các thao tác tạo URL, COD, hủy và IPN cùng khóa order để
tuần tự hóa. Kiểm tra mã merchant đã lưu, tham chiếu ngẫu nhiên duy nhất, order
info, số tiền đối chiếu cả transaction lẫn order, định dạng mã giao dịch.

Chỉ khi ResponseCode=00 và TransactionStatus=00, TransactionNo>0, PayDate nằm
trong khoảng tạo/hết hạn URL và không trong tương lai bất thường, đơn chưa hủy/
hoàn kho và payment_status=unpaid mới ghi succeeded/paid. Callback đến trễ vẫn
được chấp nhận nếu PayDate hợp lệ; không so thời điểm IPN đến với expires_at.
Provider transaction ID unique chống gán cùng mã giao dịch cho hai đơn.

IPN trả JSON RspCode/Message theo quy ước VNPay: 00 đã ghi nhận, 02 đã xử lý,
01 không khớp đơn, 04 sai tiền, 97 chữ ký/tham số không hợp lệ, 99 lỗi xử lý/cấu
hình để VNPay retry. Ghi digest nội dung callback đã xác thực, mã phản hồi,
provider status, provider transaction ID (nếu khác 0), verified_at để tra cứu.
Không lưu secret, URL đầy đủ hay query có chữ ký trong ledger.

Transaction cuối đã succeeded/failed không bị callback lặp ghi đè. Callback có
kết quả hoặc mã giao dịch mâu thuẫn sẽ đánh dấu review_required, không tự đổi
trạng thái đơn, không đánh dấu paid cho đơn đã hủy. Một digest cuối không phải
nhật ký sự kiện webhook đầy đủ; muốn audit mọi callback cần bổ sung event ledger.

## Thất bại, hết hạn, hủy và tồn kho

- IPN success/failure KHÔNG trừ/cộng kho. Orders đã trừ khi checkout.
- IPN có chữ ký hợp lệ, ResponseCode khác 00 và TransactionStatus=02 được coi
  là thất bại rõ ràng. Ghi failed nhưng không tự hủy hoặc hoàn kho. Admin có thể
  hủy pending/confirmed theo luồng Orders, hoàn kho đúng một lần.
- Trạng thái khác, dữ liệu đáng ngờ hoặc mâu thuẫn được giữ pending hoặc giữ
  trạng thái cuối và bật review_required. Không tự hoàn kho.
- Hết 15 phút tại local KHÔNG chứng minh VNPay chưa thu tiền. Không tự expire
  transaction, tạo attempt mới hay hủy đơn khi IPN chưa rõ. Cần querydr/đối soát.
- Đơn chưa tạo attempt VNPay có thể hủy vì chưa có URL được cấp; transaction
  pending/succeeded hoặc review_required sẽ chặn hủy. Đơn paid vẫn bị chặn hủy.
- VNPay chưa paid không được vào packing/shipping/delivered. COD vẫn có thể
  delivered/unpaid để xác nhận thu tiền riêng. Chuyển status không tự paid.
- Gửi lại yêu cầu hủy hoặc callback không hoàn kho lần hai. Chưa có refund;
  không coi hoàn kho là hoàn tiền. Không nhận thao tác paid từ API status đơn.

Các lỗi nghiệp vụ dùng 401/403/404/409/422/503; lỗi DB không lộ driver details.
Transaction rollback bao gồm order.payment_status và ledger, IPN trả 99 khi ghi
thất bại để có thể retry. Không tự retry POST làm phát sinh giao dịch mới.

## Biến môi trường cần người dùng cấu hình

| Biến | Giá trị cần cung cấp |
|---|---|
| VNPAY_ENABLED | true khi merchant Sandbox và callback đã sẵn sàng; mặc định false |
| VNPAY_TMN_CODE | Mã Sandbox chính thức VNPay cấp, 8 ký tự chữ/số |
| VNPAY_HASH_SECRET | Secret Sandbox VNPay cấp, không ghi vào Git/log/chat |
| VNPAY_RETURN_URL | HTTPS tới Backend /payments/vnpay/return, không query/fragment, tối đa 255 ký tự |

Biến có thể đến từ môi trường process hoặc .env gốc mà database.py đã load.
Không yêu cầu sửa database.py. Không in giá trị cấu hình. IPN URL không phải
tham số URL thanh toán; cần cấu hình/đăng ký với VNPay địa chỉ HTTPS công khai
trỏ vào Backend /payments/vnpay/ipn. Return và IPN là hai địa chỉ khác nhau.

Không tin X-Forwarded-For tự gửi bởi client. Nếu chạy sau reverse proxy, cấu hình
Uvicorn chỉ tin đúng proxy của bạn để request.client phản ánh IP khách. Không
xoay merchant/secret/return URL khi còn giao dịch pending mà chưa có kế hoạch
đối soát; phiên bản này chưa hỗ trợ nhiều thế hệ secret.

## Migration Payments — đã nằm trong lịch sử áp dụng

PostgreSQL hiện tại đã ở 20261017_0005 theo xác nhận của người dùng.
Các lệnh nâng từ 0003 lên 0004 dưới đây chỉ tham khảo cho môi trường khác chưa có Payments.

Revision 20261016_0004 nối 20261016_0003. Thêm orders.payment_method NOT NULL,
default cod và check cod/vnpay; tạo payment_transactions với FK, unique/check.
Đơn cũ được phân loại COD theo default — phải xác nhận giả định này trước khi
áp dụng nếu có đơn lịch sử dùng phương thức khác. Không thay đổi trạng thái
thanh toán hoặc kho của đơn cũ. Downgrade bị chặn để giữ lịch sử thanh toán.

Từ D:\DATN, xem SQL offline, không áp dụng:

```powershell
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini upgrade 20261016_0003:20261016_0004 --sql
```

Chỉ sau khi duyệt, sao lưu và xác nhận current=20261016_0003/đúng lumiere_db:

```powershell
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini upgrade 20261016_0004
```

Không cần chạy lại trên database hiện tại. Với môi trường mới, xử lý theo đúng
lịch sử, không dùng stamp để bỏ qua migration. Lần cập nhật tài liệu này không chạy migration.

## Test tự động và kiểm thử Sandbox sau cấu hình

```powershell
.\.venv\Scripts\python.exe -B backend/tests/test_payments_api.py
.\.venv\Scripts\python.exe -B backend/tests/test_catalog_api.py
.\.venv\Scripts\python.exe -B backend/tests/test_import_catalog.py
```

Payment suite kế thừa Order/Cart/Auth, dùng mock settings (không phải merchant
đăng ký/secret thật), gọi ASGI với SQLite memory, chặn PostgreSQL. Không gọi bất
kỳ endpoint VNPay nào. Gồm HMAC/canonicalization, URL, IPN/return, fake callback,
amount/merchant/ref sai, duplicate, failure, expiry, rollback, COD và phân quyền.

Sau khi có thông tin merchant Sandbox chính thức và database test đã áp dụng migration, nên dùng database
PostgreSQL test riêng. Cấu hình HTTPS return/IPN đúng Backend và đăng ký IPN với
VNPay. Đăng nhập customer, tạo giỏ, POST /orders với payment_method=vnpay, gọi
endpoint tạo URL rồi mở URL trên trình duyệt. Dùng dữ liệu thẻ/tài khoản test
từ tài liệu VNPay hiện hành, không dùng thẻ/tài khoản thật. Chờ IPN cập nhật,
kiểm tra đơn, ledger và stock; thử return trước IPN và callback retry. Không tự
giả lập một callback tự ký bằng secret operational trên database thật để chứng
minh tích hợp. Chưa chạy bất kỳ bước Sandbox end-to-end nào ở đây.

## Các phần đang chờ và mở rộng MoMo

`PaymentProvider` và get_provider là điểm thay adapter; không dùng lại thuật toán
ký VNPay cho MoMo. MoMo chưa có adapter, credential hoặc route; request momo bị
từ chối 422. Trước khi thêm cần giao thức chính thức, mapper callback, migration
allowlist payment_method và các test riêng.

Đang chờ merchant Sandbox/IPN công khai, kiểm thử chữ ký và mã lỗi với VNPay thật,
PostgreSQL concurrency test, querydr/reconciliation worker, refund và audit
webhook đầy đủ. Pending không có IPN có thể giữ kho lâu; đây là lựa chọn an toàn
hiện tại, cần quy trình đối soát thay vì tự giải phóng kho. Các chính sách phí
ship/thuế/giảm giá từ Orders vẫn tạm 0. Auth vẫn cần CSRF/rate limiting/Secure
cookie cho production; không triển khai các hạng mục đó trong bước này.
