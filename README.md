# ToolAutoMakeCartoonVideo2DFromComics

[![CI](https://github.com/Duyycoder/ToolAutoMakeCartoonVideo2DFromComics/actions/workflows/ci.yml/badge.svg)](https://github.com/Duyycoder/ToolAutoMakeCartoonVideo2DFromComics/actions/workflows/ci.yml)

Hệ thống tự động chuyển **truyện chữ → video hoạt hình 2D có lồng tiếng**, chạy cục bộ trên máy cá nhân (Windows + GPU NVIDIA). Đây là repo tổng (đồ án tốt nghiệp), điều phối hai dự án con qua kiến trúc **orchestrator + subprocess**.

## Kiến trúc tổng quan

Hệ thống gồm 3 tầng, giao tiếp với nhau qua tiến trình con (subprocess) và giao thức tiến độ JSON trên stdout — mỗi bước nặng chạy trong một tiến trình riêng để **tự giải phóng VRAM khi kết thúc**.

```
ToolAutoMakeCartoonVideo2DFromComics/   (repo tổng)
├── orchestrator/     # FastAPI :8100 — điều phối pipeline, máy trạng thái, quản lý tiến trình
│                     # (dùng chung AIVoice/.venv, KHÔNG import torch; các bước AI nặng chạy subprocess và tự nhả VRAM)
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

> 🟢 **Không rành kỹ thuật?** Đọc [HUONG-DAN-KHOI-DONG.md](HUONG-DAN-KHOI-DONG.md) — 3 bước, không cần biết code.

**Cách nhanh nhất:** nháy đúp `run.bat`. Máy chưa cài gì thì nó tự gọi `setup.bat` rồi mở app luôn.

Chi tiết từng bước nếu muốn kiểm soát:

1. Chạy `setup.bat` — tạo venv tổng + gọi setup của 2 dự án con (tự nhận GPU, tải model) và tự sinh `configs/global_config.json` nếu chưa có. API key điền sau ngay trong giao diện (mục **Cấu Hình Chung**); `global_config.json` đã bị `.gitignore` loại trừ nên không bao giờ commit key thật.
2. Chạy `run.bat` — mở **cửa sổ ứng dụng desktop** (WebView2 qua pywebview), bên trong tự khởi động orchestrator :8100 và Gemini-API proxy **chạy ẩn, không hiện console**; log ghi vào `logs/app.log` và `logs/gemini_api.log`. Đóng cửa sổ app sẽ tự tắt sạch mọi tiến trình con. Cần xem log trực tiếp thì chạy `run.bat debug`; máy thiếu pywebview/WebView2 sẽ tự fallback mở trình duyệt.

## Chế độ trình diễn "sạch bản quyền" (khuyến nghị cho đồ án)

Toàn bộ pipeline có thể chạy **hoàn toàn cục bộ, không dùng dịch vụ trả phí và không cào nội dung có bản quyền**. Đây là cấu hình mặc định trong `config.example.json`:

| Bước | Lựa chọn "sạch" | Ghi chú |
|------|-----------------|---------|
| 1. Nguồn truyện | **Thư mục cục bộ** (`Nguồn truyện → Local Folder`) | Dùng truyện tự sáng tác hoặc tác phẩm thuộc phạm vi công cộng (public domain) dưới dạng `.md`/`.txt` — không cào web |
| 1. Dịch thuật | **Gemini Local** (engine `gemini_api`) qua proxy [Gemini-API](toolCaoTruyen/Gemini-API) tại `localhost:7860`, hoặc **Ollama** | Chạy trên máy, không cần API key trả phí |
| 2. TTS | **Kokoro-Vietnamese / VieNeu / Piper** (offline, GPU/CPU local) | Edge-TTS là tùy chọn online miễn phí |
| 3. LLM phân cảnh & prompt | **Gemini Local** (mặc định) hoặc **Ollama** — chọn ngay trên form Bước 3 | Cùng proxy `localhost:7860` như Bước 1 |
| 3. Sinh ảnh | **Stable Diffusion local** (checkpoint mã nguồn mở, vd. Anything V5) | Chạy trên GPU cá nhân |

> Khi viết báo cáo: nhấn mạnh chuỗi xử lý trên để chứng minh hệ thống không phụ thuộc dịch vụ thương mại và không phân phối nội dung có bản quyền.

## Đóng gói bộ cài `setup.exe` (Inno Setup)

Thư mục [installer/](installer/) chứa script đóng gói ứng dụng thành bộ cài Windows:

```bash
installer\build_installer.bat   # cần Inno Setup 6 (winget install -e --id JRSoftware.InnoSetup)
```

- Kết quả: `installer/Output/AutoCartoonVideoMaker-Setup-<version>.exe` (~150 MB, chỉ chứa **mã nguồn** + tài nguyên đi kèm repo — không chứa venv/model/bí mật).
- Máy đích **không cần cài sẵn Python hay Git**: bộ cài chép mã nguồn vào `%LocalAppData%\Programs\AutoCartoonVideoMaker`, tạo sẵn `global_config.json` từ file mẫu, tạo shortcut Desktop/Start Menu, rồi chạy `setup.bat` (tự tải Python 3.11 + thư viện + model AI — cần Internet, 30–60 phút).
- Gỡ cài đặt xóa toàn bộ trừ thư mục `storage/` (truyện & video người dùng đã tạo).

## Kiểm thử & CI/CD

- **Unit tests** (`tests/`): kiểm tra logic resolve engine LLM Bước 3 (Gemini local/online, Ollama, validation thiếu API key) và fallback cấu hình TTS Bước 2 — chạy bằng `pip install pytest && pytest -v`, không cần GPU/model.
- **CI** ([.github/workflows/ci.yml](.github/workflows/ci.yml)): tự chạy trên mỗi push/PR vào `main` — lint lỗi nghiêm trọng (ruff), kiểm tra biên dịch toàn bộ `orchestrator/`, chạy unit tests.
- **CD** ([.github/workflows/release.yml](.github/workflows/release.yml)): gắn tag `v*` (vd `git tag v1.0.0 && git push origin v1.0.0`) sẽ tự đóng gói mã nguồn và tạo GitHub Release kèm release notes.
- Mỗi submodule (`AIVoice`, `toolCaoTruyen`) có workflow CI riêng kiểm tra cú pháp Python độc lập.

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
