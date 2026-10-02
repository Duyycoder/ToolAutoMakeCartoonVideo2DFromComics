# Chương 14. Ngân hàng câu hỏi bảo vệ & từ điển thuật ngữ

- Chương cuối dùng để luyện tập, không dùng để học mới. Mỗi câu hỏi có gợi ý trả lời ngắn (nói trong 30–60 giây) và trỏ tới chương có giải thích đầy đủ. Mọi con số đều lấy từ code, từ báo cáo `KTPM_2022600930_DaoKhuongDuy_baocao.pdf` , hoặc từ lần chạy lại được ghi trong các chương trước.

- Cách luyện: che phần trả lời, tự nói to, rồi so sánh. Câu nào nói vấp thì đánh dấu và quay lại chương gốc.

## 1. Ngân hàng câu hỏi (66 câu)

Ký hiệu độ khó: ● dễ, ●● trung bình, ●●● khó hoặc câu bẫy.

### 1.1 Câu hỏi tổng quát

Q1 ● Em giới thiệu ngắn gọn đề tài. Hệ thống biến truyện chữ thành video hoạt hình 2D có lời đọc tiếng Việt, chạy cục bộ trên Windows với GPU 6 GB. Luồng có 4 bước: nguồn truyện và dịch, sinh giọng, dựng hoạt hình, ghép video. Một orchestrator FastAPI điều phối các worker AI chạy thành subprocess riêng. → ch00

#### Q2 Tại sao chọn đề tài này?

Truyện chữ (nhất là truyện dịch) có lượng người đọc lớn và nhu cầu chuyển thành video/audio để nghe nhìn. Làm tay rất tốn công vì mỗi chương có hàng chục cảnh. Các công cụ hiện có hoặc là dịch vụ online (khó kiểm soát dữ liệu, chi phí), hoặc là workflow node như ComfyUI (mạnh nhưng không quản lý truyện nhiều chương), hoặc là script rời (không có trạng thái thống nhất). → ch00 mục 4

#### Q3 Đầu vào, đầu ra và dữ liệu trung gian cụ thể là gì?

Đầu vào là thư mục `.md/.txt` , URL nguồn hỗ trợ, hoặc chủ đề cho AI viết. Đầu ra là `video/<chương>.mp4` và `video/TongHop_<timestamp>.mp4` . Dữ liệu trung gian gồm: `.md [VI]` , `glossary.json` , `.wav` , `context.json` (nhân vật), `state.json` (danh sách cảnh), `generated_from_script.srt` , `draft_frames/` , `final_frames/` . → ch00 mục 5.4

#### Q4 Đóng góp chính của em là gì?

(1) Kiến trúc điều phối đa tiến trình có checkpoint, giúp chuỗi dài chạy ổn định trên 6 GB VRAM. (2) Pipeline hình ảnh có kiểm soát: style lock, LoRA, IP-Adapter, Studio có cổng chất lượng và nhánh dự phòng. (3) Trợ lý AI local có cổng tài nguyên GPU và chế độ tra cứu 0-VRAM. Kèm theo là dịch 2 tầng Zero Tolerance và sáng tác nhiều chương có rolling summary. → ch00 mục 4.3

#### Q5 "Hoạt hình 2D" nhưng thực ra là slideshow đúng không?

Đúng, và em nói thẳng: mỗi cảnh là một ảnh tĩnh giữ theo thời lượng lời đọc, cắt cứng giữa các cảnh, trong luồng truyện không có zoompan/xfade (grep ra 0 kết quả). Lý do là tài nguyên: sinh video bằng mô hình khuếch tán cần VRAM lớn hơn nhiều so với 6 GB và rất chậm với vài chục cảnh mỗi chương. Hướng gần nhất là thêm filter `zoompan` (Ken Burns) và `xfade` của ffmpeg, gần như không tốn GPU. → ch11

#### Q6 Hệ thống dùng cho ai?

Người làm nội dung một mình trên máy cá nhân: nạp truyện, chọn giọng và phong cách, theo dõi log, duyệt kết quả trung gian, chạy lại bước lỗi. Hệ thống hỗ trợ chứ không thay thế biên tập viên hay họa sĩ. → ch00

#### Q7 Hệ thống chạy trên phần cứng nào?

Windows 10/11 với GPU NVIDIA. Máy đo là RTX 3060 Laptop 6 GB, i7-12650H, RAM 15,6 GB. `hardware_adapter.py` chọn `cuda_high` khi VRAM ≥ 7 GB, `cuda_low` (fp16 + CPU offload + VAE slicing) khi dưới 7 GB, và CPU fp32 khi không có CUDA. → ch13

#### Q8 Phương pháp nghiên cứu em dùng là gì?

Nghiên cứu thiết kế (design science): xác định vấn đề, đề xuất kiến trúc, hiện thực nguyên mẫu, quan sát đầu ra trung gian và tinh chỉnh. Có 5 giả thuyết H1–H5 (báo cáo Bảng 2.2). H4 và H5 đã kiểm chứng một phần. H1–H3 (Studio, LoRA/IP-Adapter, unify) chưa kiểm chứng định lượng. → báo cáo mục 2.9, 5.6

### 1.2 Kiến trúc và kỹ thuật phần mềm

#### Q9 Vì sao kiến trúc đa tiến trình, không gọi thẳng hàm Python?

Có ba lý do. (1) VRAM: PyTorch giữ bộ nhớ cache của CUDA, gọi `empty_cache` cũng không trả hết. Process thoát thì hệ điều hành thu hồi toàn bộ. Orchestrator cố ý không import torch. (2) Cô lập lỗi và xung đột thư viện: torch, onnxruntime, OpenCV, PaddleOCR dễ xung đột DLL/OpenMP trên Windows. Worker chết chỉ trả exit code. (3) Mỗi submodule có venv riêng ( `toolCaoTruyen/.venv` , `AIVoice/.venv` ), không phải hòa giải dependency. → ch01

#### Q10 Orchestrator nói chuyện với worker bằng cách nào?

Worker in JSON Lines ra stdout ( `log_json(event, data)` , flush ngay). `ProcessManager` đọc bằng `Popen(stdout=PIPE, stderr=STDOUT, bufsize=1, encoding utf-8)` trong một reader thread, rồi đẩy vào `queue.Queue` . SSE generator lấy từ queue và gửi lên UI. Thành công hay thất bại dựa vào exit code. → ch01, ch02

#### Q11 Vì sao dùng SSE mà không dùng WebSocket?

Log là luồng một chiều server → client. SSE chạy trên HTTP thường, trình duyệt có `EventSource` tự reconnect, không cần thư viện. WebSocket là hai chiều, phức tạp hơn mức cần. Riêng chatbot dùng `fetch` + NDJSON vì cần gửi POST body và hủy bằng `AbortController` . → ch02

#### Q12 Khi bấm Dừng, làm sao chắc không còn process con?

`stop_process` ghi `user_stopped_tasks` trước, rồi chạy `taskkill /PID<pid> /T /F` để diệt cả cây (worker có thể đã spawn ffmpeg hoặc script train). Sau đó chờ tối đa 8 s; quá hạn thì tự giải phóng bookkeeping với exit_code −1. Nếu chỉ `terminate()` process con trực tiếp thì cháu vẫn giữ pipe, reader thread kẹt ở `readline()` . → ch01

#### Q13 Làm sao phân biệt "người dùng hủy" với "lỗi"?

Cả hai đều ra exit code khác 0. `user_stopped_tasks` được ghi trước khi kill, và callback hỏi `was_user_stopped(task_key)` để đặt `CANCELLED` thay vì `*_FAILED` . → ch01

#### Q14 Nếu người dùng bấm chạy một bước hai lần thì sao?

Endpoint kiểm tra `process_mgr.is_running(task_key)` và `_reject_if_auto_running` , trùng thì trả HTTP 400. Trong lúc callback hậu xử lý chạy (vd merge video), `finalizing_tasks` vẫn tính task là đang chạy. → ch01, ch02

#### Q15 Reload trang có mất tiến trình không?

Không. Tiến trình chạy ở backend. `restoreRunningTasks` hỏi status các bước và nối lại SSE. Nhưng log trước lúc reload thì mất vì queue không replay. Auto-run chạy trong thread backend nên không bị ảnh hưởng; chỉ restart server mới mất chuỗi. → ch02

#### Q16 Tại sao lưu trạng thái bằng file JSON mà còn có SQLite?

`story.json` nằm cạnh dữ liệu, là nguồn sự thật, dễ đọc và sao chép. SQLite ( `stories` , `chapters` , `jobs` , WAL, FK CASCADE) là bản mirror để thống kê/tra cứu, có thể dựng lại từ file bằng `rebuild_db` . Bảng `jobs` đã có hàm nhưng chưa được gọi; hướng phát triển là dùng làm nhật ký lần chạy. → ch01

#### Q17 Truyền cấu hình cho Bước 3 thế nào?

Qua 3 kênh: (1) `apply_sd_params` ghi `sd_*` vào `config.toml` trước khi spawn, kẹp theo `LIMITS` , giữ comment. (2) Tham số CLI (style, checkpoint, render mode, LLM…). (3) Biến môi trường `MC_STORAGE_TASKS` và `CUDA_VISIBLE_DEVICES` . → ch01

#### Q18 Design pattern nào có trong hệ thống?

Strategy/Registry cho nguồn crawl ( `sources/registry.py` ), engine dịch ( `TRANSLATOR_ENGINES` ) và engine TTS ( `BaseTTSEngine` ). Adapter cho các CLI `adapter_*.py` . Singleton cho `StorytellingPipeline` và model Whisper. Observer/producer-consumer cho log queue. Callback cho cập nhật trạng thái. State machine mô tả vòng đời truyện. → ch01, ch04, ch05

#### Q19 Em kiểm thử thế nào khi các mô hình AI cần GPU?

Test tự động không nạp mô hình. Em dùng mock/stub: `FakeProcess` / `FakePipeline` cho auto-run, stub `sys.modules` cho thư viện nặng, spy lệnh được dựng, FastAPI `TestClient` cho API, và dependency injection cho Studio ( `render_plan` nhận hàm render/matter/unify qua tham số). Kết quả 178 test repo tổng (báo cáo chốt 173) và 136 test MediaComposer, đều không cần GPU. Chất lượng đầu ra AI đánh giá riêng bằng đo CJK, eval chatbot và kiểm tra thủ công. → ch13

#### Q20 CI/CD gồm những gì?

`ci.yml` : trên push/PR chạy job lint ( `ruff check` , `compileall` ), rồi job test ( `pytest -q tests/` ) trên ubuntu-latest Python 3.11, không checkout submodule. `release.yml` : khi có tag `v*` thì checkout submodule, chạy test repo tổng + MediaComposer GPU-free, rồi đóng gói release. Hạn chế: CI chỉ chạy Linux, không có E2E GPU. → ch13

#### Q21 Cài đặt cho người dùng cuối thế nào?

Installer Inno Setup dạng web installer, quyền user ( `PrivilegesRequired=lowest` ). `setup.bat` cài Python 3.11.9 nếu thiếu và chọn bản PyTorch theo GPU (RTX 50 → cu128, NVIDIA khác → cu124, không có → CPU). `run.bat` tự gọi setup nếu thiếu venv. `model_preflight` tải model nền khi mở app lần đầu. → ch13

#### Q22 Bảo mật: API không có xác thực, có nguy hiểm không?

Server chỉ bind `127.0.0.1:8100` , CORS chỉ cho `127.0.0.1:8100` / `localhost:8100` , nên máy khác trong mạng không gọi được. Có chống path traversal ở chỗ nhận tên file ( `video_merger._select_files` chỉ nhận basename, `resolve_path_within_directory` dùng realpath + commonpath). Hạn chế thật: không auth, API key truyền qua tham số CLI nên lộ trong danh sách process, ghi JSON không atomic. Nếu mở cho nhiều người dùng thì phải thêm auth và secret store. → ch13

### 1.3 AI và lý thuyết: LLM và dịch

#### Q23 LLM hoạt động thế nào?

LLM là Transformer decoder được huấn luyện để dự đoán token kế tiếp. Self-attention cho mỗi token "nhìn" các token trước để tính biểu diễn theo ngữ cảnh: `Attention(Q,K,V) = softmax(QKᵀ/√d_k)·V` . Sinh văn bản là

lặp: tính phân phối xác suất token kế, lấy mẫu theo `temperature` / `top_p` / `top_k` , nối vào và lặp lại. → ch04

#### Q24 Vì sao chạy LLM local bằng Ollama?

Không gửi nội dung truyện ra ngoài, không tốn phí theo token, chạy offline. Ollama đóng gói llama.cpp, nạp model GGUF đã lượng tử hóa nên model 7B vừa VRAM tiêu dùng. Có API `/api/chat` và endpoint tương thích OpenAI. Hỗ trợ `keep_alive=0` để nhả VRAM ngay trước khi sinh ảnh. → ch04

#### Q25 Quantization là gì, có làm giảm chất lượng không?

Lưu trọng số bằng ít bit hơn (vd 8-bit `Q8_0` cho HY-MT2 thay vì 16-bit), kèm hệ số scale theo từng khối. Bộ nhớ giảm khoảng 2–4 lần. Sai số làm tròn làm chất lượng giảm nhẹ, và giảm nhiều hơn khi xuống 2–3 bit. Đây là đánh đổi để model vừa 6 GB. → ch04

#### Q26 Làm sao đảm bảo bản dịch không sót chữ Hán?

Dịch 2 tầng. Tầng 1 dịch từng chunk; nếu bị cắt cụt ( `done_reason==` `'length'` ) thì gọi lại với `num_predict ×1.5` ; còn chữ Hán thì dịch lại ở temperature 0.02. Tầng 2 kiểm tra từng đoạn theo 3 lỗi (untranslated, leak, content_missing) với chính sách Zero Tolerance: chỉ một ký tự trong dải `[`一`-`鿿`]` cũng tính là lỗi. Vá tối đa 3 lượt; thất bại thì chèn marker `[[MISSING_CHUNK:n]]` và ghi `.translation_report.json` . Kết quả đo: 0/214.034 ký tự CJK trên 26 chương. Lưu ý: tiêu chí này đo "không sót chữ", không đo độ đúng ngữ nghĩa. → ch04

#### Q27 Glossary hoạt động thế nào? Vì sao chỉ chèn 20 thuật ngữ?

Ba lớp: `common_idioms` < `global_glossary.json` < `glossary.json` của truyện. Chỉ thêm key mới, không ghi đè. Mỗi chunk chỉ chèn những thuật ngữ thực sự xuất hiện trong chunk, tối đa 20, để không tốn context và không làm model nhỏ bị nhiễu (glossary chủ động). Sau mỗi chương, LLM trích thêm thuật ngữ mới (JSON mode). → ch04

#### Q28 Sáng tác nhiều chương làm sao giữ mạch truyện khi context có hạn?

Rolling summary: sau mỗi chương, LLM tóm tắt 2–3 câu ở temperature 0.3, cộng dồn và chỉ giữ 2500 ký tự cuối, đưa vào prompt chương sau. Số từ mỗi chương bị kẹp trong [200, 4000], mặc định 800 ( `pipeline.py:28-33` ). → ch04

### 1.4 AI và lý thuyết: TTS

#### Q29 TTS hoạt động thế nào?

Văn bản được chuẩn hóa (số → chữ), chuyển thành âm vị/token, rồi mô hình neural sinh ra đặc trưng âm thanh (mel-spectrogram hoặc latent) và vocoder chuyển thành sóng âm. Piper dùng VITS: kết hợp VAE, normalizing flow và huấn luyện đối kháng, sinh sóng âm end-to-end; `length_scale = 1/speed` điều chỉnh tốc độ. XTTSv2 dùng GPT sinh token âm thanh có điều kiện theo giọng tham chiếu, rồi decoder ra waveform 24 kHz. → ch05

#### Q30 Vì sao có 5 engine?

Mỗi engine là một đánh đổi: Edge (online, tự nhiên, nhanh, cần mạng); Piper (offline, rất nhẹ, chạy CPU, giọng kém tự nhiên hơn); Kokoro/VieNeu (offline, tự nhiên hơn, cần GPU); XTTSv2 (clone giọng từ mẫu, nặng nhất, khoảng 5,6 GB trọng số). Adapter pattern ( `BaseTTSEngine.generate` ) giúp thêm engine mà không sửa pipeline. → ch05

#### Q31 LUFS là gì, vì sao −14?

LUFS đo độ to cảm nhận theo chuẩn ITU-R BS.1770 (có lọc K-weighting và gating), khác với đo peak. −14 LUFS là mức chuẩn hóa phổ biến của nền tảng video/stream, giúp các chương to đều nhau. Sau khi chuẩn hóa, peak được scale về 0.98 để không clip. → ch05

#### Q32 Vì sao phải chunk văn bản trước khi TTS?

Mô hình có giới hạn độ dài đầu vào (XTTS khoảng 250 ký tự), và câu quá dài làm giọng lạc nhịp. Code chunk theo `max_words=30` , `max_chars=240` , sinh song song rồi ghép với 0.3 s khoảng lặng. Số worker khác nhau theo engine: GPU = 1, Piper = 6, Edge = 3 có stagger để không bị chặn tần suất. → ch05

### 1.5 AI và lý thuyết: sinh ảnh

#### Q33 Stable Diffusion sinh ảnh như thế nào?

Khi huấn luyện, người ta thêm nhiễu Gauss dần vào ảnh (forward process) và dạy mạng U-Net dự đoán nhiễu đã thêm ở mỗi mức nhiễu t, có điều kiện theo text. Khi sinh, bắt đầu từ nhiễu thuần và lặp: U- Net dự đoán nhiễu, scheduler trừ bớt nhiễu, cho đến khi ra ảnh sạch. SD làm việc trong latent space: VAE nén ảnh 8 lần mỗi chiều (768×432 → latent 4×54×96) nên nhanh và nhẹ hơn nhiều so với làm trên pixel. Text đi vào qua CLIP text encoder, và U- Net "đọc" text bằng cross-attention. → ch07

#### Q34 Classifier-Free Guidance là gì? Vì sao CFG = 5.0?

Mỗi bước U-Net chạy hai lần, một có prompt và một không (hoặc với negative prompt), rồi ngoại suy: `ε=ε_uncond + s·(ε_cond −ε_uncond)` . `s` càng lớn thì ảnh càng bám prompt, nhưng quá lớn sẽ bị cháy màu hoặc méo. Em đo được: guidance 1.5 với 8 bước làm model bỏ qua prompt và ra texture trừu tượng, nên nâng lên 5.0 (comment trong `app/config.py:46-50` ). → ch07

#### Q35 Vì sao chỉ 8 bước mà vẫn ra ảnh?

Nhờ Hyper-SD LoRA (ByteDance), một LoRA được chưng cất (distillation) để model đi đường khử nhiễu ngắn với ít bước. Khi steps < 15, code dùng `EulerDiscreteScheduler` + `Hyper-SD15-8steps-CFG-lora` (bản dùng được với CFG > 1). Khi steps ≥ 15 thì dùng chế độ chất lượng DPM-Solver++ Karras, không dùng Hyper-SD ( `image_generator.py:23, 339-419` ). → ch07

#### Q36 Vì sao dùng SD1.5 mà không dùng SDXL/Flux?

VRAM 6 GB: SD1.5 có U-Net khoảng 0,86 tỷ tham số, chạy fp16 thoải mái. SDXL và Flux lớn hơn nhiều, phải offload nên rất chậm. Hệ sinh thái SD1.5 cho anime rất lớn: checkpoint anything-v5, IP- Adapter Plus Face, Hyper-SD, cộng thêm việc tự train LoRA nhanh ở 512 px. Đánh đổi là chất lượng chi tiết (tay, mặt nhỏ) kém hơn. → ch07

#### Q37 Seed là gì? Có tái lập được ảnh không?

Seed khởi tạo bộ sinh số ngẫu nhiên cho nhiễu ban đầu. Cùng seed, prompt, model, scheduler, số bước và kích thước thì ra cùng ảnh (xấp xỉ, có thể lệch rất nhẹ do phần cứng/fp16). Seed −1 thì random trong [0, 2147483647], và `accepted_seed` được lưu vào `state.json` để reroll/tái lập. → ch07

#### Q38 Negative prompt có tác dụng gì?

Negative prompt thay cho nhánh "không điều kiện" trong CFG, nên ảnh bị đẩy ra xa các khái niệm trong đó (vd chữ, watermark, tay dị dạng). Trong code, style preset có phần negative sau dấu `---` trong `resource/image_presets/<style>.txt` . → ch06, ch07

#### Q39 Prompt dài hơn 77 token thì sao?

CLIP text encoder chỉ nhận 77 token. Code dùng `compel` với `truncate_long_prompts=False` để chia prompt thành nhiều đoạn và nối embedding, có hỗ trợ trọng số `(tag:1.35)` . Ngoài ra prompt bị kẹp 75 từ bằng `_clamp_prompt_words` . → ch06, ch07

#### Q40 Có bug kỹ thuật nào khó mà em đã tìm ra?

Dải đen dọc 512/384 px ở 9/41 frame (22%). Nguyên nhân là VAE tiling + fp16 overflow; vị trí dải khớp biên ô tile. Em sửa bằng cách chỉ bật tiling khi cạnh ≥ 1024 ( `VAE_TILING_MIN_EDGE` ), thêm `has_dead_region` để phát hiện cột/hàng chết rồi thử lại với seed mới (tối đa 2 lần), và khóa lại bằng `tests/test_vae_dead_region.py` . Một lỗi khung đen khác đến từ Real-ESRGAN fp16, sửa bằng fp32 + kiểm độ sáng + fallback PIL. → ch07, ch13

### 1.6 AI và lý thuyết: nhất quán nhân vật và Studio

#### Q41 LoRA là gì? Vì sao không fine-tune toàn bộ?

LoRA giữ nguyên trọng số gốc W và học một cập nhật hạng thấp `ΔW =` `B·A` (A: r×k, B: d×r, r nhỏ), được scale theo α/r. Chỉ gắn vào các phép chiếu attention `to_q/to_k/to_v/to_out.0` . Với LoRA style `thuy_mac` rank 8: 1.594.368 tham số, khoảng 0,19% U-Net, file 6,4 MB. Fine-tune toàn bộ tốn VRAM và dữ liệu hơn nhiều, dễ quên kiến thức cũ, file hàng GB. → ch08

#### Q42 IP-Adapter khác LoRA thế nào?

LoRA học một khái niệm vào trọng số, phải train. IP-Adapter không cần train cho từng nhân vật: ảnh tham chiếu được encode bằng CLIP image encoder thành token ảnh, rồi đưa vào một nhánh cross-attention riêng (decoupled) song song với text. `scale` (0.6) điều chỉnh mức ảnh hưởng. Code dùng IP-Adapter Plus Face SD1.5. Cảnh không có nhân vật thì đưa ảnh xám với scale 0. → ch08

#### Q43 Giữ khuôn mặt nhân vật giữa các cảnh bằng những cơ chế nào?

Ba kênh điều kiện. (1) Text: `style_lock` ghép style → `(action:1.35)` → nội dung và lọc tag trôi style; keywords ngoại hình cố định từ hồ sơ nhân vật. (2) Ảnh: IP-Adapter với ảnh ref của nhân vật chính. (3) Trọng số: LoRA nhân vật (0.8) + LoRA style. Có thêm face detailer tùy chọn với 3 cổng chất lượng. Hạn chế thành thật: chưa đo CLIP similarity định lượng (H2 chưa kiểm chứng). → ch08

#### Q44 Chưa có ảnh nhân vật thì train LoRA bằng gì?

(bài toán con gà quả trứng) `character_bootstrap` : sinh 1 ảnh seed 512×640 từ keywords, dùng IP-Adapter scale 0.7 sinh khoảng 14 biến thể cùng khuôn mặt (tối đa 26 lần thử), crop mặt, đủ ≥ 5 ảnh thì train LoRA rank 16. Hạn chế: dataset tự sinh nên LoRA học lại cả khiếm khuyết của ảnh seed, và chưa dùng prior preservation. → ch08

#### Q45 Studio compositing là gì, vì sao cần?

SD1.5 vẽ nhân vật nhỏ trong khung rộng thường hỏng mặt/tay, và nhiều nhân vật trong một prompt dễ bị trộn đặc điểm. Studio tách ra: sinh nền riêng (có cache theo location + thời điểm), sinh từng nhân vật riêng khung 512×768 trên nền xám, tách nền bằng rembg isnet-anime ra alpha, ghép theo layout (painter's algorithm, `C =αF +` `(1−α)B` ), rồi chạy unify pass img2img strength 0.28 để hòa ánh sáng/nét. → ch09

#### Q46 Vậy tại sao Studio không phải mặc định?

Thực nghiệm cho thấy isnet-anime được huấn luyện trên anime màu nên với phong cách thủy mặc đơn sắc, alpha coverage chỉ 0,003, lớp nhân vật gần như rỗng. Cổng alpha coverage [0.05, 0.95] chặn lại và lùi về Classic. Ngoài ra còn lùi về Classic khi cảnh có hơn 3 nhân vật hoặc có tương tác (hug, fight…). Vì vậy mặc định mã nguồn là Classic, Studio là tùy chọn và được bật trên máy demo. Báo cáo ghi "studio mặc định" là theo cấu hình demo; em sẽ đính chính nếu được hỏi. → ch09, ch00 mục 7

### 1.7 AI và lý thuyết: phân cảnh, Whisper, RAG

#### Q47 LLM chia cảnh như thế nào? Nếu LLM trả JSON sai thì sao?

Văn bản được tách thành đơn vị đánh số `[i]` (bỏ quảng cáo, gộp đoạn < 5 từ, chia đoạn > 60 từ). LLM (JSON mode, temperature 0.3) gom các đơn vị thành cảnh. Code kiểm 3 bất

biến: phủ kín 0..N−1 không trùng, mỗi cảnh liên tiếp, đúng thứ tự. Sai thì fallback sang `md_parser` , và response hỏng được ghi log. Sau đó gộp cảnh < 8 s, chia đôi cảnh > 27 s. → ch06

#### Q48 Thời lượng mỗi cảnh tính thế nào để khớp lời đọc?

Đọc độ dài WAV chính xác (wave → ffmpeg → pydub, hỏng hết thì báo lỗi, không đoán). Chia theo tỷ lệ số từ: `dur_i = T·w_i/Σw` , cảnh cuối bị ép kết thúc đúng T. Không dùng Whisper trong luồng truyện (tắt cưỡng bức, `adapter_video_cli.py:222` ) vì tốn 2–3 GB VRAM và khoảng 60 s mỗi chương, trong khi TTS đọc đều nên tỷ lệ số từ đủ chính xác. → ch06, ch10

#### Q49 Whisper dùng ở đâu, hoạt động thế nào?

Chỉ dùng trong công cụ Autosub rời. Whisper là Transformer encoder- decoder: audio 16 kHz → log-mel spectrogram theo cửa sổ 30 s → encoder → decoder sinh text và timestamp. Code dùng faster-whisper (CTranslate2) với `beam_size=5` , `word_timestamps=True` , VAD (khoảng lặng tối thiểu 500 ms), rồi tự cắt câu theo dấu câu dựa trên timestamp từng từ. → ch10

#### Q50 Chatbot có dùng vector database/embedding không?

Không. Truy xuất là lexical: khớp từ khóa không dấu, trọng số IDF `ln(N/(1+df))` , header khớp ×1.5, bonus 1.3 cho file của tab đang mở, chuẩn hóa theo tổng IDF câu hỏi, cổng 0.75. Lý do: KB nhỏ (179 mảnh), toàn thuật ngữ kỹ thuật tiếng Việt; embedding model thêm VRAM và độ trễ. Em đã đo: IDF 28/28 so với BM25 27/28 ở cùng mức chặn ( `kb_index.py:13-22` ). Đo lại hôm 29/09: QA 25/28, từ chối 7/8. Điều kiện để đổi sang BM25/embedding: KB vượt khoảng 240 mảnh. Phần SentenceTransformer + FAISS trong repo là semantic cache của TTS, không phải chatbot. → ch12

#### Q51 Chatbot làm sao không "bịa"?

(1) Cổng điểm: dưới 0.75 và câu không nói về truyện thì trả lời từ chối cố định, không gọi LLM. (2) System prompt 7 quy tắc: chỉ dùng `<tailieu>` , suy luận ngoài tài liệu phải dán nhãn, cấm bịa tên nút/tham số, kết bằng "Nguồn: ". (3) Nội dung truyện đặt trong `<noidungtruyen>` và được coi là dữ liệu, không phải chỉ thị (chống prompt injection). Vẫn còn rủi ro: 1/8 câu ngoài phạm vi lọt cổng. → ch12

#### Q52 Chatbot có tranh GPU với Bước 3 không?

Không. `get_gpu_weight` trả `heavy` khi step3/step4/chuỗi tự động đang chạy. Lúc đó `/api/chat` trả HTTP 409 kèm `lookup_answer` (3 mảnh KB nguyên văn, ngưỡng 0.30, 0 VRAM). Trước mỗi bước, UI gọi `/api/chat/unload` ( `keep_alive=0` ) để Ollama nhả model. → ch12

#### Q53 "Agent" trong chatbot có tự chạy pipeline không?

Không tự chạy. Đó là router regex tất định ( `route_intent` ), không phải vòng ReAct. L1 (báo cáo trạng thái) đọc thẳng từ đĩa. L2/L3 (chọn truyện, chạy bước) chỉ trả về `agent_action` , UI hiện thẻ xác nhận, người dùng bấm thì mới gọi API. → ch12

### 1.8 Đánh giá và kết quả

#### Q54 Em đánh giá chất lượng đầu ra bằng gì? Có MOS/CLIP/FID không?

Đã đo: rò chữ Hán 0/214.034 ký tự; khung đen đã kiểm hồi quy; đồng bộ tổng thời lượng cảnh với WAV trên video mẫu; truy xuất chatbot 89,3% QA và 87,5% từ chối. Chưa đo MOS (chất lượng giọng), CLIP similarity (nhất quán nhân vật), FID. Lý do: chưa có tập ảnh chuẩn và người nghe. Báo cáo ghi rõ không điền số giả định. → báo cáo 5.5, ch13

#### Q55 Kết quả kiểm thử tự động?

Báo cáo chốt ngày 12/09/2026: 173 passed, 0 failed, 7,86 s, 21 file. Chạy lại ngày 29/09/2026: 178 passed (22 file), và MediaComposer 136 passed. Kiểm thử hệ thống: 15/16 ca đạt; ca TC16 (từ chối ≥ 90%) chưa đạt. → ch13

#### Q56 Hiệu năng và VRAM thế nào?

Trên RTX 3060 Laptop 6 GB: Bước 3 đỉnh khoảng 4,0 GB; video 45 s mất khoảng 2,6 phút (≈ 3,47× thời lượng); Piper khoảng 2,7 phút/chương. Các bước khác gần mức nền. Batch 2-pass (sinh hết ảnh, release SD, rồi mới upscale) để hai model nặng không cùng nằm trong VRAM. → ch11, ch13

#### Q57 Số liệu chỉ đo trên một máy, có suy rộng được không?

Không suy rộng, và báo cáo cũng nói vậy. Có cơ chế thích nghi phần cứng ( `cuda_high` / `cuda_low` / `cpu` ) nhưng chưa benchmark trên nhiều GPU. Hướng phát triển: bộ benchmark nhiều cấu hình. → báo cáo 5.6

### 1.9 Bản quyền và đạo đức

#### Q58 Cào truyện từ web có vi phạm bản quyền không?

Có rủi ro, và em thiết kế để tránh: nguồn mặc định là `local` ( `crawler.default_site = "local"` ) với tác phẩm public domain (vd Tây Du Ký), hoặc truyện do AI tự sáng tác. Crawler web là tùy chọn kỹ thuật, người dùng tự chịu trách nhiệm với nguồn mình chọn. Em cũng thừa nhận crawler có kỹ thuật vượt Cloudflare và không xử lý robots.txt. Nếu làm sản phẩm thì chỉ nên dùng với nội dung có quyền. → ch03

#### Q59 Dữ liệu train LoRA phong cách lấy từ đâu?

Met Museum Open Access API, chỉ lấy ảnh `isPublicDomain` /CC0, có `manifest.json` ghi nguồn. Ảnh được lọc thư pháp/triện/tranh màu bằng metadata và pixel, cắt ô trượt 512. → ch08

#### Q60 Giấy phép các mô hình?

Báo cáo cam kết dùng mô hình có giấy phép cho phép dùng lại. Cần nói cẩn thận: SD1.5 dùng giấy phép CreativeML OpenRAIL-M (cho phép dùng lại, có điều khoản hạn chế sử dụng có hại). Checkpoint cộng đồng (anything-v5…) cần kiểm tra giấy phép riêng. XTTSv2 có giấy phép riêng của Coqui, hạn chế thương mại. Edge TTS là dịch vụ của Microsoft. Proxy Gemini-API dùng cookie là tùy chọn khi phát triển, có thể vi phạm điều khoản nên không dùng khi demo. Nếu không chắc về một giấy phép cụ thể thì nói "em sẽ kiểm tra lại", đừng khẳng định. → ch05, ch07

#### Q61 Có nguy cơ tạo nội dung độc hại/deepfake không?

Có. `safety_checker=None` trong SD pipeline ( `image_generator.py:201-206` ) và Gemini đặt `BLOCK_NONE` để dịch truyện có bạo lực mà không bị chặn nhầm. Voice clone (XTTS) có thể bị lạm dụng giả giọng. Giảm thiểu: ứng dụng chạy cục bộ cho một người dùng, không phát tán tự động; hướng phát triển là thêm bộ lọc nội dung và cảnh báo khi clone giọng. → ch05, ch07

### 1.10 So sánh với sản phẩm khác

#### Q62 So với ComfyUI thì hơn gì?

ComfyUI rất mạnh cho thử nghiệm một ảnh/một workflow, nhưng không quản lý truyện nhiều chương, không có dịch, TTS, dựng video theo thời lượng, không có checkpoint theo chương. Hệ thống của em là ứng dụng quy trình hướng người dùng cuối. Đánh đổi là kém linh hoạt hơn khi đổi mô hình. → ch00

#### Q63 So với dịch vụ text-to-video online (Runway, Pika…)?

Dịch vụ online sinh clip chuyển động thật chất lượng cao, nhưng clip ngắn, khó giữ nhân vật qua nhiều cảnh, tốn phí, dữ liệu gửi ra ngoài, và không có pipeline truyện → giọng đọc. Hệ thống của em miễn phí, cục bộ, giữ nhân vật bằng LoRA/IP-Adapter, nhưng chỉ ra ảnh tĩnh. → ch00, ch11

#### Q64 So với MoneyPrinterTurbo?

Một phần code MediaComposer ( `video.py` , `composer.py` , `material.py` ) kế thừa kiểu MoneyPrinterTurbo, dùng cho luồng stock footage và Autosub. Luồng truyện → hoạt hình (storytelling/, studio/, batch runner, style lock, LoRA) là phần em xây mới. Khi được hỏi thì nói rõ ranh giới này. → ch11

### 1.11 Phần nào tự làm, phần nào dùng thư viện

#### Q65 Phần nào em tự viết, phần nào là thư viện?

Dùng thư viện/mô hình có sẵn: FastAPI, Selenium, BeautifulSoup, Ollama + model Qwen/HY-MT2, các engine TTS, diffusers + SD1.5 checkpoint, Hyper-SD, IP-Adapter, peft, Real-ESRGAN, rembg, faster-whisper, ffmpeg, pyloudnorm. Em tự viết: toàn bộ orchestrator (ProcessManager, pipeline, auto-run, storage, SSE, cấu hình, preflight), webui, adapter CLI, dịch 2 tầng + glossary chủ động, chunking TTS và hậu kỳ âm thanh, phân cảnh có kiểm bất biến, timeline, style lock, batch 2-pass + resume, character bootstrap, Studio pipeline, chatbot IDF + gating + agent, bộ test và CI. Mô hình duy nhất em tự train là LoRA phong cách `thuy_mac` (và LoRA nhân vật tự động nếu bật). → ch00 mục 6

#### Q66 Em có hiểu code do AI hỗ trợ viết không?

(câu có thể bị hỏi) Trả lời trung thực. Nếu có dùng trợ lý lập trình thì nói có dùng như công cụ, và chứng minh hiểu bằng cách giải thích một quyết định cụ thể kèm bằng chứng: vì sao `taskkill /T` thay vì `terminate()` , vì sao CFG 5.0 thay vì 1.5, vì sao IDF thay vì BM25 (có số đo). Chuẩn bị mở code tại `process_manager.py` , `style_lock.py` , `image_generator.py` và giải thích từng dòng. → ch01, ch07, ch12

## 2. Xử lý câu hỏi không biết và câu hỏi bẫy

### 2.1 Năm nguyên tắc

- 1. Không bịa số. Chưa đo thì nói "em chưa đo chỉ số đó". Sau đó nói cái em đã đo và cách em sẽ đo cái còn thiếu. 2. Tách "code có" và "code chạy mặc định". Nhiều câu bẫy xoáy vào chỗ này (Studio, face detailer, auto-train LoRA, Whisper). 3. Nhận hạn chế, rồi đưa ra hướng khắc phục cụ thể, tốt nhất có tên hàm/filter (vd `zoompan` , `xfade` , `atomic write` bằng file tạm + `os.replace` ). 4. Trả lời thẳng câu hỏi trước, giải thích sau. Câu đầu nên là có/không/con số. 5. Nếu hiểu câu hỏi không chắc thì hỏi lại: "Thầy/cô hỏi về … đúng không ạ?"

### 2.2 Mẫu câu

- **Tình huống:** Không biết · **Mẫu câu:** "Phần này em chưa tìm hiểu sâu. Theo em hiểu thì…, em xin phép tìm hiểu thêm và bổ sung sau."
- **Tình huống:** Chưa đo · **Mẫu câu:** "Chỉ số đó em chưa đo. Hiện em có … (số đã đo). Để đo, em sẽ …"
- **Tình huống:** Bị chỉ ra lỗi · **Mẫu câu:** "Dạ đúng, đó là hạn chế. Nguyên nhân là … Cách sửa là …"
- **Tình huống:** Câu hỏi so sánh không công bằng · **Mẫu câu:** "Hai hướng giải quyết bài toán khác nhau. Điểm mạnh của hướng kia là …, còn hệ thống em ưu tiên …"
- **Tình huống:** Câu hỏi ngoài phạm vi · **Mẫu câu:** "Đề tài giới hạn ở … Phần đó nằm ngoài phạm vi, nhưng có thể mở rộng bằng …"

### 2.3 Các câu bẫy hay gặp

- **Câu bẫy:** "Em tự huấn luyện Stable Diffusion à?" · **Bẫy ở đâu:** Nói "có" là sai · **Trả lời đúng:** Không. Em dùng checkpoint có sẵn, chỉ train LoRA (vài triệu tham số)
- **Câu bẫy:** "Chatbot của em dùng vector DB đúng không?" · **Bẫy ở đâu:** Tài liệu cũ nhắc FAISS · **Trả lời đúng:** Không. Lexical IDF. FAISS thuộc semantic cache TTS, mặc định tắt
- **Câu bẫy:** "Whisper đồng bộ phụ đề trong video truyện?" · **Bẫy ở đâu:** Whisper bị tắt trong luồng truyện · **Trả lời đúng:** Timeline theo tỷ lệ số từ; Whisper chỉ có trong Autosub
- **Câu bẫy:** "Studio là chế độ mặc định?" · **Bẫy ở đâu:** Báo cáo ghi mặc định, code là classic · **Trả lời đúng:** Xem Q46
- **Câu bẫy:** "Có hiệu ứng chuyển cảnh không?" · **Bẫy ở đâu:** Không có · **Trả lời đúng:** Xem Q5
- **Câu bẫy:** "Face detailer luôn chạy?" · **Bẫy ở đâu:** Mặc định tắt ( `enable_face_detailer=False` ) · **Trả lời đúng:** Tùy chọn, tắt mặc định vì chậm
- **Câu bẫy:** "Phụ đề có cháy vào video không?" · **Bẫy ở đâu:** `burn_subtitles=False` mặc định · **Trả lời đúng:** Có tùy chọn, mặc định tắt
- **Câu bẫy:** "Temperature thấp là để làm gì?" · **Bẫy ở đâu:** Không nói "cho chính xác" chung chung · **Trả lời đúng:** Temperature chia logit trước softmax; thấp làm phân phối nhọn nên chọn gần như tất định; dịch cần ổn định nên dùng 0.02–0.3
- **Câu bẫy:** "Có dùng LangChain không, sao không dùng?" · **Bẫy ở đâu:** — · **Trả lời đúng:** Không. Pipeline đơn giản, gọi HTTP trực tiếp để kiểm soát `num_ctx` , `keep_alive` , `think=false` ; thêm framework là thêm lớp trừu tượng không cần
- **Câu bẫy:** "Sao không dùng Docker?" · **Bẫy ở đâu:** — · **Trả lời đúng:** Người dùng đích là máy Windows cá nhân; GPU passthrough và WebView2 trong Docker trên Windows phức tạp; installer + venv đơn giản hơn
- **Câu bẫy:** "Chạy CPU được không?" · **Bẫy ở đâu:** — · **Trả lời đúng:** Được về mặt kỹ thuật (profile `cpu` , fp32), nhưng sinh ảnh rất chậm, không thực tế
- **Câu bẫy:** "Sao metruyenchu trên UI không chạy?" · **Bẫy ở đâu:** Bug đã biết · **Trả lời đúng:** Tên option UI ( `metruyenchu` , `tangthuvien` ) không khớp key registry ( `metruyenchuvn` ) nên `get_source` báo ValueError; sửa bằng map tên (ch03)
- **Câu bẫy:** "API key có bị lộ không?" · **Bẫy ở đâu:** Có rủi ro · **Trả lời đúng:** Key truyền qua CLI args, thấy được trong process list; hướng sửa là truyền qua biến môi trường hoặc stdin

## 3. Từ điển thuật ngữ A–Z (124 thuật ngữ)

### AdamW
- **Giải thích dễ hiểu:** Thuật toán tối ưu Adam có weight decay tách riêng, giúp train ổn định
- **Trong dự án:** Train LoRA: lr 1e-4 (nhân vật), 8e-5 (style), wd 1e-2

### Adapter pattern
- **Giải thích dễ hiểu:** Lớp bọc để các thành phần khác giao diện nói chung một "ngôn ngữ"
- **Trong dự án:** `adapter_cli.py` , `adapter_tts_cli.py` , `adapter_video_cli.py`

### Alpha channel
- **Giải thích dễ hiểu:** Kênh độ trong suốt của pixel, 0 = trong suốt, 1 = đục
- **Trong dự án:** Lớp nhân vật Studio sau matting

### Alpha compositing
- **Giải thích dễ hiểu:** Ghép lớp theo phép "over": `C =αF + (1−α)B`
- **Trong dự án:** `studio/compositor.py`

### Alpha coverage
- **Giải thích dễ hiểu:** Tỷ lệ pixel có alpha > 16; dùng làm cổng chất lượng matting
- **Trong dự án:** Ngưỡng [0.05, 0.95], `studio_pipeline.py`

### amix
- **Giải thích dễ hiểu:** Filter ffmpeg trộn nhiều luồng âm
- **Trong dự án:** Trộn giọng + BGM (0.15), `video_assembler.py`

### ASGI
- **Giải thích dễ hiểu:** Chuẩn giao tiếp server–ứng dụng Python bất đồng bộ
- **Trong dự án:** uvicorn chạy FastAPI

### Attention
- **Giải thích dễ hiểu:** Cơ chế cho mỗi token tính trọng số "chú ý" tới token khác
- **Trong dự án:** Lõi của LLM, CLIP, U-Net cross-attention

### Auto-run
- **Giải thích dễ hiểu:** Chuỗi tự động chạy step1→2→3→5
- **Trong dự án:** `orchestrator/auto_run.py`

### BeautifulSoup
- **Giải thích dễ hiểu:** Thư viện parse HTML thành cây để tìm phần tử
- **Trong dự án:** Parser 69shuba

### BM25
- **Giải thích dễ hiểu:** Hàm xếp hạng lexical cải tiến TF-IDF (bão hòa tần suất, chuẩn hóa độ dài)
- **Trong dự án:** Có trong `kb_index.search()` nhưng luồng chính không gọi

### BS.1770
- **Giải thích dễ hiểu:** Chuẩn ITU đo độ to cảm nhận (LUFS)
- **Trong dự án:** pyloudnorm ở Bước 2

### Callback
- **Giải thích dễ hiểu:** Hàm truyền vào để được gọi khi sự kiện xảy ra
- **Trong dự án:** `on_completed` của `start_process`

### CFG (Classifier-Free Guidance)
- **Giải thích dễ hiểu:** Trộn dự đoán có/không điều kiện để ảnh bám prompt
- **Trong dự án:** `guidance_scale = 5.0`

### Checkpoint (mô hình)
- **Giải thích dễ hiểu:** File trọng số đầy đủ của một mô hình
- **Trong dự án:** `anything-v5` , `dreamshaper-8`

### Checkpoint (tiến độ)
- **Giải thích dễ hiểu:** Điểm lưu tiến độ để chạy tiếp
- **Trong dự án:** `batch_state.json` , `state.json` , `.crawler_state.json`

### Chunking
- **Giải thích dễ hiểu:** Chia văn bản thành mảnh nhỏ để xử lý
- **Trong dự án:** Dịch (350–1000 ký tự), TTS (30 từ/240 ký tự), KB (400 ký tự)

### CLIP
- **Giải thích dễ hiểu:** Mô hình học chung ảnh–văn bản trong một không gian embedding
- **Trong dự án:** Text encoder của SD; image encoder của IP-Adapter; gate face detailer

### Cloudflare challenge
- **Giải thích dễ hiểu:** Trang kiểm tra "Just a moment" chặn bot
- **Trong dự án:** Crawler dùng Chrome thật, không headless

### compel
- **Giải thích dễ hiểu:** Thư viện tạo prompt embedding có trọng số, vượt 77 token
- **Trong dự án:** `image_generator.py:571-631`

### concat demuxer
- **Giải thích dễ hiểu:** Chế độ ffmpeg đọc danh sách file + duration để nối
- **Trong dự án:** `duration.txt` → `raw_video.mp4`

### Context window ( `num_ctx` )
- **Giải thích dễ hiểu:** Số token tối đa LLM "nhìn" được một lúc
- **Trong dự án:** Chatbot 8192; dịch 2048–2560

### CORS
- **Giải thích dễ hiểu:** Chính sách trình duyệt cho phép gọi API khác origin
- **Trong dự án:** Chỉ `127.0.0.1:8100` , `localhost:8100`

### CREATE_NO_WINDOW
- **Giải thích dễ hiểu:** Cờ Windows để subprocess không bật cửa sổ console
- **Trong dự án:** `process_manager.py`

### Cross-attention
- **Giải thích dễ hiểu:** Attention mà query từ ảnh, key/value từ text (hoặc ảnh tham chiếu)
- **Trong dự án:** U-Net đọc prompt; IP-Adapter

### CRF
- **Giải thích dễ hiểu:** Hệ số chất lượng hằng của x264, nhỏ hơn thì đẹp hơn và file lớn hơn
- **Trong dự án:** Mặc định 23 (không đặt), merge fallback 20

### CUDA
- **Giải thích dễ hiểu:** Nền tảng tính toán GPU của NVIDIA
- **Trong dự án:** PyTorch, ONNX GPU

### Demucs
- **Giải thích dễ hiểu:** Mô hình tách nguồn âm (giọng/nhạc)
- **Trong dự án:** Autosub `--clean-audio`

### Denoising
- **Giải thích dễ hiểu:** Khử nhiễu dần từ nhiễu thuần thành ảnh
- **Trong dự án:** Vòng lặp scheduler của SD

### Diffusion model
- **Giải thích dễ hiểu:** Mô hình học đảo ngược quá trình thêm nhiễu
- **Trong dự án:** Stable Diffusion 1.5

### diffusers
- **Giải thích dễ hiểu:** Thư viện Hugging Face cho mô hình khuếch tán
- **Trong dự án:** `StableDiffusionPipeline` 0.38.0

### Distillation
- **Giải thích dễ hiểu:** Huấn luyện mô hình/LoRA bắt chước mô hình lớn hoặc nhiều bước bằng ít bước hơn
- **Trong dự án:** Hyper-SD 8 bước

### DPM-Solver++ (Karras)
- **Giải thích dễ hiểu:** Scheduler bậc cao, lịch sigma Karras, chất lượng tốt ở 15–30 bước
- **Trong dự án:** Chế độ chất lượng (steps ≥ 15), face detailer

### Edge TTS
- **Giải thích dễ hiểu:** Dịch vụ đọc văn bản online của Microsoft Edge
- **Trong dự án:** Engine TTS mặc định

### Embedding
- **Giải thích dễ hiểu:** Vector số biểu diễn ý nghĩa của text/ảnh
- **Trong dự án:** CLIP; semantic cache TTS; không dùng cho chatbot

### EulerDiscreteScheduler
- **Giải thích dễ hiểu:** Scheduler bậc nhất đơn giản
- **Trong dự án:** Chế độ nhanh với Hyper-SD

### EventSource
- **Giải thích dễ hiểu:** API trình duyệt nhận SSE, tự reconnect
- **Trong dự án:** `app.js streamLogs`

### Exit code
- **Giải thích dễ hiểu:** Mã trả về khi process kết thúc, 0 là thành công
- **Trong dự án:** Quyết định trạng thái mọi bước

### FAISS
- **Giải thích dễ hiểu:** Thư viện tìm kiếm vector gần nhất
- **Trong dự án:** Semantic cache TTS (mặc định tắt)

### FastAPI
- **Giải thích dễ hiểu:** Framework web Python dựa trên type hint + pydantic
- **Trong dự án:** `orchestrator/main.py`

### faster-whisper
- **Giải thích dễ hiểu:** Whisper chạy trên CTranslate2, nhanh và ít RAM hơn
- **Trong dự án:** Autosub, `app/services/subtitle.py`

### ffmpeg
- **Giải thích dễ hiểu:** Bộ công cụ xử lý video/audio dòng lệnh
- **Trong dự án:** Dựng video, merge, tách audio, burn sub

### fp16 / fp32
- **Giải thích dễ hiểu:** Số thực 16-bit / 32-bit; fp16 nhẹ, nhanh nhưng dễ tràn số
- **Trong dự án:** SD fp16; ESRGAN fp32 để tránh khung đen

### FSM (State machine)
- **Giải thích dễ hiểu:** Mô hình trạng thái và chuyển trạng thái
- **Trong dự án:** `story.json['status']`

### FTS5
- **Giải thích dễ hiểu:** Module full-text search của SQLite
- **Trong dự án:** `storage/kb_index.db`

### GGUF
- **Giải thích dễ hiểu:** Định dạng file mô hình của llama.cpp, hỗ trợ lượng tử hóa
- **Trong dự án:** Model Ollama, HY-MT2 Q8_0

### Glossary
- **Giải thích dễ hiểu:** Bảng thuật ngữ dịch cố định
- **Trong dự án:** `glossary.json` , `global_glossary.json` , `common_idioms.json`

### GrabCut
- **Giải thích dễ hiểu:** Thuật toán tách nền bằng GMM + graph cut
- **Trong dự án:** Matter dự phòng của Studio

### H.264
- **Giải thích dễ hiểu:** Chuẩn nén video phổ biến
- **Trong dự án:** libx264 / h264_nvenc

### Hyper-SD
- **Giải thích dễ hiểu:** LoRA chưng cất cho phép SD sinh ảnh với ít bước
- **Trong dự án:** `Hyper-SD15-8steps-CFG-lora`

### IDF
- **Giải thích dễ hiểu:** Trọng số độ hiếm của từ: `ln(N/(1+df))`
- **Trong dự án:** Chấm điểm KB chatbot

### img2img
- **Giải thích dễ hiểu:** Sinh ảnh bắt đầu từ ảnh có sẵn + nhiễu theo `strength`
- **Trong dự án:** Face detailer (0.45), unify pass (0.28)

### InsightFace
- **Giải thích dễ hiểu:** Bộ nhận diện khuôn mặt, embedding 512 chiều
- **Trong dự án:** Engine identity `faceid` (không mặc định)

### IP-Adapter
- **Giải thích dễ hiểu:** Bộ chuyển ảnh tham chiếu thành điều kiện cho diffusion
- **Trong dự án:** Plus Face SD1.5, scale 0.6

### isnet-anime
- **Giải thích dễ hiểu:** Mô hình tách nền (họ IS-Net/U2-Net) cho ảnh anime
- **Trong dự án:** `RembgMatter`

### JSON Lines
- **Giải thích dễ hiểu:** Mỗi dòng một object JSON độc lập
- **Trong dự án:** Giao thức log worker → orchestrator

### JSON mode
- **Giải thích dễ hiểu:** Chế độ ép LLM trả JSON hợp lệ
- **Trong dự án:** Chia cảnh, trích glossary

### Ken Burns
- **Giải thích dễ hiểu:** Hiệu ứng zoom/pan chậm trên ảnh tĩnh
- **Trong dự án:** Không có trong luồng truyện (hướng phát triển)

### keep_alive
- **Giải thích dễ hiểu:** Thời gian Ollama giữ model trong VRAM; 0 là nhả ngay
- **Trong dự án:** `unload_ollama` , `/api/chat/unload`

### KV cache
- **Giải thích dễ hiểu:** Bộ nhớ đệm key/value của các token đã tính để không tính lại
- **Trong dự án:** Lý do `sticky_kb` giữ nguyên mảnh KB

### Latent space
- **Giải thích dễ hiểu:** Không gian nén của VAE (1/8 mỗi chiều, 4 kênh)
- **Trong dự án:** SD sinh ở latent 4×54×96 cho 768×432

### libass
- **Giải thích dễ hiểu:** Thư viện render phụ đề ASS/SRT
- **Trong dự án:** Filter `subtitles` của ffmpeg

### LLM
- **Giải thích dễ hiểu:** Mô hình ngôn ngữ lớn dự đoán token kế tiếp
- **Trong dự án:** Qwen2.5, Qwen3, HY-MT2, Gemini

### LoRA
- **Giải thích dễ hiểu:** Tinh chỉnh bằng cập nhật hạng thấp `ΔW = BA`
- **Trong dự án:** Style `thuy_mac` , nhân vật, Hyper-SD

### Lexical retrieval
- **Giải thích dễ hiểu:** Truy xuất dựa trên khớp từ, không dùng nghĩa vector
- **Trong dự án:** Chatbot

### LUFS
- **Giải thích dễ hiểu:** Đơn vị độ to cảm nhận
- **Trong dự án:** Chuẩn hóa −14 LUFS

### Matting
- **Giải thích dễ hiểu:** Tách tiền cảnh khỏi nền, ra mặt nạ alpha
- **Trong dự án:** rembg, GrabCut, Chroma

### Mel-spectrogram
- **Giải thích dễ hiểu:** Biểu diễn âm thanh theo thang tần số gần tai người
- **Trong dự án:** Đầu vào Whisper; trung gian TTS

### Mock / Stub
- **Giải thích dễ hiểu:** Đối tượng giả thay thành phần thật khi test
- **Trong dự án:** `FakeProcess` , `StubStorage`

### NDJSON
- **Giải thích dễ hiểu:** JSON phân tách bằng newline, dùng để stream
- **Trong dự án:** Chatbot `/api/chat`

### Negative prompt
- **Giải thích dễ hiểu:** Prompt mô tả thứ cần tránh trong ảnh
- **Trong dự án:** Phần sau `---` trong preset

### NFC
- **Giải thích dễ hiểu:** Dạng chuẩn hóa Unicode tổ hợp dấu
- **Trong dự án:** Bước đầu xử lý text TTS

### Normalizing flow
- **Giải thích dễ hiểu:** Chuỗi biến đổi khả nghịch để mô hình hóa phân phối
- **Trong dự án:** Thành phần của VITS

### num_predict
- **Giải thích dễ hiểu:** Số token tối đa LLM sinh ra
- **Trong dự án:** Dịch: `max(2048, chunk×15)` ; chat 512

### NVENC
- **Giải thích dễ hiểu:** Bộ mã hóa video phần cứng của GPU NVIDIA
- **Trong dự án:** `h264_nvenc` , fallback libx264

### Ollama
- **Giải thích dễ hiểu:** Runtime chạy LLM local, API HTTP :11434
- **Trong dự án:** Dịch, prompt, chatbot

### OOM
- **Giải thích dễ hiểu:** Hết bộ nhớ (Out Of Memory)
- **Trong dự án:** Pass A retry 1 lần sau release

### Orchestrator
- **Giải thích dễ hiểu:** Thành phần điều phối các bước/tiến trình
- **Trong dự án:** `orchestrator/`

### Painter's algorithm
- **Giải thích dễ hiểu:** Vẽ lớp xa trước, lớp gần sau
- **Trong dự án:** Sắp `z_order` khi ghép Studio

### peft
- **Giải thích dễ hiểu:** Thư viện Hugging Face cho fine-tune hiệu quả (LoRA)
- **Trong dự án:** Script train LoRA

### Piper
- **Giải thích dễ hiểu:** Engine TTS offline nhẹ dùng VITS/ONNX
- **Trong dự án:** `vi_VN-vais1000-medium` , 22050 Hz

### Popen
- **Giải thích dễ hiểu:** Hàm Python tạo process con
- **Trong dự án:** `ProcessManager.start_process`

### Prompt injection
- **Giải thích dễ hiểu:** Văn bản đầu vào lừa LLM làm theo chỉ thị lạ
- **Trong dự án:** Chatbot bọc truyện trong `<noidungtruyen>`

### pydantic
- **Giải thích dễ hiểu:** Thư viện kiểm tra/ép kiểu dữ liệu
- **Trong dự án:** Schema request FastAPI

### pytest
- **Giải thích dễ hiểu:** Framework kiểm thử Python
- **Trong dự án:** 178 test repo tổng

### pywebview
- **Giải thích dễ hiểu:** Thư viện mở cửa sổ web native
- **Trong dự án:** Cửa sổ WebView2 1280×840

### Quantization
- **Giải thích dễ hiểu:** Giảm số bit biểu diễn trọng số
- **Trong dự án:** GGUF Q8_0, Q4

### RAG
- **Giải thích dễ hiểu:** Truy xuất tài liệu rồi đưa vào prompt để LLM trả lời có căn cứ
- **Trong dự án:** Chatbot

### Real-ESRGAN
- **Giải thích dễ hiểu:** GAN siêu phân giải ảnh
- **Trong dự án:** x4plus_anime_6B → 1920×1080

### rembg
- **Giải thích dễ hiểu:** Thư viện tách nền dùng mô hình ONNX
- **Trong dự án:** Matter chính của Studio

### Resume
- **Giải thích dễ hiểu:** Chạy tiếp từ phần dở
- **Trong dự án:** Dịch, TTS, video, crawl

### Rolling summary
- **Giải thích dễ hiểu:** Tóm tắt cộng dồn để giữ mạch dài
- **Trong dự án:** `story_writer.py`

### SDPA
- **Giải thích dễ hiểu:** Scaled Dot-Product Attention tối ưu của PyTorch 2
- **Trong dự án:** Attention mặc định của SD, XTTS

### Seed
- **Giải thích dễ hiểu:** Số khởi tạo ngẫu nhiên, cố định để tái lập
- **Trong dự án:** `accepted_seed` trong `state.json`

### Selenium
- **Giải thích dễ hiểu:** Điều khiển trình duyệt thật bằng code
- **Trong dự án:** Crawler 69shuba

### Semantic cache
- **Giải thích dễ hiểu:** Cache theo độ giống ngữ nghĩa
- **Trong dự án:** TTS, all-MiniLM + FAISS, ngưỡng 0.95

### Sentinel
- **Giải thích dễ hiểu:** Giá trị đặc biệt báo kết thúc luồng
- **Trong dự án:** `None` trong log queue

### Singleton
- **Giải thích dễ hiểu:** Chỉ có một thể hiện dùng chung
- **Trong dự án:** `StorytellingPipeline` , model Whisper

### SQLite WAL
- **Giải thích dễ hiểu:** Chế độ ghi nhật ký cho phép đọc song song khi ghi
- **Trong dự án:** `storage/app.db`

### SRT
- **Giải thích dễ hiểu:** Định dạng phụ đề: số thứ tự, thời gian, nội dung
- **Trong dự án:** `generated_from_script.srt`

### SSE
- **Giải thích dễ hiểu:** Server đẩy sự kiện một chiều qua HTTP
- **Trong dự án:** `/api/pipeline/logs/{task_key}`

### Stable Diffusion
- **Giải thích dễ hiểu:** Mô hình khuếch tán trong latent, sinh ảnh từ text
- **Trong dự án:** SD1.5 + anything-v5

### Strategy pattern
- **Giải thích dễ hiểu:** Chọn thuật toán tại runtime qua giao diện chung
- **Trong dự án:** Registry nguồn, engine dịch, engine TTS

### strength (img2img)
- **Giải thích dễ hiểu:** Mức nhiễu thêm vào ảnh gốc; 0 giữ nguyên, 1 vẽ lại
- **Trong dự án:** Unify 0.28, detailer 0.45

### Style lock
- **Giải thích dễ hiểu:** Một nguồn sự thật cho style trong prompt, lọc tag trôi
- **Trong dự án:** `style_lock.build_locked_prompt`

### Subprocess
- **Giải thích dễ hiểu:** Process con do process khác tạo
- **Trong dự án:** Mọi worker AI

### taskkill /T /F
- **Giải thích dễ hiểu:** Lệnh Windows diệt cả cây process, cưỡng bức
- **Trong dự án:** `stop_process`

### Temperature
- **Giải thích dễ hiểu:** Hệ số chia logit; thấp → tất định, cao → sáng tạo
- **Trong dự án:** Dịch 0.02–0.7; chat 0.4; chia cảnh 0.3

### TF32
- **Giải thích dễ hiểu:** Định dạng số của GPU Ampere, nhanh hơn fp32 với sai số nhỏ
- **Trong dự án:** CloneEngine XTTS

### Token
- **Giải thích dễ hiểu:** Đơn vị văn bản mà mô hình xử lý (mảnh từ)
- **Trong dự án:** Giới hạn 77 token của CLIP; `num_ctx`

### top_p / top_k
- **Giải thích dễ hiểu:** Chỉ lấy mẫu trong nhóm token xác suất cao
- **Trong dự án:** Dịch HY-MT2: top_p 0.6, top_k 20

### Transformer
- **Giải thích dễ hiểu:** Kiến trúc mạng dựa trên attention
- **Trong dự án:** LLM, Whisper, CLIP, XTTS GPT

### TTS
- **Giải thích dễ hiểu:** Tổng hợp tiếng nói từ văn bản
- **Trong dự án:** Bước 2

### U-Net
- **Giải thích dễ hiểu:** Mạng mã hóa–giải mã có skip connection, dự đoán nhiễu
- **Trong dự án:** Lõi SD1.5

### Unify pass
- **Giải thích dễ hiểu:** img2img nhẹ trên frame đã ghép để hòa ánh sáng/nét
- **Trong dự án:** Studio, strength 0.28, 16 bước

### uvicorn
- **Giải thích dễ hiểu:** ASGI server chạy FastAPI
- **Trong dự án:** Thread trong `desktop.py`

### VAD
- **Giải thích dễ hiểu:** Phát hiện đoạn có tiếng nói
- **Trong dự án:** Silero VAD trong faster-whisper

### VAE
- **Giải thích dễ hiểu:** Bộ mã hóa/giải mã giữa ảnh và latent
- **Trong dự án:** SD encode/decode; bug tiling fp16

### VAE tiling
- **Giải thích dễ hiểu:** Decode latent theo ô để tiết kiệm VRAM
- **Trong dự án:** Chỉ bật khi cạnh ≥ 1024

### VITS
- **Giải thích dễ hiểu:** TTS end-to-end: VAE + flow + GAN
- **Trong dự án:** Piper

### VRAM
- **Giải thích dễ hiểu:** Bộ nhớ của GPU
- **Trong dự án:** Ràng buộc 6 GB, đỉnh ≈ 4,0 GB

### WebView2
- **Giải thích dễ hiểu:** Engine web Chromium nhúng của Windows
- **Trong dự án:** Cửa sổ ứng dụng

### Whisper
- **Giải thích dễ hiểu:** Mô hình ASR encoder-decoder của OpenAI
- **Trong dự án:** Autosub

### XTTSv2
- **Giải thích dễ hiểu:** TTS clone giọng dùng GPT + decoder
- **Trong dự án:** `CloneEngine` , 24 kHz

### Zero Tolerance
- **Giải thích dễ hiểu:** Chính sách: một ký tự Hán sót cũng là lỗi
- **Trong dự án:** Kiểm tra bản dịch

## 4. Checklist trước ngày bảo vệ

### 4.1 Kỹ thuật (trước 2–3 ngày)

[ ] Chạy `python -m pytest -q tests/` bằng `AIVoice/.venv` , ghi lại số passed và thời gian. [ ] Chạy test MediaComposer GPU-free, ghi lại số passed. [ ] Mở app bằng `run.bat` trên đúng máy sẽ demo. Chờ `model_preflight` xong, kiểm tra Ollama có `qwen2.5:3b` (chatbot) và model dịch. [ ] Chạy thử trọn một truyện ngắn 1 chương từ nguồn `local` , bấm giờ từng bước. [ ] Kiểm tra `configs/global_config.json` : `render_mode` , `default_style` , `burn_subtitles` . Quyết định demo Classic hay Studio và nhất quán với lời nói. [ ] Nếu muốn video demo có phụ đề thì bật `burn_subtitles` (mặc định tắt). [ ] Quay video dự phòng toàn pipeline, lưu vào desktop + USB + cloud. [ ] Chuẩn bị sẵn 1 truyện đã xong trong `storage/truyen/` (vd `e2e_kiem_khach` ) để xem kết quả. [ ] Tắt proxy Gemini-API. Demo bằng Ollama, không cần mạng. [ ] Kiểm tra chế độ offline: rút mạng, chạy Piper + Ollama.

[ ] Dọn key giả `sk-gemini-...` trong submodule nếu kịp (5 file, xem ch00 mục 8). Không commit vội ngay trước bảo vệ nếu chưa test lại. [ ] Đóng các app nặng GPU khác (trình duyệt nhiều tab video, game).

### 4.2 Tài liệu và nội dung

[ ] Đọc lại báo cáo chương 5 và Kết luận; thuộc bảng số liệu ở ch00 mục 3.4. [ ] Học kỹ bảng "lệch báo cáo và code" ở ch00 mục 7. [ ] Mở sẵn trong VS Code: `pipeline.py` , `process_manager.py` , `image_generator.py` , `style_lock.py` , `chatbot.py` . [ ] In 1 trang A4 gồm sơ đồ 3 tầng + luồng end-to-end để vẽ lại lên bảng nếu cần. [ ] Chuẩn bị slide dự phòng (ẩn) cho: CFG công thức, LoRA ΔW=BA, IDF công thức, sơ đồ ProcessManager.

### 4.3 Thuyết trình

[ ] Tập nói 2 lần có bấm giờ, mục tiêu 17–19 phút. [ ] Tập riêng 3 câu: "vì sao đa tiến trình", "sinh ảnh hoạt động thế nào", "slideshow hay hoạt hình". [ ] Nhờ bạn hỏi ngẫu nhiên 15 câu trong chương này. [ ] Chuẩn bị câu mở đầu và kết luận học thuộc.

### 4.4 Ngày bảo vệ

[ ] Đến sớm, cắm máy, kiểm tra máy chiếu (độ phân giải, âm thanh cho video demo). [ ] Sạc đầy laptop, mang sạc và adapter HDMI. [ ] Mở sẵn app, video dự phòng, slide, VS Code. [ ] Tắt thông báo, chế độ không làm phiền. [ ] Mang bản in báo cáo và sổ ghi câu hỏi của hội đồng.

## Câu hỏi hội đồng có thể hỏi

Phần này tổng hợp 10 câu có xác suất cao nhất. Đáp án đầy đủ ở mục 1.

### 1. Vì sao kiến trúc đa tiến trình? VRAM chỉ được trả hết khi process thoát; cô lập lỗi và xung đột thư viện; mỗi submodule có venv riêng (Q9). 2. Stable Diffusion sinh ảnh thế nào?

Khử nhiễu dần trong latent của VAE, U-Net dự đoán nhiễu, text vào qua CLIP + cross-attention, CFG 5.0, 8 bước nhờ Hyper-SD (Q33–Q35). 3. Giữ nhân vật nhất quán thế nào? Style lock + IP-Adapter 0.6 + LoRA nhân vật 0.8; chưa đo CLIP (Q43). 4. LoRA là gì? ΔW = BA hạng thấp, chỉ khoảng 0,19% tham số U-Net với rank 8 (Q41). 5. Làm sao dịch không sót chữ Hán? Dịch 2 tầng + Zero Tolerance; 0/214.034 ký tự (Q26). 6. Có phải chỉ là slideshow? Đúng, lý do là VRAM; hướng phát triển zoompan/xfade (Q5). 7. Studio có phải mặc định? Mặc định mã nguồn là Classic; Studio bật trên máy demo, tự lùi khi không qua gate (Q46). 8. Chatbot có dùng embedding không? Không, IDF lexical có số đo so sánh (Q50). 9. Đánh giá chất lượng bằng gì? CJK, khung đen, đồng bộ thời lượng, eval chatbot; chưa có MOS/CLIP (Q54). 10. Phần nào em tự làm? Toàn bộ điều phối, adapter, xử lý dữ liệu giữa các mô hình, style lock, Studio, chatbot, test; mô hình dùng lại, tự train LoRA style (Q65). 11. Bản quyền? Mặc định nguồn local/public domain hoặc AI viết; dataset style CC0; crawler là tùy chọn (Q58–Q60). 12. Nếu làm lại em sẽ đổi gì? Ghi JSON atomic, truyền key qua env, dùng bảng `jobs` làm nhật ký, bỏ merge trùng trong auto-run, thêm zoompan/xfade, đo CLIP/MOS, benchmark nhiều GPU.

## Tóm tắt 1 phút

"Khi trả lời hội đồng, em bám ba nguyên tắc. Một: không bịa số. Cái gì đã đo thì em nói con số và nguồn: 173 test tự động đạt trong báo cáo, 178 khi chạy lại gần nhất; 26 chương dịch không sót chữ Hán; chatbot truy xuất đúng 89,3% và từ chối 87,5%; VRAM đỉnh khoảng 4 GB trên máy 6 GB. Cái gì chưa đo như MOS hay CLIP thì em nói rõ là chưa đo và cách sẽ đo. Hai: phân biệt code có và code chạy mặc định. Studio compositing, face detailer, tự train LoRA nhân vật đều có trong code, nhưng mặc định

là Classic, tắt detailer, còn Whisper không dùng trong luồng truyện. Ba: chủ động nêu hạn chế kèm hướng sửa cụ thể. Video hiện là ảnh tĩnh theo thời lượng lời đọc, hướng gần nhất là zoompan và xfade của ffmpeg; API chưa có xác thực nhưng chỉ bind localhost. Về lý thuyết, em nắm chắc bốn công thức: attention softmax(QKᵀ/√d)V, classifier-free guidance, LoRA ΔW bằng BA, và IDF bằng log N trên một cộng df. Đóng góp của em là phần điều phối: đưa nhiều mô hình vào một pipeline quan sát được, dừng được và chạy lại được trên một máy cá nhân."
