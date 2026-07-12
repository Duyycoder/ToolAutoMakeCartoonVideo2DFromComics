# PLAN — Đưa Autosub + Ghép Video + Tải Video + Trích Sub lên WebUI

> **Nhánh:** `dev/feat-media-workflows` (đã tách từ `dev/glossary-model-select` — nhánh chứa webUI mới nhất).
> **Người thực thi:** một agent khác. Đọc HẾT phần "Hiện trạng đã xác minh" trước khi code. Mọi số dòng dưới đây đã được kiểm chứng tại thời điểm viết (2026-07-12).
>
> ## Quy tắc chung cho agent (BẮT BUỘC)
> - Làm tuần tự theo **Task A → F**. Mỗi task xong thì `python -m py_compile` file đã sửa; task nào đụng orchestrator thì chạy `pytest -q` ở repo tổng.
> - **KHÔNG** sửa `.github/workflows/*` (PAT thiếu scope `workflow`, push sẽ bị từ chối).
> - **KHÔNG** commit `AIVoice/apps/MediaComposer/config.toml` (đã gitignore, runtime tự ghi đè).
> - Code trong `AIVoice/` và `toolCaoTruyen/` là **submodule** → commit trong submodule trước, rồi commit con trỏ ở repo tổng (xem README mục "Ghi chú về submodule"). Task A/B/C nằm trong submodule `AIVoice`; Task D/E/F nằm ở repo tổng.
> - Giữ nguyên phong cách log JSON của adapter CLI (`print(json.dumps({...}, ensure_ascii=False))` mỗi dòng) để orchestrator stream qua SSE.
> - Toàn bộ tiến trình nặng (whisper/tts/ffmpeg/yt-dlp) chạy trong **`AIVoice/.venv`** (cwd=`AIVoice`), KHÔNG chạy trong venv orchestrator (venv này cố ý không có torch).
>
> ## Gợi ý commit (đặt tên theo Conventional Commits)
> - `feat(mediacomposer): add adapter_autosub_cli for translate-and-sub workflow` (Task A)
> - `feat(mediacomposer): add yt-dlp video downloader (tiktok/douyin/generic)` (Task B)
> - `feat(mediacomposer): add subtitle extraction (embedded + OCR) options` (Task C)
> - `feat(orchestrator): add step4 autosub + step5 merge pipeline & endpoints` (Task D, E)
> - `feat(webui): add Bước 4 Autosub & Bước 5 Ghép Video tabs` (Task F)
> - `chore: bump AIVoice submodule pointer for media workflows` (cập nhật con trỏ submodule)

---

## 0. Bối cảnh & ánh xạ yêu cầu → công việc

Hệ thống hiện có 3 bước trên webUI (`webui/index.html` nav tabs `step1/step2/step3/settings`). Orchestrator FastAPI (`orchestrator/main.py`, cổng 8100) điều phối bằng cách spawn **adapter CLI** trong submodule qua `ProcessManager`, rồi stream stdout (JSON log) về UI bằng **SSE**.

MediaComposer (Streamlit app trong `AIVoice/apps/MediaComposer`) **đã có sẵn** các workflow ta cần, nhưng chúng chỉ chạy trong Streamlit (`webui/Main.py`), CHƯA có adapter CLI để orchestrator gọi. Việc chính là: **viết adapter CLI + endpoint + tab UI** để "thông" các workflow này lên giao diện chính — KHÔNG viết lại logic xử lý video.

| Yêu cầu người dùng | Workflow có sẵn trong MediaComposer | Việc cần làm |
|---|---|---|
| **(1) Subvideo tự động / Autosub** (có lồng tiếng tuỳ chọn) | `composer.run_translation_workflow()` (`app/services/composer.py:272`) = "Workflow 4: Auto Translate & Sub" trong Streamlit (`webui/Main.py:2581`) | Task A (adapter CLI) + Task D (step4) + Task F (tab UI) |
| **(1b) Nguồn video: tải từ TikTok / "glibli" Trung Quốc** | *(chưa có)* — chỉ có local path / upload | Task B (yt-dlp downloader) |
| **(2) Tạo SRT: thêm option tách sub bên trong video + dịch** | Whisper transcribe (`app/services/subtitle.py`) đã làm SRT-từ-âm-thanh; tách sub *có sẵn trong khung hình* thì CHƯA có | Task C (embedded + OCR), tích hợp vào Task A |
| **(3) Ghép các video đã tạo mà chưa từng ghép thành 1 video** | `orchestrator/video_merger.py:merge_videos()` (concat stream-copy) + `combine_videos()` (`app/services/video.py:538`) | Task E (step5 merge) + Task F (tab UI) |

> **CÂU HỎI MỞ (cần hỏi lại chủ dự án trước/khi làm Task B):** "glibli Trung Quốc" là nền tảng nào? Nhiều khả năng là **Douyin** (TikTok Trung Quốc) hoặc **Bilibili**, hoặc một site tạo video kiểu Ghibli. `yt-dlp` hỗ trợ TikTok/Douyin/Bilibili sẵn. Task B dưới đây thiết kế downloader **generic dựa trên yt-dlp** để không phụ thuộc câu trả lời, nhưng dropdown "nền tảng" nên chốt danh sách đúng theo xác nhận của chủ dự án.

---

## Hiện trạng đã xác minh (đọc kỹ — nhiều điểm dễ hiểu sai)

### Orchestrator
- `orchestrator/main.py`: FastAPI, mount `webui/` static ở `/` (dòng 294-296). Endpoint pipeline: `POST /api/pipeline/step1|step2|step3`, `POST /api/pipeline/stop?story_name=&step=`, SSE `GET /api/pipeline/logs/{task_key}`. Có sẵn `GET /api/config`, `GET /api/stories`, `GET /api/ollama/models`, `GET /api/system/gpu-info`.
- `orchestrator/pipeline.py`: class `NovelPipeline`. Mỗi `start_step_N(...)` dựng `cmd` (list) rồi gọi `self.process_mgr.start_process(task_key, cmd, cwd, env_override, on_completed)`. Step3 (dòng 259-392) là mẫu tốt nhất để copy: nó gọi adapter `AIVoice/apps/MediaComposer/adapter_video_cli.py` với `cwd="AIVoice"`, và trong `on_video_completed` còn tự gọi `merge_videos()` sau khi sinh video xong.
- `orchestrator/process_manager.py`: `start_process` trả `False` nếu `task_key` đã chạy. `is_running(task_key)`. Log đọc theo dòng, đẩy vào `queue.Queue`, SSE lấy ra ở `get_logs_generator`. **task_key quy ước `{slug}_step{N}`**.
- `orchestrator/storage.py`: `slugify()`; `StorageManager` quản lý `storage/truyen/<slug>/` (có subdir `raw/`, `video/`) + `storage/tasks/`. Video chương nằm ở `storage/truyen/<slug>/video/*.mp4`, file ghép cuối tên `TongHop_<timestamp>.mp4`.
- `orchestrator/video_merger.py:merge_videos(video_dir, output_file)`: ffmpeg **concat stream-copy** (`-c copy`, cực nhanh, không re-encode) mọi `*.mp4` trong `video_dir` TRỪ file bắt đầu bằng `TongHop_`. Đây chính là "ghép video chưa từng ghép" ở cấp thư mục — Task E sẽ tái sử dụng, mở rộng cho phép chọn danh sách file cụ thể.

### Adapter CLI pattern (mẫu để copy — Task A/B/C bám theo)
- `AIVoice/apps/MediaComposer/adapter_video_cli.py`: parse argparse → chạy workflow → `log_json(event, data)` in mỗi dòng JSON ra stdout → `sys.exit(0/1)`. Set `KMP_DUPLICATE_LIB_OK=TRUE` đầu file. `finally:` giải phóng VRAM (`torch.cuda.empty_cache()` + `gc.collect()`). **Bắt buộc theo khuôn này** để không leak VRAM và để orchestrator biết tiến độ.
- Chạy trong `cwd="AIVoice"` → adapter tự `sys.path.insert` `mc_root` và `mc_root/app`. Import `from orchestrator.storage import slugify` hoạt động vì `cwd=AIVoice` KHÔNG có package orchestrator... **CẢNH BÁO:** `adapter_video_cli.py:74` import `from orchestrator.storage import slugify` — cái này chỉ chạy được vì `PYTHONPATH`/sys.path của tiến trình con kế thừa. Kiểm tra lại: nếu adapter mới cần `slugify`, **tự copy một hàm slug tối giản** thay vì phụ thuộc import chéo repo (an toàn hơn).

### MediaComposer — composer.py (`app/services/composer.py`)
- `run_translation_workflow(task_id, video_path, source_lang, burn_method="ffmpeg", enable_voiceover=False, tts_engine="edge", tts_voice="", ducking_ratio=90.0, auto_clone=False, clean_audio=False) -> str` (dòng 272-452). Trả về đường dẫn `translated_video.mp4` trong task_dir của MC. Luồng: extract audio (ffmpeg → wav mono 16k) → (tuỳ chọn Demucs tách giọng nếu `clean_audio`) → Whisper transcribe theo `source_lang` (`en`/`zh`) → `release_whisper_model()` → `translate_srt()` (Gemini) → (tuỳ chọn) `generate_dubbed_audio()` lồng tiếng + ducking → burn phụ đề (ffmpeg filter hoặc moviepy).
- `run_workflow(...)` (dòng 27): workflow compose stock-video (không cần cho yêu cầu này).
- `split_video_into_parts(...)` (dòng 244): chẻ video (không cần).
- **Đầu ra rơi vào `AIVoice/apps/MediaComposer/storage/tasks/<task_id>/`** (`app/utils/utils.py:task_dir` → `root_dir()/storage/tasks`). `MC_STORAGE_TASKS` env KHÔNG được `utils.task_dir` đọc (chỉ storytelling context dùng env riêng) → adapter phải TỰ copy file kết quả sang thư mục output người dùng chỉ định.

### MediaComposer — các service phụ trợ
- `app/services/subtitle.py`: `create_subtitle(audio_file, subtitle_file, language=None)` dùng **faster-whisper** (model size/device lấy từ `config.whisper` trong `config.toml`). `release_whisper_model()` giải phóng VRAM. `read_srt_text()`, `create_subtitle_from_text()`.
- `app/services/translation.py`: `translate_srt(srt_path, output_path, source_lang, target_lang="Vietnamese")` (dịch Gemini); `parse_srt()`, `build_srt()` — **tái dùng cho Task C** (dựng SRT từ text OCR).
- `app/services/dubbing.py:generate_dubbed_audio(...)`: import `from src.engines.{edge,piper,kokoro,vieneu,clone} import ...` → **phải chạy trong `AIVoice/.venv`** (project_root = AIVoice). Engine hỗ trợ: `edge|piper|kokoro|vieneu|clone`.
- `app/services/video.py`: `burn_subtitles_ffmpeg(video, srt, out, audio_path)`, `combine_videos(...)`, `generate_video(...)`.
- `config.py`: đọc `config.toml`, có `config.whisper` (model_size, device, compute_type, font_name...), `config.app` (llm_api_key/base_url/model — dùng cho `translate_srt` gọi Gemini). Adapter cần set các key này (in-memory hoặc `save_config()`).

### Tham số UI Workflow 4 (Streamlit — `webui/Main.py:2581-2799`) — dùng làm chuẩn cho tab step4
`source_lang` ∈ {English, Chinese}; `burn_method` ∈ {ffmpeg, moviepy}; `clean_audio` (Demucs) bool; `enable_voiceover` bool; nếu bật: `tts_engine` ∈ {edge, piper, kokoro, vieneu, clone}, `tts_voice` (tuỳ engine), `auto_clone` bool (engine clone), `ducking_ratio` 0-100 (mặc định 90). Danh sách voice cụ thể xem Main.py:2640-2706.

### WebUI (`webui/`)
- `index.html`: sidebar `.nav-menu` với `<button class="nav-item" data-tab="stepN">`; nội dung `<section class="tab-panel" id="tab-stepN">` gồm form + `.log-panel` console. Tab settings ở cuối.
- `app.js`: `initTabs()` (dòng 52) gắn click chuyển tab theo `data-tab`; `postPipelineAction(stepName, payload)` (dòng 564) POST `/api/pipeline/${stepName}`; `streamLogs(stepName, taskKey)` (dòng 639) mở `EventSource` `/api/pipeline/logs/{taskKey}`; `toggleFormButtons`, `clearConsole`, `appendConsoleLog`; `setupEventHandlers()` (dòng 145) gắn nút mỗi bước. `activeStoryName` là truyện đang chọn.
- Autosub/tải-video/ghép là **tác vụ độc lập, KHÔNG bắt buộc gắn với 1 truyện**. Cần quyết định task_key cho tác vụ không-thuộc-truyện: dùng prefix cố định, ví dụ `autosub_<uuid8>_step4`, `merge_<slug>_step5`. Xem Task D/E.

---

## Task A — Adapter CLI cho Autosub (`adapter_autosub_cli.py`)

**File mới:** `AIVoice/apps/MediaComposer/adapter_autosub_cli.py` (copy khung từ `adapter_video_cli.py`).

**Mục tiêu:** wrap `composer.run_translation_workflow(...)` thành CLI để orchestrator gọi.

**Argparse (khớp tham số Streamlit + mở rộng cho Task B/C):**
```
--video-path        (str)  đường dẫn video local (BẮT BUỘC nếu không có --download-url)
--download-url      (str)  link video để tải (Task B) — nếu có, tải trước rồi dùng làm --video-path
--platform          (str)  tiktok|douyin|bilibili|generic (Task B)
--output-dir        (str)  thư mục lưu kết quả cuối (BẮT BUỘC)
--source-lang       (str)  English|Chinese (mặc định English)
--sub-source        (str)  whisper|embedded|ocr   (Task C — mặc định whisper)
--burn-method       (str)  ffmpeg|moviepy (mặc định ffmpeg)
--clean-audio       (flag, default False) Demucs tách giọng trước whisper
--enable-voiceover  (flag, default False)
--tts-engine        (str)  edge|piper|kokoro|vieneu|clone (mặc định edge)
--tts-voice         (str)
--auto-clone        (flag, default False)
--ducking-ratio     (float, default 90.0)
```

**Thân hàm (thứ tự):**
1. `os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"`; set sys.path như adapter_video_cli (dòng 11-13).
2. `log_json("autosub_init", {...})`.
3. Nếu `--download-url`: gọi downloader Task B → nhận `video_path` local; `log_json("download_done", {"path":...})`. Ngược lại dùng `--video-path` (kiểm tra tồn tại, raise nếu không).
4. `task_id = uuid4().hex`; tạo MC task_dir qua `from app.utils import utils; utils.task_dir(task_id)`.
5. **Nếu `--sub-source != whisper`** (Task C): tự trích SRT nguồn (embedded/OCR) rồi dịch, KHÔNG dùng whisper. Vì `run_translation_workflow` hard-code whisper, cần một trong hai hướng (chọn hướng (a) để ít sửa nhất):
   - **(a) khuyến nghị:** thêm tham số mới `source_srt_override: str = ""` vào `run_translation_workflow` (composer.py). Nếu có, BỎ QUA bước extract audio + whisper, dùng thẳng SRT này làm `source_srt_path`. Adapter tự sinh SRT (Task C) rồi truyền vào. Sửa tối thiểu ~10 dòng trong composer.py (đầu hàm, mục 1-2).
   - (b) không khuyến nghị: viết workflow song song riêng trong adapter.
6. Gọi `composer.run_translation_workflow(task_id=task_id, video_path=..., source_lang=..., burn_method=..., enable_voiceover=..., tts_engine=..., tts_voice=..., ducking_ratio=..., auto_clone=..., clean_audio=..., source_srt_override=...)`.
7. Copy file kết quả sang `--output-dir` với tên `<basename>_autosub_<timestamp>.mp4`; `log_json("autosub_done", {"output": <đường dẫn cuối>})`.
8. `except`: `log_json("autosub_error", {"error": str(e)})`, `sys.exit(1)`.
9. `finally`: giải phóng VRAM giống adapter_video_cli (`release_whisper_model()` + torch empty_cache + gc).

**Bẫy:**
- `run_translation_workflow` gọi Gemini để dịch → adapter phải nạp `config.app["llm_api_key"/"llm_base_url"/"llm_model"]` (giống `adapter_video_cli.py:57-62`). Nhận các giá trị này qua thêm arg `--llm-api-key/--llm-base-url/--llm-model` và orchestrator truyền vào (Task D resolve giống step3 pipeline.py:283-302).
- `tts_voice` với vieneu là dạng `"Tên|mode"` (Main.py:2686). Adapter chỉ truyền chuỗi thô, không parse.
- Whisper `language`: workflow tự map English→en, Chinese→zh (composer.py:334-339). Không cần map ở adapter.

**Nghiệm thu Task A:** Chạy tay trong `AIVoice/.venv`:
```
cd AIVoice && .venv/Scripts/python.exe apps/MediaComposer/adapter_autosub_cli.py \
  --video-path <mp4 tiếng Anh ngắn> --output-dir <tmp> --source-lang English --llm-api-key ... --llm-base-url http://localhost:7860/v1 --llm-model gemini-3-flash
```
→ ra `*_autosub_*.mp4` có phụ đề tiếng Việt; stdout là các dòng JSON hợp lệ.

---

## Task B — Tải video từ TikTok / Douyin / "glibli" (yt-dlp)

**File mới:** `AIVoice/apps/MediaComposer/app/services/video_downloader.py`.

**Phụ thuộc:** thêm `yt-dlp` vào `AIVoice/apps/MediaComposer/requirements.txt` và cài vào `AIVoice/.venv` (`.venv/Scripts/pip install yt-dlp`). yt-dlp gọi ffmpeg — đã có `imageio_ffmpeg` (`utils.get_ffmpeg_binary()`), truyền qua `ffmpeg_location`.

**API:**
```python
def download_video(url: str, output_dir: str, platform: str = "generic",
                   progress_cb=None) -> str:
    """Tải 1 video về output_dir, trả về đường dẫn file mp4. Raise nếu lỗi."""
```
Dùng `yt_dlp.YoutubeDL` với opts: `format="mp4/best"`, `outtmpl=<output_dir>/dl_%(id)s.%(ext)s`, `merge_output_format="mp4"`, `ffmpeg_location=<thư mục chứa ffmpeg>`, `noplaylist=True`, `quiet=True`, và `progress_hooks=[hook]` để phát `log_json("download_progress", {...})`. Trả `ydl.prepare_filename(info)` (đổi ext thành `.mp4`).

**`platform`** hiện chỉ là nhãn (yt-dlp tự nhận extractor theo URL). Giữ tham số để: (1) validate domain hợp lệ, (2) tương lai gắn cookies/headers riêng cho site cần đăng nhập (vd Bilibili/Douyin có thể chặn). Với site "glibli" chưa xác định: nếu là trang có link video trực tiếp, thêm nhánh fallback tải bằng `requests` stream (giống `app/services/material.py:save_video` dòng 244 — có sẵn mẫu tải file trực tiếp).

**Tích hợp:** Task A gọi `download_video()` khi có `--download-url`. Không tạo endpoint tải riêng — tải là bước con của autosub (đúng ý người dùng: "paste link + chọn nền tảng" ngay trong luồng tạo phụ đề). Nếu sau này cần tải-độc-lập cho Bước 3, tách endpoint riêng.

**Bẫy:**
- yt-dlp có thể trả nhiều định dạng; ép `format="mp4/best"` + `merge_output_format` để ra 1 file mp4 chuẩn cho ffmpeg/whisper.
- TikTok có watermark; muốn bản không watermark cần format phù hợp — để mặc định, KHÔNG cố né watermark (ngoài phạm vi).
- **Pháp lý/robots:** chỉ tải nội dung người dùng có quyền. Không thêm cơ chế bypass đăng nhập/c`captcha`.
- Bilibili/Douyin đôi khi cần `cookiesfrombrowser` — KHÔNG bật mặc định; nếu lỗi 403, log rõ và hướng dẫn người dùng, đừng tự lấy cookie trình duyệt.

**Nghiệm thu Task B:** `download_video("<link tiktok công khai>", <tmp>, "tiktok")` trả về file mp4 phát được.

---

## Task C — Option "tách sub bên trong video" + dịch (nghiên cứu model + phương án)

Người dùng muốn thêm lựa chọn lấy **phụ đề có sẵn TRONG video** thay vì phiên âm từ âm thanh (whisper). Có 2 loại "sub bên trong":

### Phương án C1 — Phụ đề mềm (soft/embedded subtitle stream)  ✅ làm trước, rẻ
Nhiều video (mkv, một số mp4) chứa track phụ đề (`mov_text`, `subrip`, `ass`). Trích bằng ffmpeg, **0 chi phí AI, rất nhanh, chính xác 100%**.
- Dò: `ffprobe -v quiet -print_format json -show_streams <video>` → tìm stream `codec_type=="subtitle"`.
- Trích: `ffmpeg -y -i <video> -map 0:s:0 <out>.srt` (nếu là ass thì `-map 0:s:0 out.ass` rồi convert `ffmpeg -i out.ass out.srt`).
- Nếu KHÔNG có subtitle stream → báo và fallback sang C2 (nếu người dùng chọn OCR) hoặc whisper.

### Phương án C2 — Phụ đề cháy (hardcoded/burned-in) → OCR khung hình  ⚠️ nặng hơn
Video TikTok/Douyin thường **cháy chữ vào hình** → phải OCR. Đây là phần "tìm hiểu model" người dùng yêu cầu. **Các lựa chọn model (khuyến nghị theo thứ tự):**

| Lựa chọn | Model | Ưu | Nhược |
|---|---|---|---|
| **C2a (khuyến nghị)** | **RapidOCR** (onnxruntime, PP-OCRv4 weights) | Nhẹ, chỉ cần `onnxruntime`, hỗ trợ Trung+Anh, không kéo theo paddlepaddle nặng; hợp với `.venv` sẵn có torch/cuda | Cần tự viết vòng lặp sample frame + dedupe |
| C2b | **PaddleOCR** (`ch_PP-OCRv4`, `en_PP-OCRv4`) | Chính xác cao, cộng đồng lớn | Kéo `paddlepaddle`(-gpu) nặng, hay xung đột CUDA với torch trong cùng venv |
| C2c | **VideoSubFinder + OCR** | VideoSubFinder tự dò vùng phụ đề + mốc thời gian rất tốt (chuyên cho hardsub) | Là app ngoài (GUI/CLI Windows), khó tự động hoá trong subprocess |
| C2d | **Whisper (giữ mặc định)** | Đã có sẵn, không cần OCR | Không đọc chữ trên hình, chỉ nghe tiếng — KHÔNG đáp ứng "tách sub bên trong" |

**Khuyến nghị:** làm **C1 + C2a (RapidOCR)**. Bỏ C2b/C2c ở giai đoạn này (ghi vào "mở rộng tương lai").

**File mới:** `AIVoice/apps/MediaComposer/app/services/subtitle_extractor.py`
```python
def extract_embedded_srt(video_path: str, output_srt: str) -> str | None:
    """C1: dò & trích subtitle stream bằng ffprobe/ffmpeg. None nếu không có."""

def extract_hardsub_ocr_srt(video_path: str, output_srt: str,
                            lang: str = "ch", sample_fps: float = 2.0,
                            roi=("bottom", 0.75, 1.0), progress_cb=None) -> str:
    """C2a: sample frame (sample_fps khung/giây), crop vùng phụ đề (ROI đáy màn),
    RapidOCR đọc chữ, gộp khung liên tiếp cùng nội dung thành 1 câu + mốc thời gian,
    build SRT bằng app.services.translation.build_srt()."""
```
Chi tiết C2a:
- Lấy fps & duration bằng ffprobe; đọc frame bằng `cv2.VideoCapture` (opencv đã có trong MC — kiểm tra; nếu không, dùng `imageio_ffmpeg`/`ffmpeg -vf fps=` xuất PNG tạm).
- Với mỗi frame lấy mẫu: crop ROI (mặc định 25% đáy — nơi phụ đề thường nằm), `rapidocr(frame_crop)` → text.
- **Dedupe:** nếu text trùng frame trước (so sánh sau khi chuẩn hoá khoảng trắng, hoặc similarity ≥ 0.85) → kéo dài `end_time` của segment hiện tại; khác → chốt segment cũ, mở segment mới. Bỏ text rỗng/nhiễu (độ dài < 2 ký tự).
- Xuất list `[{index,start,end,text}]` → `build_srt()` → ghi `output_srt`. Trả path.

**Tích hợp:** trong adapter Task A, khi `--sub-source`:
- `whisper` → hành vi hiện tại (không đụng).
- `embedded` → `extract_embedded_srt()`; nếu None → log cảnh báo, fallback whisper.
- `ocr` → `extract_hardsub_ocr_srt(lang="ch" if source_lang=="Chinese" else "en")`.
- SRT thu được truyền vào `run_translation_workflow(..., source_srt_override=<srt>)` (đã thêm ở Task A mục 5a) → workflow bỏ qua whisper, chỉ dịch + (lồng tiếng) + burn.

**Phụ thuộc:** thêm `rapidocr-onnxruntime` (và `opencv-python-headless` nếu MC chưa có) vào `requirements.txt` + cài vào `.venv`. **Bẫy CUDA:** RapidOCR mặc định chạy CPU (ổn); nếu bật GPU phải đảm bảo onnxruntime-gpu không đụng CUDA của torch — để CPU cho an toàn.

**Nghiệm thu Task C:** (C1) video mkv có sub → ra `.srt` đúng lời. (C2a) video hardsub tiếng Trung ngắn → ra `.srt` có mốc thời gian hợp lý, dịch được sang tiếng Việt.

---

## Task D — Orchestrator: pipeline + endpoint cho Bước 4 (Autosub)

### D1. `orchestrator/pipeline.py` — thêm method `start_step_4_autosub(self, task_id_or_story, autosub_args) -> bool`
Bám mẫu `start_step_3_video` (dòng 259-392):
- Resolve LLM giống step3 (dòng 283-302): từ `autosub_args["llm_engine"]` → `resolved_key/base_url/model`. Autosub cần Gemini để dịch SRT.
- `python_exe = AIVoice/.venv/Scripts/python.exe`; `adapter = AIVoice/apps/MediaComposer/adapter_autosub_cli.py`.
- Dựng `cmd` với các arg Task A (chỉ thêm arg khi giá trị có mặt, giống step3 các `if ...: cmd.append(...)`).
- `output_dir`: nếu tác vụ gắn truyện thì `storage/truyen/<slug>/video/`; nếu độc lập thì `storage/tasks/autosub_<id>/` (tạo qua `os.makedirs`).
- `task_key = f"autosub_{id}_step4"` (id = slug truyện hoặc uuid8). `env_override` cho device giống step3 (dòng 348-352).
- `on_completed`: cập nhật meta nếu gắn truyện; đóng queue. KHÔNG tự merge (khác step3).
- `start_process(task_key, cmd, cwd="AIVoice", env_override, on_completed)`.

### D2. `orchestrator/main.py` — schema + endpoint
- Thêm `class Step4Schema(BaseModel)`: `story_name: Optional[str]=None`, `video_path: Optional[str]=None`, `download_url: Optional[str]=None`, `platform: Optional[str]="generic"`, `source_lang="English"`, `sub_source="whisper"`, `burn_method="ffmpeg"`, `clean_audio=False`, `enable_voiceover=False`, `tts_engine="edge"`, `tts_voice=""`, `auto_clone=False`, `ducking_ratio=90.0`, `device="cuda"`, `llm_engine="gemini_api"`, `llm_api_key/llm_offline_base_url/llm_offline_model: Optional`.
- `POST /api/pipeline/step4`: validate (phải có `video_path` HOẶC `download_url`); chặn nếu `is_running(task_key)`; gọi `pipeline.start_step_4_autosub(...)`. Trả `{"status":"success","task_key":...}` (UI cần task_key để mở SSE).
- Endpoint `stop` hiện tại (`/api/pipeline/stop`) dùng `f"{slug}_step{step}"` → KHÔNG khớp task_key autosub độc lập. **Sửa** `stop_pipeline` nhận thêm dạng task_key tự do, hoặc thêm `POST /api/pipeline/stop-task?task_key=` tổng quát. Khuyến nghị thêm endpoint mới gọn hơn.

**Bẫy:** `StaticFiles` mount ở `/` (main.py:296) nuốt mọi route KHÔNG khớp → route API phải khai báo TRƯỚC dòng mount (đã đúng vì mount ở cuối file — giữ nguyên thứ tự, thêm endpoint mới phía trên dòng 294).

**Nghiệm thu Task D:** `curl -XPOST localhost:8100/api/pipeline/step4 -d '{...}'` trả task_key; SSE `/api/pipeline/logs/<task_key>` chảy log JSON tới khi "autosub_done".

---

## Task E — Orchestrator: Bước 5 "Ghép video chưa từng ghép"

**Ý nghĩa "chưa từng ghép":** trong `storage/truyen/<slug>/video/` có nhiều `*.mp4` chương; file tổng hợp là `TongHop_*.mp4`. "Ghép các video vừa tạo mà chưa từng ghép" = gộp các mp4 chương (bỏ qua `TongHop_*`) thành 1 file. `video_merger.merge_videos()` ĐÃ làm đúng việc này (concat stream-copy, loại `TongHop_`).

### E1. Endpoint liệt kê video để người dùng chọn
- `GET /api/stories/{story_name}/videos` → trả danh sách `{name, size, is_merged}` các mp4 trong `video/` (đánh dấu `is_merged=True` nếu tên bắt đầu `TongHop_`). Cho UI hiển thị checklist.

### E2. Pipeline + endpoint ghép
- `orchestrator/pipeline.py`: `start_step_5_merge(self, story_name, selected_files: list[str] | None) -> bool`. Nếu `selected_files` None → ghép toàn bộ (dùng thẳng `merge_videos(video_dir, out)`); nếu có danh sách → tạo bản `merge_videos` biến thể nhận list file cụ thể (refactor: tách phần build concat_list ra nhận `mp4_files` truyền vào). Chạy **trong luồng nền** + đẩy log vào queue `task_key=f"{slug}_step5"` để SSE hoạt động (merge nhanh nhưng vẫn cần progress; có thể chạy `threading.Thread` như nhánh local-copy ở pipeline.py:137-151, tự `put` log + `put(None)` khi xong).
  - Output: `TongHop_<timestamp>.mp4` trong `video/`.
- `orchestrator/main.py`: `class Step5Schema(story_name, selected_files: Optional[list[str]]=None)`; `POST /api/pipeline/step5`.

**Bẫy:**
- concat stream-copy (`-c copy`) chỉ hoạt động nếu **mọi mp4 cùng codec/độ phân giải/fps**. Video từ step3 (cùng pipeline) thì đồng nhất → OK. Nhưng nếu người dùng trộn video autosub (đủ loại nguồn) → stream-copy có thể lỗi/hỏng. **Giải pháp:** thử `-c copy` trước; nếu ffmpeg exit != 0 → fallback re-encode bằng `combine_videos()` của MediaComposer (chạy qua adapter trong AIVoice/.venv) HOẶC ffmpeg re-encode đơn giản `-c:v libx264 -c:a aac`. Ghi rõ fallback trong log.
- `merge_videos` hiện `import imageio_ffmpeg` từ path AIVoice/.venv site-packages (video_merger.py:11) — giữ nguyên, đã hoạt động ở step3.

**Nghiệm thu Task E:** chọn ≥2 video chương → ra `TongHop_*.mp4` phát liền mạch; log SSE báo tiến độ + hoàn tất.

---

## Task F — WebUI: 2 tab mới (Bước 4 Autosub, Bước 5 Ghép Video)

### F1. `webui/index.html`
- Thêm 2 `<button class="nav-item" data-tab="step4">` và `data-tab="step5"` trong `.nav-menu` (sau step3, trước settings). Icon gợi ý: 🎬 (Bước 4 Phụ đề & Lồng tiếng), 🔗 (Bước 5 Ghép video).
- Thêm 2 `<section class="tab-panel" id="tab-step4">` và `id="tab-step5">` (copy khung 1 panel step3: form bên trái + `.log-panel` console bên phải).
- **Form Bước 4** (khớp Step4Schema):
  - Nhóm "Nguồn video" — radio 3 lựa chọn: `Upload` / `Đường dẫn cục bộ` / `Tải từ link`. Chọn "Tải từ link" → hiện input URL + dropdown nền tảng (`TikTok/Douyin/Bilibili/Khác`). *(Lưu ý: upload file cần endpoint nhận multipart — HIỆN orchestrator CHƯA có; xem Bẫy bên dưới.)*
  - Dropdown `source_lang` (English/Chinese).
  - Dropdown `sub_source` (**Phiên âm từ âm thanh — Whisper** / **Trích phụ đề có sẵn (mềm)** / **OCR chữ cháy trên hình**).
  - Dropdown `burn_method` (FFmpeg/MoviePy). Checkbox `clean_audio`.
  - Checkbox `enable_voiceover` → khi bật hiện dropdown `tts_engine` + ô voice (đổi theo engine, mô phỏng Main.py:2640-2706) + slider `ducking_ratio` + (engine clone) checkbox `auto_clone`.
  - Dropdown `llm_engine` (Gemini Local/Online/Ollama) — copy y hệt logic Bước 3 đã có trong app.js (tái dùng hàm resolve/hiển thị key).
  - Nút "Bắt đầu tạo phụ đề".
- **Form Bước 5**:
  - Chọn truyện (đã có `activeStoryName`). Nút "Tải danh sách video" → gọi `GET /api/stories/{name}/videos`, render checklist (bỏ tick sẵn `TongHop_*`). Nút "Ghép video đã chọn".

### F2. `webui/app.js`
- `initTabs()` tự động hoạt động với tab mới (nó quét mọi `.nav-item[data-tab]`). Kiểm tra: nếu có mảng cứng danh sách tab thì bổ sung `step4`, `step5`.
- Trong `setupEventHandlers()`: gắn nút Bước 4 → build payload → `postPipelineAction("step4", payload)` → nhận `task_key` → `streamLogs("step4", task_key)`. Tương tự Bước 5 → `postPipelineAction("step5", ...)`.
- `streamLogs` hiện nhận (stepName, taskKey) → dùng lại được ngay. Log Bước 4/5 là JSON — có thể hiển thị thô hoặc parse `event/message/percent` cho đẹp (tuỳ, không bắt buộc).
- Thêm hàm `loadStoryVideos(storyName)` cho Bước 5 (fetch danh sách + render checkbox).
- Toggle nút chạy/dừng: tái dùng `toggleFormButtons("step4"/"step5", isRunning)`.

**Bẫy (QUAN TRỌNG — quyết định trước khi code F1):**
- **Upload file qua trình duyệt CHƯA được orchestrator hỗ trợ** (không có endpoint multipart, và `postPipelineAction` gửi JSON). Có 2 hướng:
  - **(Khuyến nghị, ít việc):** Giai đoạn 1 CHỈ hỗ trợ **"Đường dẫn cục bộ"** + **"Tải từ link"** (cả hai chỉ cần gửi string trong JSON → không cần multipart). Bỏ nút Upload, hoặc để disabled kèm chú thích "sắp có". Đúng tinh thần chạy cục bộ trên máy cá nhân.
  - (Nhiều việc): thêm `POST /api/upload` multipart lưu vào `storage/tasks/uploads/` rồi truyền path — làm sau nếu người dùng thực sự cần upload.
- Style: tái dùng class `.card .glass-card .panel-grid .log-panel` sẵn có để đồng bộ giao diện; KHÔNG tự chế CSS mới trừ khi cần.

**Nghiệm thu Task F:** Mở webUI → thấy Bước 4 & Bước 5. Bước 4 với "Tải từ link" TikTok → chạy ra video có phụ đề Việt, log chảy realtime. Bước 5 chọn video → ra file ghép.

---

## Thứ tự thực thi & kiểm thử tổng

1. **Task B** (downloader) — độc lập, test riêng trước.
2. **Task C** (subtitle_extractor) — độc lập, test riêng.
3. **Task A** (adapter autosub) — tích hợp B+C, test CLI tay.
4. **Task D** (step4 pipeline+endpoint) — test bằng curl + SSE.
5. **Task E** (step5 merge) — test bằng curl.
6. **Task F** (UI) — test end-to-end trên trình duyệt.
7. Cập nhật `requirements.txt` (thêm `yt-dlp`, `rapidocr-onnxruntime`, `opencv-python-headless` nếu thiếu) + cài vào `AIVoice/.venv`.
8. Commit trong submodule `AIVoice` (Task A/B/C) → push → cập nhật con trỏ submodule ở repo tổng cùng Task D/E/F.
9. `pytest -q` ở repo tổng (đảm bảo không vỡ test hiện có); `python -m py_compile orchestrator/*.py`.
10. Cập nhật `README.md` mục pipeline: bổ sung Bước 4 (Autosub) & Bước 5 (Ghép), và bảng ánh xạ workflow.

## Checklist "không gây lỗi" (đọc lại trước khi kết thúc)
- [ ] Mọi tiến trình con chạy `cwd="AIVoice"`, dùng `.venv/Scripts/python.exe` — KHÔNG dùng python orchestrator.
- [ ] Adapter mới KHÔNG phụ thuộc `from orchestrator...` (tự copy slug tối giản nếu cần).
- [ ] `finally` giải phóng VRAM ở mọi adapter (whisper + torch).
- [ ] Route API khai báo TRƯỚC `app.mount("/", StaticFiles...)`.
- [ ] task_key duy nhất, guard `is_running` trước khi start.
- [ ] Không sửa `.github/workflows/*`, không commit `config.toml`.
- [ ] Submodule: commit con + cập nhật con trỏ ở repo tổng.
- [ ] Merge stream-copy có fallback re-encode khi codec khác nhau.
- [ ] Upload multipart: giai đoạn 1 dùng path/link, không giả định endpoint upload đã có.

## Mở rộng tương lai (ghi nhận, KHÔNG làm ở đợt này)
- PaddleOCR/VideoSubFinder cho hardsub chất lượng cao hơn.
- Endpoint upload multipart.
- Tải video độc lập (không qua autosub) để cấp nguồn cho Bước 3.
- Né watermark TikTok; hỗ trợ cookies cho site cần đăng nhập.
