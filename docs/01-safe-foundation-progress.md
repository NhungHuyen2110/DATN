# Safe foundation — tiến độ ngày 18/11/2026

**Trạng thái: partially implemented.** PHASE 0 vẫn cần hoàn tất review chi tiết các file còn lại; chưa có DB live/E2E/fault test. Các thay đổi hiện tại giới hạn ở công cụ kiểm thử/preflight đã đọc source liên quan, không thay runtime website.

## CURRENT / CHANGE

Ổ C còn rất ít dung lượng; mọi command tiếp theo đặt `TEMP`/`TMP` về `.local-tmp` trên ổ D. Không thay biến môi trường Windows vĩnh viễn. `.local-tmp/.gitignore` loại bỏ dependency/cache/checkpoint khỏi Git.

Đã tạo branch `rebuild/lumiere-audit-20261118`, giữ nguyên dirty/untracked user source. HEAD vẫn là `cb645852891748b045ac966cb1a18df637c50554`; không commit, reset, clean hoặc stash thay đổi người dùng.

Đã sao chép và xác minh SHA-256 7 file vào `.local-tmp/checkpoints/csv-preflight-20261118/`: graph importer/schema và năm file liên quan thay đổi password reset/web hiện có. Backup không chứa `.env`, CSV khách hàng hay database. Chưa phải backup toàn bộ project/data.

Thêm `scripts/run_backend_tests.py` để chạy pytest bao gồm cả test hàm và unittest, trước khi import app: đặt DB env giả, chặn dotenv, SQLAlchemy Engine.connect chỉ cho SQLite `:memory:`, chặn socket connect/connect_ex. Chỉ cho phép socketpair stdlib trên cùng thread khi asyncio Windows tạo internal wakeup pipe; không cho phép tùy ý gọi service localhost. Không coi các guard Python này là sandbox cho mọi native extension hoặc subprocess.

pytest 9.2.0 và dependencies được cài vào `.local-tmp/testdeps` trên D, không sửa environment có sẵn. Đây là bootstrap local, chưa phải requirements lock reproducible trên CI. Runner tắt pytest plugin autoload và cache.

## TEST

```powershell
$env:TEMP='D:\LUMIERE-FINAL-TEST\.local-tmp'
$env:TMP=$env:TEMP
$env:PYTHONPATH='D:\LUMIERE-FINAL-TEST\.local-tmp\testdeps'
& 'D:\JewelryDatasetGenerator\.venv\Scripts\python.exe' -B scripts/run_backend_tests.py
```

Kết quả thực tế với runner đã sửa guard Windows: **633 passed, 827 subtests passed, 1 warning trong 121.84s**. Warning: Starlette deprecation khi dùng httpx với TestClient. Lần chạy này có `-x` (dừng lỗi đầu tiên) và đi tới 100%, exit 0. Không còn 11 lỗi thiếu pytest của baseline cũ. Kết quả không chứng minh PostgreSQL transaction/concurrency production hay E2E browser; toàn bộ DB kết nối được phép là SQLite in-memory.

Lưu ý số đếm: một số module tái sử dụng/import các unittest TestCase nên pytest có thể collect lại scenario ở nhiều node ID. 633 là số item được runner collect và chạy, không phải tuyên bố có 633 kịch bản nghiệp vụ độc lập.

Sau khi thêm guard canaries: collection chạy lại thành công với 633 item; xác nhận SQLite file bị chặn, socket tới service bị chặn, SQLite in-memory và socketpair nội bộ hoạt động. Bộ 2 test inventory vẫn pass; `git diff --check` không lỗi whitespace. Không chạy lại toàn backend suite vì không đổi runtime backend/frontend.

Lần thử runner đầu bị lỗi do guard chặn socketpair của asyncio Windows; đã dừng, chẩn đoán, sửa guard và chạy lại. Các failure đó thuộc harness, không được thống kê là bug runtime. Bốn lỗi retrieval ở probe audit vẫn chưa sửa.

## COMPATIBILITY / RISK / ROLLBACK

Không sửa file Customer/Staff/Admin runtime. Code kiểm thử không gọi app thật qua mạng. Test trả pass không thay thế smoke của password reset untracked hoặc bảo đảm Playwright. Không cài package lên C và không sửa global Python. Dependency bootstrap chưa được version-lock trong repo.

Rollback tool/preflight mới bằng cách so sánh đúng file bổ sung; rollback hai file graph có bản checkpoint/hash. Không xóa `.local-tmp` hàng loạt vì có checkpoint cần giữ. Không chạy importer ghi, migration, restart/stop Docker hay public deploy.

## NEXT

Hoàn tất source coverage audit, kiểm chứng chính runner bằng guard canaries và chuẩn hóa test dependencies riêng; password-reset regression; graph preflight/writer/constraints integration trên Neo4j dev đã xác nhận; tiếp tục theo gate trong `00-audit-as-is.md`. Các phase 3–9 chưa triển khai.
