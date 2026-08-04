# Chatbot Trợ Lý — tầng agent: truy vấn dữ liệu và thực thi lệnh

> Chi tiết hoá **P5** trong [PLAN-chatbot-assistant.md](PLAN-chatbot-assistant.md), đã được
> chốt làm. Đọc kèm [PLAN-chatbot-scenarios.md](PLAN-chatbot-scenarios.md).
> **Nguyên tắc bao trùm:** giao cho model 3B càng ít việc càng tốt. Số liệu do code tính,
> hành động do người dùng bấm; model chỉ định tuyến ý định và diễn đạt kết quả.

---

## 1. Ba lớp năng lực, chia theo mức rủi ro

Không phải mọi "lệnh" đều giống nhau. Gộp chung một cơ chế là sai lầm phổ biến nhất khi làm
agent.

| Lớp | Ví dụ | Rủi ro khi model hiểu sai | Cơ chế |
|---|---|---|---|
| **L1 — Truy vấn** | "truyện C có bao nhiêu âm thanh", "A và B đã chạy bao nhiêu video" | Gần như bằng 0 — chỉ đọc | **Thực thi ngay**, không xác nhận. Số liệu do code tính, không qua model |
| **L2 — Điều hướng** | "chuyển sang truyện A", "mở Bước 3" | Thấp — đảo lại một cú bấm | Thực thi ngay, có nút **Hoàn tác** |
| **L3 — Chạy pipeline** | "cào và dịch 20 chương", "gen hình ảnh" | **Cao** — 40 phút GPU, ghi đè file, tốn quota API | **Luôn** hiện thẻ xác nhận đủ tham số, chờ người dùng bấm |

Hệ quả quan trọng: **L1 không cần LLM để lấy số**. Câu "Truyện C đã có bao nhiêu âm thanh và
chap bao nhiêu" là một phép đếm tất định trên đĩa. Model chỉ được dùng để hiểu *ý định* và
viết một câu dẫn — con số hiển thị bằng thẻ dữ liệu do `chat.js` render, model không chạm vào.
Nhờ vậy **số liệu không bao giờ sai kể cả khi model kém**, và L1 vẫn chạy khi Ollama tắt.

---

## 2. Bộ công cụ

Mọi công cụ đều ánh xạ tới code đã có, không viết mới phần lõi.

### 2.1 L1 — Truy vấn (thực thi ngay)

| Tool | Tham số | Nguồn dữ liệu |
|---|---|---|
| `list_stories()` | — | [`StorageManager.list_stories()`](../orchestrator/storage.py) + `_scan_chapters` |
| `story_report(story)` | tên/slug | `read_story_meta` + `_scan_chapters` → tổng chương, số `.wav`, số `.mp4`, chương dở dang |
| `compare_stories(stories[])` | 2–5 truyện | lặp `story_report` |
| `chapters_missing(story, kind)` | `kind` = `tts` \| `video` | `_scan_chapters` lọc `status` |
| `story_videos(story)` | | thư mục `video/` (như [`get_story_videos()` — main.py:568](../orchestrator/main.py)), phân biệt `TongHop_` |
| `system_status()` | — | `get_gpu_info()` + `list_running()` + `db.stats()` |
| `disk_usage(story?)` | | `StorageManager._dir_size` |

### 2.2 L2 — Điều hướng (thực thi ngay, hoàn tác được)

| Tool | Ánh xạ client |
|---|---|
| `select_story(name)` | `selectStory()` — [app.js:127](../webui/app.js) |
| `open_tab(tab)` | `initTabs()` handler — [app.js:59](../webui/app.js) |
| `set_field(step, field, value)` | gán `.value` vào đúng `id` form, **không** chạy gì |

### 2.3 L3 — Hành động (xác nhận bắt buộc)

| Tool | Ánh xạ client | Ghi chú |
|---|---|---|
| `run_step(n, story, overrides{})` | `buildStepNPayload()` + `postPipelineAction()` | n = 1..5 |
| `run_auto_chain(story)` | `startAutoRun()` — [app.js:382](../webui/app.js) | chuỗi 1→3 |
| `stop_task(task_key)` | `stopPipelineTask()` — [app.js:1144](../webui/app.js) | |

### 2.4 Không phải tool — vẫn là vai A

"Nên chọn mô hình sinh ảnh nào", "giới thiệu tôi cách dùng" → trả lời từ KB. Danh sách
checkpoint là **6 mục cố định** trong [index.html:447](../webui/index.html) (Anything V5,
DreamShaper 8, MajicMix Realistic, Cetus-Mix, RPG v4, MeinaMix) — viết thành một bảng
"chọn cái nào khi nào" trong `docs/kb/03-buoc3-video.md`, không cần tool.

---

## 3. Kiến trúc thực thi: **server đề xuất — client thực thi**

Đây là quyết định kiến trúc quan trọng nhất của tầng agent.

```
Người dùng gõ lệnh
   ▼
POST /api/chat  ── server định tuyến ý định
   ▼
Server trả về  { "reply": "...", "actions": [ ... ] }   ← CHỈ MÔ TẢ, không thực thi
   ▼
chat.js:
   L1 → gọi luôn /api/agent/query, render thẻ dữ liệu
   L2 → gọi hàm JS sẵn có, hiện nút Hoàn tác
   L3 → dựng THẺ XÁC NHẬN; chỉ khi người dùng bấm mới gọi buildStepNPayload() + postPipelineAction()
```

**Vì sao server không tự chạy pipeline:**

`buildStep3Payload()` ([app.js:253](../webui/app.js)) đọc **giá trị DOM** của 15 trường form.
Nếu server tự dựng payload, nó phải tái tạo toàn bộ logic đó từ `ui_settings.json` — và hai
đường sẽ **trôi lệch** ngay lần đầu ai đó thêm một trường mới vào form. Ngoài ra
`postPipelineAction()` còn nối SSE log, đổi trạng thái nút, đăng ký task để khôi phục sau
reload. Chạy vòng qua nó sẽ để lại UI mất đồng bộ: pipeline đang chạy mà nút vẫn hiện "Chạy".

Đi qua client thì agent **thừa hưởng miễn phí** toàn bộ validation, đồng bộ UI và luồng log
hiện có. Đây cũng là lớp an toàn tự nhiên: không có đường nào để một câu chat khởi động job
40 phút mà không qua một cú bấm chuột.

Riêng L1 truy vấn thì ngược lại — dữ liệu nằm ở server, nên có endpoint riêng
`POST /api/agent/query` trả JSON thuần, không qua LLM.

---

## 4. Định tuyến ý định — 3 tầng, **không** dùng tool-calling tự do

Model 3B *có* hỗ trợ tool calling, nhưng trích sai tham số đủ thường xuyên để không thể giao
phó một lệnh tốn 40 phút GPU. Thay bằng thang leo dần, mỗi tầng chỉ chạy khi tầng trước
không quyết được:

**Tầng 1 — khớp mẫu tất định (không gọi LLM).** Phủ ~70% lệnh thường dùng:

```python
(r"\b(cào|cao|crawl)\b.*?(\d+)\s*chương",           "run_step", {"n": 1, "max_chapters": "$2"}),
(r"\b(gen|sinh|tạo)\s*(hình ảnh|ảnh|video)\b",      "run_step", {"n": 3}),
(r"\b(chuyển|đổi)\s*(sang|qua)\s*truyện\s+(.+)",    "select_story", {"name": "$3"}),
(r"bao nhiêu\s*(video|âm thanh|chương|chap)",       "story_report", {}),
```

Chính xác 100%, độ trễ ~0ms, không tốn VRAM — và **chạy được khi Ollama tắt**.

**Tầng 2 — LLM với JSON schema ràng buộc.** Ollama hỗ trợ `format` là JSON Schema; ép model
trả đúng khuôn thay vì để nó tự do gọi tool:

```jsonc
{"type":"object","required":["intent"],"properties":{
  "intent":{"enum":["query","navigate","run_step","advice","clarify"]},
  "stories":{"type":"array","items":{"type":"string"}},
  "step":{"type":"integer","minimum":1,"maximum":5},
  "max_chapters":{"type":"integer","minimum":1,"maximum":500}}}
```

Schema có `minimum`/`maximum` là hàng rào thật: model bịa `max_chapters: 5000` sẽ bị JSON
schema loại, không lọt xuống thẻ xác nhận.

**Tầng 3 — hỏi lại.** JSON không hợp lệ, thiếu tham số bắt buộc, hoặc tên truyện mơ hồ →
`intent: clarify`, hiện câu hỏi kèm chip lựa chọn. **Không đoán.** Đoán sai ở L1 chỉ là câu
trả lời sai; đoán sai ở L3 là 40 phút GPU và một thư mục file rác.

---

## 5. Thẻ xác nhận và kế hoạch nhiều bước

### 5.1 Thẻ xác nhận L3

Phải hiện **tham số đã phân giải**, vì đó chính là chỗ model 3B sai:

```
▶ Chạy Bước 1 — Cào & Dịch
   Truyện       Hoả Vân Lộ  (hvl)
   Số chương    20
   Nguồn        Thư mục cục bộ
   Engine dịch  Gemini local (localhost:7860)
   Ghi đè       Không — tiếp tục từ chương 13
   Ước tính     ~25–40 phút

   [ Chạy ]   [ Sửa tham số ]   [ Huỷ ]
```

"Sửa tham số" mở đúng tab với form **đã điền sẵn** — biến một lần hiểu sai thành một lần
chỉnh nhẹ, thay vì buộc người dùng gõ lại câu lệnh.

### 5.2 Kế hoạch nhiều bước

*"Chuyển sang Truyện A và gen hình ảnh"* → hai hành động khác lớp. Không gộp thành một xác
nhận, cũng không chạy tuốt:

```
Kế hoạch:
  ✓ 1. Chuyển sang truyện "Hoả Vân Lộ"        (đã xong — Hoàn tác)
  ⏸ 2. Chạy Bước 3 — Sinh video               (chờ xác nhận ↓)
```

L2 chạy ngay (đảo được), L3 dừng ở thẻ xác nhận. Người dùng thấy rõ cái gì đã xảy ra và cái
gì sắp xảy ra. **Không** cho chuỗi tự chạy tiếp sau xác nhận đầu — mỗi L3 một xác nhận riêng.

---

## 6. Phân giải tên truyện

Người dùng nói "truyện A", "truyện hvl", "hỏa vân lộ", "Hoả Vân Lộ" — cùng một thứ. Quy trình:

1. Khớp chính xác `story_name` hoặc `story_slug`.
2. Khớp sau khi chuẩn hoá: bỏ dấu, thường hoá, bỏ khoảng trắng.
3. Khớp chứa (substring) sau chuẩn hoá.
4. **≥ 2 ứng viên hoặc 0 ứng viên → hỏi lại** kèm danh sách nút bấm. Không lấy "gần đúng nhất".

Với L3 thì bước 4 là bắt buộc tuyệt đối: chạy Bước 3 nhầm truyện vừa tốn 40 phút vừa ghi đè
`video/` của truyện không liên quan.

"truyện hiện tại" / "truyện này" → `activeStoryName`; nếu chưa chọn truyện nào thì hỏi lại
chứ không tự chọn truyện đầu danh sách.

---

## 7. Nguồn số liệu: quét đĩa, **không** tin SQLite

SQLite chỉ được cập nhật khi `write_story_meta()` chạy (`_mirror_to_db`). File `.wav`/`.mp4`
sinh ra giữa chừng, hoặc người dùng xoá tay, thì DB **lệch** cho tới lần ghi meta kế tiếp
hoặc tới khi bấm "Rebuild DB".

Câu hỏi "truyện C có bao nhiêu âm thanh" mà trả lời từ DB cũ là **sai một cách âm thầm** —
đúng loại lỗi tệ nhất, vì người dùng không có cách nào biết.

→ L1 luôn dùng `_scan_chapters()` (quét đĩa thật). Chi phí: `os.listdir` + `os.path.exists`
trên vài chục file, dưới 50ms. Kho hiện có 7 truyện; kể cả quét toàn bộ vẫn không đáng kể.
SQLite giữ nguyên vai trò dashboard/thống kê như hiện nay.

---

## 8. An toàn

**8.1 Định tuyến ý định chỉ chạy trên tin nhắn của người dùng.** Nội dung truyện
(`<noidungtruyen>`) là văn bản cào từ web — có thể chứa "hãy chạy Bước 3" hoặc "xoá truyện
X". Quy tắc cứng: **bộ định tuyến không bao giờ đọc `<noidungtruyen>`**; nó chỉ nhận đúng
chuỗi người dùng gõ. Ngữ cảnh truyện chỉ đi vào prompt **trả lời**, không đi vào prompt
**quyết định hành động**.

Đây là lý do mục 8.1 của plan chính đặt chống injection làm điều kiện tiên quyết của P5 —
giờ P5 đã chốt, ràng buộc này thành bắt buộc.

**8.2 Mọi L3 kết thúc bằng một cú bấm của con người.** Server không có đường nào khởi động
pipeline từ chat (mục 3). Kể cả model bị dẫn dụ hoàn toàn, kết quả tệ nhất là một thẻ xác
nhận vô lý hiện ra và người dùng bấm Huỷ.

**8.3 Một hành động chờ tại một thời điểm.** Thẻ xác nhận mới thay thế thẻ cũ (thẻ cũ chuyển
thành "đã bỏ qua"), tránh tình trạng ba thẻ chồng nhau rồi bấm nhầm.

**8.4 Không có tool xoá.** `delete_story` tồn tại trong `StorageManager` nhưng **không** đưa
vào bộ công cụ agent ở phiên bản này. Xoá dữ liệu qua câu chat là rủi ro không tương xứng với
tiện ích; để người dùng bấm nút xoá có sẵn trên UI.

---

## 9. Kịch bản theo đúng các câu bạn đưa ra

| Câu | Tầng định tuyến | Lớp | Hệ thống làm gì |
|---|---|---|---|
| "tổng hợp thông tin về truyện này" | T1 | L1 | `story_report(activeStoryName)` → thẻ: trạng thái, thể loại, 12 chương, 12 wav, 8 mp4, dung lượng. LLM viết 1 câu nhận xét: "còn 4 chương chưa sinh video." |
| "truyện A và truyện B đã chạy bao nhiêu video" | T1 | L1 | `compare_stories(["A","B"])` → bảng 2 dòng. Tên mơ hồ → hỏi lại trước khi đếm |
| "truyện C đã có bao nhiêu âm thanh và chap bao nhiêu" | T1 | L1 | `story_report("C")` → "18 chương, 18 tệp âm thanh, 5 video". Quét đĩa, không qua DB |
| "chuyển sang truyện A và gen hình ảnh" | T1 | L2+L3 | Kế hoạch 2 bước: chuyển truyện ngay (có Hoàn tác) → thẻ xác nhận Bước 3 |
| "cào và dịch 20 chương truyện hiện tại" | T1 (regex bắt số 20) | L3 | Thẻ xác nhận Bước 1, `max_chapters: 20`, engine lấy từ form hiện tại |
| "nên chọn mô hình sinh ảnh nào" | — | vai A | KB `03-buoc3-video.md`: bảng 6 checkpoint + khuyến nghị theo thể loại và VRAM |
| "giới thiệu tôi sử dụng" | — | vai A | KB `00-tong-quan.md`, trả lời theo `active_tab` để bám chỗ người dùng đang đứng |

---

## 10. Lỗi đặc thù của tầng agent

| Mã | Tình huống | Xử lý |
|---|---|---|
| A1 | "gen hình ảnh" khi chưa có chương nào | Kiểm tra tiền đề **trước** khi hiện thẻ: Bước 3 cần `.md`, Bước 2 cần `.md`, Bước 5 cần ≥2 `.mp4`. Thiếu → nói rõ thiếu gì và đề xuất bước cần chạy trước |
| A2 | Ra lệnh chạy Bước 3 khi Bước 3 đang chạy | `_reject_if_auto_running` + `is_running` đã chặn ở server; agent phải kiểm **trước** để không hiện thẻ rồi mới báo lỗi |
| A3 | "cào 20 chương" nhưng đã có 13 chương | Thẻ ghi rõ "tiếp tục từ chương 14" hay "tải lại từ đầu" theo `continue_download` hiện tại — không để người dùng đoán |
| A4 | Model tầng 2 trả `max_chapters: 5000` | JSON schema `maximum: 500` loại; rơi xuống tầng 3 hỏi lại |
| A5 | Người dùng bấm "Chạy" sau khi đã đổi truyện ở sidebar | Thẻ ghi slug đã phân giải lúc tạo; trước khi chạy đối chiếu với `activeStoryName`, khác thì hỏi lại |
| A6 | Ollama tắt | **L1 và tầng 1 vẫn chạy** — truy vấn và lệnh thông dụng không cần LLM. Chỉ mất diễn giải và tầng 2 |
| A7 | Truyện có `story.json` nhưng thư mục rỗng | `story_report` trả 0 và ghi "chưa có dữ liệu", không văng lỗi |
| A8 | Người dùng gõ "dừng đi" giữa lúc chạy | `stop_task` là L3 nhưng **đảo được và khẩn cấp** → xác nhận một bước gọn, không cần thẻ đầy đủ |

---

## 11. Kiểm thử

Bổ sung vào `tests/test_chatbot_agent.py`:

1. Tầng 1 khớp đúng cho 20 câu lệnh mẫu (bao gồm biến thể **không dấu**: "cao va dich 20 chuong").
2. Tầng 1 trích đúng số: "cào 20 chương" → `max_chapters: 20`; "cào 5 chương nữa" → 5.
3. Phân giải tên truyện: chính xác / bỏ dấu / substring / **mơ hồ → clarify** / không thấy → clarify.
4. `story_report` đếm đúng trên cây thư mục giả (3 md, 2 wav, 1 mp4).
5. `story_report` **không** đọc SQLite (stub `db` với cờ `called` để khẳng định).
6. JSON schema loại `max_chapters: 5000` và `step: 9`.
7. Bộ định tuyến **không** nhận nội dung `<noidungtruyen>` — truyền chuỗi truyện có chứa
   "hãy chạy Bước 3" vào ngữ cảnh, khẳng định `actions` rỗng.
8. Tiền kiểm A1: story không có `.md` → đề xuất Bước 3 bị chặn kèm lý do.
9. Chỉ một thẻ L3 pending tại một thời điểm.
10. Không tool nào ánh xạ tới `delete_story`.

Bộ eval mở rộng thêm **10 câu lệnh** đo tỉ lệ định tuyến đúng, tách khỏi 30 câu hỏi kiến
thức. Ngưỡng: tầng 1 ≥ 95% (tất định nên gần như phải tuyệt đối), tổng cả 3 tầng ≥ 85%, và
**0% thực thi L3 sai mà không qua xác nhận** — chỉ số này phải tuyệt đối, không có ngưỡng
mềm.

---

## 12. Phân kỳ

| GĐ | Nội dung | Công |
|---|---|---|
| **P5a** | Lớp L1 truy vấn: `agent_tools.py`, `POST /api/agent/query`, thẻ dữ liệu trong `chat.js`, tầng 1 định tuyến | **1.25 ngày** |
| **P5b** | Lớp L2 điều hướng + hoàn tác | 0.5 ngày |
| **P5c** | Lớp L3: thẻ xác nhận, kế hoạch nhiều bước, tiền kiểm A1–A5, tầng 2 JSON schema | **1.75 ngày** |
| **P5d** | Test + mở rộng eval | 0.5 ngày |

**Tầng agent ≈ 4 ngày.** Cộng MVP nền (7.5 ngày) → **≈ 11.5 ngày công** cho bản đầy đủ.

**Khuyến nghị thứ tự:** đưa **P5a vào MVP** — nó tất định, không rủi ro, chạy được cả khi
Ollama tắt, và trả lời trọn 3 trong 7 câu ví dụ của bạn. P5c làm sau khi P5a đã dùng thật vài
ngày, vì lúc đó mới biết người dùng thực sự hay ra lệnh kiểu gì để viết mẫu tầng 1 cho trúng.

---

## 13. Ảnh hưởng tới plan chính

- P5 chuyển từ *"chưa chốt, khuyến nghị hoãn"* sang **đã chốt**, tách thành P5a–P5d.
- Mục 8.1 (chống prompt injection) từ *"nên có"* thành **bắt buộc**, kèm ràng buộc cứng ở
  mục 8.1 tài liệu này: bộ định tuyến không đọc nội dung truyện.
- Thêm `docs/kb/03-buoc3-video.md` bảng 6 checkpoint — phục vụ câu "nên chọn mô hình nào".
- Tổng ước lượng: 7.5 → **11.5 ngày công**.
