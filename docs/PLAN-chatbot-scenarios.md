# Chatbot Trợ Lý — kịch bản vận hành, phân tích lỗi và đảm bảo chất lượng

> Tài liệu đồng hành của [PLAN-chatbot-assistant.md](PLAN-chatbot-assistant.md).
> Mục đích: hình dung hệ thống **chạy thật** trông như thế nào, tìm chỗ vỡ **trước khi
> viết code**, và chốt cơ chế giữ chất lượng câu trả lời ở mức chấp nhận được với model 3B.
> Mục 5 ghi các thay đổi thiết kế phát sinh từ chính việc mô phỏng này — đã được phản ánh
> ngược vào plan chính.

---

## 1. Ngân sách thời gian thực tế

Trước khi dựng kịch bản phải biết mỗi bước tốn bao lâu, vì phần lớn lỗi trải nghiệm là lỗi
**chờ đợi không được thông báo**, không phải lỗi kỹ thuật.

Ước tính cho `qwen2.5:3b-instruct` (Q4) trên RTX 3060 6GB, prompt ~3000 token:

| Giai đoạn | Lạnh (model chưa nạp) | Ấm (model đã trong VRAM) |
|---|---|---|
| Nạp model từ đĩa | 3–8 giây (SSD) / 15–40 giây (HDD) | 0 |
| Đọc prompt (prompt eval) | 2–4 giây | 2–4 giây, **≈0 nếu trúng prompt cache** |
| Token đầu tiên xuất hiện | **6–12 giây** | 2–4 giây (**<1s nếu cache**) |
| Sinh xong ~200 token | +4–5 giây | +4–5 giây |
| **Tổng tới khi đọc được** | **10–17 giây** | 3–5 giây |

**Kết luận rút ra:** 6–12 giây im lặng ở lần hỏi đầu tiên là ngưỡng người dùng cho rằng ứng
dụng bị treo. Đây không phải chuyện tinh chỉnh về sau — nó quyết định thiết kế luồng (mục
2.1) và sinh ra hai yêu cầu mới: **báo trạng thái nạp model** và **giữ prompt cache** (mục
5.1, 5.2).

---

## 2. Ba kịch bản vận hành

### 2.1 KB-1 — Người dùng mới hỏi cách dùng *(happy path, nhưng lạnh)*

Bối cảnh: vừa mở app lần đầu bằng `run.bat`, chưa chạy bước nào.

| # | Người dùng | Hệ thống | Thời điểm |
|---|---|---|---|
| 1 | Mở app | `desktop.py` bật uvicorn :8100 + Gemini proxy. **Ollama không được bật** (mục 3.1) | 0s |
| 2 | | `chat.js` gọi `GET /api/chat/health` → `ollama_online: true`, `model_loaded: false` | +1s |
| 3 | | Badge nút tròn: **xanh**, tooltip "Trợ lý sẵn sàng (lần hỏi đầu cần ~10 giây nạp)" | |
| 4 | Bấm nút tròn | Panel mở. **Pre-warm**: `POST /api/chat/prewarm` chạy nền vì `busy=false` | +0s |
| 5 | | Ollama nạp model. Chip gợi ý hiện sẵn: "Bắt đầu từ đâu?", "Bước 3 chọn checkpoint nào?" | +3–8s |
| 6 | Gõ "sao video ko co tieng" *(không dấu)* | Chuẩn hoá bỏ dấu → `select_kb()` khớp `07-su-co-thuong-gap.md#video-khong-co-tieng` + `02-buoc2-tts.md` | +0.1s |
| 7 | Enter | Ô nhập khoá, hiện 3 chấm nhấp nháy + dòng trạng thái "Đang đọc tài liệu…" | |
| 8 | | Nhờ pre-warm ở bước 4, model đã ấm → token đầu tiên | +1.5s |
| 9 | | Chữ chảy dần ra panel, nút **Dừng** hiện bên cạnh | |
| 10 | | Xong. Chân tin nhắn: `Nguồn: 07-su-co-thuong-gap.md, 02-buoc2-tts.md` | +6s |

Điểm chốt: **pre-warm lúc mở panel** (bước 4) biến 6–12 giây chờ thành 1.5 giây, vì người
dùng luôn mất vài giây đọc chip gợi ý và gõ câu hỏi — thời gian đó vừa đủ nạp model. Không
pre-warm lúc tải trang (lãng phí VRAM cho người không bao giờ mở trợ lý).

### 2.2 KB-2 — Hỏi trong lúc Bước 3 đang render *(vai C)*

Bối cảnh: đang render 82 cảnh, còn ~40 phút. Người dùng thấy log chạy chậm, muốn hỏi.

| # | Người dùng | Hệ thống |
|---|---|---|
| 1 | Bấm nút tròn | `/api/chat/health` → `busy: true`, `busy_tasks: ["hvl_step3"]`, `gpu_weight: "heavy"` |
| 2 | | Badge **vàng**. Placeholder ô nhập đổi sẵn: *"Đang chạy Bước 3 — gửi câu hỏi sẽ tra cứu tài liệu (không dùng GPU)"* |
| 3 | Gõ "sao render lâu vậy" + Enter | `POST /api/chat` → **409** kèm `lookup_answer` đã tính sẵn |
| 4 | | Widget hiện **ngay** thẻ trích dẫn từ `03-buoc3-video.md#thoi-gian-render`, nhãn *"Trích tài liệu — không qua AI"*, kèm 3 nút chọn |
| 5 | Đọc thấy đủ, không bấm gì | Không request nào thêm. VRAM không đổi. Bước 3 chạy tiếp không bị ảnh hưởng |

Đây là lý do vai C tồn tại: người dùng có câu trả lời trong **<200ms**, không phải chọn giữa
"dừng việc đang chạy" và "không được hỏi". Ba nút vẫn còn đó cho ai cần câu trả lời diễn
giải đầy đủ.

**Biến thể quan trọng:** nếu đang chạy là **Bước 1 với engine Gemini local** thì
`gpu_weight: "none"` → **không chặn**, chat bình thường. Chặn nhị phân theo "có task đang
chạy" như bản plan trước là quá tay (mục 5.3).

### 2.3 KB-3 — Tư vấn truyện *(vai B)*

| # | Người dùng | Hệ thống |
|---|---|---|
| 1 | Đã chọn truyện `hvl` ở sidebar | `chat.js` đọc `activeStoryName`, gửi kèm mỗi request |
| 2 | "truyện này nên chọn giọng đọc nào" | `mode: "auto"` → phát hiện có `story_name` + từ khoá "truyện này" → vai B |
| 3 | | `build_story_context("hvl")` → thể loại `tien_hiep`, 12 chương, trích 500 ký tự chương 1 và chương cuối, bọc `<noidungtruyen>` |
| 4 | | `select_kb()` vẫn nạp `02-buoc2-tts.md` — **vai B không thay thế KB, mà cộng thêm** ngữ cảnh truyện |
| 5 | | Trả lời: đề xuất giọng nam trầm cho tiên hiệp, nêu 2 engine cụ thể, ghi rõ *"dựa trên thể loại `tien_hiep` trong story.json"* |
| 6 | | `Nguồn: 02-buoc2-tts.md + story.json (hvl)` |

Điểm dễ sai: model 3B rất hay **bịa số chương** hoặc **bịa tên nhân vật**. Ràng buộc trong
system prompt: *"Mọi thông tin về truyện chỉ được lấy từ `<noidungtruyen>`. Không suy đoán
tình tiết, tên nhân vật hay số chương không có trong đó."* Đưa vào bộ eval (mục 4.6) một câu
kiểu "truyện này có bao nhiêu nhân vật nữ?" — đáp án đúng là **từ chối**, vì dữ liệu không có.

---

## 3. Phân tích lỗi

Mỗi mục: hiện tượng người dùng thấy → nguyên nhân → **cách phát hiện** → cách xử lý.

### 3.1 Tầng hạ tầng

**L1 — Ollama không chạy. *(Rủi ro cao nhất, và là rủi ro quy trình chứ không phải kỹ thuật)***

`run.bat` → `desktop.py` tự bật Gemini proxy (`_start_gemini_proxy()`, có kiểm tra
`_port_open()` để không bật trùng) nhưng **không bật Ollama**. `setup.bat` **không cài
Ollama** — grep toàn file không có một dòng nào nhắc tới. Nghĩa là trên máy cài từ
`setup.exe`, trợ lý **chết ngay từ đầu** mà không ai biết cho tới lúc bấm thử.

> Đây là hệ quả trực tiếp của quyết định chọn Ollama làm engine duy nhất: Bước 1/3 mặc định
> dùng Gemini local nên Ollama vắng mặt không ảnh hưởng gì, còn trợ lý thì phụ thuộc cứng.

Xử lý, ba lớp:

1. **Tự bật** — thêm `_start_ollama()` vào `desktop.py`, sao đúng khuôn `_start_gemini_proxy()`:
   kiểm tra `_port_open(11434)`, nếu chưa mở thì `ollama serve` chạy ẩn, kill khi đóng app.
   ~25 dòng, có sẵn mẫu.
2. **Cài đặt** — `setup.bat` kiểm tra `where ollama`; thiếu thì in hướng dẫn
   `winget install -e --id Ollama.Ollama` và `ollama pull qwen2.5:3b-instruct` (~2GB).
   **Không tự tải** trong `setup.exe` vì đã mất 30–60 phút, thêm 2GB nữa là quá nhiều —
   để người dùng chủ động.
3. **Suy giảm êm** — thiếu Ollama thì badge xám, panel vẫn mở được và **vai C tra cứu vẫn
   chạy** (không cần LLM). Trợ lý mất khả năng diễn giải chứ không biến mất.

Lớp 3 là quan trọng nhất cho buổi bảo vệ đồ án: máy lạ, không có Ollama, trợ lý vẫn tra cứu
được tài liệu.

**L2 — Model chưa `pull`.** Ollama trả `404 model not found`. → Thông báo kèm lệnh copy
được: `ollama pull qwen2.5:3b-instruct`, và nút "Chọn model khác" mở dropdown từ
`GET /api/ollama/models` (đã lọc `installed: true`).

**L3 — Ollama chết giữa lúc stream.** `httpx` ném `ReadError`/`RemoteProtocolError`. →
Gửi chunk `{"error": ...}` cuối stream, widget giữ nguyên phần chữ đã nhận và hiện nút
"Thử lại" (gửi lại đúng tin nhắn đó, không mất nội dung người dùng đã gõ).

**L4 — Đĩa chậm, nạp model 40 giây.** Người dùng nghĩ treo. → `GET /api/ollama/ps` (native,
liệt kê model đang nạp) cho biết trạng thái; nếu sau 15 giây chưa có token đầu, widget đổi
thông báo thành "Đang nạp model lần đầu, có thể mất tới 60 giây…" thay vì để 3 chấm im lặng.

### 3.2 Tầng luồng dữ liệu

**L5 — Client đóng panel giữa lúc stream, generation vẫn chạy.** GPU tiếp tục sinh token cho
một stream không ai đọc. Với FastAPI, ngắt kết nối **không** tự dừng async generator. →
Trong vòng lặp stream phải kiểm tra `await request.is_disconnected()` mỗi chunk, thoát và
đóng `httpx` stream. Bỏ sót mục này là rò rỉ GPU thầm lặng — mỗi lần đóng panel giữa chừng
lại để lại một generation chạy tới hết.

**L6 — Người dùng bấm Enter liên tục.** Lock trả 429 nhiều lần, panel đầy thông báo lỗi. →
Khoá ô nhập và nút gửi **ngay khi** bắt đầu stream (client-side); 429 chỉ còn là chốt chặn
phía server, không phải luồng thường gặp.

**L7 — Sửa file KB lúc app đang chạy.** Cache KB cũ vẫn được dùng. → Cache theo `mtime` từng
file, kiểm tra ở mỗi lần `select_kb()`. Chi phí: một `os.stat` mỗi file, không đáng kể.

**L8 — `story.json` hỏng/thiếu.** `read_story_meta` trả `None`. → Vai B suy giảm về vai A và
nói rõ *"Chưa đọc được thông tin truyện, tôi trả lời theo tài liệu chung."* Không văng 500.

**L9 — Truyện 200 chương.** `_scan_chapters` quét đĩa mỗi lần hỏi → chậm. → Chỉ đọc
`story.json` + `os.listdir` đếm file, **không** đọc nội dung mọi chương; chỉ đọc đúng 2 file
(chương đầu, chương cuối) và chỉ 500 ký tự đầu mỗi file.

### 3.3 Tầng VRAM

**L10 — Bấm "Dừng tiến trình để hỏi", chat vẫn OOM.** `stop_process` kill process tree,
nhưng VRAM chỉ được OS thu hồi sau khi tiến trình thật sự thoát, và
`ProcessManager.is_running()` cố ý trả `True` cho tới khi reader thread dọn xong bookkeeping
(xem chú thích tại [process_manager.py:204](../orchestrator/process_manager.py)). Gửi
`force: true` ngay khi `is_running` vừa thành `False` vẫn có thể chen vào lúc VRAM chưa
thoát. → Sau khi `is_running == False`, chờ thêm **1.5 giây** rồi mới nạp model chat. Nếu có
`nvidia-smi` thì kiểm tra `memory.free ≥ 3500MB` (tái dùng cách gọi ở
[`get_gpu_info()` — main.py:199](../orchestrator/main.py)); không có thì dùng mốc thời gian.

**L11 — Chat xong, bấm Bước 3 sau 30 giây, vẫn OOM.** `keep_alive` mặc định giữ model 5
phút. → `auto_unload_before_pipeline` gọi `unload_ollama()` **đồng bộ** trước khi spawn
subprocess, và **chờ kết quả** (timeout 10s) chứ không fire-and-forget — nếu không, subprocess
SD có thể khởi động trước khi Ollama kịp nhả.

**L12 — Người dùng để panel mở cả buổi.** Model chat neo trong VRAM vì pre-warm rồi không
dùng nữa. → Bộ đếm nhàn rỗi: không có tin nhắn nào trong `idle_unload_minutes` (mặc định 10)
→ tự `unload`. Hỏi lại thì nạp lại (chấp nhận 3–8 giây).

**L13 — Bước 3 tự unload model của nó, vô tình nhả luôn model chat.** Khi
`share_model_with_step3 = true`, hai bên dùng chung một model, `unload_local_llm()` của
AIVoice nhả nó ở ranh giới LLM→SD. → Vô hại: chat chỉ tốn thời gian nạp lại. Nhưng **phải
ghi rõ trong tài liệu**, vì triệu chứng ("tự dưng trả lời chậm hẳn một lần") rất khó đoán
nếu không biết.

### 3.4 Tầng chất lượng câu trả lời

**L14 — Bịa tên nút không tồn tại.** → mục 4.

**L15 — Trả lời bằng tiếng Anh hoặc chèn tiếng Trung.** Qwen hay trôi ngôn ngữ khi prompt
lẫn tiếng Anh (tên tham số, tên engine). → Ràng buộc cứng đầu system prompt: *"LUÔN trả lời
bằng tiếng Việt, kể cả khi câu hỏi hoặc tài liệu có tiếng Anh."* Thêm 2 câu vào bộ eval để
đo. Nếu vẫn trôi, thêm few-shot (mục 4.2).

**L16 — Câu trả lời cụt giữa chừng.** Chạm trần `num_predict`. → Đặt `num_predict: 512`
(đủ cho câu trả lời hướng dẫn), phát hiện `done_reason == "length"` → hiện nút **"Viết tiếp"**
gửi lượt mới với chỉ thị nối tiếp.

**L17 — Câu hỏi mơ hồ: "sao lỗi rồi?"** `select_kb` chấm điểm thấp đều, chọn bừa. → **Cổng
ngưỡng** (mục 4.1): điểm cao nhất dưới ngưỡng thì **không gọi LLM**, mà hỏi lại kèm 3 chip
gợi ý dựa trên `active_tab` ("Lỗi ở Bước 3 phải không? Bạn thấy thông báo gì?").

**L18 — Hỏi ngoài phạm vi: "viết giúp em code Python".** → Cổng ngưỡng bắt được, trả lời
"Tôi chỉ hỗ trợ về công cụ này và về truyện của bạn." Không cần model phải tự biết từ chối.

### 3.5 Tầng giao diện

**L19 — Output LLM chứa `<script>` hoặc `<img onerror=…>`.** → Escape HTML **trước** khi
render markdown; chỉ cho phép `**đậm**`, `- danh sách`, `` `code` ``. Không dùng `innerHTML`
với chuỗi thô.

**L20 — Panel che nút "Chạy Bước 3".** Nút tròn nổi ở góc phải dưới, đúng chỗ nhiều form đặt
nút hành động. → Panel tự thu nhỏ khi người dùng cuộn tới cuối form; và nút tròn kéo thả
được, vị trí lưu vào `ui_settings.json`.

**L21 — Màn hình laptop 1366×768.** Panel 380×560 + sidebar 320px chiếm gần hết. → Dưới
1024px chiều rộng, panel chuyển sang chế độ phủ toàn màn hình có nút đóng rõ ràng.

**L22 — Đóng app giữa lúc stream.** `_shutdown()` diệt uvicorn; generator đang chạy có thể
ném exception vào log. → Bọc `try/except asyncio.CancelledError` và thoát êm, không để
stacktrace bẩn `logs/app.log` gây hiểu nhầm khi debug việc khác.

---

## 4. Đảm bảo chất lượng phản hồi

Đây là phần khó nhất: `qwen2.5:3b-instruct` là model **nhỏ**. Không thể kỳ vọng nó suy luận
tốt. Chiến lược là **giảm tối đa phần việc giao cho model**, đẩy gánh nặng sang khâu truy
xuất và ràng buộc — model chỉ còn việc diễn đạt lại tài liệu bằng tiếng Việt trôi chảy.

### 4.1 Cổng ngưỡng truy xuất — biện pháp mạnh nhất

```
điểm KB cao nhất < kb_min_score  →  KHÔNG gọi LLM
                                 →  trả lời mẫu cố định + 3 mục gần nhất + chip làm rõ
```

Model không thể bịa nếu ta **không gọi nó**. Đây là bảo đảm mang tính cấu trúc, không phụ
thuộc vào việc model có nghe lời prompt hay không — khác hẳn mọi biện pháp còn lại. Ngưỡng
hiệu chỉnh bằng chính bộ eval: chọn giá trị làm tối đa tỉ lệ từ chối đúng mà không cắt nhầm
câu hợp lệ.

### 4.2 Few-shot ngay trong system prompt

Có tiền lệ trong dự án: [`ollama_translator.py`](../toolCaoTruyen/translator/ollama_translator.py)
dùng `few_shots` theo thể loại để ghim văn phong. Áp dụng tương tự với **3 ví dụ**:

1. Câu hỏi có trong tài liệu → trả lời ngắn, có gạch đầu dòng, có dòng `Nguồn:`.
2. Câu hỏi **không** có trong tài liệu → câu từ chối mẫu, đúng từng chữ.
3. Câu hỏi về truyện → chỉ dùng dữ liệu trong `<noidungtruyen>`.

Ví dụ số 2 quan trọng nhất: model 3B học hành vi từ chối qua ví dụ tốt hơn nhiều so với qua
chỉ thị.

### 4.3 Ràng buộc định dạng

- Tối đa ~150 từ, ưu tiên gạch đầu dòng.
- Nhắc tới tham số nào phải kèm **vị trí trên UI** ("Bước 3 → mục Nâng cao").
- **Luôn** kết bằng `Nguồn: <tên file KB>`.
- Luôn tiếng Việt (L15).

### 4.4 Hiển thị nguồn — để người dùng tự kiểm chứng

Mỗi câu trả lời gắn tên file KB đã dùng, bấm được để mở nguyên đoạn tài liệu. Tác dụng kép:
người dùng kiểm tra được ngay, và trong buổi bảo vệ đồ án đây là bằng chứng trực quan cho
tính "có căn cứ" của hệ thống. Chi phí gần bằng không vì `select_kb()` đã biết nó chọn gì.

### 4.5 Tham số sinh

Theo mẫu [`registry.py`](../toolCaoTruyen/translator/registry.py) của dự án:

```jsonc
"temperature": 0.4,       // thấp — ưu tiên chính xác hơn sáng tạo
"top_p": 0.9,
"repeat_penalty": 1.05,
"num_predict": 512,
"num_ctx": 8192
```

### 4.6 Bộ eval — con số nghiệm thu

`tests/eval/kb_questions.jsonl`, 30 câu chia 4 nhóm:

| Nhóm | Số câu | Đo cái gì | Ngưỡng đạt |
|---|---|---|---|
| Có trong KB, hỏi rõ ràng | 15 | Đúng nội dung | ≥ 80% |
| **Không** có trong KB | 8 | **Từ chối đúng, không bịa** | **≥ 90%** |
| Về truyện (vai B) | 4 | Không bịa số chương/nhân vật | ≥ 75% |
| Ngôn ngữ & định dạng | 3 | Tiếng Việt, có dòng `Nguồn:` | 100% |

Nhóm 2 là chỉ số quan trọng nhất. Một trợ lý từ chối thẳng khi không biết thì dùng được;
một trợ lý bịa trôi chảy thì tệ hơn là không có, vì người dùng sẽ đi sửa nhầm cấu hình.

Chạy bằng `scripts/eval_chatbot.py`, thủ công (cần Ollama thật), **không** đưa vào CI.

---

## 5. Thay đổi thiết kế phát sinh

Năm điểm dưới đây là kết quả của việc mô phỏng, không có trong plan bản 2. Đã cập nhật ngược
vào [PLAN-chatbot-assistant.md](PLAN-chatbot-assistant.md).

### 5.1 Pre-warm khi mở panel + tự unload khi nhàn rỗi

Mở panel (không phải tải trang) → nạp model nền nếu `busy=false`. Biến 6–12 giây chờ thành
~1.5 giây (mục 2.1). Cân bằng lại bằng `idle_unload_minutes: 10` (L12).

### 5.2 Giữ KB **ổn định trong một phiên** để trúng prompt cache

Ollama tái dùng KV cache khi **tiền tố prompt không đổi**. Nếu `select_kb()` chạy lại mỗi
lượt và chọn đoạn khác, tiền tố đổi → **đọc lại toàn bộ 3000 token mỗi lượt**, cộng 2–4 giây
cho *mọi* câu hỏi, không chỉ câu đầu.

→ Chọn KB ở **lượt đầu** của phiên và **giữ nguyên**; chỉ chọn lại khi câu hỏi mới đạt điểm
cao trên một nhóm KB khác hẳn (chênh lệch vượt ngưỡng). Đổi KB thì báo nhẹ trong panel
("Đã chuyển sang tài liệu Bước 2") để người dùng hiểu vì sao lượt đó chậm hơn.

Đây là loại tối ưu nếu không nghĩ từ đầu thì sau này rất khó truy ra nguyên nhân "sao chat
lúc nhanh lúc chậm".

### 5.3 Phân loại mức chiếm GPU thay vì chặn nhị phân

Bản 2 chặn chat khi *có bất kỳ task nào* đang chạy. Quá tay: Bước 1 dùng Gemini local không
đụng GPU chút nào.

| Task | `gpu_weight` | Hành vi trợ lý |
|---|---|---|
| Bước 1 — Gemini local / Gemini online | `none` | Chat bình thường |
| Bước 1 — Ollama | `medium` | Cảnh báo, cho chọn |
| Bước 2 — TTS piper / edge | `none` | Chat bình thường |
| Bước 2 — TTS xtts / kokoro / vieneu | `medium` | Cảnh báo, cho chọn |
| Bước 3 — sinh video | `heavy` | Chặn, mặc định vai C |
| Bước 4 — autosub (whisper) | `heavy` | Chặn, mặc định vai C |
| Bước 5 — ghép video (ffmpeg) | `none` | Chat bình thường |

`GET /api/system/busy` trả thêm `gpu_weight` là mức cao nhất trong các task đang chạy.

### 5.4 Chờ VRAM thoát thật sau khi dừng tiến trình

L10: sau `is_running == False`, chờ thêm 1.5 giây, và nếu có `nvidia-smi` thì kiểm tra
`memory.free ≥ 3500MB` trước khi nạp model chat.

### 5.5 Ollama là phụ thuộc chưa được cài đặt ở đâu cả

L1: thêm `_start_ollama()` vào `desktop.py`, thêm bước kiểm tra vào `setup.bat`, và bảo đảm
vai C hoạt động **không cần Ollama** để trợ lý suy giảm êm thay vì chết hẳn.

---

## 6. Checklist trước buổi demo / bảo vệ

- [ ] `ollama serve` đang chạy (hoặc `_start_ollama()` đã làm việc đó) — kiểm tra
      `curl http://localhost:11434/api/version`
- [ ] `ollama pull qwen2.5:3b-instruct` đã xong, `GET /api/ollama/models` báo `installed: true`
- [ ] Mở panel → pre-warm chạy → câu hỏi đầu tiên trả lời trong <3 giây
- [ ] Rút mạng → hỏi lại → vẫn trả lời được (mọi thứ cục bộ)
- [ ] Tắt hẳn Ollama → panel vẫn mở, vai C tra cứu vẫn trả lời → **kịch bản dự phòng của
      buổi bảo vệ**
- [ ] Chạy Bước 3, hỏi trong lúc render → nhận trích dẫn tức thì, render không gián đoạn
- [ ] Hỏi một câu ngoài phạm vi → trợ lý từ chối, không bịa
- [ ] Chạy `scripts/eval_chatbot.py`, chụp lại bảng kết quả đưa vào báo cáo
