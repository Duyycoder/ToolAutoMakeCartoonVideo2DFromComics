# Chương 02. Giao diện WebUI & giao tiếp realtime (HTML/CSS/JS thuần, REST, SSE)

Mục tiêu chương: sau khi đọc xong, bạn giải thích được (1) trình duyệt vẽ và điều khiển giao diện thế nào (DOM, event loop, `fetch` ), (2) giao diện nói chuyện với backend bằng REST ra sao, (3) log tiến độ "chảy" từ một tiến trình Python con lên màn hình theo thời gian thực bằng Server-Sent Events (SSE) như thế nào, tới mức từng byte trên đường truyền HTTP, và (4) vì sao nhóm chọn HTML/CSS/JS thuần thay vì React/Vue.

Mọi dẫn chứng đều trỏ vào code thật: `webui/index.html` (1362 dòng), `webui/app.js` (2096 dòng), `webui/chat.js` (516 dòng), `webui/style.css` (1744 dòng), `webui/chat.css` (628 dòng), `orchestrator/main.py` (1185 dòng), `orchestrator/process_manager.py` (305 dòng). Số dòng đếm bằng `wc -l` ở thời điểm viết tài liệu; tài liệu cũ `docs/trinh-` `bay-datn.md` ghi `index.html` 1.348 dòng và `app.js` 1.954 dòng, đã lỗi thời, đừng đọc con số cũ đó khi bảo vệ.

## 1. Vai trò của WebUI trong hệ thống

### 1.1. Vị trí trong kiến trúc

Hệ thống có 3 tầng:

- **Tầng:** Giao diện (presentation) · **Thành phần:** `webui/` (HTML/CSS/JS thuần) · **Chạy ở đâu:** Trong cửa sổ WebView2 (hoặc trình duyệt nếu thiếu WebView2)
- **Tầng:** Điều phối (orchestration) · **Thành phần:** `orchestrator/main.py` (FastAPI) + `pipeline.py` , `process_manager.py` , `auto_run.py` , `chatbot.py` · **Chạy ở đâu:** Tiến trình Python, uvicorn ở `127.0.0.1:8100`
- **Tầng:** Xử lý AI (workers) · **Thành phần:** Submodule `toolCaoTruyen/` (cào + dịch), `AIVoice/` (TTS, MediaComposer: sinh ảnh, dựng video, autosub) · **Chạy ở đâu:** Các subprocess Python riêng do orchestrator khởi chạy

WebUI không làm bất kỳ việc AI nào. Nó chỉ:

1. Thu thập tham số người dùng chọn (engine dịch, giọng đọc, style ảnh, checkpoint...). 2. Gửi tham số đó cho orchestrator qua REST API (HTTP + JSON). 3. Nhận log tiến độ realtime qua SSE và hiển thị lên "console" của từng bước. 4. Hiển thị trạng thái (truyện đang chọn, badge trạng thái, GPU, thống kê). 5. Cung cấp widget Trợ lý AI (chatbot RAG) — nhận câu trả lời dạng stream NDJSON.

### 1.2. Cách WebUI được phục vụ và hiển thị

Orchestrator phục vụ chính các file tĩnh của `webui/` : `app.mount("/", StaticFiles(directory=webui_dir, html=True),` `name="webui")` ở cuối `orchestrator/main.py:1183-1185` . Vì mount ở cuối file, các route `/api/...` khai báo trước được ưu tiên khớp; mọi đường dẫn còn lại rơi vào thư mục tĩnh, `html=True` nghĩa là `/` trả về `index.html` . Vì trang và API cùng origin ( `http://127.0.0.1:8100` ), trong `app.js:2` có `const API_BASE = "";` — mọi `fetch` dùng đường dẫn tương đối như `/api/stories` . Không cần CORS cho luồng chính; CORS middleware trong `main.py:44-50` chỉ cho phép đúng hai origin `http://127.0.0.1:8100` và `http://localhost:8100` (phục vụ debug). Launcher desktop `orchestrator/desktop.py` chạy uvicorn trong một thread ( `_start_server()` , dòng 101-108), chờ cổng 8100 mở ( `_wait_until_ready` , timeout 30 s), rồi mở cửa sổ `webview.create_window("AutoCartoon Video Maker",` `"http://127.0.0.1:8100/", width=1280, height=840, min_size=(1100, 720))` (dòng 190-197). Nếu thiếu `pywebview` hoặc WebView2 Runtime thì fallback về trình duyệt ( `_run_browser_fallback` ).

WebView2 là engine Chromium (Microsoft Edge) nhúng vào ứng dụng Windows. Vì vậy mọi kiến thức "trình duyệt" dưới đây áp dụng y hệt cho cửa sổ app.

### 1.3. Input/Output của WebUI

- **Chiều:** Vào (từ người dùng) · **Nội dung:** Click, gõ, chọn dropdown, kéo chuột vẽ vùng OCR · **Định dạng:** DOM events
- **Chiều:** Ra (tới backend) · **Nội dung:** Payload từng bước ( `buildStep1Payload()` ...), cấu hình · **Định dạng:** `POST` JSON
- **Chiều:** Vào (từ backend) · **Nội dung:** Danh sách truyện, meta truyện, config, trạng thái task · **Định dạng:** JSON (REST)
- **Chiều:** Vào (từ backend, realtime) · **Nội dung:** Log từng dòng của subprocess · **Định dạng:** `text/event-stream` (SSE)
- **Chiều:** Vào (từ backend, realtime) · **Nội dung:** Câu trả lời chatbot theo token · **Định dạng:** `application/x-ndjson` qua `fetch` + `ReadableStream`

## 2. Nền tảng lý thuyết từ gốc

### 2.1. Trình duyệt biến HTML thành giao diện thế nào — DOM

Trực giác. File HTML giống bản vẽ mặt bằng ngôi nhà. Trình duyệt đọc bản vẽ và dựng một "mô hình ngôi nhà" trong bộ nhớ: đó là DOM (Document Object Model) — một cây các object, mỗi thẻ HTML là một node.

Cơ chế. Quy trình render của trình duyệt (đơn giản hoá):

1. Parse HTML → cây DOM. 2. Parse CSS → CSSOM (cây quy tắc style). 3. Ghép DOM + CSSOM → render tree (chỉ gồm node được hiển thị; node `display:none` bị loại). 4. Layout (tính vị trí, kích thước) → Paint (tô pixel) → Composite (ghép lớp).

JavaScript thao tác trên DOM qua API: `document.getElementById` , `querySelectorAll` , `createElement` , `appendChild` , `classList.add/remove` , `element.style.display` ... Mỗi lần DOM thay đổi, trình duyệt có thể phải layout/paint lại.

Trong dự án:

Toàn bộ giao diện là một trang duy nhất (Single Page): 7 `<section class="tab-panel">` nằm sẵn trong `index.html` ; "chuyển tab" chỉ là ẩn/hiện section bằng CSS: `.tab-panel { display: none; }` và `.tab-panel.active { display: flex;` `... }` ( `style.css:589-595` ). Vì section ẩn có `display:none` nên nó không vào render tree → không tốn layout. `initTabs()` ( `app.js:59-71` ) gắn listener cho mọi `.nav-item` ; khi click, gỡ class `active` khỏi tất cả rồi thêm `active` cho nút được bấm và cho `#tab-${data-tab}` .

```
function initTabs() {
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetTab = item.getAttribute("data-tab");
            navItems.forEach(nav => nav.classList.remove("active"));
            tabPanels.forEach(panel => panel.classList.remove("active"));
            item.classList.add("active");
            document.getElementById(`tab-${targetTab}`).classList.add("active");
        });
    });
}
```

Chống XSS bằng `textContent` . Log từ subprocess có thể chứa ký tự `<` , `>` . `appendConsoleLog()` ( `app.js:1271-1288` ) tạo `<span>` và gán `span.textContent = text` — trình duyệt coi đó là chữ thuần, không parse thành HTML, nên log không thể chèn thẻ `<script>` . Trong chatbot, `renderMarkdown()` ( `chat.js:28-41` ) gọi `escapeHTML()` trước rồi mới thay `**...**` thành `<strong>` , cũng để chống XSS. Tab Thống kê có `_statEsc()` ( `app.js:2046-2048` ) escape `&<> "` trước khi nhét vào `innerHTML` . Ngoại lệ cần biết (trung thực): vẫn còn vài chỗ ghép chuỗi vào `innerHTML` không escape: tên file video trong `loadStoryVideos()` ( `label.innerHTML =`${v.name}... , `app.js:2020` ) và `story_slug` , `status` , tên task trong thẻ chatbot `renderCard()` ( `chat.js:276, 282, 291` ). Rủi ro thấp vì dữ liệu này do chính máy người dùng sinh ra (tên file trên đĩa, slug do server tạo), nhưng về nguyên tắc nên dùng `textContent` hoặc escape.

### 2.2. Sự kiện (events) và lan truyền sự kiện

- Event là tín hiệu "có chuyện xảy ra": `click` , `change` , `input` , `submit` , `mousedown` , `DOMContentLoaded` ... `addEventListener(type, handler)` đăng ký hàm xử lý. Sự kiện đi qua 3 pha: capture (từ `window` xuống phần tử), target, bubble (từ phần tử ngược lên gốc). Dự án tận dụng điều này ở mấy chỗ tinh tế: `el.dispatchEvent(new Event("change", { bubbles: true }))` trong `applyAllSettings()` ( `app.js:354` ): sau khi khôi phục giá trị một ô (vd engine dịch), code tự bắn sự kiện `change` để các handler ẩn/hiện nhóm phụ thuộc chạy lại — giống như người dùng vừa tự chọn. Sự kiện `invalid` của form không bubble, nên `buildSdMirror()` đăng ký với `capture = true` ( `app.js:1883-1886` ) để bắt được khi một ô không hợp lệ nằm trong `<details>` đang đóng, rồi mở `<details>` ra cho người dùng thấy lỗi. `e.preventDefault()` ở handler `submit` của mỗi form (vd `app.js:765` ) chặn hành vi mặc định (tải lại trang, gửi form kiểu cũ) để JS tự gửi bằng `fetch` .

### 2.3. Event loop của trình duyệt — vì sao giao diện không "đơ"

Trực giác. JavaScript trong trang chạy trên một luồng duy nhất (main thread) — giống một đầu bếp duy nhất trong bếp. Nếu đầu bếp đứng chờ nồi nước sôi (chờ mạng), cả bếp đứng. Giải pháp: đầu bếp đặt nồi lên bếp, dán giấy nhắc "sôi thì gọi tôi", rồi làm việc khác. Đó là event loop.

Cơ chế.

- **Thành phần:** Call stack · **Vai trò:** Nơi các hàm đang thực thi được xếp chồng
- **Thành phần:** Web APIs (do trình duyệt cung cấp, chạy ngoài luồng JS) · **Vai trò:** Mạng ( `fetch` , `EventSource` ), timer ( `setTimeout` ), sự kiện DOM
- **Thành phần:** Task queue (macrotask) · **Vai trò:** Callback của timer, sự kiện UI, tin nhắn SSE ( `onmessage` )
- **Thành phần:** Microtask queue · **Vai trò:** Tiếp nối của Promise ( `.then` , phần sau `await` )

Vòng lặp: lấy 1 macrotask → chạy tới khi call stack rỗng → chạy hết microtask → (nếu cần) render lại màn hình → lặp lại.

Hệ quả với code dự án:

- `async function` + `await fetch(...)` : tại `await` , hàm nhường luồng; trình duyệt vẫn render, vẫn nhận click. Khi response về, phần còn lại của hàm được xếp vào microtask queue. Ví dụ `DOMContentLoaded` handler ( `app.js:28-38` ) `await` `loadStories(); await loadGlobalConfig(); await loadAndApplySettings();` — tuần tự về logic nhưng không chặn giao diện. Mỗi tin SSE đến là một macrotask gọi `source.onmessage` . Render diffusion có thể phun hàng chục nghìn dòng log → hàng chục nghìn lần thêm `<span>` . Vì thế `MAX_CONSOLE_LINES = 4000` ( `app.js:1269` ): khi vượt trần, xoá dòng cũ nhất. Comment trong code ghi rõ lý do: không cắt thì WebView2 "phình bộ nhớ tới mức Out of Memory và sập trang". Polling dùng `setTimeout(pollAutoRun, 2000)` ( `app.js:482` ) chứ không dùng vòng `while` — vòng `while` sẽ chiếm call stack và đóng băng UI.

2.4. HTTP, REST và `fetch`

HTTP là giao thức request/response chạy trên TCP (HTTP/1.1 — phiên bản uvicorn phục vụ ở đây — có định dạng văn bản; HTTP/2 thì đóng khung nhị phân). Một request gồm: method ( `GET` , `POST` , `DELETE` ...), path, headers, body. Response gồm: status code (200, 400, 404, 409, 429, 500, 503, 504...), headers (vd `Content-Type` ), body.

REST (Representational State Transfer) là phong cách thiết kế API: coi dữ liệu là tài nguyên có URL ( `/api/stories/{story_name}` ), dùng method HTTP để nói hành động (GET = đọc, POST = tạo/kích hoạt, DELETE = xoá), stateless (mỗi request tự mang đủ thông tin). Dự án theo REST "thực dụng": tài nguyên dữ liệu ( `/api/stories` , `/api/config` ) đúng REST; còn các lệnh chạy ( `POST /api/pipeline/step1` ) là kiểu RPC-over-HTTP — hợp lý vì "chạy bước 1" là hành động, không phải tài nguyên.

`fetch` là Web API trả về Promise:

```
const response = await fetch(`${API_BASE}/api/pipeline/${stepName}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
});
if (!response.ok) {
    const err = await response.json();
    alert(`Lỗi khởi chạy: ${err.detail}`);
    return null;
}
const data = await response.json();
return data.task_key;
```

( `postPipelineAction` , `app.js:1172-1196` )

Hai chi tiết quan trọng:

- 1. `fetch` chỉ reject khi lỗi mạng; HTTP 400/500 vẫn resolve bình thường → phải tự kiểm `response.ok` (true khi status 200- 299). Code dự án làm đúng điều này. 2. Backend FastAPI trả lỗi dạng `{"detail": "..."}` khi `raise HTTPException(...)` → frontend đọc `err.detail` .

Phía server, FastAPI dùng Pydantic để validate body: ví dụ `Step3Schema` ( `main.py:147-165` ) khai báo kiểu và giá trị mặc định ( `genre="tien_hiep"` , `style="thuy_mac"` , `checkpoint="anything-v5"` , `bgm_volume=0.15` , `render_mode="auto"` ...). Body sai kiểu → FastAPI tự trả 422 Unprocessable Entity trước khi vào hàm.

`{ cache: "no-store" }` được dùng cho các request trạng thái ( `/api/pipeline/status/...` , `/api/ui-settings` , `/api/pipeline/auto-run/...` , `/api/stats` ) để trình duyệt không trả kết quả cũ từ cache — trạng thái task phải luôn là hiện tại.

### 2.5. Bài toán realtime: server muốn "nói trước"

HTTP gốc là client hỏi – server đáp. Nhưng Bước 3 (dựng hoạt hình) có thể chạy nhiều giờ ( `app.js:421` tự ghi "Bước 3 có thể chạy nhiều giờ") và in log liên tục. Làm sao đẩy log từ server lên màn hình ngay khi có?

Có 4 phương án kinh điển:

- **Phương án:** Short polling · **Cách làm:** Client hỏi định kỳ (vd 2 s/lần) · **Ưu:** Cực đơn giản, qua mọi proxy · **Nhược:** Trễ tối đa = chu kỳ; phí request rỗng; log giữa hai lần hỏi phải gom lại
- **Phương án:** Long polling · **Cách làm:** Client hỏi, server giữ request tới khi có dữ liệu rồi mới trả; client hỏi lại ngay · **Ưu:** Gần realtime · **Nhược:** Mỗi tin = 1 request mới; code server phức tạp
- **Phương án:** SSE (Server- Sent Events) · **Cách làm:** 1 response HTTP không bao giờ kết thúc, server ghi dần các "event" dạng text · **Ưu:** Một chiều server→client, chuẩn HTML5, tự reconnect, chỉ là HTTP thường · **Nhược:** Chỉ một chiều; chỉ text (UTF-8); giới hạn số kết nối/origin ở HTTP/1.1
- **Phương án:** WebSocket · **Cách làm:** Nâng cấp (Upgrade) kết nối HTTP thành kênh song công nhị phân/text · **Ưu:** Hai chiều, độ trễ thấp nhất · **Nhược:** Giao thức riêng (frame, ping/pong, handshake), phải tự viết reconnect, server phải hỗ trợ WS

Analogy dễ nói trước hội đồng:

- Polling = cứ 2 phút gọi điện hỏi "xong chưa?". SSE = nghe đài phát thanh: bật đài một lần, đài phát liên tục, mình chỉ nghe. WebSocket = gọi điện thoại: hai bên nói qua lại.

### 2.6. SSE ở mức giao thức HTTP — từng byte

Request (trình duyệt tự gửi khi tạo `new EventSource(url)` ):

```
GET /api/pipeline/logs/dac-ky-tru-vuong_step3 HTTP/1.1
Host: 127.0.0.1:8100
Accept: text/event-stream
Cache-Control: no-cache
```

Response (server giữ kết nối mở và ghi dần; các dòng log dưới đây là ví dụ minh hoạ định dạng, không phải log thật được trích; header `charset=utf-8` do Starlette tự thêm cho media type `text/*` , `chunked` do uvicorn dùng khi không biết trước độ dài body):

```
HTTP/1.1 200 OK
content-type: text/event-stream; charset=utf-8
transfer-encoding: chunked
```

```
data: [Pipeline] Bắt đầu ...
```

```
data: {"event": "tts_file_start", "index": 1, "total": 5, "file": "chuong_001.md"}
```

```
data: [PING]
```

```
data: [SYSTEM] Process completed (exit_code=0).
```

Quy tắc định dạng `text/event-stream` (chuẩn WHATWG HTML):

- **Trường:** `data:<text>` · **Ý nghĩa:** Nội dung. Nhiều dòng `data:` liên tiếp được nối bằng `\n` thành một message
- **Trường:** Dòng trống ( `\n\n` ) · **Ý nghĩa:** Kết thúc một event → trình duyệt phát `message`
- **Trường:** `event:<tên>` · **Ý nghĩa:** Loại event tuỳ chọn (mặc định là `message` )
- **Trường:** `id:<x>` · **Ý nghĩa:** ID event; khi reconnect, trình duyệt gửi header `Last-Event-ID:<x>`
- **Trường:** `retry:<ms>` · **Ý nghĩa:** Server đề nghị thời gian chờ trước khi reconnect
- **Trường:** Dòng bắt đầu bằng `:` · **Ý nghĩa:** Comment, bị bỏ qua (thường dùng làm heartbeat)

Tự reconnect. Nếu kết nối rớt (server restart, mạng chập chờn), `EventSource` phát `error` , chuyển `readyState` về `CONNECTING` và tự mở lại sau vài giây (giá trị mặc định do trình duyệt quyết định, thường khoảng 3 s, trừ khi server gửi `retry:` ). Chỉ khi gọi `source.close()` hoặc server trả status không phải 200 (vd `204 No Content` ) / content-type sai thì trình duyệt mới dừng hẳn.

Điểm hay bị hiểu sai: khi server kết thúc response một cách bình thường (generator `break` ), `EventSource` không coi đó là "xong" mà coi là rớt kết nối → phát `error` rồi tự nối lại. SSE không có khái niệm "stream đã hoàn tất". Vì vậy dự án phải tự định nghĩa một terminal message ( `[SYSTEM] Process completed...` ) và client phải chủ động `source.close()` khi nhận được nó ( `app.js:1312-1326` ). Nếu client lỡ tin đó và reconnect, server vẫn trả lại terminal message nhờ nhánh `q.empty() and completed` (mục 4.5c).

Dự án dùng tập con nào? Code server `ProcessManager._sse_data()` ( `process_manager.py:261-268` ) chỉ phát trường `data:` , không dùng `event:` , `id:` , `retry:` :

```
@staticmethod
def _sse_data(payload) -> str:
    """Mỗi dòng SSE phải có prefix data:, kể cả log nhiều dòng/dict cũ."""
    if isinstance(payload, dict):
        payload = payload.get("line", str(payload))
    text = str(payload).strip("\r\n")
    lines = text.splitlines() or [""]
    return "".join(f"data: {line}\n" for line in lines) + "\n"
```

Nghĩa là: một log nhiều dòng được tách thành nhiều dòng `data:` rồi kết bằng một dòng trống → client nhận một message có `\n` bên trong. Test `test_multiline_and_legacy_dict_logs_are_valid_sse` ( `tests/test_process_manager.py:124-134` ) đưa vào queue một log kiểu dict cũ `{"type": "stderr", "line": "first\nsecond\n"}` và khẳng định event đầu tiên phải đúng bằng `"data: first\ndata: second\n\n"` .

Heartbeat: thay vì comment `:` , server gửi một message thật `data: [PING]` mỗi khi queue rỗng quá 1 giây ( `process_manager.py:300-302` ), và client bỏ qua nó ( `if (rawLine==="[PING]") return;` , `app.js:1310` ). Tác dụng: (1) giữ kết nối "sống", tránh bị proxy/timeout cắt khi subprocess im lặng lâu (vd đang nạp model SD); (2) vòng lặp generator quay lại ít nhất mỗi 1 s để kiểm tra task đã `completed` chưa; (3) khi client ngắt, Starlette nhận `http.disconnect` và dừng stream — nhờ `q.get(timeout=1.0)` nên thread đang chạy generator không bị kẹt vô hạn mà thoát trong khoảng 1 s. (Chi tiết cơ chế phát hiện ngắt phụ thuộc phiên bản Starlette, nên khi trả lời chỉ cần nói ý chính.)

Ghi chú: `orchestrator/requirements.txt` có khai báo thư viện `sse-starlette>=1.6.0` , nhưng code không dùng (grep `EventSourceResponse` / `sse_starlette` trong `orchestrator/` không thấy). SSE được tự hiện thực bằng `StreamingResponse` + tự định dạng `data:` . Nếu hội đồng hỏi, trả lời đúng như vậy: phần SSE cần rất ít nên tự viết cho kiểm soát được định dạng; dependency đó là thừa.

2.7. NDJSON streaming qua `fetch` (dùng cho chatbot)

Chatbot cần gửi body POST (câu hỏi, session_id, tab đang mở...) và nhận câu trả lời theo token. `EventSource` chỉ hỗ trợ GET, không có body, nên chatbot dùng cách khác:

Server trả `StreamingResponse(..., media_type="application/x-ndjson")` ( `main.py:1035` ) — NDJSON = mỗi dòng là một JSON độc lập, kết thúc bằng `\n` . Client dùng `res.body.getReader()` (Streams API) + `TextDecoder` để đọc từng chunk byte, cộng vào `buffer` , tách theo `\n` , giữ lại mảnh dòng dở dang cuối ( `buffer = lines.pop()` ) cho lần đọc sau ( `chat.js:436-494` ). Hủy giữa chừng bằng `AbortController` ( `chat.js:403, 412` ): bấm nút "Dừng" gọi `abortController.abort()` → `fetch` ném `AbortError` → hiển thị "(Đã dừng sinh)". Phía server, generator kiểm `await request.is_disconnected()` ( `main.py:1016` ) để ngừng sinh.

Đây là một kiến thức hay để trả lời hội đồng: dự án dùng hai kỹ thuật streaming khác nhau cho hai nhu cầu khác nhau — SSE (GET, một chiều, tự reconnect) cho log pipeline; fetch-stream NDJSON (POST có body, hủy được bằng AbortController) cho chatbot.

### 2.8. Phía server: vì sao một HTTP response "không kết thúc" được?

FastAPI xây trên Starlette (ASGI). `StreamingResponse` nhận một iterator/generator; mỗi giá trị `yield` ra được ghi xuống socket ngay dưới dạng một chunk (HTTP/1.1 `Transfer-Encoding: chunked` ). `get_logs_generator()` là generator đồng bộ (hàm `def` có `yield` ). Starlette chạy iterator đồng bộ trong threadpool (để `q.get(timeout=1.0)` blocking không chặn event loop asyncio của uvicorn). Hệ quả: mỗi kết nối SSE đang mở giữ một worker thread của threadpool — không vấn đề với app local một người dùng, nhưng là điểm cần biết nếu mở rộng nhiều người dùng. Threadpool này (của AnyIO, mặc định khoảng 40 thread) cũng là nơi chạy mọi endpoint khai báo bằng `def` thường (vd `autosub_prepare` chạy `subprocess.run` đồng bộ tới 900 s), nên các tác vụ chặn lâu cùng chia một "bể" thread. Chatbot thì ngược lại: `async def generate_chat()` là async generator, vì bên trong nó `async for chunk in` `chat_stream_ollama(...)` gọi Ollama bằng `httpx.AsyncClient` stream ( `orchestrator/llm.py:94-165` ).

### 2.9. CSS: biến, layout, responsive

CSS Custom Properties (biến CSS): `:root {--bg-app: #0B0C0E;--accent: #F2683C;--success: #3FB950;--danger:` `#E5484D;... }` (khối `:root` ở `style.css:13-123` ). Thay một biến là đổi màu toàn app → thiết kế nhất quán ("design tokens"). Grid: `.panel-grid { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, .95fr); }` ( `style.css:606-` `610` ) chia mỗi tab thành 2 cột: form bên trái, console log bên phải. Responsive bằng `@media` : `max-width: 1400px` → lưới form thu còn 6 cột; `max-width: 1280px` → `.panel-grid` gộp thành 1 cột (log xuống dưới form); `max-width: 1100px` → sidebar thu còn icon 64 px ( `--sidebar-width: 64px` ); `max-width: 820px` → xếp dọc ( `style.css:1626-1690` ). `prefers-reduced-motion: reduce` tắt animation cho người nhạy cảm chuyển động ( `style.css:1691` ). Màu log: `.log-success` , `.log-error/.log-danger` , `.log-warn` , `.log-system` ( `style.css:1269-1291` ) — JS chỉ gán class, CSS lo màu. Tách hành vi (JS) và trình bày (CSS). Font Inter được tự host ( `webui/fonts/fonts.css` , preload `inter-latin.woff2` , `inter-vietnamese.woff2` — `index.html:8-` `10` ) thay vì Google Fonts → chạy offline được, đúng tinh thần "chạy local".

## 3. Vì sao chọn công nghệ này (so sánh phương án)

### 3.1. HTML/CSS/JS thuần vs React/Vue

- **Tiêu chí:** Build toolchain · **JS thuần (đang dùng):** Không cần (không Node, npm, bundler) — sửa file, F5 là thấy · **React/Vue:** Cần Node.js + Vite/Webpack, bước build
- **Tiêu chí:** Cài đặt trên máy người dùng · **JS thuần (đang dùng):** Chỉ Python (đã có sẵn vì AI cần) · **React/Vue:** Hoặc build sẵn, hoặc thêm Node vào installer
- **Tiêu chí:** Kích thước · **JS thuần (đang dùng):** ~5 file, không dependency frontend · **React/Vue:** Runtime framework + `node_modules`
- **Tiêu chí:** Bản chất ứng dụng · **JS thuần (đang dùng):** Form tham số + console log; state ít (truyện đang chọn, task đang chạy) · **React/Vue:** Tỏa sáng khi UI có nhiều state phức tạp phụ thuộc nhau
- **Tiêu chí:** Nhược điểm · **JS thuần (đang dùng):** Code DOM thủ công, `app.js` dài 2096 dòng, dễ lặp lại (nhiều handler ẩn/hiện) · **React/Vue:** Học thêm, phức tạp thêm tầng build

Lập luận chính khi bảo vệ: nút thắt cổ chai của hệ thống là GPU/AI, không phải giao diện. Giao diện chủ yếu là form và log, một người dùng, chạy local. Thêm framework chỉ tăng chi phí cài đặt/bảo trì (installer phải gói thêm Node hoặc bước build) mà không đổi được trải nghiệm đáng kể. KISS/YAGNI.

Cũng nên thừa nhận trung thực: khi `app.js` phình to, các kỹ thuật như `buildConfigMirror()` / `buildSdMirror()` (tự nhân bản control) là thứ framework có data-binding làm sẵn. Nếu phát triển tiếp, có thể tách `app.js` thành ES modules hoặc dùng thư viện nhẹ (Alpine.js, Preact) mà không cần build.

### 3.2. SSE vs WebSocket vs polling cho log

Lý do chọn SSE (khớp với code):

- 1. Luồng log một chiều server → client. Client không cần gửi gì qua kênh đó; lệnh dừng đi bằng REST riêng ( `POST` `/api/pipeline/stop` ). 2. SSE chỉ là HTTP thường: FastAPI làm được bằng `StreamingResponse(..., media_type="text/event-stream")` ( `main.py:509-515` ) — 4 dòng code. WebSocket cần endpoint `@app.websocket` , quản lý handshake, vòng nhận/gửi. 3. Tự reconnect có sẵn trong `EventSource` ; code chỉ bổ sung logic kiểm trạng thái khi `onerror` (mục 4.6). 4. Log là text → hợp giới hạn "chỉ UTF-8" của SSE.

Nhưng dự án không dùng SSE cho mọi thứ — chọn công cụ theo nhu cầu:

- **Nhu cầu:** Log từng bước · **Kỹ thuật:** SSE `GET /api/pipeline/logs/{task_key}` · **Lý do:** Một chiều, liên tục, tự reconnect
- **Nhu cầu:** Trạng thái chuỗi Auto- run 1→4 · **Kỹ thuật:** Short polling 2 s `GET /api/pipeline/auto-run/{story}` ( `app.js:467-496` ) · **Lý do:** Chỉ cần biết "đang ở bước mấy"; trễ 2 s chấp nhận được; đơn giản
- **Nhu cầu:** Kiểm tra task sau khi bấm Dừng · **Kỹ thuật:** Polling 400 ms × tối đa 25 lần (~10 s) ( `waitTaskStopped` , `app.js:215-234` ) · **Lý do:** Dự phòng khi SSE không còn mở
- **Nhu cầu:** Badge trạng thái chatbot · **Kỹ thuật:** Polling 10 s `GET /api/chat/health` ( `chat.js:126-127` ) · **Lý do:** Thông tin thay đổi chậm
- **Nhu cầu:** Câu trả lời chatbot · **Kỹ thuật:** fetch + ReadableStream (NDJSON) `POST /api/chat` · **Lý do:** Cần POST body + hủy bằng AbortController

## 4. Hiện thực trong code

### 4.1. Bản đồ file

- **File:** `webui/index.html` · **Dòng:** 1362 · **Vai trò:** Khung: sidebar (chọn truyện + 7 nav), header (Lưu cấu hình, Chạy tự động 1→4, badge), 7 `tab-` `panel` , `#chatWidget` , nạp `app.js` rồi `chat.js`
- **File:** `webui/app.js` · **Dòng:** 2096 · **Vai trò:** Toàn bộ logic pipeline: tab, truyện, payload, REST, SSE, lưu/khôi phục cấu hình, mirror cấu hình, ROI selector, thống kê
- **File:** `webui/chat.js` · **Dòng:** 516 · **Vai trò:** Widget Trợ lý AI, bọc trong IIFE `(function(){...})()` để không rò biến ra global
- **File:** `webui/style.css` · **Dòng:** 1744 · **Vai trò:** Design tokens, layout, console, modal, responsive
- **File:** `webui/chat.css` · **Dòng:** 628 · **Vai trò:** Style widget chat, badge `ready/busy/offline`
- **File:** `orchestrator/main.py` · **Dòng:** 1185 · **Vai trò:** Toàn bộ REST + SSE endpoint, mount static
- **File:** `orchestrator/process_manager.py` · **Dòng:** 305 · **Vai trò:** Subprocess + queue log + generator SSE

### 4.2. Các tab và chức năng

Chú ý đánh số lệch giữa hiển thị và nội bộ — hội đồng dễ hỏi:

- **Nút sidebar (hiển thị):** Bước 1: Nguồn & Dịch · **`data-tab` → section:** `step1` → `#tab-step1` · **Chức năng:** Nguồn: thư mục local, Sáng tác bằng AI, web 69shu/Mê Truyện Chữ/Tàng Thư Viện; dịch bằng Ollama/Gemini; glossary · **Endpoint chạy chính:** `POST /api/pipeline/step1` · **Task key:** `{slug}_step1`
- **Nút sidebar (hiển thị):** Bước 2: Sinh Giọng · **`data-tab` → section:** `step2` → `#tab-step2` · **Chức năng:** TTS: edge, clone (XTTS), piper, kokoro, vieneu; chuẩn hoá LUFS, fade, cache ngữ nghĩa · **Endpoint chạy chính:** `POST /api/pipeline/step2` · **Task key:** `{slug}_step2`
- **Nút sidebar (hiển thị):** Bước 3: Dựng Hoạt Hình · **`data-tab` → section:** `step3` → `#tab-step3` · **Chức năng:** Genre, style, checkpoint SD, BGM, upscale, render mode, LLM tách cảnh, tham số sinh ảnh · **Endpoint chạy chính:** `POST /api/pipeline/step3` · **Task key:** `{slug}_step3`
- **Nút sidebar (hiển thị):** Bước 4: Ghép Video · **`data-tab` → section:** `step5` → `#tab-step5` · **Chức năng:** Chọn ≥ 2 file `.mp4` và ghép · **Endpoint chạy chính:** `POST /api/pipeline/step5` · **Task key:** `{slug}_step5`
- **Nút sidebar (hiển thị):** Tự Động Tạo Phụ Đề · **`data-tab` → section:** `step4` → `#tab-step4` · **Chức năng:** Công cụ rời: video local/URL → Whisper hoặc OCR → dịch → burn sub, lồng tiếng · **Endpoint chạy chính:** `POST /api/autosub/prepare` , `POST /api/pipeline/step4` · **Task key:** `{slug}_step4` hoặc `autosub_{uuid8}_step4`
- **Nút sidebar (hiển thị):** Cấu Hình Chung · **`data-tab` → section:** `settings` · **Chức năng:** API key, URL Ollama/Gemini proxy, mặc định mọi bước, tham số SD, chatbot, `storage_dir` · **Endpoint chạy chính:** `POST /api/config` · **Task key:** —
- **Nút sidebar (hiển thị):** Thống Kê · **`data-tab` → section:** `stats` · **Chức năng:** Thẻ số liệu từ SQLite, dọn thư mục tạm, đồng bộ lại CSDL · **Endpoint chạy chính:** `GET /api/stats` , `POST` `/api/maintenance/...` · **Task key:** —

Nguồn gốc lệch số: autosub được thêm sau, là công cụ rời không thuộc chuỗi chính. `orchestrator/auto_run.py:1-6` ghi rõ: "trên UI 'Bước 4: Ghép Video' là task nội bộ `step5` (merge); tab autosub ( `step4` ) là công cụ rời, KHÔNG nằm trong chuỗi". Frontend có bảng ánh xạ `INTERNAL_STEP_BY_DISPLAY = { 1: 1, 2: 2, 3: 3, 4: 5 }` ( `app.js:402` ), backend có `DISPLAY_NO = {1: 1, 2:` `2, 3: 3, 5: 4}` ( `auto_run.py:20` ).

### 4.3. Khởi động trang

```
document.addEventListener("DOMContentLoaded", async () => {
    initTabs();
    setupEventHandlers();
                            // gắn listener TRƯỚC để applyAllSettings dispatch 'change' có tác dụng
    buildConfigMirror();
                            // nhân bản control từng bước vào Cấu Hình Chung
    fetchGpuInfo();
    await loadStories();
    await loadGlobalConfig();
    // Cấu hình người dùng đã lưu phải áp SAU CÙNG để thắng các giá trị default
    await loadAndApplySettings();
    resumeAutoRunUi();
});
```

( `app.js:28-38` )

Thứ tự này có chủ ý — một câu hỏi hay:

- 1. Gắn listener trước, vì lát nữa khôi phục cấu hình sẽ `dispatchEvent("change")` — listener chưa gắn thì ẩn/hiện nhóm phụ thuộc không chạy. 2. `buildConfigMirror()` trước `loadGlobalConfig()` vì phải có control clone trong tab Cấu Hình thì mới điền giá trị config vào được. 3. `fetchGpuInfo()` không `await` — chạy song song, không chặn phần còn lại. 4. Ưu tiên: mặc định trong HTML < global_config.json ( `loadGlobalConfig` ) < ui_settings.json ( `loadAndApplySettings` ). Cái áp sau thắng. 5. `resumeAutoRunUi()` hỏi server xem chuỗi tự động có đang chạy không (sau khi reload trang).

`chat.js` được nạp sau `app.js` ( `index.html:1359-1360` ), tự khởi động qua `DOMContentLoaded` hoặc chạy ngay nếu DOM đã sẵn ( `chat.js:511-515` ).

### 4.4. Luồng "Bấm Bắt đầu Bước N" — từ click tới subprocess

Lấy Bước 3 làm ví dụ ( `app.js:822-837` ):

- 1. `submit` của `#formStep3` → `e.preventDefault()` ; nếu chưa chọn truyện thì `alert` . 2. `buildStep3Payload()` ( `app.js:289-312` ) đọc ~17 ô thành JSON: `genre` , `style` , `checkpoint` , `bgm_path` , `bgm_volume` , `enable_upscale` , `burn_subtitles` , `use_semantic_split` , `extract_characters` , `enable_face_detailer` , `render_mode` , `hardware_profile` , `device` , `llm_engine` , `llm_api_key` , `llm_offline_base_url` , `llm_offline_model` (Ollama thì lấy từ `s3OllamaModel` , ngược lại từ `s3LlmModel` ). 3. `toggleFormButtons("step3", true)` — ẩn nút Bắt đầu, hiện nút Dừng; `clearConsole("step3")` . 4. `postPipelineAction("step3", payload)` :

- Gọi trước `POST /api/chat/unload` ( `app.js:1174-1176` ) để nhả model chatbot khỏi VRAM ( `unload_ollama` với `keep_alive=0` ) — tránh chatbot và Stable Diffusion tranh GPU (máy mục tiêu 6 GB VRAM). Gọi `POST /api/pipeline/step3` .

- 5. Backend `run_step3()` ( `main.py:474-490` ):

- `slug = slugify(story_name)` , `task_key = f"{slug}_step3"` . `_reject_if_auto_running(slug)` → 400 nếu chuỗi tự động đang chạy truyện này. `process_mgr.is_running(task_key)` → 400 nếu bước đó đang chạy (chống double-click / chạy trùng). `pipeline.start_step_3_video(story_name, body.dict())` ; `ValueError` (vd thiếu API key) → 400. Trả `{"status": "success", "task_key":...}` .

- 6. `start_step_3_video` cuối cùng gọi `process_mgr.start_process(...)` ( `pipeline.py:606` ) → `subprocess.Popen` với `stdout=PIPE, stderr=STDOUT, bufsize=1, text=True, encoding="utf-8"` , `env["PYTHONIOENCODING"]="utf-8"` , `creationflags=CREATE_NO_WINDOW` ( `process_manager.py:42-58` ). 7. Frontend nhận `task_key` → `streamLogs("step3", taskKey)` mở SSE.

Endpoint trả về ngay (không chờ render xong) — đây là mô hình fire-and-forget + theo dõi bất đồng bộ. Nếu endpoint chờ Bước 3 (nhiều giờ) thì request HTTP sẽ timeout.

Bước 1 có thêm việc phụ: sau khi start thành công, nếu dùng Gemini thì `GET /api/config` rồi `POST /api/config` để lưu `api_keys.gemini` / `crawler.gemini_offline_base_url` vào cấu hình chung ( `app.js:774-797` ).

### 4.5. Đường ống log: subprocess → queue → generator → SSE → DOM

(a) Subprocess in log. Adapter in ra stdout. Hai kiểu:

- Text thường: `[Pipeline]...` , `[ERROR]...` , `Traceback...` . JSON một dòng có trường `event` , vd `toolCaoTruyen/adapter_cli.py:16-19` :

```
def log_json(event: str, data: dict):
    """Outputs progress log as a JSON string to stdout."""
    print(json.dumps({"event": event, **data}, ensure_ascii=False))
    sys.stdout.flush()
```

`flush()` quan trọng: khi stdout của Python trỏ vào pipe (không phải terminal), nó mặc định block-buffered (dồn vài KB mới ghi một lần); không flush thì log dồn cục, UI không realtime. Lưu ý `bufsize=1` trong `Popen` chỉ quy định bộ đệm phía đọc của orchestrator, không ép được tiến trình con xả bộ đệm; orchestrator cũng không đặt `PYTHONUNBUFFERED` hay `python -u` (grep không thấy) — nên việc realtime phụ thuộc vào việc adapter tự `flush()` (hoặc `print(..., flush=True)` ).

(b) Reader thread đẩy vào queue. Mỗi process có một `threading.Thread(daemon=True)` đọc `for line in` `iter(process.stdout.readline, '')` và `q.put(line)` vào `queue.Queue` riêng của task ( `process_manager.py:66-72` ). Kết thúc: `process.wait()` lấy exit code, chạy callback `on_completed` (vd ghép video) trước, rồi mới ghi `completed_exit_codes[task_key]` và đặt sentinel `None` vào queue ( `process_manager.py:95-119` ). Comment giải thích: "Callback hậu xử lý (vd merge video) phải hoàn tất và ghi log TRƯỚC sentinel; nếu không SSE sẽ báo xong quá sớm." Test `test_callback_logs_arrive_before_terminal_event` bảo đảm thứ tự này.

(c) Generator SSE. `get_logs_generator(task_key)` ( `process_manager.py:275-305` ):

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
    except Exception as e:
        yield f"data: [SYSTEM ERROR] Log generation error: {e}\n\n"
        break
```

Ba kiểu output: dòng log, `[PING]` (queue rỗng quá 1 s), và event kết thúc `[SYSTEM] Process completed (exit_code=N).` . Nhánh đầu ( `q.empty() and completed` ) xử lý trường hợp sentinel đã bị một kết nối cũ tiêu thụ → kết nối mới nhận ngay event kết thúc thay vì PING vô hạn (test `test_reconnect_after_terminal_does_not_ping_forever` ).

(d) Endpoint.

```
@app.get("/api/pipeline/logs/{task_key}")
def stream_logs(task_key: str):
    """Real-time logs streaming using Server-Sent Events (SSE)."""
    return StreamingResponse(
        process_mgr.get_logs_generator(task_key),
        media_type="text/event-stream"
    )
```

( `main.py:509-515` )

(e) Client. `streamLogs(stepName, taskKey)` ( `app.js:1291-1557` ):

- Đóng EventSource cũ nếu có — chỉ một luồng SSE toàn cục `currentLogsSse` . `new EventSource('/api/pipeline/logs/' + encodeURIComponent(taskKey))` .

- `onmessage` : bỏ `[PING]` ; nếu bắt đầu bằng `[SYSTEM] Process completed` → đọc `exit_code` bằng regex `/exit_code=(-?` `\d+)/` , in "Quy trình hoàn thành xong." (xanh) hoặc "kết thúc với mã lỗi N" (đỏ), `source.close()` , trả nút về "Bắt đầu", `loadStories()` để cập nhật trạng thái. Ngược lại thử `JSON.parse` : nếu có `parsed.event` thì `switch` dịch sang câu tiếng Việt + class màu. Có 33 nhánh `case` (đếm bằng grep) được xử lý: cào ( `crawl_start/completed/failed` ), dịch ( `translate_start` , `file_start` , `file_log` , `file_success` , `file_failed` , `file_repair_start/done/warn` , `translate_warn/completed/failed` ), TTS ( `tts_file_start/success/failed/skip` , `tts_batch_completed` ), autosub ( `autosub_init/progress/done/error/warn` , `download_start/progress/done/error` , `ocr_start/roi/progress/done/error` ). Nếu parse được JSON nhưng không có trường `event` (hoặc `event` lạ, rơi vào `default` ) thì in nguyên dòng, không tô màu. Không phải JSON → tô màu theo từ khoá ( `[ERROR]` , `Traceback` , `[`✓`]` , `[WARN]` , `[SYSTEM]` ...) ( `app.js:1475-1486` ). `appendConsoleLog` thêm `<span>` (CSS `.console-box span { display: block; border-left: 2px... }` , `style.css:1263-` `1267` ; console dùng font mono, `white-space: pre-wrap` ), cắt còn 4000 dòng, auto-scroll bằng `consoleBox.scrollTop =` `consoleBox.scrollHeight` .

Đây là giao thức "JSON-lines trên stdout": tiến trình con không cần biết gì về HTTP; orchestrator chỉ chuyển tiếp nguyên dòng; frontend mới là nơi diễn giải. Tách lớp rõ ràng.

### 4.6. Xử lý rớt kết nối SSE — phần tinh tế nhất

`EventSource` tự reconnect, nhưng có ba tình huống cần phân biệt khi `onerror` bắn:

- 1. Task đã xong nhưng client lỡ event cuối. 2. Task vẫn chạy, chỉ là kết nối chập chờn. 3. Task không còn (server restart, bị dừng) và không có terminal event.

`source.onerror` ( `app.js:1491-1556` ) gọi `GET /api/pipeline/status/{task_key}` ( `main.py:518-521` → `process_mgr.get_task_status` , trả `{running, completed, exit_code, has_log_queue}` ):

- **Trạng thái trả về:** `completed: true` · **Hành động:** Đóng SSE, in kết quả theo `exit_code` , trả nút, `loadStories()`
- **Trạng thái trả về:** `running: true` · **Hành động:** Giữ EventSource mở để trình duyệt tự reconnect; in cảnh báo một lần ( `reconnectNoticeShown` )
- **Trạng thái trả về:** Còn lại · **Hành động:** Đóng SSE, báo task không còn chạy, trả nút
- **Trạng thái trả về:** `fetch` lỗi · **Hành động:** Đóng SSE, báo không liên lạc được server

Ba "khoá an toàn" chống race condition:

- `if (currentLogsSse!== source||terminalReceived) return;` — handler của luồng cũ không được đụng UI của luồng mới (người dùng có thể đã chạy task khác trong lúc `fetch` status đang chờ). `statusCheckInFlight` — không bắn nhiều request status song song khi `onerror` bắn liên tục. `terminalReceived` — sau khi đã nhận kết thúc thì bỏ qua mọi message/error.

Một trường hợp đặc biệt: nếu task chưa từng có log queue (vd server vừa restart), generator gửi `data: [SYSTEM] No active log` `queue found for this task.` rồi đóng response ( `process_manager.py:277-283` ). Như đã nói ở mục 2.6, đóng response khiến `EventSource` bắn `error` → rơi vào nhánh "Còn lại" của bảng trên (không running, không completed) → client đóng SSE và trả nút.

### 4.7. Khôi phục sau khi reload trang

Vấn đề: người dùng reload (F5) khi Bước 3 đang render. Trang mới mặc định hiển thị nút "Bắt đầu" → bấm lại sẽ lỗi "already active" mà không có nút Dừng.

Giải pháp `restoreRunningTasks(storySlug)` ( `app.js:187-211` ), gọi trong `selectStory()` :

- Hỏi `GET /api/pipeline/status/{slug}_step{i}` cho i = 1..5. `toggleFormButtons` theo `running` thật. Bám SSE vào bước đang chạy sau cùng (vì chỉ có một luồng SSE toàn cục) và chỉ khi chưa có EventSource mở.

Vì trạng thái task nằm ở backend ( `ProcessManager` giữ `active_processes` , `log_queues` , `completed_exit_codes` ) nên reload trang không làm mất tiến trình. Đây là lợi ích kiến trúc: frontend stateless, backend giữ sự thật.

### 4.8. Dừng tiến trình

Bước 1-3: `stopPipelineTask(stepName, stepNum)` → `POST /api/pipeline/stop?story_name=...&step=N` ( `app.js:1199-` `1215` ) → `stop_pipeline()` ( `main.py:492-507` ) → `process_mgr.stop_process(task_key)` và ghi `meta["status"] =` `"CANCELLED"` . Bước autosub: `stopTaskByKey("step4")` → `POST /api/pipeline/stop-task?task_key=...` ( `main.py:730-751` ). `stop_process` ( `process_manager.py:151-185` ) diệt cả cây tiến trình bằng `taskkill /PID<pid> /T /F` trên Windows ( `_kill_process_tree` ), vì nếu chỉ kill tiến trình con thì tiến trình cháu (ffmpeg, SD...) còn giữ đầu ghi pipe → reader thread kẹt `readline()` mãi. Chờ reader dọn tối đa 8 s; quá hạn thì tự giải phóng và đẩy `[SYSTEM]Đã buộc dừng tiến trình theo` `yêu cầu.` + sentinel. Frontend sau đó `waitTaskStopped()` poll 400 ms × 25 lần để trả nút. Bước "Ghép Video" (task `step5` ) chạy bằng thread ( `register_manual_task` ), không phải subprocess → nút Dừng chỉ in cảnh báo "chạy bằng thread không thể dừng cưỡng bức" ( `app.js:1161-1163` ).

### 4.9. Chuỗi Chạy tự động 1→4

Nút header `#btnAutoRun` → `startAutoRun()` ( `app.js:418-442` ): `confirm()` , gom `step1: buildStep1Payload()` , `step2:` `buildStep2Payload()` , `step3: buildStep3Payload()` → `POST /api/pipeline/auto-run` → `start_auto_run()` ( `main.py:531-` `544` ) → `auto_run_mgr.start(...)` . Chuỗi chạy hoàn toàn ở backend trong thread daemon: `_run_chain` lần lượt start step 1 → 2 → 3 → 5, mỗi bước `_wait_step` poll `get_task_status` mỗi `poll_interval = 1.0` s tới khi `completed` ( `auto_run.py:120-165` ). Thất bại hoặc hủy → dừng chuỗi, ghi `error` . Frontend chỉ theo dõi: `pollAutoRun()` mỗi 2 s gọi `GET /api/pipeline/auto-run/{story}` → nhận `{running, current_step,` `total_steps, step_label, error, finished}` ; khi `current_step` đổi (hoặc SSE rớt) thì `followAutoRunStep()` tự bấm sang tab của bước đó ( `navBtn.click()` ) và sau 800 ms mở SSE cho `{slug}_step{internal}` (chờ backend kịp tạo log queue). Payload dùng chung builder với nút chạy lẻ → đảm bảo cấu hình như nhau (comment `app.js:236-238` ). Khác biệt nhỏ so với chạy lẻ: chuỗi tự động không đi qua `postPipelineAction` , nên không gọi `POST /api/chat/unload` trước mỗi bước; bước Ghép Video trong chuỗi gọi `start_step_5_merge(story_name, None)` (không truyền danh sách file chọn tay — `auto_run.py:143` ).

### 4.10. Lưu cấu hình — hai tầng lưu trữ

- **UI settings (snapshot form):** Nút "Lưu cấu hình" trên header ( `#btnSaveSettings` ) · **Global config (mặc định dùng chung):** "Lưu cấu hình" trong tab Cấu Hình Chung ( `#formSettings` submit)
- **UI settings (snapshot form):** Endpoint `GET/POST /api/ui-settings` · **Global config (mặc định dùng chung):** `GET/POST /api/config`
- **UI settings (snapshot form):** Backend `load_ui_settings()/save_ui_settings()` · **Global config (mặc định dùng chung):** `load_global_config()/save_global_config()`
- **UI settings (snapshot form):** File `configs/ui_settings.json` ( `config.py:6` ) · **Global config (mặc định dùng chung):** `configs/global_config.json` ( `config.py:5` )
- **UI settings (snapshot form):** Nội dung `{fields: {id: {v}|{c}}, radios: {name:` `value}, story}` · **Global config (mặc định dùng chung):** Cây `api_keys` , `crawler` , `translate` , `tts` , `video` , `autosub` , `chatbot` , `storage_dir` ...
- **UI settings (snapshot form):** Ai đọc Chỉ frontend (khôi phục form) · **Global config (mặc định dùng chung):** Backend + pipeline (vd `start_step_3_video` gọi `mediacomposer_config.apply_sd_params(cfg["video"])` trước khi spawn subprocess, ghi các khoá `sd_*` xuống mục `[storytelling]` trong `AIVoice/apps/MediaComposer/config.toml` — `pipeline.py:505-511` , `mediacomposer_config.py:79` )

`collectAllSettings()` ( `app.js:317-329` ) duyệt mọi `input/select/textarea` có `id` trong `.tab-panel` (trừ `#tab-settings` ), lưu checkbox bằng `{c: checked}` , còn lại `{v: value}` ; radio lưu theo `name` . `applyAllSettings()` ( `app.js:331-367` ) áp ngược, chèn tạm `<option>` nếu dropdown chưa có (vì danh sách model Ollama nạp bất đồng bộ) và `dispatchEvent("change")` .

Tại sao lưu trên server (file JSON) chứ không `localStorage` ? Vì app là desktop: WebView2 có thể bị reset profile, và file `configs/ui_settings.json` dễ sao lưu/sửa tay. Có 3 test ở `tests/test_ui_settings.py` (roundtrip, thiếu file → `{}` , file hỏng → `{}` ). Riêng chatbot dùng `localStorage` cho `chatbot_session_id` ( `chat.js:6-10` ) — thông tin per-trình-duyệt, mất cũng không sao.

Mirror cấu hình (data-driven UI). Tab Cấu Hình Chung có 84 phần tử `data-cfg` (đếm bằng grep). Thay vì chép tay mọi control, HTML đặt placeholder `<span class="cfg-clone" data-clone="s1Engine" data-cfg="translate.default_engine">` và

`buildConfigMirror()` ( `app.js:1682-1695` ) `cloneNode(true)` control gốc (giữ nguyên mọi `<option>` ), đổi id thành `cfg_<id>` , gắn `data-cfg` (đường dẫn trong JSON) và `data-seed` (id control gốc để gieo mặc định). Khi lưu, `cfgSetByPath(payload,` `"translate.default_engine", value)` ghi vào đúng nhánh cây JSON ( `app.js:1647-1655` ); `cfgReadField` ép kiểu số cho `number/range/data-num` để Python không nhận `"22"` thay vì `22` . Backend chấp nhận khoá mới nhờ `GlobalConfigSchema` có `model_config = ConfigDict(extra="allow")` ( `main.py:70-83` ). Đây là kỹ thuật UI khai báo bằng dữ liệu: thêm một tham số mới chỉ cần một dòng HTML.

`buildSdMirror()` ( `app.js:1784-1887` ) làm chiều ngược: nhân bản 9 control tham số sinh ảnh ( `cfgSdAspect` , `cfgSdSteps` , `cfgSdGuidance` , `cfgSdIpScale` , `cfgSdFdSteps` , `cfgSdFdStrength` , `cfgSdStudioSteps` , `cfgSdStudioGuidance` , `cfgSdFps` ) xuống `<details>` của Bước 3, đồng bộ hai chiều bằng hàm `push(from, to)` chống vòng lặp bằng cách so giá trị (bằng nhau thì dừng). Bản sao bị gỡ `id` và `data-cfg` để không bị lưu hai lần. Kèm nút "Lưu tham số sinh ảnh" gọi `formSettings.requestSubmit()` . Khoảng giá trị thanh trượt lấy từ HTML: steps 1-50, guidance 0-20 bước 0.5, IP-Adapter scale 0-1 bước 0.05, Face Detailer steps 1-40, strength 0-1 bước 0.05, studio steps 0-40, studio guidance 0-20 bước 0.5, FPS 1-60 (ô number) ( `index.html:1129-1176` ). Giá trị mặc định phía backend nằm trong `SD_TUNING_DEFAULTS` ( `orchestrator/config.py:14-27` ): `sd_steps=8` , `sd_guidance=5.0` , ảnh sinh `768×432` , xuất `1920×1080` , `sd_video_fps=24` , `sd_face_detailer_steps=14` , `sd_face_detailer_strength=0.45` , `sd_ip_adapter_scale=0.6` , `sd_studio_render_steps=0` , `sd_studio_render_guidance=0.0` (ý nghĩa từng tham số: xem chương sinh ảnh). Nếu `global_config.json` đã có giá trị khác thì giá trị trong file thắng.

### 4.11. Tab Tự Động Tạo Phụ Đề — REST đồng bộ + tương tác canvas

"Tải & Xem trước" → `POST /api/autosub/prepare` ( `main.py:615-683` ): chạy đồng bộ `subprocess.run([python,` `adapter_autosub_cli.py, "--prepare-only",...], timeout=900)` (tối đa 15 phút; quá hạn trả 504), đọc stdout tìm dòng JSON `{"event": "prepare_done"}` , đọc ảnh preview và trả về Base64 data URL `data:image/jpeg;base64,...` cùng `width` , `height` , `duration` . Frontend gán `img.src = data.preview_b64` và gọi `setupRoiSelector()` ( `app.js:1934-1967` ): nghe `mousedown` trên ảnh, `mousemove` / `mouseup` trên `window` (để kéo ra ngoài ảnh vẫn bắt được), vẽ khung bằng một `div` tuyệt đối. Khi thả chuột, quy đổi toạ độ hiển thị về pixel gốc: `kx = natW / r.width` , `ky = natH / r.height` , `x_goc = round(x_hienthi * kx)` . Bỏ qua khung < 5 px. Toạ độ gửi kèm `crop_x/y/w/h` cho OCR. Submit → `POST /api/pipeline/step4` ; nếu không có truyện thì task key là `autosub_{uuid.hex[:8]}_step4` ( `main.py:590-` `596` ).

### 4.12. Chatbot widget (chat.js)

`initDOM()` sinh toàn bộ HTML widget vào `#chatWidget` , polling `checkHealth()` 10 s → badge `ready` (xanh) / `busy` (vàng, nhấp nháy) / `offline` (xám) ( `chat.css:75-77` ). Mở panel → `POST /api/chat/prewarm` (nạp sẵn model với `keep_alive: "5m"` , bỏ qua nếu GPU `heavy` ). Dropdown model: `GET /api/chat/models` (theo VRAM, `tier` 6gb/8gb) và `POST /api/chat/model` (nhả model cũ khỏi VRAM trước khi đổi). Gửi câu hỏi: `POST /api/chat` với `{session_id, message, story_name, active_tab, mode, force}` . Các nhánh phản hồi của server ( `main.py:814-1042` ):

- **Tình huống:** Chatbot tắt · **Status / dạng:** 503 · **Client xử lý:** In lỗi
- **Tình huống:** Đang trả lời câu trước ( `single_chat_lock` ) · **Status / dạng:** 429 · **Client xử lý:** In lỗi
- **Tình huống:** GPU `heavy` (có step3/step4/chuỗi), `block_when_busy` bật (mặc định `True` ), không `force` và `mode` khác `"lookup"` · **Status / dạng:** 409 + `busy_tasks` + `lookup_answer` · **Client xử lý:** `show409Modal` : Tra cứu (0 VRAM) / Dừng pipeline để hỏi / Để sau
- **Tình huống:** Lời chào · **Status / dạng:** NDJSON `delta` + `done` · **Client xử lý:** Hiển thị ngay, không gọi LLM
- **Tình huống:** Lệnh agent `run_step` / `select_story` · **Status / dạng:** NDJSON `agent_action` · **Client xử lý:** Thẻ xác nhận "Chấp nhận chạy / Huỷ"
- **Tình huống:** Truy vấn `list_stories` / `story_report` / `system_status` · **Status / dạng:** NDJSON `agent_result` · **Client xử lý:** Thẻ dữ liệu
- **Tình huống:** `mode="lookup"` (hoặc GPU `heavy` mà không `force` ) · **Status / dạng:** NDJSON `delta` + `done` có `mode: "lookup"` , `sources` · **Client xử lý:** Hiển thị câu tra cứu, không gọi LLM
- **Tình huống:** Điểm RAG < `kb_min_score` (mặc định 0.75) và câu hỏi không chứa chữ "truyện"/"story" · **Status / dạng:** NDJSON có `gate_refusal` · **Client xử lý:** Câu từ chối + gợi ý tài liệu
- **Tình huống:** Câu hỏi lặp, đủ điều kiện cache · **Status / dạng:** NDJSON `delta` + `done` có `from_cache` · **Client xử lý:** Hiển thị ngay
- **Tình huống:** Bình thường · **Status / dạng:** NDJSON nhiều `delta` rồi `done` (có `truncated` ) · **Client xử lý:** Ghép dần, render markdown an toàn

Mức GPU tính ở `ChatManager.get_gpu_weight()` ( `chatbot.py:498-523` ): task chứa `step3` / `step4` hoặc chuỗi tự động → `heavy` ; `step1` / `step2` → `medium` .

Thẻ xác nhận gọi các hàm của `app.js` qua `window.selectStory` , `window.postPipelineAction` , `window.buildStep1Payload` . Hoạt động được vì trong script cổ điển (không phải module), `function` khai báo ở top-level trở thành thuộc tính của `window` .

### 4.13. Bảng ánh xạ đầy đủ: hành động UI → endpoint → hàm backend

- **Hành động trên UI:** Mở app · **Hàm JS:** `fetchGpuInfo` · **Endpoint:** `GET /api/system/gpu-info` · **Hàm backend chính:** `get_gpu_info` (nvidia-smi, fallback WMI `_wmi_gpu` )
- **Hành động trên UI:** Mở app / sau khi chạy xong · **Hàm JS:** `loadStories` · **Endpoint:** `GET /api/stories` · **Hàm backend chính:** `storage_mgr.list_stories`
- **Hành động trên UI:** Mở app · **Hàm JS:** `loadGlobalConfig` · **Endpoint:** `GET /api/config` · **Hàm backend chính:** `load_global_config`
- **Hành động trên UI:** Mở app · **Hàm JS:** `loadAndApplySettings` · **Endpoint:** `GET /api/ui-settings` · **Hàm backend chính:** `load_ui_settings`
- **Hành động trên UI:** Mở app / đổi truyện · **Hàm JS:** `pollAutoRun` · **Endpoint:** `GET /api/pipeline/auto-` `run/{story}` · **Hàm backend chính:** `auto_run_mgr.status`
- **Hành động trên UI:** Tạo truyện mới (modal) · **Hàm JS:** handler `btnConfirmStory` · **Endpoint:** `POST /api/stories` · **Hàm backend chính:** `create_story` → `storage_mgr.init_story_workspace` (409 nếu trùng)
- **Hành động trên UI:** Chọn truyện · **Hàm JS:** `selectStory` · **Endpoint:** `GET /api/stories/{name}` · **Hàm backend chính:** `get_story_details` (+ `story_dir` , `raw_chapters_count` )
- **Hành động trên UI:** Chọn truyện · **Hàm JS:** `restoreRunningTasks` · **Endpoint:** `GET /api/pipeline/status/{key}` ×5 · **Hàm backend chính:** `process_mgr.get_task_status`
- **Hành động trên UI:** Bắt đầu Bước 1/2/3 · **Hàm JS:** `postPipelineAction` · **Endpoint:** `POST /api/chat/unload` rồi `POST` `/api/pipeline/step{1,2,3}` · **Hàm backend chính:** `unload_ollama` ; `run_step1/2/3` → `pipeline.start_step_1_crawl_translate /` `start_step_2_tts / start_step_3_video`
- **Hành động trên UI:** Xem log · **Hàm JS:** `streamLogs` · **Endpoint:** `GET /api/pipeline/logs/{key}` (SSE) · **Hàm backend chính:** `stream_logs` → `process_mgr.get_logs_generator`
- **Hành động trên UI:** Dừng Bước 1/2/3 · **Hàm JS:** `stopPipelineTask` · **Endpoint:** `POST /api/pipeline/stop?` `story_name&step` · **Hàm backend chính:** `stop_pipeline` → `process_mgr.stop_process`
- **Hành động trên UI:** Mở thư mục đầu ra · **Hàm JS:** `openStepOutputFolder` · **Endpoint:** `POST /api/stories/{name}/open-` `folder?step=` · **Hàm backend chính:** `_step_output_dir` + `_reveal_in_file_manager` ( `os.startfile` )
- **Hành động trên UI:** Chọn engine Ollama · **Hàm JS:** `loadOllamaModels` · **Endpoint:** `GET /api/ollama/models` · **Hàm backend chính:** `get_ollama_models` (gọi `localhost:11434/api/tags` , timeout 3 s)
- **Hành động trên UI:** Xoá cache giọng · **Hàm JS:** handler `btnClearCache` · **Endpoint:** `POST /api/system/clear-cache` · **Hàm backend chính:** `clear_semantic_cache` (xoá `AIVoice/storage/cache` )
- **Hành động trên UI:** Autosub: Tải & Xem trước · **Hàm JS:** handler `btnS4Prepare` · **Endpoint:** `POST /api/autosub/prepare` · **Hàm backend chính:** `autosub_prepare` (subprocess.run, timeout 900 s)
- **Hành động trên UI:** Autosub: Bắt đầu · **Hàm JS:** submit `formStep4` · **Endpoint:** `POST /api/pipeline/step4` · **Hàm backend chính:** `run_step4` → `pipeline.start_step_4_autosub`
- **Hành động trên UI:** Autosub: Dừng · **Hàm JS:** `stopTaskByKey` · **Endpoint:** `POST /api/pipeline/stop-task?` `task_key` · **Hàm backend chính:** `stop_task`
- **Hành động trên UI:** Ghép video: Tải danh sách · **Hàm JS:** `loadStoryVideos` · **Endpoint:** `GET /api/stories/{name}/videos` · **Hàm backend chính:** `get_story_videos` (glob `video/*.mp4` , `is_merged` nếu tên bắt đầu `TongHop_` )
- **Hành động trên UI:** Ghép video: Bắt đầu · **Hàm JS:** submit `formStep5` · **Endpoint:** `POST /api/pipeline/step5` · **Hàm backend chính:** `run_step5` → `pipeline.start_step_5_merge`
- **Hành động trên UI:** Lưu cấu hình (header) · **Hàm JS:** `saveAllSettings` · **Endpoint:** `POST /api/ui-settings` · **Hàm backend chính:** `save_ui_settings`
- **Hành động trên UI:** Lưu Cấu Hình Chung · **Hàm JS:** submit `formSettings` · **Endpoint:** `POST /api/config` (+ `POST` `/api/ui-settings` ) · **Hàm backend chính:** `update_config` → `save_global_config`
- **Hành động trên UI:** Chạy tự động 1→4 · **Hàm JS:** `startAutoRun` · **Endpoint:** `POST /api/pipeline/auto-run` · **Hàm backend chính:** `start_auto_run` → `auto_run_mgr.start`
- **Hành động trên UI:** Dừng chuỗi · **Hàm JS:** `stopAutoRun` · **Endpoint:** `POST /api/pipeline/auto-run/stop?` `story_name` · **Hàm backend chính:** `stop_auto_run` → `auto_run_mgr.stop`
- **Hành động trên UI:** Mở tab Thống kê · **Hàm JS:** `loadStats` · **Endpoint:** `GET /api/stats` · **Hàm backend chính:** `get_stats` → `db.stats` , `db.list_stories` (SQLite)
- **Hành động trên UI:** Xem trước / Dọn dẹp · **Hàm JS:** `previewCleanup` / `doCleanup` · **Endpoint:** `POST /api/maintenance/cleanup-` `tasks?dry_run=true/false` · **Hàm backend chính:** `storage_mgr.cleanup_tasks`
- **Hành động trên UI:** Đồng bộ lại CSDL · **Hàm JS:** `rebuildStatsDb` · **Endpoint:** `POST /api/maintenance/rebuild-db` · **Hàm backend chính:** `storage_mgr.rebuild_db`
- **Hành động trên UI:** Chat: badge · **Hàm JS:** `checkHealth` (10 s) · **Endpoint:** `GET /api/chat/health` · **Hàm backend chính:** `get_chat_health` (Ollama `/api/ps` , `/api/tags` )
- **Hành động trên UI:** Chat: mở panel · **Hàm JS:** `prewarmModel` · **Endpoint:** `POST /api/chat/prewarm` · **Hàm backend chính:** `prewarm_chat_model`
- **Hành động trên UI:** Chat: danh sách/đổi model · **Hàm JS:** `loadModels` / `onModelChange` · **Endpoint:** `GET /api/chat/models` , `POST` `/api/chat/model` · **Hàm backend chính:** `list_chat_models` , `set_chat_model`
- **Hành động trên UI:** Chat: gửi · **Hàm JS:** `sendMessage` · **Endpoint:** `POST /api/chat` (NDJSON) · **Hàm backend chính:** `post_chat` → `ChatManager` + `chat_stream_ollama`
- **Hành động trên UI:** Chat: cuộc trò chuyện mới · **Hàm JS:** `clearSession` · **Endpoint:** `DELETE /api/chat/sessions/{id}` · **Hàm backend chính:** `delete_chat_session_endpoint`

Lưu ý: `postPipelineAction` được dùng cho cả Bước 4 (autosub, `step4` ) và Ghép Video ( `step5` ), nên hai nút đó cũng gọi `POST` `/api/chat/unload` trước ( `app.js:1113` , `app.js:1152` , `app.js:1174-1176` ).

Có 3 endpoint backend không được WebUI gọi (grep `webui/` không thấy): `GET/POST /api/models/preflight` , `GET` `/api/system/busy` , `POST /api/agent/query` . Chúng phục vụ kiểm tra/tích hợp khác — nếu hội đồng hỏi, trả lời đúng như vậy.

## 5. Sơ đồ luồng

### 5.1. Kiến trúc tổng thể của tầng giao diện

### 5.2. Tuần tự: bấm "Bắt đầu Bước 3" tới lúc xong

### 5.3. Quyết định khi SSE báo lỗi

### 5.4. Chuỗi tự động: backend chạy, frontend theo dõi

### 5.5. Thứ tự ưu tiên cấu hình khi mở app

## 6. Hạn chế & hướng phát triển

Các hạn chế dưới đây đọc ra từ code, nên tự nêu trước khi hội đồng phát hiện:

1. Một luồng SSE toàn cục. `currentLogsSse` chỉ có một → không xem log hai bước song song; khi reload chỉ bám bước chạy sau cùng ( `app.js:205-210` ). Hướng: mỗi bước một EventSource, hoặc một SSE ghép kênh dùng trường `event:` . 2. Log không phát lại (no replay). Queue là `queue.Queue` — lấy ra là mất. Kết nối SSE sau khi reload chỉ thấy log từ thời điểm đó; log cũ không còn. Không dùng `id:` / `Last-Event-ID` . Hệ quả thêm: nếu hai tab trình duyệt cùng mở SSE của một task, hai kết nối chia nhau các dòng (competing consumers). Hướng: ring buffer + `id:` để client xin lại từ `Last-Event-ID` , hoặc ghi log ra file và cho tải phần đầu. 3. Trạng thái nằm trong RAM. `ProcessManager` , `AutoRunManager` giữ state trong bộ nhớ; restart orchestrator là mất (comment `auto_run.py:5-6` thừa nhận "chấp nhận ở v1"). 4. Mỗi kết nối SSE giữ một thread (generator đồng bộ + `q.get(timeout=1.0)` ). Ổn cho một người dùng local; nhiều người dùng cần chuyển sang `asyncio.Queue` + async generator. 5. Bước Ghép Video không dừng được vì chạy bằng thread ( `app.js:1161-1163` ). 6. `app.js` quá dài (2096 dòng), nhiều handler ẩn/hiện lặp lại; danh sách giọng TTS và preset Bước 2 hardcode trong JS ( `app.js:606-699` , comment ghi "Hardcode a few presets for demo since backend preset endpoint isn't fully set up"). Hướng: tách ES modules, lấy danh sách giọng từ backend.

7. Một số điểm lệch nhỏ trong `chat.js` (đọc code thấy, nên biết để trả lời thật):

- Nút "Dừng pipeline để hỏi đầy đủ" gọi `window.stopPipelineTask(detailData.busy_tasks[0])` với một đối số là task key, trong khi `stopPipelineTask(stepName, stepNum)` của `app.js` cần số bước → URL gửi lên là `...&step=undefined` , mà `stop_pipeline(story_name: str, step: int)` ( `main.py:493` ) khai báo `step` là `int` → FastAPI sẽ trả 422, tiến trình không bị dừng; ngoài ra `busy_tasks[0]` có thể là `"auto_chain"` ( `chatbot.py:505` ) chứ không phải task key. Đây là suy luận từ code, chưa chạy thử để xác nhận. `getActiveTab()` ( `chat.js:43-54` ) dò chữ số trong `data-tab` ; tab `settings` / `stats` không có số và không chứa chữ `config` → rơi về `"step1"` (nhánh `"config"` thực tế không bao giờ khớp). Thẻ xác nhận `run_step` chỉ thực thi cho `args.n===1` .

8. Đánh số tab lệch nội bộ (Bước 4 hiển thị = `step5` ) gây khó hiểu khi đọc code; đã được ghi chú ở `auto_run.py` và `INTERNAL_STEP_BY_DISPLAY` . 9. Không xác thực (authentication). API mở ở `127.0.0.1` — chấp nhận được với app local (không lắng nghe ra mạng ngoài), nhưng nếu đưa lên server phải thêm auth. 10. `/api/autosub/prepare` chặn một worker tới 15 phút (subprocess.run đồng bộ). Hướng: chuyển thành task nền + SSE như các bước khác.

Hướng phát triển tổng quát: thanh tiến độ phần trăm (hiện chỉ có log chữ, trừ vài event có `percent` ), hiển thị ảnh cảnh vừa sinh ngay trong UI, SSE có replay, tách frontend thành module.

## Câu hỏi hội đồng có thể hỏi

### 1. Vì sao không dùng React/Vue?

Giao diện chủ yếu là form tham số + console log cho một người dùng chạy local; nút thắt là GPU chứ không phải UI. JS thuần không cần Node/bundler, installer chỉ cần Python, sửa là chạy. Đổi lại `app.js` dài 2096 dòng và phải tự đồng bộ DOM (vd `buildConfigMirror` , `buildSdMirror` ); nếu mở rộng sẽ tách module hoặc dùng thư viện nhẹ.

### 2. SSE là gì, khác WebSocket thế nào? Vì sao chọn SSE?

SSE là một HTTP response `text/event-stream` không kết thúc, server ghi dần các khối `data:...\n\n` ; một chiều, text, trình duyệt tự reconnect. WebSocket là kênh hai chiều qua Upgrade, giao thức frame riêng. Log chỉ đi server→client, lệnh dừng đã có REST riêng, nên SSE đủ và đơn giản: endpoint chỉ là `StreamingResponse(get_logs_generator(key), media_type="text/event-stream")` ( `main.py:509-515` ).

### 3. Log từ tiến trình con lên màn hình đi qua những khâu nào?

Adapter `print` (JSON một dòng + `flush` ) → pipe stdout → reader thread `readline()` → `queue.Queue` riêng của task → `get_logs_generator` lấy với timeout 1 s, `yield "data:` `...\n\n"` → StreamingResponse → `EventSource.onmessage` → parse JSON `event` thành câu tiếng Việt + màu → `appendConsoleLog` thêm `<span>` , giữ tối đa 4000 dòng.

### 4. Mất kết nối giữa chừng thì sao?

`EventSource` tự reconnect. `onerror` hỏi `GET /api/pipeline/status/{task_key}` : xong rồi thì đóng và báo kết quả theo `exit_code` ; còn chạy thì giữ kết nối cho trình duyệt tự nối lại; không còn thì đóng và trả nút. Có các cờ `terminalReceived` , `statusCheckInFlight` và so sánh `currentLogsSse!== source` để handler cũ không phá UI mới.

### 5. Reload trang khi Bước 3 đang chạy thì có mất tiến trình không?

Không. Tiến trình và trạng thái nằm ở backend ( `ProcessManager` ). Khi chọn lại truyện, `restoreRunningTasks` hỏi status 5 bước, bật lại nút Dừng và nối lại SSE. Nhưng log trước lúc reload không phát lại được vì queue đã bị tiêu thụ.

### 6. `[PING]` để làm gì?

Heartbeat mỗi khi queue rỗng quá 1 s ( `q.get(timeout=1.0)` ném `queue.Empty` ): giữ kết nối sống khi subprocess im lặng lâu, cho vòng lặp cơ hội kiểm tra task đã `completed` chưa, và bảo đảm khi client ngắt thì thread chạy generator không kẹt vô hạn trong `q.get()` . Dự án dùng message thật `data: [PING]` thay cho comment `:` của chuẩn SSE, nên client phải tự bỏ qua dòng `[PING]` .

### 7. Làm sao biết tiến trình kết thúc thành công hay lỗi?

Reader thread `process.wait()` lấy exit code, chạy callback hậu xử lý, ghi `completed_exit_codes` , rồi đặt sentinel `None` . Generator gặp sentinel phát `[SYSTEM] Process completed` `(exit_code=N).` ; frontend dùng regex `/exit_code=(-?\d+)/` — 0 là thành công, khác 0 là lỗi. Callback trả `False` có thể đổi exit 0 thành 1.

### 8. Chống người dùng bấm Bắt đầu hai lần thế nào?

Hai tầng: frontend ẩn nút Bắt đầu, hiện nút Dừng ( `toggleFormButtons` ); backend kiểm `process_mgr.is_running(task_key)` → 400 "already active", và `_reject_if_auto_running` → 400 nếu chuỗi tự động đang chạy. `is_running` được bảo vệ bằng `threading.Lock` .

### 9. Chatbot stream bằng gì, sao không dùng SSE?

Dùng `fetch` POST + `ReadableStream` đọc NDJSON ( `application/x-` `ndjson` ). `EventSource` chỉ hỗ trợ GET không body, mà chatbot cần gửi câu hỏi, session, tab đang mở; ngoài ra cần hủy giữa chừng bằng `AbortController` . Client tự tách dòng bằng buffer và xả nốt dòng cuối khi `done` .

### 10. Event loop là gì, liên quan gì tới app?

JS chạy một luồng; I/O (fetch, SSE, timer) do trình duyệt làm nền và trả callback vào hàng đợi. `await fetch` nhường luồng nên UI không đơ. Mỗi tin SSE là một task; log quá nhiều sẽ làm DOM phình, nên code giới hạn 4000 dòng. Polling dùng `setTimeout` chứ không dùng vòng lặp chặn.

### 11. Cấu hình được lưu ở đâu, có mấy loại?

Hai loại: `configs/ui_settings.json` qua `/api/ui-settings` — snapshot mọi ô form + truyện đang chọn, chỉ frontend dùng; và `configs/global_config.json` qua `/api/config` — mặc định dùng chung mà pipeline đọc (vd tham số sinh ảnh). Khi mở app áp theo thứ tự HTML → global config → ui_settings, cái sau thắng.

### 12. "Chạy tự động 1→4" chạy ở frontend hay backend?

Backend: `AutoRunManager` chạy thread daemon, lần lượt step1→2→3→5, mỗi bước poll trạng thái 1 s. Frontend chỉ poll `GET /api/pipeline/auto-run/{story}` mỗi 2 s, tự chuyển tab và mở SSE của bước hiện tại. Nhờ vậy đóng/reload trang không làm dừng chuỗi.

### 13. Vì sao tab "Bước 4: Ghép Video" lại là `step5` trong code?

Autosub ( `step4` ) được làm như công cụ rời, không thuộc chuỗi chính; ghép video giữ task nội bộ `step5` . Ánh xạ nằm ở `INTERNAL_STEP_BY_DISPLAY` ( `app.js:402` ) và `DISPLAY_NO` ( `auto_run.py:20` ).

### 14. Giao diện có an toàn trước XSS không?

Phần chính có: log hiển thị bằng `textContent` (không parse HTML); chatbot `escapeHTML` trước khi render markdown; bảng thống kê escape bằng `_statEsc` . Còn vài chỗ chưa escape (tên file video ở `loadStoryVideos` , slug/status trong thẻ chatbot) — rủi ro thấp vì dữ liệu do máy người dùng tự sinh, nhưng em ghi nhận là điểm cần sửa. Server chỉ lắng nghe `127.0.0.1` ( `desktop.py:18` ), CORS giới hạn hai origin cổng 8100. Chưa có authentication vì là app local.

### 15. Vẽ vùng OCR trên ảnh preview hoạt động thế nào?

`/api/autosub/prepare` trả ảnh Base64 + kích thước gốc. `setupRoiSelector` bắt `mousedown/mousemove/mouseup` , vẽ khung bằng `div` , khi thả quy đổi toạ độ hiển thị sang pixel gốc bằng tỉ lệ `natW / r.width` , `natH / r.height` , bỏ khung nhỏ hơn 5 px, rồi gửi `crop_x/y/w/h` cho bước OCR.

### 16. Server kết thúc stream SSE thì trình duyệt có tự hiểu là "xong" không?

Không. Với `EventSource` , response bị đóng được coi như rớt mạng và trình duyệt sẽ tự kết nối lại. Vì vậy server gửi một dòng kết thúc quy ước `[SYSTEM] Process` `completed (exit_code=N).` và client gọi `source.close()` ngay khi nhận ( `app.js:1312-1326` ). Nếu client lỡ dòng đó mà reconnect, generator thấy `q.empty()` và task đã `completed` nên gửi lại dòng kết thúc thay vì PING mãi.

### 17. Trong `requirements.txt` có `sse-starlette` , sao code lại dùng `StreamingResponse` ?

Code không import `sse-` `starlette` ở đâu cả; SSE được tự hiện thực: `_sse_data()` tự thêm tiền tố `data:` cho từng dòng và dòng trống kết thúc, endpoint trả `StreamingResponse(..., media_type="text/event-stream")` . Dự án chỉ cần trường `data:` nên tự viết là đủ; dependency đó là thừa và có thể gỡ.

## Tóm tắt 1 phút

"Giao diện của em là một trang web một trang viết bằng HTML, CSS, JavaScript thuần, được nhúng vào cửa sổ ứng dụng Windows qua WebView2. Chính server FastAPI ở cổng 8100 phục vụ trang này, nên giao diện và API cùng origin. Giao diện có bảy tab: Nguồn & Dịch, Sinh Giọng, Dựng Hoạt Hình, Ghép Video, Tự động tạo phụ đề, Cấu hình chung và Thống kê; chuyển tab chỉ là ẩn hiện section bằng CSS.

Khi bấm Bắt đầu, JavaScript gom tham số thành JSON và gọi REST, ví dụ `POST /api/pipeline/step3` . Backend kiểm tra không chạy trùng, khởi động một subprocess Python và trả về ngay một `task_key` . Sau đó trình duyệt mở một kết nối Server-Sent Events tới `/api/pipeline/logs/{task_key}` . Mỗi dòng stdout của tiến trình con được một thread đọc vào hàng đợi, rồi đẩy lên trình duyệt dưới dạng `data:...` . Frontend dịch các event JSON sang câu tiếng Việt có màu. Khi xong, server gửi dòng `Process` `completed` kèm exit code.

Em chọn SSE vì log chỉ đi một chiều, SSE chỉ là HTTP thường và tự kết nối lại; còn chatbot cần gửi câu hỏi bằng POST nên dùng fetch stream NDJSON. Em không dùng React vì ứng dụng chủ yếu là form và log, chạy local, không cần thêm Node và bước build. Trạng thái tiến trình nằm ở backend nên reload trang không mất tiến trình."
