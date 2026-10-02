# 8. Kiểm thử, hiệu năng, bảo mật, triển khai

Chạy lại hôm nay (01/10/2026): 223 passed / 26 tệp test / 23,54 s ở repo tổng (gồm cả test Dashboard chưa commit); MediaComposer GPU-free: **138 passed / 46,93 s**. Báo cáo chốt 12/09 ghi 173 passed / 21 tệp / 7,86 s; tài liệu ôn tập ghi 178 (29/09). Nói số trong báo cáo trước, rồi bổ sung "sau ngày chốt em thêm test, chạy lại được 223/223".

## 8.1 Kiểm thử

### 8.1.1 Kế hoạch kiểm thử gồm mấy cấp?
- **Mức:** ★
- **Ý trả lời chính:** Ba cấp: (1) tự động — unit/API bằng pytest + FastAPI TestClient, AI được mock; (2) chức năng hệ thống — 16 ca TC01–TC16 theo use case, phần lớn thủ công trên dữ liệu thật; (3) phi chức năng — thời gian, VRAM, chất lượng đầu ra. Cộng hồi quy trên CI.
- **Tra ở:** Báo cáo 5.1

### 8.1.2 AI cần GPU, vậy kiểm thử tự động thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** Tách điều phối khỏi mô hình: test không nạp model. Dùng `FakeProcess` / `FakePipeline` , `StubStorage` , spy lệnh được dựng ( `captured_cmd` ), stub `sys.modules` cho thư viện nặng, TestClient cho API, dependency injection cho Studio. Chất lượng AI đo riêng (CJK, eval chatbot, kiểm thủ công).
- **Tra ở:** Q19, ch13 câu 1

### 8.1.3 Unit test và integration test khác gì? Ví dụ?
- **Mức:** ★
- **Ý trả lời chính:** Unit: một hàm, không I/O — `test_storage.py` ( `slugify` ), `test_video_merger.py` ( `_select_files` ). Integration: nhiều thành phần thật — `test_process_manager.py` spawn process Python thật và đọc SSE; `test_chatbot.py` gọi endpoint qua TestClient.
- **Tra ở:** ch13 câu 2

### 8.1.4 `monkeypatch` và mock khác nhau thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** `monkeypatch` (fixture pytest) thay tạm thuộc tính/hàm và tự khôi phục (vd thay `storage_mgr` trong `test_dashboard_crud.py` ). `MagicMock/AsyncMock` là đối tượng giả cấu hình giá trị trả về và ghi lại lời gọi (thay HTTP client Ollama).
- **Tra ở:** ch13 câu 3

### 8.1.5 Fixture là gì? `tmp_path` dùng để làm gì?
- **Mức:** ★★
- **Ý trả lời chính:** Hàm chuẩn bị môi trường tái dùng cho test. `tmp_path` cho thư mục tạm riêng mỗi test, test không đụng `storage/` thật.
- **Tra ở:** `tests/test_dashboard_crud.py:11-` `24`

### 8.1.6 Kể vài ca kiểm thử hệ thống. Ca nào chưa đạt?
- **Mức:** ★
- **Ý trả lời chính:** TC01 tạo workspace, TC05 chạy lại Bước 2 chỉ sinh chương thiếu, TC07 upscale FP32 + fallback, TC09 chặn path traversal, TC10 AutoRun dừng khi lỗi, TC12 dừng cây tiến trình, TC13 dựng lại SQLite. 15/16 đạt; TC16 từ chối ngoài phạm vi 87,5% < 90%.
- **Tra ở:** Bảng 5.3

### 8.1.7 Bảng 5.3 thiếu cột các bước thực hiện — làm sao tái hiện được ca kiểm thử?
- **Mức:** ★★
- **Ý trả lời chính:** Nhận thiếu sót trình bày; mỗi ca theo đúng luồng chính của use case tương ứng (Bảng 3.4–3.19). Chuẩn bị nói miệng 3–4 bước cho TC05 và TC12.
- **Tra ở:** Báo cáo 5.3

### 8.1.8 Độ phủ mã (coverage) bao nhiêu?
- **Mức:** ★★
- **Ý trả lời chính:** Chưa đo (báo cáo ghi ngoài phạm vi). Cách đo: `pytest --` `cov=orchestrator` . Nói thẳng, khóa bằng số test theo nhóm mô-đun.
- **Tra ở:** Báo cáo 5.1.1

### 8.1.9 Kiểm thử hộp đen, hộp trắng, hồi quy là gì? Ở đâu trong dự án?
- **Mức:** ★★
- **Ý trả lời chính:** Hộp đen: theo đặc tả đầu vào– đầu ra (TC theo use case, eval chatbot). Hộp trắng: biết cấu trúc code (test nhánh fallback, spy lệnh). Hồi quy: test khóa lỗi đã sửa ( `test_vae_dead_region.py` , `test_step3_crash_retry.py` ).
- **Tra ở:** ch13

### 8.1.10 Phân vùng tương đương / giá trị biên có dùng không?
- **Mức:** ★★
- **Ý trả lời chính:** Có, ví dụ số từ mỗi chương kẹp [200, 4000]: test 199/200/4000/4001; coverage alpha [0,05; 0,95]; ngưỡng VRAM 7,0 GB.
- **Tra ở:** `test_pipeline_ai_write.py`

### 8.1.11 CI gồm gì? Vì sao CI không chạy test GPU?
- **Mức:** ★★
- **Ý trả lời chính:** `ci.yml` : push/PR → job lint ( `ruff check` , `compileall` ) → job test ( `pytest -q tests/` ), ubuntu-latest, Python 3.11, cache pip, hủy run cũ. `release.yml` : tag `v*` → checkout submodule, test repo tổng + MediaComposer GPU- free, compile toolCaoTruyen, zip, GitHub Release. Runner miễn phí không có GPU; hướng: self-hosted GPU runner, matrix windows-latest.
- **Tra ở:** ch13 câu 4, 15

### 8.1.12 Chất lượng đầu ra AI đánh giá bằng gì? Có MOS/CLIP/FID không?
- **Mức:** ★★
- **Ý trả lời chính:** Đã đo: rò CJK 0/214.034; khung đen kiểm hồi quy; tổng thời lượng cảnh = WAV trên video mẫu; truy xuất KB 25/28. Chưa đo MOS, CLIP, FID vì thiếu tập ảnh chuẩn và người nghe; báo cáo không điền số giả định. Cách đo: MOS 1–5 người nghe ẩn danh; cosine CLIP giữa mặt nhân vật các cảnh.
- **Tra ở:** Q54, Bảng 5.6

### 8.1.13 Bao nhiêu test cho chatbot? Đánh giá truy xuất thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** 41 test tự động nhóm Trợ lý AI (báo cáo); bộ eval 36 câu (28 QA có `must_include` + 8 ngoài phạm vi) chạy bằng `scripts/eval_chatbot.py` . Kết quả chỉ phản ánh tầng truy xuất, không phải độ đúng câu trả lời của LLM.
- **Tra ở:** Báo cáo 4.8, 5.5

## 8.2 Hiệu năng và phần cứng

### 8.2.1 VRAM dùng bao nhiêu, bước nào nặng nhất?
- **Mức:** ★
- **Ý trả lời chính:** Bước 3 đỉnh ≈ 4,0 GB trên 6 GB; các bước khác gần mức nền trong cấu hình đo (Piper chạy CPU, ffmpeg không dùng GPU); worker kết thúc thì VRAM về gần nền.
- **Tra ở:** Bảng 5.5

### 8.2.2 Đo VRAM bằng cách nào?
- **Mức:** ★★
- **Ý trả lời chính:** Quan sát `nvidia-smi` / Task Manager trong lúc chạy, lấy đỉnh; Hình 5.2 là minh họa định tính. Nói thật nếu không có log tự động; hướng: ghi `torch.cuda.max_memory_allocated()` trong worker.
- **Tra ở:** Báo cáo 5.4.2

### 8.2.3 Thời gian xử lý mỗi bước? Sao không có số Bước 1 và Bước 4?
- **Mức:** ★
- **Ý trả lời chính:** Piper ≈ 2,7 phút/chương; Bước 3 ≈ 2,6 phút cho video 45 s. Bước 1 phụ thuộc engine LLM và độ dài, chưa tổng hợp; Bước 4 là stream copy, phụ thuộc tốc độ đĩa — chưa có tập đo ổn định, không suy diễn.
- **Tra ở:** Bảng 5.4

### 8.2.4 3,47× thời lượng nghĩa là một chương 10 phút mất bao lâu? Nghẽn ở đâu?
- **Mức:** ★★
- **Ý trả lời chính:** Ước ~35 phút nếu tuyến tính (chỉ là ước, chưa đo). Nghẽn chính ở sinh ảnh SD và upscale; LLM chia cảnh/prompt đứng thứ hai. Tối ưu: ít cảnh hơn (~40 s/cảnh), 8 bước Hyper-SD, cache nền, NVENC.
- **Tra ở:** ch11

### 8.2.5 Chạy trên máy không có GPU được không? Hai GPU thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** Không GPU: profile `cpu` fp32, chạy được nhưng sinh ảnh rất chậm, không thực tế. Chọn GPU: từ 01/10 danh sách lấy theo tên card NVIDIA từ `nvidia-smi` (chỉ số CUDA khác số "GPU 0/1" trong Task Manager vốn đếm cả card Intel); `cuda:N` không tồn tại thì về GPU mặc định — tránh SD lỡ chạy CPU chậm ~30 lần.
- **Tra ở:** `pipeline.py_gpu_count` , `main.py:442`

### 8.2.6 Process con crash trong driver GPU thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** Mã thoát native (0xC0000005…) được nhận diện trong `ma_thoat.py` ; Bước 3 tự chạy lại 1 lần (nếu không phải người dùng dừng), chương đã xong được giữ nhờ `batch_state.json` ; có test `test_step3_crash_retry.py` .
- **Tra ở:** `orchestrator/ma_thoat.py`

### 8.2.7 Hết VRAM (OOM) giữa chừng thì xử lý sao?
- **Mức:** ★★
- **Ý trả lời chính:** Pass A gặp OOM thì `release()` (gc + synchronize + `empty_cache` ) rồi thử lại 1 lần; vẫn lỗi thì đánh dấu failed và sang chương kế, không dừng cả batch.
- **Tra ở:** `batch_video_runner.py:271`

## 8.3 Bảo mật và an toàn dữ liệu

### 8.3.1 API không xác thực có nguy hiểm không?
- **Mức:** ★★★
- **Ý trả lời chính:** Bind `127.0.0.1` nên máy khác trong mạng không kết nối được; CORS chỉ 2 origin cổng 8100. Chương trình khác trên cùng máy vẫn gọi được (CORS không phải xác thực). Hướng: sinh token ngẫu nhiên lúc khởi động, cửa sổ webview gửi kèm.
- **Tra ở:** Q22, ch13 câu 16

### 8.3.2 Path traversal là gì? Chống ở đâu?
- **Mức:** ★★
- **Ý trả lời chính:** Dùng `../` để đọc/ghi ngoài thư mục cho phép. `resolve_path_within_directory` : `realpath` + `commonpath` so theo thành phần; `_select_files` chỉ nhận basename có trong danh sách quét; `slugify` loại `.` , `/` , `\` ; `_kb_path` dùng regex tên tệp + cấm `..` .
- **Tra ở:** ch13 câu 11, `main.py` `_kb_path`

### 8.3.3 Command injection khi spawn tiến trình?
- **Mức:** ★★
- **Ý trả lời chính:** Lệnh truyền dạng list cho `Popen` , không qua shell, nên tham số người dùng không được thông dịch như lệnh.
- **Tra ở:** `process_manager.py:22`

### 8.3.4 API key bảo vệ ra sao?
- **Mức:** ★★
- **Ý trả lời chính:** Lưu trong `configs/global_config.json` ; tệp này cùng `.env` , `cookies.json` , `api_keys.json` , `*.key` , `*.pem` nằm trong `.gitignore` . Hạn chế: key truyền cho subprocess qua tham số dòng lệnh nên lộ trong danh sách tiến trình; installer chưa loại `api_keys.json` ; còn key giả `sk-` `gemini-...` trong 5 tệp submodule (key cục bộ của proxy).
- **Tra ở:** ch13 câu 12, ch00 §8

### 8.3.5 Proxy Gemini-API có vấn đề gì?
- **Mức:** ★★
- **Ý trả lời chính:** Dùng cookie (có thể vi phạm điều khoản), bind `0.0.0.0` , CORS `*` , nhánh JWT không kiểm chữ ký. Chỉ là tùy chọn lúc phát triển; demo dùng Ollama, tắt proxy.
- **Tra ở:** ch00 §8

### 8.3.6 Xóa truyện có an toàn không? (tính năng mới)
- **Mức:** ★★
- **Ý trả lời chính:** Backend từ chối xóa/sửa khi truyện đang chạy bước hoặc chuỗi (400); xóa thư mục + bản ghi DB, không hoàn tác; còn tệp bị khóa thì báo 500. Dọn dữ liệu tạm có chế độ xem trước và bảo vệ `contexts` , `character_loras` .
- **Tra ở:** `main.py:288-341`

### 8.3.7 Ghi `story.json` có an toàn khi mất điện?
- **Mức:** ★★
- **Ý trả lời chính:** Chưa: ghi đè trực tiếp, mất điện đúng lúc có thể hỏng tệp. Sửa: ghi tệp tạm + `os.replace` (mẫu 7.12). Dữ liệu nặng không mất; SQLite dựng lại được.
- **Tra ở:** ch00 §8

### 8.3.8 Log có xoay vòng không?
- **Mức:** ★★
- **Ý trả lời chính:** Chưa có log rotation; hướng: `RotatingFileHandler` .
- **Tra ở:** ch13 câu 15

## 8.4 Cài đặt và triển khai

### 8.4.1 Người dùng không biết lập trình cài thế nào?
- **Mức:** ★
- **Ý trả lời chính:** Installer Inno Setup (web installer, không cần Admin) hoặc `git clone` + nháy đúp `run.bat` . Thiếu venv thì `setup.bat` : đồng bộ submodule, tải Python 3.11.9, tạo 2 venv, chọn PyTorch theo GPU (RTX 50 → cu128, NVIDIA khác → cu124, không có → CPU). Mở app thì `model_preflight` tải nốt model.
- **Tra ở:** Q21, ch13 câu 5

### 8.4.2 Sao không dùng Docker?
- **Mức:** ★★
- **Ý trả lời chính:** Người dùng đích là Windows cá nhân; Docker + GPU trên Windows cần WSL2 + NVIDIA Container Toolkit, image PyTorch CUDA nặng nhiều GB, và app cần cửa sổ WebView2. venv + `.bat` đơn giản hơn.
- **Tra ở:** ch13 câu 6

### 8.4.3 Vì sao luôn gọi `python -` `m ...` chứ không chạy `.exe` trong venv?
- **Mức:** ★★
- **Ý trả lời chính:** Tệp `.exe` sinh ra trong venv ghi cứng đường dẫn, dời thư mục là hỏng; `python -m` luôn chạy đúng.
- **Tra ở:** ch00 §5.2

### 8.4.4 `setup.bat` tự sửa `onnxruntime-gpu` là gì?
- **Mức:** ★★
- **Ý trả lời chính:** Mỗi lần `pip` cài gói khác có thể kéo bản `onnxruntime` CPU ghi đè bản GPU (rembg, Piper dùng ONNX); setup kiểm và cài lại bản GPU. (Commit 01/10.)
- **Tra ở:** `setup.bat` , commit `066b6c0`

### 8.4.5 Clone về máy mới có lỗi gì không?
- **Mức:** ★★
- **Ý trả lời chính:** Đường dẫn dài > 200 ký tự và gitlink lồng nhau từng làm `git clone --` `recursive` lỗi; phải test clone thật trước khi phát hành.
- **Tra ở:** —

### 8.4.6 Cập nhật phiên bản thế nào?
- **Mức:** ★
- **Ý trả lời chính:** `CAP-NHAT.bat` kéo mã mới từ nhánh main kèm submodule; release theo tag `v*` .
- **Tra ở:** Báo cáo 4.9
