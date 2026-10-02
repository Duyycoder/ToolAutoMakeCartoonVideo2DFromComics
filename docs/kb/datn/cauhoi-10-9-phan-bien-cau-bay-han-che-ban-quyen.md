# 9. Phản biện, câu bẫy, hạn chế, bản quyền

Phần lớn câu bẫy xoáy vào chỗ lệch giữa báo cáo, lời nói và code. Hai nguyên tắc: tách "code có" với "code chạy mặc định", và không bịa số.

## 9.1 Chỗ lệch phải thống nhất trước ngày bảo vệ

- **#:** 9.1.1 · **Báo cáo / lời nói:** Studio là `render_mode` mặc định (mục 4.5, Bảng 4.3, Bảng 4.5, Bảng 3.20) · **Thực tế code hoặc máy demo (01/10):** Mặc định code là `classic` ( `MC/app/config.py:86` , `adapter_video_cli.py:101` ); `global_config.json` máy hiện cũng `classic` · **Cách trả lời an toàn:** "Studio là hướng thiết kế chính; mặc định an toàn là Classic vì với thủy mặc coverage chỉ 0,003; Studio tự lùi Classic từng cảnh."
- **#:** 9.1.2 · **Báo cáo / lời nói:** Studio tự huấn luyện Character LoRA cho 2 nhân vật chính · **Thực tế code hoặc máy demo (01/10):** Code mặc định bật nhưng chỉ chạy trong Studio; `resource/character_loras/` trống · **Cách trả lời an toàn:** "Cơ chế có và có test; trên máy demo em tắt để tiết kiệm thời gian."
- **#:** 9.1.3 · **Báo cáo / lời nói:** Zero Tolerance chữ Hán · **Thực tế code hoặc máy demo (01/10):** Sau khi vá hết lượt, còn ≤ 5 ký tự Hán vẫn chấp nhận (UC04 cũng ghi vậy) · **Cách trả lời an toàn:** Zero Tolerance là tiêu chí phát hiện; 0/214.034 là số đo.
- **#:** 9.1.4 · **Báo cáo / lời nói:** Cổng 0,75 từ chối câu ngoài phạm vi, không gọi LLM; từ chối 7/8 · **Thực tế code hoặc máy demo (01/10):** Từ 01/10: không khớp thì gọi LLM với prompt suy luận có nhãn "`⚠️` Ngoài tài liệu" · **Cách trả lời an toàn:** "Sau khi nộp em đổi vì người dùng hỏi câu chính đáng nhưng lệch từ khóa bị bỏ dở; số đo từ chối cần đo lại." Hoặc hoàn lại bản cũ trước buổi bảo vệ — cần quyết định.
- **#:** 9.1.5 · **Báo cáo / lời nói:** LLM lập kế hoạch cảnh (kiểm 3 bất biến, fallback `md_parser` ) · **Thực tế code hoặc máy demo (01/10):** Viết lại 01/10: LLM chỉ đánh mốc, code dựng và cân cảnh 20/40/60 s · **Cách trả lời an toàn:** Xem 2.5.2: vì context 4.096 của Ollama.
- **#:** 9.1.6 · **Báo cáo / lời nói:** UC14: giao diện không có thao tác xóa truyện · **Thực tế code hoặc máy demo (01/10):** Có `PATCH/DELETE` `/api/stories/{name}` + quản lý tài liệu chatbot, chưa commit · **Cách trả lời an toàn:** Bổ sung sau nộp; hoặc không demo phần này.
- **#:** 9.1.7 · **Báo cáo / lời nói:** NFR01 "ghi lỗi vào job"; Kết luận "mở rộng bảng jobs" · **Thực tế code hoặc máy demo (01/10):** Bảng `jobs` 0 dòng, `add_job` chưa được gọi · **Cách trả lời an toàn:** Nhận thẳng, chỉ cách nối (mẫu 7.9).
- **#:** 9.1.8 · **Báo cáo / lời nói:** 173 test · **Thực tế code hoặc máy demo (01/10):** 223 test (01/10) · **Cách trả lời an toàn:** Nói số báo cáo trước, bổ sung số mới.
- **#:** 9.1.9 · **Báo cáo / lời nói:** Nguồn mặc định là thư mục cục bộ; phong cách thủy mặc; 8 bước, CFG 5.0; TTS Edge · **Thực tế code hoặc máy demo (01/10):** `global_config.json` máy hiện: `crawler.default_site =` `biquge` , `video.default_style =` `dreamshaper_cinematic` , `sd_steps = 28` , `sd_guidance =` `10` , `translate.default_engine =` `gemini_api` , `tts.default_engine` `= kokoro` · **Cách trả lời an toàn:** Sửa cấu hình máy demo cho khớp lời nói, hoặc nói rõ "cấu hình máy em đang chỉnh thử; mặc định code là …".
- **#:** 9.1.10 · **Báo cáo / lời nói:** Dữ liệu demo sạch bản quyền · **Thực tế code hoặc máy demo (01/10):** Tab Thống kê máy hiện liệt kê 11 truyện, nhiều tên là truyện mạng/fanfic (vd "Bảng học tập Hogwarts") · **Cách trả lời an toàn:** Trước khi demo chuyển `storage_dir` sang `storage_demo` hoặc dọn; không để hội đồng thấy.
- **#:** 9.1.11 · **Báo cáo / lời nói:** Slide: kiến trúc 3 tầng; báo cáo: 4 tầng · **Thực tế code hoặc máy demo (01/10):** Cùng kiến trúc · **Cách trả lời an toàn:** Xem 4.2.
- **#:** 9.1.12 · **Báo cáo / lời nói:** Bìa "FLATFORM" · **Thực tế code hoặc máy demo (01/10):** Lỗi đánh máy · **Cách trả lời an toàn:** Nhận lỗi.

## 9.2 Câu bẫy thường gặp

### 9.2.1 "Em tự huấn luyện Stable Diffusion à?"
- **Bẫy ở đâu:** Nói "có" là sai
- **Trả lời đúng:** Không. Dùng checkpoint có sẵn, chỉ train LoRA (1,6–3,2 triệu tham số).

### 9.2.2 "Chatbot dùng vector DB đúng không?"
- **Bẫy ở đâu:** Repo có FAISS
- **Trả lời đúng:** Không; IDF lexical. FAISS là cache TTS, mặc định tắt.

### 9.2.3 "Whisper đồng bộ phụ đề trong video truyện?"
- **Bẫy ở đâu:** Whisper bị tắt trong luồng truyện
- **Trả lời đúng:** Timing theo tỷ lệ số từ; Whisper chỉ ở Autosub.

### 9.2.4 "Có hiệu ứng chuyển cảnh không?"
- **Bẫy ở đâu:** Không có
- **Trả lời đúng:** Slideshow ảnh tĩnh; hướng zoompan/xfade.

### 9.2.5 "Face detailer luôn chạy?"
- **Bẫy ở đâu:** Mặc định tắt
- **Trả lời đúng:** Tùy chọn, tắt vì chậm.

### 9.2.6 "Phụ đề có cháy vào video không?"
- **Bẫy ở đâu:** `burn_subtitles=False`
- **Trả lời đúng:** Có tùy chọn, mặc định tắt; SRT vẫn sinh.

### 9.2.7 "Temperature thấp để làm gì?"
- **Bẫy ở đâu:** Đừng nói "cho chính xác" chung chung
- **Trả lời đúng:** Chia logit trước softmax, phân phối nhọn, gần tất định.

### 9.2.8 "API key có bị lộ không?"
- **Bẫy ở đâu:** Có rủi ro
- **Trả lời đúng:** Lộ trong danh sách tiến trình; sửa bằng biến môi trường.

### 9.2.9 "Chạy CPU được không?"
- **Bẫy ở đâu:** —
- **Trả lời đúng:** Được về kỹ thuật, sinh ảnh rất chậm.

### 9.2.10 "Agent tự chạy pipeline?"
- **Bẫy ở đâu:** Gọi "agent" dễ bị hiểu là ReAct
- **Trả lời đúng:** Router regex; chạy bước cần người dùng bấm xác nhận.

### 9.2.11 "State machine ép thứ tự bước chứ?"
- **Bẫy ở đâu:** Không ép
- **Trả lời đúng:** Điều kiện thật là tệp trên đĩa, có chủ đích để chạy lại từng bước.

### 9.2.12 "Resume nằm ở orchestrator à?"
- **Bẫy ở đâu:** Không
- **Trả lời đúng:** Resume nằm ở từng bước (bỏ qua `[VI]` , `.wav` , `batch_state.json` ); auto- run mất khi restart.

### 9.2.13 "Số liệu đo trên 1 máy có suy rộng được không?"
- **Bẫy ở đâu:** —
- **Trả lời đúng:** Không suy rộng; có cơ chế thích nghi phần cứng nhưng chưa benchmark nhiều GPU.

### 9.2.14 "Em có hiểu code do AI viết không?"
- **Bẫy ở đâu:** Câu dễ bị hỏi
- **Trả lời đúng:** Trả lời trung thực; chứng minh bằng một quyết định cụ thể có số liệu: `taskkill` `/T` thay `terminate()` , CFG 5.0 thay 1.5, IDF thay BM25, tách cảnh theo mốc vì context 4.096.

### 9.2.15 "Video này làm tay có nhanh hơn không?"
- **Bẫy ở đâu:** So sánh không cùng điều kiện
- **Trả lời đúng:** Làm tay: mỗi chương hàng chục cảnh vẽ + thu âm; hệ thống chạy không cần người, ~3,47× thời lượng trên 6 GB. Chưa đo thời gian làm tay để so.

### 9.2.16 "Tại sao không dùng dịch vụ có sẵn cho nhanh?"
- **Bẫy ở đâu:** —
- **Trả lời đúng:** Mục tiêu là cục bộ, không phí, không gửi nội dung ra ngoài, giữ nhân vật qua nhiều chương.

## 9.3 Bản quyền, pháp lý, đạo đức AI

### 9.3.1 Cào truyện từ web có vi phạm bản quyền không?
- **Mức:** ★★★
- **Ý trả lời chính:** Có rủi ro nếu phát tán lại. Thiết kế: nguồn hợp lệ là tệp tự chuẩn bị, public domain (vd Tây Du Ký), nội dung AI viết; crawler là tùy chọn, trách nhiệm thuộc người vận hành; không phát tán, không lưu tập trung. Thừa nhận crawler có kỹ thuật vượt Cloudflare và chưa đọc robots.txt.

### 9.3.2 Video sinh ra từ truyện có bản quyền thì ai chịu trách nhiệm? Đăng lên YouTube được không?
- **Mức:** ★★
- **Ý trả lời chính:** Tác phẩm phái sinh vẫn cần quyền của tác giả gốc; công cụ không tự đăng, người dùng chịu trách nhiệm với nội dung họ đưa vào.

### 9.3.3 Giấy phép các mô hình?
- **Mức:** ★★
- **Ý trả lời chính:** SD1.5: CreativeML OpenRAIL-M (cho dùng lại, có điều khoản cấm dùng có hại). Checkpoint cộng đồng (anything- v5, dreamshaper) cần kiểm riêng. XTTSv2: giấy phép Coqui hạn chế thương mại. Edge TTS là dịch vụ Microsoft. Không chắc thì nói "em sẽ kiểm tra lại".

### 9.3.4 Dữ liệu train LoRA phong cách có hợp pháp không?
- **Mức:** ★★
- **Ý trả lời chính:** Chỉ ảnh public domain/CC0 từ Met Museum Open Access, có `manifest.json` ghi nguồn từng ảnh.

### 9.3.5 Nguy cơ nội dung độc hại, deepfake giọng nói?
- **Mức:** ★★
- **Ý trả lời chính:** Có: `safety_checker=None` , Gemini `BLOCK_NONE` , XTTS clone giọng từ mẫu. Giảm thiểu: chạy cục bộ một người, không phát tán tự động; hướng: bộ lọc nội dung, cảnh báo và xác nhận đồng ý khi clone giọng, đánh dấu nội dung do AI tạo.

### 9.3.6 Dữ liệu cá nhân, Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15?
- **Mức:** ★★
- **Ý trả lời chính:** Mọi dữ liệu nằm trên máy người dùng, không gửi lên server (trừ khi chọn Edge/Gemini); giọng mẫu để clone là dữ liệu sinh trắc học, cần sự đồng ý của chủ giọng. Báo cáo viện dẫn luật này ở lý do chọn đề tài — nắm được ý chính.

### 9.3.7 Proxy Gemini dùng cookie có hợp lệ?
- **Mức:** ★★
- **Ý trả lời chính:** Có thể vi phạm điều khoản dịch vụ; chỉ là tùy chọn lúc phát triển, không dùng khi demo.

## 9.4 Hạn chế và hướng phát triển

### 9.4.1 Hạn chế lớn nhất của đề tài?
- **Mức:** ★
- **Ý trả lời chính:** Video tĩnh; Studio chưa mặc định; chưa đo MOS/CLIP; chỉ đo 1 máy; API không xác thực; key qua CLI; JSON không atomic; auto-run trong RAM; chưa có test E2E GPU, CI chưa chạy Windows.

### 9.4.2 Hướng phát triển gần nhất, làm được ngay?
- **Mức:** ★
- **Ý trả lời chính:** zoompan/xfade; ghi job vào `jobs` ; atomic write; key qua env; bỏ merge trùng; đo lại eval chatbot với held-out set.

### 9.4.3 Hướng dài hạn?
- **Mức:** ★★
- **Ý trả lời chính:** AnimateDiff/SVD khi có GPU lớn hơn; forced alignment/WordBoundary từ TTS để timing chính xác; hybrid retrieval (embedding CPU + IDF); hàng đợi GPU và đa người dùng; benchmark nhiều GPU; bộ MOS/CLIP.

### 9.4.4 Nếu có GPU 24 GB em sẽ đổi gì?
- **Mức:** ★★
- **Ý trả lời chính:** SDXL/Flux cho ảnh đẹp hơn, giữ các model cùng lúc trong VRAM (bỏ 2-pass), LLM lớn hơn cho chia cảnh, video diffusion cho một số cảnh quan trọng.

### 9.4.5 Đề tài có tính mới/khoa học gì, hay chỉ ghép thư viện?
- **Mức:** ★★
- **Ý trả lời chính:** Không đề xuất mô hình mới; đóng góp là kỹ thuật hệ thống: điều phối nhiều mô hình trên 6 GB có checkpoint, các cơ chế kiểm soát đầu ra LLM bằng code, kèm số đo so sánh (IDF vs BM25, CFG 1.5 vs 5.0, quét trọng số LoRA). Đây là đồ án KTPM nên trọng tâm là thiết kế và hiện thực phần mềm.

### 9.4.6 Phần khó nhất em gặp?
- **Mức:** ★★
- **Ý trả lời chính:** Chọn một chuyện có số: dải đen VAE tiling fp16 (9/41 frame, sửa + test); tiến trình cháu giữ pipe khi dừng ( `taskkill` `/T` ); context 4.096 cắt truyện khi tách cảnh.
