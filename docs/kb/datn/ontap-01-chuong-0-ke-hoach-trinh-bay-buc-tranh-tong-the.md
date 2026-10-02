# Chương 0. Kế hoạch trình bày & bức tranh tổng thể

Chương mở đầu của bộ tài liệu ôn bảo vệ. Chương này không đi sâu lý thuyết. Nó cho em ba thứ: (1) lộ trình học 13 chương còn lại, (2) kịch bản buổi thuyết trình 15–20 phút kèm demo, (3) bức tranh toàn hệ thống và luồng hoạt động end-to- end, từ lúc bấm nút đến khi có file video cuối, đối chiếu với code thật ( `orchestrator/pipeline.py` , `orchestrator/storage.py` , `AIVoice/apps/MediaComposer/...` ).

Quy ước: `path:LINE` là vị trí trong repo. "Bước 1–4" là số hiển thị trên UI. `step1/step2/step3/step5` là tên task nội bộ trong code.

## 1. Thông tin đề tài (để nói cho đúng từng chữ)

- Mục · Nội dung (lấy từ bìa báo cáo `KTPM_2022600930_DaoKhuongDuy_baocao.pdf` )
- Tên đề tài · Xây dựng platform đa tiến trình cho quy trình tự động sản xuất video hoạt hình 2D từ truyện chữ bằng các mô hình AI local
- Sinh viên · Đào Khương Duy, MSV 2022600930, lớp 2022DHKTPM01, khóa 2022–2026
- CBHD · ThS. Trần Thanh Hùng
- Ngành · Kỹ thuật phần mềm, Trường CNTT&TT, ĐH Công nghiệp Hà Nội
- Máy đo/demo (Bảng 5.1 báo cáo) · Windows 11, Python 3.11, i7-12650H, RAM 15,6 GB, RTX 3060 Laptop 6 GB VRAM

Lưu ý chính tả: trên bìa báo cáo in "FLATFORM" nhưng lời cam đoan viết "platform". Nếu hội đồng hỏi thì nhận là lỗi đánh máy trên bìa.

## 2. Lộ trình học 13 chương

### 2.1 Thứ tự đọc khuyến nghị

Không nên đọc theo số chương. Nên đọc theo dòng chảy của một câu chuyện: kiến trúc → dữ liệu chạy qua từng bước → phần lõi AI → phần kỹ thuật phần mềm → ngân hàng câu hỏi.

- **Thứ tự:** 1 · **Chương:** ch00 (chương này) · **Nội dung:** Bức tranh tổng + luồng end-to-end · **Thời gian gợi ý:** 1 giờ · **Ưu tiên:** ★★★ · **Hội đồng hay hỏi?:** Luôn luôn (câu mở màn)
- **Thứ tự:** 2 · **Chương:** ch01 Kiến trúc & Orchestrator · **Nội dung:** FastAPI, subprocess, state machine, VRAM · **Thời gian gợi ý:** 3 giờ · **Ưu tiên:** ★★★ · **Hội đồng hay hỏi?:** Rất cao: "vì sao đa tiến trình?"
- **Thứ tự:** 3 · **Chương:** ch07 Diffusion & Stable Diffusion · **Nội dung:** Nguyên lý sinh ảnh, CFG, scheduler, Hyper-SD · **Thời gian gợi ý:** 4 giờ · **Ưu tiên:** ★★★ · **Hội đồng hay hỏi?:** Rất cao: "sinh ảnh hoạt động thế nào?"
- **Thứ tự:** 4 · **Chương:** ch06 Phân cảnh & sinh prompt · **Nội dung:** LLM lập kế hoạch cảnh, style lock · **Thời gian gợi ý:** 2,5 giờ · **Ưu tiên:** ★★★ · **Hội đồng hay hỏi?:** Cao
- **Thứ tự:** 5 · **Chương:** ch08 LoRA & nhất quán nhân vật · **Nội dung:** LoRA, IP-Adapter, face detailer · **Thời gian gợi ý:** 3 giờ · **Ưu tiên:** ★★★ · **Hội đồng hay hỏi?:** Cao: "giữ mặt nhân vật thế nào?"
- **Thứ tự:** 6 · **Chương:** ch04 Dịch bằng LLM · **Nội dung:** Transformer, Ollama, quantization, glossary · **Thời gian gợi ý:** 3 giờ · **Ưu tiên:** ★★★ · **Hội đồng hay hỏi?:** Cao: "LLM là gì, vì sao chạy local?"
- **Thứ tự:** 7 · **Chương:** ch12 Chatbot RAG · **Nội dung:** IDF, gating, NDJSON, agent · **Thời gian gợi ý:** 2,5 giờ · **Ưu tiên:** ★★☆ · **Hội đồng hay hỏi?:** Cao (vì là đóng góp số 3)
- **Thứ tự:** 8 · **Chương:** ch13 Kỹ thuật phần mềm · **Nội dung:** Test, CI, installer, bảo mật · **Thời gian gợi ý:** 2 giờ · **Ưu tiên:** ★★☆ · **Hội đồng hay hỏi?:** Cao với hội đồng KTPM
- **Thứ tự:** 9 · **Chương:** ch05 TTS · **Nội dung:** Edge/Piper/VITS/XTTS, LUFS · **Thời gian gợi ý:** 2,5 giờ · **Ưu tiên:** ★★☆ · **Hội đồng hay hỏi?:** Trung bình
- **Thứ tự:** 10 · **Chương:** ch11 Dựng video FFmpeg · **Nội dung:** concat demuxer, codec, merge · **Thời gian gợi ý:** 1,5 giờ · **Ưu tiên:** ★★☆ · **Hội đồng hay hỏi?:** Trung bình: "hoạt hình hay slideshow?"
- **Thứ tự:** 11 · **Chương:** ch09 Studio compositing · **Nội dung:** Matting, alpha, layout, unify · **Thời gian gợi ý:** 2 giờ · **Ưu tiên:** ★★☆ · **Hội đồng hay hỏi?:** Trung bình (dễ bị hỏi xoáy, xem mục 7)
- **Thứ tự:** 12 · **Chương:** ch02 WebUI & SSE · **Nội dung:** SPA, SSE, EventSource · **Thời gian gợi ý:** 1,5 giờ · **Ưu tiên:** ★☆☆ · **Hội đồng hay hỏi?:** Trung bình
- **Thứ tự:** 13 · **Chương:** ch03 Crawler · **Nội dung:** Selenium, BS4, bản quyền · **Thời gian gợi ý:** 1,5 giờ · **Ưu tiên:** ★☆☆ · **Hội đồng hay hỏi?:** Thấp về kỹ thuật, cao về đạo đức/bản quyền
- **Thứ tự:** 14 · **Chương:** ch10 Whisper & phụ đề · **Nội dung:** ASR, SRT, burn subtitle · **Thời gian gợi ý:** 1,5 giờ · **Ưu tiên:** ★☆☆ · **Hội đồng hay hỏi?:** Thấp (Autosub là công cụ rời)
- **Thứ tự:** 15 · **Chương:** ch14 Ngân hàng câu hỏi · **Nội dung:** 60+ câu hỏi, thuật ngữ, checklist · **Thời gian gợi ý:** 3 giờ + luyện nói · **Ưu tiên:** ★★★ · **Hội đồng hay hỏi?:** Dùng để luyện

Tổng khoảng 35–40 giờ. Nếu chỉ còn 3 ngày thì học theo thứ tự ưu tiên ★★★ trước: ch00 → ch01 → ch07 → ch08 → ch06 → ch04 → ch14.

### 2.2 Kế hoạch 7 ngày (ví dụ)

- **Ngày:** 1 · **Việc:** ch00 + ch01 · **Đầu ra tự kiểm tra:** Vẽ lại được sơ đồ 3 tầng và luồng end-to-end mà không nhìn tài liệu
- **Ngày:** 2 · **Việc:** ch07 · **Đầu ra tự kiểm tra:** Giải thích được forward/reverse diffusion, latent, U-Net, CFG bằng lời của mình trong 3 phút
- **Ngày:** 3 · **Việc:** ch06 + ch08 · **Đầu ra tự kiểm tra:** Nói được một cảnh đi từ đoạn văn → prompt → ảnh ra sao; LoRA rank 16 nghĩa là gì
- **Ngày:** 4 · **Việc:** ch04 + ch05 · **Đầu ra tự kiểm tra:** Nói được Transformer/attention, quantization Q8_0, VITS, LUFS
- **Ngày:** 5 · **Việc:** ch12 + ch13 · **Đầu ra tự kiểm tra:** Đọc thuộc số đo: 178 test, 25/28 QA, 7/8 từ chối; IDF công thức
- **Ngày:** 6 · **Việc:** ch02, ch03, ch09, ch10, ch11 · **Đầu ra tự kiểm tra:** Trả lời được "slideshow hay hoạt hình", "cào truyện có vi phạm bản quyền không"
- **Ngày:** 7 · **Việc:** ch14 + tập thuyết trình 2 lần có bấm giờ + chạy thử demo · **Đầu ra tự kiểm tra:** Dưới 20 phút, demo có phương án dự phòng

### 2.3 Cách học mỗi chương

- 1. Đọc mục "Vai trò trong hệ thống" để biết chương nằm ở đâu trong luồng. 2. Đọc lý thuyết. Sau mỗi mục, gập tài liệu lại và tự giảng bằng một ví dụ đời thường. 3. Mở đúng file code được dẫn và đọc lại đoạn đó ít nhất một lần. Hội đồng có thể yêu cầu mở code. 4. Tự trả lời mục "Câu hỏi hội đồng" trước khi đọc đáp án.

5. Nói to phần "Tóm tắt 1 phút" và bấm giờ.

## 3. Kế hoạch bài thuyết trình bảo vệ (khoảng 18 phút)

### 3.1 Nguyên tắc

Một thông điệp xuyên suốt: "Không mô hình AI nào tự làm trọn việc biến truyện thành video. Phần khó là điều phối nhiều mô hình trên một máy 6 GB VRAM sao cho quan sát được, dừng được và chạy lại được." Câu này khớp với báo cáo (mục 1.1: "Phần khó nằm ở điều phối"). Nói điểm yếu trước khi bị hỏi: slideshow tĩnh, Studio chưa là mặc định trong code, TTS mặc định là Edge (online). Tự nêu ra thì được đánh giá là trung thực. Để hội đồng phát hiện thì em bị động. Mỗi con số phải có nguồn. Xem bảng số liệu ở mục 3.4.

### 3.2 Danh sách slide và thời lượng

- **#:** 1 · **Slide:** Tiêu đề · **Thời lượng:** 0:20 · **Nội dung nói chính:** Tên đề tài, CBHD, sinh viên · **Chương tham chiếu:** —
- **#:** 2 · **Slide:** Bài toán & động lực · **Thời lượng:** 1:15 · **Nội dung nói chính:** Truyện chữ thiếu thông tin để vẽ và đọc (bao lâu, ai, ở đâu). Làm tay tốn công theo số chương. Có ba nhóm giải pháp: dịch vụ online, ComfyUI, script rời; khoảng trống là nền tảng cục bộ có trạng thái · **Chương tham chiếu:** ch00 mục 4
- **#:** 3 · **Slide:** Mục tiêu, phạm vi, đóng góp · **Thời lượng:** 1:00 · **Nội dung nói chính:** 3 đóng góp: Storytelling Studio + nhất quán nhân vật; điều phối tài nguyên none/medium/heavy + checkpoint từng bước; Trợ lý AI local có tra cứu 0-VRAM · **Chương tham chiếu:** ch00 mục 4.3
- **#:** 4 · **Slide:** Kiến trúc 3 tầng · **Thời lượng:** 2:00 · **Nội dung nói chính:** WebUI ↔ Orchestrator FastAPI ↔ worker subprocess. Orchestrator không import torch; mỗi bước GPU là một process, process thoát thì VRAM được trả hết · **Chương tham chiếu:** ch01
- **#:** 5 · **Slide:** Pipeline 4 bước + dữ liệu trung gian · **Thời lượng:** 1:15 · **Nội dung nói chính:** Sơ đồ mục 5 của chương này; nhấn mạnh file trung gian ( `.md [VI]` , `.wav` , `state.json` , `scene_XXX.png` , `.mp4` ) · **Chương tham chiếu:** ch00 mục 5
- **#:** 6 · **Slide:** Bước 1: Dịch bằng LLM · **Thời lượng:** 1:15 · **Nội dung nói chính:** Ollama chạy local, model lượng tử hóa; glossary chủ động (≤20 thuật ngữ/chunk); Zero Tolerance chữ Hán; kết quả 0/214.034 ký tự CJK trên 26 chương · **Chương tham chiếu:** ch04
- **#:** 7 · **Slide:** Bước 2: TTS · **Thời lượng:** 0:45 · **Nội dung nói chính:** Adapter pattern cho 5 engine; chunk 30 từ/240 ký tự; ghép WAV, chuẩn hóa −14 LUFS; chạy lại thì bỏ qua chương đã có WAV · **Chương tham chiếu:** ch05
- **#:** 8 · **Slide:** Bước 3a: Phân cảnh + prompt · **Thời lượng:** 1:15 · **Nội dung nói chính:** LLM chia đoạn đã đánh số thành cảnh, kiểm 3 bất biến phủ kín; thời lượng cảnh tỷ lệ số từ trên độ dài WAV thật; style lock · **Chương tham chiếu:** ch06
- **#:** 9 · **Slide:** Bước 3b: Sinh ảnh · **Thời lượng:** 2:00 · **Nội dung nói chính:** Latent diffusion SD1.5 (anything-v5), 8 bước + Hyper-SD LoRA, CFG 5.0, 768×432 → Real-ESRGAN 1920×1080. Nhất quán: text (style lock) + ảnh (IP-Adapter 0.6) + trọng số (LoRA) · **Chương tham chiếu:** ch07, ch08
- **#:** 10 · **Slide:** Studio compositing · **Thời lượng:** 0:45 · **Nội dung nói chính:** Nền và nhân vật sinh riêng, tách nền isnet-anime, ghép alpha, unify pass 0.28; không qua gate thì lùi về Classic · **Chương tham chiếu:** ch09
- **#:** 11 · **Slide:** Bước 4: Dựng & ghép video · **Thời lượng:** 0:30 · **Nội dung nói chính:** ffmpeg concat demuxer 2 lượt; merge `-c copy` ; `batch_state.json` cho resume · **Chương tham chiếu:** ch11
- **#:** 12 · **Slide:** Trợ lý AI · **Thời lượng:** 1:00 · **Nội dung nói chính:** RAG lexical IDF (không vector DB); cổng 0.75; GPU heavy → HTTP 409 + tra cứu 0- VRAM; agent chỉ đề xuất, người dùng xác nhận · **Chương tham chiếu:** ch12
- **#:** 13 · **Slide:** DEMO · **Thời lượng:** 3:30 · **Nội dung nói chính:** Xem mục 3.3 · **Chương tham chiếu:** —
- **#:** 14 · **Slide:** Kiểm thử & kết quả · **Thời lượng:** 1:15 · **Nội dung nói chính:** 178 test repo tổng + 136 test MediaComposer (chạy lại 29/09/2026); CI 2 job; VRAM đỉnh ≈ 4,0 GB; 45 s video mất ≈ 2,6 phút · **Chương tham chiếu:** ch13
- **#:** 15 · **Slide:** Hạn chế & hướng phát triển · **Thời lượng:** 1:00 · **Nội dung nói chính:** Slideshow tĩnh (→ zoompan/xfade); Studio còn thử nghiệm; chưa đo MOS/CLIP; API không auth; 1 máy đo · **Chương tham chiếu:** ch00 mục 7
- **#:** 16 · **Slide:** Kết luận · **Thời lượng:** 0:20 · **Nội dung nói chính:** Nhắc lại thông điệp điều phối + cảm ơn · **Chương tham chiếu:** —
- **Slide:** Tổng · **Thời lượng:** ≈ 19:25 · **Nội dung nói chính:** Nếu hội đồng giới hạn 15 phút: cắt slide 7, 10, 11 thành 1 slide, demo rút còn 2:30

### 3.3 Kịch bản demo (3–4 phút)

Chuẩn bị trước khi vào phòng:

Mở sẵn app bằng `run.bat` (cửa sổ WebView2 1280×840, server `127.0.0.1:8100` theo `orchestrator/desktop.py:18-20` ). Chờ `model_preflight` tải xong mô hình. Có sẵn truyện đã chạy xong trong `storage/truyen/` . Máy dev hiện có `storage/truyen/e2e_kiem_khach/` với `Chương 0001` `- [VI] Kiếm khách trên núi sương.md/.wav` , file `video/Chương 0001 - ....mp4` và các file `TongHop_*.mp4` . Chuẩn bị một thư mục truyện ngắn cục bộ (1 chương khoảng 100–200 từ, tác phẩm public domain hoặc tự viết) để demo Bước 1 nguồn `local` . Video quay sẵn toàn bộ pipeline (quay màn hình, tua nhanh phần sinh ảnh), để trên desktop và một USB.

Thứ tự demo:

- **Thứ tự:** 1 · **Thao tác:** Mở tab danh sách truyện, tạo truyện mới · **Nói gì:** "Mỗi truyện có workspace riêng: `story.json` + `raw/` + `video/` , đồng thời mirror sang SQLite" · **Thời gian:** 0:20 · **Rủi ro:** Thấp
- **Thứ tự:** 2 · **Thao tác:** Bước 1, nguồn local, bấm chạy · **Nói gì:** "Log realtime qua SSE; nguồn local để demo sạch bản quyền" · **Thời gian:** 0:30 · **Rủi ro:** Thấp (không cần mạng, không GPU)
- **Thứ tự:** 3 · **Thao tác:** Bước 2 với Piper (offline) hoặc Edge (cần mạng) cho 1 chương ngắn · **Nói gì:** "Adapter JSON-lines, log từng chunk" · **Thời gian:** 0:40 · **Rủi ro:** Edge cần Internet, nên ưu tiên Piper
- **Thứ tự:** 4 · **Thao tác:** Bấm chạy Bước 3, cho xem log 20–30 giây, rồi bấm Dừng · **Nói gì:** "Dừng bằng `taskkill /T /F` , diệt cả cây tiến trình, trạng thái chuyển CANCELLED chứ không phải FAILED" · **Thời gian:** 0:40 · **Rủi ro:** Trung bình
- **Thứ tự:** 5 · **Thao tác:** Trong lúc Bước 3 chạy (trước khi dừng), hỏi Trợ lý AI một câu · **Nói gì:** "GPU đang heavy nên server trả 409 và dùng chế độ tra cứu 0-VRAM" · **Thời gian:** 0:30 · **Rủi ro:** Trung bình
- **Thứ tự:** 6 · **Thao tác:** Mở truyện đã chạy sẵn, phát video chương + video tổng hợp · **Nói gì:** "Đây là đầu ra cuối; ảnh 1920×1080, 24 fps" · **Thời gian:** 0:40 · **Rủi ro:** Thấp
- **Thứ tự:** 7 · **Thao tác:** (Nếu còn giờ) mở `storage/tasks/video/tasks/<uuid>/` · **Nói gì:** Cho xem `state.json` , `draft_frames/` , `final_frames/` , `generated_from_script.srt` · **Thời gian:** 0:20 · **Rủi ro:** Thấp
- **Thứ tự:** Phương án dự phòng:
- **Thứ tự:** Sự cố · **Thao tác:** Cách xử lý
- **Thứ tự:** App không mở / WebView2 lỗi · **Thao tác:** `desktop.py` tự fallback sang trình duyệt. Mở `http://127.0.0.1:8100/` bằng tay
- **Thứ tự:** Ollama chưa chạy · **Thao tác:** `ollama_manager.ensure_server` tự khởi động. Nếu vẫn lỗi thì bỏ qua Bước 1 dịch, dùng nguồn local đã có `[VI]`
- **Thứ tự:** Mất mạng · **Thao tác:** Chỉ dùng Piper, Ollama, nguồn local. Không demo Edge/Gemini
- **Thứ tự:** Bước 3 quá chậm hoặc OOM · **Thao tác:** Không chờ. Dừng tác vụ, chuyển sang video quay sẵn
- **Thứ tự:** Máy trình chiếu không có GPU · **Thao tác:** Chạy video quay sẵn toàn bộ, chỉ demo live UI + chatbot tra cứu
- **Thứ tự:** Hội đồng yêu cầu xem code · **Thao tác:** Mở sẵn VS Code với 4 tab: `orchestrator/pipeline.py` , `orchestrator/process_manager.py` , `.../storytelling/image_generator.py` , `.../storytelling/style_lock.py`

### 3.4 Bảng số liệu phải nhớ (và nguồn)

- **Số liệu:** Test repo tổng · **Giá trị:** 178 passed (22 file, 21,63 s), chạy lại 29/09/2026 · **Nguồn:** ch13; báo cáo ghi 173 passed / 21 file / 7,86 s (chốt 12/09/2026)
- **Số liệu:** Test MediaComposer (GPU- free) · **Giá trị:** 136 passed trong 44,25 s · **Nguồn:** ch13
- **Số liệu:** Rò chữ Hán sau dịch · **Giá trị:** 0 / 214.034 ký tự, 26 chương · **Nguồn:** Báo cáo mục 5.5
- **Số liệu:** Trợ lý AI: truy xuất QA · **Giá trị:** 25/28 = 89,3% (ngưỡng ≥ 80%) · **Nguồn:** Báo cáo 5.5, `scripts/eval_chatbot.py`
- **Số liệu:** Trợ lý AI: từ chối ngoài phạm vi · **Giá trị:** 7/8 = 87,5% (ngưỡng ≥ 90%, chưa đạt) · **Nguồn:** Báo cáo 5.5
- **Số liệu:** VRAM đỉnh Bước 3 · **Giá trị:** ≈ 4,0 GB trên máy 6 GB · **Nguồn:** Báo cáo 5.4.2
- **Số liệu:** Thời gian Bước 3 · **Giá trị:** ≈ 2,6 phút cho video 45 s (≈ 3,47× thời lượng) · **Nguồn:** Báo cáo Bảng 5.4
- **Số liệu:** Thời gian Piper · **Giá trị:** ≈ 2,7 phút/chương · **Nguồn:** Báo cáo Bảng 5.4
- **Số liệu:** Tham số SD mặc định · **Giá trị:** 8 steps, CFG 5.0, 768×432 → 1920×1080, 24 fps, IP-Adapter 0.6 · **Nguồn:** `orchestrator/config.py:14-27`
- **Số liệu:** Dữ liệu thử hệ thống · **Giá trị:** 5 truyện, 32 chương (26 có audio, 3 có video) · **Nguồn:** Báo cáo 5.3

- Khi nói số test, dùng số trong báo cáo (173) vì đó là văn bản đã nộp. Nếu được hỏi thì bổ sung: "sau ngày chốt em thêm 1 file test, chạy lại hôm 29/09 được 178/178".

## 4. Bức tranh tổng thể

### 4.1 Bài toán

Đầu vào: một truyện chữ. Có thể là thư mục `.md/.txt` trên máy, một trang web hỗ trợ, hoặc chủ đề để LLM tự sáng tác. Đầu ra: mỗi chương một video MP4 có lời đọc tiếng Việt và ảnh minh họa theo cảnh, cộng một MP4 tổng hợp.

Vì sao khó? Truyện chữ không chứa các thông tin máy cần để làm video: một cảnh dài bao nhiêu giây, trong cảnh có ai, ở đâu, góc máy nào, nhân vật trông ra sao. Hệ thống phải tự sinh các thông tin đó (phân cảnh, prompt, hồ sơ nhân vật, timeline) trước khi sinh ảnh và âm thanh. Không có mô hình nào làm trọn chuỗi này trong một lần gọi, nên đây là bài toán ghép nối và điều phối.

### 4.2 Mục tiêu và phạm vi

- Pipeline có trạng thái, từ truyện đến MP4. Mỗi bước quan sát được (log realtime), dừng được (kill cả cây tiến trình) và chạy lại được (bỏ qua phần đã xong). Chạy cục bộ trên Windows + GPU NVIDIA phổ thông (thiết kế cho 6 GB VRAM). Người dùng vẫn duyệt kết quả trung gian. Hệ thống không thay thế họa sĩ hay biên tập viên. Ngoài phạm vi: nhiều người dùng, xác thực, phân quyền, chạy trên cloud, animation chuyển động thật (AnimateDiff/SVD).

### 4.3 Đóng góp chính (theo báo cáo, kèm cách nói trung thực)

- **Đóng góp:** Pipeline nhiều mô hình có checkpoint và luồng dữ liệu rõ ràng · **Bằng chứng trong code:** `pipeline.py` , `batch_video_runner.py` ( `batch_state.json` ), TTS bỏ qua chương có WAV · **Cách nói trung thực:** Resume nằm ở từng bước, không phải ở orchestrator
- **Đóng góp:** Sáng tác truyện nhiều chương bằng LLM có bộ nhớ tóm tắt · **Bằng chứng trong code:** `orchestrator/story_writer.py` (rolling summary 2–3 câu, giữ 2500 ký tự cuối) · **Cách nói trung thực:** Chạy bằng thread, không qua bước dịch
- **Đóng góp:** Storytelling Studio + nhất quán nhân vật · **Bằng chứng trong code:** `studio/studio_pipeline.py` , `image_generator.py` , `character_bootstrap.py` · **Cách nói trung thực:** Studio có sẵn và có cổng chất lượng, nhưng mặc định code là classic; xem mục 7
- **Đóng góp:** Điều phối tiến trình/VRAM cho máy cá nhân · **Bằng chứng trong code:** `process_manager.py` , `chatbot.get_gpu_weight` , `unload_ollama` , 2-pass batch · **Cách nói trung thực:** Đây là đóng góp chắc chắn nhất, nên nói kỹ
- **Đóng góp:** Trợ lý AI local có KB, agent, 0- VRAM · **Bằng chứng trong code:** `orchestrator/chatbot.py` , `kb_index.py` , `main.py:814-` `1043` · **Cách nói trung thực:** Truy xuất là lexical IDF, không phải vector DB
- **Đóng góp:** Tài liệu phân tích thiết kế đối chiếu được với code · **Bằng chứng trong code:** Báo cáo chương 3–4; KB 08/09 sinh tự động từ code · **Cách nói trung thực:** —

### 4.4 Kiến trúc 3 tầng

Ba ý phải nói được:

1. Tầng giao diện là SPA HTML/CSS/JS thuần do chính FastAPI phục vụ ( `main.py:1183-1185` mount `StaticFiles` ), cùng origin nên `API_BASE = ""` . 2. Tầng điều phối chỉ làm việc "nhẹ": nhận request, dựng lệnh, spawn process, đọc log, ghi trạng thái. Nó không bao giờ import torch (đã grep toàn bộ `orchestrator/*.py` ). Nhờ vậy server không giữ VRAM. 3. Tầng worker là các CLI adapter chạy bằng python của venv riêng ( `toolCaoTruyen/.venv` , `AIVoice/.venv` , xem `pipeline.py:150, 411, 525, 632` ). Worker in log dạng JSON Lines ( `log_json(event, data)` ). Kết quả thành công hay thất bại được quyết định bằng exit code.

### 4.5 Bản đồ công nghệ

- **Bước:** Khởi động · **Công nghệ:** pywebview, uvicorn, FastAPI · **Nguyên lý một câu:** Server ASGI chạy trong thread, cửa sổ WebView2 hiển thị web local · **File code chính:** `orchestrator/desktop.py` , `main.py` · **Chương:** ch01, ch02
- **Bước:** Điều phối · **Công nghệ:** `subprocess.Popen` , thread, `queue.Queue` , `taskkill /T` `/F` · **Nguyên lý một câu:** Mỗi bước nặng là một process riêng; OS thu hồi toàn bộ VRAM khi process chết · **File code chính:** `process_manager.py` · **Chương:** ch01
- **Bước:** Realtime log · **Công nghệ:** Server-Sent Events · **Nguyên lý một câu:** HTTP response không đóng, server đẩy dần từng dòng `data:` · **File code chính:** `process_manager.get_logs_generator` , `app.js` `streamLogs` · **Chương:** ch02
- **Bước:** Lưu trữ · **Công nghệ:** File JSON + SQLite (WAL, FK) · **Nguyên lý một câu:** File là nguồn sự thật; SQLite là bản mirror để thống kê · **File code chính:** `storage.py` , `db.py` · **Chương:** ch01
- **Bước:** 1a Cào truyện · **Công nghệ:** Selenium (Chrome thật), BeautifulSoup · **Nguyên lý một câu:** Trình duyệt thật vượt Cloudflare; parse DOM, theo link "下一章" · **File code chính:** `toolCaoTruyen/core/crawler_engine.py` , `sources/shuba69.py` · **Chương:** ch03
- **Bước:** 1a Nguồn local · **Công nghệ:** Regex chuẩn hóa tên chương · **Nguyên lý một câu:** Đánh số lại và gắn tên chuẩn `Chương 0001 -...` · **File code chính:** `orchestrator/chapter_naming.py` · **Chương:** ch03
- **Bước:** 1a Sáng tác AI · **Công nghệ:** LLM + rolling summary · **Nguyên lý một câu:** Viết từng chương, mang theo tóm tắt các chương trước · **File code chính:** `orchestrator/story_writer.py` · **Chương:** ch04
- **Bước:** 1b Dịch · **Công nghệ:** Transformer LLM qua Ollama (GGUF lượng tử hóa), Gemini · **Nguyên lý một câu:** Mô hình dự đoán token kế tiếp có điều kiện theo prompt + glossary · **File code chính:** `toolCaoTruyen/translator/ollama_translator.py` · **Chương:** ch04
- **Bước:** 2 TTS · **Công nghệ:** Edge TTS, Piper (VITS), Kokoro, VieNeu, XTTSv2 · **Nguyên lý một câu:** Văn bản → âm vị/token → mel/waveform bằng mạng neural · **File code chính:** `AIVoice/adapter_tts_cli.py` , `src/main.py` , `src/engines/*` · **Chương:** ch05
- **Bước:** 2 Hậu kỳ âm · **Công nghệ:** pyloudnorm (BS.1770), librosa · **Nguyên lý một câu:** Đo loudness cảm nhận rồi scale về −14 LUFS · **File code chính:** `AIVoice/src/utils/audio.py` · **Chương:** ch05
- **Bước:** 3a Phân cảnh · **Công nghệ:** LLM JSON mode + kiểm bất biến · **Nguyên lý một câu:** LLM gom đoạn đã đánh số thành cảnh; code kiểm phủ kín, liên tiếp · **File code chính:** `semantic_scene_splitter.py` · **Chương:** ch06
- **Bước:** 3a Timeline · **Công nghệ:** Tỷ lệ số từ · **Nguyên lý một câu:** `dur_i = T·w_i/Σw` , cảnh cuối ép bằng T · **File code chính:** `srt_mapper.py` · **Chương:** ch06, ch10
- **Bước:** 3a Prompt · **Công nghệ:** LLM + style lock · **Nguyên lý một câu:** Mỗi cảnh sinh prompt theo schema; ghép style → (action:1.35) → nội dung · **File code chính:** `llm_prompter.py` , `style_lock.py` · **Chương:** ch06
- **Bước:** 3b Sinh ảnh · **Công nghệ:** Stable Diffusion 1.5 (diffusers), Hyper-SD, compel · **Nguyên lý một câu:** Khử nhiễu dần trong latent 4×(H/8)×(W/8), U-Net dự đoán nhiễu, CFG trộn có/không điều kiện · **File code chính:** `image_generator.py` · **Chương:** ch07
- **Bước:** 3c Nhất quán · **Công nghệ:** LoRA (peft), IP-Adapter Plus Face, InsightFace, OpenCV animeface · **Nguyên lý một câu:** Cập nhật hạng thấp ΔW=BA; ảnh tham chiếu thành token ảnh cho cross-attention · **File code chính:** `lora_trainer.py` , `scripts/train_*.py` , `face_detailer.py` · **Chương:** ch08
- **Bước:** 3d Studio · **Công nghệ:** rembg isnet-anime, GrabCut, alpha compositing · **Nguyên lý một câu:** Tách nền ra alpha, ghép theo phép "over" C = αF + (1−α)B · **File code chính:** `studio/*.py` · **Chương:** ch09
- **Bước:** 3e Upscale · **Công nghệ:** Real-ESRGAN x4plus anime 6B · **Nguyên lý một câu:** GAN siêu phân giải 4×, fp32 để tránh khung đen · **File code chính:** `postprocess.py` · **Chương:** ch07, ch11
- **Bước:** 3e Dựng video · **Công nghệ:** ffmpeg (imageio-ffmpeg) · **Nguyên lý một câu:** concat demuxer ảnh + duration → H.264, sau đó mux audio · **File code chính:** `video_assembler.py` · **Chương:** ch11
- **Bước:** 4 Ghép · **Công nghệ:** ffmpeg concat `-c copy` · **Nguyên lý một câu:** Nối stream không mã hóa lại · **File code chính:** `orchestrator/video_merger.py` · **Chương:** ch11
- **Bước:** Autosub (rời) · **Công nghệ:** faster-whisper, Demucs, PaddleOCR, libass · **Nguyên lý một câu:** ASR encoder-decoder, VAD, timestamp từng từ · **File code chính:** `app/services/subtitle.py` , `composer.py` · **Chương:** ch10
- **Bước:** Trợ lý AI · **Công nghệ:** IDF lexical retrieval, SQLite FTS5 (index), Ollama `/api/chat` , NDJSON · **Nguyên lý một câu:** Chấm điểm từ khóa hiếm, chỉ đưa mảnh đủ điểm vào prompt · **File code chính:** `chatbot.py` , `kb_index.py` , `llm.py` · **Chương:** ch12
- **Bước:** Chất lượng · **Công nghệ:** pytest, ruff, GitHub Actions, Inno Setup · **Nguyên lý một câu:** Mock/stub để test không cần GPU · **File code chính:** `tests/` , `.github/workflows/` · **Chương:** ch13

5. Luồng hoạt động end-to-end (đã đối chiếu `orchestrator/pipeline.py` )

### 5.1 Tổng quan dạng flowchart

### 5.2 Chi tiết từng bước

Bước 0 — Khởi động ứng dụng

- **Việc:** `run.bat` gọi `setup.bat` nếu chưa có venv, rồi chạy `pythonw -m orchestrator.desktop` · **Code:** `run.bat` · **Ghi chú:** Luôn dùng `python -m` vì file `.exe` trong venv hỏng khi dời thư mục
- **Việc:** uvicorn chạy trong thread daemon, pywebview ở main thread · **Code:** `desktop.py:141-` `217` · **Ghi chú:** Thiếu WebView2 thì mở trình duyệt
- **Việc:** FastAPI lifespan chạy `model_preflight.start()` · **Code:** `main.py:32-39` · **Ghi chú:** Pull model Ollama đang cấu hình; tải Piper (timeout 1800 s) và model MediaComposer (7200 s), marker `models/.preflight_ok`
- **Việc:** `StorageManager.__init__` tạo `storage/truyen` , `storage/tasks` , `storage/app.db` · **Code:** `storage.py:51-` `63` · **Ghi chú:** SQLite bật WAL + foreign_keys
- **Việc:** Đóng cửa sổ thì `_shutdown` gọi `process_mgr.stop_all()` · **Code:** `desktop.py:120-` `138` · **Ghi chú:** Không để lại process mồ côi giữ VRAM

Bước tạo truyện

`POST /api/stories` ( `main.py:326-335` ) gọi `init_story_workspace` ( `storage.py:70-119` ):

```
storage/truyen/<slug>/        slug = slugify(tên), vd "Đắc Kỷ Trụ Vương" -> "dac_ky_tru_vuong"
├── story.json                status "CREATED", pipeline_step 1
├── raw/
└── video/
```

`write_story_meta` ghi JSON ( `indent=2, ensure_ascii=False` ) rồi `_mirror_to_db` upsert sang bảng `stories` và thay bảng `chapters` ( `storage.py:135-148, 207-212` ). Tên trùng thì trả 409.

Bước 1 — Nguồn truyện và dịch (task `<slug>_step1` )

Trình tự phía UI: `postPipelineAction` gọi `POST /api/chat/unload` trước để Ollama nhả model chatbot, sau đó mới gọi `POST` `/api/pipeline/step1` . Backend kiểm tra `_reject_if_auto_running` và `process_mgr.is_running` , trùng thì trả 400 ( `main.py:435-457` ). Sau đó gọi `pipeline.start_step_1_crawl_translate` ( `pipeline.py:135` ).

Có 3 nhánh:

- **Nhánh:** `ai_write` · **Cách chạy:** Thread + `register_manual_task` , gọi `story_writer.generate_story` ; xong đặt `TRANSLATED` , `pipeline_step=2` vì nội dung đã là tiếng Việt · **Code:** `pipeline.py:143-145,` `333-390`
- **Nhánh:** `local` · **Cách chạy:** Thread `_copy_local` → `chapter_naming.normalize_dir(local_dir, raw_dir)` rồi gọi `on_crawl_completed(exit_code)` đúng một lần · **Code:** `pipeline.py:278-331`
- **Nhánh:** Web ( `69shuba` , …) · **Cách chạy:** Subprocess `toolCaoTruyen/.venv/Scripts/python.exe adapter_cli.py crawl--source...--` `output-dir raw/` , `cwd="toolCaoTruyen"` , `close_queue_on_exit=False` · **Code:** `pipeline.py:150-169,` `270-277`

Khi crawl hoặc copy thành công và `auto_translate` bật, `on_crawl_completed` đặt `TRANSLATING` , rồi spawn translate trên cùng `task_key` với `reuse_queue=True, close_queue_on_exit=True` ( `pipeline.py:220-251` ). Nhờ vậy UI chỉ cần mở một luồng SSE cho cả Bước 1.

Lệnh dịch: `adapter_cli.py translate--input-dir raw/--output-dir raw/--engine<ollama|gemini|gemini_api> [--auto-` `extract]...` ( `pipeline.py:172-196` ).

File trung gian sinh ra trong `raw/` :

- **File:** `Chương 0001 -<tên>.md` · **Sinh bởi:** crawl ( `crawler_engine.py:111-150` ) hoặc normalize_dir · **Định dạng:** Markdown UTF-8, chỉ nội dung
- **File:** `.crawler_state.json` · **Sinh bởi:** crawl · **Định dạng:** `{last_chapter_index, next_url,` `reached_end}` để resume
- **File:** `_original.zip` · **Sinh bởi:** adapter crawl ( `adapter_cli.py:50-59` ) · **Định dạng:** Backup bản gốc, vì bước dịch sẽ xóa bản gốc
- **File:** `Chương 0001 - [VI]<tên>.md` · **Sinh bởi:** translate · **Định dạng:** Bản dịch; dấu `" - [VI] "` là "hợp đồng" cho các bước sau
- **File:** `<tên>.translation_report.json` · **Sinh bởi:** translator ( `ollama_translator.py:737-752` ) · **Định dạng:** Báo cáo chunk lỗi, marker `[[MISSING_CHUNK:n]]`
- **File:** `glossary.json` · **Sinh bởi:** GlossaryManager ( `glossary_manager.py:21-22` , `adapter_cli.py:144-145` ) · **Định dạng:** Từ điển riêng của truyện (dict Trung → Việt)

Trạng thái: `CRAWLING→TRANSLATING→TRANSLATED` (hoặc `CRAWLED` nếu tắt dịch, `CRAWL_FAILED` , `TRANSLATE_FAILED` , `CANCELLED` ). `pipeline_step` chuyển thành 2.

- Chi tiết cần nhớ: thư mục `translated/` không còn được tạo trong luồng hiện tại. Bản dịch nằm ngay trong `raw/` . Code vẫn kiểm tra `translated/` "nếu có" để tương thích dữ liệu cũ ( `pipeline.py:400-405, 520-523` ).

Bước 2 — Sinh giọng (task `<slug>_step2` )

`start_step_2_tts` ( `pipeline.py:392-497` ):

- Thư mục đầu vào: `translated/` nếu có `.md` , ngược lại dùng `raw/` . Output dir = input dir, nên file `.wav` nằm cạnh file `.md` ( `pipeline.py:403-405, 430-431` ). Lệnh: `AIVoice/.venv/Scripts/python.exe AIVoice/adapter_tts_cli.py--engine edge--voice vi-VN-NamMinhNeural--`

```
speed 1.0 --target-lufs -14.0 --fade-in 0.1 --fade-out 0.1 --silence-duration 0.3 --device cuda --no-phonemize --
```

- `normalize--no-cache...` , `cwd="AIVoice"` . Adapter chỉ lấy file có `" - [VI] "` và bỏ qua chương đã có `.wav/.mp3` ( `adapter_tts_cli.py:157-207` ). File ra là `<cùng` `tên>.wav` ( `adapter_tts_cli.py:212` ). Bên trong adapter, mỗi file đi qua: chuẩn hóa NFC → làm sạch markdown → chunk (30 từ / 240 ký tự) → engine sinh từng chunk (ThreadPool) → `concatenate_wavs` (chèn 0.3 s lặng) → fade + LUFS.

Trạng thái: `VOICE_GENERATING→VOICE_GENERATED` ( `pipeline_step=3` ), hoặc `VOICE_FAILED` / `CANCELLED` .

Bước 3 — Dựng hoạt hình (task `<slug>_step3` )

Trước khi spawn, `mediacomposer_config.apply_sd_params` ghi các tham số `sd_*` từ `global_config.json` xuống `[storytelling]` trong `AIVoice/apps/MediaComposer/config.toml` ( `pipeline.py:508-513` ). Việc này phải làm trước vì process con chỉ đọc config lúc khởi động.

Cấu hình đi vào process con qua 3 kênh:

- 1. `config.toml` : `sd_steps` , `sd_guidance` , kích thước, … 2. Tham số CLI ( `pipeline.py:538-584` ): `--story-name--genre--input-dir--output-dir<slug>/video--style thuy_mac-`

```
-checkpoint anything-v5 --bgm-volume 0.15 --llm-* --enable-upscale --no-subtitles --use-semantic-split --extract-
```

- `characters--no-face-detailer--hardware-profile auto [--render-mode classic|studio]` .
- 3. Biến môi trường ( `pipeline.py:587-594` ): `MC_STORAGE_TASKS=<storage>/tasks` , `CUDA_VISIBLE_DEVICES` khi chọn cpu hoặc Bên trong `adapter_video_cli.py` : · `cuda:N` .
- Pha · Việc Code File sinh ra
- Quét · `scan_batch_dir(input_dir)` : ghép `.md` — `batch_video_runner.py:101-` `[VI]` với `.wav` cùng stem `175`
- Context truyện · `ContextManager(slug)` : nạp hoặc tạo, `storage/tasks/contexts/<slug>/context.json` , `adapter_video_cli.py:145-` áp style preset `168` , `context_manager.py:13-` `style_prompt.txt` , `learned_corrections.json` , `26` `characters/`
- Nhân vật · Nếu chưa có: LLM đọc 5 chương đầu, Ghi vào `context.json` `adapter_video_cli.py:170-209` trích 5–10 nhân vật
- Pass A (từng chương) · `step1_generate_script` → `storage/tasks/video/tasks/<uuid>/state.json` , `batch_video_runner.py:359-` `generated_from_script.srt` , `step2_generate_images` `457` `draft_frames/scene_XXX.png`
- Release · `batch_video_runner.py` (sau VRAM trống cho ESRGAN `StorytellingPipeline().release()` vòng Pass A)
- Pass B (từng chương) · `step3_render_final` : ESRGAN → `final_frames/scene_XXX.png` , `final_video.mp4` , `batch_video_runner.py:460-` `final_frames/` → `assemble_video` → `515` , `orchestrator.py:541-615` `storage/truyen/<slug>/video/<stem>.mp4` `final_video.mp4` → copy ra `video/<stem>.mp4`
- Báo cáo · `batch_state.json` , `batch_report.json` `batch_video_runner.py:177-` `storage/truyen/<slug>/video/batch_state.json` trong output dir `213, 352`
- Kết thúc · Còn chương thiếu mp4 thật thì exit 1 — `adapter_video_cli.py:29-38` ( `count_incomplete_items` ) (chỉ tính item `video_done` có file mp4 thật, dung lượng > 0)

Bên trong `step1_generate_script` (ch06): đọc độ dài WAV chính xác ( `audio_utils.get_audio_duration` ), LLM chia cảnh ( `semantic_scene_splitter` ), gán thời lượng theo tỷ lệ số từ ( `srt_mapper` ), sinh SRT từ kịch bản, rồi sinh prompt từng cảnh ( `llm_prompter.generate_prompts_batch` ). `state.json` lưu `step = "SCRIPT_READY"` .

Bên trong `step2_generate_images` (ch07–ch09): unload Ollama ( `keep_alive=0` ), nạp SD pipeline singleton, áp LoRA bằng `set_adapters` , sinh ảnh theo `shot_type` (close 576×704, medium 704×528, wide 768×432). Nếu `render_mode=="studio"` thì đi nhánh Studio, lỗi thì lùi về classic theo từng cảnh. `state.json` chuyển sang `STORYBOARD_READY` .

Một mẫu `state.json` thật (máy dev, `storage/tasks/video/tasks/dc526b9c-.../state.json` ) có các khóa `step, scenes,` `task_dir, audio_path, srt_path, md_path` . Mỗi scene có: `scene_id, text_vi, word_count, start_time, end_time,`

```
duration_sec, image_prompt, characters_in_scene, primary_character, fallback_level, accepted_seed, frame_path,
```

`shot_type, _semantic_meta` . Ví dụ scene 0 có `duration_sec≈30.50` , `shot_type "medium"` , prompt mở đầu bằng `thuymac ink` `wash style,...` , rồi `(practices swordsmanship:1.35)` .

Sau khi process thoát, callback `_finalize_video_task` chạy ( `pipeline.py:99-133` ):

- `exit_code==0` thì gọi `merge_videos(video/, video/TongHop_<YYYYmmdd_HHMMSS>.mp4)` . Chỉ khi merge thành công mới đặt `VIDEO_GENERATED` . Nếu không: `CANCELLED` (người dùng dừng) hoặc `VIDEO_FAILED` .

Bước 4 — Ghép video (task `<slug>_step5` )

`start_step_5_merge` ( `pipeline.py:750-797` ) chạy trong thread (không phải subprocess). Nó redirect stdout của `merge_videos` vào log queue. `merge_videos` dùng `ffmpeg -f concat -safe 0 -i concat_list.txt -c copy` , lỗi thì re-encode libx264. Thứ tự ghép là `sorted(glob('*.mp4'))` , loại bỏ file `TongHop_*` ( `video_merger.py:6-8` ).

- Quan sát từ code, nên biết trước: trong chuỗi auto-run, `step3` thành công đã tự merge một lần ( `_finalize_video_task` ), sau đó `CHAIN_STEPS` còn chạy `step5` merge thêm lần nữa ( `auto_run.py:13-18, 143` ). Kết quả là có 2 file `TongHop_*` gần như giống nhau. Thư mục mẫu `storage/truyen/e2e_kiem_khach/video/` đang có 3 file `TongHop_*` . Đây không phải lỗi dữ liệu, vì `_select_files` loại file `TongHop_*` nên không bị ghép lồng, nhưng tốn thời gian và dung lượng. Nếu bị hỏi thì nhận là điểm cần tinh gọn: bỏ merge trong `_finalize_video_task` khi chạy từ chuỗi, hoặc bỏ `step5` khỏi chuỗi.

Autosub (task `<slug>_step4` hoặc `autosub_<id>_step4` ) — công cụ rời

Không nằm trong chuỗi. Nó nhận video hoặc URL, chạy `adapter_autosub_cli.py` (ffmpeg tách audio 16 kHz → Demucs tùy chọn → faster-whisper → dịch SRT → lồng tiếng tùy chọn → burn phụ đề). Xem ch10.

### 5.3 Sequence diagram: một lần bấm "Chạy Bước 3"

Điểm tinh tế cần nói được: callback `on_completed` chạy trước khi đặt sentinel `None` vào queue ( `process_manager.py:66-119` ). Trong lúc merge (có thể mất vài phút), task vẫn được tính là "đang chạy" nhờ `finalizing_tasks` . UI không thể chen một lần chạy mới vào giữa.

### 5.4 Bảng tổng hợp file trung gian theo vị trí

- `storage/` `├──app.db SQLite: stories, chapters, jobs (mirror)` `├──kb_index.db Index KB của chatbot (FTS5 + kb_chunks)` `├──truyen/<slug>/` `│├──story.json status, pipeline_step, updated_at,...` `│├──raw/` `││├──_original.zip backup bản gốc (nguồn web)` `││├──.crawler_state.json resume crawl` `││├──glossary.json glossary riêng của truyện` `││├──Chương 0001 - [VI]<tên>.md bản dịch / bản tiếng Việt` `││├──Chương 0001 - [VI]<tên>.wav giọngđọc (cạnh .md)` `││└──<tên>.translation_report.json báo cáo chunk lỗi` `│└──video/` `│├──Chương 0001 - [VI]<tên>.mp4 video từng chương` `│├──batch_state.json, batch_report.json` `│└──TongHop_YYYYmmdd_HHMMSS.mp4 video tổng hợp` `└──tasks/ = MC_STORAGE_TASKS` · `├──contexts/<slug>/ tri thức truyện (được bảo vệkhi dọn)` `│├──context.json nhân vật, genre, art_style, checkpoint` `│├──style_prompt.txt positive--- negative` `│├──learned_corrections.json` `│└──characters/<char_slug>/ ref.png, dataset/` `└──video/tasks/` `├──<uuid>/ task_dir của một chương` `│├──state.json SCRIPT_READY / STORYBOARD_READY / DONE` `│├──generated_from_script.srt` `│├──draft_frames/scene_XXX.pngảnh SD gốc` `│├──final_frames/scene_XXX.pngảnh sau ESRGAN 1920x1080` `│└──final_video.mp4` `└──batch_<uuid>/ thưmục runner tạo trước; state.jsonđược dời sang<uuid>`
- Ghi chú về độ tin cậy của cây thư mục:

Đường dẫn `tasks/video/tasks/<uuid>` lấy từ `orchestrator.py:223-233` và `batch_video_runner.py:398-404` . `contexts` lấy từ `context_manager.py:13-16` . LoRA nhân vật và style nằm trong `AIVoice/apps/MediaComposer/resource/character_loras/` và `resource/style_loras/` (hiện chỉ có `thuy_mac.safetensors` + `thuy_mac.json` ). Trong `storage/tasks/contexts/e2e_kiem_khach/` trên máy dev có thêm `llm_cache/` và `character_bible.json` . Grep toàn bộ `*.py` trong repo không tìm thấy code nào sinh ra chúng, nên đây là dữ liệu của phiên bản cũ. Đừng trình bày như tính năng hiện có. `cleanup_tasks` chỉ xóa thư mục UUID và các thư mục khung trung gian, không bao giờ đụng `contexts` / `character_loras` ( `storage.py:236-277` ).

### 5.5 Định dạng dữ liệu giữa các bước

- **Giữa:** UI → API · **Định dạng:** JSON (pydantic `Step1Schema` … `Step5Schema` , `AutoRunSchema` ) · **Hợp đồng:** `main.py:104-212`
- **Giữa:** API → UI (log) · **Định dạng:** SSE `data:<dòng>` ; PING mỗi 1 s khi rỗng; `[SYSTEM] Process completed` `(exit_code=N).` · **Hợp đồng:** `process_manager.py:261-305`
- **Giữa:** Worker → Orchestrator · **Định dạng:** stdout JSON Lines `{"event": "...",...}` , `ensure_ascii=False` , flush · **Hợp đồng:** Các `log_json` trong adapter
- **Giữa:** Kết quả bước · **Định dạng:** exit code (0 là thành công) · **Hợp đồng:** Callback `on_*_completed`
- **Giữa:** Bước 1 → 2 · **Định dạng:** File `.md` có `" - [VI] "` trong tên · **Hợp đồng:** `adapter_tts_cli.py:157-207`
- **Giữa:** Bước 2 → 3 · **Định dạng:** Cặp `<stem>.md` + `<stem>.wav` cùng thư mục · **Hợp đồng:** `scan_batch_dir`
- **Giữa:** Pass A → Pass B · **Định dạng:** `state.json` (danh sách `Scene` + `task_dir` ) · **Hợp đồng:** `models.scene_from_dict`
- **Giữa:** Bước 3 → 4 · **Định dạng:** `video/*.mp4` (trừ `TongHop_*` ) · **Hợp đồng:** `video_merger._select_files`
- **Giữa:** Chatbot · **Định dạng:** NDJSON ( `delta/done/agent_action/...` ) qua `fetch` + ReadableStream · **Hợp đồng:** `main.py:814+` , `chat.js`

### 5.6 Máy trạng thái của một truyện

Quan trọng: FSM này chỉ mô tả trạng thái. Code không ép điều kiện chuyển bước. Người dùng có thể chạy Bước 3 khi truyện đang `CREATED` nếu thư mục đã có sẵn `.md + .wav` . Điều kiện thực sự nằm ở file trên đĩa, không nằm ở chuỗi status. Đây là thiết kế có chủ ý để chạy lại từng bước linh hoạt. Đổi lại, nếu thiếu dữ liệu thì bước sau tự báo lỗi (vd TTS exit 1 khi không có chương `[VI]` ).

### 5.7 Chuỗi tự động 1→4

`AutoRunManager` ( `auto_run.py` ) chạy thread daemon theo thứ tự `step1→step2→step3→step5` . Cứ 1,0 s nó poll `get_task_status` một lần, gặp exit code khác 0 thì dừng chuỗi, hủy bằng `threading.Event` . UI poll `GET /api/pipeline/auto-` `run/{story}` mỗi 2 s để tự chuyển tab. Trạng thái chuỗi chỉ nằm trong RAM, nên restart server là mất (docstring ghi "chấp nhận ở v1").

## 6. Bản đồ module của cả 3 repo

- 6.1 Repo tổng — `orchestrator/` và `webui/`
- File · Dòng · Vai trò một dòng
- `orchestrator/desktop.py` · 230 · Điểm vào ứng dụng: uvicorn thread + cửa sổ pywebview, dọn process khi đóng
- `orchestrator/main.py` · 1185 · FastAPI app: schema, 39 route, SSE, chatbot, mount webui
- `orchestrator/pipeline.py` · 797 · `NovelPipeline` : dựng lệnh từng bước, callback cập nhật `story.json`
- `orchestrator/process_manager.py` · 305 · Spawn/kill subprocess, reader thread, log queue, SSE generator
- `orchestrator/auto_run.py` · 165 · Chuỗi tự động step1→2→3→5 chạy nền
- `orchestrator/storage.py` · 289 · Workspace truyện, `slugify` , mirror SQLite, dọn `tasks/`
- `orchestrator/db.py` · 203 · Schema SQLite `stories/chapters/jobs` , WAL, FK
- `orchestrator/config.py` · 228 · Đọc/ghi `global_config.json` , `ui_settings.json` , giá trị mặc định, `SD_TUNING_DEFAULTS`
- `orchestrator/mediacomposer_config.py` · 145 · Ghi tham số `sd_*` xuống `config.toml` , kẹp theo `LIMITS` , giữ comment
- `orchestrator/chapter_naming.py` · 260 · Chuẩn hóa tên chương cho nguồn local
- `orchestrator/story_writer.py` · 90 · Sáng tác truyện bằng LLM với rolling summary
- `orchestrator/llm.py` · 188 · `resolve_llm` , chat OpenAI-compatible, `chat_stream_ollama` , `unload_ollama`
- `orchestrator/chatbot.py` · 629 · Trợ lý AI: chấm điểm IDF, chọn mảnh KB, system prompt, router intent, GPU weight
- `orchestrator/kb_index.py` · 293 · Chia markdown thành mảnh, index SQLite FTS5, số đo IDF vs BM25
- `orchestrator/ollama_manager.py` · 262 · Tự tìm/chạy `ollama serve` , pull model có lock và tiến độ
- `orchestrator/model_preflight.py` · 238 · Kiểm tra và tải mô hình nền khi mở app
- `orchestrator/video_merger.py` · 96 · Ghép mp4 bằng ffmpeg concat, chống path traversal
- `orchestrator/cleanup.py` · 51 · CLI dọn dẹp `tasks/`
- `webui/index.html` · 1362 · Khung 7 tab, form các bước, tab Cấu Hình
- `webui/app.js` · 2096 · Logic UI: gọi API, SSE `streamLogs` (33 case event), auto-run, đồng bộ cấu hình
- `webui/chat.js` · 516 · Chatbot: fetch + NDJSON stream, thẻ xác nhận agent
- `webui/style.css` , `chat.css` · 1744, 628 · Giao diện
- `tests/` · 22 file · pytest, không cần GPU
- `scripts/eval_chatbot.py` , `gen_kb_*.py` · — · Đánh giá chatbot; sinh KB 08/09 từ code
- `docs/kb/*.md` · 11 file · Knowledge base của chatbot
- `.github/workflows/ci.yml` , `release.yml` · — · CI lint + test; release theo tag
- `installer/` · — · Inno Setup web installer

6.2 Submodule `toolCaoTruyen/` (cào & dịch)

- **File:** `adapter_cli.py` · **Dòng:** 427 · **Vai trò:** CLI `crawl` / `translate` cho orchestrator, log JSON Lines
- **File:** `core/crawler_engine.py` · **Dòng:** 644 · **Vai trò:** Selenium Chrome ẩn danh, vòng tải chương, resume 3 lớp
- **File:** `core/intelligent_search.py` · **Dòng:** 244 · **Vai trò:** LLM dịch từ khóa tìm kiếm sang tiếng Trung (chỉ trong app riêng của tool)
- **File:** `core/config_manager.py` · **Dòng:** 93 · **Vai trò:** Cấu hình tool (có key mặc định hardcode, xem ch03)
- **File:** `sources/base.py` , `registry.py` · **Dòng:** 119, 27 · **Vai trò:** ABC `BaseSourceParser` + registry Strategy
- **File:** `sources/shuba69.py` · **Dòng:** 782 · **Vai trò:** Parser 69shuba: Cloudflare wait, 6 selector, lọc quảng cáo
- **File:** `sources/metruyenchuvn.py` · **Dòng:** 351 · **Vai trò:** Parser metruyenchu
- **File:** `sources/book_search.py` · **Dòng:** 92 · **Vai trò:** Tìm truyện
- **File:** `translator/base.py` · **Dòng:** 235 · **Vai trò:** Lớp cơ sở, phát hiện leak chữ Hán
- **File:** `translator/ollama_translator.py` · **Dòng:** 756 · **Vai trò:** Dịch 2 tầng qua Ollama, glossary chủ động, vá chunk
- **File:** `translator/gemini_translator.py` · **Dòng:** 728 · **Vai trò:** Gemini REST, safety BLOCK_NONE, fallback Ollama
- **File:** `translator/gemini_api_translator.py` · **Dòng:** 271 · **Vai trò:** Biến thể OpenAI Chat Completions (proxy)
- **File:** `translator/glossary_manager.py` · **Dòng:** 79 · **Vai trò:** Gộp idioms < global < story, chỉ thêm key mới
- **File:** `translator/registry.py` · **Dòng:** 50 · **Vai trò:** `TRANSLATOR_ENGINES` , `OLLAMA_MODELS` (tham số từng model)
- **File:** `ollama_models/Modelfile.hy-mt2` · **Dòng:** — · **Vai trò:** Template viết tay cho HY-MT2 GGUF
- **File:** `Gemini-API/` · **Dòng:** — · **Vai trò:** Proxy OpenAI-compatible :7860 dùng cookie (tùy chọn khi phát triển)

6.3 Submodule `AIVoice/` (TTS + MediaComposer)

- **File:** `adapter_tts_cli.py` · **Dòng:** 270 · **Vai trò:** CLI TTS cho orchestrator: gộp config, resume, log JSON
- **File:** `src/main.py` · **Dòng:** 1109 · **Vai trò:** `process_single_file` : làm sạch, chunk, song song, ghép WAV
- **File:** `src/engines/base.py` · **Dòng:** 16 · **Vai trò:** ABC `BaseTTSEngine.generate(text, output_path)`
- **File:** `src/engines/edge.py` , `piper.py` , `kokoro.py` , `vieneu.py` , `clone.py` · **Dòng:** 62–311 · **Vai trò:** 5 engine TTS (clone = XTTSv2)
- **File:** `src/utils/text.py` , `audio.py` , `cache.py` , `phoneme.py` · **Dòng:** 217, 235, 230, 30 · **Vai trò:** Chuẩn hóa tiếng Việt/chunk; ghép, LUFS; semantic cache; phonemize
- **File:** `setup.bat` · **Dòng:** — · **Vai trò:** Chọn PyTorch cu128/cu124/CPU theo GPU
- **File:** `apps/MediaComposer/adapter_video_cli.py` · **Dòng:** 265 · **Vai trò:** CLI Bước 3: context, trích nhân vật, `run_batch`
- **File:** `apps/MediaComposer/adapter_autosub_cli.py` · **Dòng:** 253 · **Vai trò:** CLI Autosub
- **File:** `app/config.py` · **Dòng:** 188 · **Vai trò:** Nạp `config.toml` , mặc định `[storytelling]`
- **File:** `storytelling/batch_video_runner.py` · **Dòng:** 517 · **Vai trò:** Batch 2-pass, `batch_state.json` , reconcile, OOM retry
- **File:** `storytelling/orchestrator.py` · **Dòng:** 648 · **Vai trò:** `StorytellingOrchestrator` : step1 script, step2 ảnh, step3 render
- **File:** `storytelling/semantic_scene_splitter.py` · **Dòng:** 382 · **Vai trò:** LLM chia cảnh + kiểm bất biến + giới hạn thời lượng
- **File:** `storytelling/srt_mapper.py` · **Dòng:** 540 · **Vai trò:** Timeline theo tỷ lệ từ, sinh SRT từ kịch bản
- **File:** `storytelling/audio_utils.py` · **Dòng:** 78 · **Vai trò:** Đọc độ dài audio chính xác (wave → ffmpeg → pydub)
- **File:** `storytelling/llm_prompter.py` · **Dòng:** 326 · **Vai trò:** Director's Note + prompt từng cảnh song song
- **File:** `storytelling/style_lock.py` · **Dòng:** 127 · **Vai trò:** Ghép prompt khóa phong cách, lọc tag trôi style
- **File:** `storytelling/prompt_translator.py` · **Dòng:** 297 · **Vai trò:** Kẹp độ dài prompt (75 từ)
- **File:** `storytelling/character_extractor.py` · **Dòng:** 195 · **Vai trò:** LLM trích nhân vật
- **File:** `storytelling/context_manager.py` · **Dòng:** 360 · **Vai trò:** Lưu context truyện, style preset, dataset nhân vật
- **File:** `storytelling/models.py` · **Dòng:** 181 · **Vai trò:** Dataclass `Scene` , `Character` , `StoryContext`
- **File:** `storytelling/image_generator.py` · **Dòng:** 934 · **Vai trò:** `StorytellingPipeline` singleton: SD1.5, scheduler, LoRA, IP- Adapter, compel, VAE
- **File:** `storytelling/image_gen_service.py` · **Dòng:** 330 · **Vai trò:** Dịch vụ sinh ảnh cấp cao
- **File:** `storytelling/hardware_adapter.py` · **Dòng:** 84 · **Vai trò:** Chọn profile cuda_high/cuda_low/cpu theo VRAM
- **File:** `storytelling/face_detailer.py` · **Dòng:** 491 · **Vai trò:** Sửa mặt img2img có 3 cổng chất lượng; helper img2img
- **File:** `storytelling/face_extractor.py` · **Dòng:** 65 · **Vai trò:** InsightFace (engine faceid)
- **File:** `storytelling/character_bootstrap.py` · **Dòng:** 228 · **Vai trò:** Sinh dataset nhân vật bằng IP-Adapter để train LoRA
- **File:** `storytelling/lora_trainer.py` · **Dòng:** 151 · **Vai trò:** Gọi script train LoRA trong subprocess
- **File:** `storytelling/dataset_collector.py` · **Dòng:** 202 · **Vai trò:** Thu thập ảnh tốt làm dataset nhân vật
- **File:** `storytelling/postprocess.py` · **Dòng:** 192 · **Vai trò:** Real-ESRGAN fp32 + chống khung đen + fallback PIL
- **File:** `storytelling/video_assembler.py` · **Dòng:** 278 · **Vai trò:** ffmpeg 2 lượt: ảnh → video, mux audio/BGM/phụ đề
- **File:** `storytelling/md_parser.py` · **Dòng:** 128 · **Vai trò:** Fallback chia cảnh không cần LLM
- **File:** `storytelling/studio/*.py` · **Dòng:** 7 file · **Vai trò:** Studio: layout, render nền/nhân vật, matting, compositor, unify
- **File:** `app/services/subtitle.py` · **Dòng:** 190 · **Vai trò:** faster-whisper (Autosub)
- **File:** `app/services/composer.py` , `video.py` , `dubbing.py` , `material.py` · **Dòng:** 524–1659 · **Vai trò:** Luồng Autosub/dịch video, kế thừa kiểu MoneyPrinterTurbo; không dùng cho luồng truyện
- **File:** `app/services/llm.py` · **Dòng:** 100 · **Vai trò:** Client LLM OpenAI-compatible, `unload_local_llm`
- **File:** `scripts/train_character_lora.py` , `train_style_lora.py` · **Dòng:** 198, 375 · **Vai trò:** Train LoRA bằng diffusers + peft
- **File:** `scripts/detect_faces_cli.py` · **Dòng:** 67 · **Vai trò:** Phát hiện mặt anime bằng OpenCV trong process riêng
- **File:** `scripts/build_style_dataset.py` , `style_weight_sweep.py` · **Dòng:** — · **Vai trò:** Dữ liệu style CC0 từ Met Museum; quét trọng số LoRA
- **File:** `resource/image_presets/*.txt` · **Dòng:** 16 file · **Vai trò:** Preset style (positive `---` negative), mặc định `thuy_mac`
- **File:** `config.toml` · **Dòng:** — · **Vai trò:** Cấu hình runtime (gitignored), orchestrator ghi `sd_*` vào đây

## 7. Những điểm lệch giữa báo cáo và code: phải thống nhất trước khi bảo vệ

Đây là phần quan trọng nhất của chương này. Hội đồng có thể đọc báo cáo rồi hỏi, hoặc mở code ra đối chiếu.

- **Báo cáo ghi:** Bảng 4.3: `render_mode` = "studio (mặc định)"; Studio là "chế độ dựng chính" · **Code hiện tại:** Mặc định trong `app/config.py:86` là `"classic"` . `adapter_video_cli.py:59` mặc định `classic` . `Step3Schema.render_mode="auto"` ( `main.py:159` ) nhưng `pipeline.py:582-584` không truyền cờ khi auto, nên chạy classic. UI có option studio ghi "(thử nghiệm)" ( `index.html:546` ). Riêng máy dev đặt `video.render_mode` `= "studio"` trong `configs/global_config.json` · **Cách trả lời an toàn:** "Studio là hướng thiết kế chính và được bật trong cấu hình máy demo của em. Ở mức mã nguồn, mặc định an toàn vẫn là Classic, và Studio tự lùi về Classic từng cảnh khi không qua cổng chất lượng. Thực nghiệm với phong cách thủy mặc cho alpha coverage chỉ 0,003 ( `docs/PLAN-quality-speed-` `v2.md` ), nên em giữ Classic làm mặc định."
- **Báo cáo ghi:** 173 test / 21 file / 7,86 s · **Code hiện tại:** 178 passed / 22 file / 21,63 s (chạy lại 29/09/2026) + 136 test MediaComposer · **Cách trả lời an toàn:** Nói số trong báo cáo, bổ sung số mới nếu được hỏi
- **Báo cáo ghi:** Studio "tự huấn luyện Character LoRA cho 2 nhân vật chính" · **Code hiện tại:** Code mặc định `studio_auto_train_leads = True` , nhưng `config.toml` máy dev đặt `false` . `resource/character_loras/` hiện trống · **Cách trả lời an toàn:** "Cơ chế đã có và có test; trên máy demo em tắt auto-train để tiết kiệm thời gian"
- **Báo cáo ghi:** K01: khung đen sửa bằng Real- ESRGAN FP32 + fallback PIL · **Code hiện tại:** Đúng ( `postprocess.py:41-42, 135-146` ). Ngoài ra còn một lỗi dải đen khác do VAE tiling fp16, sửa bằng `VAE_TILING_MIN_EDGE=1024` + `has_dead_region` (ch07) · **Cách trả lời an toàn:** Nêu cả hai nếu được hỏi về khung đen: hai nguyên nhân, hai chỗ sửa
- **Báo cáo ghi:** Hệ thống dùng "AI local" · **Code hiện tại:** TTS mặc định là Edge (dịch vụ online của Microsoft) ( `global_config tts.default_engine = "edge"` ) · **Cách trả lời an toàn:** "Mặc định Edge để nhanh và giọng tự nhiên. Toàn bộ pipeline có thể chạy offline bằng Piper/Kokoro/VieNeu/XTTS; phép đo trong báo cáo dùng Piper"
- **Báo cáo ghi:** Trợ lý AI có "tầng truy xuất tri thức" · **Code hiện tại:** Truy xuất lexical IDF, không embedding. FTS5/BM25 có code nhưng không được gọi trong luồng chính · **Cách trả lời an toàn:** Nói rõ lý do chọn IDF: đo IDF 28/28 so với BM25 27/28 (kb_index.py:13-22)
- **Báo cáo ghi:** Auto-run step1→2→3→5 · **Code hiện tại:** Đúng, nhưng step3 đã tự merge nên có 2 lần merge (mục 5.2) · **Cách trả lời an toàn:** Nhận là điểm tinh gọn

## 8. Hạn chế tổng thể (nói trước, đừng để bị bắt)

- 1. Video là slideshow ảnh tĩnh: không có Ken Burns, zoompan hay xfade trong luồng truyện (grep 0 kết quả, ch11). AnimateDiff/SVD cần VRAM lớn hơn nhiều so với 6 GB. Hướng gần nhất là `zoompan` + `xfade` của ffmpeg, chi phí thấp. 2. Studio chưa là mặc định (mục 7). 3. Chỉ đo trên một máy, chưa có MOS (chất lượng giọng) và điểm CLIP (nhất quán nhân vật). 4. API không xác thực. Bù lại, server bind `127.0.0.1` và CORS chỉ cho `127.0.0.1:8100` / `localhost:8100` . 5. API key truyền qua tham số CLI ( `pipeline.py:181, 548, 662` ) nên lộ trong danh sách process. 6. Ghi JSON không atomic ( `write_story_meta` ), nên có thể hỏng file nếu mất điện đúng lúc ghi. 7. Trạng thái auto-run chỉ nằm trong RAM. 8. Proxy Gemini-API dùng cookie, có thể vi phạm điều khoản dịch vụ, bind `0.0.0.0` , CORS `*` ( `Gemini-` `API/server/config.py:18` , `server/main.py:126` ). Đây chỉ là tùy chọn lúc phát triển; demo dùng Ollama.

9. Key giả `sk-gemini-...` còn nằm trong 5 file của submodule ( `toolCaoTruyen/app.py` , `config.json` , `core/config_manager.py` , `setup_helper.py` , `MediaComposer/webui/Main.py` ). Đó là key local của proxy, không phải credential Google, nhưng nên dọn.

## Câu hỏi hội đồng có thể hỏi

### 1. Em tóm tắt hệ thống trong 30 giây?

Hệ thống nhận truyện chữ (thư mục local, web, hoặc AI tự viết), dịch sang tiếng Việt bằng LLM local, đọc thành giọng nói bằng TTS, dùng LLM chia cảnh và viết prompt, sinh ảnh từng cảnh bằng Stable Diffusion có khóa phong cách và nhân vật, rồi ffmpeg dựng video từng chương và ghép thành video tổng. Tất cả được một orchestrator FastAPI điều phối qua các subprocess, chạy trên máy cá nhân 6 GB VRAM.

### 2. Đóng góp của em ở đâu, khi các mô hình đều là của người khác?

Đóng góp nằm ở tầng điều phối và ghép nối: kiến trúc đa tiến trình để giải phóng VRAM, giao thức JSON Lines + SSE, checkpoint/resume từng bước, style lock, kiểm bất biến khi LLM chia cảnh, dịch 2 tầng Zero Tolerance, batch 2-pass, Studio có cổng chất lượng, chatbot có cổng GPU. Mô hình em chỉ dùng lại; em tự train LoRA phong cách `thuy_mac` .

### 3. Vì sao không làm tất cả trong một process Python?

Vì PyTorch và CUDA không trả hết VRAM kể cả khi gọi `empty_cache` , và các thư viện (torch, onnxruntime, OpenCV, PaddleOCR) xung đột DLL/OpenMP với nhau. Process thoát thì hệ điều hành thu hồi toàn bộ tài nguyên. Ngoài ra lỗi của một worker chỉ trả exit code, không làm sập server.

### 4. Làm sao biết một bước thành công?

Bằng exit code của process con. Log JSON chỉ để hiển thị. Riêng Bước 3 còn kiểm tra thêm: adapter đếm chương thiếu mp4 thật để trả exit 1, và `_finalize_video_task` chỉ đặt `VIDEO_GENERATED` khi merge thành công ( `pipeline.py:99-133` ).

### 5. Nếu đang chạy Bước 3 mà mất điện, chạy lại có mất hết không?

Không. `batch_state.json` được ghi sau mỗi lần đổi trạng thái chương. Chạy lại thì chương `video_done` được bỏ qua, chương dở chạy tiếp từ `script_done` hoặc `images_done` . TTS bỏ qua chương có `.wav` ; dịch bỏ qua chương có bản `[VI]` .

### 6. File trung gian giữa Bước 2 và Bước 3 là gì?

Cặp `<stem>.md` + `<stem>.wav` cùng thư mục `raw/` , trong đó stem có chứa `" - [VI] "` . `scan_batch_dir` ghép chúng theo stem.

### 7. Thư mục `storage/tasks` dùng để làm gì?

Đó là thư mục làm việc của MediaComposer, được truyền qua biến môi trường `MC_STORAGE_TASKS` . Bên trong có `contexts/<slug>/` (nhân vật, style, được bảo vệ khi dọn) và `video/tasks/<uuid>/` (state.json, ảnh nháp, ảnh cuối, final_video.mp4 của từng chương).

### 8. Trạng thái truyện có ép thứ tự bước không?

Không. Status chỉ để mô tả và hiển thị. Điều kiện thật là dữ liệu trên đĩa. Như vậy có thể chạy lại riêng một bước bất kỳ.

### 9. Vì sao UI có "Bước 4" mà code gọi step5?

Lịch sử: step4 là công cụ Autosub, được tách ra thành tab rời. Ghép video giữ tên nội bộ step5. Ánh xạ nằm ở `DISPLAY_NO={1:1,2:2,3:3,5:4}` ( `auto_run.py:20` ) và `INTERNAL_STEP_BY_DISPLAY` `{4:5}` ( `app.js:402` ).

### 10. Hệ thống có thật sự chạy local 100% không?

Có thể chạy offline hoàn toàn nếu chọn nguồn local/ai_write, dịch Ollama, TTS Piper/Kokoro/VieNeu/XTTS. Mặc định TTS là Edge (online) vì chất lượng/tốc độ. Gemini là tùy chọn.

### 11. Chạy một chương mất bao lâu?

Báo cáo đo được: Piper khoảng 2,7 phút/chương; Bước 3 khoảng 2,6 phút cho video 45 giây (≈ 3,47× thời lượng) trên RTX 3060 Laptop 6 GB. Bước 1 chưa tổng hợp thời gian trung bình.

### 12. Nếu hội đồng hỏi "Studio là chế độ mặc định?

" Trả lời theo mục 7 dòng 1: được thiết kế làm hướng chính và bật trên máy demo, nhưng mặc định mã nguồn là Classic vì thực nghiệm alpha coverage thấp với phong cách thủy mặc; Studio lùi về Classic từng cảnh.

### 13. Vì sao lại lưu cả file JSON và SQLite?

File JSON cạnh dữ liệu là nguồn sự thật, dễ đọc, dễ sao chép. SQLite là bản mirror để thống kê và truy vấn nhanh, có thể dựng lại từ file ( `rebuild_db` , `POST /api/maintenance/rebuild-db` ).

## Tóm tắt 1 phút

"Đề tài của em giải bài toán biến một truyện chữ thành video hoạt hình 2D có lời đọc tiếng Việt, chạy hoàn toàn trên máy cá nhân 6 GB VRAM. Không mô hình nào tự làm trọn việc này, nên trọng tâm là điều phối. Hệ thống có ba tầng: giao diện web thuần, orchestrator FastAPI không import torch, và các worker chạy thành subprocess riêng để khi xong thì hệ điều hành trả lại toàn bộ VRAM. Luồng gồm bốn bước. Bước một lấy truyện từ thư mục, web hoặc để AI sáng tác, rồi dịch bằng LLM chạy local qua Ollama, có glossary và kiểm tra không còn chữ Hán. Bước hai đọc thành file WAV bằng TTS, chuẩn hóa âm lượng về −14 LUFS. Bước ba dùng LLM chia cảnh theo thời lượng lời đọc, viết prompt, sinh ảnh bằng Stable Diffusion 1.5 với khóa phong cách, LoRA và IP-Adapter, phóng to bằng Real-ESRGAN rồi dựng bằng ffmpeg. Bước bốn ghép các chương thành video tổng. Log chạy realtime qua SSE, mỗi bước dừng được và chạy lại được nhờ checkpoint. Ngoài ra có trợ lý AI local, tự chuyển sang chế độ tra cứu không tốn VRAM khi GPU đang bận. Kết quả: 173 test tự động đạt, 26 chương dịch không sót chữ Hán, VRAM đỉnh khoảng 4 GB."
