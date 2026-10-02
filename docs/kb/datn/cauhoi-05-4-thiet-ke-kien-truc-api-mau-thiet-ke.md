# 4. Thiết kế kiến trúc, API, mẫu thiết kế

Câu trọng tâm là "vì sao đa tiến trình". Trả lời bằng ba lý do theo thứ tự: VRAM chỉ được trả hết khi process thoát, cô lập lỗi và xung đột thư viện, mỗi submodule một venv.

## 4.1 Mô tả kiến trúc tổng thể.
- **Mức:** ★
- **Ý trả lời chính:** Giao diện web thuần trong WebView2 ↔ REST/SSE ↔ Orchestrator FastAPI `127.0.0.1:8100` (NovelPipeline, ProcessManager, AutoRunManager, StorageManager, ChatManager) ↔ `Popen` stdout=PIPE ↔ worker CLI ( `adapter_cli.py` , `adapter_tts_cli.py` , `adapter_video_cli.py` , `adapter_autosub_cli.py` ) → Ollama/GPU. Lưu trữ: `story.json` + SQLite + tệp media.
- **Tra ở:** ch00 §4.4, báo cáo Hình 3.7

## 4.2 Slide nói 3 tầng, báo cáo nói 4 tầng — cái nào đúng?
- **Mức:** ★★★
- **Ý trả lời chính:** Cùng một kiến trúc, khác cách cắt: 3 tầng thực thi (giao diện – điều phối – worker); báo cáo tách thêm tầng lưu trữ (story.json, SQLite, workspace) thành tầng thứ 4 vì nó đóng vai checkpoint. Chuẩn bị nói thống nhất một cách.
- **Tra ở:** Báo cáo 3.3

## 4.3 "Modular monolith + tiến trình con" là gì? Sao không microservices?
- **Mức:** ★★
- **Ý trả lời chính:** Một ứng dụng triển khai chung, chia module rõ ranh giới; việc nặng tách thành process. Microservices cần nhiều service chạy thường trực, mạng, điều phối container — thừa cho một người trên một máy, và service thường trực lại giữ VRAM.
- **Tra ở:** Bảng 3.20

## 4.4 Vì sao không gọi thẳng hàm Python trong một process? Đánh đổi là gì?
- **Mức:** ★★★
- **Ý trả lời chính:** (1) PyTorch giữ cache CUDA, `empty_cache` không trả hết; process thoát thì driver thu hồi toàn bộ; orchestrator cố ý không import torch. (2) torch, onnxruntime, OpenCV, PaddleOCR xung đột DLL/OpenMP; worker chết chỉ trả exit code. (3) venv riêng. Đánh đổi: mỗi bước tốn thời gian nạp lại model.
- **Tra ở:** Q9, ch01 câu 1

## 4.5 Kiến trúc này có phải MVC không?
- **Mức:** ★★
- **Ý trả lời chính:** Không đúng MVC kinh điển. Gần với client–server phân tầng: View là SPA, "controller" là route FastAPI + NovelPipeline (facade), "model" là StorageManager + tệp/SQLite; còn thêm tầng worker ngoài process.
- **Tra ở:** Báo cáo 3.3

## 4.6 Em dùng những design pattern nào? Chỉ vào code.
- **Mức:** ★★
- **Ý trả lời chính:** Facade: `NovelPipeline` . Adapter: các `adapter_*.py` , `BaseTTSEngine` . Strategy + Registry: `sources/registry.py` , `TRANSLATOR_ENGINES` . Singleton: `StorytellingPipeline` , model Whisper. Producer–consumer/Observer: queue log + callback `on_completed` . Dependency injection: `render_plan` nhận hàm render/matter/unify. State machine: vòng đời truyện.
- **Tra ở:** Q18

## 4.7 Facade là gì? `NovelPipeline` che cái gì?
- **Mức:** ★★
- **Ý trả lời chính:** Một giao diện đơn giản che hệ con phức tạp. Route chỉ gọi `start_step_X` ; NovelPipeline dựng lệnh, chọn venv, đặt env, đăng ký process, cập nhật `story.json` trong callback.
- **Tra ở:** `orchestrator/pipeline.py`

## 4.8 Nguyên lý SOLID thể hiện ở đâu?
- **Mức:** ★★
- **Ý trả lời chính:** OCP: thêm engine TTS/nguồn truyện bằng class mới, không sửa pipeline. SRP: ProcessManager chỉ quản lý process, StorageManager chỉ lưu trữ. DIP: Studio phụ thuộc interface `Matter` /hàm được tiêm. Thừa nhận: `main.py` (~1.200 dòng) và `app.js` (~2.100 dòng) còn to, vi phạm SRP.
- **Tra ở:** ch00 §6

## 4.9 API chính gồm những endpoint nào?
- **Mức:** ★
- **Ý trả lời chính:** `POST /api/pipeline/step1..5` , `POST` `/api/pipeline/auto-run` , `GET` `/api/pipeline/logs/{task_key}` (SSE), `GET` `/api/pipeline/status/{task_key}` , `POST /api/pipeline/stop-task` , `POST/GET /api/stories` , `GET` `/api/stats` , `POST /api/maintenance/cleanup-tasks
- **Tra ở:** rebuild-db `, nhóm` /api/chat* `,` /api/agent/query`.

## 4.10 Vì sao API chạy bước trả về ngay `task_key` thay vì chờ xong?
- **Mức:** ★★
- **Ý trả lời chính:** Bước chạy hàng phút–giờ, HTTP timeout và không quan sát được. Mẫu "long- running job": trả khóa tác vụ, client theo dõi qua SSE và hỏi `status` . `task_key =` `<slug>_stepN` cũng là khóa chống chạy trùng.
- **Tra ở:** ch01, ch02

## 4.11 Sao không dùng hàng đợi như Celery/Redis/RabbitMQ?
- **Mức:** ★★
- **Ý trả lời chính:** Một người, một máy, mỗi bước là một process; `subprocess` + `queue.Queue` + thread đủ dùng, không phải cài thêm dịch vụ. Hạn chế: chưa có hàng đợi GPU toàn cục — hai truyện chạy Bước 3 cùng lúc có thể OOM; hướng sửa là semaphore/hàng đợi job.
- **Tra ở:** ch01 câu 17

## 4.12 Giữa các bước truyền dữ liệu bằng "hợp đồng" gì?
- **Mức:** ★★
- **Ý trả lời chính:** UI→API: JSON pydantic. Worker→Orchestrator: JSON Lines + exit code. Bước 1→2: tệp `.md` có `" - [VI]` `"` . Bước 2→3: cặp `<stem>.md` + `<stem>.wav` . Pass A→B: `state.json` . Bước 3→4: `video/*.mp4` trừ `TongHop_*` . Chatbot: NDJSON.
- **Tra ở:** ch00 §5.5

## 4.13 Cấu hình được thiết kế mấy lớp? Thứ tự ưu tiên?
- **Mức:** ★★
- **Ý trả lời chính:** `configs/global_config.json` (mặc định dùng chung, pipeline đọc, qua `/api/config` ) và `configs/ui_settings.json` (snapshot form, chỉ frontend). Mở app: HTML → global → ui_settings, cái sau thắng. Bước 3 còn ghi `sd_*` xuống `config.toml` của MediaComposer.
- **Tra ở:** ch02 câu 11

## 4.14 Thiết kế xử lý lỗi theo nguyên tắc nào?
- **Mức:** ★★
- **Ý trả lời chính:** Lỗi worker → exit code ≠ 0 → callback đặt *_FAILED, không sập server. Chuỗi fallback có chủ đích: LLM chia cảnh hỏng → `md_parser` ; Studio hỏng → Classic; Real-ESRGAN đen → PIL; NVENC lỗi → libx264; Gemini chặn → Ollama. Nhưng lỗi thật không bị che: tất cả prompt hỏng → dừng, không sinh ảnh rác.
- **Tra ở:** ch06, ch07, ch11

## 4.15 Thiết kế quản lý tài nguyên GPU ra sao?
- **Mức:** ★★
- **Ý trả lời chính:** Phân mức none/medium/heavy ( `get_gpu_weight` ); heavy thì chatbot chỉ tra cứu 0-VRAM; UI gọi `/api/chat/unload` trước mỗi bước; Ollama `keep_alive=0` trước khi nạp SD; batch 2-pass tách SD và ESRGAN; process thoát trả VRAM.
- **Tra ở:** Bảng 3.20, ch12

## 4.16 Muốn thêm một bước mới vào pipeline thì sửa những đâu?
- **Mức:** ★★
- **Ý trả lời chính:** Viết adapter CLI mới in JSON Lines; thêm schema pydantic + route `POST` `/api/pipeline/stepN` trong `main.py` ; thêm `start_step_N` + callback trong `pipeline.py` ; nếu vào chuỗi thì thêm vào `CHAIN_STEPS` của `auto_run.py` ; thêm tab/form + case event trong `app.js` .
- **Tra ở:** ch01, ch02

## 4.17 Mở rộng cho nhiều người dùng/cloud cần đổi gì?
- **Mức:** ★★
- **Ý trả lời chính:** Thêm xác thực + phân quyền, hàng đợi GPU (Celery/Redis), lưu trạng thái auto- run vào DB thay vì RAM, chuyển SQLite sang PostgreSQL, lưu media lên object storage, worker thành container có GPU.
- **Tra ở:** ch00 §4.2

## 4.18 Vì sao làm ứng dụng desktop mà không phải web app?
- **Mức:** ★
- **Ý trả lời chính:** Mô hình chạy trên GPU của chính người dùng, dữ liệu không rời máy; nhưng giao diện vẫn là web nên phát triển nhanh và có thể mở bằng trình duyệt khi thiếu WebView2.
- **Tra ở:** `desktop.py`

## 4.19 Auto-run lưu trạng thái ở đâu? Restart server thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** Trong RAM ( `AutoRunManager` , thread daemon, poll 1 s, hủy bằng `threading.Event` ). Restart là mất chuỗi, dữ liệu các bước đã xong vẫn còn; docstring ghi "chấp nhận ở v1".
- **Tra ở:** `auto_run.py`

## 4.20 Chạy auto-run thì video tổng bị ghép hai lần — đúng không?
- **Mức:** ★★★
- **Ý trả lời chính:** Đúng: step3 thành công đã tự merge trong `_finalize_video_task` , chuỗi lại chạy step5 nên có 2 file `TongHop_*` gần giống nhau. Không ghép lồng nhờ loại `TongHop_*` , nhưng tốn thời gian/dung lượng. Sửa: bỏ merge trong finalize khi chạy từ chuỗi hoặc bỏ step5 khỏi chuỗi.
- **Tra ở:** `pipeline.py:99-133` , `auto_run.py:13-18`

## 4.21 Callback `on_completed` chạy trước hay sau khi báo kết thúc cho UI? Vì sao?
- **Mức:** ★★
- **Ý trả lời chính:** Trước khi đặt sentinel. Trong lúc merge (có thể vài phút), task vẫn tính là đang chạy nhờ `finalizing_tasks` , UI không chèn được lần chạy mới.
- **Tra ở:** `process_manager.py:66-119`

## 4.22 Sơ đồ triển khai gồm gì?
- **Mức:** ★
- **Ý trả lời chính:** Một nút Windows: WebView/trình duyệt → HTTP/SSE → tiến trình điều phối → subprocess/JSON → tiến trình AI; CPU/RAM lo điều phối và FFmpeg; LLM, TTS, Diffusion dùng GPU, nạp/nhả theo bước. Ollama chạy dịch vụ riêng cổng 11434.
- **Tra ở:** Báo cáo Hình 3.8
