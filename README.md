# Cào &amp; Dịch Video

> **Nhánh `feat/video-only`** — bản tách riêng của dự án, **chỉ làm hai việc**: cào video từ mạng
> xã hội và dịch/gắn phụ đề cho chúng. Toàn bộ luồng truyện chữ → hoạt hình 2D (Bước 1-3, TTS
> truyện, chatbot) đã được gỡ khỏi nhánh này; xem nhánh `main` nếu bạn cần luồng đó.

Chạy cục bộ trên máy cá nhân (Windows + GPU NVIDIA), không phụ thuộc dịch vụ trả phí.

```
ToolAutoMakeCartoonVideo2DFromComics/   (nhánh feat/video-only)
├── orchestrator/     # FastAPI :8100 — điều phối, quản lý tiến trình, thư viện video
├── webui/            # Giao diện 1 trang (HTML/CSS/JS thuần + SSE theo dõi tiến độ)
├── configs/          # Cấu hình (config.example.json → global_config.json)
├── storage/          # Dữ liệu người dùng: videos/, merged/, tasks/
└── AIVoice/          # [submodule] MediaComposer: yt-dlp, Whisper, PaddleOCR, TTS, ffmpeg
```

## Ba tác vụ

| Tác vụ | Chạy bằng | Vào → Ra |
|--------|-----------|----------|
| **Cào video** | `AIVoice/apps/MediaComposer/adapter_download_cli.py` | link video / playlist / kênh → thư mục video + `video.json` trong thư viện |
| **Dịch &amp; gắn phụ đề** | `AIVoice/apps/MediaComposer/adapter_autosub_cli.py` | video → `.srt` gốc + `.srt` đã dịch (+ video đã ghi phụ đề, lồng tiếng nếu bật) |
| **Ghép video** | `orchestrator/video_merger.py` | nhiều video → một file trong `storage/merged/` |

Mọi việc nặng (yt-dlp, Whisper, PaddleOCR, ffmpeg, TTS) chạy trong **tiến trình con** dùng
`AIVoice/.venv` để tự nhả VRAM khi xong. Orchestrator cố ý **không import torch/ffmpeg** — nó chỉ
dựng dòng lệnh, đọc stdout (mỗi dòng một JSON) rồi đẩy sang giao diện qua SSE.

## Tính năng

**Cào video**
- Dán nhiều link cùng lúc, mỗi dòng một link; nhận cả **playlist, kênh, hashtag** (yt-dlp tự giải).
- **Xem trước danh sách** trước khi tải, tích chọn đúng video mình muốn.
- Giới hạn số video mỗi link, **bỏ qua video đã có** trong thư viện, chọn dừng-hay-bỏ-qua khi lỗi.
- Hỗ trợ **file cookies** (Netscape `.txt`) cho video riêng tư/giới hạn vùng; tự lọc cookie WAF của
  TikTok (`_waftokenid`) — đây là nguyên nhân số một gây lỗi 403.
- Chẩn đoán lỗi bằng tiếng Việt: IP bị chặn, video là tập phim TikTok Series, thiếu đăng nhập…
- Tuỳ chọn **dịch luôn sau khi tải xong** — cào và dịch trong một lần bấm.

**Thư viện video**
- Danh sách video đã tải: nền tảng, độ phân giải, thời lượng, dung lượng, đã dịch hay chưa.
- Xem video ngay trong giao diện, mở thư mục trong File Explorer, xoá, lọc, tìm theo tên.
- **Nhập video có sẵn trên máy** — mặc định chỉ trỏ tới file gốc, không nhân đôi file hàng GB.
- Xem/sửa/tải file `.srt`, và ghi thẳng bản vừa sửa vào video.

**Dịch &amp; gắn phụ đề**
- Nguồn phụ đề: **Whisper** (phiên âm tiếng nói), **OCR** (tách chữ cháy trên hình, khoanh vùng bằng
  chuột), hoặc **nạp file `.srt` có sẵn**.
- Ngôn ngữ đích chọn được (Việt, Anh, Trung, Nhật, Hàn, Thái, Pháp, Tây Ban Nha).
- **Chỉ xuất `.srt`** (nhanh, để sửa tay trước) hoặc ghi hẳn phụ đề vào video.
- Tuỳ chỉnh kiểu chữ: phông, cỡ, màu, viền, nền hộp, vị trí.
- **Lồng tiếng** bản dịch (Edge-TTS / Piper / Kokoro / VieNeu / XTTSv2 clone) kèm ducking nhạc nền.
- Tách giọng khỏi nhạc nền bằng Demucs trước khi phiên âm.
- **Xử lý hàng loạt**: chọn nhiều video, chạy lần lượt cùng một bộ tham số, một luồng log duy nhất.
- Engine dịch: **Ollama** (mặc định, chạy trên máy, không cần key), **Gemini Online** (cần API key),
  hoặc proxy Gemini-API cục bộ nếu bạn tự cài.

## Cài đặt &amp; chạy

Repo dùng **git submodule** cho `AIVoice`. Phải clone kèm submodule:

```bash
git clone --recursive -b feat/video-only https://github.com/Duyycoder/ToolAutoMakeCartoonVideo2DFromComics.git
```

Lỡ clone thường thì chạy `git submodule update --init --recursive`.

Sau đó nháy đúp **`run.bat`** — máy chưa cài gì thì nó tự gọi `setup.bat` (tải Python 3.11 + thư viện
+ model, cần Internet, 30-60 phút) rồi mở cửa sổ ứng dụng. Muốn xem log trực tiếp: `run.bat debug`.

Dịch phụ đề mặc định dùng Ollama, cài một lần:

```bash
ollama pull qwen2.5:3b-instruct
```

## Giao diện

Mở ra là cửa sổ ứng dụng (WebView2), bên trong chạy orchestrator ở `http://127.0.0.1:8100`:

| Tab | Việc |
|-----|------|
| 📥 Cào Video | dán link, xem trước, tải hàng loạt |
| 📚 Thư Viện | video đã tải, phụ đề, bản đã gắn sub |
| 🈯 Dịch &amp; Phụ Đề | chọn nguồn phụ đề, ngôn ngữ, kiểu chữ, lồng tiếng |
| 🔗 Ghép Video | nối nhiều video thành một |
| ⚙️ Cấu Hình | thư mục dữ liệu, API key, engine dịch, dọn dẹp file tạm |

Nút **💾 Lưu cấu hình** ghi cả hai lớp: giá trị mặc định xuống `configs/global_config.json` và trạng
thái từng ô nhập xuống `configs/ui_settings.json` (mở lại app là điền sẵn như cũ).

## Dữ liệu nằm ở đâu

```
storage/
  videos/<ten_video>/
      video.json          # link nguồn, nền tảng, W×H, thời lượng
      <ten_video>.mp4     # bản gốc
      subs/*.srt          # phụ đề gốc + phụ đề đã dịch
      output/*.mp4        # bản đã ghi phụ đề / lồng tiếng
  merged/                 # video đã ghép
  tasks/                  # thư mục tạm (ảnh xem trước OCR…) — xoá được trong tab Cấu Hình
```

Đổi chỗ lưu bằng ô **Thư mục dữ liệu** trong tab Cấu Hình (cần khởi động lại app).

## API (nếu muốn tự động hoá)

| Endpoint | Việc |
|----------|------|
| `POST /api/download/probe` | giải link → danh sách video |
| `POST /api/download/start` | tải hàng loạt (task_key `download`) |
| `GET /api/videos`, `GET/DELETE /api/videos/{id}` | thư viện |
| `POST /api/videos/import` | nhập video có sẵn |
| `GET/POST /api/videos/{id}/sub` | đọc/ghi file phụ đề |
| `POST /api/translate/start` | dịch 1..n video (task_key `translate`) |
| `POST /api/autosub/prepare` | khung hình xem trước để khoanh vùng OCR |
| `POST /api/merge/start` | ghép video (task_key `merge`) |
| `GET /api/tasks/logs/{task_key}` | luồng log SSE |
| `POST /api/tasks/stop?task_key=` | dừng tác vụ |

Mỗi loại tác vụ chỉ chạy **một lần một** (GPU 6GB không kham nổi song song), đổi lại giao diện nối
lại đúng luồng log sau khi F5.

## Kiểm thử

```bash
AIVoice\.venv\Scripts\python.exe -m pytest -q
```

CI chạy `ruff` + `pytest` cho `orchestrator/` và `tests/` trên mỗi lần đẩy.

## Ghi chú về submodule

`AIVoice` là repo Git độc lập. Nhánh này trỏ tới nhánh `feat/video-only` của nó (chứa
`adapter_download_cli.py` và các tuỳ chọn dịch mới). Khi sửa code trong submodule: commit trong
`AIVoice/` trước, rồi commit con trỏ ở repo tổng.
