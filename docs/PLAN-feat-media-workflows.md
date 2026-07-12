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
> ## ⚠️ CẢNH BÁO KỸ THUẬT SỐ 1 (đọc trước khi làm Task A/C — dễ làm hỏng luồng nếu bỏ qua)
> `composer.run_translation_workflow()` (`app/services/composer.py:272`) **hard-code Whisper** ở mục 1-2 (dòng ~329-347): nó LUÔN extract audio rồi gọi `create_subtitle()` để sinh SRT nguồn. Muốn cho phép nguồn SRT là **OCR (tách chữ trên hình)** thay vì Whisper, KHÔNG được viết workflow song song — hãy **thêm 1 tham số `source_srt_override: str = ""`** vào hàm này:
> - Nếu `source_srt_override` có giá trị (đường dẫn SRT đã dựng sẵn) → **BỎ QUA** extract audio + Whisper + `release_whisper_model`, gán thẳng `source_srt_path = source_srt_override` rồi đi tiếp mục dịch (translate_srt) + lồng tiếng + burn.
> - Nếu rỗng → giữ nguyên hành vi cũ (Whisper). Đây là sửa **~10 dòng, tương thích ngược 100%** (tham số mới có default rỗng).
> - Lý do phải override thay vì tự dịch trong adapter: bước lồng tiếng + burn + ducking nằm gọn trong workflow này; tái dùng để không lặp code và không lệch hành vi.
>
> ## Gợi ý commit (đặt tên theo Conventional Commits)
> - `feat(mediacomposer): add adapter_autosub_cli for translate-and-sub workflow` (Task A)
> - `feat(mediacomposer): add yt-dlp video downloader (tiktok/douyin/generic)` (Task B)
> - `feat(mediacomposer): add hardsub OCR extraction + preview frame (videocr-PaddleOCR)` (Task C)
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
| **(1b) Nguồn video: tải từ Bilibili/TikTok/Douyin/YouTube** | *(chưa có)* — chỉ có local path / upload | Task B (yt-dlp downloader) |
| **(2) Tạo SRT: chọn Whisper HOẶC OCR tách sub trên hình + dịch** | Whisper transcribe (`app/services/subtitle.py`) đã làm SRT-từ-âm-thanh; OCR tách hardsub *trên khung hình* thì CHƯA có | Task C (OCR hardsub) + Task C-preview (chọn vùng ROI), tích hợp vào Task A |
| **(3) Ghép các video đã tạo mà chưa từng ghép thành 1 video** | `orchestrator/video_merger.py:merge_videos()` (concat stream-copy) + `combine_videos()` (`app/services/video.py:538`) | Task E (step5 merge) + Task F (tab UI) |

> **ĐÃ CHỐT (chủ dự án xác nhận 2026-07-12):** Nền tảng tải video = **Bilibili** (chủ dự án nhầm "glibli" → thực ra là Bilibili), **TikTok**, **Douyin**, **YouTube**. Cả 4 đều được `yt-dlp` hỗ trợ sẵn → dropdown "nền tảng" ở Bước 4 chốt đúng 4 mục này (+ "Khác/generic" phòng hờ). Task B thiết kế downloader generic dựa trên `yt-dlp` nên không cần logic riêng cho từng site (yt-dlp tự nhận extractor theo URL).

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
--sub-source        (str)  whisper|ocr   (Task C — mặc định whisper)
--crop-x --crop-y --crop-w --crop-h  (int, mặc định -1)  vùng ROI cho OCR (Task C-Preview); -1 = không crop
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
5. **Nếu `--sub-source == ocr`** (Task C): gọi `extract_hardsub_ocr_srt(video_path, <srt>, lang=map(source_lang), crop=(crop_x,crop_y,crop_w,crop_h) nếu != -1)` → nhận `source_srt`. Vì `run_translation_workflow` hard-code whisper, truyền `source_srt` qua tham số mới `source_srt_override` (xem **⚠️ CẢNH BÁO KỸ THUẬT SỐ 1** đầu tài liệu — sửa ~10 dòng composer.py, tương thích ngược). Nếu `whisper` → để rỗng, workflow tự chạy whisper như cũ.
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

## Task B — Tải video từ Bilibili / TikTok / Douyin / YouTube (yt-dlp)

**File mới:** `AIVoice/apps/MediaComposer/app/services/video_downloader.py`.

**Phụ thuộc:** thêm `yt-dlp` vào `AIVoice/apps/MediaComposer/requirements.txt` và cài vào `AIVoice/.venv` (`.venv/Scripts/pip install yt-dlp`). yt-dlp gọi ffmpeg — đã có `imageio_ffmpeg` (`utils.get_ffmpeg_binary()`), truyền qua `ffmpeg_location`.

**API:**
```python
def download_video(url: str, output_dir: str, platform: str = "generic",
                   progress_cb=None) -> str:
    """Tải 1 video về output_dir, trả về đường dẫn file mp4. Raise nếu lỗi."""
```
Dùng `yt_dlp.YoutubeDL` với opts: `format="mp4/best"`, `outtmpl=<output_dir>/dl_%(id)s.%(ext)s`, `merge_output_format="mp4"`, `ffmpeg_location=<thư mục chứa ffmpeg>`, `noplaylist=True`, `quiet=True`, và `progress_hooks=[hook]` để phát `log_json("download_progress", {...})`. Trả `ydl.prepare_filename(info)` (đổi ext thành `.mp4`).

**`platform`** ∈ {`bilibili`, `tiktok`, `douyin`, `youtube`, `generic`} — hiện chỉ là nhãn (yt-dlp tự nhận extractor theo URL). Giữ tham số để: (1) validate domain hợp lệ theo nền tảng, (2) tương lai gắn cookies/headers riêng cho site cần đăng nhập (Bilibili/Douyin có thể chặn khách).

**Tích hợp:** Task A gọi `download_video()` khi có `--download-url`. Không tạo endpoint tải riêng — tải là bước con của autosub (đúng ý người dùng: "paste link + chọn nền tảng" ngay trong luồng tạo phụ đề). Nếu sau này cần tải-độc-lập cho Bước 3, tách endpoint riêng.

**Bẫy:**
- yt-dlp có thể trả nhiều định dạng; ép `format="mp4/best"` + `merge_output_format` để ra 1 file mp4 chuẩn cho ffmpeg/whisper.
- TikTok có watermark; muốn bản không watermark cần format phù hợp — để mặc định, KHÔNG cố né watermark (ngoài phạm vi).
- **Pháp lý/robots:** chỉ tải nội dung người dùng có quyền. Không thêm cơ chế bypass đăng nhập/c`captcha`.
- Bilibili/Douyin đôi khi cần `cookiesfrombrowser` — KHÔNG bật mặc định; nếu lỗi 403, log rõ và hướng dẫn người dùng, đừng tự lấy cookie trình duyệt.

**Nghiệm thu Task B:** `download_video("<link tiktok công khai>", <tmp>, "tiktok")` trả về file mp4 phát được.

---

## Task C — Nguồn SRT: Whisper HOẶC OCR tách chữ cháy trên hình (nghiên cứu công cụ + phương án)

**Yêu cầu người dùng (mô tả lại chính xác 2026-07-12):**
1. Video đầu ra **luôn có phụ đề** (burn sub) — điều này không đổi, `run_translation_workflow` đã burn sẵn.
2. File SRT nguồn được tạo bằng **1 trong 2 cách** (đây là điểm mới):
   - **(A) Whisper** — phiên âm từ *âm thanh* (đã có, giữ mặc định).
   - **(B) OCR** — công cụ đọc **chữ tiếng Trung/tiếng Anh cháy trên khung hình** rồi trích thành SRT.
3. Với cách (B): **sau khi tải video xong, hiện màn hình preview để người dùng khoanh vùng (ROI) chứa phụ đề** → OCR chỉ chạy trong vùng đó để **tăng tốc & giảm nhiễu**. (Chi tiết preview ở Task C-Preview + Task D3 + Task F.)

→ Dropdown `sub_source` ở UI chỉ có **2 mục**: `whisper` và `ocr`. (Trích phụ đề *mềm* embedded stream là bonus rẻ — xem "Ghi chú C0" cuối mục, KHÔNG đưa thành mục UI riêng để tránh rối.)

### Nghiên cứu công cụ OCR hardsub (đã tra cứu, cập nhật 07/2026)

| Công cụ | Bản chất | ROI/crop | Ngôn ngữ | Đánh giá cho dự án này |
|---|---|---|---|---|
| **`videocr-PaddleOCR`** (thư viện Python, fork `devmaxxing`/`oliverfei`) | Lib gọi PaddleOCR, sample frame → SRT **1 hàm** | ✅ `crop_x/crop_y/crop_width/crop_height` | `ch`, `en`, +nhiều | **KHUYẾN NGHỊ** — API gọn (`save_subtitles_to_file`), có sẵn crop ROI + `time_start/time_end`, tự dedupe (`sim_threshold`), tự lo timestamp. Ít code nhất. |
| **VideOCR** (`timminator/VideOCR`) | App GUI + CLI đóng gói, PaddleOCR, hỗ trợ 200+ ngôn ngữ | ✅ (GUI kéo vùng) | 200+ | Tốt cho người dùng cuối, nhưng là app ngoài → khó nhúng headless vào adapter subprocess. Tham khảo UI ROI của họ. |
| RapidOCR (onnxruntime) | Engine OCR thô, tự viết vòng lặp frame | tự crop | ch/en | Nhẹ (chỉ onnxruntime, không kéo paddle), nhưng **phải tự viết** sample+dedupe+timestamp → nhiều việc hơn videocr. |
| VideoSubFinder | App Windows dò vùng sub + mốc thời gian rất tốt | ✅ | (cần OCR ngoài) | Chuyên hardsub nhưng là .exe GUI, khó tự động hoá. Ghi nhận cho tương lai. |

**Chốt:** dùng **`videocr-PaddleOCR`** làm engine chính (API `crop_*` khớp thẳng với yêu cầu ROI). Dự phòng: nếu cài PaddleOCR gặp xung đột CUDA (xem Bẫy), fallback **RapidOCR** tự viết. Ghi VideoSubFinder/VideOCR-GUI vào "mở rộng tương lai".

### C-core: file `AIVoice/apps/MediaComposer/app/services/subtitle_extractor.py`
```python
def extract_hardsub_ocr_srt(
    video_path: str,
    output_srt: str,
    lang: str = "ch",                # "ch" (Trung) | "en" (Anh)
    crop: tuple[int,int,int,int] | None = None,  # (x, y, w, h) theo pixel gốc; None = toàn khung
    time_start: str = "",            # "" hoặc "mm:ss"
    time_end: str = "",
    conf_threshold: int = 75,
    sim_threshold: int = 80,
    frames_to_skip: int = 1,         # tăng để nhanh hơn (bỏ bớt frame)
    use_gpu: bool = False,           # xem Bẫy CUDA — mặc định CPU
    progress_cb=None
) -> str:
    """Gọi videocr-PaddleOCR: save_subtitles_to_file(video_path, output_srt, lang=..,
    crop_x/crop_y/crop_width/crop_height=.., time_start/time_end=.., conf_threshold,
    sim_threshold, frames_to_skip, use_gpu). Trả về output_srt."""
```
- Nếu `crop` = None → gọi với `use_fullframe=True` (chậm hơn, nhưng vẫn chạy).
- `lang`: map `source_lang` "Chinese"→"ch", "English"→"en".
- Bọc `progress_hooks`/log JSON nếu lib cho phép callback; nếu không, log mốc "bắt đầu OCR / xong OCR".

### C-Preview: trích 1 khung hình đại diện để người dùng khoanh vùng
File cùng module, hàm:
```python
def grab_preview_frame(video_path: str, out_image: str, at_seconds: float = None) -> dict:
    """Dùng ffmpeg lấy 1 frame (mặc định ~giữa video nếu at_seconds=None) ghi ra out_image (jpg/png).
    Trả về {'image': out_image, 'width': W, 'height': H, 'duration': D} (kích thước gốc để UI map toạ độ)."""
```
- ffmpeg: `ffmpeg -y -ss <t> -i <video> -frames:v 1 -q:v 3 <out_image>` (dùng `utils.get_ffmpeg_binary()`).
- Lấy W/H/duration qua ffprobe (JSON). **W/H là kích thước GỐC** — UI sẽ vẽ rectangle trên ảnh scale rồi quy đổi về pixel gốc trước khi gửi crop (Task F).
- Chọn `at_seconds`: mặc định giữa video để chắc chắn có phụ đề; cho phép người dùng đổi thời điểm ở UI (tuỳ chọn).

### Tích hợp vào adapter Task A (`--sub-source`)
- `whisper` → hành vi hiện tại, KHÔNG đụng.
- `ocr` → gọi `extract_hardsub_ocr_srt(lang=.., crop=(cx,cy,cw,ch) nếu có, ...)` → nhận `source_srt` → truyền `run_translation_workflow(..., source_srt_override=source_srt)` (dùng tham số mới ở ⚠️ CẢNH BÁO KỸ THUẬT SỐ 1). Adapter nhận crop qua arg mới: `--crop-x --crop-y --crop-w --crop-h` (int, mặc định -1 = không crop).
- Bất kể cách nào, sau khi có `source_srt` thì luồng dịch + (lồng tiếng) + burn của workflow chạy y như cũ → **đầu ra luôn có sub**.

### Ghi chú C0 (bonus, tuỳ chọn — làm nếu còn thời gian)
Trước khi OCR, có thể thử trích phụ đề **mềm** (nếu video có subtitle stream): `ffprobe` dò `codec_type=="subtitle"` → `ffmpeg -map 0:s:0 out.srt`. Nếu có → dùng luôn (0 chi phí, chính xác 100%), khỏi OCR. Đa số video Bilibili/TikTok là hardsub nên thường KHÔNG có → cứ để như một bước kiểm tra nhanh, không phải mục UI.

### Phụ thuộc & Bẫy
- Thêm vào `AIVoice/apps/MediaComposer/requirements.txt`: `videocr-PaddleOCR` (cài qua `pip install "git+https://github.com/oliverfei/videocr-PaddleOCR.git"` — kiểm tra fork còn sống; nếu không, dùng `devmaxxing/videocr-PaddleOCR`) + `paddleocr` + `paddlepaddle` (CPU) hoặc `paddlepaddle-gpu`. Python `.venv` phải 3.8–3.12 (kiểm tra: dự án dùng 3.11 ✅).
- **Bẫy CUDA (QUAN TRỌNG):** `paddlepaddle-gpu` và `torch` cùng venv dễ xung đột phiên bản CUDA/cuDNN và giành VRAM (GPU 6GB). **Mặc định cài `paddlepaddle` bản CPU + `use_gpu=False`** cho ổn định (OCR vài chục frame không quá chậm khi đã crop ROI). Chỉ bật GPU nếu người thực thi tự xác minh không vỡ môi trường. Vì OCR chạy trong **subprocess adapter riêng** (nạp/nhả độc lập), CPU-only không ảnh hưởng các bước khác.
- **Tốc độ:** crop ROI + `frames_to_skip>=2` giảm mạnh thời gian. Đây chính là lý do có màn preview chọn vùng.
- Model PaddleOCR tải lần đầu (vài chục–trăm MB) → cần mạng lần đầu; log rõ "đang tải model OCR" để người dùng không tưởng bị treo.
- `videocr` nhận `time_start/time_end` dạng chuỗi `"m:ss"` — adapter tự format từ giây nếu cần.

**Nghiệm thu Task C:**
- `grab_preview_frame(<mp4>, <jpg>)` ra ảnh + đúng W/H/duration.
- `extract_hardsub_ocr_srt(<mp4 hardsub tiếng Trung ngắn>, <srt>, lang="ch", crop=<vùng đáy>)` ra `.srt` có mốc thời gian hợp lý; sau đó `translate_srt` dịch sang tiếng Việt OK.
- So sánh: chạy có crop nhanh hơn rõ rệt so với `use_fullframe`.

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

### D2. `orchestrator/main.py` — schema + endpoint chạy autosub
- Thêm `class Step4Schema(BaseModel)`: `story_name: Optional[str]=None`, `video_path: Optional[str]=None`, `download_url: Optional[str]=None`, `platform: Optional[str]="generic"`, `source_lang="English"`, `sub_source="whisper"` (∈ whisper|ocr), `crop_x/crop_y/crop_w/crop_h: int=-1`, `burn_method="ffmpeg"`, `clean_audio=False`, `enable_voiceover=False`, `tts_engine="edge"`, `tts_voice=""`, `auto_clone=False`, `ducking_ratio=90.0`, `device="cuda"`, `llm_engine="gemini_api"`, `llm_api_key/llm_offline_base_url/llm_offline_model: Optional`.
- `POST /api/pipeline/step4`: validate (phải có `video_path` HOẶC `download_url`); nếu `sub_source=="ocr"` thì **khuyến nghị đã có `video_path`** (đã tải sẵn ở phase preview, xem D3) + `crop_*`; chặn nếu `is_running(task_key)`; gọi `pipeline.start_step_4_autosub(...)`. Trả `{"status":"success","task_key":...}`.
- Endpoint `stop` hiện tại (`/api/pipeline/stop`) dùng `f"{slug}_step{step}"` → KHÔNG khớp task_key autosub độc lập. **Thêm** `POST /api/pipeline/stop-task?task_key=` tổng quát (gọi `process_mgr.stop_process(task_key)`), UI Bước 4/5 dùng cái này.

### D3. Luồng 2 pha cho OCR + endpoint Preview (phục vụ chọn vùng ROI)
Vì OCR cần người dùng khoanh vùng phụ đề TRƯỚC khi chạy, Bước 4 (chế độ OCR) chạy **2 pha**:

**Pha 1 — Chuẩn bị & lấy khung xem trước:** `POST /api/autosub/prepare`
- Body: `{video_path?, download_url?, platform?, at_seconds?}`.
- Xử lý: tạo `task_id=uuid8`, thư mục `storage/tasks/autosub_<task_id>/`. Nếu có `download_url` → gọi downloader Task B tải về `source.mp4` (video mạng xã hội thường ngắn → chạy đồng bộ chấp nhận được; **nếu lo tải lâu** thì làm biến thể SSE giống các step khác — ghi chú, không bắt buộc). Nếu `video_path` → dùng thẳng. Sau đó gọi `subtitle_extractor.grab_preview_frame()` → `preview.jpg`.
- Trả: `{task_id, prepared_path: <abs path source.mp4>, width, height, duration, preview_b64: "data:image/jpeg;base64,..."}`. **Dùng base64 data-URI** cho ảnh preview để KHỎI thêm route static (đơn giản, ảnh 1 frame ~50-200KB ổn). *(Thay thế: `GET /api/autosub/preview/{task_id}` trả `FileResponse` — chỉ dùng nếu ảnh quá lớn.)*

**Pha 2 — Chạy:** UI gửi `POST /api/pipeline/step4` với `video_path=<prepared_path>` (KHÔNG gửi lại `download_url` → adapter không tải lại) + `sub_source="ocr"` + `crop_x/y/w/h` (đã quy đổi về **pixel gốc**) + phần còn lại.

**Chế độ Whisper KHÔNG cần pha 1** — người dùng dán link/đường dẫn rồi bấm chạy thẳng `POST /api/pipeline/step4` (adapter tự tải nếu là link). Preview chỉ bắt buộc khi `sub_source=="ocr"`.

**Bẫy:** `StaticFiles` mount ở `/` (main.py:296) nuốt mọi route KHÔNG khớp → mọi route API (kể cả `/api/autosub/prepare`) phải khai báo TRƯỚC dòng `app.mount(...)` ở cuối file. Toạ độ crop từ UI phải quy đổi từ ảnh hiển thị (đã scale) về **pixel gốc** trước khi gửi (UI biết `width/height` gốc từ pha 1 → nhân tỉ lệ). Kẹp giá trị trong `[0, width/height]`.

**Nghiệm thu Task D:**
- `POST /api/autosub/prepare {download_url:<tiktok>}` → trả `prepared_path` + `preview_b64` + `width/height`.
- `POST /api/pipeline/step4 {video_path:<prepared_path>, sub_source:"ocr", crop_*}` → task_key; SSE chảy log tới `autosub_done`.
- Chế độ whisper: `POST /api/pipeline/step4 {download_url:<link>, sub_source:"whisper"}` chạy 1 phát.

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
  - Nhóm "Nguồn video" — radio 2 lựa chọn: `Đường dẫn cục bộ` / `Tải từ link`. Chọn "Tải từ link" → hiện input URL + dropdown nền tảng (`Bilibili / TikTok / Douyin / YouTube / Khác`). *(Upload multipart CHƯA hỗ trợ — xem Bẫy; đừng thêm nút Upload ở giai đoạn 1.)*
  - Dropdown `source_lang` (English/Chinese).
  - Dropdown `sub_source` chỉ **2 mục**: **"Phiên âm từ âm thanh (Whisper)"** / **"Tách chữ cháy trên hình (OCR)"**.
  - **Khối Preview + chọn vùng ROI (chỉ hiện khi `sub_source == ocr`):**
    - Nút **"Tải & Xem trước"** → `POST /api/autosub/prepare` → nhận `preview_b64` + `width/height/duration` + `prepared_path` (lưu vào biến JS của tab). Vẽ ảnh preview lên `<canvas>` (hoặc `<img>` phủ 1 `<div>` overlay).
    - **Bộ chọn hình chữ nhật:** cho người dùng kéo chuột trên ảnh để vẽ khung ROI (mousedown→mousemove→mouseup, vanilla JS). Hiển thị khung + cho kéo lại. Lưu toạ độ **theo pixel ảnh hiển thị**, rồi **quy đổi về pixel gốc** = `round(val * width_goc / width_hien_thi)`. Mặc định gợi ý khung 25% đáy màn (người dùng chỉnh lại).
    - Chỉ khi đã có `prepared_path` + ROI mới cho bấm "Bắt đầu".
  - Dropdown `burn_method` (FFmpeg/MoviePy). Checkbox `clean_audio` (chỉ có tác dụng với Whisper — có thể ẩn khi OCR).
  - Checkbox `enable_voiceover` → khi bật hiện dropdown `tts_engine` + ô voice (đổi theo engine, mô phỏng Main.py:2640-2706) + slider `ducking_ratio` + (engine clone) checkbox `auto_clone`.
  - Dropdown `llm_engine` (Gemini Local/Online/Ollama) — copy y hệt logic Bước 3 đã có trong app.js (tái dùng hàm resolve/hiển thị key). Cần cho bước dịch SRT.
  - Nút **"Bắt đầu tạo phụ đề"**.
- **Form Bước 5**:
  - Chọn truyện (đã có `activeStoryName`). Nút "Tải danh sách video" → gọi `GET /api/stories/{name}/videos`, render checklist (bỏ tick sẵn `TongHop_*`). Nút "Ghép video đã chọn".

### F2. `webui/app.js`
- `initTabs()` tự động hoạt động với tab mới (nó quét mọi `.nav-item[data-tab]`). Kiểm tra: nếu có mảng cứng danh sách tab thì bổ sung `step4`, `step5`.
- **Bước 4 (Whisper):** build payload → `postPipelineAction("step4", payload)` → `streamLogs("step4", task_key)`.
- **Bước 4 (OCR) — 2 pha:**
  1. Nút "Tải & Xem trước" → `fetch POST /api/autosub/prepare` → lưu `state.step4 = {prepared_path, width, height}` + vẽ ảnh + bật bộ chọn ROI.
  2. Nút "Bắt đầu" → payload gồm `video_path=prepared_path`, `sub_source:"ocr"`, `crop_x/y/w/h` (đã quy đổi pixel gốc) → `postPipelineAction("step4", ...)` → `streamLogs`.
- Thêm hàm mới: `prepareAutosub(payload)` (gọi /prepare + render preview), `setupRoiSelector(canvas, imgW, imgH)` (kéo vẽ + trả crop gốc), `getCrop()`.
- `streamLogs` hiện nhận (stepName, taskKey) → dùng lại được ngay. Log Bước 4/5 là JSON — có thể parse `event/message/percent` cho đẹp (tuỳ).
- Thêm hàm `loadStoryVideos(storyName)` cho Bước 5 (fetch danh sách + render checkbox).
- Toggle nút chạy/dừng: tái dùng `toggleFormButtons("step4"/"step5", isRunning)`. Nút "Dừng" gọi endpoint `POST /api/pipeline/stop-task?task_key=` mới (D2).

**Bẫy (QUAN TRỌNG — quyết định trước khi code F1):**
- **Upload file qua trình duyệt CHƯA được orchestrator hỗ trợ** (không có endpoint multipart, và `postPipelineAction` gửi JSON). Có 2 hướng:
  - **(Khuyến nghị, ít việc):** Giai đoạn 1 CHỈ hỗ trợ **"Đường dẫn cục bộ"** + **"Tải từ link"** (cả hai chỉ cần gửi string trong JSON → không cần multipart). Bỏ nút Upload, hoặc để disabled kèm chú thích "sắp có". Đúng tinh thần chạy cục bộ trên máy cá nhân.
  - (Nhiều việc): thêm `POST /api/upload` multipart lưu vào `storage/tasks/uploads/` rồi truyền path — làm sau nếu người dùng thực sự cần upload.
- Style: tái dùng class `.card .glass-card .panel-grid .log-panel` sẵn có để đồng bộ giao diện; KHÔNG tự chế CSS mới trừ khi cần.

**Nghiệm thu Task F:** Mở webUI → thấy Bước 4 & Bước 5.
- Bước 4 (Whisper) + "Tải từ link" TikTok → ra video có phụ đề Việt, log realtime.
- Bước 4 (OCR): dán link → "Tải & Xem trước" hiện khung hình → kéo vẽ vùng phụ đề → "Bắt đầu" → OCR đúng vùng đã chọn, ra video phụ đề Việt.
- Bước 5 chọn video chương → ra file `TongHop_*.mp4` ghép liền mạch.

---

## Thứ tự thực thi & kiểm thử tổng

0. Cập nhật `AIVoice/apps/MediaComposer/requirements.txt` + cài vào `AIVoice/.venv`: `yt-dlp` (Task B), `videocr-PaddleOCR` + `paddleocr` + `paddlepaddle` (bản CPU) (Task C). Kiểm tra `opencv`/`ffprobe` sẵn có. Xác minh cài được TRƯỚC khi code (paddle hay lỗi cài trên Windows — nếu vỡ, chuyển phương án RapidOCR ngay từ đầu, đừng để lộ ở cuối).
1. **Task B** (downloader) — độc lập, test riêng trước với link Bilibili/TikTok/YouTube công khai.
2. **Task C** (subtitle_extractor: `grab_preview_frame` + `extract_hardsub_ocr_srt`) — độc lập, test riêng có/không crop.
3. **Task A** (adapter autosub) — tích hợp B+C + `source_srt_override`, test CLI tay cả whisper lẫn ocr.
4. **Task D** (step4 pipeline + endpoint + `/api/autosub/prepare` + `stop-task`) — test bằng curl + SSE.
5. **Task E** (step5 merge) — test bằng curl.
6. **Task F** (UI: 2 tab + bộ chọn ROI) — test end-to-end trên trình duyệt.
7. Commit trong submodule `AIVoice` (Task A/B/C) → push → cập nhật con trỏ submodule ở repo tổng cùng Task D/E/F.
8. `pytest -q` ở repo tổng (đảm bảo không vỡ test hiện có); `python -m py_compile orchestrator/*.py`.
9. Cập nhật `README.md` mục pipeline: bổ sung Bước 4 (Autosub) & Bước 5 (Ghép), và bảng ánh xạ workflow.

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
- [ ] **`source_srt_override` đã thêm vào `run_translation_workflow`** — OCR mới bỏ qua được Whisper (⚠️ CẢNH BÁO KỸ THUẬT SỐ 1).
- [ ] **Toạ độ ROI quy đổi về pixel gốc** trước khi gửi + kẹp trong biên ảnh.
- [ ] **paddlepaddle chạy CPU (`use_gpu=False`)** để không đụng CUDA của torch; nếu paddle cài lỗi → fallback RapidOCR.
- [ ] Chế độ OCR đi qua 2 pha (prepare → step4); chế độ Whisper chạy 1 pha.

## Mở rộng tương lai (ghi nhận, KHÔNG làm ở đợt này)
- VideOCR (GUI, timminator) hoặc RapidOCR làm engine thay thế/nâng cấp cho hardsub.
- Trích phụ đề mềm (embedded stream) tự động trước khi OCR (Ghi chú C0).
- Endpoint upload multipart; tải video độc lập cấp nguồn cho Bước 3.
- Cho người dùng đổi thời điểm frame preview (thanh trượt thời gian) + xem trước nhiều frame.
- Né watermark; cookies cho site cần đăng nhập (Bilibili/Douyin).
- Tải video độc lập (không qua autosub) để cấp nguồn cho Bước 3.
- Né watermark TikTok; hỗ trợ cookies cho site cần đăng nhập.
