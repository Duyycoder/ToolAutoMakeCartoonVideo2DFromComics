# 6. "Code chức năng này ở đâu?"

Hội đồng hay chỉ vào một chức năng trên màn hình rồi bảo mở code. Số dòng dưới đây đo trên mã nguồn hiện tại (01/10/2026, gồm cả phần Dashboard chưa commit), nên có thể khác số dòng ghi trong tài liệu ôn tập. Tiền tố `MC/` = `AIVoice/apps/MediaComposer/` , `ST/` = `MC/app/services/storytelling/` .

Mở sẵn trước buổi bảo vệ: `orchestrator/pipeline.py` , `orchestrator/process_manager.py` , `orchestrator/main.py` , `orchestrator/db.py` , `ST/image_generator.py` , `ST/style_lock.py` , `orchestrator/chatbot.py` , `webui/app.js` .

## 6.1 Điểm vào ứng dụng, mở cửa sổ
- **Tệp : dòng:** `run.bat` → `orchestrator/desktop.py`
- **Hàm / biến cần chỉ:** uvicorn trong thread, `webview.start()` , `_shutdown` gọi `stop_all()`

## 6.2 Khai báo FastAPI, phục vụ giao diện
- **Tệp : dòng:** `orchestrator/main.py:1374`
- **Hàm / biến cần chỉ:** `app.mount("/", StaticFiles(webui))` , `API_BASE = ""` ở `webui/app.js:2`

## 6.3 Tải model nền khi mở app
- **Tệp : dòng:** `orchestrator/model_preflight.py` , `main.py` lifespan
- **Hàm / biến cần chỉ:** marker `models/.preflight_ok`

## 6.4 Tạo truyện mới
- **Tệp : dòng:** `main.py:515` → `storage.py:70`
- **Hàm / biến cần chỉ:** `POST /api/stories` , `init_story_workspace` , `slugify` ( `storage.py:15` )

## 6.5 Ghi `story.json` + đồng bộ SQLite
- **Tệp : dòng:** `storage.py:135, 207, 214`
- **Hàm / biến cần chỉ:** `write_story_meta` , `_mirror_to_db` , `rebuild_db`

## 6.6 Lược đồ và truy vấn SQLite
- **Tệp : dòng:** `orchestrator/db.py`
- **Hàm / biến cần chỉ:** `SCHEMA` , `connect` (WAL, FK), `upsert_story` , `list_stories` , `stats`

## 6.7 Trang Thống kê / Dashboard
- **Tệp : dòng:** `main.py:222, 264` ; `webui/app.js:2101`
- **Hàm / biến cần chỉ:** `GET /api/stats` , `GET` `/api/stats/stories/{name}` , `loadStats` , `_statEsc` ( `app.js:2098` )

## 6.8 Sửa / xóa truyện (mới, chưa commit)
- **Tệp : dòng:** `main.py:288, 327` ; `storage.py:279`
- **Hàm / biến cần chỉ:** `patch_story` , `delete_story_api` , `StorageManager.delete_story`

## 6.9 Quản lý tài liệu chatbot (mới, chưa commit)
- **Tệp : dòng:** `main.py:366-420`
- **Hàm / biến cần chỉ:** `GET/PUT/DELETE /api/kb/{fname}` , `_kb_path` (regex chống `..` ), `_reload_kb`

## 6.10 Dọn dữ liệu tạm
- **Tệp : dòng:** `main.py:231` ; `storage.py:242` ; `orchestrator/cleanup.py`
- **Hàm / biến cần chỉ:** `cleanup_tasks(keep_days, dry_run)` , `PROTECTED_DIRS = ("contexts",` `"character_loras")`

## 6.11 Chạy Bước 1 (route)
- **Tệp : dòng:** `main.py:624`
- **Hàm / biến cần chỉ:** `_reject_if_auto_running` ( `main.py:65` ), `process_mgr.is_running`

## 6.12 Bước 1: ba nguồn truyện, nối cào → dịch
- **Tệp : dòng:** `pipeline.py:145, 230, 296, 343`
- **Hàm / biến cần chỉ:** `start_step_1_crawl_translate` , `on_crawl_completed` , `_copy_local` , `start_ai_write`

## 6.13 Sáng tác truyện bằng AI
- **Tệp : dòng:** `orchestrator/story_writer.py:24`
- **Hàm / biến cần chỉ:** `generate_story` , rolling summary 2.500 ký tự

## 6.14 Chuẩn hóa tên chương nguồn local
- **Tệp : dòng:** `orchestrator/chapter_naming.py`
- **Hàm / biến cần chỉ:** `normalize_dir`

## 6.15 Crawler Selenium, lưu trạng thái tải tiếp
- **Tệp : dòng:** `toolCaoTruyen/core/crawler_engine.py`
- **Hàm / biến cần chỉ:** cờ Chrome, `.crawler_state.json` , `visited_urls`

## 6.16 Parser trang nguồn, registry nguồn
- **Tệp : dòng:** `toolCaoTruyen/sources/shuba69.py` , `sources/registry.py:7`
- **Hàm / biến cần chỉ:** `BaseSourceParser` , `SOURCES` , `get_source`

## 6.17 Dịch bằng Ollama, vá chữ Hán
- **Tệp : dòng:** `toolCaoTruyen/translator/ollama_translator.p` `y`
- **Hàm / biến cần chỉ:** chunk `67-101` , Zero Tolerance `106` , nới ≤ 5 ký tự `709-714` , report `.translation_report.json`

## 6.18 Glossary
- **Tệp : dòng:** `toolCaoTruyen/translator/glossary_manager.py`
- **Hàm / biến cần chỉ:** gộp idioms < global < story, chỉ thêm key mới

## 6.19 Chạy Bước 2 TTS
- **Tệp : dòng:** `main.py:648` → `pipeline.py:402` → `AIVoice/adapter_tts_cli.py`
- **Hàm / biến cần chỉ:** `start_step_2_tts` , `log_json` ( `adapter_tts_cli.py:12` )

## 6.20 Chunk văn bản TTS, chuẩn hóa LUFS
- **Tệp : dòng:** `AIVoice/src/utils/text.py:36` ; `src/utils/audio.py:122-175`
- **Hàm / biến cần chỉ:** `chunk_text` , `pyln.normalize.loudness` , kẹp 0,98

## 6.21 Các engine TTS
- **Tệp : dòng:** `AIVoice/src/engines/{edge,piper,kokoro,viene` `u,clone}.py`
- **Hàm / biến cần chỉ:** `BaseTTSEngine.generate`

## 6.22 Chạy Bước 3, ghi tham số SD, tự chạy lại khi crash native
- **Tệp : dòng:** `main.py:663` → `pipeline.py:509` ; `mediacomposer_config.py:79` ; `orchestrator/ma_thoat.py`
- **Hàm / biến cần chỉ:** `start_step_3_video` , `apply_sd_params` , `LIMITS` , `NATIVE_CRASH_CODES`

## 6.23 Hoàn tất Bước 3 + ghép video tổng
- **Tệp : dòng:** `pipeline.py:109`
- **Hàm / biến cần chỉ:** `_finalize_video_task`

## 6.24 Adapter Bước 3, tắt Whisper
- **Tệp : dòng:** `MC/adapter_video_cli.py:71, 101, 269`
- **Hàm / biến cần chỉ:** `count_incomplete_items` , `--render-mode` (mặc định classic), `use_whisper: False`

## 6.25 Batch 2-pass, chạy tiếp
- **Tệp : dòng:** `ST/batch_video_runner.py:74, 101, 216`
- **Hàm / biến cần chỉ:** `_reconcile_video_done` , `scan_batch_dir` , `run_batch` (Pass A/B), `batch_state.json`

## 6.26 Tách cảnh bằng LLM
- **Tệp : dòng:** `ST/semantic_scene_splitter.py:53, 182, 280`
- **Hàm / biến cần chỉ:** `split_scenes_semantic` , `_call_llm_boundaries` , `_boundaries_to_ranges` , `_normalize_ranges`

## 6.27 Chia thời lượng cảnh, sinh SRT
- **Tệp : dòng:** `ST/srt_mapper.py:197, 322, 335`
- **Hàm / biến cần chỉ:** `_fallback_proportional_duration` , `_assign_proportional` , `_fix_monotonic`

## 6.28 Sinh prompt, Director's Note
- **Tệp : dòng:** `ST/llm_prompter.py`
- **Hàm / biến cần chỉ:** `generate_prompts_batch` , `AllPromptsFailedError`

## 6.29 Khóa phong cách
- **Tệp : dòng:** `ST/style_lock.py:62, 103`
- **Hàm / biến cần chỉ:** `strip_style_drift` , `build_locked_prompt`

## 6.30 Sinh ảnh SD, LoRA, Hyper-SD, sửa dải đen
- **Tệp : dòng:** `ST/image_generator.py:23, 32, 62, 204, 318,` `381, 475, 896`
- **Hàm / biến cần chỉ:** `QUALITY_MODE_MIN_STEPS` , `VAE_TILING_MIN_EDGE` , `StorytellingPipeline` , `safety_checker=None` , `has_dead_region` , `_configure_mode` , `set_adapters` , `release`

## 6.31 Chọn cấu hình theo VRAM
- **Tệp : dòng:** `ST/hardware_adapter.py:16, 58`
- **Hàm / biến cần chỉ:** `get_hardware_config` , ngưỡng 7,0 GB

## 6.32 LoRA nhân vật tự động, train
- **Tệp : dòng:** `ST/character_bootstrap.py` , `ST/lora_trainer.py` , `MC/scripts/train_character_lora.py:157-163`
- **Hàm / biến cần chỉ:** `has_trained_lora` , loss MSE

## 6.33 Face detailer
- **Tệp : dòng:** `ST/face_detailer.py:387-406` ; `MC/scripts/detect_faces_cli.py`
- **Hàm / biến cần chỉ:** 3 cổng chất lượng

## 6.34 Studio: cổng alpha, ghép lớp, unify
- **Tệp : dòng:** `ST/studio/studio_pipeline.py:31-32, 81, 415` ; `studio/matting.py:193` ; `studio/compositor.py:79` ; `studio/unify_pass.py:26, 57`
- **Hàm / biến cần chỉ:** `_MIN/_MAX_COVERAGE` , `MatteQualityError` , `alpha_coverage` , `composite` , `MAX_SAFE_STRENGTH` , `unify_frame`

## 6.35 Upscale Real- ESRGAN, chống khung đen
- **Tệp : dòng:** `ST/postprocess.py:43, 71`
- **Hàm / biến cần chỉ:** `_use_fp16 = False` , `run_realesrgan`

## 6.36 Dựng video ffmpeg, NVENC fallback
- **Tệp : dòng:** `ST/video_assembler.py:82, 117`
- **Hàm / biến cần chỉ:** `_run_ffmpeg_with_nvenc_fallback` , `assemble_video`

## 6.37 Bước 4 ghép video, chống path traversal
- **Tệp : dòng:** `main.py:874` → `pipeline.py:816` → `orchestrator/video_merger.py:6, 15`
- **Hàm / biến cần chỉ:** `start_step_5_merge` , `_select_files` , `merge_videos`

## 6.38 Autosub (Whisper, OCR, lồng tiếng)
- **Tệp : dòng:** `main.py:771, 804` ; `MC/adapter_autosub_cli.py` ; `MC/app/services/subtitle.py:40`
- **Hàm / biến cần chỉ:** `word_timestamps=True` , VAD

## 6.39 Spawn, đọc log, dừng tiến trình
- **Tệp : dòng:** `orchestrator/process_manager.py:22, 126,` `151, 187, 192, 204, 275`
- **Hàm / biến cần chỉ:** `start_process` , `_kill_process_tree` ( `taskkill /T /F` ), `stop_process` , `was_user_stopped` , `stop_all` , `is_running` , `get_logs_generator`

## 6.40 Endpoint SSE log, trạng thái task
- **Tệp : dòng:** `main.py:698, 707`
- **Hàm / biến cần chỉ:** `StreamingResponse(media_type="text/event-` `stream")`

## 6.41 Dừng bước
- **Tệp : dòng:** `main.py:681, 919`
- **Hàm / biến cần chỉ:** `/api/pipeline/stop` , `/api/pipeline/stop-` `task`

## 6.42 Chạy tự động 1→4
- **Tệp : dòng:** `main.py:720, 735, 739` ; `orchestrator/auto_run.py:13, 20, 58, 121`
- **Hàm / biến cần chỉ:** `CHAIN_STEPS` , `DISPLAY_NO` , `start` , `_wait_step`

## 6.43 Phía giao diện: gọi API, mở SSE, nối lại khi reload
- **Tệp : dòng:** `webui/app.js:1224, 1343, 238, 1323, 1296,` `453`
- **Hàm / biến cần chỉ:** `postPipelineAction` , `streamLogs` , `restoreRunningTasks` , `appendConsoleLog` , `toggleFormButtons` , `INTERNAL_STEP_BY_DISPLAY`

## 6.44 Đồng bộ tab Cấu hình chung
- **Tệp : dòng:** `webui/app.js:1734` ; `main.py:218, 505, 747,` `751`
- **Hàm / biến cần chỉ:** `buildConfigMirror` , `/api/config` , `/api/ui-` `settings`

## 6.45 Chọn GPU theo tên card (mới 01/10)
- **Tệp : dòng:** `main.py:442` ; `pipeline.py_gpu_count`
- **Hàm / biến cần chỉ:** `nvidia-smi --query-gpu` , bỏ `cuda:N` không tồn tại

## 6.46 Chatbot: chấm điểm, cổng GPU, router
- **Tệp : dòng:** `orchestrator/chatbot.py:136, 259, 383, 510,` `561, 588`
- **Hàm / biến cần chỉ:** `_build_idf` , `select_kb` , `lookup_only` , `build_system_prompt` , `get_gpu_weight` , `route_intent`

## 6.47 Endpoint chat, 409 khi GPU bận, stream
- **Tệp : dòng:** `main.py:1003-1224, 1233`
- **Hàm / biến cần chỉ:** `/api/chat` , `/api/chat/unload`

## 6.48 Chỉ mục tri thức FTS5
- **Tệp : dòng:** `orchestrator/kb_index.py:13-22, 33-46`
- **Hàm / biến cần chỉ:** `SCHEMA` , `build_index` , `search` (BM25)

## 6.49 Client LLM, stream, nhả VRAM
- **Tệp : dòng:** `orchestrator/llm.py:20, 92, 117, 192`
- **Hàm / biến cần chỉ:** `resolve_llm` , `chat` , `chat_stream_ollama` , `unload_ollama`

## 6.50 Widget chat phía client
- **Tệp : dòng:** `webui/chat.js:19, 28, 397-436`
- **Hàm / biến cần chỉ:** `escapeHTML` , `renderMarkdown` , `sendMessage` ( `AbortController` , `getReader` )

## 6.51 Giá trị mặc định cấu hình
- **Tệp : dòng:** `orchestrator/config.py:10, 14`
- **Hàm / biến cần chỉ:** `DEFAULT_OLLAMA_MODEL` , `SD_TUNING_DEFAULTS`

## 6.52 Test, CI, bộ cài
- **Tệp : dòng:** `tests/` (pytest), `.github/workflows/ci.yml` , `release.yml` , `installer/` , `setup.bat`
- **Hàm / biến cần chỉ:** `pytest.ini`
