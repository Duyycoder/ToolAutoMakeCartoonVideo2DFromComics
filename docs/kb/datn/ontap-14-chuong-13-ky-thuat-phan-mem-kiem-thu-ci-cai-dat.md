# Chương 13. Kỹ thuật phần mềm: kiểm thử, CI, cài đặt, xử lý lỗi, bảo mật, hiệu năng phần cứng

- Mục tiêu chương: các chương trước giải thích AI làm gì (dịch, TTS, sinh ảnh, dựng video). Chương này giải thích vì sao hệ thống đứng vững được trên máy người dùng thật: được kiểm thử ra sao, CI chạy gì, cài đặt thế nào, lỗi được xử lý/khôi phục ra sao, bảo mật ở đâu, và phần cứng GPU được khai thác thế nào. Đây là phần hội đồng hay hỏi để phân biệt "một demo chạy được trên máy tác giả" với "một sản phẩm phần mềm".

- Mọi số liệu trong chương được đọc trực tiếp từ code/config hoặc từ lần chạy test thật (ngày 2026-09-29). Những chỗ chưa chắc chắn được ghi rõ là "chưa xác minh".

## 1. Vai trò trong hệ thống

### 1.1. Vị trí của "kỹ thuật phần mềm" trong pipeline

Pipeline chính (Bước 1 cào & dịch → Bước 2 TTS → Bước 3 dựng hoạt hình → Bước 4 ghép video) là luồng nghiệp vụ. Lưu ý đánh số: trên UI hiển thị "Bước 1-4", nhưng trong code bước ghép video là `start_step_5_merge` (số nội bộ 5), còn số nội bộ 4 là `start_step_4_autosub` (phụ đề tự động, không nằm trong chuỗi tự động). Ánh xạ nằm ở `orchestrator/auto_run.py:13-20` ( `CHAIN_STEPS` gồm bước 1, 2, 3, 5; `DISPLAY_NO = {1: 1, 2: 2, 3: 3, 5: 4}` ). Phần kỹ thuật phần mềm là lớp cắt ngang (cross-cutting concerns) bao quanh luồng đó:

- **Mối quan tâm:** Kiểm thử · **Nằm ở đâu:** `tests/` (22 file, repo tổng), `AIVoice/apps/MediaComposer/tests/` (21 file) · **Input → Output:** Code → báo cáo pass/fail
- **Mối quan tâm:** CI/CD · **Nằm ở đâu:** `.github/workflows/ci.yml` , `.github/workflows/release.yml` · **Input → Output:** Mỗi push/PR/tag → lint + test + (release zip)
- **Mối quan tâm:** Cài đặt · **Nằm ở đâu:** `setup.bat` , `run.bat` , `CAP-NHAT.bat` , `installer/AutoCartoon.iss` · **Input → Output:** Máy trắng → môi trường Python + model + app chạy
- **Mối quan tâm:** Tự tải model · **Nằm ở đâu:** `orchestrator/model_preflight.py` · **Input → Output:** Cấu hình hiện tại → model còn thiếu được tải nền
- **Mối quan tâm:** Quản lý tiến trình & lỗi · **Nằm ở đâu:** `orchestrator/process_manager.py` , `orchestrator/auto_run.py` , `batch_video_runner.py` · **Input → Output:** Subprocess AI → log SSE, exit code, trạng thái, resume
- **Mối quan tâm:** Bảo mật · **Nằm ở đâu:** `file_security.py` , `video_merger._select_files` , `storage.slugify` , `desktop.py` (HOST), `.gitignore` · **Input → Output:** Input người dùng → đường dẫn an toàn; bí mật không lên git
- **Mối quan tâm:** Phần cứng · **Nằm ở đâu:** `hardware_adapter.py` , `AIVoice/src/check_gpu.py` , `main._gpu_total_mb` , `chatbot.vram_tier` · **Input → Output:** VRAM thật → profile chạy (fp16, CPU offload, thiết bị cho từng model)
- **Mối quan tâm:** Logging · **Nằm ở đâu:** `desktop._ensure_streams` → `logs/app.log` ; `ProcessManager.log_queues` → SSE · **Input → Output:** stdout/stderr → file log + màn hình UI

### 1.2. Bối cảnh ràng buộc (vì sao phần này quan trọng với dự án này)

Dự án có 3 đặc điểm làm cho kỹ thuật phần mềm khó hơn một web app thông thường:

- 1. Model AI nặng, cần GPU – không thể chạy Stable Diffusion trong CI (máy GitHub không có GPU). → Phải thiết kế test "GPU-free". 2. Chạy trên máy người dùng Windows chứ không phải server mình quản lý → cài đặt phải tự động, tự sửa, tự tải model thiếu. 3. Tác vụ rất dài (dựng một chương video có thể hàng chục phút) → phải chịu được crash giữa chừng, người dùng bấm Dừng, tràn VRAM (OOM) và chạy lại không làm lại từ đầu.

## 2. Nền tảng lý thuyết từ gốc

### 2.1. Kiểm thử phần mềm (software testing)

Trực giác. Test là "một người kiểm tra tự động không bao giờ mệt": mỗi lần sửa code, ta hỏi lại hàng trăm câu hỏi "chỗ này còn đúng không?" trong vài giây.

Các mức kiểm thử (testing pyramid – kim tự tháp kiểm thử):

- **Mức:** Unit · **Kiểm tra gì:** Logic của 1 hàm (vd `slugify` , `_select_files` ) · **Tốc độ:** mili- giây · **Độ tin cậy về "hệ thống thật":** Thấp nhất nhưng định vị lỗi chính xác
- **Mức:** Integration · **Kiểm tra gì:** Nhiều thành phần phối hợp (vd `ProcessManager` spawn process Python thật, FastAPI `TestClient` gọi endpoint) · **Tốc độ:** giây · **Độ tin cậy về "hệ thống thật":** Trung bình
- **Mức:** End-to-end (E2E) · **Kiểm tra gì:** Toàn bộ app, GPU thật, model thật · **Tốc độ:** phút– giờ · **Độ tin cậy về "hệ thống thật":** Cao nhất nhưng chậm, khó tự động

Nguyên tắc kim tự tháp: nhiều test đáy, ít test đỉnh, vì test đáy rẻ, ổn định, chạy mỗi lần commit; test đỉnh đắt và "flaky" (lúc pass lúc fail).

Test double – "diễn viên đóng thế" (thuật ngữ của Gerard Meszaros):

- **Loại:** Stub · **Ý nghĩa:** Trả về giá trị cố định, không có logic · **Ví dụ trong repo:** `StubStorage.read_story_meta` trả `{"story_slug": "test-story",...}` ( `tests/test_pipeline_llm.py` )
- **Loại:** Fake · **Ý nghĩa:** Bản cài đặt đơn giản nhưng hoạt động được · **Ví dụ trong repo:** `FakeProcess` , `FakePipeline` trong `tests/test_auto_run.py` có trạng thái running/exit_code
- **Loại:** Mock · **Ý nghĩa:** Đối tượng ghi lại lời gọi để assert · **Ví dụ trong repo:** `MagicMock` , `patch("httpx.Client.post")` trong `tests/test_chatbot.py`
- **Loại:** Spy · **Ý nghĩa:** Ghi nhận tham số thật được truyền · **Ví dụ trong repo:** `proc.captured_cmd` – stub ghi lại câu lệnh CLI mà pipeline dựng ( `tests/test_pipeline_build_cmd.py` )

Tại sao cần test double cho dự án AI? Vì hàm cần test (vd "Bước 3 có truyền đúng `--llm-api-key` không") không cần Stable Diffusion thật để trả lời. Ta cô lập logic điều phối khỏi model nặng. Đây là ý tưởng then chốt: test cái mình viết, không test PyTorch.

Các công cụ pytest cần nắm:

- fixture: hàm chuẩn bị môi trường, được pytest "tiêm" (dependency injection) vào test qua tên tham số. Ví dụ `tmp_path` (fixture có sẵn) cho mỗi test một thư mục tạm riêng → test không đụng dữ liệu thật và không ảnh hưởng nhau. monkeypatch: thay tạm thời một thuộc tính/hàm trong lúc test, tự khôi phục khi test xong. Ví dụ thật trong `tests/test_pipeline_llm.py:77` : `monkeypatch.setattr(config_mod, "load_global_config", lambda: state["config"])` → mỗi test tự đặt cấu hình giả trong `state["config"]` , không phụ thuộc file `configs/global_config.json` trên máy. `unittest.mock.patch` / `MagicMock` / `AsyncMock` : tạo đối tượng giả để thay HTTP client, Ollama... `@pytest.mark.parametrize` : một hàm test chạy với nhiều bộ input (data-driven test). `pytest.importorskip("cv2")` : bỏ qua test nếu thiếu thư viện (dùng trong `test_studio_matting.py:75` ).

Regression test (test hồi quy): test được viết sau khi phát hiện bug, để khoá bug đó không quay lại. Repo có rất nhiều test dạng này, docstring kể rõ bug gốc (vd `tests/test_chatbot_gate.py` "khoá lại ba khiếm khuyết đã từng xảy ra", `test_vae_dead_region.py` "batch 41 cảnh ngày 24/07 có 9 frame (22%) bị đen").

Giới hạn: test chỉ chứng minh có lỗi, không chứng minh không có lỗi (Dijkstra). Unit test với fake có thể pass trong khi hệ thống thật hỏng nếu fake khác hành vi thật.

### 2.2. Lint, static check và CI

- Lint (ở đây là Ruff): phân tích tĩnh mã nguồn, không chạy code, bắt lỗi như biến chưa định nghĩa, import thừa, cú pháp sai. Ruff viết bằng Rust nên rất nhanh. `python -m compileall` : biên dịch mọi file `.py` sang bytecode → bắt lỗi cú pháp ở cả những file không có test. CI (Continuous Integration): mỗi lần push/PR, một máy chủ sạch tự checkout code, cài dependency, chạy lint + test. Ý nghĩa: "nó chạy trên máy tôi" không còn là lý do – phải chạy trên máy sạch. CD / Release automation: khi gắn tag phiên bản, tự đóng gói và phát hành. GitHub Actions: dịch vụ CI của GitHub. Khái niệm: workflow (file YAML) → jobs (chạy trên runner – máy ảo) → steps (lệnh hoặc action dùng lại như `actions/checkout@v4` ). `needs:` tạo phụ thuộc giữa job.

### 2.3. Môi trường ảo và quản lý dependency

- virtualenv ( `python -m venv .venv` ): một thư mục chứa trình thông dịch Python + `site-packages` riêng. Mỗi dự án có bộ thư viện riêng, không xung đột phiên bản với dự án khác hay với Python hệ thống. `requirements.txt` : danh sách thư viện + ràng buộc phiên bản ( `fastapi>=0.100.0` ). `-r requirements.txt` trong file dev cho phép kế thừa. Vấn đề "dependency hell": PyTorch có nhiều bản build theo CUDA (cu121, cu124, cu128…). Cài nhầm bản CPU thì `torch.cuda.is_available()` = False dù máy có GPU. Vì vậy PyTorch phải cài từ index riêng `https://download.pytorch.org/whl/<cuXXX>` . `--system-site-packages` : venv được "nhìn thấy" thư viện của Python hệ thống → tái sử dụng PyTorch 2.4 GB đã có sẵn thay vì tải lại. Trong dự án đây là tuỳ chọn: `AIVoice/setup.bat` (dòng ~151-202) hỏi người dùng Y/N khi phát hiện Python hệ thống đã có torch; nếu không thì tạo venv sạch ( `python -m venv .venv` ).

### 2.4. GPU, CUDA, cuDNN, VRAM, fp16 – từ gốc

Tại sao GPU? Mạng nơ-ron thực chất là rất nhiều phép nhân ma trận. CPU có vài chục lõi mạnh, xử lý tuần tự giỏi; GPU có hàng nghìn lõi yếu chạy song song cùng một phép tính trên nhiều dữ liệu (SIMT). Nhân ma trận 1000×1000 = 10⁹ phép nhân-cộng, độc lập nhau → GPU nhanh hơn hàng chục lần.

CUDA: nền tảng lập trình của NVIDIA cho phép code chạy trên GPU. PyTorch gọi CUDA ở dưới. Mỗi thế hệ GPU có compute capability (vd RTX 50-series Blackwell là sm_120) – bản PyTorch phải được biên dịch cho kiến trúc đó, lý do RTX 50 bắt buộc cu128.

cuDNN: thư viện NVIDIA tối ưu sẵn các phép toán deep learning (convolution, attention, normalization). U-Net của Stable Diffusion dùng convolution rất nhiều → cuDNN quyết định tốc độ.

VRAM: bộ nhớ riêng của GPU. Mọi tensor tham gia tính toán (trọng số model + activation trung gian) phải nằm trong VRAM. Hết VRAM → lỗi `torch.cuda.OutOfMemoryError` (OOM). Ước lượng thô: số tham số × số byte/tham số. Ví dụ U-Net SD 1.5 khoảng 860 triệu tham số → fp32 (4 byte) ≈ 3.4 GB, fp16 (2 byte) ≈ 1.7 GB, chưa tính text encoder, VAE, activation.

PyTorch caching allocator: PyTorch không trả VRAM cho driver ngay mà giữ lại để tái dùng. Vì thế có hai con số:

`memory_allocated` = VRAM tensor đang thực sự dùng. `memory_reserved` = VRAM PyTorch đang giữ (≥ allocated). `torch.cuda.empty_cache()` trả phần reserved-nhưng-không- dùng về driver.

fp32 vs fp16 (số thực dấu phẩy động):

- **Định dạng:** fp32 · **Bit dấu:** 1 · **Bit mũ (exponent):** 8 · **Bit định trị (mantissa):** 23 · **Giá trị lớn nhất:** ≈ 3.4 × 10³⁸ · **Byte:** 4
- **Định dạng:** fp16 · **Bit dấu:** 1 · **Bit mũ (exponent):** 5 · **Bit định trị (mantissa):** 10 · **Giá trị lớn nhất:** 65504 · **Byte:** 2

Giá trị (số chuẩn hoá) = (−1)^dấu × 1.mantissa × 2^(exponent − bias), với bias = 15 cho fp16 và 127 cho fp32. Số mũ chỉ 5 bit nên phạm vi hẹp ở cả hai đầu: lớn nhất 65504, nhỏ nhất (chuẩn hoá) ≈ 6.1 × 10⁻⁵ – nhỏ hơn nữa thì dần underflow về 0. Mantissa 10 bit cho độ chính xác chỉ ≈ 3 chữ số thập phân. fp16 giảm một nửa bộ nhớ và chạy nhanh hơn trên Tensor Core, nhưng phạm vi nhỏ: phép tính nào vượt 65504 sẽ thành `inf` , rồi `inf − inf` thành `NaN` → pixel đen. Đây chính là nguồn gốc (theo phân tích của dự án) của lỗi "dải đen" với VAE tiling (mục 4.8).

bf16 (bfloat16) – câu hội đồng hay hỏi: cũng 16 bit nhưng 1 dấu / 8 mũ / 7 định trị → phạm vi giống fp32 (không tràn ở 65504) nhưng kém chính xác hơn fp16. GPU từ thế hệ Ampere (RTX 30) trở lên mới chạy bf16 nhanh. Dự án không dùng bf16: `image_generator.py:162` chỉ chọn giữa `torch.float16` và `torch.float32` . Đây là một hướng khắc phục khả dĩ cho lỗi tràn số VAE (chưa thử nghiệm trong dự án).

CPU offload: thay vì đặt toàn bộ pipeline (text encoder, U-Net, VAE) lên VRAM cùng lúc, chỉ đưa module đang chạy lên GPU, xong thì đẩy về RAM. Tiết kiệm VRAM đổi lấy thời gian copy qua PCIe. Trong diffusers là `enable_model_cpu_offload()` .

VAE slicing / tiling: VAE decode latent → ảnh tốn nhiều bộ nhớ. Slicing chia theo chiều batch (từng ảnh một); tiling chia ảnh thành các ô chồng lấn rồi ghép – tiết kiệm hơn nhưng có thể sinh đường nối/lỗi biên.

### 2.5. Xử lý lỗi, khôi phục, idempotency

Fail fast: phát hiện sai cấu hình càng sớm càng tốt (vd thiếu API key → báo lỗi trước khi spawn process 20 phút). Isolation (cô lập lỗi): chạy phần nguy hiểm trong subprocess riêng. Process con crash (segfault CUDA, OOM) không kéo sập server chính. Checkpoint/Resume: lưu trạng thái sau mỗi bước vào file; chạy lại thì đọc trạng thái và bỏ qua phần đã xong. Idempotency (tính luỹ đẳng): thực hiện một thao tác 1 lần hay N lần cho cùng kết quả: f(f(x)) = f(x). Ví dụ "chuẩn hoá tên chương" chạy lần 2 không đổi gì thêm. Idempotency làm cho retry an toàn. Graceful degradation: thiếu thành phần phụ thì hạ cấp chứ không chết (thiếu WebView2 → mở trình duyệt).

### 2.6. Bảo mật – các khái niệm cần thiết

Path traversal (duyệt ngược thư mục): kẻ tấn công truyền `../../Windows/win.ini` hoặc đường dẫn tuyệt đối để đọc/ghi ngoài thư mục cho phép. Phòng chống đúng cách: chuẩn hoá đường dẫn thật ( `realpath` – giải quyết `..` , symlink) rồi kiểm tra nó vẫn nằm trong thư mục gốc (so sánh `commonpath` ), không phải so sánh chuỗi tiền tố (vì `C:\data_evil` cũng bắt đầu bằng `C:\data` ). Allow-list (danh sách trắng) tốt hơn deny-list: chỉ nhận thứ đã biết là an toàn. Loopback binding: server lắng nghe `127.0.0.1` chỉ nhận kết nối từ chính máy đó; `0.0.0.0` nhận từ mọi máy trong mạng. CORS: cơ chế của trình duyệt chặn JavaScript ở origin khác đọc phản hồi API của mình (trừ khi server cho phép qua header `Access-Control-Allow-Origin` ). CORS không phải xác thực: chương trình không phải trình duyệt (curl, script Python) bỏ qua CORS hoàn toàn, và request "đơn giản" (vd form POST) vẫn tới được server dù trình duyệt không cho đọc kết quả. Vì vậy CORS chỉ là lớp phụ; lớp chính là binding loopback. Secret management: API key, cookie không bao giờ commit lên git (git lưu lịch sử vĩnh viễn). Least privilege: chạy với quyền tối thiểu cần thiết (installer không cần Admin).

## 3. Vì sao chọn các công nghệ này (so sánh phương án)

- **Quyết định:** Framework test · **Phương án được chọn:** pytest · **Phương án khác:** unittest (stdlib), nose · **Lý do chọn (bám code):** Fixture + `tmp_path` + `monkeypatch` + `parametrize` gọn; `unittest.mock` vẫn dùng được bên trong
- **Quyết định:** Lint · **Phương án được chọn:** Ruff · **Phương án khác:** flake8 + isort + pylint · **Lý do chọn (bám code):** Một công cụ, rất nhanh; CI chạy `ruff check orchestrator` `tests`
- **Quyết định:** CI · **Phương án được chọn:** GitHub Actions · **Phương án khác:** Jenkins, GitLab CI · **Lý do chọn (bám code):** Repo đã ở GitHub, miễn phí cho public repo, không cần server riêng
- **Quyết định:** Test AI · **Phương án được chọn:** GPU-free (stub model) · **Phương án khác:** Chạy model thật trong CI · **Lý do chọn (bám code):** Runner GitHub không có GPU; model nhiều GB; test chậm & flaky
- **Quyết định:** Môi trường · **Phương án được chọn:** venv + `requirements.txt` · **Phương án khác:** conda, Docker, Poetry · **Lý do chọn (bám code):** Người dùng Windows phổ thông; Docker trên Windows + GPU phức tạp (WSL2, NVIDIA Container Toolkit); conda nặng
- **Quyết định:** Số venv · **Phương án được chọn:** 2 venv: `AIVoice/.venv` (orchestrator dùng chung) + `toolCaoTruyen/.venv` · **Phương án khác:** 1 venv chung · **Lý do chọn (bám code):** Hai submodule là dự án độc lập, dependency có thể xung đột; orchestrator nhẹ nên "ở nhờ" AIVoice venv
- **Quyết định:** Cô lập model · **Phương án được chọn:** subprocess ( `adapter_*_cli.py` ) · **Phương án khác:** import trực tiếp torch vào FastAPI · **Lý do chọn (bám code):** Crash/OOM không kéo sập server; kill được cả cây process; giải phóng VRAM tuyệt đối khi process kết thúc
- **Quyết định:** Installer · **Phương án được chọn:** Inno Setup "web installer" · **Phương án khác:** PyInstaller đóng gói tất cả; MSI · **Lý do chọn (bám code):** Model + torch hàng chục GB, không nhét vào 1 file exe được; Inno Setup miễn phí, script đơn giản
- **Quyết định:** Cửa sổ app · **Phương án được chọn:** pywebview + WebView2, fallback trình duyệt · **Phương án khác:** Electron · **Lý do chọn (bám code):** Electron kéo theo Chromium ~150 MB; WebView2 có sẵn trên Windows 11
- **Quyết định:** Phát hiện GPU · **Phương án được chọn:** `torch.cuda` (trong AIVoice) + `nvidia-` `smi` /WMI (trong orchestrator) · **Phương án khác:** chỉ `torch` · **Lý do chọn (bám code):** Orchestrator cố ý không import torch ( `model_preflight.py:11-12` ) → dùng công cụ hệ thống

## 4. Hiện thực trong code

4.1. Bộ test của repo tổng ( `tests/` )

Cấu hình: `pytest.ini` chỉ có:

```
[pytest]
; Chi thu thap test trong thu muc tests/ — cac file test_*.py o goc repo
; la script tich hop thu cong (can server/GPU that), khong chay trong CI.
testpaths = tests
```

`tests/conftest.py` chỉ thêm gốc repo vào `sys.path` để `import orchestrator` hoạt động dù chạy pytest ở đâu.

Kết quả chạy thật (máy tác giả, `AIVoice/.venv` , 2026-09-29): `178 passed` – thời gian đo được dao động từ 6.7 s đến 21.6 s giữa các lần chạy, tuỳ tải máy.

Danh mục 22 file test và mục đích:

- **File:** `test_auto_run.py` · **Kiểm thử cái gì:** Chuỗi tự động Bước 1→2→3→5: chạy đúng thứ tự, dừng khi bước lỗi, hủy giữa chừng, từ chối chạy chồng · **Kỹ thuật:** `FakeProcess` , `FakePipeline` (không GPU, không process thật)
- **File:** `test_chapter_naming.py` · **Kiểm thử cái gì:** Nhận diện số chương từ tên file ( `"Chap.12.txt"` → 12), chuẩn hoá tên, chạy lại không đổi gì (idempotent), dry-run không đụng đĩa · **Kỹ thuật:** `parametrize` , `tmp_path`
- **File:** `test_chatbot.py` · **Kiểm thử cái gì:** Bỏ dấu tiếng Việt, chọn KB, vòng đời session, API `/api/chat/*` (health, busy 409, prewarm) · **Kỹ thuật:** `TestClient(app)` , `patch("httpx.Client.post")`
- **File:** `test_chatbot_agent.py` · **Kiểm thử cái gì:** Định tuyến ý định (intent) của agent: truy vấn, điều hướng, chạy pipeline · **Kỹ thuật:** Unit thuần
- **File:** `test_chatbot_gate.py` · **Kiểm thử cái gì:** Cổng chống bịa đặt `kb_min_score` : câu ngoài phạm vi bị chặn, stopword không overfit bộ eval, NDJSON kết thúc bằng newline · **Kỹ thuật:** Regression test
- **File:** `test_chatbot_rag.py` · **Kiểm thử cái gì:** Chia chunk KB mang đường dẫn tiêu đề, cache câu lặp (TTL, giới hạn, tách theo model), lượt "suy nghĩ" · **Kỹ thuật:** Logic thuần, `MagicMock` HTTP
- **File:** `test_chatbot_stream.py` · **Kiểm thử cái gì:** Stream câu trả lời; Ollama tắt thì trả lời rõ ràng không ném 500; payload `options.num_ctx` · **Kỹ thuật:** `AsyncMock` , `patch("httpx.AsyncClient.stream")`
- **File:** `test_mediacomposer_config.py` · **Kiểm thử cái gì:** Ghi tham số SD xuống `config.toml` giữ nguyên chú thích, chặn giá trị vô lý · **Kỹ thuật:** fixture `cfg_file` trên `tmp_path`
- **File:** `test_model_preflight.py` · **Kiểm thử cái gì:** Chỉ pull model Ollama mà cấu hình hiện tại thực sự dùng, không trùng · **Kỹ thuật:** Unit thuần `_wanted_ollama_models`
- **File:** `test_ollama_manager.py` · **Kiểm thử cái gì:** Chuẩn hoá URL, so tag `:latest` , tự khởi động server, tự pull model thiếu, báo lý do khi fail · **Kỹ thuật:** `patch.object(om, "is_server_up",...)`
- **File:** `test_open_output_folder.py` · **Kiểm thử cái gì:** Nút "Mở thư mục đầu ra" chọn đúng thư mục theo bước; endpoint 404 khi không có truyện · **Kỹ thuật:** `monkeypatchmain.storage_mgr` , không mở Explorer thật
- **File:** `test_p0_render_mode_cmd.py` · **Kiểm thử cái gì:** `render_mode="auto"` không truyền `--render-mode` xuống CLI; chọn tay thì thắng · **Kỹ thuật:** Tái dùng fixture `pipe`
- **File:** `test_pipeline_ai_write.py` · **Kiểm thử cái gì:** Nguồn "Sáng tác bằng AI" đi qua Bước 1; clamp số từ/chương · **Kỹ thuật:** Stub `story_writer.generate_story`
- **File:** `test_pipeline_build_cmd.py` · **Kiểm thử cái gì:** Câu lệnh CLI dựng cho Bước 1/4/5 (crop, cookies, output dir) · **Kỹ thuật:** Spy `proc.captured_cmd`
- **File:** `test_pipeline_llm.py` · **Kiểm thử cái gì:** Resolve LLM Bước 3 (Gemini offline/online, Ollama, fallback 11434), thiếu key phải báo lỗi sớm; fallback voice TTS · **Kỹ thuật:** Stub + `monkeypatch load_global_config`
- **File:** `test_pipeline_local_folder.py` · **Kiểm thử cái gì:** Nguồn "thư mục cục bộ": chép + đổi tên chuẩn, nạp lại không lỗi · **Kỹ thuật:** `tmp_path`
- **File:** `test_pipeline_video_completion.py` · **Kiểm thử cái gì:** Ghép video lỗi → `VIDEO_FAILED` ; thành công → `VIDEO_GENERATED` · **Kỹ thuật:** `ProcessManager` thật + monkeypatch merge
- **File:** `test_process_manager.py` · **Kiểm thử cái gì:** Log callback đến trước sự kiện kết thúc; reconnect không ping mãi; callback trả `False` ép exit 1; SSE hợp lệ khi log nhiều dòng · **Kỹ thuật:** Integration: spawn `sys.executable -c...` thật
- **File:** `test_storage.py` · **Kiểm thử cái gì:** `slugify` tiếng Việt & ký tự đặc biệt · **Kỹ thuật:** Unit thuần
- **File:** `test_ui_settings.py` · **Kiểm thử cái gì:** Lưu/đọc `ui_settings.json` ; file thiếu/hỏng trả `{}` · **Kỹ thuật:** `monkeypatch UI_SETTINGS_PATH`
- **File:** `test_video_downloader_diagnose.py` · **Kiểm thử cái gì:** Chẩn đoán lỗi tải video (IP bị chặn, bài riêng tư, WAF 403, TikTok); `probe` không bao giờ ném exception · **Kỹ thuật:** Nạp module bằng `importlib` với stub `sys.modules` cho `yt_dlp`
- **File:** `test_video_merger.py` · **Kiểm thử cái gì:** Lọc file ghép, chống path traversal trong `only_files` · **Kỹ thuật:** Unit thuần

Ngoài ra `tests/eval/kb_questions.jsonl` (36 câu) + `scripts/eval_chatbot.py` là bộ đánh giá chất lượng chatbot (đo tầng truy xuất KB), không phải unit test.

Ví dụ 1 – Fake để test máy trạng thái mà không cần GPU ( `tests/test_auto_run.py` ):

```
def test_chain_aborts_when_step_fails():
    mgr, pipe, _ = make_mgr(results={2: 7})
    ok, _ = mgr.start("Test", STEP1_ARGS, {}, {})
    assert ok
    st = wait_finished(mgr)
    assert "Bước 2" in st["error"] and "7" in st["error"]
                                         # bước 3 và 5 không được chạy
    assert pipe.calls == [1, 2]
```

`FakePipeline` nhận `results={2: 7}` nghĩa là "Bước 2 kết thúc với exit code 7". Test khẳng định chuỗi dừng đúng ở Bước 2 và không gọi Bước 3 (tốn GPU vô ích).

Ví dụ 2 – Cô lập module phụ thuộc nặng bằng stub `sys.modules` ( `tests/test_video_downloader_diagnose.py` ):

```
@pytest.fixture(scope="module")
def vd():
    saved = {k: sys.modules.get(k) for k in ("yt_dlp", "app", "app.utils", "app.utils.utils")}
    sys.modules["yt_dlp"] = types.ModuleType("yt_dlp")
    ...
    spec = importlib.util.spec_from_file_location("_vd_under_test", VD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        yield mod
    finally:
        for k, v in saved.items():
                 # khôi phục sys.modules
            ...
```

Kỹ thuật: Python tra `sys.modules` trước khi import thật → đặt module rỗng vào đó là "đánh lừa" được `import yt_dlp` . Fixture dùng `yield` để setup trước, teardown sau (khôi phục `sys.modules` ), tránh rò trạng thái sang test khác.

Ví dụ 3 – Integration test với process thật ( `tests/test_process_manager.py` ):

```
def test_callback_false_overrides_zero_child_exit_code(tmp_path):
    manager = ProcessManager()
    key = "failed-postprocess"
    assert manager.start_process(
        key, [sys.executable, "-c", "pass"], str(tmp_path),
        on_completed=lambda _exit_code: False,
    )
    events = list(manager.get_logs_generator(key))
    assert "exit_code=1" in "".join(events)
    assert manager.get_task_status(key)["exit_code"] == 1
```

Process con thành công (exit 0) nhưng bước hậu xử lý (vd ghép video) thất bại → trạng thái cuối phải là lỗi. Đây là bug thật từng có: UI báo "xong" dù video chưa ghép.

### 4.2. Bộ test GPU-free của MediaComposer

`AIVoice/apps/MediaComposer/tests/` có 21 file, tập trung vào phần sinh ảnh/dựng video nhưng không cần GPU: `test_batch_video_resume.py` (resume batch), `test_vae_dead_region.py` (phát hiện dải đen do VAE tiling), `test_style_lock.py` , `test_style_preset_applied.py` , 11 file `test_studio_*` (layout, llm_layout, compositor, matting, shadow, bg_cache, character_renderer, face_detail_gate, runtime, unify_pass, pipeline_smoke), `test_prompt_batch_failure.py` , `test_config_app_override.py` , `test_character_extractor.py` , `test_scene_state_metadata.py` , `test_storytelling_smoke.py` , `test_e2e_chapter_probe.py` (hồi quy nửa sau của một lần chạy thử chương "Tây Du Ký", dùng ảnh/âm thanh giả tạo bằng PIL và `wave` ).

Chạy thật: `136 passed, 6 warnings` (dùng `AIVoice/.venv` ; thời gian 17.7 s đến 44.3 s tuỳ lần chạy).

Ví dụ khoá bug VAE ( `test_vae_dead_region.py` ): tạo ảnh nhiễu ngẫu nhiên bằng numpy, rồi kiểm `StorytellingPipeline.has_dead_region(img)` – hàm thuần xử lý ảnh, gọi được mà không cần nạp model SD.

### 4.3. CI với GitHub Actions

`ci.yml` – chạy khi push lên `main` , `feat/**` , `dev/**` , khi PR vào `main` / `dev/**` , hoặc bấm tay ( `workflow_dispatch` ):

```
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: 'pip' }
      - run: python -m pip install -r orchestrator/requirements-dev.txt
      - run: python -m ruff check orchestrator tests
      - run: python -m compileall orchestrator -q
  test:
    needs: lint
    ...
      - run: python -m pytest -q tests/
```

(đã rút gọn cú pháp `with` , nội dung giữ nguyên ý). Điểm cần nói:

`permissions: contents: read` – quyền tối thiểu cho token CI. `concurrency: cancel-in-progress: true` – push liên tiếp thì huỷ run cũ, tiết kiệm phút CI. `needs: lint` – lint fail thì không tốn thời gian chạy test. Không checkout submodule trong `ci.yml` → chỉ test orchestrator. Đó là lý do test nào chạm vào code AIVoice phải tự stub phụ thuộc (như `test_video_downloader_diagnose.py` stub `yt_dlp` ). Rủi ro chưa xác minh: test này nạp file `AIVoice/apps/MediaComposer/app/services/video_downloader.py` nằm trong submodule; `ci.yml` không có `submodules:` `recursive` nên trên runner file có thể không tồn tại và fixture sẽ lỗi. Không kiểm tra được lịch sử Actions từ máy này ( `gh` chưa đăng nhập) – nên mở tab Actions trên GitHub xem run gần nhất trước khi bảo vệ. ( `release.yml` có checkout submodule nên không bị vấn đề này.) Runner là Ubuntu, trong khi app chạy Windows → code phân nhánh `os.name=="nt"` (vd `taskkill` ) không được CI kiểm.

`release.yml` – chạy khi push tag `v*` :

1. Job `verify` : checkout kèm submodule ( `submodules: recursive` ), chạy lại lint + test repo tổng, rồi cài tối thiểu `numpy` `pillow loguru openai toml opencv-python-headless` và chạy `pytest tests -q` trong `AIVoice/apps/MediaComposer` (ruff chỉ chọn lỗi nghiêm trọng `E9,F63,F7,F82` ), cuối cùng `compileall` / `py_compile` cho `toolCaoTruyen` . 2. Job `dong-goi` ( `needs: verify` ): zip mã nguồn (loại `.git` , `__pycache__` ) và tạo GitHub Release bằng `softprops/action-` `gh-release@v2` với release notes tự sinh.

### 4.4. Dependency và môi trường ảo

`orchestrator/requirements.txt` (runtime, cố ý nhẹ – không có torch):

```
fastapi>=0.100.0
uvicorn>=0.23.0
sse-starlette>=1.6.0
pydantic>=2.0.0
requests>=2.31.0
httpx>=0.24.0
pywebview>=5.0
```

`requirements-dev.txt` = `-r requirements.txt` + `ruff>=0.3.0` , `pytest>=8.0.0` , `pytest-cov>=4.1.0` .

Bố cục venv:

`toolCaoTruyen/.venv` – crawler/dịch ( `pipeline.py:150` ). `AIVoice/.venv` – TTS, MediaComposer, và cả orchestrator ( `pipeline.py:411, 525, 632` ; `setup.bat` bước 3 cài `orchestrator\requirements.txt` vào venv này).

Chọn bản PyTorch theo GPU trong `AIVoice/setup.bat` (dòng ~226-247): dùng PowerShell `Get-CimInstance` `Win32_VideoController` :

Tên GPU khớp `RTX 50` → `TORCH_INDEX=cu128` (Blackwell sm_120 bắt buộc). Có `NVIDIA` khác → `cu124` . Không có NVIDIA → bỏ qua, cài bản mặc định từ `requirements.txt` (CPU). Sau đó kiểm tra chuỗi `TORCH_INDEX` có nằm trong `torch.__version__` không (vd `2.x.y+cu124` ; `AIVoice/setup.bat:250` ); sai bản thì gỡ và cài lại đồng bộ `torch` `torchvision torchaudio` (ba gói phải cùng bản CUDA). Với RTX 50 còn nâng `onnxruntime-gpu>=1.22` cho InsightFace.

Lưu ý nhất quán: `AIVoice/src/check_gpu.py` gợi ý `cu121` cho RTX 30/40, trong khi `setup.bat` dùng `cu124` . Đây là thông báo cũ trong script chẩn đoán, không ảnh hưởng luồng cài.

### 4.5. Luồng cài đặt và khởi chạy

`setup.bat` (repo tổng), theo thứ tự:

1. `git submodule update--init--recursive` ; kiểm tra `toolCaoTruyen\setup.bat` và `AIVoice\setup.bat` tồn tại (clone thiếu `--recursive` sẽ để lại thư mục rỗng). 0.5. Tìm Python 3.11 theo 4 cách: `python` trong PATH (kiểm `py_ver:~0,4` == `3.11` ), `py -3.11` , `%LocalAppData%\Programs\Python\Python311` , `%ProgramFiles%\Python311` . Không có thì `curl` tải `python-3.11.9-amd64.exe` và cài im lặng `/quiet PrependPath=1` .

2. `call toolCaoTruyen\setup.bat` ; 2. `call AIVoice\setup.bat` (tạo venv, torch, thư viện, model).

3. Cài `orchestrator\requirements.txt` vào `AIVoice\.venv` . 3b. `scripts\cai_webview2.bat` .

4. Sinh `configs\global_config.json` bằng chính `load_global_config()` – một nguồn sự thật cho giá trị mặc định, và cố ý không copy `config.example.json` (vì file mẫu chứa key giả `YOUR_GEMINI_API_KEY_HERE` sẽ lọt qua kiểm tra rồi chết lúc gọi API).

`run.bat` :

Nếu thiếu `AIVoice\.venv\Scripts\python.exe` hoặc `toolCaoTruyen\.venv\Scripts\python.exe` → tự gọi `setup.bat` ("người dùng chỉ cần nháy đúp MỘT file"). Đặt `PYTHONPATH=%CD%` , `PYTHONIOENCODING=utf-8` . Chạy `pythonw.exe -m orchestrator.desktop` (không console, log vào `logs\app.log` ); `run.bat debug` dùng `python.exe` để thấy log trực tiếp. Ghi chú quan trọng trong file: sau khi di chuyển thư mục dự án, các `.exe` trong venv (uvicorn.exe, pip.exe) hỏng vì chứa đường dẫn tuyệt đối cũ → luôn gọi qua `python -m...` .

`orchestrator/desktop.py` : khởi động Gemini proxy ẩn (cổng 7860, bằng cách chạy `toolCaoTruyen/Gemini-` `API/start_server.bat` ; bỏ qua nếu thiếu file hoặc cổng đã mở), chạy uvicorn trong thread ( `HOST="127.0.0.1"` , `PORT=8100` ), chờ cổng mở tối đa 30 s ( `_wait_until_ready` ), mở cửa sổ pywebview 1280×840. Thiếu pywebview hoặc WebView2 → `_run_browser_fallback` ghi rõ lý do và mở trình duyệt. Đóng cửa sổ → `_shutdown` : `process_mgr.stop_all()` → kill Gemini proxy → `server.should_exit = True` . Có chế độ `--smoke` để tự kiểm: mở cửa sổ, chờ trang load, tự đóng sau 3 s, trả exit code 2 nếu trang chưa load.

`CAP-NHAT.bat` (cập nhật phần mềm):

Tự chép mình sang `%TEMP%` rồi chạy bản sao, vì bước cập nhật sẽ ghi đè chính file này và `cmd.exe` đọc `.bat` theo vị trí byte → file bị thay giữa chừng sẽ nhảy lung tung. Đo rủi ro trước khi ghi đè: đang ở nhánh khác `main` , có file sửa chưa commit, có commit chưa push → cảnh báo; có commit chưa push thì sao lưu vào nhánh `sao-luu/truoc-cap-nhat-<random>` . Người dùng phải gõ `Y` . Sau đó `git checkout -f -B main origin/main` , `git reset--hard origin/main` , `git submodule` `sync` + `update--init--recursive--force` , rồi `pip install -q -r orchestrator\requirements.txt` (vì cập nhật mã nguồn không tự kéo thư viện mới), cài WebView2, và gọi `run.bat` . Giữ nguyên: `storage` (truyện/video), `configs` (API key), model đã tải (đều bị `.gitignore` nên `reset--hard` không động tới).

`installer/AutoCartoon.iss` (Inno Setup 6, build bằng `installer/build_installer.bat` ):

Kiểu web installer: chỉ đóng gói mã nguồn; mục `[Run]` có `setup.bat` với cờ `postinstall` (ô tick ở trang cuối trình cài, bị bỏ qua khi cài im lặng) để tải Python + thư viện + model (cần Internet, 30-60 phút). Nếu người dùng bỏ tick, lần đầu mở `run.bat` vẫn tự gọi `setup.bat` . `PrivilegesRequired=lowest` , `DefaultDirName={userpf}\AutoCartoonVideoMaker` → cài vào `%LocalAppData%\Programs\...` không cần Admin; lý do ghi trong file: app tự ghi vào thư mục cài (venv, storage, logs, config) nên không được nằm trong Program Files. `Excludes:` loại `.git` , venv, model, `storage` , và các bí mật `\configs\global_config.json` , `cookies.json` , `*cookies*` , `*.key` , `*.pem` , `.env` , `.env.*` . Lỗ hổng cần biết: danh sách này không loại `api_keys.json` (khác `.gitignore` có `**/api_keys.json` ). Trên máy tác giả hiện có `toolCaoTruyen/Gemini-API/api_keys.json` (khoá truy cập proxy Gemini) → nếu build installer từ thư mục này, file đó sẽ bị đóng gói kèm. Nên thêm `api_keys.json` vào `Excludes` . `[UninstallDelete]` xoá venv, model, logs nhưng giữ lại `{app}\storage` (dữ liệu người dùng). `Compression=lzma2/max` , `SolidCompression=yes` .

Điểm không nhất quán cần biết: `[Run]` của installer vẫn copy `config.example.json` → `global_config.json` nếu chưa có, trái với lý do `setup.bat` bước 4 đã nêu (file mẫu chứa key giả). Hệ quả: máy cài bằng installer có thể có `api_keys.gemini` `= "YOUR_GEMINI_API_KEY_HERE"` . Nên sửa ở bản sau (đề xuất: bỏ dòng copy, để `load_global_config()` tự sinh).

4.6. Tự tải model còn thiếu: `model_preflight.py`

Gọi trong `_lifespan` của FastAPI ( `orchestrator/main.py` ) → chạy trong thread nền daemon, không chặn khởi động. Trạng thái đọc qua `get_state()` (endpoint `/api/models/preflight` ). Các bước:

- **Bước:** `ollama` · **Điều kiện bỏ qua:** Cấu hình không dùng Ollama · **Hành động:** `ensure_server` + `pull_model` cho chỉ model đang được cấu hình ( `_wanted_ollama_models` : chatbot nếu bật; translate nếu engine=ollama; video nếu LLM engine=ollama) · **Timeout:** theo `ollama_manager`
- **Bước:** `tts` · **Điều kiện bỏ qua:** Đã có `AIVoice/models/piper/vi_VN-` `vais1000-medium.onnx` · **Hành động:** subprocess `src/download_models.py--engine piper` · **Timeout:** 1800 s
- **Bước:** `video` · **Điều kiện bỏ qua:** Đã có marker `models/.preflight_ok` · **Hành động:** subprocess `app/services/model_downloader.py--download` · **Timeout:** 7200 s

Thiết kế đáng chú ý:

- Marker file `.preflight_ok` → lần mở sau bỏ qua ngay, khỏi gọi HuggingFace kiểm ETag mỗi lần (idempotent + nhanh). Tải qua subprocess dùng venv AIVoice → orchestrator không import torch/huggingface_hub. Lỗi được gói thành trạng thái `failed` kèm 3 dòng log cuối ( `tail =...splitlines()[-3:]` ), không ném exception làm sập app. `start()` dùng `_state_lock` để không chạy hai lượt song song.

4.7. Quản lý tiến trình & xử lý lỗi: `process_manager.py`

Đây là "trái tim" của độ bền hệ thống. Các cơ chế:

- 1. Mỗi task một khoá ( `task_key` ) – `start_process` trả `False` nếu key đang chạy/đang finalize → không chạy chồng cùng bước. 2. Log theo dòng: `stdout=PIPE, stderr=STDOUT, bufsize=1` , một `reader_thread` đọc `readline()` đẩy vào `queue.Queue` → SSE stream lên UI. `PYTHONIOENCODING=utf-8` để log tiếng Việt không vỡ. 3. Callback hậu xử lý trước sentinel: `on_completed(exit_code)` chạy xong mới `q.put(None)` . Nếu callback trả `False` hoặc ném exception, exit code 0 bị ép thành 1. 4. Kill cả cây tiến trình ( `_kill_process_tree` ):

```
if os.name == "nt":
    subprocess.run(
        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
        capture_output=True, timeout=15,
        creationflags=NO_WINDOW)
else:
    proc.terminate()
```

Docstring giải thích: nếu chỉ `terminate()` con, cháu (ffmpeg, SD...) mồ côi vẫn giữ đầu ghi của pipe stdout → reader kẹt ở `readline()` vĩnh viễn → UI kẹt "đang chạy". `/T` = cả cây, `/F` = cưỡng bức.

- 1. Kill ngoài lock: vì `wait` mất vài giây, giữ lock sẽ treo mọi endpoint khác. 2. Fallback 8 giây: chờ reader tự dọn tối đa 8 s; quá hạn thì tự giải phóng bookkeeping, đặt exit code (hoặc `-1` ), đẩy log `[SYSTEM]Đã buộc dừng tiến trình theo yêu cầu.` → người dùng luôn bắt đầu lại được. 3. Phân biệt "người dùng dừng" với "lỗi thật": `user_stopped_tasks` / `was_user_stopped()` → trạng thái truyện thành `CANCELLED` thay vì `*_FAILED` . 4. `stop_all()` khi tắt app: không để lại process mồ côi chiếm VRAM.

Máy trạng thái truyện ( `story.json` → `status` , trong `pipeline.py` ): `CRAWLING→CRAWLED→TRANSLATING→TRANSLATED→` `VOICE_GENERATING→VOICE_GENERATED→VIDEO_GENERATING→VIDEO_GENERATED` , và nhánh phụ đề `AUTOSUB_RUNNING→` `AUTOSUB_COMPLETED` ; cùng các trạng thái lỗi `CRAWL_FAILED` , `TRANSLATE_FAILED` , `VOICE_FAILED` , `VIDEO_FAILED` , `AUTOSUB_FAILED` , `WRITE_FAILED` (nguồn "Sáng tác bằng AI") và `CANCELLED` (người dùng bấm Dừng).

Fail fast: `test_pipeline_llm.py` có `test_step3_gemini_online_thieu_key_phai_bao_loi_som` – Bước 3 thiếu key phải báo lỗi trước khi spawn process. `auto_run._run_chain` bắt `ValueError` (vd thiếu API key) và dừng chuỗi với thông điệp `Bước X:...` .

Chống tranh chấp GPU giữa chatbot và pipeline ( `main.pypost_chat` ):

- `single_chat_lock.acquire(blocking=False)` → câu trước chưa xong thì trả 429. Nếu `block_when_busy` (mặc định `True` ) và pipeline đang chạy tác vụ GPU nặng → trả 409 kèm `lookup_answer` (trả lời bằng tra cứu KB, không gọi LLM) thay vì tranh VRAM.

### 4.8. Resume, idempotency và xử lý OOM trong sinh video

Batch resume ( `AIVoice/apps/MediaComposer/app/services/storytelling/batch_video_runner.py` ):

- Trạng thái mỗi item lưu trong `batch_state.json` ở thư mục output: `pending→script_done→images_done→upscale_done` `→video_done` , hoặc `failed` . Mỗi lần đổi trạng thái gọi `save()` ngay → crash ở đâu thì chạy lại tiếp từ đó. Item `failed` được reset về `pending` khi chạy lại; trạng thái tuyên bố nhưng thiếu `state.json` hợp lệ → hạ về `pending` (không tin trạng thái "nói dối"). `_reconcile_video_done` ( `batch_video_runner.py:74` ): item ghi `video_done` nhưng file output mất → thử khôi phục `final_video.mp4` từ task dir; không có thì hạ cấp về trạng thái suy ra từ `state.json` của task ( `_resume_status_from_task_state` : `upscale_done` / `images_done` / `script_done` / `pending` ) – tests `test_stale_video_done_recovers_final_video_from_task_dir` và `test_stale_video_done_without_any_video_is_downgraded` .

Chiến lược 2 pass tối ưu VRAM (docstring `run_batch` ):

- Pass A: kịch bản + sinh toàn bộ ảnh bằng SD (giữ SD "nóng" trong VRAM). `StorytellingPipeline().release()` giải phóng SD. Pass B: upscale (Real-ESRGAN) + render video (giữ ESRGAN nóng). → Tránh việc SD và ESRGAN cùng chiếm VRAM trên GPU 6-8 GB.

OOM → release + retry 1 lần:

```
except Exception as e:
    error_msg = str(e)
    is_oom = "OutOfMemoryError" in error_msg or "CUDA out of memory" in error_msg
    if is_oom:
        logger.warning(f"[BatchRunner] OOM cho {item.stem} trong Pass A, release & retry...")
        try:
            from app.services.storytelling.image_generator import StorytellingPipeline
            StorytellingPipeline().release()
        except Exception:
            pass
        try:
            _process_single_item_pass_a(...)
            continue
        except Exception as e2:
            error_msg = str(e2)
    state.update_item(item.stem, STATUS_FAILED, error=error_msg)
```

Lỗi của 1 item không dừng cả batch – ghi `failed` rồi sang item kế.

`release()` ( `image_generator.py` ): `unload_lora_weights()` → `del self._pipe` → `gc.collect()` hai lần (dọn tham chiếu vòng) → `torch.cuda.synchronize()` (chờ kernel GPU chạy ngầm xong, tránh "illegal memory access") → `empty_cache()` → `ipc_collect()` . `log_vram()` cảnh báo khi `reserved/total > 92%` vì driver có thể "spill" sang RAM làm chậm 2-3 lần.

Bug fp16 + VAE tiling (ví dụ điển hình để kể với hội đồng): bản cũ bật VAE tiling cho mọi ảnh khi CPU offload. Quan sát thực tế: batch 41 cảnh có 9 frame (22%) bị dải đen dọc rộng đúng 512 hoặc 384 px – khớp biên ô tiling. Nguyên nhân: một ô tràn số fp16 (> 65504 → inf/NaN) là cả dải pixel của ô đó đen. Sửa: chỉ bật tiling khi cạnh ảnh ≥ `VAE_TILING_MIN_EDGE = 1024` ( `image_generator.py:32` , hàm `_set_vae_tiling` ), ảnh mặc định 768×432 không cần tiling; thêm `has_dead_region()` (chỉ tính các hàng/cột bão hoà trọn vẹn, `min_fraction=0.04` ) để phát hiện; phát hiện thì sinh lại với seed khác tối đa `DEAD_REGION_RETRIES = 2` lần ( `image_generator.py:34, 719-738` ); khoá bằng `test_vae_dead_region.py` . Lưu ý trung thực: "tràn số fp16" là giải thích ghi trong docstring `_set_vae_tiling` , dựa trên quan sát dải đen khớp đúng biên ô (latent rộng 96, ô 64, chồng lấn 25% → bước 48 → ô pixel 0-512 và 384-768); đây là suy luận có căn cứ, dự án không đo trực tiếp giá trị inf/NaN.

Idempotency ở các nơi khác:

`chapter_naming` – test `test_normalize_chay_lai_khong_doi_gi_them` . `test_pipeline_local_folder.test_nap_lai_thu_muc_da_nap_thi_khong_bao_loi` . `model_preflight` marker, `pip install` (bỏ qua nhanh khi đã đủ – ghi chú trong `CAP-NHAT.bat` ). `AIVoice/setup.bat` kiểm bản torch trước khi cài lại.

Dọn dẹp ( `orchestrator/cleanup.py` + `StorageManager.cleanup_tasks` ): CLI `python -m orchestrator.cleanup--tasks [--days` `N] [--dry-run]` , `--rebuild-db` , `--stats` . Chỉ xoá thư mục job dạng UUID và thư mục khung ảnh tạm ( `draft_frames` , `final_frames` , `scenes` , `temp_audio` , `temp` ); không bao giờ đi vào `contexts` , `character_loras` (tri thức nhân vật/LoRA – `PROTECTED_DIRS` ). `--rebuild-db` dựng lại SQLite từ các `story.json` (file JSON là nguồn sự thật, SQLite chỉ là bản mirror).

### 4.9. Bảo mật

(a) Chống path traversal – `file_security.resolve_path_within_directory` ( `AIVoice/apps/MediaComposer/app/utils/file_security.py` ):

```
base_dir_real = os.path.realpath(base_dir)
candidate_path = unsafe_path
if not os.path.isabs(candidate_path):
    candidate_path = os.path.join(base_dir_real, candidate_path)
```

```
resolved_path = os.path.realpath(candidate_path)
try:
    common_path = os.path.commonpath([base_dir_real, resolved_path])
except ValueError as exc:
    # Windows: khac o dia -> ValueError -> chac chan ngoai thu muc cho phep
    raise ValueError("path is outside the allowed directory") from exc
```

```
if common_path != base_dir_real:
    raise ValueError("path is outside the allowed directory")
```

(chú thích gốc bằng tiếng Trung vì kế thừa từ dự án mã nguồn mở gốc của MediaComposer; ở đây dịch ý). Vì sao đúng:

- `realpath` giải quyết `..` , dấu phân cách trùng, symlink → so sánh trên đường dẫn thật. `commonpath` so sánh theo thành phần thư mục, không theo chuỗi → `C:\songs_evil` không lọt khi gốc là `C:\songs` . Khác ổ đĩa trên Windows → `ValueError` → coi là ngoài vùng. `require_file=True` mặc định: phải là file tồn tại.

Nơi dùng ( `AIVoice/apps/MediaComposer/app/services/video.py` ): nhạc nền chỉ được đọc trong `resource/songs` (dòng ~482- 495) và lọc vật liệu video local (chỉ trong `storage/local_videos` , dòng ~1222; path không an toàn thì `logger.warning` và bỏ qua).

(b) Ghép video chỉ nhận basename – `orchestrator/video_merger._select_files` :

```
# CHỐNG PATH TRAVERSAL: chỉ nhận basename thuần, phải nằm trong danh sách quét được
wanted = {name for name in only_files if os.path.basename(name) == name}
filtered = [f for f in filtered if os.path.basename(f) in wanted]
```

Hai lớp: (1) tên có dấu phân cách bị loại; (2) chỉ chọn trong danh sách file thực sự quét được từ thư mục video (allow-list). Test `test_select_files_path_traversal` truyền `["../secret.mp4", "1.mp4", "/etc/passwd.mp4"]` → chỉ còn `1.mp4` .

(c) Tên truyện → thư mục qua `slugify` ( `orchestrator/storage.py` ): `re.sub(r'[^\w\s-]', '', text)` loại `.` , `/` , `\` , `:` → tên `"../../x"` thành `"x"` ; rỗng thì `"unknown"` . `get_story_dir` luôn là `truyen_dir/<slug>` → tên truyện không thể thoát khỏi thư mục storage.

(d) Chỉ lắng nghe loopback: `desktop.pyHOST = "127.0.0.1"` ; uvicorn `host=HOST` . MediaComposer WebUI (Streamlit) cũng `-server.address 127.0.0.1` ( `app/api.py:44` ). CORS chỉ cho `http://127.0.0.1:8100` và `http://localhost:8100` , `allow_credentials=False` ( `main.py:44-50` ). Kết quả: máy khác trong mạng LAN không gọi được API orchestrator (cổng 8100).

Ngoại lệ quan trọng – Gemini proxy cổng 7860: `toolCaoTruyen/Gemini-API/start_server.bat` chạy `uvicorn server.main:app` `-host 0.0.0.0--port 7860` (và `server/config.py:18` mặc định `HOST="0.0.0.0"` ) → proxy này nghe trên mọi card mạng, máy khác trong LAN kết nối tới được. Proxy có xác thực Bearer bằng `api_keys.json` ( `server/auth.pyverify_api_key` ), nhưng có nhánh chấp nhận mọi token bắt đầu bằng `ey` (JWT) có `iss` chứa "openai" mà không kiểm chữ ký ( `_decode_jwt_payload_unverified` , `server/auth.py:48-55` ) → về nguyên tắc có thể giả mạo token để dùng ké cookie Gemini của người dùng. Hướng sửa: bind `127.0.0.1` và bỏ nhánh JWT không kiểm chữ ký. (Mã này nằm trong submodule `toolCaoTruyen` .)

(e) Bí mật không lên git ( `.gitignore` dòng ~29-37): `.env` , `.env.*` , `configs/global_config.json` , `configs/ui_settings.json` , `**/cookies.json` , `**/api_keys.json` , `*cookies*` , `*.key` , `*.pem` . Trọng số model ( `*.safetensors` , `*.ckpt` , `*.onnx` , `*.pth` , `*.gguf` ) và media sinh ra cũng bị loại (vừa nặng vừa có thể chứa dữ liệu người dùng). Installer áp dụng danh sách loại trừ tương tự. `config.example.json` chỉ chứa placeholder.

(f) Least privilege: CI `permissions: contents: read` (release thì `contents: write` vì phải tạo release); installer `PrivilegesRequired=lowest` .

(g) Không lộ cửa sổ/không leo quyền: subprocess dùng `CREATE_NO_WINDOW` , truyền `cmd` dạng list (không `shell=True` ) → không bị shell injection qua tham số tên truyện/URL.

### 4.10. Phần cứng: phát hiện và phân tầng (tiering)

Trong MediaComposer – `hardware_adapter.get_hardware_config()` :

```
# RTX 5060 8GB (hoặc các dòng GPU >= 8GB VRAM)
if vram_gb >= 7.0:
resolved_profile = "cuda_high"
else:
resolved_profile = "cuda_low"
```

- **Khoá:** `sd_device` · **`cpu` (không có CUDA):** cpu · **`cuda_low` (VRAM < 7 GB):** cuda · **`cuda_high` (VRAM ≥ 7 GB):** cuda
- **Khoá:** `face_device` (InsightFace) · **`cpu` (không có CUDA):** cpu · **`cuda_low` (VRAM < 7 GB):** cpu (tránh tranh VRAM) · **`cuda_high` (VRAM ≥ 7 GB):** cuda
- **Khoá:** `esrgan_device` · **`cpu` (không có CUDA):** cpu · **`cuda_low` (VRAM < 7 GB):** cuda · **`cuda_high` (VRAM ≥ 7 GB):** cuda
- **Khoá:** `whisper_device` · **`cpu` (không có CUDA):** cpu · **`cuda_low` (VRAM < 7 GB):** cpu (chừa VRAM cho SD/ESRGAN) · **`cuda_high` (VRAM ≥ 7 GB):** cuda
- **Khoá:** `enable_cpu_offload` · **`cpu` (không có CUDA):** False · **`cuda_low` (VRAM < 7 GB):** True · **`cuda_high` (VRAM ≥ 7 GB):** False
- **Khoá:** `use_fp16` · **`cpu` (không có CUDA):** False · **`cuda_low` (VRAM < 7 GB):** True · **`cuda_high` (VRAM ≥ 7 GB):** True
- **Khoá:** `profile_name` · **`cpu` (không có CUDA):** "Chỉ chạy CPU (CPU Only)" · **`cuda_low` (VRAM < 7 GB):** "Tiết kiệm VRAM (GPU <= 6GB VRAM)" · **`cuda_high` (VRAM ≥ 7 GB):** "Tối đa tốc độ (GPU >= 8GB VRAM)"

- Ngưỡng 7.0 GB (không phải 8.0): code chỉ chú thích "RTX 5060 8GB (hoặc các dòng GPU >= 8GB VRAM)". Giải thích hợp lý (suy luận, không ghi trong code): `total_memory` của card "8 GB" thường báo thấp hơn 8.0 GiB một chút, đặt ngưỡng 8.0 sẽ xếp nhầm card 8 GB vào `cuda_low` ; 7.0 chừa biên an toàn. Profile đọc từ `config.toml` khoá `hardware_profile` (mặc định `"auto"` ), có thể ép qua CLI `--hardware-profile` `auto|cuda_high|cuda_low|cpu` ( `adapter_video_cli.py` ). Dò VRAM lỗi → fallback an toàn `cuda_low` . Người dùng: `image_generator.py:159-162` lấy `sd_device` và `dtype = torch.float16 if use_fp16 else torch.float32` ; `:274-285` bật `enable_model_cpu_offload()` + `vae.enable_slicing()` khi offload; bật offload lỗi thì fallback `.to(device)` .

Trong orchestrator (không có torch):

- `main._gpu_total_mb()` : `nvidia-smi--query-gpu=memory.total--format=csv,noheader,nounits` ; không có thì `_wmi_gpu()` qua PowerShell `Get-CimInstance Win32_VideoController` (AMD/Intel). Ghi chú: `AdapterRAM` là uint32 nên card > 4 GB bị báo trần ~4 GB – thiên về an toàn. `chatbot.vram_tier(total_mb)` : `"6gb" if total_mb<7168 else "8gb"` ; `TIER_DEFAULT_MODEL = {"6gb": "qwen2.5:3b",` `"8gb": "qwen2.5:7b-instruct"}` . Không dò được VRAM → mặc định `"8gb"` . `/api/system/gpu-info` trả tên GPU + VRAM cho UI.

Chẩn đoán – `AIVoice/src/check_gpu.py` : in phiên bản PyTorch, `torch.cuda.is_available()` , `torch.version.cuda` , cuDNN ( `torch.backends.cudnn.version()` ), từng GPU (compute capability, total/allocated/reserved), thử SDPA ( `scaled_dot_product_attention` với tensor fp16 1×1×8×64) và nhân ma trận 1000×1000 + `torch.cuda.synchronize()` . Dùng khi người dùng báo "chạy chậm" để biết có đang chạy CPU không.

Tham số sinh ảnh mặc định ( `orchestrator/config.py:14-27SD_TUNING_DEFAULTS` ): `sd_steps=8` , `sd_guidance=5.0` , ảnh 768×432 (upscale lên output 1920×1080), 24 fps, face detailer 14 steps / strength 0.45, IP-Adapter scale 0.6. `sd_steps=8` < `QUALITY_MODE_MIN_STEPS = 15` ( `image_generator.py:23` ) nên mặc định chạy chế độ Fast (Hyper-SD LoRA) thay vì Quality (DPM++). Sinh ở 768×432 rồi upscale bằng Real-ESRGAN tiết kiệm VRAM/thời gian hơn sinh thẳng 1080p; code không ghi lý do chọn từng con số, phần "vừa GPU 6-8 GB" là diễn giải.

### 4.11. Logging

- **Nguồn:** Orchestrator khi chạy `pythonw` · **Đích:** `logs/app.log` · **Cơ chế:** `desktop._ensure_streams()` : dưới `pythonw` , `sys.stdout/stderr` là `None` → mọi `print` /logging sẽ lỗi → chuyển hướng vào file append, `buffering=1` (line- buffered)
- **Nguồn:** Gemini proxy · **Đích:** `logs/gemini_api.log` · **Cơ chế:** `_start_gemini_proxy` truyền file handle cho `Popen`
- **Nguồn:** Subprocess AI (crawler, TTS, video) · **Đích:** UI qua SSE · **Cơ chế:** `ProcessManager.log_queues[task_key]` → `get_logs_generator` → `_sse_data`
- **Nguồn:** MediaComposer · **Đích:** console của subprocess → SSE · **Cơ chế:** `loguru` ( `logger.info/warning/error` )
- **Nguồn:** Orchestrator module · **Đích:** `logging.getLogger(__name__)` · **Cơ chế:** theo cấu hình mặc định của uvicorn

Thư mục `logs/` hiện có `app.log` , `dl-mc.log` , `dl-tts.log` , `gemini_api.log` , `prefetch-*.log` , `setup-aivoice.log` , `uvicorn-` `*.log` . `*.log` bị `.gitignore` . Chưa có log rotation (file chỉ append) – xem mục Hạn chế.

## 5. Sơ đồ tổng hợp: một lần chạy Bước 3 đi qua các lớp bảo vệ

## 6. Hạn chế & hướng phát triển (đánh giá trung thực)

- **#:** 1 · **Hạn chế:** Không có test E2E tự động với GPU; chất lượng ảnh/giọng chỉ kiểm bằng mắt/tai · **Bằng chứng:** CI chạy `ubuntu-latest` , không GPU · **Hướng khắc phục:** Self-hosted runner có GPU chạy smoke test 1 chương ngắn hàng đêm; đo metric (CLIP score, thời gian/scene)
- **#:** 2 · **Hạn chế:** CI chạy Linux, app chạy Windows → nhánh `os.name=="nt"` ( `taskkill` ), file `.bat` , pywebview không được CI kiểm · **Bằng chứng:** `runs-on: ubuntu-latest` · **Hướng khắc phục:** Thêm matrix `windows-latest` ; chạy `desktop.py-` `-smoke`
- **#:** 3 · **Hạn chế:** `ci.yml` không checkout submodule và không chạy test MediaComposer; chỉ `release.yml` mới chạy · **Bằng chứng:** So sánh 2 workflow · **Hướng khắc phục:** Thêm job MediaComposer GPU-free vào `ci.yml`
- **#:** 4 · **Hạn chế:** Chưa đo coverage dù có `pytest-cov` trong dev requirements · **Bằng chứng:** `ci.yml` không có `--cov` · **Hướng khắc phục:** `pytest--cov=orchestrator--cov-report=xml` , đặt ngưỡng
- **#:** 5 · **Hạn chế:** Ghi JSON không atomic: `write_story_meta` , `save_global_config` , `_BatchState.save` mở file `"w"` trực tiếp; mất điện giữa chừng → file hỏng (đọc lại trả `None` / `{}` ) · **Bằng chứng:** `storage.py:135-147` , `config.py:200-208` · **Hướng khắc phục:** Ghi ra file tạm rồi `os.replace()` (atomic trên cùng ổ)
- **#:** 6 · **Hạn chế:** `load_global_config()` nuốt mọi exception và trả `{}` → lỗi cấu hình bị che · **Bằng chứng:** `config.py:197` · **Hướng khắc phục:** Log cảnh báo, giữ bản sao `.bak`
- **#:** 7 · **Hạn chế:** API key truyền qua tham số dòng lệnh ( `--` `llm-api-key` , `--gemini-api-key` ) → nhìn thấy được trong danh sách tiến trình (Task Manager, `wmic process` ) · **Bằng chứng:** `pipeline.py:181, 548, 662` · **Hướng khắc phục:** Truyền qua biến môi trường ( `env_override` đã có sẵn trong `start_process` ) hoặc stdin
- **#:** 8 · **Hạn chế:** API không xác thực: dựa hoàn toàn vào bind `127.0.0.1` ; bất kỳ chương trình nào trên cùng máy đều gọi được · **Bằng chứng:** `desktop.py:18` · **Hướng khắc phục:** Token ngẫu nhiên sinh lúc khởi động, cửa sổ webview gửi kèm header
- **#:** 8b · **Hạn chế:** Gemini proxy nghe `0.0.0.0:7860` , chấp nhận JWT "openai" không kiểm chữ ký, và in 30 ký tự đầu của API key ra log ( `DEBUG` `AUTH` ) · **Bằng chứng:** `toolCaoTruyen/Gemini-` `API/start_server.bat` , `server/auth.py:46-55` · **Hướng khắc phục:** Bind `127.0.0.1` , bỏ nhánh JWT, bỏ log key
- **#:** 8c · **Hạn chế:** Installer không loại `api_keys.json` khỏi gói · **Bằng chứng:** `installer/AutoCartoon.iss` `Excludes` · **Hướng khắc phục:** Thêm `api_keys.json` (đồng bộ với `.gitignore` )
- **#:** 9 · **Hạn chế:** Installer copy `config.example.json` (có key giả) trái với chủ đích `setup.bat` · **Bằng chứng:** `AutoCartoon.iss[Run]` · **Hướng khắc phục:** Bỏ dòng copy, để `load_global_config()` tự sinh
- **#:** 10 · **Hạn chế:** Không có log rotation; `app.log` tăng mãi · **Bằng chứng:** `desktop._ensure_streams` mở `"a"` · **Hướng khắc phục:** `logging.handlers.RotatingFileHandler`
- **#:** 11 · **Hạn chế:** Nhận diện OOM bằng so khớp chuỗi trong message; chỉ retry 1 lần, không tự hạ độ phân giải/profile · **Bằng chứng:** `batch_video_runner.py:269` · **Hướng khắc phục:** Bắt `torch.cuda.OutOfMemoryError` trực tiếp; retry với `cuda_low` hoặc ảnh nhỏ hơn
- **#:** 12 · **Hạn chế:** Phát hiện GPU phía orchestrator: WMI `AdapterRAM` uint32 trần ~4 GB với AMD/Intel; ngưỡng tier cố định · **Bằng chứng:** `main._wmi_gpu` · **Hướng khắc phục:** Dùng DXGI hoặc thông tin từ `torch` qua subprocess
- **#:** 13 · **Hạn chế:** Phụ thuộc phiên bản bằng `>=` (không lock) → bản mới của thư viện có thể phá build · **Bằng chứng:** `requirements.txt` · **Hướng khắc phục:** Lock file ( `pip-tools` / `uv lock` ) có hash
- **#:** 14 · **Hạn chế:** `check_gpu.py` gợi ý `cu121` trong khi `setup.bat` dùng `cu124` · **Bằng chứng:** 2 file · **Hướng khắc phục:** Đồng bộ thông báo
- **#:** `▾` Câu hỏi hội đồng có thể hỏi

### 1. Hệ thống dùng AI nặng, vậy các em kiểm thử thế nào khi CI không có GPU?

Tách logic điều phối khỏi model. Model chạy trong subprocess riêng, còn orchestrator chỉ dựng câu lệnh, quản lý process và trạng thái → test được bằng stub/fake (vd `FakePipeline` , `StubStorage` , spy `captured_cmd` ). Phần xử lý ảnh thuần của MediaComposer (layout, compositor, phát hiện dải đen VAE) cũng test không cần GPU. Kết quả: 178 test repo tổng + 136 test MediaComposer, đều pass, mỗi bộ chạy trong vài chục giây.

### 2. Phân biệt unit test và integration test trong dự án của em?

Unit: `test_storage.py` ( `slugify` ), `test_video_merger.py` ( `_select_files` ) – một hàm, không I/O. Integration: `test_process_manager.py` spawn process Python thật và đọc SSE; `test_chatbot.py` dùng FastAPI `TestClient` gọi endpoint thật qua toàn bộ stack HTTP.

### 3. `monkeypatch` và `mock` khác nhau thế nào, em dùng khi nào?

`monkeypatch` (fixture pytest) thay tạm một thuộc tính/hàm và tự khôi phục – em dùng để thay `load_global_config` hay `UI_SETTINGS_PATH` để test không phụ thuộc máy. `MagicMock/AsyncMock` là đối tượng giả có thể cấu hình giá trị trả về và ghi lại lời gọi – dùng thay HTTP client của Ollama.

### 4. CI của em chạy những gì?

`ci.yml` : mỗi push/PR → job `lint` (Ruff + `compileall` ) → job `test` ( `pytest -q tests/` ) trên Ubuntu, Python 3.11, có cache pip, huỷ run cũ khi push mới. `release.yml` : khi gắn tag `v*` → kiểm tra cả 3 phần (kèm submodule, test MediaComposer GPU-free, compile toolCaoTruyen) rồi zip mã nguồn và tạo GitHub Release.

### 5. Người dùng không biết lập trình cài phần mềm thế nào?

Hai cách: chạy installer Inno Setup (không cần Admin) hoặc `git clone` rồi nháy đúp `run.bat` . `run.bat` thấy thiếu venv thì tự chạy `setup.bat` : đồng bộ submodule, tự tải Python 3.11.9 nếu thiếu, tạo 2 venv, chọn bản PyTorch theo GPU (cu128 cho RTX 50, cu124 cho NVIDIA khác), tải model. Lần mở app sau, `model_preflight` tự tải nốt model còn thiếu ở nền.

### 6. Vì sao không dùng Docker?

Người dùng mục tiêu là máy Windows cá nhân. Docker + GPU trên Windows cần WSL2 và NVIDIA Container Toolkit, image chứa PyTorch CUDA nặng nhiều GB, và app cần cửa sổ desktop (WebView2) – venv + script `.bat` đơn giản hơn nhiều cho đối tượng này.

### 7. Em phát hiện phần cứng và chọn cấu hình như thế nào?

`hardware_adapter.get_hardware_config()` : không có CUDA → CPU fp32. Có CUDA và `hardware_profile="auto"` → đọc `total_memory` ; ≥ 7.0 GB là `cuda_high` (fp16, không offload, mọi model trên GPU), dưới là `cuda_low` (fp16, bật CPU offload cho SD, InsightFace và Whisper chạy CPU để chừa VRAM). Ngưỡng 7.0 vì card 8 GB thực báo ~7.6 GiB.

### 8. fp16 là gì, tại sao dùng, có rủi ro gì?

Số thực 16 bit (1 dấu, 5 mũ, 10 định trị), giảm một nửa VRAM so với fp32 và nhanh hơn trên Tensor Core. Rủi ro: giá trị lớn nhất chỉ 65504, tràn → inf/NaN. Dự án gặp thật: VAE tiling ở fp16 làm 9/41 frame có dải đen dọc 512/384 px; sửa bằng cách chỉ bật tiling khi cạnh ≥ 1024 px và thêm bộ phát hiện `has_dead_region` , khoá bằng test.

### 9. Nếu đang dựng video mà máy tắt đột ngột hoặc hết VRAM thì sao?

Batch runner lưu trạng thái từng item vào `batch_state.json` sau mỗi giai đoạn ( `script_done` , `images_done` , `upscale_done` , `video_done` ) → chạy lại tiếp từ chỗ dở. OOM thì `release()` pipeline SD (gc + `synchronize` + `empty_cache` ) và thử lại 1 lần; vẫn lỗi thì đánh dấu `failed` và sang item kế, không dừng cả batch. Trạng thái "đã xong" mà mất file thì bị hạ cấp để làm lại.

### 10. Khi người dùng bấm Dừng, làm sao đảm bảo không còn tiến trình chiếm GPU?

`ProcessManager._kill_process_tree` dùng `taskkill /PID<pid> /T /F` diệt cả cây (adapter + ffmpeg + SD). Nếu chỉ kill con, cháu mồ côi giữ pipe khiến UI kẹt "đang chạy". Có fallback 8 s tự giải phóng trạng thái. Đóng app thì `stop_all()` diệt hết.

### 11. Chống path traversal ở đâu và theo nguyên lý gì?

`file_security.resolve_path_within_directory` : `realpath` để giải `..` /symlink, rồi `commonpath` phải bằng thư mục gốc (so theo thành phần, không theo chuỗi), khác ổ đĩa coi là ngoài vùng. Dùng cho nhạc nền và video local. `video_merger._select_files` chỉ nhận basename thuần nằm trong danh sách quét được. Tên truyện đi qua `slugify` loại hết `.` , `/` , `\` .

### 12. API key được bảo vệ ra sao?

Lưu trong `configs/global_config.json` – file này, cùng `.env` , `cookies.json` , `api_keys.json` , `*.key` , `*.pem` đều trong `.gitignore` ; installer cũng loại `global_config.json` , cookies, `.env` , `*.key` , `*.pem` . Server orchestrator chỉ bind `127.0.0.1` , CORS chỉ cho origin `127.0.0.1:8100` / `localhost:8100` . Hạn chế em nhận thấy: (1) key đang được truyền cho subprocess qua tham số dòng lệnh (lộ trong danh sách tiến trình) – hướng sửa là truyền qua biến môi trường; (2) proxy Gemini trong submodule nghe `0.0.0.0` và có nhánh JWT không kiểm chữ ký – cần bind loopback; (3) installer chưa loại `api_keys.json` .

### 13. Idempotency thể hiện ở đâu trong hệ thống?

Chuẩn hoá tên chương chạy lần 2 không đổi gì (có test); nạp lại thư mục local không lỗi; `model_preflight` dùng marker `.preflight_ok` và kiểm file Piper trước khi tải; `setup.bat` kiểm bản torch trước khi cài lại; `pip install` bỏ qua khi đã đủ. Nhờ vậy người dùng có thể chạy lại bất kỳ bước nào an toàn.

### 14. Vì sao chatbot trả 409 khi pipeline đang chạy?

Chatbot dùng LLM qua Ollama cũng cần VRAM. Trên GPU 6-8 GB, chạy song song với SD dễ OOM. Nếu `block_when_busy=True` và có tác vụ GPU nặng, endpoint trả 409 kèm câu trả lời tra cứu KB (không gọi LLM); người dùng có thể ép `force` . Ngoài ra khoá `single_chat_lock` trả 429 nếu câu trước chưa xong.

### 15. Điểm yếu lớn nhất về mặt kỹ thuật phần mềm là gì?

Chưa có kiểm thử E2E tự động với GPU thật và CI chưa chạy trên Windows – hai thứ mà sản phẩm thực sự phụ thuộc. Ngoài ra ghi JSON chưa atomic, chưa có log rotation, và proxy Gemini (submodule) còn nghe `0.0.0.0` thay vì loopback. Em đã có hướng khắc phục cụ thể (self-hosted GPU runner, matrix windows-latest, ghi tạm + `os.replace` , `RotatingFileHandler` ).

### 16. Em đã cấu hình CORS, vậy API đã an toàn chưa?

Chưa đủ, và CORS không phải cơ chế xác thực. CORS chỉ khiến trình duyệt không cho trang web ở origin lạ đọc phản hồi; curl hay script Python bỏ qua CORS. Lớp bảo vệ chính là bind `127.0.0.1` (máy khác trong LAN không kết nối được). Chương trình khác trên cùng máy vẫn gọi được API vì chưa có token – hướng phát triển là sinh token ngẫu nhiên lúc khởi động và cửa sổ webview gửi kèm.

### 17. Vì sao không dùng bf16 để tránh tràn số fp16?

bf16 có 8 bit mũ như fp32 nên không tràn ở 65504, nhưng chỉ chạy nhanh trên GPU từ Ampere trở lên và kém chính xác hơn fp16. Code hiện chỉ chọn fp16/fp32 ( `image_generator.py:162` ); em xử lý lỗi dải đen bằng cách tắt VAE tiling cho ảnh nhỏ và tự sinh lại khi phát hiện dải chết. bf16 là một hướng thử nghiệm tiếp theo.

## Tóm tắt 1 phút

"Phần kỹ thuật phần mềm của em giải quyết một bài toán khó: hệ thống dùng model AI nặng cần GPU nhưng vẫn phải kiểm thử tự động được và chạy ổn định trên máy Windows của người dùng. Em tách logic điều phối khỏi model: model chạy trong subprocess riêng, còn orchestrator được kiểm thử bằng stub và fake – 178 test ở repo tổng và 136 test GPU-free ở MediaComposer, tất cả đều pass. GitHub Actions chạy Ruff và pytest mỗi lần push, còn khi gắn tag phiên bản thì kiểm tra cả ba phần rồi tự đóng gói release. Người dùng chỉ cần nháy đúp run.bat: script tự cài Python 3.11, tạo venv, chọn bản PyTorch đúng CUDA theo GPU, tải model, và lúc mở app thì tự tải nốt model còn thiếu. Về phần cứng, hệ thống đọc VRAM: từ 7 GB trở lên chạy fp16 toàn bộ trên GPU, dưới mức đó thì bật CPU offload và đẩy Whisper, InsightFace sang CPU. Về độ bền: trạng thái batch được lưu từng bước để chạy tiếp khi gặp lỗi, OOM thì giải phóng VRAM rồi thử lại, bấm Dừng thì diệt cả cây tiến trình. Về bảo mật: server chính chỉ nghe 127.0.0.1, đường dẫn được kiểm bằng realpath và commonpath, bí mật không lên git. Điểm em còn thiếu là test E2E với GPU thật và CI trên Windows – đó là hướng phát triển tiếp theo."
