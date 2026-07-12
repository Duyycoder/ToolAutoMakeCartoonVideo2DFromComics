# ToolAutoMakeCartoonVideo2DFromComics

Hệ thống tự động chuyển **truyện chữ → video hoạt hình 2D có lồng tiếng**, chạy cục bộ trên máy cá nhân (Windows + GPU NVIDIA). Đây là repo tổng (đồ án tốt nghiệp), điều phối hai dự án con qua kiến trúc **orchestrator + subprocess**.

## Kiến trúc tổng quan

Hệ thống gồm 3 tầng, giao tiếp với nhau qua tiến trình con (subprocess) và giao thức tiến độ JSON trên stdout — mỗi bước nặng chạy trong một tiến trình riêng để **tự giải phóng VRAM khi kết thúc**.

```
ToolAutoMakeCartoonVideo2DFromComics/   (repo tổng)
├── orchestrator/     # FastAPI :8100 — điều phối pipeline, máy trạng thái, quản lý tiến trình
│                     # (venv siêu nhẹ: fastapi + uvicorn + httpx, KHÔNG import torch)
├── webui/            # Giao diện web 1 trang (HTML/CSS/JS thuần + SSE cập nhật tiến độ)
├── configs/          # Cấu hình toàn cục (config.example.json — copy thành global_config.json)
├── AIVoice/          # [submodule] TTS đa engine (edge/piper/xtts/kokoro/vieneu) + MediaComposer (sinh video)
└── toolCaoTruyen/    # [submodule] Cào truyện + dịch AI (Gemini API / Ollama) + quản lý glossary
```

### Luồng xử lý (pipeline 4 bước)

| Bước | Thành phần | Đầu vào → Đầu ra |
|------|-----------|------------------|
| 1. Cào + Dịch | `toolCaoTruyen/adapter_cli.py` | URL/ID truyện → chương `.md` tiếng Việt |
| 2. TTS | `AIVoice/adapter_tts_cli.py` | `.md` → `.wav` (giọng đọc) |
| 3. Sinh video | `AIVoice/apps/MediaComposer/adapter_video_cli.py` | `.md` + `.wav` → cảnh ảnh AI + video `.mp4` |
| 4. Hợp nhất | `orchestrator/video_merger.py` | các `.mp4` → video tổng hợp |

## Tải mã nguồn (QUAN TRỌNG — có submodule)

Repo này dùng **git submodule** cho `AIVoice` và `toolCaoTruyen`. Phải clone kèm submodule, nếu không hai thư mục đó sẽ **rỗng**:

```bash
git clone --recursive https://github.com/<user>/ToolAutoMakeCartoonVideo2DFromComics.git
```

Nếu đã lỡ clone thường (chưa có submodule):

```bash
git submodule update --init --recursive
```

## Cài đặt & chạy

1. Copy cấu hình mẫu và điền API key thật:
   ```bash
   copy configs\config.example.json configs\global_config.json
   ```
   (`global_config.json` đã bị `.gitignore` loại trừ — không bao giờ commit key thật.)
2. Chạy `setup.bat` — tạo venv tổng + gọi setup của 2 dự án con (tự nhận GPU, tải model).
3. Chạy `run.bat` — khởi động orchestrator :8100, tự bật Gemini-API proxy, mở trình duyệt.

## Yêu cầu hệ thống

- Windows 10/11, Python 3.11
- GPU NVIDIA ≥ 6GB VRAM (tối ưu cho RTX 3060/4060/5060); có fallback CPU
- Microsoft C++ Build Tools + Git for Windows

## Ghi chú về submodule

`AIVoice` và `toolCaoTruyen` là hai repo Git độc lập, phát triển và push riêng. Repo tổng chỉ lưu **con trỏ tới một commit cụ thể** của mỗi submodule. Khi cập nhật code trong một submodule:

```bash
cd AIVoice
git add -A && git commit -m "..." && git push      # push repo con
cd ..
git add AIVoice && git commit -m "Cap nhat submodule AIVoice"   # cập nhật con trỏ ở repo tổng
```
