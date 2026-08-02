# Tham số thực tế của ứng dụng

> Tệp này được SINH TỰ ĐỘNG từ `webui/index.html` và `orchestrator/config.py`
> bằng `scripts/gen_kb_from_project.py`. Không sửa tay — sửa mã nguồn rồi chạy lại.
> Mọi lựa chọn liệt kê ở đây là lựa chọn CÓ THẬT trên giao diện.

## Tên các bước trên giao diện

Số hiệu hiển thị cho người dùng KHÔNG trùng tên hàm trong mã nguồn:

| Người dùng thấy | Mã nội bộ |
|---|---|
| Bước 1: Nguồn & Dịch | `step1` |
| Bước 2: Sinh Giọng | `step2` |
| Bước 3: Dựng Hoạt Hình | `step3` |
| Bước 4: Ghép Video | `step5` |
| Tự Động Tạo Phụ Đề | `step4` |
| Cấu Hình Chung | `settings` |

## Lựa chọn hợp lệ — Bước 1: Nguồn & Dịch

**Nguồn truyện** (`s1Source`) — các giá trị hợp lệ:
- `local`: 📁 Thư mục cục bộ (.md / .txt)
- `ai_write`: ✍️ Sáng tác bằng AI (LLM cục bộ)
- `69shuba`: Web: 69shu (Tiếng Trung)
- `metruyenchu`: Web: Mê Truyện Chữ (Tiếng Việt)
- `tangthuvien`: Web: Tàng Thư Viện

**Thể loại truyện (cho dịch thuật)** (`s1Genre`) — các giá trị hợp lệ:
- `tien_hiep`: Tiên Hiệp / Huyền Huyễn
- `ngon_tinh`: Ngôn Tình / Đô Thị
- `khoa_huyen`: Khoa Huyễn / Võng Du

**Bộ máy dịch (Translator)** (`s1Engine`) — các giá trị hợp lệ:
- `gemini_api`: Gemini Offline (Local Server / Free API)
- `gemini`: Gemini Online (Yêu cầu API Key)
- `ollama`: Ollama Local (Mô hình Offline)

**Model Ollama** (`s1OllamaModel`) — các giá trị hợp lệ:
- `qwen2.5:7b-instruct`: qwen2.5:7b-instruct

**Engine trích xuất từ điển** (`s1GlossaryEngine`) — các giá trị hợp lệ:
- `gemini`: Gemini API (Online)
- `ollama`: Ollama (Offline Local)
- `gemini_api`: Gemini API (Offline/Local)
- `same_as_trans`: Sử dụng cùng Engine dịch thuật

## Lựa chọn hợp lệ — Bước 2: Sinh Giọng

**Cấu hình mẫu (Preset)** (`s2Preset`) — các giá trị hợp lệ:
- `default`: Mặc định (Edge-TTS NamMinh)
- `fast`: Đọc Nhanh (Edge-TTS NamMinh 1.15x)
- `female_reading`: Giọng Nữ (Edge-TTS HoaiMy)
- `offline_cloning`: Nhân Bản Giọng (Local XTTSv2 - GPU)
- `offline_fast`: Offline Nhanh (Local Piper - CPU/GPU)
- `kokoro_vi`: Local Kokoro Vietnamese (GPU)
- `vieneu`: Local VieNeu TTS (GPU)

**Bộ máy TTS (Engine)** (`s2Engine`) — các giá trị hợp lệ:
- `edge`: Edge-TTS (Online Microsoft)
- `piper`: Piper (Offline ONNX)
- `clone`: XTTSv2 (Local Voice Cloning)
- `kokoro`: Kokoro-Vietnamese (Offline)
- `vieneu`: VieNeu-TTS (Offline)

**Giọng đọc / Mã ngôn ngữ** (`s2Voice`) — các giá trị hợp lệ:
- `vi-VN-NamMinhNeural`: vi-VN-NamMinhNeural (Nam)
- `vi-VN-HoaiMyNeural`: vi-VN-HoaiMyNeural (Nữ)

**Chế độ VieNeu-TTS (Mode)** (`s2VieneuMode`) — các giá trị hợp lệ:
- `v3turbo`: v3turbo (ONNX - Siêu tốc CPU)
- `standard`: standard (PyTorch - Chất lượng cao)

**Ngữ điệu / Biểu cảm (Emotion)** (`s2VieneuEmotion`) — các giá trị hợp lệ:
- `natural`: Tự nhiên (Natural)
- `happy`: Vui vẻ (Happy)
- `sad`: Buồn (Sad)
- `angry`: Tức giận (Angry)
- `storytelling`: Đọc truyện (Storytelling)

**Thiết Bị Xử Lý (Device)** (`s2Device`) — các giá trị hợp lệ:
- `cuda`: GPU (CUDA)
- `cpu`: CPU

## Lựa chọn hợp lệ — Bước 3: Dựng Hoạt Hình

**Thể loại truyện (Làm context cho AI)** (`s3Genre`) — các giá trị hợp lệ:
- `tien_hiep`: Tiên Hiệp / Cổ Trang
- `ngon_tinh`: Ngôn Tình / Đô Thị
- `khoa_huyen`: Khoa Huyễn / Viễn Tưởng

**Thiết bị xử lý Video (GPU)** (`s3GpuDevice`) — các giá trị hợp lệ:
- `auto`: Tự động nhận diện
- `cuda:0`: NVIDIA GPU 0
- `cuda:1`: NVIDIA GPU 1
- `cpu`: CPU (Rất chậm)

**Phong cách hình ảnh (Style)** (`s3Style`) — các giá trị hợp lệ:
- `thuy_mac`: Thủy Mặc (Mực tàu — có LoRA riêng, khuyên dùng)
- `flat_anime`: Anime 2D Flat (Lineart)
- `anime_2d`: Anime 2D Truyền Thống
- `xianxia`: Xianxia / Cổ Trang Trung Hoa
- `storyboard`: Storyboard Flat Pastel
- `storyboard_min`: Storyboard Tối Giản
- `watercolor`: Watercolor (Màu nước loang)
- `comic`: Comic / Truyện Tranh Mỹ
- `manga`: Manga (Trắng Đen)
- `chibi`: Chibi (Dễ thương)
- `cinematic`: Cinematic (Điện ảnh)
- `photorealistic`: Photorealistic (Chân thực)
- `oil_painting`: Sơn Dầu / Oil Painting
- `pixel_art`: Pixel Art
- `stickman`: Stickman / Người Que

**Mô hình SD Checkpoint** (`s3Checkpoint`) — các giá trị hợp lệ:
- `anything-v5`: Anything V5 (Anime)
- `dreamshaper-8`: DreamShaper 8 (Semi-Realistic)
- `majicmix-realistic`: MajicMix Realistic
- `cetus-mix`: Cetus-Mix (Anime)
- `rpg-v4`: RPG v4 (Fantasy)
- `meinamix`: MeinaMix (Anime)

**Engine LLM Kịch bản & Prompt** (`s3LlmEngine`) — các giá trị hợp lệ:
- `gemini_api`: Gemini Offline (Local Server / Free API)
- `gemini`: Gemini Online (Yêu cầu API Key)
- `ollama`: Ollama (Local)

**Model Ollama** (`s3OllamaModel`) — các giá trị hợp lệ:
- `qwen2.5:3b-instruct`: qwen2.5:3b-instruct

**Chế độ dựng ảnh (Render Mode)** (`s3RenderMode`) — các giá trị hợp lệ:
- `classic`: Classic — 1 ảnh/cảnh (SD vẽ chung, ổn định)
- `studio`: Studio — render theo lớp: nền + nhân vật riêng rồi ghép (thử nghiệm)

**Cấu hình VRAM** (`s3HardwareProfile`) — các giá trị hợp lệ:
- `auto`: Tự động phát hiện (Auto)
- `cuda_low`: Tiết kiệm VRAM (6GB) - Chậm
- `cuda_high`: Tối đa tốc độ (8GB+) - Nhanh nhưng dễ sập

## Lựa chọn hợp lệ — Tự Động Tạo Phụ Đề

**Nền tảng** (`s4Platform`) — các giá trị hợp lệ:
- `generic`: Tự động nhận diện / Khác
- `bilibili`: Bilibili
- `tiktok`: TikTok
- `douyin`: Douyin
- `youtube`: YouTube

**Ngôn ngữ gốc của Video** (`s4SourceLang`) — các giá trị hợp lệ:
- `English`: Tiếng Anh (English)
- `Chinese`: Tiếng Trung (Chinese)

**Nguồn tạo phụ đề** (`s4SubSource`) — các giá trị hợp lệ:
- `whisper`: Phiên âm từ âm thanh (Whisper)
- `ocr`: Tách chữ cháy trên hình (OCR)

**Phương pháp ghi phụ đề** (`s4BurnMethod`) — các giá trị hợp lệ:
- `ffmpeg`: FFmpeg native filter (Nhanh)
- `moviepy`: MoviePy filter (Tương thích tốt)

**Bộ máy TTS (Engine)** (`s4TtsEngine`) — các giá trị hợp lệ:
- `edge`: Edge-TTS (Online Microsoft)
- `piper`: Piper (Offline ONNX)
- `clone`: XTTSv2 (Local Voice Cloning)
- `kokoro`: Kokoro-Vietnamese (Offline)
- `vieneu`: VieNeu-TTS (Offline)

**Phông chữ (Font)** (`s4FontName`) — các giá trị hợp lệ:
- `Montserrat-Bold.ttf`: Montserrat Bold
- `Montserrat-Regular.ttf`: Montserrat Regular
- `BeVietnamPro-Bold.ttf`: BeVietnam Pro Bold
- `BeVietnamPro-SemiBold.ttf`: BeVietnam Pro SemiBold
- `BeVietnamPro-Regular.ttf`: BeVietnam Pro Regular
- `Arial-Bold.ttf`: Arial Bold
- `Arial-Regular.ttf`: Arial Regular
- `Charm-Bold.ttf`: Charm Bold
- `Charm-Regular.ttf`: Charm Regular
- `STHeitiMedium.ttc`: STHeiti Medium
- `MicrosoftYaHeiBold.ttc`: Microsoft YaHei Bold
- `UTM Kabel KT.ttf`: UTM Kabel KT

**Kiểu nền (Background Style)** (`s4BgStyle`) — các giá trị hợp lệ:
- `None`: Không nền (None)
- `Box`: Có nền hộp (Box)

**Vị trí phụ đề (Position)** (`s4SubPosition`) — các giá trị hợp lệ:
- `bottom`: Dưới (Bottom)
- `top`: Trên (Top)
- `center`: Giữa (Center)
- `custom`: Tùy chọn (Custom Y %)

**Engine LLM Dịch Phụ Đề** (`s4LlmEngine`) — các giá trị hợp lệ:
- `gemini_api`: Gemini Offline (Local Server / Free API)
- `gemini`: Gemini Online (Yêu cầu API Key)
- `ollama`: Ollama (Local)

**Model Ollama** (`s4OllamaModel`) — các giá trị hợp lệ:
- `qwen2.5:3b-instruct`: qwen2.5:3b-instruct

## Lựa chọn hợp lệ — Cấu Hình Chung

**TTS Engine Mặc định** (`cfgTtsEngine`) — các giá trị hợp lệ:
- `edge`: Edge-TTS
- `piper`: Piper
- `clone`: XTTSv2
- `kokoro`: Kokoro
- `vieneu`: VieNeu

**Style Mặc định** (`cfgVideoStyle`) — các giá trị hợp lệ:
- `thuy_mac`: Thủy Mặc (có LoRA riêng)
- `flat_anime`: Anime 2D Flat
- `anime_2d`: Anime 2D Truyền Thống
- `xianxia`: Xianxia / Cổ Trang
- `storyboard`: Storyboard Flat Pastel
- `watercolor`: Watercolor
- `manga`: Manga (Trắng Đen)
- `comic`: Comic Mỹ

**Step 3 LLM Engine Mặc định** (`cfgVideoLlmEngine`) — các giá trị hợp lệ:
- `gemini_api`: Gemini Offline (Local)
- `gemini`: Gemini Online (AI Studio)
- `ollama`: Ollama (Local)

**Trạng thái Trợ Lý AI** (`cfgChatbotEnabled`) — các giá trị hợp lệ:
- `true`: Bật trợ lý
- `false`: Tắt trợ lý

**Chặn chat khi GPU bận** (`cfgChatbotBlockBusy`) — các giá trị hợp lệ:
- `true`: Có (Cảnh báo 409 + Tra cứu 0-VRAM)
- `false`: Không (Cho phép chạy đè)

**Tự nhả VRAM trước khi chạy Pipeline** (`cfgChatbotAutoUnload`) — các giá trị hợp lệ:
- `true`: Có (Tự động unload Ollama)
- `false`: Không

## Giá trị mặc định trong cấu hình

**Khối `tts`:**
- `default_engine` = "edge"
- `default_voice` = "vi-VN-NamMinhNeural"
- `kokoro_voice` = "thuc_trinh"
- `vieneu_mode` = "v3turbo"
- `vieneu_voice` = "Ngọc Lan"
- `vieneu_emotion` = ""
- `normalize` = True
- `target_lufs` = -14.0
- `speed` = 1.0
- `fade_in` = 0.1
- `fade_out` = 0.1
- `silence_duration` = 0.3
- `device` = "auto"
- `use_cache` = False
- `cache_threshold` = 0.95
- `temperature` = 0.3

**Khối `video`:**
- `default_style` = "anime_2d_flat"
- `use_gpu` = True
- `default_checkpoint` = "anything-v5"
- `bgm_path` = ""
- `bgm_volume` = 0.15
- `default_llm_engine` = "gemini_api"
- `default_llm_model` = DEFAULT_GEMINI_PROXY_MODEL
- `downloader_cookies` = ""
- `genre` = "tien_hiep"
- `enable_upscale` = True
- `burn_subtitles` = False
- `use_semantic_split` = True
- `extract_characters` = True
- `enable_face_detailer` = False
- `render_mode` = "studio"
- `hardware_profile` = "auto"
- `device` = "auto"

**Khối `translate`:**
- `default_engine` = "gemini_api"
- `ollama_model` = "qwen2.5:7b-instruct"
- `gemini_offline_model` = "gemini-2.5-flash"
- `genre` = "tien_hiep"
- `auto_translate` = True
- `auto_extract` = True
- `glossary_extract_engine` = "gemini"
- `glossary_extract_ollama_model` = ""

**Khối `chatbot`:**
- `enabled` = True
- `model` = "qwen2.5:3b"
- `share_model_with_step3` = False
- `base_url` = ""
- `temperature` = 0.4
- `top_p` = 0.9
- `repeat_penalty` = 1.05
- `num_predict` = 512
- `num_ctx` = 8192
- `max_history_turns` = 12
- `kb_token_budget` = 3000
- `kb_min_score` = 0.65
- `kb_sticky_per_session` = True
- `keep_alive` = "5m"
- `prewarm_on_open` = True
- `idle_unload_minutes` = 10
- `auto_unload_before_pipeline` = True
- `block_when_busy` = True
- `autostart_ollama` = True
- `max_sessions` = 20
- `session_ttl_minutes` = 120
