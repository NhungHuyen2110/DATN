# Dependencies và chính sách tái sử dụng environment

Kiểm tra 19/11/2026 bằng metadata, `pip check`, import probes trong process riêng,
AST imports của backend/tests/tools/migrations, AI mới/cũ và dataset tools; không chạy
module legacy có eager clients. [Inventory đầy đủ](evidence/dependency-audit.json)
ghi từng distribution/version và trạng thái từng requirement, không phải danh sách đề nghị cài.

**Lượt này: 0 lượt cài package, 0 model downloads, không đổi system Python, không kết nối
database production, không khởi động/pull Docker, không thay đổi Application Control.**

## Những gì đã có

| Thành phần | Kết quả | Xử lý |
| --- | --- | --- |
| `.venv` | Python 3.11.9, 83 distributions, không dùng system-site-packages | Giữ nguyên và gọi `.venv/Scripts/python.exe` trực tiếp |
| Pip dependency metadata | `pip check`: No broken requirements; active runtime/dev/semantic pins đều tương thích | Không cài lại hoặc upgrade |
| Backend libraries | FastAPI 0.143.0, SQLAlchemy 2.1.4, psycopg 3.3.6, Alembic 1.20.0, auth/test packages đã có | Reuse; import probe không gọi DB |
| AI mới | Neo4j 6.4.1, Qdrant client 1.20.0, ST 6.3.0, torch 2.15.0+cpu, NumPy/sklearn đã có | Reuse; CPU build thỏa pin torch==2.15.0 |
| Pandas 3.1.1 | Metadata đúng version nhưng `hashtable` DLL bị Windows Application Control chặn | BLOCKED nhánh cần Pandas; không cài lại cùng wheel hoặc tắt bảo vệ |
| Model cache | `.cache/hf/models`, 479729245 bytes (~457.5 MiB) trên đĩa | Reuse; đây là dung lượng cache, không phải ước lượng download mới |
| Cached-model smoke | 2 vectors 384D, network connections bị cấm, cache không đổi | PASS; không phải quality benchmark |
| Node | Portable `.cache/node.exe` v22.16.0; không có npm trên PATH | Unit transport không cần npm hoặc package ngoài |
| Frontend E2E | Có lock Playwright 1.64.1 nhưng chưa có node_modules/browser được xác minh | BLOCKED E2E; không tự npm install/tải browser |
| Docker | CLI có, daemon pipe không tồn tại | Images inventory chưa xác định, không được coi là không có images; không tự bật Desktop/pull |
| Portable test runtimes | Java 21.0.9+10 và Neo4j Community 5.26.33 đã có trong `.cache/runtime` | Giữ nguyên; lượt audit không start/stop/reinstall |
| System Python | Kiểm kê riêng chỉ thấy pip/setuptools | Không dùng để cài dependencies dự án hoặc bật system-site-packages |

## Requirements theo chức năng

| File | Mục đích |
| --- | --- |
| `requirements.txt` | Entry point runtime backend + modular AI, không kéo model weights/CrewAI |
| `requirements-dev.txt` | Backend tests + AI runtime + packaging cho audit; các package hiện đã có |
| `backend/requirements.txt` | Business service/migrations/auth runtime |
| `backend/requirements-test.txt` | Thêm pytest và **httpx 0.28.1** cho FastAPI TestClient |
| `backend/requirements-migrations.txt` | Profile migrations cũ, Alembic hiện có đã thỏa; không cần cài riêng |
| `AI/requirements-runtime.txt` | API và graph/vector/catalog SDKs; giữ Pandas phục vụ callers legacy hiện hữu |
| `AI/requirements-semantic.txt` | Runtime + ST/torch versions đang chạy; không thay CPU torch đã có |
| `AI/requirements.txt` | Snapshot đầy đủ legacy giữ để đối chiếu; không cài gộp vào environment mới |
| `frontend/package.json` + lock | Giữ dependencies, thêm engine Node >=20 nhất quán; không regenerate bằng npm |

Đã sửa test dependency `httpx2` sang `httpx`: TestClient import `httpx`, hai distribution
khác nhau. Không uninstall httpx2 đang có; chỉ tránh kéo package không dùng trong profile test mới.
Snapshot AI legacy có 159 entries: 57 thỏa version, 91 chưa cài và 11 version mismatch
so với `.venv` hiện tại. Đây không phải lý do cài thêm 91 packages: nhiều dependencies
thuộc CrewAI/Chroma/CLI/OS tools không cần cho modular pipeline và có thể thay version
FastAPI/uvicorn/dotenv đang được kiểm chứng. Legacy cần environment riêng và compatibility
check trước khi lựa chọn installer; lượt này không resolve hoặc cài stack đó.

Source scan không thấy distribution thiếu ở backend runtime/tests/tools, modular AI/tests
hoặc scripts. Legacy thiếu requests/CrewAI; tools tạo dataset/chuyển ảnh thiếu Faker/Pillow.
Những module tùy chọn này chưa nằm trong công việc chạy hiện tại, không nhập package từ
system Python hoặc thêm PYTHONPATH để lách cách ly. Full legacy runtime vẫn chưa nghiệm thu.

## Không tự tải model

Modular `SemanticModelProvider` mặc định `local_files_only=True`, `trust_remote_code=False`.
Ưu tiên AI_MODEL_CACHE nếu khai báo, rồi workspace cache đã có; trong container có thể dùng
HF_HOME được mount. Thiếu cache thì source được báo unavailable, không tự tải weights.
AI_ALLOW_MODEL_DOWNLOAD chỉ là opt-in vận hành sau khi người dùng đã cho phép; agent không
tự bật nó. Unit test của opt-in mock constructor, không phát sinh download.

Policy mới áp dụng provider modular; các scripts legacy còn eager model/client initialization
chưa được chạy hoặc xác nhận an toàn tải model trong lượt này. Không dùng chúng làm dependency
probe. Không dùng `--trusted-host`, tắt TLS/antivirus/App Control hoặc thay execution policy.

## Lệnh kiểm tra không cài đặt

```powershell
.venv/Scripts/python.exe scripts/audit_dependencies.py
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe scripts/check_cached_model.py
.venv/Scripts/python.exe scripts/run_ai_checks.py
.venv/Scripts/python.exe scripts/run_business_checks.py --sqlite-bootstrap --pytest --openapi docs/baseline/business-openapi-current.json
```

Audit exit 1/PARTIAL khi có import bị chặn, dù metadata/requirements đều thỏa; không tự
chạy installer để "sửa". `--metadata-only` không import SDK/model libraries và không phải
readiness proof. Test DB runner giữ guard chỉ SQLite `:memory:`. Cached-model checker cấm
socket connections, ép offline/local-only và kiểm file cache không đổi. Không tải model mới.

## Khi phát sinh nhu cầu cài thêm

Hiện không cần cài gì để tiếp tục các phần đã kiểm thử. Trước một thao tác cài thực sự,
kiểm lại package/version/import trong đúng venv, mục đích và compatibility; chỉ đề nghị
phần thiếu cho nhánh đang cần. Nguồn dự kiến cho Python packages là PyPI; CPU torch dùng
index chính thức PyTorch khi cần, không thay bằng GPU build. Frontend dùng npm registry
theo lockfile; browser/model download phải xem là thao tác riêng.

Chưa resolve/download nên không biết chính xác transfer size của các packages tùy chọn;
không ghi số ước đoán như dữ kiện. Nếu cần installer về sau, cung cấp tên, mục đích,
nguồn và dung lượng ước tính được xác minh trước yêu cầu quyền. Không chạy bulk install
để kiểm tra package đã có, không cài toàn hệ thống, không chạy image/model pulls ẩn.

## Triển khai và kiểm thử không bị chặn

Backend đã có `/health/live` không đọc DB và `/health/ready` dùng kiểm tra DB hiện hữu;
giữ `/health` và OpenAPI 60 paths. Dockerfile dùng liveness để không gắn process health
với DB readiness. Docker image mới chưa build/run nên không gọi đây là container evidence.

[Regression lượt này](evidence/dependency-regression.json): 640 backend tests + 827 subtests
PASS, 51 AI tests PASS + 1 skip empty-graph gate. Schema business 60/AI 6 paths exact equality.
Hai backend tests mới kiểm liveness độc lập DB và readiness 503 không lộ DSN; hai AI tests
kiểm model policy/cache reuse. Năm frontend transport tests đã PASS lượt trước; lượt này chỉ
kiểm package/lock consistency vì không thay JS. Model cache smoke PASS với network bị cấm.
Không công bố điểm chất lượng AI từ những kiểm tra này. Review CSV/benchmark vẫn PENDING_REVIEW.
