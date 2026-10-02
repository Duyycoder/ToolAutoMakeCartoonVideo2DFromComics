# Chương 03. Bước 1a — Cào truyện (Web crawler, HTML parsing, tìm kiếm)

- Mục tiêu chương: hiểu từ gốc một web crawler hoạt động thế nào (HTTP, HTML, DOM, CSS selector, encoding, rate limiting, chống bot), sau đó đi vào đúng code của `toolCaoTruyen/` và cách `orchestrator/` gọi nó. Cuối chương có bộ câu hỏi hội đồng và bản tóm tắt 1 phút.

- Quy ước trích dẫn: `đường/dẫn/file.py:DÒNG` là vị trí thật trong repo (commit hiện tại trên nhánh `main` ). Mọi con số (timeout, số lần retry, delay...) đều đọc từ code, không ước lượng.

## 1. Vai trò trong hệ thống

### 1.1. Vị trí trong pipeline

Toàn bộ hệ thống có 5 bước: (1) Nguồn truyện & dịch → (2) Sinh giọng (TTS) → (3)/(4) Phân cảnh, sinh ảnh, dựng video → (5) Ghép video. Chương này nói về Bước 1a: lấy văn bản truyện về máy. Bước 1b (dịch Trung → Việt) là chương sau.

Bước 1 có 4 nguồn đầu vào, chọn bằng dropdown `s1Source` ở `webui/index.html:130-136` :

- **Giá trị `source_site`:** `local` (mặc định, `selected` ) · **Ý nghĩa:** Thư mục cục bộ chứa `.md` / `.txt` · **Ai xử lý:** `orchestrator/pipeline.py:278-331` (thread copy + chuẩn hoá tên)
- **Giá trị `source_site`:** `ai_write` · **Ý nghĩa:** LLM cục bộ tự sáng tác truyện tiếng Việt · **Ai xử lý:** `orchestrator/pipeline.py:143-145` → `start_ai_write` / `orchestrator/story_writer.py`
- **Giá trị `source_site`:** `69shuba` · **Ý nghĩa:** Cào web truyện chữ tiếng Trung 69shu · **Ai xử lý:** subprocess `toolCaoTruyen/adapter_cli.py crawl`
- **Giá trị `source_site`:** `metruyenchu` , `tangthuvien` · **Ý nghĩa:** Có trong dropdown UI · **Ai xử lý:** Không khớp registry (xem mục 6 — hạn chế)

Cấu hình chung cũng đặt nguồn mặc định là thư mục cục bộ: `configs/global_config.json` → `"crawler": {"default_site":` `"local",...}` . Đây là lựa chọn có chủ ý cho chế độ demo sạch bản quyền (mục 2.8).

### 1.2. Input / Output

Input (chế độ cào web): tên nguồn ( `--source` ), `--base-url` , `--story-id` (ID số hoặc URL), `--start-chapter-id` (ID hoặc URL), `--num-chapters` , `--output-dir` , cờ `--continue-download` — định nghĩa tại `toolCaoTruyen/adapter_cli.py:395-403` .

Output: thư mục `storage/truyen/<slug>/raw/` ( `StorageManager.truyen_dir =<storage_dir>/truyen` , `orchestrator/storage.py:53` , `get_story_dir:65-68` ; `storage_dir` mặc định `"storage"` trong `configs/global_config.json` ) chứa:

- **File:** `Chương 0001 -1` `.md` ... · **Nội dung:** Văn bản thuần một chương (UTF-8), đoạn cách nhau 1 dòng trống · **Tạo ở đâu:** `core/crawler_engine.py:111-150` `save_to_markdown`
- **File:** `.crawler_state.json` · **Nội dung:** `{"last_chapter_index", "next_url", "reached_end"}` để tải tiếp · **Tạo ở đâu:** `core/crawler_engine.py:589-599`
- **File:** `_original.zip` · **Nội dung:** Nén (ZIP_DEFLATED) mọi file `.md` đang có trong `raw/` tại thời điểm cào xong — mục đích là sao lưu bản gốc trước khi bước dịch xoá chúng. Lưu ý: vì bước dịch ghi bản `[VI]` vào cùng thư mục `raw/` ( `pipeline.py:174-175` ), zip cũng chứa cả các bản `[VI]` đã có; và zip được mở chế độ `'w'` nên mỗi lần cào lại sẽ ghi đè zip cũ · **Tạo ở đâu:** `adapter_cli.py:50-59`
- **File:** stdout: các dòng JSON · **Nội dung:** `{"event": "crawl_start",...}` , `compress_start` , `compress_success` , `crawl_warn` , `crawl_completed` , `crawl_failed` · **Tạo ở đâu:** `adapter_cli.py:16-19log_json`

Quy ước tên `Chương NNNN -<tiêuđề>.md` (4 chữ số, đệm 0) là "khoá" nhận diện chương của cả pipeline: bước dịch thêm nhãn `- [VI]` , bước TTS và ghép video lọc theo nhãn này ( `orchestrator/chapter_naming.py:21` , `:125-127` hàm `chapter_prefix` ).

### 1.3. Sơ đồ vị trí

## 2. Nền tảng lý thuyết từ gốc

### 2.1. Web hoạt động thế nào: HTTP request / response

Trực giác: trình duyệt giống người gọi điện đến tổng đài (server). Mỗi cuộc gọi là một request: "Cho tôi trang `/txt/30756/30756382` ". Tổng đài trả lời một response: mã trạng thái + tiêu đề + nội dung.

Cơ chế: HTTP/1.1 là giao thức dạng văn bản chạy trên TCP (thường bọc TLS → HTTPS). HTTP/2 giữ nguyên ngữ nghĩa (method, header, status) nhưng mã hoá khung dạng nhị phân và ghép nhiều request trên một kết nối; HTTP/3 chạy trên QUIC (UDP). Ví dụ dưới viết theo dạng HTTP/1.1 cho dễ đọc. Một request tối thiểu:

```
GET /txt/30756/30756382 HTTP/1.1
Host: www.69shuba.com
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/125.0.0.0 Safari/537.36
Accept: text/html
Accept-Language: zh-CN,zh;q=0.9
Cookie: cf_clearance=...
```

Response:

```
HTTP/1.1 200 OK
Content-Type: text/html; charset=gbk
Set-Cookie: ...
```

```
<!DOCTYPE html><html>...
```

Các khái niệm cần nắm:

- **Khái niệm:** Method · **Giải thích:** `GET` (lấy dữ liệu), `POST` (gửi dữ liệu, ví dụ form tìm kiếm). Code dùng cả hai: `driver.get(url)` là GET; form tìm kiếm 69shu là POST ( `sources/shuba69.py:546-560` ).
- **Khái niệm:** Status code · **Giải thích:** `200` OK, `301/302` chuyển hướng, `403` bị cấm, `404` không tồn tại, `429` quá nhiều request, `503` (Cloudflare challenge thường trả 403/503).
- **Khái niệm:** Header · **Giải thích:** Metadata dạng `Tên: giá trị`. Quan trọng với crawler: `User-Agent` , `Cookie` , `Accept-Language` , `Content-Type` (chứa `charset` ).
- **Khái niệm:** User-Agent (UA) · **Giải thích:** Chuỗi tự giới thiệu "tôi là trình duyệt gì". Script Python mặc định gửi `python-requests/2.x` → server nhận ra ngay là bot.
- **Khái niệm:** Cookie · **Giải thích:** Server "đóng dấu" vào client để nhớ phiên. Cloudflare cấp cookie `cf_clearance` sau khi trình duyệt vượt thử thách; các request sau mang cookie này sẽ được cho qua nhanh.
- **Khái niệm:** Stateless · **Giải thích:** HTTP không nhớ gì giữa các request; mọi "trạng thái" nằm ở cookie/URL.

Liên hệ code: project không gửi HTTP thô bằng `requests` / `urllib` để cào truyện. Nó điều khiển một Chrome thật qua Selenium ( `core/crawler_engine.py:14-76` ), nên header/cookie/TLS đều do Chrome tạo — giống hệt người dùng. UA được ghi đè thành Chrome 125/Windows ( `core/crawler_engine.py:35-39` ). Chỉ phần gọi LLM trong tìm kiếm thông minh mới dùng `urllib.request` ( `core/intelligent_search.py:40-47` ).

### 2.2. HTML, DOM và vì sao phải "parse"

HTML là văn bản có thẻ lồng nhau:

```
<div class="txtnav">
  <h1 class="hide720">1 </h1>
  <div class="txtinfo">...</div>
          <br><br><br>
  <script>loadAdv(...)</script>
</div>
```

Trình duyệt (hoặc thư viện parser) đọc chuỗi này thành DOM — Document Object Model: một cây trong đó mỗi thẻ là một node, có cha/con/anh em, có attribute ( `class` , `id` , `href` ) và text node.

Vì sao không dùng regex trên toàn bộ HTML? HTML có thẻ lồng nhau tuỳ ý (ngôn ngữ phi chính quy — non-regular), regex không đếm được độ sâu lồng nhau, dễ vỡ khi thuộc tính đổi thứ tự hay có xuống dòng. Parser xây cây đúng cấu trúc rồi cho phép truy vấn trên cây. Project vẫn dùng regex nhưng chỉ cho các mẩu nhỏ, có cấu trúc cố định (biến JS `bookinfo` , ID trong URL) — đây là cách dùng đúng.

### 2.3. CSS selector — ngôn ngữ "chỉ đường" trong cây DOM

CSS selector vốn dùng để chọn phần tử cần tô màu; crawler mượn nó để chọn phần tử cần lấy dữ liệu.

- **Selector:** `div.txtnav` · **Nghĩa:** thẻ `div` có class `txtnav` · **Ví dụ trong code:** `sources/shuba69.py:224`
- **Selector:** `div#txtright` · **Nghĩa:** `div` có `id="txtright"` · **Ví dụ trong code:** `sources/shuba69.py:225`
- **Selector:** `h1.hide720,` `h1.txtTitle, h1` · **Nghĩa:** dấu phẩy = "hoặc" (hợp các tập khớp). Với `select_one` , kết quả là phần tử khớp đứng đầu theo thứ tự trong tài liệu, không phải theo thứ tự ưu tiên viết trong selector · **Ví dụ trong code:** `sources/shuba69.py:202`
- **Selector:** `.catalog > ul > li >` `a` · **Nghĩa:** `>` = con trực tiếp · **Ví dụ trong code:** `sources/shuba69.py:698`
- **Selector:** `.catalog ul li a` · **Nghĩa:** khoảng trắng = hậu duệ ở mọi độ sâu · **Ví dụ trong code:** `sources/shuba69.py:699`
- **Selector:** `table.grid tr` · **Nghĩa:** mọi hàng của bảng class `grid` · **Ví dụ trong code:** `sources/shuba69.py:629`

- Điểm tinh tế hay bị hỏi: selector có dấu phẩy không tạo thứ tự ưu tiên. Vì trong DOM mọi `h1.hide720` cũng là một `h1` , selector `h1.hide720, h1.txtTitle, h1` thực chất tương đương "thẻ `h1` đầu tiên trong trang". Muốn thật sự ưu tiên thì phải thử lần lượt từng selector trong vòng lặp — đúng như code làm với danh sách 6 selector nội dung ( `shuba69.py:223-235` : `for selector in content_selectors:... if content_div: break` ).

XPath là ngôn ngữ truy vấn khác, mạnh hơn ở chỗ lọc theo nội dung text: `//a[contains(text(), '`下一章`')]` = "mọi thẻ `a` có chữ 'chương sau'". Code dùng XPath với Selenium để tìm nút chuyển chương ( `sources/shuba69.py:315` , `:322` ; `sources/metruyenchuvn.py:163` ).

### 2.4. BeautifulSoup — parser HTML của Python

`BeautifulSoup(html, "html.parser")` nhận chuỗi HTML, dựng cây DOM trong bộ nhớ (dùng parser có sẵn của thư viện chuẩn Python, không cần cài `lxml` ). Các thao tác project dùng:

- **API:** `soup.select_one(sel)` · **Tác dụng:** phần tử đầu tiên khớp selector, hoặc `None` · **Chỗ dùng:** `shuba69.py:185, 202, 233`
- **API:** `soup.select(sel)` · **Tác dụng:** danh sách mọi phần tử khớp · **Chỗ dùng:** `shuba69.py:708`
- **API:** `tag.find_all([...])` · **Tác dụng:** tìm theo tên thẻ / class (có thể regex) · **Chỗ dùng:** `shuba69.py:253-266`
- **API:** `tag.decompose()` · **Tác dụng:** xoá hẳn node khỏi cây (và giải phóng) · **Chỗ dùng:** xoá `script/style/iframe/ins/noscriptshuba69.py:253-256`
- **API:** `br.replace_with("\n")` · **Tác dụng:** thay node bằng text · **Chỗ dùng:** `shuba69.py:269-270`
- **API:** `p.insert_before("\n\n")` · **Tác dụng:** chèn text trước node · **Chỗ dùng:** `shuba69.py:273-275`
- **API:** `tag.get_text(strip=True)` · **Tác dụng:** ghép mọi text node con thành chuỗi · **Chỗ dùng:** nhiều nơi
- **API:** `a.get("href", "")` · **Tác dụng:** đọc attribute · **Chỗ dùng:** `shuba69.py:356`

Ý tưởng làm sạch: thay vì "cắt chữ", ta sửa cây trước (xoá node rác, đổi `<br>` thành xuống dòng, bọc `<p>` bằng dòng trống) rồi mới gọi `get_text()` một lần. Kết quả là văn bản có cấu trúc đoạn đúng như trang gốc.

### 2.5. Encoding: GBK, UTF-8 và "mojibake"

Trực giác: máy tính chỉ lưu byte. Encoding là "bảng tra" byte ↔ ký tự. Đọc bằng sai bảng → chữ loạn (mojibake), ví dụ `é‡ç”Ÿ` thay vì 重生.

- **Encoding:** ASCII · **Đặc điểm:** 1 byte, 128 ký tự Latin cơ bản.
- **Encoding:** GBK / GB2312 / GB18030 · **Đặc điểm:** Chuẩn Trung Quốc; chữ Hán = 2 byte. Nhiều site truyện Trung (đặc biệt site cũ) khai báo `charset=gbk` .
- **Encoding:** UTF-8 · **Đặc điểm:** Mã hoá Unicode độ dài biến đổi 1–4 byte; chữ Hán thường 3 byte, chữ Việt có dấu 2–3 byte. Chuẩn phổ biến nhất hiện nay.

Chuỗi decode đúng: server khai báo charset (header `Content-Type` hoặc thẻ `<meta charset>` ) → client dùng đúng bảng để biến byte thành Unicode string → khi ghi file, encode lại thành UTF-8.

Project xử lý thế nào (đọc từ code):

- 1. Không tự decode byte. `driver.page_source` ( `shuba69.py:110` ) trả về chuỗi Python `str` là cây DOM hiện tại đã được Chrome decode theo charset trang khai báo rồi serialize lại (không phải byte gốc server gửi). Vì vậy dù trang dùng GBK hay UTF-8, Python nhận Unicode chuẩn. (Việc 69shu cụ thể dùng GBK hay UTF-8 không được kiểm chứng trong code — code không cần biết, đó chính là lợi ích.) 2. Ghi file luôn `encoding="utf-8"` ( `crawler_engine.py:147` ), state JSON cũng UTF-8 ( `:352` , `:596` ). 3. In log JSON với `ensure_ascii=False` ( `adapter_cli.py:18` ) để chữ Hán/Việt không bị escape thành `\uXXXX` . 4. Orchestrator ép tiến trình con in UTF-8: `env["PYTHONIOENCODING"] = "utf-8"` và đọc pipe `encoding="utf-8"` ( `orchestrator/process_manager.py:43` , `:54` ). Nếu không có dòng này, khi stdout là pipe (không phải cửa sổ console), Python trên Windows dùng code page ANSI của hệ thống (ví dụ cp1252/cp1258) — code page này không chứa chữ Hán nên `print()` sẽ ném `UnicodeEncodeError` . 5. Chế độ `local` : file `.txt` / `.md` người dùng đưa vào được chép nguyên byte ( `shutil.copy2` , `orchestrator/chapter_naming.py:258` ), code không chuyển mã. Nghĩa là file đầu vào phải là UTF-8; file GBK/ANSI sẽ gây lỗi hoặc ra ký tự thay thế ở các bước sau (khi đọc tiêu đề, `_read_head` dùng `errors="replace"` , `chapter_naming.py:135-` `140` ).

- Nếu hội đồng hỏi "nếu dùng `requests` thì sao?": `requests` đoán encoding từ header; khi header thiếu charset nó mặc định ISO-8859-1 cho `text/*` → chữ Hán vỡ; phải tự đặt `resp.encoding = 'gbk'` hoặc dùng `resp.apparent_encoding` . Dùng Chrome thì tránh được lớp lỗi này.

### 2.6. Rate limiting, retry, backoff, circuit breaker

Rate limiting (phía server): server giới hạn số request/đơn vị thời gian của một IP; vượt → 429, CAPTCHA hoặc ban IP. Phía crawler phải "lịch sự": giãn cách request.

Jitter (độ trễ ngẫu nhiên): nếu nghỉ đúng 2.000s mỗi lần, lưu lượng có nhịp đều như máy → dễ bị phát hiện. Nghỉ ngẫu nhiên trong khoảng [a, b] giống người đọc hơn và phân tán tải.

Retry: lỗi mạng/lỗi tạm thời (timeout, trang chưa render xong) thường tự hết; thử lại vài lần có lợi. Nhưng retry vô hạn thì nguy hiểm.

Circuit breaker (cầu dao): mượn từ điện dân dụng — khi lỗi liên tiếp vượt ngưỡng, "ngắt cầu dao" dừng hẳn thay vì tiếp tục đập vào server hỏng (tránh lãng phí và tránh bị ban).

Các con số thật trong code:

- **Cơ chế:** Nghỉ giữa 2 chương thành công · **Giá trị:** `random.uniform(1.0, 2.5)` giây · **Vị trí:** `crawler_engine.py:616-` `622`
- **Cơ chế:** Nghỉ giữa 2 lần retry cùng URL · **Giá trị:** `random.uniform(0.5, 1.5)` giây · **Vị trí:** `crawler_engine.py:534`
- **Cơ chế:** Số lần thử lại cùng 1 URL · **Giá trị:** `MAX_PAGE_RETRIES = 10` · **Vị trí:** `crawler_engine.py:487`
- **Cơ chế:** Ngưỡng circuit breaker · **Giá trị:** `MAX_CONSECUTIVE_FAILURES = 10` · **Vị trí:** `crawler_engine.py:12`
- **Cơ chế:** Chờ Cloudflare lần đầu / các lần sau · **Giá trị:** 30 / 10 vòng poll (mỗi vòng ngủ 1s nếu còn "Just a moment", 0.5s nếu title rỗng → tối đa khoảng 30s / 10s) · **Vị trí:** `shuba69.py:78-101`
- **Cơ chế:** Nghỉ sau khi mở trang kết quả tìm kiếm · **Giá trị:** `time.sleep(1.5)` · **Vị trí:** `shuba69.py:397` , `:464`

Lưu ý: code không dùng exponential backoff (tăng thời gian chờ theo cấp số nhân: 1s, 2s, 4s...) mà dùng khoảng ngẫu nhiên cố định. Với tốc độ 1 chương / vài giây của một người dùng đơn lẻ, như vậy là đủ; nêu exponential backoff như hướng phát triển.

### 2.7. Chống bot và Cloudflare — nguyên lý

Cloudflare là reverse proxy/CDN đứng trước website. Chế độ "I'm Under Attack"/Managed Challenge trả về trang "Just a moment..." chạy JavaScript kiểm tra trình duyệt (thực thi JS, đặc điểm `navigator` , TLS fingerprint, hành vi...). Qua được → nhận cookie `cf_clearance` → các request sau được phục vụ trực tiếp.

Vì sao `requests` thuần thất bại: nó không chạy JavaScript, nên không bao giờ qua được challenge; TLS fingerprint của Python cũng khác Chrome.

Dấu hiệu tự động hoá mà trang web có thể soi:

- **Dấu hiệu:** `navigator.webdriver===true` (Selenium bật cờ này) · **Code xử lý:** Inject JS qua CDP `Page.addScriptToEvaluateOnNewDocument` để trả `undefined` · **Vị trí:** `crawler_engine.py:54-` `67`
- **Dấu hiệu:** Thiếu `window.chrome.runtime` , `navigator.plugins` rỗng · **Code xử lý:** `plugins` được ghi đè trả `[1, 2, 3, 4, 5]` ( `:60-62` ). Riêng dòng `window.navigator.chrome = { runtime: {} }` ( `:59` ) gán vào `navigator.chrome` , không phải `window.chrome` mà các script kiểm tra thường đọc — nên dòng này gần như không có tác dụng (Chrome chạy có giao diện vốn đã có sẵn `window.chrome` ). Nên nói thật nếu bị hỏi · **Vị trí:** `crawler_engine.py:59-` `62`
- **Dấu hiệu:** `navigator.languages` lạ · **Code xử lý:** Đặt `['zh-CN','zh','en']` (khớp site Trung) · **Vị trí:** `crawler_engine.py:63-` `65`
- **Dấu hiệu:** Thanh "Chrome is being controlled by automated software" / cờ `enable-` `automation` · **Code xử lý:** `excludeSwitches: ['enable-automation','enable-logging']` , `useAutomationExtension: False` · **Vị trí:** `crawler_engine.py:42-` `45`
- **Dấu hiệu:** Blink feature `AutomationControlled` · **Code xử lý:** `--disable-blink-features=AutomationControlled` · **Vị trí:** `crawler_engine.py:32`
- **Dấu hiệu:** Chế độ headless (UA chứa "HeadlessChrome", thiếu GPU...) · **Code xử lý:** Không dùng headless; đẩy cửa sổ ra ngoài màn hình `--window-` `position=-2400,0` , kích thước `1920,1080` · **Vị trí:** `crawler_engine.py:23-` `26`

Một điểm nữa cần biết: UA bị ghi đè cứng thành `Chrome/125.0.0.0` bằng tham số dòng lệnh, trong khi Chrome thật trên máy có thể là phiên bản khác. Các header Client Hints ( `Sec-CH-UA` ) và `navigator.userAgentData` vẫn báo phiên bản thật → UA và Client Hints có thể lệch nhau, bản thân sự lệch này cũng là một dấu hiệu bot (code không xử lý; hệ quả thực tế chưa được kiểm chứng).

CDP (Chrome DevTools Protocol) là kênh điều khiển nội bộ của Chrome (cái mà DevTools dùng). `Page.addScriptToEvaluateOnNewDocument` đảm bảo script chạy trước mọi script của trang, nên khi Cloudflare kiểm tra `navigator.webdriver` thì giá trị đã bị sửa.

Cách code đợi challenge ( `shuba69.py:78-108` ): poll `driver.title` mỗi giây; còn chứa "Just a moment" thì chờ tiếp; title có nội dung khác → đã qua. Hết thời gian mà vẫn "Just a moment" → trả `None` (coi như lỗi tải, để vòng retry xử lý).

- Về mặt đạo đức/pháp lý: kỹ thuật này chỉ làm crawler trông giống một người dùng trình duyệt bình thường, không phá mã hoá, không dò mật khẩu, không vượt paywall. Tuy vậy, vượt cơ chế chống bot vẫn có thể vi phạm điều khoản sử dụng của site — xem mục 2.8.

### 2.8. Pháp lý & đạo đức khi cào dữ liệu

- **Vấn đề:** Bản quyền nội dung · **Nội dung:** Truyện là tác phẩm có bản quyền (Luật SHTT VN; Công ước Berne). Tải về đọc cá nhân khác với phân phối lại / tạo tác phẩm phái sinh (video) để đăng công khai. · **Project làm gì:** Chế độ demo sạch bản quyền: `local` (tác phẩm public domain — nghiệm thu end-to-end bằng Tây Du Ký hồi 1 từ Project Gutenberg, theo `docs/trinh-bay-` `datn.md:714` ) và `ai_write` (nội dung tự sinh, docstring `orchestrator/story_writer.py:8-9` ).
- **Vấn đề:** robots.txt · **Nội dung:** File quy ước site nói bot nào được cào đường dẫn nào. Không bắt buộc về luật nhưng là chuẩn mực. · **Project làm gì:** Code không đọc robots.txt (grep không thấy) — cần thừa nhận thẳng là hạn chế.
- **Vấn đề:** Điều khoản sử dụng (ToS) · **Nội dung:** Nhiều site cấm cào tự động. · **Project làm gì:** Không kiểm tra; thuộc trách nhiệm người dùng.
- **Vấn đề:** Tải cho server · **Nội dung:** Cào ồ ạt = gần như tấn công DoS. · **Project làm gì:** Tuần tự 1 trình duyệt, nghỉ 1.0–2.5s/chương, circuit breaker.
- **Vấn đề:** Dữ liệu cá nhân · **Nội dung:** Không liên quan (chỉ lấy văn bản truyện). · **Project làm gì:** —

Cách trả lời an toàn trước hội đồng: "Module cào là thành phần kỹ thuật để chứng minh khả năng tích hợp nguồn dữ liệu thật; khi demo và nghiệm thu em dùng nguồn public domain hoặc AI tự sáng tác, nên sản phẩm video không vi phạm bản quyền. Crawler được thiết kế lịch sự: tuần tự, có độ trễ ngẫu nhiên và cầu dao ngắt."

### 2.9. Design pattern: Strategy + Registry (plugin)

Vấn đề: mỗi website có cấu trúc HTML khác nhau, nhưng thuật toán "tải trang → bóc nội dung → tìm link chương sau → lưu → lặp" là giống nhau.

Strategy pattern: tách phần thay đổi (cách bóc tách từng site) ra khỏi phần cố định (vòng lặp tải). Mỗi site là một "chiến lược" cài cùng một interface.

Registry pattern: một bảng tra `tên→class` , để chọn chiến lược bằng chuỗi (từ CLI/UI) mà không cần `if/elif` rải rác.

- Interface: `BaseSourceParser(ABC)` với các `@abstractmethodbuild_chapter_url` , `get_html` , `parse_chapter` , `is_valid_response` và các method có mặc định `get_next_chapter_url` (trả `None` ), `search_book` / `get_catalog` (ném `NotImplementedError` ), `get_book_url` (trả `None` ) — `sources/base.py:38-117` . Registry: `SOURCES = {"69shuba": Shuba69Parser, "metruyenchuvn": MetruyenchuvnParser}` và factory `get_source(name,` `base_url)` — `sources/registry.py:7-27` . Engine chỉ biết `BaseSourceParser` ( `crawler_engine.py:306` ), không biết site cụ thể.

Lợi ích (Open/Closed Principle): thêm site mới = viết 1 file `sources/<site>.py` + thêm 1 dòng vào `SOURCES` ; không sửa engine.

### 2.10. Crawler hay scraper? Mô hình duyệt trang

Web crawler (theo nghĩa hẹp, như Googlebot) là chương trình duyệt đồ thị web: mỗi trang là một đỉnh, mỗi link là một cạnh; crawler giữ một hàng đợi URL (frontier) và thường duyệt theo BFS, có tập "đã thăm" để không lặp. Web scraper tập trung trích xuất dữ liệu có cấu trúc từ một số trang đã biết. Công cụ trong đồ án là scraper có tính năng đi theo link: nó không duyệt cả đồ thị mà đi theo một chuỗi duy nhất "chương này → nút 下一章 → chương sau", giống duyệt một danh sách liên kết (linked list). Điều kiện dừng: hết link ( `next_url is None` ), đủ số chương, hoặc gặp lại URL đã thăm ( `visited_urls` — chính là tập "đã thăm" của thuật toán duyệt đồ thị, ở đây dùng để phát hiện chu trình).

Trang tĩnh và trang render bằng JavaScript:

- **Loại:** Server-side rendering (HTML có sẵn nội dung) · **Cách trình duyệt có nội dung:** Nội dung nằm ngay trong HTML server trả về · **Hệ quả với crawler:** `requests` + BS4 là đủ, nếu không có lớp chống bot
- **Loại:** Client-side rendering (JS gọi API rồi vẽ DOM) · **Cách trình duyệt có nội dung:** HTML ban đầu gần như rỗng, JS điền nội dung sau · **Hệ quả với crawler:** Cần trình duyệt chạy JS, hoặc gọi thẳng API
- **Loại:** Có challenge chống bot (Cloudflare) · **Cách trình duyệt có nội dung:** Trang đầu là trang kiểm tra bằng JS, qua mới thấy nội dung · **Hệ quả với crawler:** Cần chạy JS để lấy cookie — lý do chính project dùng Selenium

Vì `driver.page_source` lấy DOM hiện tại (sau khi JS đã chạy), code nhận được nội dung giống hệt người dùng nhìn thấy, bất kể trang thuộc loại nào ở trên.

## 3. Vì sao chọn công nghệ này (so sánh phương án)

### 3.1. Công cụ tải trang

- **Phương án:** `requests` / `urllib` + BeautifulSoup · **Ưu:** Rất nhanh, nhẹ, dễ · **Nhược:** Không chạy JS → không qua Cloudflare; phải tự xử lý encoding/cookie · **Kết luận cho project:** Không dùng cho cào; chỉ dùng `urllib` gọi LLM
- **Phương án:** `cloudscraper` / `curl_cffi` (giả TLS fingerprint) · **Ưu:** Nhanh hơn trình duyệt · **Nhược:** Chạy đua với Cloudflare, dễ hỏng khi CF cập nhật · **Kết luận cho project:** Không chọn
- **Phương án:** Selenium + Chrome thật · **Ưu:** Chạy JS đầy đủ, cookie/TLS thật, qua được challenge; Selenium 4 tự tải ChromeDriver (Selenium Manager) · **Nhược:** Chậm, tốn RAM (~vài trăm MB), cần cài Chrome · **Kết luận cho project:** Chọn ( `requirements.txt` : `selenium>=4.20.0` )
- **Phương án:** Playwright · **Ưu:** API hiện đại, auto-wait tốt · **Nhược:** Phải tải thêm bộ trình duyệt riêng; cũng bị phát hiện ở headless · **Kết luận cho project:** Có thể thay thế — hướng phát triển
- **Phương án:** Scrapy · **Ưu:** Framework crawl quy mô lớn, song song · **Nhược:** Quá nặng cho bài toán tuần tự vài chục chương; không chạy JS · **Kết luận cho project:** Over-engineering

Lý do quyết định: bài toán là tải tuần tự vài–vài chục chương cho một người dùng trên máy cá nhân, nút thắt là Cloudflare chứ không phải tốc độ. Chậm hơn vài giây mỗi chương không quan trọng vì các bước sau (TTS, Stable Diffusion) tốn hàng phút mỗi chương.

### 3.2. Parser

- **Phương án:** BeautifulSoup4 + `html.parser` · **Nhận xét:** Chịu lỗi HTML "bẩn" tốt, API CSS selector, không cần thư viện C. Chọn ( `beautifulsoup4>=4.12.0` ).
- **Phương án:** `lxml` · **Nhận xét:** Nhanh hơn nhiều nhưng cần build/wheel C; tốc độ không phải vấn đề ở đây.
- **Phương án:** Selenium `find_element` trực tiếp · **Nhận xét:** Mỗi truy vấn là 1 round-trip tới Chrome → chậm; dùng khi cần (tìm nút ) và có fallback sang BS4.
- **Phương án:** Regex toàn trang · **Nhận xét:** Dễ vỡ; chỉ dùng cho `var bookinfo = {...}` và ID trong URL.

### 3.3. Kiến trúc tích hợp: vì sao gọi qua subprocess CLI

`toolCaoTruyen` là một tool độc lập (có `main.py` CLI tương tác, `app.py` FastAPI + WebSocket riêng) và là git submodule với virtualenv riêng ( `toolCaoTruyen/.venv` ). Orchestrator dựng lệnh ( `orchestrator/pipeline.py:150-169` ), gọi `ProcessManager.start_process` ( `pipeline.py:270-277` ), hàm này chạy `subprocess.Popen` ( `orchestrator/process_manager.py:48-58` ) với `adapter_cli.py` :

- Cô lập dependency: Selenium, gemini_webapi... không lẫn vào venv của orchestrator. Cô lập lỗi: Chrome treo/crash không kéo sập server FastAPI; có thể `taskkill /T /F` cả cây tiến trình khi người dùng bấm Dừng ( `process_manager.py:126-140` ). Giao tiếp đơn giản: tham số qua argv, tiến độ qua stdout mỗi dòng một JSON, kết quả qua exit code (0/1) và file trên đĩa. Nhược: khởi động chậm hơn gọi hàm, phải serialize dữ liệu. Chấp nhận được.

## 4. Hiện thực trong code

### 4.1. Bản đồ module

- **File:** `toolCaoTruyen/adapter_cli.py` · **Dòng:** 427 · **Vai trò:** CLI không tương tác cho orchestrator; subcommand `crawl` và `translate`
- **File:** `toolCaoTruyen/main.py` · **Dòng:** 471 · **Vai trò:** CLI tương tác (hỏi `input()` ), có luồng tìm kiếm + chọn mục lục
- **File:** `toolCaoTruyen/app.py` · **Dòng:** 1011 · **Vai trò:** Web UI riêng của tool: FastAPI, `/api/search` , `/api/catalog` , WebSocket `/ws/crawl`
- **File:** `toolCaoTruyen/core/crawler_engine.py` · **Dòng:** 644 · **Vai trò:** `create_browser` , `download_chapters` (vòng lặp chính), `save_to_markdown` , resume
- **File:** `toolCaoTruyen/core/intelligent_search.py` · **Dòng:** 244 · **Vai trò:** Dùng LLM dịch tên truyện Việt → Trung, sinh tên thay thế, dịch kết quả
- **File:** `toolCaoTruyen/core/config_manager.py` · **Dòng:** 93 · **Vai trò:** Đọc/ghi `config.json` của tool, migrate field thiếu
- **File:** `toolCaoTruyen/sources/base.py` · **Dòng:** 119 · **Vai trò:** Interface `BaseSourceParser` + dataclass `BookSearchResult` , `ChapterInfo`
- **File:** `toolCaoTruyen/sources/registry.py` · **Dòng:** 27 · **Vai trò:** Bảng `SOURCES` + `get_source`
- **File:** `toolCaoTruyen/sources/shuba69.py` · **Dòng:** 782 · **Vai trò:** Parser 69shu: tải, bóc, làm sạch, tìm kiếm 3 tầng, mục lục
- **File:** `toolCaoTruyen/sources/metruyenchuvn.py` · **Dòng:** 351 · **Vai trò:** Parser Mê Truyện Chữ (tiếng Việt)
- **File:** `toolCaoTruyen/sources/book_search.py` · **Dòng:** 92 · **Vai trò:** `BookSearcher` — context manager quản lý Chrome cho search/catalog
- **File:** `orchestrator/pipeline.py` · **Dòng:** — · **Vai trò:** `start_step_1_crawl_translate` : dựng lệnh, chạy, chuyển trạng thái, chế độ `local`
- **File:** `orchestrator/chapter_naming.py` · **Dòng:** — · **Vai trò:** Chuẩn hoá tên file chương cho chế độ `local`

Ba "cửa vào" cùng dùng chung engine `download_chapters` : `adapter_cli.py:40` (orchestrator), `main.py:238` (CLI), `app.py:575-` `585` (WebSocket của tool). Đây là điểm cộng thiết kế: một lõi, nhiều giao diện, phân biệt nhau bằng `progress_callback` .

### 4.2. Orchestrator dựng lệnh cào

Endpoint `POST /api/pipeline/step1` ( `orchestrator/main.py:435-457` ) nhận `Step1Schema` ( `main.py:104-124` : `source_site` , `base_url` , `story_id` , `local_folder` , `start_chapter_id` , `max_chapters` mặc định 1, ...), gọi `_build_step1_args` ( `main.py:399-` `429` ) rồi `pipeline.start_step_1_crawl_translate` .

```
# orchestrator/pipeline.py:150-169
python_exe = os.path.abspath("toolCaoTruyen/.venv/Scripts/python.exe")
adapter_path = os.path.abspath("toolCaoTruyen/adapter_cli.py")
```

```
crawl_cmd = None
if crawl_args.get("source") != "local":
    crawl_cmd = [
        python_exe, adapter_path, "crawl",
        "--source", crawl_args["source"],
        "--story-id", crawl_args.get("story_id") or "Auto",
        "--start-chapter-id", crawl_args.get("start_chapter_id") or "Auto",
        "--num-chapters", str(crawl_args.get("num_chapters", 1)),
        "--output-dir", raw_dir
    ]
    if crawl_args.get("base_url"):
        crawl_cmd.extend(["--base-url", crawl_args["base_url"]])
    if crawl_args.get("continue_download"):
        crawl_cmd.append("--continue-download")
```

Điểm cần nói được:

- Dùng python của venv riêng của submodule, `cwd="toolCaoTruyen"` ( `pipeline.py:274` ) để `config.json` , `common_idioms.json` tương đối được tìm đúng. Lệnh là list (không phải chuỗi shell) → không có shell injection dù `story_id` là URL tuỳ ý. Trạng thái story: `CRAWLING` ( `pipeline.py:266` ) → khi xong `on_crawl_completed` : exit 0 và bật tự dịch → `TRANSLATING` rồi chạy tiếp `translate_cmd` trên cùng log queue ( `reuse_queue=True` , `pipeline.py:236-243` ); exit 0 không dịch → `CRAWLED` ; exit ≠ 0 → `CRAWL_FAILED` hoặc `CANCELLED` nếu người dùng bấm dừng ( `pipeline.py:220-263` ).

`close_queue_on_exit=False` cho tiến trình cào ( `pipeline.py:276` ) để queue log không đóng giữa lúc chuyển từ cào sang dịch — SSE ở WebUI thấy một luồng log liền mạch.

4.3. `adapter_cli.py crawl` — lớp vỏ mỏng

```
# toolCaoTruyen/adapter_cli.py:38-59 (rút gọn)
parser = get_source(args.source, args.base_url)
download_chapters(
    base_url=args.base_url, story_id=args.story_id,
    start_chapter_id=args.start_chapter_id, num_chapters=args.num_chapters,
    output_dir=output_dir, parser=parser,
    continue_download=args.continue_download)
```

```
md_files = [f for f in os.listdir(output_dir) if f.endswith(".md")]
if md_files:
    zip_path = os.path.join(output_dir, "_original.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for f in md_files:
            zipf.write(os.path.join(output_dir, f), f)
```

Default CLI: `--source 69shuba` , `--base-url https://www.69shuba.com/txt` , `--num-chapters 10` , `--start-chapter-id` `Auto` ( `adapter_cli.py:396-402` ). (Orchestrator luôn truyền `--num-chapters` nên giá trị 10 chỉ áp dụng khi chạy tay.) `--base-url` thực tế luôn là giá trị mặc định khi chạy từ WebUI chính: `buildStep1Payload` đọc `document.getElementById("s1BaseUrl")?.value||null` ( `webui/app.js:244` ) nhưng `webui/index.html` không có phần tử `s1BaseUrl` → `base_url = null` → orchestrator không thêm `--base-url` ( `pipeline.py:165-166` ) → adapter dùng `https://www.69shuba.com/txt` . Không truyền `progress_callback` → engine dùng `default_progress_callback` in chữ có màu ANSI ra stdout ( `crawler_engine.py:170-273` ); orchestrator đọc từng dòng và đẩy lên WebUI (grep `webui/*.js` , `orchestrator/*.py` không thấy chỗ lọc mã ANSI, nên log có thể lẫn ký tự điều khiển — chưa kiểm chứng trên giao diện). Chỉ các mốc chính ( `crawl_start` , `compress_start` / `compress_success` , `crawl_warn` , `crawl_completed` , `crawl_failed` ) là JSON. `_original.zip` tồn tại vì bước dịch sẽ xoá file gốc sau khi dịch thành công ( `adapter_cli.py:374-381` ) — zip là bản sao lưu (xem lưu ý ghi đè ở mục 1.2). Mọi `Exception` → `crawl_failed` + `sys.exit(1)` ( `adapter_cli.py:66-68` ) → orchestrator đặt `CRAWL_FAILED` . Nhưng: `download_chapters` không ném lỗi khi tải hỏng (nó chỉ `break` và báo qua callback). Vì vậy nếu không tải được chương nào, adapter chỉ in `crawl_warn "No chapters downloaded."` rồi vẫn `crawl_completed` + exit 0 ( `adapter_cli.py:60-64` ) → orchestrator coi là thành công và chuyển sang dịch/ `CRAWLED` . Ngược lại, lỗi mở Chrome gọi `sys.exit(1)` trong `create_browser` → `SystemExit` không phải `Exception` nên không có dòng `crawl_failed` , nhưng exit code vẫn là 1 → `CRAWL_FAILED` .

4.4. `create_browser` — dựng Chrome "giống người"

Đã phân tích ở 2.7. Thêm hai chi tiết:

`webdriver.Chrome(options=options)` không truyền đường dẫn driver → Selenium Manager (Selenium ≥ 4.6) tự tìm/tải ChromeDriver khớp phiên bản Chrome (thông điệp `crawler_engine.py:75` ). Lỗi khởi tạo → `sys.exit(1)` ( `crawler_engine.py:72-76` ) — hợp lý với CLI. Nhưng `app.py` gọi `download_chapters` qua `asyncio.to_thread` ( `app.py:575-585` ): `SystemExit` sinh trong thread worker được chuyển lại cho coroutine đang `await` , và vì nó không phải `Exception` nên khối `except Exception` của handler không bắt được; asyncio xử lý `SystemExit` đặc biệt (ném tiếp ra event loop), nên có nguy cơ làm dừng cả server của tool (suy luận từ cơ chế, chưa kiểm chứng thực nghiệm). Cải thiện: ném exception có kiểu riêng thay vì `sys.exit` .

4.5. `download_chapters` — trái tim của crawler

Chữ ký ( `crawler_engine.py:300-310` ): `base_url, story_id, start_chapter_id, num_chapters, output_dir, parser,`

- `progress_callback=None, is_stopped=None, continue_download=False` .
- Bước A — Xác định URL xuất phát ( `crawler_engine.py:334-340` ): · 1. `start_chapter_id` là URL `http(s)://` → dùng luôn. 2. Ngược lại `story_id` là URL → dùng `story_id` .

- 3. Ngược lại → `parser.build_chapter_url(story_id, start_chapter_id)` ; với 69shu là `f"` `{base_url}/{story_id}/{chapter_id}"` ( `shuba69.py:33-35` ).

Hệ quả: URL dán vào phải là URL của một trang chương. Nếu người dùng dán link trang giới thiệu truyện ( `/book/<id>.htm` ), engine vẫn mở nó như một chương; trang đó không có `txtnav` / `txtright` nên `is_valid_response` trả `False` 10 lần liên tiếp → dừng mà không tải được gì.

Bước B — Resume (tải tiếp), nếu `continue_download` ( `crawler_engine.py:345-389` ). Logic 3 lớp:

- **Tình huống:** Có `next_url` trong `.crawler_state.json` và `last_chapter_index>=disk_index` · **Hành động:** Tin state: nhảy thẳng tới `next_url` , đánh số tiếp từ `state_index`
- **Tình huống:** State thiếu/cũ hơn số file trên đĩa ( `disk_index` `> 0` ) · **Hành động:** Lập `resume_plan` : sau khi mở Chrome, tra mục lục `parser.get_catalog` để tìm chương `disk_index + 1` ( `:403-437` )
- **Tình huống:** Tra mục lục thất bại · **Hành động:** Dùng `fallback_url` từ state nếu có; nếu người dùng đã nhập điểm bắt đầu cụ thể thì dùng nó; nếu không còn cách nào → abort với thông báo rõ ràng, không âm thầm tải lại từ chương 1 ( `:439-464` )
- **Tình huống:** Mục lục hợp lệ nhưng không có chương kế tiếp · **Hành động:** `reached_end = True` , báo "Truyện chưa ra chương mới" ( `:423-430` )

`disk_index` lấy bằng `find_last_chapter_index` — regex `r"Chương\s+(\d+)\s+-"` trên tên file, tính cả bản `[VI]` ( `crawler_engine.py:153-167` ). Nhờ vậy dù bước dịch đã xoá file gốc, số chương vẫn đúng.

Bước C — Vòng lặp chính ( `crawler_engine.py:466-622` ):

```
# crawler_engine.py:487-534 (rút gọn)
MAX_PAGE_RETRIES = 10
while page_load_retry_count < MAX_PAGE_RETRIES:
    total_attempted += 1
    is_first = (total_attempted == 1)
    html = parser.get_html(driver, current_url, is_first_request=is_first)
    if html is not None:
        result = parser.parse_chapter(html)
        if result is not None:
            load_success = True
            break
    page_load_retry_count += 1
    # báo chapter_not_exist (html None) hoặc chapter_empty (parse None)
    time.sleep(random.uniform(0.5, 1.5))
```

Sau khi tải thành công 1 chương:

- 1. Reset `consecutive_failures = 0` , thêm URL vào `visited_urls` ( `:556-558` ). 2. Lấy `story_name` ở chương đầu tiên ( `:562-568` ). 3. `current_chapter_number += 1` và `save_to_markdown(...)` ( `:571-575` ). 4. Tìm URL chương sau từ DOM thật: `parser.get_next_chapter_url(driver)` ( `:587` ) — thay vì đoán `ID + 1` . Lý do: ID chương trên site không liên tục (chương bị xoá, chương VIP, chèn thông báo), tăng ID + 1 sẽ trúng 404 hoặc nhảy nhầm truyện. 5. Ghi state sau khi đã serialize xong ( `json.dumps` trước rồi mới `open(...,"w")` , `:590-597` ) → nếu serialize lỗi thì không để lại file state rỗng. 6. `next_url is None` → hết truyện, `reached_end = True` ( `:601-604` ). 7. Kiểm tra `is_stopped()` rồi nghỉ `uniform(1.0, 2.5)` ( `:609-622` ).

Các "chốt an toàn":

- **Chốt:** `visited_urls` · **Mục đích:** Nếu trỏ lại trang cũ → phát hiện vòng lặp vô hạn, dừng · **Vị trí:** `:476-481`
- **Chốt:** 10 lần retry / URL · **Mục đích:** Lỗi tạm thời · **Vị trí:** `:487-534`
- **Chốt:** Thất bại cả 10 lần → `break` · **Mục đích:** Không có trang hiện tại thì không biết link chương sau, buộc phải dừng · **Vị trí:** `:537-553`
- **Chốt:** `MAX_CONSECUTIVE_FAILURES` · **Mục đích:** Cầu dao tổng; do cơ chế `break` ở trên nên thực tế chỉ tăng tới 1 rồi dừng — hằng số này là di sản từ phiên bản cũ tự tăng ID · **Vị trí:** `:12` , `:544-551`
- **Chốt:** `finally: driver.quit()` · **Mục đích:** Luôn đóng Chrome, kể cả khi exception · **Vị trí:** `:624-630`
- **Chốt:** `is_stopped` · **Mục đích:** Cho phép Web UI của tool dừng giữa chừng · **Vị trí:** `:468-473` , `:610-615`

Nhận xét trung thực: đoạn `:341-342` khai báo lại `story_name` , `successful_downloads` (đã khai báo ở `:328-330` ) và `:392-` `393` reset lại `consecutive_failures` , `total_attempted` — dư thừa, không sai. Ngoài ra thông điệp in ra cho sự kiện `chapter_not_exist` ở `default_progress_callback` vẫn ghi "đang thử ID tiếp theo..." ( `:184` ) — là chữ còn sót từ phiên bản cũ tự tăng ID; thực tế engine đang thử lại cùng URL.

4.6. `Shuba69Parser` — bóc tách một trang chương

`get_html` ( `shuba69.py:55-124` ):

1. `driver.get(url)` . 2. Poll Cloudflare: `max_wait = 30 if is_first_request else 10` vòng; "Just a moment" → `sleep(1)` ; title thật → break; title rỗng → `sleep(0.5)` . 3. Vẫn còn challenge → `None` . 4. `html = driver.page_source` ; `is_valid_response` yêu cầu `len(html)>=500` và chứa chuỗi `txtnav` hoặc `txtright` ( `:126-136` ). 5. Phát hiện 404 bằng so khớp chính xác title `"69`书吧`_404"` hoặc `"404"` , hoặc chứa 找不到 (không tìm thấy) / 不存在 (không tồn tại) ( `:116-118` ). Comment giải thích: tránh nhận nhầm chương có tên "第404章" là trang lỗi — một edge case tinh tế đáng kể với hội đồng.

`parse_chapter` ( `shuba69.py:138-246` ) dùng hai phương pháp theo thứ tự tin cậy:

```
# shuba69.py:159-175 (gộp dòng, bỏ comment)
bookinfo_match = re.search(r"var\s+bookinfo\s*=\s*\{(.*?)\};", html, re.DOTALL)
if bookinfo_match:
    bookinfo_text = bookinfo_match.group(1)
    name_match = re.search(r"articlename:\s*'([^']*)'", bookinfo_text)
    if name_match:
        story_name = name_match.group(1).strip()
    chapter_match = re.search(r"chaptername:\s*'([^']*)'", bookinfo_text)
    if chapter_match:
        chapter_name = chapter_match.group(1).strip()
```

PP1: site nhúng metadata trong biến JavaScript `bookinfo` → đọc bằng regex (non-greedy `.*?` + `re.DOTALL` để khớp qua nhiều dòng). Đây là dữ liệu máy sinh, ổn định hơn giao diện. PP2 (fallback): tên truyện từ breadcrumb `div.bread` (link cuối), rồi `<title>` tách theo `-` ; tên chương từ `h1.hide720,` `h1.txtTitle, h1` (thực chất là `h1` đầu tiên — xem lưu ý ở 2.3), rồi `<title>` ( `:184-213` ). Không có tên chương → `None` (trang không hợp lệ). Nội dung: thử lần lượt 6 selector `div.txtnav` , `div#txtright` , `div.txtcont` , `div#content` , `div.chapter-content` , `div.content` ( `:223-235` ) — chuỗi fallback selector giúp chịu được việc site đổi giao diện nhẹ. Nội dung sau làm sạch `<50` ký tự → `None` (coi là rỗng, kích hoạt retry) ( `:243-244` ).

`_clean_content` ( `shuba69.py:248-303` ) — pipeline 7 bước:

1. `decompose` thẻ `script, style, iframe, ins, noscript` (quảng cáo/tracking). 2. `decomposeh1` (tiêu đề đã lấy riêng), `div.txtinfo` (thời gian cập nhật), và div có class khớp regex `txtbottom|pagebtn|bookbtn|txtlast|operation` (nút điều hướng).

3. `<br>` → `"\n"` . 4. Bọc mỗi `<p>` bằng `"\n\n"` trước và sau. 5. `get_text()` lấy text thô. 6. Lọc từng dòng theo `AD_PATTERNS` (16 regex, `:10-27` : `69shuba\.com` , `69`书吧, 请记住本站域名 "hãy nhớ tên miền trang này", 百度搜索, 笔趣阁, `loadAdv` ...) với `re.IGNORECASE` . 7. Gộp `\n{3,}` → `\n\n` , `strip()` .

Lưu ý về bước 6: lọc theo dòng nên một dòng chỉ cần chứa mẫu ở bất kỳ đâu là bị bỏ cả dòng. Mẫu rộng như 推荐`.*`阅读 ("giới thiệu ... đọc") hay 笔趣阁 có thể xoá nhầm một câu truyện hợp lệ có chứa các cụm này (false positive). Code không ghi lý do, nhưng có thể trình bày như một đánh đổi: mất một câu hiếm gặp còn hơn để quảng cáo lọt vào bước dịch và TTS.

Kết quả: văn bản thuần, mỗi đoạn cách nhau đúng 1 dòng trống — đúng định dạng đoạn của Markdown, thuận lợi cho bước dịch (chia chunk theo đoạn) và TTS.

`get_next_chapter_url` ( `shuba69.py:305-366` ): 2 tầng

1. Selenium XPath `//div[contains(@class, 'page1')]/a[contains(text(), '`下一章`')]` , rồi rộng hơn `//a[contains(text(),` `'`下一章`')]` . 2. Fallback BeautifulSoup trên `page_source` , tìm `a` chứa 下一章, chuyển link tương đối thành tuyệt đối bằng `urljoin(driver.current_url, href)` . - Bộ lọc quan trọng: href không chứa `/txt/` → trả `None` ( `:331-332` ). Ở chương cuối, nút "chương sau" của 69shu trỏ về trang thông tin truyện `/book/...` hoặc danh sách → nhờ lọc này engine hiểu là đã hết truyện.

4.7. `MetruyenchuvnParser` — nguồn tiếng Việt

So với 69shu ( `sources/metruyenchuvn.py` ):

`build_chapter_url` → `f"{base_url}/chuong-{chapter_id}"` ( `:13-18` ), nhưng docstring nói rõ chủ yếu dùng dán URL chương trực tiếp (vì URL có hậu tố ngẫu nhiên kiểu `chuong-1-AoCo2t_YhnIh` , xem `main.py:103-104` ). `is_valid_response` : `len>=500` và có `class="truyen"` , nếu không thì parse thử tìm `div.truyen` ( `:68-77` ). Tên truyện: selector `h1.current-book a, h1.current-book, h1` ; tên chương: `h2.current-chapter a, h2.current-chapter,` `h2` ; fallback breadcrumb `.breadcrumb a, .bread a` phần tử thứ 2/3, rồi `<title>` ( `:83-113` ). Nội dung `div.truyen` , làm sạch tương tự nhưng đơn giản hơn: chỉ xoá `script/style/iframe/ins/noscript` , đổi `<br>` / `<p>` ; không có `AD_PATTERNS` , không xoá `h1` / `div.txtinfo` /nút điều hướng ( `:118-151` ). `get_html` cũng không có bước nhận diện trang 404 như 69shu ( `:20-66` ). Chương sau: XPath chứa `Chương tiếp` hoặc `Tiếp` , bỏ `href="#"` ; fallback BS4 khớp rất rộng ( `"tiếp" in text.lower()` ) và không có bộ lọc "hết truyện" kiểu `/txt/` của 69shu ( `:158-182` ). Ở chương cuối, chốt `visited_urls` là thứ ngăn lặp vô hạn. Tìm kiếm: chỉ DuckDuckGo → Yahoo ( `:345-351` ), không có tầng form nội bộ. Parser này không cài `get_book_url` (base trả `None` , `base.py:114-117` ) và không cài `get_catalog` → trong chế độ resume, `book_url` là `None` nên engine bỏ qua bước tra mục lục ( `crawler_engine.py:411-412` ) và rơi xuống nhánh fallback ( `:439-464` ).

### 4.8. Tìm kiếm truyện theo tên

Có hai lớp: (a) chiến lược tìm trên web của parser, (b) lớp "thông minh" dùng LLM chuyển ngữ truy vấn.

(a) `Shuba69Parser.search_book` — 3 tầng fallback ( `shuba69.py:525-685` ):

- **Tầng:** 1. DuckDuckGo HTML ( `_search_via_ddg` , `:380-445` ) · **Cách làm:** Mở bằng chính Chrome/Selenium ( `driver.get` , không dùng `requests` ) URL `https://html.duckduckgo.com/html/?q=site:69shuba.com<từ` `khoá>` (domain lấy từ `base_url` , bỏ `www.` ); nghỉ 1.5s; parse `a.result__url` ; giải mã link thật từ tham số `uddg=` ; chỉ nhận URL có `69shuba` , không có `/txt/` , trích `book_id` bằng `/book/(\d+)` hoặc `69shuba\.com/(\d+)/?$` · **Vì sao:** Trang tìm kiếm của 69shu có Cloudflare Turnstile (comment `:527` ); search engine là "cửa sau" không bị chặn
- **Tầng:** 2. Yahoo Search ( `_search_via_yahoo` , `:447-523` ) · **Cách làm:** Mở `https://search.yahoo.com/search?p=...` ; selector `.algo-title,` `.compTitle h3 a, #web a` ; giải mã link thật từ `/RU=` ; chấp nhận cả domain `69shu` · **Vì sao:** Dự phòng khi DDG lỗi/rỗng
- **Tầng:** 3. Form POST nội bộ ( `:537-685` ) · **Cách làm:** Mở trang chủ, chờ CF, dùng JS tạo `<form method=POST` `action=/modules/article/search.php>` với `searchkey` , `searchtype=all` rồi `submit()` · **Vì sao:** Mô phỏng người dùng bấm tìm; nếu site redirect thẳng tới `/book/<id>` (khớp duy nhất) thì đọc tiêu đề/tác giả trên trang đó; nếu không, parse danh sách bằng 3 bộ selector ( `div.newbox > ul >` `li` / `div.newbox ul li` , `table.grid` `tr` , `.booklist .bookinfo, .booklist` `li, .book-item` )

Hậu xử lý khác nhau theo tầng (đọc kỹ code):

- Tầng 1 và 2: loại trùng ngay trong vòng lặp bằng `seen_ids` , làm sạch tiêu đề bằng regex bỏ đuôi 最新章节`...` , 无弹窗`...` , `-69`书吧`...` ; không giới hạn số kết quả; tác giả để `"Unknown"` . Tầng 3: loại trùng theo `book_id` và giới hạn 20 kết quả ( `:675-682` ); có đọc tác giả/trạng thái từ trang kết quả.

`search_debug.html` ở thư mục gốc tool là file HTML lưu lại để dò selector khi phát triển (không được code tham chiếu).

`get_catalog` ( `shuba69.py:687-780` ): mở `book_url` , thử 6 selector mục lục ( `.catalog > ul > li > a` , ..., `.listmain dd a` ) và chỉ chấp nhận khi tìm được ≥ 5 link (tránh khớp nhầm một khối nhỏ); fallback URL `/{book_id}/` ; lọc link có `/txt/\d+/(\d+)` ; loại trùng; rồi sắp xếp theo ID chương tăng dần và đánh lại `index` 1-based ( `:765-775` ). Lý do (comment trong code): đầu trang thường có khối "chương mới nhất" làm lệch thứ tự.

`BookSearcher` ( `sources/book_search.py:9-92` ) bọc parser thành context manager:

- Lazy init Chrome chỉ khi gọi `search` / `get_catalog` lần đầu ( `_ensure_driver` , `:29-37` ), dùng chung `create_browser` (cùng cấu hình chống bot). Reuse một driver cho cả search và catalog. `__exit__` luôn `quit()` driver và trả `False` (không nuốt exception) ( `:87-92` ).

(b) `core/intelligent_search.py` — tìm kiếm có LLM

Vấn đề: người dùng Việt nhớ tên Hán-Việt ("Mục Thần Ký") nhưng site Trung chỉ tìm được bằng chữ Hán ("牧神记").

- **Hàm:** `call_llm_raw` ( `:11-124` ) · **Làm gì:** Gọi 1 trong 3 engine theo `config.json` của tool · **Chi tiết thật:** Ollama `http://localhost:11434/api/chat` ( `stream: False` , `format: "json"` khi cần); Gemini REST `generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` ; proxy OpenAI-compatible `{base}/chat/completions` . Temperature 0.3, timeout 30s
- **Hàm:** `translate_query_to_chinese` ( `:126-` `154` ) · **Làm gì:** Việt/Hán-Việt → tên Trung gốc · **Chi tiết thật:** Nếu truy vấn không có ký tự Latin/tiếng Việt thì coi là tiếng Trung, trả nguyên ( `:129-130` ). Prompt few-shot 5 ví dụ (Đấu La Đại Lục → 斗罗大陆, ...). Kết quả bỏ nháy/khoảng trắng. Lỗi → dùng truy vấn gốc
- **Hàm:** `generate_alternative_chinese_names` ( `:156-184` ) · **Làm gì:** Khi tìm rỗng: prompt yêu cầu 5 tên thay thế, tránh các từ đã thất bại (code không kiểm tra lại số lượng — model trả bao nhiêu dùng bấy nhiêu) · **Chi tiết thật:** Yêu cầu JSON `{"alternatives": [...]}` ( `response_json=True` ), bóc code fence json` nếu model trả kèm; lỗi → trả danh sách rỗng
- **Hàm:** `translate_search_results` ( `:186-` `244` ) · **Làm gì:** Dịch tiêu đề + tác giả kết quả sang Hán-Việt trong 1 lần gọi · **Chi tiết thật:** Ghép theo `id` ; lỗi → giữ nguyên tiếng Trung

Hai luồng gọi:

`app.py:365-432/api/search` : dịch truy vấn → search → nếu rỗng thì gọi LLM sinh tên thay thế một lần (truyền `[keyword,` `translated_keyword]` làm danh sách thất bại) và thử lần lượt từng tên → dịch kết quả sang Hán-Việt. Cả ba bước LLM chỉ bật khi `source=="69shuba"` ( `:386-406` ). Chạy trong `asyncio.to_thread` để không chặn event loop. `main.py:278-359` CLI: tối đa 10 vòng ( `max_retries = 10` , `:310` ) sinh tên thay thế, mỗi vòng truyền danh sách `failed_attempts` tích luỹ để LLM không lặp lại → một dạng tìm kiếm có phản hồi (feedback loop). CLI không gọi `translate_search_results` .

Luồng tìm kiếm chỉ có ở UI riêng của `toolCaoTruyen` ( `app.py` , `main.py` ). WebUI chính của đồ án không gọi tìm kiếm: form Bước 1 chỉ có ô "ID truyện hoặc Link" ( `webui/index.html:139-141` ).

4.9. Định dạng file đầu ra `.md`

```
# crawler_engine.py:135-148
safe_chapter_name = sanitize_filename(chapter_name)
filename = f"Chương {chapter_index:04d} - {safe_chapter_name}.md"
os.makedirs(output_dir, exist_ok=True)
md_content = f"{content}\n"
filepath = os.path.join(output_dir, filename)
with open(filepath, "w", encoding="utf-8") as f:
    f.write(md_content)
```

`chapter_index` là số thứ tự tải về (1, 2, 3... hoặc tiếp nối khi resume), không phải ID trên site → tên file luôn liên tục, sắp xếp đúng nhờ đệm 4 chữ số ( `0009` < `0010` ). Nội dung không chứa tiêu đề chương (comment `:143` : "tránh lặp/thừa"; tiêu đề đã nằm trong tên file). Lưu ý docstring của hàm ( `:120-123` ) vẫn mô tả định dạng cũ có dòng `# {Tên Chương gốc}` — docstring đã lỗi thời, code mới là chuẩn. `sanitize_filename` ( `:79-108` ): thay `\ / : * ? "<>|` bằng `_` , bỏ ký tự điều khiển, gộp `_` , bỏ dấu chấm cuối (Windows không cho), cắt 200 ký tự, rỗng → `untitled` . Tham số `story_name` được truyền vào nhưng không dùng để tạo thư mục con (comment `:140` ), vì orchestrator đã cấp sẵn thư mục riêng cho mỗi truyện.

Vì sao chọn `.md` thay vì `.txt` /JSON: là văn bản thuần đọc được bằng mọi editor, đoạn phân cách bằng dòng trống (chuẩn Markdown), dễ diff, và các bước sau (dịch, ghép video) chỉ quét `.md` (comment `orchestrator/chapter_naming.py:23-25` ).

4.10. Chế độ nguồn `local` (demo sạch bản quyền)

Khi `source=="local"` , `crawl_cmd = None` và pipeline chạy thread nền `_copy_local` ( `pipeline.py:278-331` ):

1. `register_manual_task` với một `queue.Queue` để log vẫn chảy về WebUI như tiến trình thật ( `:282-284` ). 2. Nếu `local_folder` là thư mục: `chapter_naming.normalize_dir(local_dir, raw_dir, translated=not auto_translate,` `log=...)` — chép (không di chuyển, `shutil.copy2` ) sang `raw/` với tên chuẩn. 3. Thành công nếu vừa chép được file hoặc `raw/` đã có sẵn chương (chạy lại là idempotent, `:302-314` ). 4. Không nạp được gì → `_chan_doan_thu_muc_cuc_bo` ( `pipeline.py:43-87` ) chẩn đoán cụ thể: thư mục trống / chương nằm trong thư mục con (gợi ý đường dẫn đúng, tối đa 5) / sai phần mở rộng (liệt kê đuôi file thực có). 5. Là file chứ không phải thư mục, hoặc không tồn tại → thông báo tương ứng. 6. Gọi `on_crawl_completed(exit_code)` đúng một lần (comment `:287-288` ) → luồng dịch/trạng thái y hệt chế độ cào web.

Chuẩn hoá tên ( `orchestrator/chapter_naming.py` ):

Đoán số chương bằng 5 regex theo thứ tự ưu tiên ( `:30-41` ): 第`12`章/ 第`12`回; `Chương 12` / `chapter` / `chap` / `ch` ; `c12` ; tên chỉ có số; số ở cuối tên. Nếu có file không đoán được số hoặc số bị trùng → đánh số lại theo thứ tự sắp xếp tự nhiên ( `_natural_key` : `ch9` trước `ch10` ) ( `:188-197` ), vì TTS coi hai file cùng số là bản trùng và chỉ đọc một. Tiêu đề: phần còn lại của tên file, không có thì lấy dòng đầu nội dung ( `title_from_text` ), cắt `MAX_TITLE_LEN = 80` . Tên đích: `Chương NNNN - [VI] Tiêuđề.md` nếu không dịch (sẵn sàng cho TTS), hoặc không nhãn `[VI]` nếu sẽ dịch ( `chapter_filename` , `:50-60` ). File đã đúng chuẩn thì giữ nguyên, không tham gia đánh số lại. Được kiểm thử: `tests/test_chapter_naming.py` (13 test, ví dụ `test_normalize_danh_so_lai_khi_so_bi_trung` ) và `tests/test_pipeline_local_folder.py` (6 test, ví dụ `test_chuong_nam_trong_thu_muc_con_thi_chi_duong` ), `tests/test_pipeline_build_cmd.py::test_step1_crawl_cmd_source_local` .

4.11. Cấu hình của tool: `core/config_manager.py`

`DEFAULT_BASE_URL = "https://www.69shuba.com/txt"` , `DEFAULT_OUTPUT_DIR = "./truyen_tai_ve"` , `CONFIG_FILE =` `"config.json"` ( `:6-8` ). `load_config` tự migrate: thiếu `source` → điền `69shuba` ; thiếu block `translator` hoặc thiếu field con → điền mặc định và ghi lại file ( `:37-62` ). Đây là kỹ thuật schema migration đơn giản cho file cấu hình. Cấu hình này chỉ dùng cho UI riêng của tool và `intelligent_search` . Khi chạy từ orchestrator, tham số cào đi qua argv.

## 5. Sơ đồ luồng

### 5.1. Luồng cào một truyện (end-to-end)

5.2. Vòng lặp retry / dừng trong `download_chapters`

Xac dinh current_url

continue_download?

co

Doc state / tra muc luc

- khong

- da du num_chapters?

- chua

- is_stopped?

- khong

- url da tham?

abort

- khong

- get_html +

du roi

- parse_chapter

co

- ok

- loi

co

save_to_markdown

- con luot thu, toi da 10?

- co

- get_next_chapter_url,

- sleep 0.5-1.5s

- khong

- ghi state

- None

- url moi

- driver.quit, event

- sleep 1.0-2.5s

- complete

### 5.3. Luồng tìm kiếm thông minh (UI riêng của tool)

Sơ đồ vẽ cho nguồn `69shuba` . Vòng "sinh tên thay thế" chạy 1 lần trong `app.py` và tối đa 10 vòng trong `main.py` ; bước dịch kết quả sang Hán-Việt chỉ có ở `app.py` .

## 6. Hạn chế & hướng phát triển

- **#:** 1 · **Hạn chế (đọc từ code):** Lệch tên nguồn giữa UI và registry: dropdown có `metruyenchu` , `tangthuvien` ( `webui/index.html:134-135` ) nhưng `SOURCES` chỉ có `69shuba` , `metruyenchuvn` ( `sources/registry.py:7-10` ) · **Hệ quả:** Chọn 2 nguồn này → `get_source` ném `ValueError` → `crawl_failed` → `CRAWL_FAILED` · **Hướng khắc phục:** Đồng bộ key ( `metruyenchu` → `metruyenchuvn` ), ẩn/xoá `tangthuvien` cho tới khi có parser; hoặc để UI lấy danh sách từ registry (tool đã có `/api/sources` ở `app.py:274` )
- **#:** 2 · **Hạn chế (đọc từ code):** `--start-chapter-id Auto` với `story_id` là số: help text nói "'Auto' uses the first chapter" ( `adapter_cli.py:399` ) và placeholder WebUI ghi "Bỏ trống nếu lấy chương đầu mặc định" ( `webui/index.html:178` ), nhưng engine chỉ gọi `build_chapter_url(story_id, "Auto")` → URL `.../<id>/Auto` ( `crawler_engine.py:340` ). Dán link trang truyện `/book/...` cũng không chạy (xem 4.5 bước A) · **Hệ quả:** Không tải được, phải dán URL chương · **Hướng khắc phục:** Khi `Auto` : gọi `get_book_url` + `get_catalog` lấy chương 1 (logic đã có sẵn trong nhánh resume)
- **#:** 3 · **Hạn chế (đọc từ code):** Selector cứng theo HTML hiện tại của site · **Hệ quả:** Site đổi giao diện là hỏng; đã giảm nhẹ bằng chuỗi fallback selector + `bookinfo` · **Hướng khắc phục:** Selector cấu hình ngoài code; test hồi quy bằng HTML mẫu lưu sẵn; hoặc trích xuất nội dung chính bằng thuật toán (readability/boilerplate removal)
- **#:** 4 · **Hạn chế (đọc từ code):** Không đọc `robots.txt` , không kiểm tra ToS · **Hệ quả:** Rủi ro pháp lý/đạo đức · **Hướng khắc phục:** Thêm `urllib.robotparser` ; mặc định demo bằng `local` / `ai_write` (đã làm)
- **#:** 5 · **Hạn chế (đọc từ code):** Delay ngẫu nhiên cố định, không exponential backoff, không nhận biết 429 · **Hệ quả:** Nếu site siết rate limit sẽ fail nhanh · **Hướng khắc phục:** Backoff `base * 2^k + jitter` , đọc header `Retry-After`
- **#:** 6 · **Hạn chế (đọc từ code):** Tuần tự 1 trình duyệt · **Hệ quả:** Chậm (vài giây/chương) · **Hướng khắc phục:** Song song vài tab có giới hạn — nhưng tăng rủi ro bị ban; hiện tại không cần vì TTS/SD mới là nút thắt
- **#:** 7 · **Hạn chế (đọc từ code):** Chrome thật (không headless) tốn RAM, cần cài Chrome · **Hệ quả:** Nặng trên máy yếu · **Hướng khắc phục:** Playwright + stealth; hoặc dùng API chính thức nếu site có
- **#:** 8 · **Hạn chế (đọc từ code):** Vượt Cloudflare dựa vào "trông giống người" — cuộc đua mèo- chuột · **Hệ quả:** Có thể hỏng khi CF cập nhật · **Hướng khắc phục:** Chấp nhận; ưu tiên nguồn hợp pháp
- **#:** 9 · **Hạn chế (đọc từ code):** `create_browser` gọi `sys.exit(1)` khi lỗi ( `crawler_engine.py:76` ) · **Hệ quả:** Trong `app.py` ( `asyncio.to_thread` ), `SystemExit` không bị `except` `Exception` bắt, có thể lan ra event loop (chưa kiểm chứng) · **Hướng khắc phục:** Ném exception có kiểu riêng
- **#:** 10 · **Hạn chế (đọc từ code):** `MAX_CONSECUTIVE_FAILURES` gần như không bao giờ đạt 10 vì vòng lặp `break` sau 1 URL thất bại hoàn toàn · **Hệ quả:** Mã thừa gây hiểu nhầm · **Hướng khắc phục:** Bỏ, hoặc đổi chiến lược "bỏ qua chương lỗi" khi có mục lục
- **#:** 11 · **Hạn chế (đọc từ code):** `metruyenchuvn` không có `get_book_url` / `get_catalog` , không lọc quảng cáo, không nhận diện 404, không có bộ lọc "hết truyện" · **Hệ quả:** Resume kém tin cậy hơn, có thể lẫn text rác · **Hướng khắc phục:** Cài `get_book_url` + `get_catalog` , thêm `AD_PATTERNS` , lọc link chương sau theo mẫu URL chương
- **#:** 12 · **Hạn chế (đọc từ code):** `core/config_manager.py:22` có giá trị mặc định `gemini_offline_key` là một chuỗi key cứng trong source · **Hệ quả:** Lộ bí mật nếu repo public (dù chỉ là key proxy cục bộ) · **Hướng khắc phục:** Để rỗng, đọc từ biến môi trường
- **#:** 13 · **Hạn chế (đọc từ code):** Tìm kiếm phụ thuộc DuckDuckGo/Yahoo HTML — không phải API chính thức · **Hệ quả:** Search engine đổi HTML hoặc chặn bot là hỏng · **Hướng khắc phục:** Có tầng form nội bộ dự phòng; có thể thêm API tìm kiếm chính thức
- **#:** 14 · **Hạn chế (đọc từ code):** Tải hỏng không làm tiến trình thất bại: `download_chapters` chỉ `break` , adapter vẫn `exit 0` kể cả khi 0 chương ( `adapter_cli.py:60-64` ) · **Hệ quả:** Orchestrator báo `CRAWLED` /chuyển sang dịch dù không có dữ liệu mới; lỗi chỉ lộ ra ở log · **Hướng khắc phục:** `download_chapters` trả về số chương tải được; adapter `exit 1` khi bằng 0
- **#:** 15 · **Hạn chế (đọc từ code):** `_original.zip` nén cả bản `[VI]` và bị ghi đè mỗi lần cào ( `'w'` , `adapter_cli.py:55` ) · **Hệ quả:** Khi tải tiếp sau lúc bước dịch đã xoá bản gốc, zip mới không còn bản gốc của các chương cũ · **Hướng khắc phục:** Mở zip chế độ `'a'` và bỏ qua file đã có / chỉ nén file không có `[VI]`
- **#:** 16 · **Hạn chế (đọc từ code):** WebUI chính không có ô `s1BaseUrl` ( `webui/app.js:244` đọc phần tử không tồn tại) · **Hệ quả:** Luôn dùng base URL mặc định của 69shu · **Hướng khắc phục:** Thêm ô nhập hoặc suy base URL theo nguồn
- **#:** 17 · **Hạn chế (đọc từ code):** UA cứng `Chrome/125` có thể lệch phiên bản Chrome thật và Client Hints; `navigator.chrome` gán nhầm chỗ ( `crawler_engine.py:35-39` , `:59` ) · **Hệ quả:** Tăng khả năng bị nhận diện (chưa kiểm chứng) · **Hướng khắc phục:** Không ghi đè UA, hoặc dùng thư viện stealth duy trì đồng bộ

## Câu hỏi hội đồng có thể hỏi

### 1. Tại sao dùng Selenium mà không dùng `requests` cho nhanh?

Vì 69shu đặt sau Cloudflare, trang đầu trả "Just a moment..." yêu cầu chạy JavaScript để cấp cookie `cf_clearance` . `requests` không chạy JS và có TLS fingerprint khác Chrome nên không qua được. Selenium điều khiển Chrome thật ( `core/crawler_engine.py:14-76` ). Chậm hơn vài giây/chương nhưng không đáng kể so với TTS và Stable Diffusion.

### 2. Tại sao không chạy headless cho gọn?

Comment `crawler_engine.py:23` ghi rõ: Cloudflare phát hiện headless Chrome. Thay vào đó cửa sổ được đẩy ra ngoài màn hình ( `--window-position=-2400,0` ), người dùng không thấy nhưng trình duyệt vẫn là chế độ có giao diện.

### 3. Làm sao Chrome do Selenium điều khiển không bị nhận ra là bot?

Tắt cờ `AutomationControlled` , bỏ switch `enable-` `automation` , đặt UA Chrome 125/Windows, và inject JS qua CDP `Page.addScriptToEvaluateOnNewDocument` để `navigator.webdriver` trả `undefined` , giả `plugins` , `languages` ( `crawler_engine.py:29-67` ). Script CDP chạy trước mọi script của trang. Quan trọng nhất là không chạy headless — Chrome có giao diện thật nên phần lớn đặc điểm trình duyệt là thật. Em cũng tự nhận thấy dòng `window.navigator.chrome = {runtime: {}}` gán nhầm vào `navigator` thay vì `window.chrome` , nên gần như không có tác dụng — là điểm sẽ sửa.

### 4. Tại sao đi theo nút "下一章" (chương sau) thay vì tăng ID chương + 1?

ID chương trên site không liên tục (chương bị xoá, chèn thông báo). Đi theo link thật trong DOM ( `get_next_chapter_url` , `shuba69.py:305-366` ) luôn đúng thứ tự. Ở chương cuối, link trỏ sang `/book/` nên bị lọc (thiếu `/txt/` ) → engine biết đã hết truyện.

### 5. Nếu đang cào thì mất mạng hoặc tắt máy, tải tiếp thế nào?

Sau mỗi chương, engine ghi `.crawler_state.json` gồm `last_chapter_index` , `next_url` , `reached_end` . Với `--continue-download` : state còn mới → nhảy thẳng tới `next_url` ; state cũ hơn số file trên đĩa → tra mục lục tìm chương `disk_index + 1` ; không xác định được → dừng và báo người dùng nhập URL, không âm thầm tải lại từ chương 1 ( `crawler_engine.py:345-464` ).

### 6. Làm sao tránh lặp vô hạn hoặc spam server?

`visited_urls` phát hiện URL lặp ( `:476-481` ); tối đa 10 lần thử mỗi URL với nghỉ 0.5–1.5s; nghỉ 1.0–2.5s ngẫu nhiên giữa các chương; thất bại hoàn toàn một URL thì dừng; `finally` luôn `driver.quit()` .

### 7. Em xử lý encoding tiếng Trung (GBK) thế nào?

Không tự decode byte: `driver.page_source` là chuỗi Unicode đã được Chrome decode đúng theo charset trang khai báo. File ghi `encoding="utf-8"` , log JSON `ensure_ascii=False` , và orchestrator đặt `PYTHONIOENCODING=utf-8` cho tiến trình con ( `process_manager.py:43` ) để không lỗi codepage trên Windows.

### 8. BeautifulSoup làm gì, CSS selector là gì?

BS4 dựng cây DOM từ chuỗi HTML; CSS selector (ví dụ `div.txtnav` , `.catalog > ul > li > a` ) là cú pháp chỉ đường tới node cần lấy. Code dùng chuỗi selector fallback (6 selector nội dung, `shuba69.py:223-235` ) thử lần lượt trong vòng lặp để chịu được thay đổi giao diện nhẹ. (Nếu gộp bằng dấu phẩy trong một selector thì `select_one` trả phần tử đứng đầu tài liệu, không theo thứ tự ưu tiên — vì vậy phải dùng vòng lặp.)

### 9. Tại sao lấy tên truyện/chương bằng regex biến `bookinfo` trước rồi mới dùng HTML?

`var bookinfo = {...}` là metadata máy sinh của site, ổn định hơn giao diện hiển thị. Regex dùng được ở đây vì cấu trúc cố định và nhỏ; khi không có biến này mới fallback sang breadcrumb/ `h1` / `<title>` ( `shuba69.py:159-213` ).

### 10. Làm sao lọc quảng cáo khỏi nội dung?

Hai tầng: tầng cây DOM — `decompose` các thẻ `script/style/iframe/ins/noscript` , `h1` , `div.txtinfo` , các div điều hướng; tầng dòng — bỏ dòng khớp một trong 16 regex `AD_PATTERNS` như `69`书吧, 请记住本站域名 ( `shuba69.py:10-27` , `:248-303` ).

### 11. Kiến trúc thêm nguồn truyện mới thế nào?

Strategy + Registry: viết class kế thừa `BaseSourceParser` cài `build_chapter_url` , `get_html` , `parse_chapter` , `is_valid_response` (tuỳ chọn `get_next_chapter_url` , `search_book` , `get_catalog` ), rồi thêm 1 dòng vào `SOURCES` ( `sources/registry.py:7-10` ). Engine không cần sửa.

### 12. Tìm kiếm bằng tên tiếng Việt hoạt động ra sao?

LLM (temperature 0.3, timeout 30s) dịch tên Hán-Việt sang tên Trung bằng prompt few-shot; tìm qua DuckDuckGo → Yahoo → form POST của site; nếu rỗng thì LLM được yêu cầu sinh 5 tên thay thế, tránh các tên đã thất bại (Web UI của tool thử 1 lượt, CLI tối đa 10 vòng); cuối cùng (ở Web UI của tool) LLM dịch kết quả sang Hán-Việt. Ở Web UI của tool, các bước LLM chỉ bật cho nguồn 69shuba ( `core/intelligent_search.py` , `main.py:278-359` ). Tính năng này nằm ở UI riêng của tool, WebUI chính nhận ID/link.

### 13. Tại sao tìm qua DuckDuckGo thay vì ô tìm kiếm của site?

Trang tìm kiếm của 69shu có Cloudflare Turnstile (comment `shuba69.py:527` ). Search engine đã index site nên truy vấn `site:69shuba.com<tên>` cho link `/book/<id>` mà không đụng challenge. Form POST nội bộ vẫn được giữ làm tầng dự phòng cuối.

### 14. Cào truyện có bản quyền thì có vi phạm không? Demo của em dùng nguồn gì?

Có rủi ro nếu phân phối lại. Vì vậy nguồn mặc định là `local` ( `configs/global_config.jsondefault_site: "local"` ) và có `ai_write` ; nghiệm thu end-to- end dùng tác phẩm public domain. Crawler là thành phần kỹ thuật chứng minh khả năng tích hợp; em thừa nhận code chưa đọc `robots.txt` và đó là hướng cải tiến.

### 15. Tại sao orchestrator gọi crawler qua subprocess chứ không import trực tiếp?

Submodule có venv riêng (Selenium...), chạy tách tiến trình để lỗi Chrome không làm sập server, có thể kill cả cây tiến trình khi dừng ( `taskkill /T` `/F` ), giao tiếp đơn giản qua argv–stdout–exit code ( `orchestrator/pipeline.py:150-277` , `process_manager.py:22-140` ).

### 16. Nếu cào không được chương nào thì hệ thống báo gì?

Trả lời trung thực: log sẽ hiện lỗi từng lần thử và dòng `crawl_warn "No chapters downloaded."` , nhưng adapter vẫn thoát mã 0 ( `adapter_cli.py:60-64` ) vì `download_chapters` không ném lỗi khi tải hỏng. Orchestrator vì thế vẫn chuyển sang bước dịch/ `CRAWLED` . Đây là hạn chế em đã xác định; cách sửa là để engine trả số chương tải được và adapter thoát mã 1 khi bằng 0.

### 17. Crawler của em duyệt web theo BFS hay DFS?

Không phải cả hai theo nghĩa đầy đủ: nó không duyệt cả đồ thị link mà đi theo một chuỗi duy nhất "chương → nút 下一章 → chương sau", giống duyệt danh sách liên kết. Tập `visited_urls` đóng vai trò tập "đã thăm" để phát hiện chu trình. Mục lục ( `get_catalog` ) chỉ dùng để định vị lại khi tải tiếp, không dùng để duyệt.

## Tóm tắt 1 phút

"Bước 1a có nhiệm vụ đưa văn bản truyện về máy dưới dạng các file `Chương NNNN - tiêuđề.md` . Có ba nguồn: thư mục cục bộ, AI tự sáng tác, và cào web. Hai nguồn đầu là chế độ demo sạch bản quyền, trong đó thư mục cục bộ là nguồn mặc định. Với cào web, orchestrator gọi `adapter_cli.py crawl` bằng subprocess trong venv riêng. Crawler dùng Selenium điều khiển một Chrome thật, không headless, đã xoá dấu hiệu automation qua CDP, để vượt trang 'Just a moment' của Cloudflare. Mỗi chương được tải, parse bằng BeautifulSoup với chuỗi CSS selector dự phòng, lọc quảng cáo bằng regex, rồi ghi UTF-8. Link chương sau lấy từ nút '下一章' thật trong DOM chứ không đoán ID. Crawler lịch sự: nghỉ ngẫu nhiên 1 đến 2,5 giây, tối đa 10 lần thử mỗi trang, chống lặp URL, và lưu trạng thái để tải tiếp chính xác. Các nguồn truyện được cắm vào theo Strategy + Registry, nên thêm site mới chỉ cần một class. Hạn chế chính là selector phụ thuộc giao diện site và vấn đề pháp lý, nên em demo bằng nguồn public domain."
