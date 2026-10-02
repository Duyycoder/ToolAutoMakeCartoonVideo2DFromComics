# Chương 01. Kiến trúc tổng thể & Orchestrator (FastAPI, state machine, subprocess, JSON progress, VRAM)

- Mục tiêu chương. Sau chương này bạn phải trả lời trôi chảy được: hệ thống gồm những khối nào, khối nào gọi khối nào, dữ liệu đi đâu, vì sao lại tách thành nhiều tiến trình (process) thay vì một chương trình Python duy nhất, và "bộ não điều phối" (orchestrator) làm việc cụ thể ra sao ở mức file/hàm/tham số.

- Nguồn đã đọc để viết chương: `orchestrator/main.py` , `pipeline.py` , `process_manager.py` , `auto_run.py` , `config.py` , `storage.py` , `db.py` , `cleanup.py` , `desktop.py` , `video_merger.py` , `model_preflight.py` , `ollama_manager.py` , `mediacomposer_config.py` , `llm.py` (hàm `resolve_llm` , `unload_ollama` ), `chatbot.py` (hàm `get_gpu_weight` ), `run.bat` , `setup.bat` , `configs/config.example.json` , `configs/global_config.json` (chỉ đọc tên khoá, không đọc key), các adapter `AIVoice/adapter_tts_cli.py` , `AIVoice/apps/MediaComposer/adapter_video_cli.py` , `toolCaoTruyen/adapter_cli.py` , `AIVoice/apps/MediaComposer/app/services/storytelling/batch_video_runner.py` , `webui/app.js` (phần SSE). Số dòng trích dẫn là theo code tại commit `f219bd9` .

## 1. Vai trò trong hệ thống

### 1.1 Bài toán tổng thể trong một câu

Người dùng đưa vào một truyện chữ (cào từ web, lấy từ thư mục trên máy, hoặc để LLM tự sáng tác), hệ thống trả ra một video hoạt hình 2D có lồng tiếng tiếng Việt. Tất cả chạy cục bộ trên máy Windows có GPU NVIDIA.

Quy trình chia thành các bước. Chú ý: số bước trên giao diện khác số nội bộ trong code — hội đồng hay bắt lỗi chỗ này, bạn phải nắm rõ:

- **Trên UI:** Bước 1 · **Tên nội bộ ( `task_key` hậu tố):** `step1` · **Việc làm:** Cào truyện + dịch (hoặc nạp thư mục cục bộ, hoặc AI sáng tác) · **Ai thực thi:** subprocess `toolCaoTruyen/adapter_cli.py` (crawl, translate); thread cho `local` / `ai_write`
- **Trên UI:** Bước 2 · **Tên nội bộ ( `task_key` hậu tố):** `step2` · **Việc làm:** TTS: văn bản → giọng đọc `.wav` · **Ai thực thi:** subprocess `AIVoice/adapter_tts_cli.py`
- **Trên UI:** Bước 3 · **Tên nội bộ ( `task_key` hậu tố):** `step3` · **Việc làm:** Dựng hoạt hình: chia cảnh, LLM viết prompt, Stable Diffusion sinh ảnh, ghép video · **Ai thực thi:** subprocess `AIVoice/apps/MediaComposer/adapter_video_cli.py`
- **Trên UI:** Bước 4 · **Tên nội bộ ( `task_key` hậu tố):** `step5` · **Việc làm:** Ghép các video chương thành một file `TongHop_*.mp4` · **Ai thực thi:** thread trong orchestrator, gọi FFmpeg
- **Trên UI:** Tab "Autosub" (công cụ rời) · **Tên nội bộ ( `task_key` hậu tố):** `step4` · **Việc làm:** Phụ đề tự động/lồng tiếng cho video bất kỳ · **Ai thực thi:** subprocess `adapter_autosub_cli.py`

Bằng chứng: `orchestrator/auto_run.py:13-20` định nghĩa `CHAIN_STEPS = [(1,"Cào&Dịch"), (2,"Sinh Giọng"), (3,"Dựng` `Hoạt Hình"), (5,"Ghép Video")]` và `DISPLAY_NO = {1: 1, 2: 2, 3: 3, 5: 4}` ; docstring đầu file ghi rõ "tab autosub ( `step4` ) là công cụ rời, KHÔNG nằm trong chuỗi".

### 1.2 Orchestrator đứng ở đâu

Orchestrator là một web server FastAPI chạy tại `127.0.0.1:8100` . Nó không tự làm AI (không `import torch` — đã kiểm tra: không có dòng `import torch` nào trong `orchestrator/*.py` , và `model_preflight.py:11-12` ghi rõ "orchestrator cố ý không import torch/huggingface_hub"). Việc của nó:

- 1. Phục vụ giao diện web ( `webui/` ) và API REST. 2. Nhận lệnh "chạy bước N", dựng dòng lệnh (command line) và spawn tiến trình con dùng đúng virtualenv của từng submodule. 3. Đọc stdout của tiến trình con từng dòng, đẩy về trình duyệt theo thời gian thực bằng SSE.

4. Khi tiến trình con kết thúc, dựa trên exit code để cập nhật trạng thái truyện ( `story.json` + SQLite). 5. Quản lý tài nguyên: chống chạy trùng, dừng cả cây tiến trình, nhả VRAM, tự tải model thiếu, tự bật Ollama.

### 1.3 Sơ đồ kiến trúc

### 1.4 Input / Output của orchestrator

Input: request JSON từ UI (các schema pydantic `Step1Schema` … `Step5Schema` , `AutoRunSchema` trong `main.py:104-212` , `525-529` ), cấu hình chung `configs/global_config.json` . Output: thư mục dữ liệu truyện, luồng log SSE, trạng thái trong `story.json` và `app.db` .

Cấu trúc thư mục dữ liệu (tạo bởi `StorageManager.__init__storage.py:51-63` và `init_story_workspacestorage.py:70-119` ):

```
storage/                    <- global_config["storage_dir"], mặc định "storage"
├── app.db                  <- SQLite (metadata nhẹ)
├── tasks/                  <- thư mục làm việc của MediaComposer (MC_STORAGE_TASKS)
└── truyen/
    └── <slug>/             <- slugify("Đắc Kỷ Trụ Vương") = "dac_ky_tru_vuong"
        ├── story.json      <- trạng thái + metadata truyện
        ├── raw/            <- chương .md: bản gốc, rồi bản dịch "... - [VI] ....md", .wav cạnh .md, _original.zip
        ├── translated/     <- KHÔNG được tạo trong luồng hiện tại; code chỉ kiểm tra "nếu có" để tương thích
        └── video/          <- mp4 từng chương + TongHop_YYYYmmdd_HHMMSS.mp4
```

Lưu ý quan trọng:

Bước dịch ghi ngay vào `raw/` : lệnh translate có `--input-dir raw_dir--output-dir raw_dir` ( `pipeline.py:172-177` ). Adapter cào nén bản gốc vào `raw/_original.zip` ( `toolCaoTruyen/adapter_cli.py:50-58` ), adapter dịch ghi file mới có dấu `" - [VI] "` trong tên rồi xoá file gốc đã dịch xong (event `cleanup_file` , `adapter_cli.py:374-379` ). `init_story_workspace` chỉ tạo `raw/` và `video/` ( `storage.py:78-84` ); `translated/` chỉ còn được kiểm tra ở `pipeline.py:400-405` , `517-523` , `storage.py:173` , `main.py:358` (tương thích dữ liệu cũ).

- File `.wav` nằm cạnh file `.md` (docstring `storage.py:198-204` ; TTS dùng `--output-dir` bằng chính `--input-dir` , `pipeline.py:430-431` ), không có thư mục `audio/` riêng.

### 1.5 Bản đồ module của orchestrator

- **File:** `main.py` · **Dòng:** 1185 · **Vai trò:** FastAPI app: schema, endpoint, singleton, mount webui
- **File:** `pipeline.py` · **Dòng:** 797 · **Vai trò:** `NovelPipeline` : dựng lệnh từng bước, callback cập nhật trạng thái
- **File:** `process_manager.py` · **Dòng:** 305 · **Vai trò:** `ProcessManager` : spawn/kill subprocess, log queue, SSE generator
- **File:** `auto_run.py` · **Dòng:** 165 · **Vai trò:** `AutoRunManager` : chuỗi tự động 1→4 chạy nền
- **File:** `storage.py` · **Dòng:** 289 · **Vai trò:** `StorageManager` , `slugify` , dọn dẹp `tasks/`
- **File:** `db.py` · **Dòng:** 203 · **Vai trò:** Lớp SQLite: schema `stories/chapters/jobs`
- **File:** `config.py` · **Dòng:** 228 · **Vai trò:** Đọc/ghi `global_config.json` , `ui_settings.json` , giá trị mặc định
- **File:** `desktop.py` · **Dòng:** 230 · **Vai trò:** Launcher: uvicorn trong thread + cửa sổ WebView2 + dọn tiến trình khi đóng
- **File:** `model_preflight.py` · **Dòng:** 238 · **Vai trò:** Tự kiểm tra/tải model thiếu khi mở app
- **File:** `ollama_manager.py` · **Dòng:** 262 · **Vai trò:** Tự bật Ollama, tự `pull` model qua HTTP
- **File:** `mediacomposer_config.py` · **Dòng:** 145 · **Vai trò:** Ghi tham số Stable Diffusion xuống `config.toml` của MediaComposer
- **File:** `video_merger.py` · **Dòng:** 96 · **Vai trò:** Ghép mp4 bằng FFmpeg concat
- **File:** `cleanup.py` · **Dòng:** 51 · **Vai trò:** CLI dọn dẹp + rebuild DB
- **File:** `llm.py` , `chatbot.py` , `kb_index.py` , `story_writer.py` , `chapter_naming.py` · **Dòng:** — · **Vai trò:** LLM client, trợ lý RAG, sáng tác, chuẩn hoá tên chương (các chương khác)

## 2. Nền tảng lý thuyết từ gốc

### 2.1 Mô hình client–server và HTTP

Trực giác. Giống quán ăn: khách (client) gọi món bằng phiếu (request), bếp (server) làm rồi trả đĩa (response). Khách không cần biết bếp nấu thế nào, chỉ cần biết "ngôn ngữ phiếu gọi món".

Cơ chế. HTTP là giao thức văn bản chạy trên TCP. Một request gồm:

- Method: `GET` (đọc), `POST` (tạo/kích hoạt hành động), `DELETE` (xoá)… Path: `/api/pipeline/step3` Header: ví dụ `Content-Type: application/json` Body: JSON, ví dụ `{"story_name": "Tây Du Ký", "style": "thuy_mac"}`

Response có status code: `200` OK, `400` yêu cầu sai (vd đang chạy rồi), `404` không tìm thấy, `409` xung đột (truyện đã tồn tại), `429` quá nhiều request, `500` lỗi server, `503` dịch vụ tắt, `504` quá thời gian. Code dự án dùng đúng các mã này, ví dụ `main.py:335` trả `409` khi tạo truyện trùng, `main.py:822` trả `429` khi chatbot đang trả lời câu trước, `main.py:648` trả `504` khi tải video quá 15 phút.

REST là phong cách thiết kế API: mỗi "tài nguyên" có URL riêng ( `/api/stories/{story_name}` ), dùng method để diễn tả hành động, server không giữ trạng thái phiên giữa các request (stateless) — trạng thái nằm ở tài nguyên (file/DB).

Localhost & port. `127.0.0.1` là địa chỉ "chính máy này"; server chỉ lắng nghe trên loopback nên máy khác trong mạng không truy cập được ( `desktop.py:18-19` : `HOST = "127.0.0.1"` , `PORT = 8100` ). Port giống "số phòng" trong một toà nhà IP: 8100 cho

orchestrator, 11434 cho Ollama, 7860 cho Gemini proxy.

### 2.2 Process, thread và GIL

Process (tiến trình): một chương trình đang chạy, có không gian bộ nhớ riêng, handle file riêng, và (với GPU) CUDA context riêng. Hai process không đọc được bộ nhớ của nhau; giao tiếp phải qua kênh: pipe, socket, file. Thread (luồng): nhiều luồng thực thi chung một process, chung bộ nhớ. Rẻ hơn process nhưng lỗi ở một luồng (vd crash thư viện C) kéo sập cả process. GIL (Global Interpreter Lock) của CPython: tại một thời điểm chỉ một thread chạy bytecode Python. Nhưng khi thread chờ I/O (đọc pipe, đợi mạng, `queue.get` ) nó nhả GIL, nên thread vẫn rất hợp cho việc chờ — đúng kiểu việc orchestrator làm (đọc stdout của con, poll trạng thái). Việc nặng CPU/GPU thì giao cho process con.

### 2.3 Đồng thời: blocking, event loop, async/await, ASGI, uvicorn

Vấn đề. Server phải phục vụ nhiều kết nối cùng lúc: một tab đang nghe log SSE của Bước 3 (kéo dài hàng giờ), đồng thời UI vẫn gọi `/api/stories` , `/api/system/busy` … Nếu mỗi request "chặn" (block) server cho tới khi xong thì UI treo.

Event loop (vòng lặp sự kiện). Tưởng tượng một người phục vụ duy nhất nhưng không bao giờ đứng chờ: gọi món cho bàn 1, trong lúc bếp nấu thì sang bàn 2, bếp báo xong thì quay lại bàn 1. Trong Python, `async def` định nghĩa coroutine; `await x` nghĩa là "tôi đang chờ x, event loop cứ đi làm việc khác". Event loop (asyncio) giữ danh sách các coroutine và đánh thức coroutine nào có dữ liệu sẵn sàng.

ASGI (Asynchronous Server Gateway Interface) là chuẩn giao tiếp giữa web server và web framework Python kiểu async (kế nhiệm WSGI đồng bộ). uvicorn là ASGI server: mở socket, nhận byte HTTP, parse, gọi vào app ASGI (FastAPI), rồi gửi response. FastAPI xây trên Starlette (lõi ASGI) + pydantic (kiểm tra dữ liệu).

Chi tiết quan trọng để trả lời hội đồng: trong FastAPI,

endpoint `async def` chạy trực tiếp trên event loop → tuyệt đối không được gọi hàm chặn lâu bên trong (nếu không cả server đứng). endpoint `def` thường (đồng bộ) được FastAPI tự đẩy vào threadpool (của AnyIO), nên có thể gọi hàm chặn mà không làm đứng event loop.

Dự án dùng đúng nguyên tắc này:

Phần lớn endpoint pipeline là `def` (vd `run_step1main.py:436` , `stream_logsmain.py:510` ) → chạy trong threadpool; `StreamingResponse` với generator đồng bộ `get_logs_generator` cũng được Starlette lặp trong threadpool, nên `q.get(timeout=1.0)` chặn không ảnh hưởng event loop. Endpoint chat là `async def` ( `post_chatmain.py:815` ), và với hàm chặn lâu ( `ollama_manager.ensure_ready` — có thể chờ Ollama khởi động tới 30s rồi pull model) thì bọc bằng `await asyncio.to_thread(...)` ( `main.py:985-992` ) — đẩy sang thread để event loop rảnh. Nói cho trung thực: một số thao tác đồng bộ ngắn vẫn chạy thẳng trên event loop trong `post_chat` (đọc `global_config.json` bằng `load_global_config()` , `chat_mgr.get_gpu_weight()` , `select_kb` , `lookup_only` ); chúng chỉ mất vài ms nên chấp nhận được, nhưng về nguyên tắc cũng chặn loop trong khoảng đó. Con số nên nhớ: threadpool mặc định của AnyIO (mà Starlette dùng) giới hạn 40 luồng đồng thời — đây là trần cho số request `def` /generator đồng bộ chạy cùng lúc.

### 2.4 Pydantic — kiểm tra dữ liệu bằng type hint

Pydantic biến khai báo class có type hint thành bộ kiểm tra + chuyển đổi dữ liệu. FastAPI đọc type của tham số endpoint: nếu là `BaseModel` , nó parse body JSON, kiểm tra kiểu, điền giá trị mặc định, và tự trả `422` nếu sai. Ví dụ `Step3Schema` ( `main.py:147-` `165` ) đặt mặc định `style="thuy_mac"` , `checkpoint="anything-v5"` , `bgm_volume=0.15` , `enable_upscale=True` , `render_mode="auto"` .

Hai chi tiết pydantic v2 trong code:

`GlobalConfigSchema` dùng `model_config = ConfigDict(extra="allow")` ( `main.py:74` ) để giữ lại các khoá cấu hình chưa khai báo — cấu hình phát triển liên tục mà không phải sửa schema. `ChatModelSchema` dùng `ConfigDict(protected_namespaces=())` ( `main.py:98` ). Bối cảnh: pydantic v2 dành tiền tố `model_` cho các method nội bộ ( `model_dump` , `model_validate` …) và cảnh báo khi một trường có tên bắt đầu bằng `model_` . Trường ở đây tên đúng là `model` (không có dấu `_` phía sau) nên thực tế không bị cảnh báo; dòng cấu hình này là biện pháp phòng ngừa (vô hại). Nếu hội đồng hỏi, trả lời đúng như vậy thay vì nói "không tắt thì lỗi".

Code gọi `body.dict()` (vd `main.py:485` ) — đây là API kiểu pydantic v1, trong v2 vẫn chạy nhưng bị đánh dấu deprecated (tên mới là `model_dump()` ).

### 2.5 Server đẩy dữ liệu về client: polling vs SSE vs WebSocket

HTTP gốc là "hỏi–đáp": client hỏi thì server mới trả. Muốn server chủ động đẩy log theo thời gian thực có 3 cách:

- **Cách:** Polling · **Cơ chế:** Client hỏi lại mỗi N giây · **Ưu:** Đơn giản · **Nhược:** Trễ, tốn request
- **Cách:** SSE (Server- Sent Events) · **Cơ chế:** Một response HTTP không đóng, server ghi dần từng "event" dạng văn bản, content-type `text/event-stream` · **Ưu:** Một chiều server→client, chạy trên HTTP thường, trình duyệt có sẵn `EventSource` tự reconnect · **Nhược:** Chỉ một chiều, chỉ văn bản
- **Cách:** WebSocket · **Cơ chế:** Nâng cấp kết nối thành kênh 2 chiều · **Ưu:** Hai chiều, nhị phân · **Nhược:** Phức tạp hơn, cần tự lo reconnect

Log tiến trình chỉ cần một chiều → SSE là vừa đủ. Định dạng SSE: mỗi event là một hoặc nhiều dòng `data:...` và kết thúc bằng một dòng trống:

```
data: {"event": "tts_file_start", "index": 1, "total": 12, "file": "Chuong 001 - [VI] ....md"}
```

```
data: [PING]
```

Bổ sung nền tảng (hay bị hỏi): chuẩn SSE còn có các trường `event:` (tên loại sự kiện), `id:` (trình duyệt gửi lại qua header `Last-Event-ID` khi reconnect), `retry:` (thời gian chờ reconnect, ms), và dòng bắt đầu bằng `:` là comment — cách keep-alive "chuẩn". Dự án chỉ dùng trường `data:` ; keep-alive được gửi dưới dạng `data: [PING]` và UI tự bỏ qua ( `webui/app.js` , `streamLogs` : `if (rawLine==="[PING]") return;` ). Dự án không dùng `id:` nên khi reconnect server không "phát lại" log cũ — kết nối mới chỉ nhận phần log còn trong hàng đợi.

### 2.6 Pipe, stdout, buffering và JSON Lines

Khi process A spawn process B với `stdout=PIPE` , hệ điều hành tạo một ống (pipe): B ghi vào đầu ghi, A đọc ở đầu đọc. Hai điểm hay gây lỗi:

1. Buffering. Python khi ghi vào pipe (không phải terminal) sẽ gom output vào bộ đệm (mặc định `io.DEFAULT_BUFFER_SIZE` = 8192 byte) mới xả. Kết quả: log đến "cục" và rất trễ. Vấn đề nằm ở phía ghi (process con), nên cách chữa chính là bên con gọi `sys.stdout.flush()` sau mỗi dòng (các adapter làm vậy, xem 4.5); cách tương đương là chạy con với `python -u` hoặc biến môi trường `PYTHONUNBUFFERED=1` (dự án không dùng hai cách này). Bên cha mở pipe ở text mode với `bufsize=1` (line-buffered) và đọc bằng `readline()` — `readline()` trả về ngay khi có đủ một dòng, nên phía đọc không gây trễ. 2. EOF. Bên đọc chỉ nhận EOF (hết dữ liệu) khi mọi process đang giữ đầu ghi đều đóng. Nếu B đẻ ra C (vd ffmpeg) và C kế thừa handle stdout, thì B chết rồi nhưng C còn sống → A không bao giờ thấy EOF → treo. Đây chính là lý do phải "kill cả cây tiến trình" (mục 4.4.4).

JSON Lines (NDJSON): mỗi dòng là một object JSON độc lập. Ưu điểm: đọc theo dòng là đủ tách message (không cần parser dòng chảy), một dòng hỏng không làm hỏng dòng khác, và dòng không phải JSON (vd log thư viện) vẫn có thể hiển thị thô.

### 2.7 GPU, VRAM, CUDA context — vì sao "process thoát = VRAM sạch"

VRAM là bộ nhớ riêng trên card đồ hoạ. Mô hình Stable Diffusion 1.5 fp16, TTS, LLM đều phải nằm trong VRAM để GPU tính. Máy mục tiêu có thể chỉ 6–8GB, không đủ chứa tất cả cùng lúc. CUDA context: khi một process dùng GPU lần đầu, driver tạo một context (bảng trang bộ nhớ, kernel đã nạp…), chiếm vài trăm MB VRAM suốt đời process. Caching allocator của PyTorch: khi tensor bị giải phóng, PyTorch không trả VRAM cho driver mà giữ lại trong cache để cấp phát lần sau cho nhanh. `torch.cuda.empty_cache()` trả phần cache chưa dùng, nhưng không xoá CUDA context, và nếu còn tham chiếu Python nào đó giữ tensor (rò rỉ, vòng tham chiếu) thì phần đó vẫn bị chiếm. Ngoài ra còn phân mảnh bộ nhớ. Khi process kết thúc, driver thu hồi toàn bộ tài nguyên của process đó — context, cache, cả phần rò rỉ. Đây là cách giải phóng VRAM chắc chắn nhất.

Kết luận thiết kế: mỗi bước nặng GPU chạy trong process con riêng, xong là thoát → bước sau bắt đầu với VRAM sạch. Orchestrator (sống suốt phiên) không bao giờ đụng GPU.

### 2.8 Máy trạng thái hữu hạn (Finite State Machine)

FSM gồm: tập trạng thái hữu hạn, trạng thái đầu, và hàm chuyển (sự kiện nào đưa trạng thái nào sang trạng thái nào). Ví dụ đèn giao thông: Xanh → Vàng → Đỏ → Xanh. Lợi ích: tại mọi thời điểm hệ thống ở đúng một trạng thái có tên, UI hiển thị được, và có thể khôi phục sau khi tắt máy nếu trạng thái được lưu xuống đĩa. Trong dự án, trạng thái truyện là trường `status` trong `story.json` (mục 4.7).

### 2.9 SQLite, giao dịch và WAL

SQLite là CSDL quan hệ nhúng: toàn bộ DB là một file ( `app.db` ), không cần server. Hỗ trợ SQL, khoá ngoại, giao dịch ACID. Chế độ WAL (Write-Ahead Logging): thay vì ghi đè trực tiếp file DB, thay đổi được ghi nối vào file `app.db-wal` trước (định kỳ "checkpoint" gộp về file chính), nhờ đó người đọc không bị chặn bởi người ghi và người ghi không chặn người đọc — hợp khi nhiều thread (endpoint, callback) cùng truy cập. Giới hạn cần nói đúng: tại một thời điểm vẫn chỉ một người ghi; người ghi thứ hai phải chờ khoá. Tham số `timeout=15` trong `sqlite3.connect` ( `db.py:62` ) chính là thời gian tối đa chờ khoá đó trước khi báo lỗi `database is locked` .

### 2.10 Desktop wrapper: WebView2 và pywebview

WebView2 là thành phần Windows cho phép nhúng engine Chromium của Edge vào một cửa sổ ứng dụng. pywebview là thư viện Python tạo cửa sổ native chứa webview đó. Kết quả: giao diện vẫn là HTML/CSS/JS, nhưng người dùng thấy một ứng dụng desktop (không thanh địa chỉ, có tiêu đề riêng), và khi đóng cửa sổ, launcher có "móc" để dọn sạch tiến trình con.

### 2.11 Vài khái niệm hệ điều hành hay bị hỏi thêm

- Exit code (mã thoát): số nguyên process trả cho cha khi kết thúc. Quy ước: `0` = thành công, khác `0` = lỗi. Trong Python, `sys.exit(1)` / `raise SystemExit(1)` đặt mã 1; exception không bắt được cũng cho mã 1. Process bị `taskkill /F` có mã khác 0 (Windows thường trả 1) — vì thế không thể dùng riêng exit code để phân biệt "bị dừng" với "lỗi" (xem 4.7). `Popen` vs `subprocess.run` : `run` chặn tới khi con xong rồi trả kết quả (dùng cho việc ngắn: `nvidia-smi` , `taskkill` , FFmpeg trong `video_merger` , `/api/autosub/prepare` ); `Popen` khởi động con và trả về ngay, cha tự đọc pipe và `wait()` sau (dùng cho các bước dài trong `ProcessManager` ). Daemon thread: thread đánh dấu `daemon=True` không giữ process sống; khi main thread thoát, Python kết thúc luôn các daemon thread. Reader thread, thread chuỗi tự động, thread uvicorn trong `desktop.py` đều là daemon → đóng app không bị treo vì thread còn chạy. Race condition & lock: khi hai thread cùng đọc–sửa–ghi một dict, thứ tự xen kẽ có thể làm sai dữ liệu. `threading.Lock` bảo đảm tại một thời điểm chỉ một thread ở trong đoạn "with self._lock:". Cây tiến trình (process tree): process con có thể đẻ tiếp process cháu (adapter → ffmpeg). Trên Windows, giết cha không tự giết con; phải diệt cả cây ( `taskkill /T` ) hoặc gom chúng vào một Job Object (dự án chưa dùng Job Object — xem mục 6).

## 3. Vì sao chọn công nghệ/kiến trúc này

### 3.1 Vì sao Orchestrator + subprocess thay vì một chương trình nguyên khối

- **Tiêu chí:** Xung đột thư viện · **Nguyên khối (import hết vào 1 process):** `toolCaoTruyen` và `AIVoice` có venv riêng ( `toolCaoTruyen/.venv` , `AIVoice/.venv` , xem `pipeline.py:150` , `411` ) — gộp dễ vỡ phiên bản · **Orchestrator + subprocess (đã chọn):** Mỗi submodule dùng đúng venv của nó
- **Tiêu chí:** Giải phóng VRAM · **Nguyên khối (import hết vào 1 process):** Phụ thuộc `empty_cache` , dễ rò rỉ · **Orchestrator + subprocess (đã chọn):** Process thoát → driver thu hồi toàn bộ
- **Tiêu chí:** Cô lập lỗi · **Nguyên khối (import hết vào 1 process):** Crash thư viện C (CUDA, onnx) kéo sập cả UI · **Orchestrator + subprocess (đã chọn):** Con chết, orchestrator vẫn sống, báo `*_FAILED`
- **Tiêu chí:** Dừng giữa chừng · **Nguyên khối (import hết vào 1 process):** Khó "giết" một thread Python an toàn · **Orchestrator + subprocess (đã chọn):** `taskkill /T /F` cả cây
- **Tiêu chí:** Tái sử dụng · **Nguyên khối (import hết vào 1 process):** Phải sửa submodule · **Orchestrator + subprocess (đã chọn):** Submodule chạy độc lập qua CLI adapter, cũng chạy tay được
- **Tiêu chí:** Chi phí · **Nguyên khối (import hết vào 1 process):** Không tốn thời gian khởi động · **Orchestrator + subprocess (đã chọn):** Mỗi bước phải nạp lại model (vài chục giây) — chấp nhận được vì mỗi bước chạy hàng phút–giờ

### 3.2 Vì sao FastAPI

- **Phương án:** Flask · **Nhận xét:** Đồng bộ (WSGI), streaming SSE được nhưng phải tự lo concurrency; không có validation sẵn
- **Phương án:** Django · **Nhận xét:** Quá nặng (ORM, admin, template) cho một app cục bộ
- **Phương án:** FastAPI · **Nhận xét:** ASGI async, hỗ trợ cả `def` và `async def` , pydantic validation + tài liệu OpenAPI tự sinh ( `/docs` ), `StreamingResponse` cho SSE/NDJSON, khởi động nhanh
- **Phương án:** Giao diện desktop thuần (Tkinter/Qt) · **Nhận xét:** Phải viết lại UI; mất khả năng dùng trình duyệt làm fallback

### 3.3 Vì sao SSE mà không WebSocket

Log chỉ đi một chiều; SSE chạy trên HTTP thường, `EventSource` tự reconnect, và FastAPI chỉ cần `StreamingResponse(...,` `media_type="text/event-stream")` ( `main.py:512-515` ). Lệnh điều khiển (start/stop) đã có REST riêng nên không cần kênh hai chiều.

### 3.4 Vì sao JSON Lines qua stdout mà không dùng socket/HTTP giữa các process

- stdout là kênh có sẵn cho mọi process, không cần mở port, không lo firewall, không lo xung đột cổng. Tách message bằng xuống dòng — cực đơn giản. Chạy tay adapter trên terminal vẫn đọc được log. Nhược: một chiều (con → cha). Chiều cha → con dùng tham số dòng lệnh + biến môi trường + file config.

### 3.5 Vì sao file JSON + SQLite (hai lớp)

`story.json` là nguồn sự thật gần dữ liệu nặng (copy thư mục truyện là mang theo trạng thái); SQLite là bản mirror để truy vấn thống kê nhanh (dashboard `/api/stats` ) mà không phải quét đĩa. Không dùng PostgreSQL/MySQL vì app cục bộ một người dùng, không muốn bắt cài server CSDL.

### 3.6 Vì sao pywebview thay vì Electron

Electron phải đóng gói thêm Node.js + Chromium (~100MB+) và viết launcher bằng JS; pywebview dùng WebView2 Runtime — có sẵn trên Windows 11 và phần lớn Windows 10 đã cập nhật, máy cũ thiếu thì `setup.bat` gọi `scripts\cai_webview2.bat` để cài, và nếu vẫn lỗi thì `desktop.py` fallback sang trình duyệt. pywebview chạy trong chính Python của `AIVoice/.venv` và có thể gọi thẳng `process_mgr.stop_all()` khi đóng cửa sổ ( `desktop.py:120-138` ).

## 4. Hiện thực trong code

4.1 Khởi động ứng dụng: từ `run.bat` tới trang web

Chi tiết từng bước:

1. `run.bat` : nếu thiếu `AIVoice\.venv\Scripts\python.exe` hoặc `toolCaoTruyen\.venv\Scripts\python.exe` thì tự `call` `setup.bat` (máy mới chỉ cần nhấp một file). Sau đó đặt `PYTHONPATH=%CD%` , `PYTHONIOENCODING=utf-8` và chạy `start ""` `"AIVoice\.venv\Scripts\pythonw.exe" -m orchestrator.desktop` (không console); tham số `debug` thì dùng `python.exe` để thấy log. Comment trong `run.bat` giải thích vì sao luôn gọi `-m module` : sau khi di chuyển thư mục dự án, các `.exe` launcher trong venv (uvicorn.exe, pip.exe) chứa đường dẫn tuyệt đối cũ nên hỏng, chỉ `python.exe` còn chạy đúng. 2. `setup.bat` : đồng bộ submodule ( `git submodule update--init--recursive` ), tìm/tự cài Python 3.11.9, gọi `setup.bat` của `toolCaoTruyen` và `AIVoice` , `pip install -r orchestrator\requirements.txt` vào venv của AIVoice (orchestrator dùng chung venv này), cài WebView2 ( `scripts\cai_webview2.bat` ), rồi sinh `configs\global_config.json` bằng chính `load_global_config()` để giá trị mặc định chỉ có một nguồn sự thật. 3. `desktop.main()` ( `desktop.py:160-226` ):

- `_ensure_streams()` ( `29-40` ): dưới `pythonw` , `sys.stdout` là `None` → mọi `print` sẽ lỗi; hàm chuyển stdout/stderr vào `logs/app.log` . `os.chdir(ROOT_DIR)` vì `main.py` resolve `"webui"` , `"AIVoice/.venv"` theo thư mục làm việc (comment `desktop.py:23` ). `_start_gemini_proxy()` ( `49-78` ): chạy `toolCaoTruyen/Gemini-API/start_server.bat` ẩn nếu cổng 7860 chưa mở. Nếu cổng 8100 đã mở (app đang chạy) thì chỉ mở cửa sổ; ngược lại `_start_server()` ( `101-108` ) tạo `uvicorn.Server` chạy trong thread daemon, rồi `_wait_until_ready(timeout=30.0)` thử kết nối socket mỗi 0.3s.

```
webview.create_window(WINDOW_TITLE, URL, width=1280, height=840, min_size=(1100, 720), confirm_close=not
```

- `smoke,...)` ( `190-198` ). pywebview bắt buộc chạy GUI trên main thread, nên uvicorn phải nằm ở thread phụ. Thiếu `pywebview` hoặc WebView2 lỗi → `_run_browser_fallback` mở trình duyệt mặc định và ghi rõ lý do ( `141-157` ). Đóng cửa sổ → `_shutdown` ( `120-138` ): `orchestrator_main.process_mgr.stop_all()` (diệt mọi tiến trình AI), kill Gemini proxy, `server.should_exit = True` . Cờ `--smoke` : mở cửa sổ, chờ trang load, tự đóng sau 3s — dùng làm kiểm thử khói.

4. `main.py` được import: `_lifespan` ( `32-39` ) gọi `model_preflight.start()` (chạy nền, không chặn); tạo các singleton ( `55-` `61` ):

```
_cfg = load_global_config()
_storage_dir = (_cfg.get("storage_dir") or "storage").strip() or "storage"
storage_mgr = StorageManager(base_storage_dir=_storage_dir)
process_mgr = ProcessManager()
pipeline = NovelPipeline(storage_mgr, process_mgr)
auto_run_mgr = AutoRunManager(storage_mgr, process_mgr, pipeline)
chat_mgr = ChatManager(storage_mgr, process_mgr, auto_run_mgr)
```

Đây là dependency injection thủ công: `NovelPipeline` không tự tạo `ProcessManager` mà nhận từ ngoài, nên test có thể thay bằng bản giả. Cuối file, `app.mount("/", StaticFiles(directory=webui_dir, html=True))` ( `main.py:1183-1185` ) phục vụ giao diện ở cùng origin — vì thế `webui/app.js:2` đặt `API_BASE = ""` và CORS chỉ cho `127.0.0.1:8100` / `localhost:8100` ( `main.py:44-50` ).

### 4.2 Bảng endpoint chính

- **Method + path:** `GET/POST /api/config` · **Hàm:** `get_config` , `update_config` · **Việc làm:** Đọc/ghi `global_config.json`
- **Method + path:** `GET/POST /api/stories` · **Hàm:** `get_stories` , `create_story` · **Việc làm:** Liệt kê / tạo workspace truyện (409 nếu trùng)
- **Method + path:** `GET /api/stories/{name}` · **Hàm:** `get_story_details` · **Việc làm:** `story.json` + `story_dir` + số chương quét từ đĩa
- **Method + path:** `POST /api/pipeline/step1..5` · **Hàm:** `run_step1` … `run_step5` · **Việc làm:** Kiểm tra trùng → gọi `pipeline.start_step_*` → trả `task_key`
- **Method + path:** `POST /api/pipeline/stop?story_name&step` · **Hàm:** `stop_pipeline` · **Việc làm:** `process_mgr.stop_process` + đặt `CANCELLED`
- **Method + path:** `GET /api/pipeline/logs/{task_key}` · **Hàm:** `stream_logs` · **Việc làm:** SSE log
- **Method + path:** `GET /api/pipeline/status/{task_key}` · **Hàm:** `pipeline_task_status` · **Việc làm:** `{running, completed, exit_code}` cho UI khi SSE rớt
- **Method + path:** `POST /api/pipeline/auto-run` (+ `/stop` , `GET` `/{story}` ) · **Hàm:** `start_auto_run` … · **Việc làm:** Chuỗi tự động 1→4
- **Method + path:** `GET /api/system/gpu-info` · **Hàm:** `get_gpu_info` · **Việc làm:** `nvidia-smi` , fallback WMI cho AMD/Intel
- **Method + path:** `GET /api/system/busy` · **Hàm:** `get_system_busy` · **Việc làm:** Task đang chạy + mức chiếm GPU
- **Method + path:** `GET/POST /api/models/preflight` · **Hàm:** — · **Việc làm:** Tiến độ/chạy lại preflight
- **Method + path:** `POST /api/chat` , `/api/chat/unload` , `/prewarm` , `/model` · **Hàm:** — · **Việc làm:** Trợ lý AI (chương riêng)
- **Method + path:** `GET /api/stats` , `POST /api/maintenance/*` · **Hàm:** — · **Việc làm:** Thống kê SQLite, dọn `tasks/` , rebuild DB

Mẫu chung của một endpoint chạy bước ( `main.py:474-490` ):

```
@app.post("/api/pipeline/step3")
def run_step3(body: Step3Schema):
    from orchestrator.storage import slugify
    slug = slugify(body.story_name)
    task_key = f"{slug}_step3"
    _reject_if_auto_running(slug)
    if process_mgr.is_running(task_key):
        raise HTTPException(status_code=400, detail="A video generation process is already active for this story.")
    try:
        success = pipeline.start_step_3_video(body.story_name, body.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if success:
        return {"status": "success", "task_key": task_key}
    raise HTTPException(status_code=500, detail="Failed to start pipeline Step 3.")
```

Điểm cần nhớ: endpoint trả về ngay (vài ms) sau khi spawn; công việc thật chạy nền. Client dùng `task_key` (dạng `<slug>_step<N>` ) để mở SSE. Hai lớp bảo vệ: `_reject_if_auto_running` (không chen vào chuỗi tự động, `main.py:63-67` ) và

`is_running(task_key)` (không chạy trùng một bước).

4.3 `NovelPipeline` : dựng lệnh và gắn callback

Mỗi `start_step_*` theo cùng khuôn: (1) đọc `story.json` , (2) chọn thư mục vào/ra, (3) trộn tham số request + cấu hình chung + mặc định cứng, (4) dựng `cmd` (list, không phải chuỗi shell → không bị shell injection), (5) định nghĩa callback `on_*_completed(exit_code)` , (6) ghi trạng thái "đang chạy", (7) `process_mgr.start_process(...)` .

4.3.1 Thứ tự ưu tiên tham số

Ví dụ Bước 2 ( `pipeline.py:414-426` ): `engine = tts_args.get("engine") or tts_cfg.get("default_engine", "edge")` . Tức là request > global_config > hằng số trong code. Cùng quy tắc cho Bước 3: `--style` = request → `video.default_style` → `"thuy_mac"` ; `--checkpoint` → `"anything-v5"` ( `pipeline.py:544-545` ).

4.3.2 Bước 1: chuỗi crawl → translate trên cùng một `task_key`

`start_step_1_crawl_translate` ( `pipeline.py:135-331` ) có ba nhánh:

- `source=="ai_write"` → `start_ai_write` (thread gọi LLM sáng tác, xong đặt `TRANSLATED` , `pipeline_step=2` vì nội dung đã là tiếng Việt, `pipeline.py:370-375` ). `source=="local"` → thread `_copy_local` chuẩn hoá tên chương từ thư mục người dùng sang `raw/` qua `chapter_naming.normalize_dir` ; nếu không nạp được gì thì `_chan_doan_thu_muc_cuc_bo` ( `43-87` ) giải thích lý do (trỏ nhầm thư mục cha, sai đuôi file). Còn lại → subprocess `adapter_cli.py crawl--source...--story-id...--num-chapters...--output-dir raw/` ( `pipeline.py:155-169` ).

Lệnh dịch được dựng sẵn trước khi crawl ( `pipeline.py:172-196` ): `adapter_cli.py translate--input-dir raw/--output-dir` `raw/--engine...` (dịch tại chỗ trong `raw/` ), kèm các cờ model/key/genre và `--auto-extract` (trích thuật ngữ vào glossary) nếu bật. Engine dịch lấy theo thứ tự: request → `translate.default_engine` trong config (mặc định `"ollama"` , model `"qwen2.5:7b-instruct"` ) — do `_build_step1_args` ( `main.py:399-429` ) quyết định; hằng `"gemini_api"` ở `pipeline.py:176` chỉ là sàn cuối khi `engine` rỗng.

Lưu ý với nguồn `local` : trạng thái vẫn được ghi `CRAWLING` ( `pipeline.py:266-268` ) dù không cào — tên trạng thái mang nghĩa "đang nạp chương".

Điểm hay: crawl xong, callback `on_crawl_completed` ( `220-263` ) spawn tiếp tiến trình translate trên cùng `task_key` và cùng log queue:

```
started = self.process_mgr.start_process(
    task_key=task_key,
    cmd=translate_cmd,
    cwd="toolCaoTruyen",
    on_completed=on_translate_completed,
    close_queue_on_exit=True,
    reuse_queue=True
)
```

Còn khi spawn crawl thì `close_queue_on_exit=False` ( `pipeline.py:276` ) — nghĩa là "đừng gửi tín hiệu kết thúc SSE khi crawl xong, vì còn translate". Nhờ vậy UI thấy một luồng log liền mạch crawl → dịch. Hệ quả: khi crawl lỗi hoặc không dịch, chính callback phải tự đóng luồng — hàm `finish_step1` ( `pipeline.py:200-204` ) gọi `process_mgr.mark_completed(task_key,` `exit_code)` rồi `q.put(None)` .

Vì sao `start_process` lần hai (translate) không bị từ chối là "đang chạy"? Ở reader thread, slot `active_processes[task_key]` được xoá trước khi gọi callback ( `process_manager.py:77-85` ), và `reuse_queue=True` bỏ qua kiểm tra `finalizing_tasks` / `manual_running_tasks` ( `process_manager.py:25-27` ).

4.3.3 Bước 3: truyền cấu hình cho tiến trình con bằng 3 kênh

`start_step_3_video` ( `pipeline.py:499-612` ) cho thấy đủ ba kênh cha → con:

- 1. File config: trước khi spawn, `mediacomposer_config.apply_sd_params(load_global_config().get("video", {}))` ( `508-` `513` ) ghi `num_inference_steps` , `guidance_scale` , `image_width` … vào `[storytelling]` của

- `AIVoice/apps/MediaComposer/config.toml` . Comment nói rõ lý do: "tiến trình đọc config lúc khởi động, ghi sau đó là không kịp". 2. Tham số dòng lệnh ( `pipeline.py:538-584` ): `--story-name` , `--genre` , `--input-dir` , `--output-dir` , `--style` , `--` `checkpoint` , `--bgm-path` , `--bgm-volume` , `--llm-api-key/--llm-base-url/--llm-model` , các cặp cờ bật/tắt `--enable-` `upscale/--no-upscale` , `--burn-subtitles/--no-subtitles` , `--use-semantic-split/--no-semantic-split` , `--extract-` `characters/--no-extract-characters` , `--enable-face-detailer/--no-face-detailer` , `--hardware-profile` , và `--render-` `mode` chỉ khi người dùng chọn rõ `classic` / `studio` ( `582-584` ); `auto` thì bỏ cờ để MediaComposer tự chọn. 3. Biến môi trường ( `587-594` ):

```
env_override = {
    "MC_STORAGE_TASKS": self.storage_mgr.tasks_dir
}
device = video_args.get("device", "auto")
if device == "cpu":
    env_override["CUDA_VISIBLE_DEVICES"] = ""
elif device.startswith("cuda:"):
    env_override["CUDA_VISIBLE_DEVICES"] = device.split(":")[1]
```

`CUDA_VISIBLE_DEVICES=""` làm PyTorch trong con không thấy GPU nào → chạy CPU; `"1"` thì chỉ thấy GPU số 1 (và bên trong con nó được đánh số lại thành `cuda:0` ). Đây là cách chọn thiết bị mà không phải sửa code submodule. Lưu ý: `Step3Schema.device` mặc định là `"cuda"` (không có dấu `:` ) — khi đó không đặt biến môi trường nào, con thấy mọi GPU.

LLM cho Bước 3 được phân giải bởi `llm.resolve_llm` ( `llm.py:20-66` ). Engine lấy theo thứ tự request `llm_engine` → `video.default_llm_engine` (config mặc định `"ollama"` ) → `"gemini_api"` ( `pipeline.py:533` ). Ba nhánh:

- **Engine:** `gemini` (Gemini online) · **api_key:** request hoặc `api_keys.gemini` , thiếu → `ValueError` · **base_url:** `https://generativelanguage.googleapis.com/v1beta/openai/` · **model mặc định:** `DEFAULT_GEMINI_ONLINE_MODEL` `= "gemini-2.0-flash"`
- **Engine:** `ollama` · **api_key:** chuỗi giả `"ollama"` · **base_url:** request → `crawler.ollama_base_url` → `http://localhost:11434/v1` · **model mặc định:** `DEFAULT_OLLAMA_MODEL =` `"qwen2.5:3b-instruct"`
- **Engine:** còn lại = `gemini_api` (proxy Gemini cục bộ) · **api_key:** request → `crawler.gemini_offline_key` → `api_keys.gemini` , thiếu → `ValueError` · **base_url:** request → `crawler.gemini_offline_base_url` → `http://localhost:7860/v1` · **model mặc định:** `DEFAULT_GEMINI_PROXY_MODEL` `= "gemini-3-flash"`

(Các hằng ở `config.py:8-10` .) Trước các hằng này, model còn lấy từ request `llm_offline_model` rồi `video.default_llm_model` . Cả ba nhánh đều là API tương thích OpenAI ( `/chat/completions` ) nên MediaComposer chỉ cần một client `openai.OpenAI(api_key, base_url)` ( `AIVoice/apps/MediaComposer/app/services/llm.py` ). Thiếu key → `ValueError` → endpoint trả `400` ( `main.py:486-487` ).

4.3.4 Callback hoàn tất Bước 3 — chỉ báo thành công khi có video thật

`_finalize_video_task` ( `pipeline.py:99-133` ): nếu `exit_code==0` thì gọi `merge_videos` ghép thành `TongHop_<timestamp>.mp4` ; chỉ khi ghép thành công mới đặt `VIDEO_GENERATED` , ngược lại `VIDEO_FAILED` (hoặc `CANCELLED` nếu người dùng bấm dừng). Hàm trả `False` khi thất bại, và `ProcessManager` sẽ đổi exit code 0 thành 1 ( `process_manager.py:101-` `103` ) để chuỗi tự động không đi tiếp. Test: `tests/test_pipeline_video_completion.py::test_merge_failure_marks_video_failed` .

4.3.5 Bước 4 (UI) = `step5` : ghép video bằng thread

`start_step_5_merge` ( `pipeline.py:750-797` ) không spawn process (FFmpeg tự nó đã là process con của `subprocess.run` ), mà chạy thread, dùng `register_manual_task` để vẫn có log queue, và `contextlib.redirect_stdout(QueueWriter(q))` để mọi `print` của `merge_videos` chảy vào SSE.

4.4 `ProcessManager` : trái tim quản lý tiến trình

4.4.1 Cấu trúc dữ liệu ( `process_manager.py:13-20` )

- **Thuộc tính:** `active_processes` · **Kiểu:** `Dict[str, Popen]` · **Ý nghĩa:** task_key → process đang chạy
- **Thuộc tính:** `log_queues` · **Kiểu:** `Dict[str, queue.Queue]` · **Ý nghĩa:** task_key → hàng đợi log (cầu nối reader thread ↔ SSE)
- **Thuộc tính:** `completed_exit_codes` · **Kiểu:** `Dict[str, int]` · **Ý nghĩa:** exit code cuối của task đã xong (để reconnect biết kết quả)
- **Thuộc tính:** `finalizing_tasks` · **Kiểu:** `Dict[str, int]` · **Ý nghĩa:** task đang chạy callback hậu xử lý (vẫn tính là "đang chạy")
- **Thuộc tính:** `manual_running_tasks` · **Kiểu:** `set` · **Ý nghĩa:** task chạy bằng thread (local copy, ai_write, merge)
- **Thuộc tính:** `user_stopped_tasks` · **Kiểu:** `set` · **Ý nghĩa:** task bị người dùng dừng — để phân biệt `CANCELLED` với `*_FAILED`
- **Thuộc tính:** `_lock` · **Kiểu:** `threading.Lock` · **Ý nghĩa:** bảo vệ tất cả các dict trên khỏi race condition

4.4.2 `start_process` — spawn ( `process_manager.py:22-123` )

```
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
if env_override:
    env.update(env_override)
proc = subprocess.Popen(
    cmd,
    cwd=cwd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT, # Redirect stderr to stdout to capture everything in order
    text=True,
    encoding="utf-8",
    env=env,
    bufsize=1, # Line buffered
    creationflags=NO_WINDOW
)
```

Giải thích từng tham số:

`stderr=STDOUT` : gộp stderr vào stdout để giữ đúng thứ tự log và traceback. `PYTHONIOENCODING=utf-8` + `encoding="utf-8"` : log tiếng Việt không vỡ trên console Windows (mặc định cp1252). `bufsize=1` + `text=True` : đọc theo dòng. `creationflags=NO_WINDOW` ( `= subprocess.CREATE_NO_WINDOW` , `process_manager.py:10` ): vì orchestrator chạy dưới `pythonw` (không console), mỗi process con console-mode sẽ tự bật một cửa sổ đen nếu không có cờ này. `cmd` là list → không qua shell → tên truyện có ký tự đặc biệt không thể thành lệnh shell.

Kiểm tra trùng trước khi spawn ( `25-29` ): task đã có trong `active_processes` , hoặc đang manual, hoặc đang finalizing (trừ khi `reuse_queue=True` — trường hợp crawl → translate). Nếu hợp lệ, hàm xoá kết quả cũ ( `completed_exit_codes.pop` , `user_stopped_tasks.discard` , dòng 36-37) để lần chạy mới không bị nhầm với lần trước. Nếu `Popen` ném exception (vd thiếu `python.exe` của venv) thì đẩy `"[ERROR] Failed to start process:..."` vào queue và trả `False` .

4.4.3 Reader thread — biến stdout thành hàng đợi ( `process_manager.py:66-119` )

Mỗi process có một thread daemon đọc `process.stdout.readline` cho tới EOF, `q.put(line)` . Khi EOF:

1. `exit_code = process.wait()` . 2. Trong lock: chỉ thread "sở hữu" đúng process này ( `self.active_processes.get(task_key) is process` ) mới xoá slot — tránh reader cũ xoá nhầm process mới vừa được đăng ký cùng key. 3. Nếu có callback: tăng `finalizing_tasks[task_key]` → trong lúc callback (vd merge video mất vài phút) task vẫn được coi là đang chạy, không ai chen vào được. 4. Gọi `on_completed(exit_code)` ; callback trả `False` hoặc ném exception → exit code cuối thành 1. 5. Ghi `completed_exit_codes` , rồi mới `q.put(None)` — sentinel (tín hiệu kết thúc). Comment `95-96` : "Callback hậu xử lý phải hoàn tất và ghi log TRƯỚC sentinel; nếu không SSE sẽ báo xong quá sớm." Test: `tests/test_process_manager.py::test_callback_logs_arrive_before_terminal_event` . Bước này chỉ làm khi `close_queue_on_exit=True` hoặc callback lỗi ( `116-119` ); với crawl ( `close_queue_on_exit=False` ) việc ghi kết quả + sentinel do callback tự làm qua `mark_completed` (xem 4.3.2). 6. Trường hợp đặc biệt: nếu reader thấy mình không còn sở hữu slot (do `stop_process` đã cưỡng chế giải phóng, xem 4.4.4) thì `return` luôn — không chạy callback, không đặt sentinel ( `89-93` ), vì queue có thể đã thuộc về lần chạy mới.

Đây là mẫu producer–consumer: reader thread là producer, generator SSE là consumer, `queue.Queue` (thread-safe) là băng chuyền.

4.4.4 Dừng tiến trình: kill cả cây trên Windows ( `process_manager.py:125-185` )

```
if os.name == "nt":
    subprocess.run(
        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
        capture_output=True, timeout=15,
        creationflags=NO_WINDOW)
else:
    proc.terminate()
```

`/T` = tree (diệt cả con cháu), `/F` = force. Sau đó `_kill_process_tree` còn `proc.wait(timeout=3)` , quá hạn thì gọi thêm `proc.kill()` ( `process_manager.py:143-149` ). Mọi lỗi đều bị nuốt để việc dừng không bao giờ ném exception ra endpoint. Lý do (docstring `127-132` ): nếu chỉ `terminate()` process adapter, các "cháu" (ffmpeg, worker…) mồ côi vẫn giữ đầu ghi của pipe → reader thread kẹt ở `readline()` mãi mãi → UI kẹt "đang chạy" (xem lý thuyết EOF ở 2.6).

`stop_process` :

- 1. Đánh dấu `user_stopped_tasks.add(task_key)` (trong lock). 2. Kill ngoài lock (vì `wait` mất vài giây; giữ lock thì mọi endpoint khác treo). 3. Chờ tối đa 8 giây ( `deadline = time.time() + 8.0` ) cho reader tự dọn. 4. Nếu vẫn chưa sạch (còn process mồ côi giữ pipe): tự giải phóng bookkeeping, đặt exit code `-1` nếu chưa có, đẩy `"` `[SYSTEM]Đã buộc dừng tiến trình theo yêu cầu."` và sentinel.

`stop_all()` ( `192-202` ) dùng khi đóng app: kill tất cả, không chờ — mục tiêu "không bỏ lại tiến trình mồ côi chiếm GPU/VRAM".

4.4.5 SSE generator ( `get_logs_generator` , `process_manager.py:275-305` ; hàm phụ `_sse_data` / `_completed_event` ở `261-273` )

Nếu task không có queue (vd server vừa khởi động lại): đã có kết quả thì trả ngay sự kiện kết thúc, không thì gửi `"[SYSTEM] No` `active log queue found for this task."` rồi đóng ( `277-283` ). Vòng lặp chính:

```
while True:
    try:
        if q.empty() and self.get_task_status(task_key)["completed"]:
            yield self._completed_event(task_key)
            break
        line = q.get(timeout=1.0)
        if line is None:
            yield self._completed_event(task_key)
            break
        yield self._sse_data(line)
    except queue.Empty:
        yield "data: [PING]\n\n"
```

- `q.get(timeout=1.0)` : chờ tối đa 1s; không có log thì gửi `[PING]` — keep-alive để kết nối không bị coi là chết và để phát hiện client ngắt. `_sse_data` ( `262-268` ) tách log nhiều dòng thành nhiều dòng `data:` (SSE bắt buộc mỗi dòng có tiền tố). `_completed_event` : `"[SYSTEM] Process completed (exit_code=N)."` — UI bắt chuỗi này ( `webui/app.js` , hàm `streamLogs` ) để đóng `EventSource` , tô màu thành công/lỗi. Reconnect: sentinel có thể đã bị một kết nối cũ "ăn" mất; nhờ `completed_exit_codes` , kết nối mới thấy `q.empty() and` `completed` là kết thúc ngay thay vì PING vô hạn (test `test_reconnect_after_terminal_does_not_ping_forever` ). Khi SSE lỗi, UI gọi `GET /api/pipeline/status/{task_key}` để phân biệt "mạng chập chờn nhưng task còn chạy" với "task đã xong".

### 4.5 Giao thức tiến độ JSON Lines trên stdout

Mọi adapter CLI định nghĩa cùng một hàm (vd `adapter_video_cli.py:23-26` , tương tự `adapter_tts_cli.py:12-15` , `AIVoice/apps/MediaComposer/adapter_autosub_cli.py:16-19` , `toolCaoTruyen/adapter_cli.py:16-19` ):

```
def log_json(event: str, data: dict):
    """Outputs progress log as a JSON string to stdout."""
    print(json.dumps({"event": event, **data}, ensure_ascii=False))
    sys.stdout.flush()
```

- `event` là tên sự kiện, các khoá còn lại là payload. `ensure_ascii=False` giữ nguyên chữ Việt. `flush()` ngay để vượt qua buffering pipe.

Danh mục event thật (đã grep):

- **Adapter:** `toolCaoTruyen/adapter_cli.py` · **Event:** `crawl_start` , `crawl_warn` , `crawl_completed` , `crawl_failed` , `compress_start/success` , `translate_start` , `translate_warn` , `file_start` , `file_log` , `file_success` , `file_failed` , `file_repair_start/done/warn` , `glossary_added` , `glossary_warn` , `cleanup_file` , `cleanup_warn` , `translate_completed` , `translate_failed`
- **Adapter:** `AIVoice/adapter_tts_cli.py` · **Event:** `preset_loaded/warn` , `tts_batch_start` , `tts_file_skip` , `tts_batch_warn` , `tts_file_start` , `tts_file_success` , `tts_file_failed` , `tts_batch_completed` , `tts_error` , `hardware_released` ; chế độ một file ( `--input` ): `tts_start` , `tts_success` , `tts_failed`
- **Adapter:** `adapter_video_cli.py` · **Event:** `video_init` , `video_error` , `model_warn` , `model_ready` , `context_loaded` , `context_created_start/success` , `style_applied` , `video_progress` ( `message` , `percent` ), `video_warn` , `video_batch_start` , `video_batch_completed` , `hardware_released`

Ai hiểu JSON? Điểm tinh tế cần nói đúng: orchestrator không parse JSON trong luồng chính — `ProcessManager` chuyển nguyên văn từng dòng sang SSE. Việc diễn giải nằm ở trình duyệt: `webui/app.js` trong `source.onmessage` thử `JSON.parse(rawLine)` , nếu có `parsed.event` thì `switch` sang câu tiếng Việt và màu tương ứng (vd `tts_file_start` → `"[TTS]Đang sinh giọngđọc` `file i/N:..."` ); dòng không phải JSON (log thư viện, traceback) hiển thị thô. Nguồn sự thật về thành/bại là exit code, không phải event. Ngoại lệ duy nhất orchestrator tự parse JSON: `/api/autosub/prepare` ( `main.py:654-663` ) chạy `subprocess.run(..., timeout=900)` rồi tìm dòng có `"event": "prepare_done"` để lấy `prepared_path` , `width` , `height` , ảnh preview.

Quy ước exit code mà adapter tuân thủ, ví dụ `adapter_video_cli.py` : thư mục đầu vào không có cặp md+audio → `video_error` + `sys.exit(1)` ( `adapter_video_cli.py:97-128` ; kiểm tra này đặt trước khi tải model để báo lỗi sớm), comment giải thích "Thoát 0 ở đây là nói dối: chuỗi tự động sẽ chạy tiếp sang bước ghép video..." và phân biệt 3 tình huống để chỉ đúng bước cần quay lại (thiếu thư mục/rỗng → Bước 1; có `.md` nhưng không ghép được audio → Bước 2); có item không ra được mp4 → `video_batch_completed` với `status: "partial_failure"` rồi `raise SystemExit(1)` ( `count_incomplete_items` , dòng 238- 245).

### 4.6 Xử lý theo từng chương, resume và skip

Không có "resume" tập trung trong orchestrator; thay vào đó mỗi bước idempotent (chạy lại không làm hỏng, chỉ làm phần còn thiếu) dựa trên file trên đĩa:

- **Bước:** Crawl · **Cơ chế resume/skip:** Cờ `--continue-download` · **Nguồn:** `pipeline.py:168-169`
- **Bước:** Dịch · **Cơ chế resume/skip:** Bỏ qua file gốc đã có bản `" - [VI] "` cùng tiền tố chương; không còn gì để dịch thì báo rõ lý do · **Nguồn:** `toolCaoTruyen/adapter_cli.py:97-133` , `254-267`
- **Bước:** Nạp local · **Cơ chế resume/skip:** Chạy lại mà `raw/` đã đủ chương thì vẫn coi thành công · **Nguồn:** `pipeline.py:302-314`
- **Bước:** TTS · **Cơ chế resume/skip:** Bỏ qua chương đã có `.wav/.mp3` cùng tên; chỉ đọc file có dấu `" - [VI] "` ; tất cả đã có audio → `tts_batch_warn` + exit 0; không có file hợp lệ → `tts_error` + exit 1 · **Nguồn:** `adapter_tts_cli.py:157-207`
- **Bước:** Video · **Cơ chế resume/skip:** `batch_state.json` trong thư mục output lưu trạng thái từng item: `pending→` `script_done→images_done→upscale_done→video_done` (hoặc `failed` ); item `video_done` nhưng mp4 mất thì hạ trạng thái để chạy lại · **Nguồn:** `batch_video_runner.py:37-43` , `_reconcile_video_done`
- **Bước:** Ghép · **Cơ chế resume/skip:** Bỏ file `TongHop_*` khỏi danh sách; chỉ nhận basename thuần (chống path traversal) · **Nguồn:** `video_merger.py:6-13`

Bước 3 còn tổ chức 2 pass để tiết kiệm VRAM (docstring của `batch_video_runner.run_batch` , dòng 216): Pass A sinh kịch bản + toàn bộ ảnh SD cho mọi chương (giữ SD "nóng" trong VRAM), sau đó `StorytellingPipeline().release()` , rồi Pass B upscale (RealESRGAN) + render video. Gặp `OutOfMemoryError` thì release và thử lại 1 lần. (Chi tiết ở chương về MediaComposer.)

### 4.7 Máy trạng thái của truyện

Trạng thái lưu ở `story.json["status"]` , cộng thêm `pipeline_step` (1: crawl/dịch, 2: TTS, 3: video). Mọi giá trị dưới đây đã grep trong `pipeline.py` và `storage.py` :

- **Trạng thái:** `CREATED` · **Ghi bởi:** `init_story_workspace` ( `storage.py:92` )
- **Trạng thái:** `CRAWLING` → `CRAWLED` / `CRAWL_FAILED` · **Ghi bởi:** `start_step_1_crawl_translate` , `on_crawl_completed`
- **Trạng thái:** `TRANSLATING` → `TRANSLATED` / `TRANSLATE_FAILED` · **Ghi bởi:** `on_crawl_completed` , `on_translate_completed`
- **Trạng thái:** `WRITING` → `TRANSLATED` / `WRITE_FAILED` · **Ghi bởi:** `start_ai_write`
- **Trạng thái:** `VOICE_GENERATING` → `VOICE_GENERATED` / `VOICE_FAILED` · **Ghi bởi:** `start_step_2_tts` , `on_tts_completed`
- **Trạng thái:** `VIDEO_GENERATING` → `VIDEO_GENERATED` / `VIDEO_FAILED` · **Ghi bởi:** `start_step_3_video` , `_finalize_video_task`
- **Trạng thái:** `AUTOSUB_RUNNING` → `AUTOSUB_COMPLETED` / `AUTOSUB_FAILED` · **Ghi bởi:** `start_step_4_autosub`
- **Trạng thái:** `CANCELLED` · **Ghi bởi:** callback khi `was_user_stopped` , và endpoint `stop_pipeline` / `stop_task`

Cách phân biệt `CANCELLED` và `*_FAILED` : process bị `taskkill` cũng có exit code khác 0, giống lỗi thật. Vì vậy `stop_process` ghi `user_stopped_tasks` trước khi kill, và callback hỏi `self.process_mgr.was_user_stopped(task_key)` (vd `pipeline.py:481-` `484` ). Ngoài ra endpoint `stop_pipeline` ( `main.py:492-507` ) và `stop_task` ( `main.py:730-751` ) sau khi dừng thành công còn ghi đè `status = "CANCELLED"` lần nữa (trường hợp reader bị cưỡng chế giải phóng thì callback không chạy, nên lần ghi này là cần thiết).

`pipeline_step` chỉ tăng khi bước thành công: dịch/sáng tác xong → 2 ( `pipeline.py:212` , `373` ), TTS xong → 3 ( `480` ), video xong → giữ 3 ( `130` ). Chú ý: comment trong `storage.py:92` ghi chuỗi "CREATED -> CRAWLED -> TRANSLATED -> ..." chỉ là mô tả đơn giản hoá, không liệt kê đủ trạng thái trung gian.

Nói thật với hội đồng: đây là FSM mô tả (descriptive) hơn là FSM cưỡng chế: code không chặn việc chạy Bước 3 khi trạng thái chưa phải `VOICE_GENERATED` — bảo vệ thực tế nằm ở (a) `is_running` chống chạy trùng, (b) adapter tự kiểm tra đầu vào và thoát 1 kèm lý do rõ ràng (4.5), (c) chuỗi tự động chỉ đi tiếp khi exit code 0. Lựa chọn này cho phép người dùng chạy lại một bước bất kỳ (vd đổi style rồi chạy lại Bước 3) mà không bị trạng thái cứng khoá lại.

4.8 `AutoRunManager` : chuỗi tự động 1→4

- `start()` ( `auto_run.py:58-95` ): từ chối nếu chuỗi đang chạy hoặc có bước lẻ đang chạy tay; tạo `threading.Event` làm cờ huỷ; khởi thread daemon `_run_chain` . `_run_chain` ( `137-165` ): lặp `CHAIN_STEPS` , gọi starter tương ứng, rồi `_wait_step` poll `get_task_status` mỗi `poll_interval` `= 1.0` giây ( `28` ) tới khi `completed` . Exit 0 → bước tiếp; khác 0 → dừng chuỗi với thông báo `"Bước X thất bại (mã lỗi N).` `Xem log của bướcđểbiết chi tiết."` . `stop()` ( `97-108` ): `cancel.set()` rồi `stop_process` mọi bước của truyện. Vì chạy ở backend, reload trang không làm gián đoạn chuỗi; restart server thì chuỗi mất (ghi nhận trong docstring: "chấp nhận ở v1"). Test: `tests/test_auto_run.py` (chạy đúng thứ tự, dừng khi bước lỗi, huỷ giữa chừng, từ chối khi đang chạy…).

4.9 Lưu trữ: `StorageManager` và SQLite

`slugify` ( `storage.py:15-48` ): chữ thường → thay dấu tiếng Việt bằng regex ( `[áàảãạ...]` → `a` , `đ` → `d` ) → `unicodedata.normalize('NFKD')` + bỏ ký tự không ASCII → xoá dấu câu/ký tự đặc biệt ( `[^\w\s-]` → rỗng) → gộp mỗi cụm khoảng trắng/ `_` / `-` thành một `_` và cắt `_` ở hai đầu; chuỗi rỗng thì trả `"unknown"` . Ví dụ docstring: `"Đắc KỷTrụVương"` → `"dac_ky_tru_vuong"` . Hệ quả cần biết: hai tên chỉ khác dấu (vd "Tây Du" và "Tay Du") ra cùng slug → cùng thư mục; `init_story_workspace` sẽ báo trùng (409). Lý do: tên thư mục ASCII an toàn trên mọi công cụ (FFmpeg, concat list, đường dẫn Windows).

Ghi metadata ( `write_story_meta135-148` ): ghi `story.json` (UTF-8, `ensure_ascii=False` ), sau đó mirror sang SQLite qua `_mirror_to_db` ( `207-212` ) = `db.upsert_story` + `db.replace_chapters(slug, self._scan_chapters(...))` . Lỗi DB bị nuốt ( `except: pass` ) để không phá luồng file — DB là phụ.

`_scan_chapters` ( `169-196` ) chọn `translated/` nếu có `.md` , không thì `raw/` ; với mỗi `.md` kiểm tra `.wav` cạnh nó và `video/<stem>.mp4` , suy ra trạng thái chương `text` / `tts` / `video` .

Schema SQLite ( `db.py:17-52` ):

```
CREATE TABLE IF NOT EXISTS stories (
    slug TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT, language TEXT,
    status TEXT, pipeline_step INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT, story_slug TEXT NOT NULL, idx INTEGER NOT NULL,
    title TEXT, md_path TEXT, wav_path TEXT, mp4_path TEXT, status TEXT,
    UNIQUE(story_slug, idx),
    FOREIGN KEY (story_slug) REFERENCES stories(slug) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, story_slug TEXT NOT NULL, step TEXT NOT NULL,
    status TEXT, message TEXT, started_at TEXT, ended_at TEXT,
    FOREIGN KEY (story_slug) REFERENCES stories(slug) ON DELETE CASCADE);
```

Quan hệ: `stories` 1–N `chapters` , `stories` 1–N `jobs` . `connect()` ( `59-66` ) mở kết nối ngắn hạn mỗi thao tác, `check_same_thread=False` , `timeout=15` , bật `PRAGMA journal_mode=WAL` và `PRAGMA foreign_keys=ON` (SQLite mặc định tắt khoá ngoại). `upsert_story` dùng `INSERT... ON CONFLICT(slug) DO UPDATE` (upsert nguyên tử; khi cập nhật không ghi đè `created_at` ). `replace_chapters` xoá hết chương của truyện rồi chèn lại danh sách vừa quét đĩa ( `db.py:109-125` ) — đơn giản và luôn khớp với đĩa. Mọi câu lệnh dùng tham số `?` (parameterized query) nên không bị SQL injection. Ngoài bảng còn hai index `idx_chapters_story` , `idx_jobs_story` ( `db.py:50-51` ).

Lưu ý trung thực: bảng `jobs` và hàm `add_job` / `finish_job` có định nghĩa nhưng hiện không được gọi ở đâu trong orchestrator (đã grep) → `stats()["jobs_failed"]` luôn 0. Nên trình bày là "thiết kế sẵn cho lịch sử job, chưa nối dây".

Dọn dẹp ( `cleanup_tasks242-277` , CLI `cleanup.py` ): chỉ xoá thư mục job dạng UUID và thư mục khung trung gian ( `draft_frames` , `final_frames` , `scenes` , `temp_audio` , `temp` ), không bao giờ đụng `PROTECTED_DIRS = ("contexts",` `"character_loras")` (tri thức nhân vật, LoRA). Hỗ trợ `dry_run` và `keep_days` .

### 4.10 Cấu hình nhiều lớp

- **Lớp:** 1. Hằng số trong code · **Vị trí:** `config.py` ( `DEFAULT_OLLAMA_MODEL` , `SD_TUNING_DEFAULTS` , dict mặc định trong `load_global_config` ), các `or "..."` trong `pipeline.py` · **Ghi chú:** Sàn cuối cùng
- **Lớp:** 2. Cấu hình chung · **Vị trí:** `configs/global_config.json` (bị `.gitignore` vì chứa API key) · **Ghi chú:** Các mục: `api_keys` , `storage_dir` , `orchestrator_port` , `crawler` , `translate` , `tts` , `video` , `autosub` , `chatbot`
- **Lớp:** 3. Trạng thái form UI · **Vị trí:** `configs/ui_settings.json` ( `load_ui_settings` / `save_ui_settings` ) · **Ghi chú:** Lưu toàn bộ form khi bấm "Lưu cấu hình"
- **Lớp:** 4. Tham số request · **Vị trí:** body JSON từng lần chạy · **Ghi chú:** Ưu tiên cao nhất
- **Lớp:** 5. Config riêng submodule · **Vị trí:** `AIVoice/apps/MediaComposer/config.toml` · **Ghi chú:** Orchestrator ghi đè mục `[storytelling]` trước Bước 3

`load_global_config` ( `config.py:29-198` ): nếu file chưa có → tạo từ dict mặc định; nếu có → đọc, bổ sung khoá thiếu ( `chatbot` , và `video_cfg.setdefault(key, value)` cho mọi `SD_TUNING_DEFAULTS` , dòng 193-195) để máy cũ nâng cấp vẫn có giá trị khuyến nghị. Giá trị SD mặc định ( `SD_TUNING_DEFAULTS` , `config.py:14-27` ): `sd_steps=8` , `sd_guidance=5.0` , `sd_image_width=768` , `sd_image_height=432` , `sd_output_width=1920` , `sd_output_height=1080` , `sd_video_fps=24` , `sd_face_detailer_steps=14` , `sd_face_detailer_strength=0.45` , `sd_ip_adapter_scale=0.6` , `sd_studio_render_steps=0` , `sd_studio_render_guidance=0.0` (hai khoá cuối: `0` = dùng chung giá trị steps/guidance, theo comment `mediacomposer_config.py:54-55` ). Một chi tiết cần biết: nếu `global_config.json` hỏng JSON, `load_global_config` nuốt lỗi và trả `{}` ( `config.py:197-198` ) — mọi nơi đọc sẽ rơi về hằng mặc định trong code.

Vài mặc định khác trong dict tạo mới ( `config.py:33-156` ): `translate.default_engine="ollama"` , `translate.ollama_model="qwen2.5:7b-instruct"` , `tts.default_engine="edge"` , `tts.default_voice="vi-VN-NamMinhNeural"` , `video.default_style="thuy_mac"` , `video.default_checkpoint="anything-v5"` , `video.default_llm_engine="ollama"` , `video.default_llm_model="qwen2.5:3b-instruct"` , `chatbot.model="qwen2.5:3b"` , `chatbot.keep_alive="5m"` .

`mediacomposer_config.apply_sd_params` ( `mediacomposer_config.py:79-145` ): ánh xạ `SD_PARAM_MAP` (12 khoá: `sd_steps` → `num_inference_steps` , `sd_guidance` → `guidance_scale` , `sd_image_width` → `image_width` …, `mediacomposer_config.py:26-39` ), kẹp giá trị theo `LIMITS` ( `43-56` : steps 1–60, guidance 0–20, ảnh 256–2048, output 256–3840 x 256–2160, fps 1–60, face detailer strength 0–1, ip_adapter_scale 0–1.5…; giới hạn nguyên thì ép về `int` ), rồi sửa từng dòng bằng regex trong mục `[storytelling]` thay vì parse TOML rồi ghi lại — để giữ nguyên comment giải thích trong file. Khoá chưa có thì chèn vào cuối mục. Best-effort: lỗi chỉ log cảnh báo. Test: `tests/test_mediacomposer_config.py` .

### 4.11 Chiến lược VRAM — tổng hợp mọi cơ chế

- **Cơ chế:** Mỗi bước GPU là một process riêng; thoát là driver thu hồi VRAM · **Vị trí:** `ProcessManager.start_process`
- **Cơ chế:** Orchestrator không import torch · **Vị trí:** toàn bộ `orchestrator/`
- **Cơ chế:** Adapter `finally` dọn trước khi thoát: adapter video gọi `StorytellingPipeline().release()` rồi `torch.cuda.empty_cache()` , `torch.cuda.ipc_collect()` , `gc.collect()` ; adapter TTS chỉ có `empty_cache` + `ipc_collect` + `gc.collect` ; cả hai in `hardware_released` . (Đây là lớp phòng thủ phụ — process thoát ngay sau đó thì driver cũng thu hồi.) · **Vị trí:** `adapter_video_cli.py:250-262` , `adapter_tts_cli.py:260-267`
- **Cơ chế:** 2-pass trong Bước 3: giải phóng SD trước khi nạp upscaler; OOM thì release + retry 1 lần · **Vị trí:** `batch_video_runner.run_batch`
- **Cơ chế:** Trước mỗi lần bấm chạy một bước lẻ, UI gọi `POST /api/chat/unload` → `unload_ollama` gửi `{"model":..., "keep_alive": 0}` tới `/api/generate` để Ollama nhả model chatbot khỏi VRAM. Lưu ý trung thực: (a) UI gọi vô điều kiện — khoá cấu hình `chatbot.auto_unload_before_pipeline` có trong config nhưng không nơi nào đọc; (b) nút "Chạy tự động" ( `startAutoRun` ) không gọi unload — trong chuỗi, chatbot chỉ bị chuyển sang chế độ tra cứu (dòng 7), model đã nạp sẽ tự nhả khi hết `keep_alive` (mặc định `"5m"` ) · **Vị trí:** `webui/app.js:1172-1176` ( `postPipelineAction` ), `llm.py:169-188`
- **Cơ chế:** Đổi model chatbot: nhả model cũ trước ("nếu không hai model cùng neo trong VRAM ... đúng thứ gây OOM trên máy 6GB") · **Vị trí:** `main.py:1163-1170`
- **Cơ chế:** Trợ lý AI đo mức bận GPU: có `step3` / `step4` /chuỗi tự động → `heavy` → chỉ trả lời tra cứu, không gọi LLM · **Vị trí:** `chatbot.py:498-523` , `main.py:828-` `838`
- **Cơ chế:** Kill cả cây khi dừng/đóng app → không có process mồ côi giữ VRAM · **Vị trí:** `_kill_process_tree` , `stop_all`
- **Cơ chế:** Chọn thiết bị bằng `CUDA_VISIBLE_DEVICES` · **Vị trí:** `pipeline.py:590-594`

4.12 `model_preflight` và `ollama_manager`

Preflight ( `model_preflight.py` ): chạy một thread nền lúc app mở ( `start()224-238` ). Ba bước, trạng thái mỗi bước `pending|` `running|ok|skipped|failed` , đọc qua `GET /api/models/preflight` :

- 1. Ollama: `_wanted_ollama_models` ( `73-99` ) chỉ lấy model mà cấu hình hiện tại thực sự dùng (chatbot, dịch nếu engine là ollama, LLM Bước 3 nếu là ollama) — không pull cả bộ vì mỗi model vài GB. 2. TTS: nếu thiếu `AIVoice/models/piper/vi_VN-vais1000-medium.onnx` thì chạy `src/download_models.py--engine piper` bằng venv AIVoice, `timeout=1800` . 3. MediaComposer: nếu thiếu marker `models/.preflight_ok` thì chạy `app/services/model_downloader.py--download` , `timeout=7200` ; thành công thì ghi marker để lần sau bỏ qua mà không phải hỏi HuggingFace.

Tất cả tải nặng đều qua subprocess dùng venv AIVoice ( `subprocess.run` với `timeout` , `CREATE_NO_WINDOW` , lấy 3 dòng cuối output làm thông báo lỗi — `model_preflight.py:141-169` ) — nhất quán với nguyên tắc orchestrator không import thư viện AI. Bước 2 và 3 chỉ chạy nếu đã có `AIVoice/.venv/Scripts/python.exe` , ngược lại đánh dấu `skipped` ( `202-213` ). `start()` không chạy lại nếu lượt trước đã xong, trừ khi gọi `POST /api/models/preflight` ( `force=True` ).

`ollama_manager` :

- `ensure_server` ( `87-135` ): hỏi `GET /api/tags` ; không lên và `autostart=True` → tìm `ollama.exe` (PATH, `%LOCALAPPDATA%\Programs\Ollama` , `Program Files` , `Program Files (x86)` ) → `Popen([exe, "serve"],` `creationflags=CREATE_NO_WINDOW)` → thăm dò mỗi 1s, tối đa `wait_seconds=30.0` . Có `_server_lock` để hai thread không cùng khởi động (mẫu double-checked: kiểm tra lại `is_server_up` sau khi lấy lock). Process `ollama serve` này không được `ProcessManager` quản lý nên không bị diệt khi đóng app — Ollama được coi là dịch vụ nền dùng chung. `pull_model` ( `156-222` ): gọi `POST /api/pull` với `stream: True` , đọc NDJSON `{total, completed}` tính phần trăm, chỉ báo khi nhích ≥5%; mỗi model có một lock riêng ( `_pull_locks` ) để không pull trùng; xong vẫn xác nhận lại bằng `/api/tags` ("để không báo thành công khi stream đứt giữa chừng"). `timeout=3600` . `ensure_ready` ( `225-262` ): gộp cả hai, trả `{ok, server, model_installed, reason}` ; dùng trước lượt chat ( `main.py:985` ). Cố ý dùng HTTP API thay vì CLI `ollama pull` : có tiến độ dạng số và không đẻ cửa sổ console dưới `pythonw` (docstring `13-14` ).

4.13 `video_merger` (tóm tắt)

`merge_videos` ( `video_merger.py:15-90` ): lấy FFmpeg từ `imageio_ffmpeg` trong venv AIVoice, viết `concat_list.txt` (đường dẫn dùng `/` , escape dấu `'` ), chạy `ffmpeg -y -f concat -safe 0 -i list -c copy out.mp4` (stream copy: không mã hoá lại, cực nhanh, không giảm chất lượng). Nếu thất bại (thường do khác codec/độ phân giải) → fallback một tầng mã hoá lại `libx264 -preset veryfast -crf 20` + `aac` . Luôn xoá file list trong `finally` .

## 5. Sơ đồ luồng

### 5.1 End-to-end một job (Bước 3 chạy lẻ)

### 5.2 Luồng dừng tiến trình

### 5.3 Chuỗi tự động

## 6. Hạn chế & hướng phát triển

- **Hạn chế (có dẫn chứng):** Trạng thái chuỗi tự động, log queue, task đang chạy chỉ nằm trong RAM ( `AutoRunManager._states` , `ProcessManager.*` ) · **Hệ quả:** Restart server là mất chuỗi; process con có thể mồ côi nếu server chết đột ngột (không qua `_shutdown` ) · **Hướng phát triển:** Lưu job vào bảng `jobs` (đã có schema), dùng Windows Job Object để con tự chết theo cha
- **Hạn chế (có dẫn chứng):** Bảng `jobs` chưa được ghi ( `add_job` không được gọi) · **Hệ quả:** Không có lịch sử chạy, `jobs_failed` luôn 0 · **Hướng phát triển:** Gọi `add_job` trong `start_process` , `finish_job` trong reader thread
- **Hạn chế (có dẫn chứng):** FSM không cưỡng chế điều kiện chuyển · **Hệ quả:** Có thể bấm Bước 3 khi chưa có audio (adapter sẽ báo lỗi rõ ràng) · **Hướng phát triển:** Kiểm tra tiền điều kiện ở endpoint, hiển thị nút theo trạng thái
- **Hạn chế (có dẫn chứng):** `pipeline.start_step_*` ghi trạng thái "đang chạy" trước khi `start_process` ; nếu spawn thất bại trạng thái có thể kẹt `*_GENERATING` · **Hệ quả:** Hiển thị sai trạng thái · **Hướng phát triển:** Ghi trạng thái sau khi spawn thành công hoặc rollback
- **Hạn chế (có dẫn chứng):** Một máy chỉ chạy tuần tự các bước GPU nặng; không có hàng đợi toàn cục giữa các truyện khác nhau (khoá theo `task_key` riêng từng truyện) · **Hệ quả:** Hai truyện chạy Bước 3 song song có thể OOM · **Hướng phát triển:** Thêm semaphore GPU toàn cục/hàng đợi job
- **Hạn chế (có dẫn chứng):** Tiến độ `percent` chỉ được UI diễn giải, orchestrator không lưu · **Hệ quả:** Không có thanh tiến độ bền vững khi mở lại app · **Hướng phát triển:** Parse event ở reader thread, lưu progress
- **Hạn chế (có dẫn chứng):** Mỗi kết nối SSE chiếm một thread của threadpool (generator đồng bộ, `q.get(timeout=1.0)` ) · **Hệ quả:** Nhiều tab mở cùng lúc tốn thread · **Hướng phát triển:** Chuyển sang async generator + `asyncio.Queue`
- **Hạn chế (có dẫn chứng):** `orchestrator_port` có trong config nhưng `desktop.py` cứng `PORT = 8100` · **Hệ quả:** Đổi port trong config không có tác dụng · **Hướng phát triển:** Đọc port từ config
- **Hạn chế (có dẫn chứng):** `requirements.txt` khai báo `sse-starlette` , `requests` nhưng code orchestrator dùng `StreamingResponse` và `httpx` / `urllib` · **Hệ quả:** Phụ thuộc thừa · **Hướng phát triển:** Dọn requirements
- **Hạn chế (có dẫn chứng):** `desktop._start_ollama` có định nghĩa nhưng `main()` không gọi (việc bật Ollama do `ollama_manager.ensure_server` ) · **Hệ quả:** Code chết · **Hướng phát triển:** Xoá hoặc hợp nhất
- **Hạn chế (có dẫn chứng):** Khoá `chatbot.auto_unload_before_pipeline` không được đọc; UI luôn unload trước bước lẻ nhưng chuỗi tự động thì không unload · **Hệ quả:** Cấu hình "tắt" không có tác dụng; trong chuỗi, model chatbot có thể còn giữ VRAM tới khi hết `keep_alive` · **Hướng phát triển:** Đọc cờ ở backend, gọi `unload_ollama` trong `AutoRunManager.start`
- **Hạn chế (có dẫn chứng):** Thư mục `translated/` vẫn được kiểm tra ở 4 nơi dù luồng hiện tại dịch tại chỗ trong `raw/` · **Hệ quả:** Code thừa, dễ gây hiểu nhầm khi đọc · **Hướng phát triển:** Gom logic chọn thư mục chương về một hàm ( `scan_chapters` đã làm một phần)
- **Hạn chế (có dẫn chứng):** Không có xác thực API; dựa vào việc chỉ lắng nghe `127.0.0.1` · **Hệ quả:** Phần mềm khác trên cùng máy gọi được API · **Hướng phát triển:** Token cục bộ sinh lúc khởi động
- **Hạn chế (có dẫn chứng):** Chi phí khởi động process: mỗi bước nạp lại model · **Hệ quả:** Chậm vài chục giây mỗi bước · **Hướng phát triển:** Chấp nhận; hoặc worker giữ model khi VRAM dư

## Câu hỏi hội đồng có thể hỏi

### 1. Vì sao không viết tất cả trong một chương trình Python mà phải tách orchestrator và subprocess?

Ba lý do chính: (a) VRAM — process thoát thì driver thu hồi toàn bộ VRAM kể cả CUDA context và phần rò rỉ, còn `empty_cache()` không đảm bảo điều đó; (b) xung đột thư viện — `toolCaoTruyen` và `AIVoice` có venv riêng ( `pipeline.py:150` , `411` ); (c) cô lập lỗi và dừng được — crash CUDA chỉ làm chết process con, orchestrator vẫn báo `*_FAILED` ; dừng bằng `taskkill /T /F` cả cây. Đánh đổi là tốn thời gian nạp model mỗi bước.

### 2. Làm sao orchestrator biết tiến độ của tiến trình con?

Con in từng dòng JSON `{"event":...,...}` ra stdout rồi `flush()` ( `log_json` trong mọi adapter). Orchestrator mở pipe với `stdout=PIPE, stderr=STDOUT, bufsize=1` , một reader thread đọc từng dòng đẩy vào `queue.Queue` , endpoint SSE lấy ra gửi trình duyệt. Trình duyệt `JSON.parse` và hiển thị theo `event` . Thành/bại thì dựa vào exit code.

### 3. SSE khác WebSocket thế nào, sao chọn SSE?

SSE là một response HTTP không đóng, server→client một chiều, định dạng `data:...\n\n` , trình duyệt có `EventSource` tự reconnect. WebSocket hai chiều, phức tạp hơn. Log chỉ cần một chiều, lệnh điều khiển đã có REST, nên SSE đủ và đơn giản.

### 4. `[PING]` để làm gì?

Keep-alive: nếu 1 giây không có log ( `q.get(timeout=1.0)` hết hạn) server gửi `data: [PING]` để kết nối không bị coi là chết và phát hiện client đã ngắt. UI bỏ qua dòng này.

### 5. Nếu người dùng reload trang giữa lúc Bước 3 đang chạy thì sao?

Process con vẫn chạy (do orchestrator quản lý, không phải trình duyệt). UI mở lại SSE bằng `task_key` ; nếu sentinel đã bị kết nối cũ nhận, `completed_exit_codes` giúp kết nối mới kết thúc đúng; UI còn gọi `/api/pipeline/status/{task_key}` để phân biệt "còn chạy" hay "đã xong". Chuỗi tự động chạy ở thread backend nên cũng không bị ảnh hưởng.

### 6. Dừng tiến trình trên Windows có gì khó?

`terminate()` chỉ giết process trực tiếp; các process cháu (ffmpeg…) mồ côi vẫn giữ đầu ghi pipe nên reader không nhận EOF, UI kẹt "đang chạy". Code dùng `taskkill /PID<pid> /T /F` , chờ tối đa 8s, quá hạn thì tự giải phóng bookkeeping và gửi sentinel ( `process_manager.py:151-185` ).

### 7. Phân biệt "người dùng dừng" với "lỗi" bằng cách nào?

Cả hai đều exit code khác 0. `stop_process` ghi `user_stopped_tasks` trước khi kill; callback gọi `was_user_stopped(task_key)` để đặt `CANCELLED` thay vì `*_FAILED` .

### 8. FastAPI xử lý đồng thời ra sao khi một request SSE kéo dài hàng giờ?

uvicorn chạy event loop asyncio. Endpoint `def` và generator đồng bộ được Starlette chạy trong threadpool nên việc chặn `q.get` không làm đứng event loop; endpoint `async def` như `/api/chat` dùng `await asyncio.to_thread(...)` cho hàm chặn. Công việc nặng thì đã nằm ở process khác.

### 9. State machine của truyện gồm những trạng thái nào, lưu ở đâu?

`story.json["status"]` : `CREATED` , `CRAWLING/CRAWLED/CRAWL_FAILED` , `TRANSLATING/TRANSLATED/TRANSLATE_FAILED` , `WRITING/WRITE_FAILED` , `VOICE_GENERATING/VOICE_GENERATED/VOICE_FAILED` , `VIDEO_GENERATING/VIDEO_GENERATED/VIDEO_FAILED` , `AUTOSUB_*` , `CANCELLED` ; kèm `pipeline_step` . Được mirror sang bảng `stories` của SQLite. Chuyển trạng thái xảy ra trong callback dựa trên exit code.

### 10. Chạy lại một bước có làm lại từ đầu không?

Không nhất thiết. Mỗi bước idempotent theo file: dịch bỏ qua chương đã có bản `[VI]` ; TTS bỏ qua chương đã có `.wav` ; Bước 3 đọc `batch_state.json` ( `pending→script_done→images_done→` `upscale_done→video_done` ) để làm tiếp item dở; crawl có `--continue-download` .

### 11. Vì sao vừa có `story.json` vừa có SQLite?

`story.json` nằm cạnh dữ liệu nặng, là nguồn sự thật, di chuyển thư mục là mang theo trạng thái. SQLite là bản mirror ( `_mirror_to_db` ) để thống kê nhanh cho dashboard. Lỗi DB không được phép phá luồng file. SQLite chạy WAL, bật khoá ngoại, kết nối ngắn hạn cho an toàn đa luồng.

### 12. Tham số sinh ảnh từ giao diện đi xuống Stable Diffusion bằng đường nào?

Lưu ở `global_config.json["video"]` `["sd_*"]` . Trước khi spawn Bước 3, `apply_sd_params` ghi chúng vào `[storytelling]` của `MediaComposer/config.toml` (sửa từng dòng để giữ comment, có kẹp giới hạn). Process con đọc config lúc khởi động. Tham số khác đi qua dòng lệnh, còn thiết bị đi qua biến môi trường `CUDA_VISIBLE_DEVICES` .

### 13. Làm sao để máy mới chạy được ngay?

`run.bat` tự gọi `setup.bat` nếu thiếu venv; `setup.bat` cài Python 3.11.9, dựng venv hai submodule, cài requirements, WebView2, tạo config mặc định. Khi mở app, `model_preflight` tải nền model thiếu (Ollama theo cấu hình, Piper, model SD/upscale) và `ollama_manager` tự bật Ollama, tự pull model khi cần.

### 14. Chatbot và pipeline cùng dùng GPU thì tranh chấp thế nào?

Trước khi chạy một bước lẻ, UI gọi `/api/chat/unload` (Ollama `keep_alive: 0` ) để nhả model chat (chuỗi tự động thì không gọi — đây là hạn chế đã ghi nhận). Khi có `step3` / `step4` /chuỗi tự động, `get_gpu_weight` trả `heavy` và chatbot chuyển sang chế độ tra cứu, không gọi LLM (trừ khi người dùng ép `force` ).

### 15. Có rủi ro bảo mật gì?

Server chỉ nghe `127.0.0.1` , CORS giới hạn origin cổng 8100, lệnh spawn dùng list (không qua shell), ghép video chỉ nhận basename (chống path traversal, `video_merger.py:10-12` ), SQL dùng tham số `?` . Hạn chế: chưa có xác thực token cho API cục bộ; API key Gemini được truyền cho process con qua tham số dòng lệnh ( `--llm-api-` `key` ) nên có thể thấy được trong danh sách tiến trình của máy.

### 16. Vì sao trong `desktop.py` uvicorn chạy ở thread phụ mà không phải main thread?

Vì vòng lặp GUI của pywebview ( `webview.start()` ) bắt buộc chạy trên main thread. uvicorn được tạo bằng `uvicorn.Server(config)` và `server.run` chạy trong thread daemon ( `desktop.py:101-108` ); khi đóng cửa sổ, `_shutdown` đặt `server.should_exit = True` để uvicorn tự dừng êm.

### 17. Hai truyện khác nhau cùng chạy Bước 3 thì sao?

Được phép, vì khoá chống trùng là theo `task_key =<slug>_step3` , mỗi truyện một key. Nhưng hai process SD cùng lúc rất dễ OOM trên GPU 6–8GB — hệ thống chưa có hàng đợi GPU toàn cục; đây là hạn chế đã nêu ở mục 6, hướng sửa là semaphore/hàng đợi job.

## Tóm tắt 1 phút

"Hệ thống của em có kiến trúc orchestrator – worker. Orchestrator là một server FastAPI chạy tại 127.0.0.1 cổng 8100, được bọc trong cửa sổ desktop pywebview/WebView2. Nó không tự chạy AI, mà mỗi bước — cào và dịch, sinh giọng, dựng hoạt hình — được chạy thành một tiến trình con riêng, dùng đúng virtualenv của từng module. Lý do chính là VRAM: tiến trình kết thúc thì driver thu hồi toàn bộ bộ nhớ GPU, bước sau luôn bắt đầu sạch; đồng thời lỗi của một bước không làm sập ứng dụng và có thể dừng bằng cách diệt cả cây tiến trình.

Tiến trình con báo tiến độ bằng JSON Lines trên stdout; orchestrator đọc từng dòng bằng reader thread, đưa vào hàng đợi, rồi đẩy lên giao diện theo thời gian thực bằng Server-Sent Events. Khi tiến trình kết thúc, exit code quyết định trạng thái của truyện trong một máy trạng thái lưu ở story.json và được mirror sang SQLite. Các bước đều có khả năng chạy tiếp phần dở, và có chế độ tự động chạy liên tiếp bốn bước ở backend."
