# Cào &amp; Dịch Video

> **Nhánh `feat/video-only`** — bản tách riêng của dự án, **chỉ lo video**: lấy video từ
> máy hoặc từ mạng xã hội, sắp đúng thứ tự, dịch + gắn phụ đề + lồng tiếng từng video, rồi ghép lại
> thành một. Luồng truyện chữ → hoạt hình 2D nằm ở nhánh `main`.

Chạy cục bộ trên máy cá nhân (Windows + GPU NVIDIA), không phụ thuộc dịch vụ trả phí.

---

## Cài trên máy mới

**Cần có sẵn:** Windows 10/11, [Git](https://git-scm.com), Internet, ~12 GB đĩa trống.
Python 3.11 không cần cài trước — `setup.bat` tự tải nếu máy chưa có.

### 1. Đặt thư mục gần gốc ổ đĩa

Ví dụ `D:\Tool\`. **Đừng** để sâu kiểu `Desktop\Đồ án\Năm 4\...` — dự án có submodule, đường dẫn
bên trong dễ vượt giới hạn 260 ký tự của Windows và clone sẽ hỏng giữa chừng. Cho chắc, bật hỗ trợ
đường dẫn dài một lần (mở `cmd` bằng quyền Administrator):

```bash
git config --system core.longpaths true
```

### 2. Clone kèm submodule

Mở `cmd` tại thư mục vừa chọn rồi chạy:

```bash
git clone --recursive -b feat/video-only https://github.com/Duyycoder/ToolAutoMakeCartoonVideo2DFromComics.git
```

Bắt buộc có `-b feat/video-only` — thiếu nó sẽ ra nhánh `main` (công cụ truyện tranh, khác hẳn).
Lỡ quên `--recursive` thì không sao — `setup.bat` tự kéo submodule về.

### 3. Nhấp đúp `setup.bat`

Nó tự làm hết: cài Python 3.11 (nếu thiếu), tạo môi trường, cài thư viện, tải mô hình giọng đọc,
cài WebView2, tạo file cấu hình. **Mất 30–60 phút**, cứ để cửa sổ chạy. Xong bấm một phím là cửa sổ
ứng dụng mở ra.

Từ lần sau chỉ cần nhấp đúp **`run.bat`**. (Nhấp `run.bat` ngay từ đầu cũng được — thấy máy chưa cài
thì nó tự gọi `setup.bat`.)

### 4. (Nên làm) Cài Ollama để dịch không cần API key

Tải ở [ollama.com](https://ollama.com), rồi:

```bash
ollama pull qwen2.5:3b-instruct
```

### Kiểm tra cài đúng chưa

```bash
AIVoice\.venv\Scripts\python.exe -m pytest -q
```

### Khi có sự cố

| Hiện tượng | Cách sửa |
|---|---|
| `run.bat` báo *"thiếu thư viện"* | Lần cài trước chưa xong — nhấp đúp `setup.bat` để cài bù. |
| Cửa sổ app không mở, nó bật trình duyệt thay thế | Thiếu WebView2 → chạy `scripts\cai_webview2.bat`. |
| Muốn xem app đang báo lỗi gì | `run.bat debug` — log hiện thẳng ra màn hình. Hoặc xem `logs\app.log`. |
| Đã **di chuyển thư mục dự án** rồi lỗi lung tung | Chạy lại `setup.bat` (các file `.exe` trong môi trường Python nhúng đường dẫn cũ). |
| Clone hỏng giữa chừng | Xoá hẳn thư mục đó, đặt ở chỗ đường dẫn ngắn hơn (bước 1) rồi clone lại. |

---

## Cách dùng

Mở ra là cửa sổ ứng dụng (WebView2), bên trong chạy ở `http://127.0.0.1:8100`.

**Dự án** — mọi việc bắt đầu từ ô *Dự án hiện tại* ở thanh bên trái:

- **📂 Mở thư mục có video…** — chọn thư mục chứa video của bạn. Lần đầu, app hiện **bảng xem trước**
  đổi tên theo dạng `001_ten.mp4`, `002_ten.mp4`… (sắp tự nhiên: `tap 2` đứng trước `tap 10`). Bạn duyệt
  thì mới đổi tên thật; tên cũ được lưu lại nên **hoàn tác lúc nào cũng được**. Chọn *Giữ nguyên tên
  file* nếu không muốn đổi.
- **➕ Tạo dự án trống…** — chọn chỗ đặt + đặt tên, dùng khi tải video từ link về.

Dự án chính là thư mục bạn chọn, có thêm file đánh dấu `.duan.json`:

```
<thư mục dự án>/
  .duan.json            # đánh dấu dự án + tên gốc của từng file (để hoàn tác)
  001_tap_1.mp4         # video, đã đánh số theo thứ tự
  002_tap_2.mp4
  phu_de/               # .srt
  da_sub/               # bản đã gắn phụ đề / lồng tiếng
  ban_ghep/             # bản ghép
```

| Tab | Việc |
|-----|------|
| 🎬 Lô Video | chọn file trên máy / dán link, sắp hàng đợi, chạy một mạch tải → dịch → ghép |
| 📚 Thư Viện | video của dự án: **tích chọn + ▲▼ sắp thứ tự ghép**, mặc định ẩn video đã ghép |
| 🈯 Dịch &amp; Phụ Đề | nguồn phụ đề (Whisper/OCR/file có sẵn), ngôn ngữ, kiểu chữ, lồng tiếng |
| 🔗 Ghép Video | nối video theo thứ tự; video khác độ phân giải được **tự chuẩn hoá** |
| ⚙️ Cấu Hình | engine dịch, API key, dọn file tạm |

Nút **💾 Lưu cấu hình** ghi giá trị mặc định xuống `configs/global_config.json` và trạng thái từng ô
nhập xuống `configs/ui_settings.json` (mở lại app là điền sẵn như cũ).

## Tính năng chính

- **Lấy video**: chọn nhiều file hoặc cả thư mục bằng hộp thoại của Windows; hoặc dán link video /
  playlist / kênh (TikTok, YouTube, Bilibili, Douyin — yt-dlp tự giải). Hỗ trợ file cookies Netscape
  cho video riêng tư, tự lọc cookie WAF của TikTok — nguyên nhân số một gây lỗi 403.
- **Đúng thứ tự từ đầu tới cuối**: thứ tự được ghi xuống đĩa (`.duan.json`, `video.json`), tắt app
  mở lại vẫn giữ; playlist dán vào được xếp gọn đúng chỗ của nó trong lô.
- **Dịch &amp; phụ đề**: Whisper (nghe tiếng) hoặc OCR (đọc chữ cháy trên hình, khoanh vùng bằng chuột)
  hoặc nạp `.srt` có sẵn. Ngôn ngữ đích chọn được. Tuỳ chỉnh phông, cỡ, màu, viền, vị trí.
- **Lồng tiếng**: Edge-TTS / Piper / Kokoro / VieNeu / XTTSv2 clone, tự hạ nhạc nền khi có lời.
- **Ghép**: cùng độ phân giải thì nối thẳng trong vài giây; lẫn video dọc với ngang thì tự đưa về
  chung khung (thêm viền đen, không kéo méo), video câm được chèn luồng tiếng im lặng cho khỏi lỗi.
- **Engine dịch**: Ollama (mặc định, chạy trên máy), Gemini Online (cần API key), hoặc proxy
  Gemini-API cục bộ nếu bạn tự cài.

Mọi việc nặng (yt-dlp, Whisper, PaddleOCR, ffmpeg, TTS) chạy trong **tiến trình con** dùng
`AIVoice/.venv` để tự nhả VRAM khi xong. Orchestrator cố ý **không import torch/ffmpeg** — nó chỉ
dựng dòng lệnh, đọc stdout (mỗi dòng một JSON) rồi đẩy sang giao diện qua SSE.

## Cấu trúc mã nguồn

```
orchestrator/     # FastAPI :8100 — điều phối, quản lý tiến trình, dự án, thư viện
  project.py      #   dự án = thư mục có .duan.json (đổi tên 2 pha, hoàn tác)
  pipeline.py     #   chuỗi tải/nhập → dịch → ghép
  video_merger.py #   nối video, chuẩn hoá khi khác cỡ
  file_picker.py  #   hộp thoại chọn file của Windows (chạy tiến trình riêng)
  desktop.py      #   cửa sổ ứng dụng (pywebview)
webui/            # giao diện 1 trang (HTML/CSS/JS thuần + SSE)
configs/          # cấu hình (tự sinh global_config.json lần chạy đầu)
AIVoice/          # [submodule] MediaComposer: yt-dlp, Whisper, PaddleOCR, TTS
tests/            # pytest
```

## API (nếu muốn tự động hoá)

| Endpoint | Việc |
|----------|------|
| `POST /api/project/inspect` | xem trước một thư mục: có video không, đổi tên sẽ ra sao (chỉ đọc) |
| `POST /api/project/init` · `create` · `open` · `undo-rename` | tạo / mở / hoàn tác dự án |
| `GET /api/project/videos?folder=` · `GET /api/project/recent` | video của dự án · dự án gần đây |
| `POST /api/system/pick-files` | mở hộp thoại chọn file/thư mục của Windows |
| `POST /api/download/probe` · `POST /api/download/start` | giải link · tải hàng loạt |
| `POST /api/videos/import-batch` | nhập nhiều file theo thứ tự (chạy nền) |
| `POST /api/translate/start` | dịch 1..n video |
| `POST /api/merge/start` | ghép video |
| `GET /api/tasks/logs/{task_key}` · `POST /api/tasks/stop?task_key=` | luồng log SSE · dừng |

Mỗi loại tác vụ chỉ chạy **một lần một** (GPU 6GB không kham nổi song song), đổi lại giao diện nối
lại đúng luồng log sau khi F5.

## Kiểm thử

```bash
AIVoice\.venv\Scripts\python.exe -m pytest -q
```

## Ghi chú cho người sửa code

- `AIVoice` là repo Git độc lập; nhánh này trỏ tới nhánh `feat/video-only` của nó. Sửa code trong
  submodule thì commit trong `AIVoice/` **trước**, rồi mới commit con trỏ ở repo tổng.
- File `.bat` phải là **CRLF + chỉ ký tự ASCII**. `.gitattributes` đặt `*.bat -text` nên git lưu
  nguyên như trên đĩa — lưu nhầm LF là hỏng trên mọi máy clone về.
- Sửa `orchestrator/*.py` xong phải tắt hẳn app rồi mở lại (server không chạy `--reload`).
