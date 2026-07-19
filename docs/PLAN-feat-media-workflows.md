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
> ## ⚠️ 5 CẢNH BÁO KỸ THUẬT (đọc TRƯỚC khi code — mỗi cái đều đã được xác minh trên code thật; bỏ qua là chắc chắn gây lỗi)
>
> ### CB1 — Patch `source_srt_override` vào `run_translation_workflow`, nhưng PHẢI GIỮ bước extract audio
> `composer.run_translation_workflow()` (`app/services/composer.py:272`) hard-code Whisper. Thêm tham số mới `source_srt_override: str = ""` (cuối danh sách tham số, default rỗng → tương thích ngược 100%). **Patch chính xác như sau** (vị trí theo composer.py hiện tại):
> - **GIỮ NGUYÊN** mục "1. Extract audio" (dòng ~303-322, tạo `extracted_audio.wav`) — vì biến `audio_path` còn được dùng ở nhánh moviepy phía dưới (dòng ~441 `moviepy_audio = target_audio if target_audio else audio_path`). Xoá block này là `NameError`/mất tiếng ở nhánh moviepy.
> - Bọc đoạn từ `whisper_audio_path = audio_path` (dòng ~324) đến hết `release_whisper_model()` (dòng ~347) — tức cả Demucs (`clean_audio`) lẫn Whisper + kiểm tra SRT rỗng — vào nhánh `else`. Nhánh `if source_srt_override:` thì:
>   ```python
>   if source_srt_override:
>       logger.info(f"Dùng SRT nguồn có sẵn (OCR/bên ngoài): {source_srt_override} — bỏ qua Demucs + Whisper")
>       source_srt_path = source_srt_override
>       if not os.path.exists(source_srt_path) or os.path.getsize(source_srt_path) == 0:
>           raise RuntimeError(f"SRT nguồn không tồn tại hoặc rỗng: {source_srt_path}")
>   else:
>       # (toàn bộ khối cũ: clean_audio/Demucs → create_subtitle → check rỗng → release_whisper_model)
>   ```
> - Từ mục "4. Translate" trở đi giữ nguyên — `source_srt_path` đã trỏ đúng; `generate_dubbed_audio` nhận `source_srt_path` này bình thường.
>
> ### CB2 — Bộ key LLM cho dịch SRT là `openai_*`, KHÔNG phải `llm_*`
> Đã xác minh: `translation.py:72-83` và `dubbing.py:157-167` đọc `config.app["openai_api_key"]`, `config.app["openai_base_url"]`, `config.app["openai_model"]`. Bộ `llm_api_key/llm_base_url/llm_model` mà `adapter_video_cli.py:57-62` set là cho storytelling (llm.py:63-65 có fallback), **KHÔNG được translate_srt dùng**. Adapter autosub phải set **in-memory** (KHÔNG `save_config()`):
> ```python
> config.app["openai_api_key"] = args.llm_api_key
> config.app["openai_base_url"] = args.llm_base_url
> config.app["openai_model"] = args.llm_model
> ```
> Nếu set nhầm `llm_*`: `translate_srt` thấy key rỗng → **copy nguyên phụ đề tiếng gốc, KHÔNG raise lỗi** (translation.py:73-77) → video ra phụ đề chưa dịch mà log vẫn "thành công". Vì vậy **nghiệm thu phải kiểm tra phụ đề LÀ TIẾNG VIỆT**, không chỉ "có phụ đề".
>
> ### CB3 — Import `orchestrator.*` trong tiến trình con chỉ sống nhờ `run.bat` set `PYTHONPATH`
> Đã xác minh: `run.bat` có `set PYTHONPATH=%CD%` (repo tổng) → tiến trình con kế thừa qua `os.environ.copy()` trong process_manager → đó là lý do duy nhất `adapter_video_cli.py:74` import được `orchestrator.storage`. Chạy adapter bằng tay KHÔNG set PYTHONPATH sẽ `ModuleNotFoundError`. **Adapter mới TUYỆT ĐỐI KHÔNG import `orchestrator.*`** — không cần slugify (task_id là uuid). Khi test CLI tay, không cần set gì thêm nếu tuân thủ điều này.
>
> ### CB4 — Orchestrator KHÔNG ĐƯỢC import bất kỳ module nào của MediaComposer
> `AIVoice/apps/MediaComposer/app/config.py:3` có `import torch` ở top-level → chỉ cần `main.py` orchestrator import `app.services.video_downloader` hay `subtitle_extractor` là **kéo torch (+paddle) vào process orchestrator** — vi phạm kiến trúc (orchestrator phải nhẹ, không torch), ngốn RAM, chậm khởi động. Mọi việc nặng (tải video, grab frame, OCR) đều đi qua **subprocess adapter** trong `AIVoice/.venv`. Endpoint `/api/autosub/prepare` gọi adapter với cờ `--prepare-only` (xem Task D3), KHÔNG import trực tiếp.
>
> ### CB5 — `ffprobe` KHÔNG tồn tại trên máy đích
> `imageio_ffmpeg` chỉ ship **ffmpeg.exe**, không có ffprobe. Mọi chỗ cần metadata video (W/H/duration) dùng **moviepy** (đã có trong requirements MC):
> ```python
> from moviepy.video.io.VideoFileClip import VideoFileClip
> clip = VideoFileClip(video_path); w, h = clip.size; dur = clip.duration; clip.close()
> ```
> KHÔNG gọi `ffprobe` ở bất kỳ đâu trong code mới.
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
- Chạy trong `cwd="AIVoice"` → adapter tự `sys.path.insert` `mc_root` và `mc_root/app`. Import `from orchestrator.storage import slugify` ở `adapter_video_cli.py:74` chỉ sống nhờ `run.bat` set `PYTHONPATH=%CD%` — chi tiết và quy tắc cho adapter mới xem **CB3** (đầu tài liệu).

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
- `config.py`: đọc `config.toml`, có `config.whisper` (model_size, device, compute_type, font_name...) và `config.app`. **Chú ý:** `config.app` chứa CẢ HAI bộ key `openai_*` và `llm_*` — `translate_srt`/`dubbing` chỉ đọc bộ `openai_*` (xem **CB2**). Adapter set in-memory, KHÔNG `save_config()`.

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

**Argparse (khớp tham số Streamlit + mở rộng cho Task B/C/D):**
```
--video-path        (str)  đường dẫn video local (BẮT BUỘC nếu không có --download-url)
--download-url      (str)  link video để tải (Task B) — nếu có, tải trước rồi dùng làm video_path
--platform          (str)  bilibili|tiktok|douyin|youtube|generic (Task B)
--output-dir        (str)  thư mục lưu kết quả cuối (BẮT BUỘC)
--prepare-only      (flag) CHỈ tải video + trích 1 frame preview rồi thoát (phục vụ D3), KHÔNG chạy workflow
--source-lang       (str)  English|Chinese (mặc định English)
--sub-source        (str)  whisper|ocr   (Task C — mặc định whisper)
--crop-x --crop-y --crop-w --crop-h  (int, mặc định -1)  vùng ROI cho OCR (Task C-Preview); -1 = không crop
--burn-method       (str)  ffmpeg|moviepy (mặc định ffmpeg)
--clean-audio       (flag, default False) Demucs tách giọng trước whisper (vô hiệu khi sub-source=ocr)
--enable-voiceover  (flag, default False)
--tts-engine        (str)  edge|piper|kokoro|vieneu|clone (mặc định edge)
--tts-voice         (str)
--auto-clone        (flag, default False)
--ducking-ratio     (float, default 90.0)
--llm-api-key --llm-base-url --llm-model  (str)  LLM để DỊCH SRT — bắt buộc set vào config.app["openai_*"] (CB2!)
```

**Cấu trúc import (QUAN TRỌNG cho `--prepare-only` nhanh & nhẹ):** chỉ import stdlib + argparse ở top file. Các import nặng (`app.services.composer`, `app.config`, moviepy, torch) đặt **bên trong** nhánh xử lý tương ứng (lazy import) — `--prepare-only` chỉ cần `video_downloader` + moviepy (metadata) + ffmpeg (grab frame), KHÔNG được kéo composer/whisper/torch.

**Thân hàm (thứ tự):**
1. `os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"`; set sys.path như adapter_video_cli (dòng 11-13). **KHÔNG import `orchestrator.*` (CB3).**
2. `log_json("autosub_init", {...})`.
3. Nếu `--download-url`: gọi downloader Task B, lưu vào `--output-dir` (chế độ prepare) hoặc task_dir → nhận `video_path` local; `log_json("download_done", {"path":...})`. Ngược lại dùng `--video-path` (kiểm tra tồn tại, raise nếu không).
4. **Nếu `--prepare-only`:** gọi `grab_preview_frame(video_path, <output-dir>/preview.jpg)` (Task C) → in ĐÚNG MỘT dòng:
   `log_json("prepare_done", {"prepared_path": <abs video>, "preview_image": <abs jpg>, "width": W, "height": H, "duration": D})` → `sys.exit(0)`. (KHÔNG in base64 ra stdout — orchestrator tự đọc file ảnh.)
5. `task_id = uuid4().hex`; tạo MC task_dir qua `from app.utils import utils; utils.task_dir(task_id)`.
6. **Nạp LLM config theo CB2:** `from app.config import config` rồi set `config.app["openai_api_key"/"openai_base_url"/"openai_model"] = args.llm_*` (in-memory, KHÔNG `save_config()`).
7. **Nếu `--sub-source == ocr`** (Task C): gọi `extract_hardsub_ocr_srt(video_path, <srt>, lang=("ch" if source_lang=="Chinese" else "en"), crop=(x,y,w,h) nếu cả 4 giá trị != -1)` → `source_srt`. Nếu `whisper` → `source_srt = ""`.
8. Gọi `composer.run_translation_workflow(task_id=task_id, video_path=..., source_lang=..., burn_method=..., enable_voiceover=..., tts_engine=..., tts_voice=..., ducking_ratio=..., auto_clone=..., clean_audio=(False nếu ocr), source_srt_override=source_srt)` — dùng patch CB1.
9. Copy file kết quả sang `--output-dir` với tên `<basename>_autosub_<timestamp>.mp4`; `log_json("autosub_done", {"output": <đường dẫn cuối>})`.
10. `except`: `log_json("autosub_error", {"error": str(e)})`, `sys.exit(1)`.
11. `finally`: giải phóng VRAM giống adapter_video_cli (`release_whisper_model()` nếu đã import + torch empty_cache trong try/except + gc). Với `--prepare-only` thì finally không có gì để nhả (đừng import torch chỉ để nhả).

**Bẫy:**
- **CB2**: key dịch là `openai_*`. Set nhầm `llm_*` → dịch bị bỏ qua IM LẶNG, sub ra tiếng gốc.
- (Tuỳ chọn, khuyến khích) Sau `run_translation_workflow`, đọc vài dòng đầu của `vietnamese_subtitles.srt` và `source_subtitles.srt`/SRT OCR — nếu **giống hệt nhau** → `log_json("autosub_warn", {"message": "Bản dịch trùng bản gốc — kiểm tra LLM key/proxy!"})` để người dùng thấy ngay trên console.
- `tts_voice` với vieneu là dạng `"Tên|mode"` (Main.py:2686). Adapter chỉ truyền chuỗi thô, không parse.
- Whisper `language`: workflow tự map English→en, Chinese→zh (composer.py:334-339). Không cần map ở adapter.
- Không chạy Bước 4 (Whisper GPU) song song với Bước 3 (Stable Diffusion) trên GPU 6GB — ghi chú vận hành, không cần code guard.

**Nghiệm thu Task A:** Chạy tay trong `AIVoice/.venv` (không cần PYTHONPATH nếu tuân thủ CB3):
```
cd AIVoice
.venv/Scripts/python.exe apps/MediaComposer/adapter_autosub_cli.py --prepare-only \
  --video-path <mp4 ngắn> --output-dir <tmp>          # → 1 dòng prepare_done, có preview.jpg, thoát ngay
.venv/Scripts/python.exe apps/MediaComposer/adapter_autosub_cli.py \
  --video-path <mp4 tiếng Anh ngắn> --output-dir <tmp> --source-lang English \
  --llm-api-key <key> --llm-base-url http://localhost:7860/v1 --llm-model gemini-3-flash
```
(Lệnh 2 cần **Gemini-API proxy đang chạy** ở :7860 — bật bằng `toolCaoTruyen/Gemini-API/start_server.bat` hoặc chạy `run.bat` tổng.)
→ ra `*_autosub_*.mp4` mà phụ đề **là TIẾNG VIỆT** (mở video kiểm tra mắt — CB2); stdout là các dòng JSON hợp lệ; tiến trình thoát hẳn, không giữ VRAM (kiểm tra `nvidia-smi`).

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
    """Lấy 1 frame (mặc định ~giữa video nếu at_seconds=None) ghi ra out_image (jpg).
    Trả về {'image': out_image, 'width': W, 'height': H, 'duration': D} (kích thước gốc để UI map toạ độ)."""
```
- **Metadata (W/H/duration) lấy bằng moviepy — KHÔNG dùng ffprobe (CB5: máy đích không có ffprobe):**
  ```python
  from moviepy.video.io.VideoFileClip import VideoFileClip
  clip = VideoFileClip(video_path); w, h = clip.size; dur = clip.duration; clip.close()
  ```
- Grab frame bằng ffmpeg: `[utils.get_ffmpeg_binary(), "-y", "-ss", str(t), "-i", video_path, "-frames:v", "1", "-q:v", "3", out_image]` với `t = at_seconds if at_seconds is not None else dur/2`. Chạy `subprocess.run(capture_output=True)`, check returncode.
- **W/H là kích thước GỐC** — UI vẽ rectangle trên ảnh đã scale rồi quy đổi về pixel gốc trước khi gửi crop (Task F).

### Tích hợp vào adapter Task A (`--sub-source`)
- `whisper` → hành vi hiện tại, KHÔNG đụng.
- `ocr` → gọi `extract_hardsub_ocr_srt(lang=.., crop=(cx,cy,cw,ch) nếu có, ...)` → nhận `source_srt` → truyền `run_translation_workflow(..., source_srt_override=source_srt)` (dùng tham số mới ở **CB1**). Adapter nhận crop qua arg mới: `--crop-x --crop-y --crop-w --crop-h` (int, mặc định -1 = không crop).
- Bất kể cách nào, sau khi có `source_srt` thì luồng dịch + (lồng tiếng) + burn của workflow chạy y như cũ → **đầu ra luôn có sub**.

### Ghi chú C0 (bonus, tuỳ chọn — CHỈ làm nếu mọi thứ khác đã xong và pass nghiệm thu)
Trước khi OCR, có thể thử trích phụ đề **mềm** (nếu video có subtitle stream): chạy `ffmpeg -y -i <video> -map 0:s:0 out.srt` và kiểm tra returncode + file có nội dung (KHÔNG dùng ffprobe — CB5; ffmpeg tự fail nếu không có stream sub). Nếu ra SRT hợp lệ → dùng luôn, khỏi OCR. Đa số video Bilibili/TikTok là hardsub nên thường KHÔNG có — đây chỉ là bước thử nhanh, không phải mục UI, và **được phép bỏ hẳn** nếu gây phức tạp.

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
- `task_key = f"autosub_{id}_step4"` (id = slug truyện hoặc uuid8).
- **KHÔNG có tuỳ chọn `device` cho Bước 4** (khác step3). Lý do đã xác minh: Whisper lấy device từ `config.whisper["device"]` trong config.toml của MC (subtitle.py:22); nếu set `CUDA_VISIBLE_DEVICES=""` mà config.toml vẫn ghi `cuda` thì `WhisperModel(device="cuda")` crash khó hiểu. Để device do config.toml quyết — không expose ở UI/schema/env_override.
- `on_completed`: cập nhật meta nếu gắn truyện; đóng queue. KHÔNG tự merge (khác step3).
- `start_process(task_key, cmd, cwd="AIVoice", on_completed=on_completed)` (không cần env_override).

### D2. `orchestrator/main.py` — schema + endpoint chạy autosub
- Thêm `class Step4Schema(BaseModel)`: `story_name: Optional[str]=None`, `video_path: Optional[str]=None`, `download_url: Optional[str]=None`, `platform: Optional[str]="generic"`, `source_lang="English"`, `sub_source="whisper"` (∈ whisper|ocr), `crop_x/crop_y/crop_w/crop_h: int=-1`, `burn_method="ffmpeg"`, `clean_audio=False`, `enable_voiceover=False`, `tts_engine="edge"`, `tts_voice=""`, `auto_clone=False`, `ducking_ratio=90.0`, `llm_engine="gemini_api"`, `llm_api_key/llm_offline_base_url/llm_offline_model: Optional`. (KHÔNG có field `device` — xem D1.)
- `POST /api/pipeline/step4`: validate (phải có `video_path` HOẶC `download_url`); nếu `sub_source=="ocr"` thì **khuyến nghị đã có `video_path`** (đã tải sẵn ở phase preview, xem D3) + `crop_*`; chặn nếu `is_running(task_key)`; gọi `pipeline.start_step_4_autosub(...)`. Trả `{"status":"success","task_key":...}`.
- Endpoint `stop` hiện tại (`/api/pipeline/stop`) dùng `f"{slug}_step{step}"` → KHÔNG khớp task_key autosub độc lập. **Thêm** `POST /api/pipeline/stop-task?task_key=` tổng quát (gọi `process_mgr.stop_process(task_key)`), UI Bước 4/5 dùng cái này.

### D3. Luồng 2 pha cho OCR + endpoint Preview (phục vụ chọn vùng ROI)
Vì OCR cần người dùng khoanh vùng phụ đề TRƯỚC khi chạy, Bước 4 (chế độ OCR) chạy **2 pha**:

**Pha 1 — Chuẩn bị & lấy khung xem trước:** `POST /api/autosub/prepare`
- Body (`PrepareSchema`): `{video_path?: str, download_url?: str, platform?: str = "generic"}`. Validate: phải có đúng 1 trong 2 nguồn.
- **Chạy qua SUBPROCESS adapter với cờ `--prepare-only` (CB4 — TUYỆT ĐỐI KHÔNG import module MediaComposer vào main.py):**
  ```python
  @app.post("/api/autosub/prepare")
  def autosub_prepare(body: PrepareSchema):        # def SYNC — FastAPI tự chạy trong threadpool.
      import subprocess, uuid, base64, json as _json
      task_id = uuid.uuid4().hex[:8]
      work_dir = os.path.join(storage_mgr.tasks_dir, f"autosub_{task_id}")
      os.makedirs(work_dir, exist_ok=True)
      python_exe = os.path.abspath("AIVoice/.venv/Scripts/python.exe")
      adapter = os.path.abspath("AIVoice/apps/MediaComposer/adapter_autosub_cli.py")
      cmd = [python_exe, adapter, "--prepare-only", "--output-dir", work_dir]
      if body.download_url:
          cmd += ["--download-url", body.download_url, "--platform", body.platform or "generic"]
      else:
          cmd += ["--video-path", body.video_path]
      try:
          res = subprocess.run(cmd, cwd="AIVoice", capture_output=True, text=True,
                               encoding="utf-8", timeout=900)
      except subprocess.TimeoutExpired:
          raise HTTPException(status_code=504, detail="Tải/chuẩn bị video quá 15 phút — kiểm tra link hoặc mạng.")
      # Tìm dòng JSON có event == "prepare_done" trong stdout (duyệt từng dòng, json.loads trong try/except)
      # Nếu không thấy → HTTPException(500, detail=đuôi stdout+stderr (~1000 ký tự cuối) để debug)
      # Đọc info["preview_image"] → base64 → trả:
      # {"task_id":..., "prepared_path":..., "width":..., "height":..., "duration":...,
      #  "preview_b64": "data:image/jpeg;base64," + b64}
  ```
  - **Dùng `def` SYNC, KHÔNG `async def`** — `subprocess.run` là blocking; đặt trong `async def` sẽ treo toàn bộ event loop (mọi request khác + SSE đứng hình). FastAPI tự đưa `def` thường vào threadpool.
  - Ảnh preview trả bằng **base64 data-URI** (1 frame jpg ~50-300KB, chấp nhận được) để khỏi thêm route static.

**Pha 2 — Chạy:** UI gửi `POST /api/pipeline/step4` với `video_path=<prepared_path>` (KHÔNG gửi lại `download_url` → adapter không tải lại) + `sub_source="ocr"` + `crop_x/y/w/h` (đã quy đổi về **pixel gốc**) + phần còn lại.

**Chế độ Whisper KHÔNG cần pha 1** — người dùng dán link/đường dẫn rồi bấm chạy thẳng `POST /api/pipeline/step4` (adapter tự tải nếu là link). Preview chỉ bắt buộc khi `sub_source=="ocr"`.

**Bẫy:**
- `StaticFiles` mount ở `/` (main.py:296) nuốt mọi route KHÔNG khớp → mọi route API (kể cả `/api/autosub/prepare`) phải khai báo TRƯỚC dòng `app.mount(...)` ở cuối file.
- Toạ độ crop từ UI phải quy đổi từ ảnh hiển thị (đã scale) về **pixel gốc** trước khi gửi (UI biết `width/height` gốc từ pha 1 → nhân tỉ lệ). Server kẹp (clamp) crop trong `[0, width/height]` phòng UI gửi lệch.
- KHÔNG thêm dependency mới vào venv orchestrator (base64/uuid/subprocess đều là stdlib).

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
- **`orchestrator/video_merger.py`: GIỮ NGUYÊN chữ ký cũ, chỉ thêm tham số optional** (step3 `on_video_completed` tại pipeline.py:369 đang gọi `merge_videos(video_output_dir, output_file)` — đổi chữ ký bắt buộc là VỠ step3):
  ```python
  def merge_videos(video_dir: str, output_file: str, only_files: list[str] | None = None) -> bool:
      ...
      mp4_files = sorted(glob.glob(os.path.join(video_dir, "*.mp4")))
      mp4_files = [f for f in mp4_files if not os.path.basename(f).startswith("TongHop_")]
      if only_files:
          # CHỐNG PATH TRAVERSAL: chỉ nhận basename thuần, phải nằm trong danh sách quét được
          wanted = {name for name in only_files if os.path.basename(name) == name}
          mp4_files = [f for f in mp4_files if os.path.basename(f) in wanted]
      ...
  ```
- `orchestrator/pipeline.py`: `start_step_5_merge(self, story_name, selected_files: list[str] | None) -> bool`. Merge nhanh nhưng vẫn cần SSE — chạy **thread nền tự quản queue** (KHÔNG qua `start_process` vì không có subprocess). Snippet mẫu:
  ```python
  def start_step_5_merge(self, story_name, selected_files=None):
      import queue as _q, threading, time
      meta = self.storage_mgr.read_story_meta(story_name)
      if not meta:
          return False
      task_key = f"{meta['story_slug']}_step5"
      q = _q.Queue()
      self.process_mgr.log_queues[task_key] = q          # SSE đọc queue này
      video_dir = os.path.join(self.storage_mgr.get_story_dir(story_name), "video")
      out = os.path.join(video_dir, f"TongHop_{time.strftime('%Y%m%d_%H%M%S')}.mp4")
      def _run():
          try:
              from orchestrator.video_merger import merge_videos
              q.put(f"[SYSTEM] Bắt đầu ghép video vào {out}...\n")
              ok = merge_videos(video_dir, out, only_files=selected_files)
              q.put("[SYSTEM] Ghép video thành công!\n" if ok
                    else "[SYSTEM] Ghép thất bại — xem chi tiết phía trên.\n")
          except Exception as e:
              q.put(f"[ERROR] {e}\n")
          finally:
              q.put(None)                                 # BẮT BUỘC — thiếu là SSE treo vĩnh viễn
      threading.Thread(target=_run, daemon=True).start()
      return True
  ```
  - Output: `TongHop_<timestamp>.mp4` trong `video/`.
  - **Lưu ý:** `merge_videos` hiện in bằng `print()` → khi chạy trong thread orchestrator, output đó KHÔNG vào queue. Chấp nhận được (đã có message SYSTEM); nếu muốn chi tiết hơn thì thêm tham số callback `log_fn=print` vào `merge_videos` và truyền `q.put` — tuỳ chọn, không bắt buộc.
- `orchestrator/main.py`: `class Step5Schema(BaseModel): story_name: str; selected_files: Optional[list[str]] = None`; `POST /api/pipeline/step5` → validate story tồn tại → gọi `start_step_5_merge` → trả `{"status":"success","task_key":f"{slug}_step5"}`.
- **Nút Dừng cho step5: KHÔNG có** — `stop_process` chỉ dừng được subprocess, không dừng thread; merge stream-copy chỉ vài giây nên không cần. UI ẩn nút Stop ở tab step5 (xem Task F).

**Bẫy:**
- concat stream-copy (`-c copy`) chỉ hoạt động nếu **mọi mp4 cùng codec/độ phân giải/fps**. Video từ step3 (cùng pipeline) đồng nhất → OK. Nếu người dùng trộn video khác nguồn → có thể lỗi. **Fallback ĐÚNG 1 TẦNG, giữ đơn giản:** nếu lệnh `-c copy` trả exit != 0 → chạy lại đúng lệnh đó nhưng thay `"-c", "copy"` bằng `"-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac"` (xử lý được khác codec, CÙNG độ phân giải). Nếu vẫn fail → return False kèm message tiếng Việt rõ: `"Các video khác độ phân giải/định dạng — hãy chọn các video cùng nguồn (cùng được tạo từ Bước 3)."`. KHÔNG cố xử lý khác-độ-phân-giải bằng filter phức tạp (ngoài phạm vi, dễ sai).
- `merge_videos` hiện `import imageio_ffmpeg` từ path AIVoice/.venv site-packages (video_merger.py:11) — giữ nguyên, đã hoạt động ở step3.

**Nghiệm thu Task E:** chọn ≥2 video chương → ra `TongHop_*.mp4` phát liền mạch; log SSE báo tiến độ + hoàn tất; chạy lại lần 2 vẫn hoạt động (file `TongHop_` cũ không bị gộp vào file mới); `pytest -q` vẫn xanh (không vỡ chữ ký `merge_videos` mà step3 dùng).

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

**BẢNG ID BẮT BUỘC** (đã xác minh từ code app.js — đặt sai tên là hàm sẵn có KHÔNG hoạt động, lỗi im lặng):

| Thành phần | ID bắt buộc | Vì sao |
|---|---|---|
| Nút chạy Bước 4 | `btnStartStep4` | `toggleFormButtons` (app.js:605-607) dựng ID bằng `` `btnStartStep${stepName.slice(-1)}` `` |
| Nút dừng Bước 4 | `btnStopStep4` | như trên |
| Console log Bước 4 | `logConsole-step4` | `appendConsoleLog`/`clearConsole` (app.js:619-626) dùng `` `logConsole-${stepName}` `` |
| Nút chạy Bước 5 | `btnStartStep5` | như trên |
| Nút dừng Bước 5 | `btnStopStep5` | tạo nhưng để `style="display:none"` vĩnh viễn (step5 không dừng được — Task E2). PHẢI tồn tại trong DOM vì `toggleFormButtons` gọi `.style` không check null → thiếu là JS crash. |
| Console log Bước 5 | `logConsole-step5` | như trên |

- `initTabs()` (app.js:52) quét mọi `.nav-item[data-tab]` → tab mới tự hoạt động, không phải sửa.
- **Bước 4 (Whisper):** build payload → `postPipelineAction("step4", payload)` (app.js:564 — trả `task_key` hoặc null) → nếu có task_key: `toggleFormButtons("step4", true)` + `clearConsole("step4")` + `streamLogs("step4", task_key)`.
- **Bước 4 (OCR) — 2 pha:**
  1. Nút "Tải & Xem trước" → `fetch POST /api/autosub/prepare` → lưu `step4State = {preparedPath, natW, natH}` + gán `img.src = preview_b64` + bật bộ chọn ROI.
  2. Nút "Bắt đầu" → payload gồm `video_path: step4State.preparedPath`, `sub_source: "ocr"`, `crop_x/y/w/h` từ ROI → `postPipelineAction("step4", ...)` → `streamLogs`.
- **Dừng Bước 4:** KHÔNG dùng `stopPipelineTask` cũ (app.js:587 — nó yêu cầu `activeStoryName` + format `slug_stepN`, không khớp task_key autosub). Viết hàm mới:
  ```js
  let currentTaskKeys = {};   // { step4: "autosub_ab12cd34_step4", ... } — set sau mỗi postPipelineAction
  async function stopTaskByKey(stepName) {
      const key = currentTaskKeys[stepName];
      if (!key) return;
      const res = await fetch(`${API_BASE}/api/pipeline/stop-task?task_key=${encodeURIComponent(key)}`, { method: "POST" });
      const data = await res.json();
      appendConsoleLog(stepName, res.ok ? "[SYSTEM] Đã gửi yêu cầu dừng." : `[SYSTEM] Không dừng được: ${data.detail}`, "log-system");
  }
  ```
- **Bộ chọn ROI — dùng nguyên mẫu này** (`<img id="s4PreviewImg">` bọc trong `<div style="position:relative">`):
  ```js
  function setupRoiSelector(imgEl, natW, natH, onChange) {
      const box = document.createElement("div");
      box.style.cssText = "position:absolute;border:2px dashed #4ade80;background:rgba(74,222,128,.15);pointer-events:none;display:none";
      imgEl.parentElement.appendChild(box);
      let sx = 0, sy = 0, drag = false, rect = null;
      const rel = (e) => {
          const r = imgEl.getBoundingClientRect();
          return [Math.min(Math.max(e.clientX - r.left, 0), r.width),
                  Math.min(Math.max(e.clientY - r.top, 0), r.height)];
      };
      imgEl.addEventListener("mousedown", (e) => { [sx, sy] = rel(e); drag = true; e.preventDefault(); });
      window.addEventListener("mousemove", (e) => {
          if (!drag) return;
          const [x, y] = rel(e);
          rect = { x: Math.min(sx, x), y: Math.min(sy, y), w: Math.abs(x - sx), h: Math.abs(y - sy) };
          Object.assign(box.style, { display: "block", left: rect.x + "px", top: rect.y + "px",
                                     width: rect.w + "px", height: rect.h + "px" });
      });
      window.addEventListener("mouseup", () => {
          if (!drag) return;
          drag = false;
          if (rect && rect.w > 5 && rect.h > 5) {
              const r = imgEl.getBoundingClientRect(), kx = natW / r.width, ky = natH / r.height;
              onChange({ x: Math.round(rect.x * kx), y: Math.round(rect.y * ky),
                         w: Math.round(rect.w * kx), h: Math.round(rect.h * ky) });  // PIXEL GỐC
          }
      });
  }
  ```
- `streamLogs` (app.js:639) dùng lại được ngay — nó tự parse JSON theo `parsed.event` và có default hiển thị raw; THÊM (tuỳ chọn) case `autosub_init/download_progress/autosub_done/autosub_error/autosub_warn` vào switch cho đẹp.
- **Giới hạn có sẵn, KHÔNG "sửa giùm":** `currentLogsSse` là biến toàn cục đơn (app.js:640-641) → mở console step5 sẽ đóng stream step4. Chấp nhận (giống hành vi các bước hiện tại), KHÔNG refactor thành multi-stream trong đợt này.
- Thêm hàm `loadStoryVideos(storyName)` cho Bước 5 (fetch `GET /api/stories/{name}/videos` + render checkbox; disable nút Ghép khi chưa tick ≥ 2).

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

0. Cập nhật `AIVoice/apps/MediaComposer/requirements.txt` + cài vào `AIVoice/.venv`: `yt-dlp` (Task B), `videocr-PaddleOCR` + `paddleocr` + `paddlepaddle` (bản CPU) (Task C). **Xác minh cài + import được TRƯỚC khi code** (`python -c "import yt_dlp; from videocr import save_subtitles_to_file"`) — paddle hay lỗi cài trên Windows; nếu vỡ, chuyển phương án RapidOCR ngay từ đầu, đừng để lộ ở cuối. Nhớ CB5: không có ffprobe, đừng viết code phụ thuộc nó.
1. **Task B** (downloader) — độc lập, test riêng trước với link Bilibili/TikTok/YouTube công khai.
2. **Task C** (subtitle_extractor: `grab_preview_frame` + `extract_hardsub_ocr_srt`) — độc lập, test riêng có/không crop.
3. **Task A** (adapter autosub) — tích hợp B+C + `source_srt_override`, test CLI tay cả whisper lẫn ocr.
4. **Task D** (step4 pipeline + endpoint + `/api/autosub/prepare` + `stop-task`) — test bằng curl + SSE.
5. **Task E** (step5 merge) — test bằng curl.
6. **Task F** (UI: 2 tab + bộ chọn ROI) — test end-to-end trên trình duyệt.
7. Commit trong submodule `AIVoice` (Task A/B/C) → push → cập nhật con trỏ submodule ở repo tổng cùng Task D/E/F.
8. `pytest -q` ở repo tổng (đảm bảo không vỡ test hiện có); `python -m py_compile orchestrator/*.py`.
9. Cập nhật `README.md` mục pipeline: bổ sung Bước 4 (Autosub) & Bước 5 (Ghép), và bảng ánh xạ workflow.

## Checklist "không gây lỗi" (đọc lại trước khi kết thúc — mỗi dòng chiếu về CB/Task tương ứng)
- [ ] **CB1**: `source_srt_override` đã thêm vào `run_translation_workflow`, bước extract audio VẪN GIỮ (audio_path còn dùng ở nhánh moviepy).
- [ ] **CB2**: adapter set `config.app["openai_api_key"/"openai_base_url"/"openai_model"]` (KHÔNG phải `llm_*`); đã mở video kết quả xác nhận phụ đề LÀ TIẾNG VIỆT.
- [ ] **CB3**: adapter mới KHÔNG có dòng `from orchestrator...` nào (grep để chắc).
- [ ] **CB4**: `orchestrator/main.py` + `pipeline.py` KHÔNG import module nào từ `AIVoice/...` (grep `from app.` và `import app` để chắc); prepare đi qua subprocess `--prepare-only`.
- [ ] **CB5**: grep toàn bộ code mới không có chữ `ffprobe`.
- [ ] Mọi tiến trình con chạy `cwd="AIVoice"`, dùng `AIVoice/.venv/Scripts/python.exe`.
- [ ] `finally` giải phóng VRAM ở adapter (release_whisper_model + torch empty_cache + gc, đều bọc try/except).
- [ ] Route API khai báo TRƯỚC `app.mount("/", StaticFiles...)` (cuối main.py).
- [ ] `/api/autosub/prepare` là `def` SYNC (không `async def` + blocking subprocess).
- [ ] task_key duy nhất, guard `is_running` trước khi start; step5 thread PHẢI `q.put(None)` trong `finally`.
- [ ] `merge_videos` giữ nguyên 2 tham số cũ, `only_files` là optional; `only_files` chỉ nhận basename (chống path traversal).
- [ ] Merge: fallback re-encode đúng 1 tầng; fail thì message tiếng Việt rõ ràng.
- [ ] UI: ID đúng bảng bắt buộc (`btnStartStep4/5`, `btnStopStep4/5`, `logConsole-step4/5`); `btnStopStep5` tồn tại nhưng ẩn.
- [ ] ROI quy đổi về pixel gốc ở UI + server clamp trong biên ảnh.
- [ ] paddlepaddle bản CPU, `use_gpu=False`; paddle cài lỗi → chuyển RapidOCR ngay từ mục 0.
- [ ] Chế độ OCR đi 2 pha (prepare → step4); Whisper 1 pha.
- [ ] Không sửa `.github/workflows/*`; không commit `config.toml`; không thêm dependency vào venv orchestrator.
- [ ] Submodule AIVoice: commit + push repo con TRƯỚC, rồi cập nhật con trỏ ở repo tổng.
- [ ] `pytest -q` xanh ở repo tổng; `python -m py_compile` mọi file .py đã sửa (cả trong submodule).

## Mở rộng tương lai (ghi nhận, KHÔNG làm ở đợt này)
- VideOCR (GUI, timminator) hoặc RapidOCR làm engine thay thế/nâng cấp cho hardsub.
- Trích phụ đề mềm (embedded stream) tự động trước khi OCR (Ghi chú C0).
- Endpoint upload multipart; tải video độc lập (không qua autosub) cấp nguồn cho Bước 3.
- Cho người dùng đổi thời điểm frame preview (thanh trượt thời gian) + xem trước nhiều frame.
- Né watermark TikTok; hỗ trợ cookies cho site cần đăng nhập (Bilibili/Douyin).
- SSE đa kênh (xem đồng thời log 2 bước).
