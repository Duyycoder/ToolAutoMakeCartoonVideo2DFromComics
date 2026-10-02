# 3. Phân tích yêu cầu và UML

Báo cáo chương 3 có 9 nhóm yêu cầu chức năng (FR01–FR09), 7 yêu cầu phi chức năng (NFR01–NFR07), 16 use case (UC01–UC16) chia 4 nhóm, 16 biểu đồ VOPC và 8 biểu đồ trình tự. Hội đồng KTPM thường chỉ vào một hình rồi hỏi ký pháp.

## 3.1 Hệ thống có những tác nhân nào? Sao chỉ có "Người dùng"?
- **Mức:** ★
- **Ý trả lời chính:** Một tác nhân: người dùng vận hành máy cá nhân. Mô hình AI, FFmpeg, SQLite, hệ thống tệp là thành phần bên trong, không vẽ là actor, để use case mô tả mục tiêu người dùng chứ không phải lưu đồ kỹ thuật.
- **Tra ở:** Báo cáo 3.1.1

## 3.2 Ollama hay Gemini là hệ thống bên ngoài, sao không vẽ thành actor phụ?
- **Mức:** ★★
- **Ý trả lời chính:** Câu hay bị bắt bừa. Trả lời: Ollama chạy cục bộ do hệ thống tự khởi động/quản lý nên coi là thành phần trong; Gemini là tùy chọn. Nếu thầy/cô yêu cầu vẽ theo kiểu secondary actor thì có thể thêm "Dịch vụ LLM" và "Trang nguồn" bên phải biểu đồ.
- **Tra ở:** Báo cáo 3.1.1

## 3.3 Yêu cầu chức năng gồm gì? Ưu tiên ra sao?
- **Mức:** ★
- **Ý trả lời chính:** FR01 Quản lý truyện, FR02 Nguồn và nội dung, FR03 Giọng đọc, FR04 Storytelling Studio, FR05 Dựng và ghép video, FR06 Điều phối, FR08 Trợ lý AI — ưu tiên Cao; FR07 Cấu hình/dữ liệu, FR09 Phụ đề và lồng tiếng — Trung bình.
- **Tra ở:** Bảng 3.1

## 3.4 Yêu cầu phi chức năng gồm gì? Đo được không?
- **Mức:** ★
- **Ý trả lời chính:** NFR01 Phục hồi, NFR02 Quan sát, NFR03 Hiệu năng/tài nguyên (VRAM 6 GB), NFR04 Bảo trì, NFR05 An toàn dữ liệu, NFR06 An toàn AI, NFR07 Khả dụng. Đo được: VRAM đỉnh 4,0 GB, thời gian 3,47× thời lượng, resume bằng `batch_state.json` . NFR04/NFR07 đánh giá định tính.
- **Tra ở:** Bảng 3.2, chương 5

## 3.5 Kể tên các use case.
- **Mức:** ★
- **Ý trả lời chính:** Quản lý: UC01 Khởi tạo/chọn truyện, UC14 Quản lý dữ liệu, UC15 Dọn dữ liệu tạm. Nội dung: UC02 Nhập/thu thập, UC03 Sáng tác AI, UC04 Dịch, UC05 Trích glossary. Sản xuất: UC06 Sinh giọng, UC07 Sinh ảnh + dựng video, UC08 Ghép video, UC09 Autosub. Vận hành: UC10 AutoRun, UC11 Theo dõi tiến độ, UC12 Dừng, UC13 Đồng bộ trạng thái chương, UC16 Trợ lý AI.
- **Tra ở:** Bảng 3.3

## 3.6 «include» và «extend» khác nhau thế nào? Cho ví dụ trong báo cáo.
- **Mức:** ★★
- **Ý trả lời chính:** include: hành vi luôn xảy ra, mũi tên từ UC cơ sở tới UC được gộp (UC04 luôn kiểm chữ Hán; UC10 luôn gồm UC11). extend: hành vi có điều kiện, mũi tên từ UC mở rộng về UC cơ sở (UC05 extend UC04 khi bật quét; lùi Classic extend UC07; UC12 extend UC10; tra cứu 0-VRAM extend UC16).
- **Tra ở:** Báo cáo 3.2.1, Hình 3.2–3.4

## 3.7 Sao biểu đồ tổng quát không có include/extend?
- **Mức:** ★★
- **Ý trả lời chính:** Chủ đích: tổng quát chỉ gom theo mục tiêu người dùng (4 nhóm); quan hệ chi tiết đặt ở biểu đồ phân rã để không rối.
- **Tra ở:** Báo cáo 3.2.1

## 3.8 "Dừng pipeline" (UC12) là use case hay chỉ là một nút?
- **Mức:** ★★
- **Ý trả lời chính:** Là mục tiêu có giá trị riêng cho người dùng (giải phóng GPU, hủy chạy sai), có luồng sự kiện và ngoại lệ riêng (diệt cây tiến trình, CANCELLED, 404 khi không có tiến trình).
- **Tra ở:** Bảng 3.15

## 3.9 Một đặc tả use case gồm những mục nào? Đọc đặc tả UC01.
- **Mức:** ★
- **Ý trả lời chính:** Tên, tác nhân, mô tả, điều kiện tiên quyết, luồng chính, luồng rẽ nhánh/ngoại lệ, hậu điều kiện. UC01: nhập tên → `POST` `/api/stories` tạo `raw/` , `video/` , `story.json` (CREATED, pipeline_step 1); tên rỗng 400, trùng 409.
- **Tra ở:** Bảng 3.4

## 3.10 Đặc tả UC04 ghi "còn ≤ 5 ký tự Hán thì chấp nhận", vậy Zero Tolerance ở đâu?
- **Mức:** ★★★
- **Ý trả lời chính:** Zero Tolerance là tiêu chí phát hiện: một ký tự Hán cũng kích hoạt dịch lại. Sau khi hết lượt vá, code nới lỏng: còn ≤ 5 ký tự thì giữ bản dịch kèm cảnh báo (tốt hơn chèn marker). Kết quả 0/214.034 là số đo thực tế trên 26 chương, không phải bảo đảm tuyệt đối.
- **Tra ở:** `ollama_translator.py:709-` `714` , `translator/base.py:188-` `196`

## 3.11 UC14 ghi "giao diện không có thao tác xóa truyện", nhưng app demo lại có nút xóa/đổi tên?
- **Mức:** ★★★
- **Ý trả lời chính:** Code trên máy đang có thêm Dashboard xem/sửa/xóa truyện và quản lý tài liệu chatbot ( `PATCH/DELETE` `/api/stories/{name}` , `/api/kb` ), chưa có trong báo cáo và chưa commit. Chuẩn bị câu: "đây là phần em bổ sung sau khi nộp, đặc tả UC14 sẽ cập nhật", hoặc không demo phần này.
- **Tra ở:** `orchestrator/main.py:264-` `420`

## 3.12 Biếu đồ hoạt động (Hình 3.6) có mấy làn, nói gì?
- **Mức:** ★★
- **Ý trả lời chính:** Bốn swimlane: Người dùng (bấm "Chạy tự động 1→4", nhận video), AutoRunManager (chạy chuỗi, lỗi/dừng thì ghi *_FAILED/CANCELLED), Worker (các bước, quality gate, fallback Classic), Lưu trữ.
- **Tra ở:** Báo cáo 3.3

## 3.13 VOPC là gì? Boundary, control, entity là gì?
- **Mức:** ★★
- **Ý trả lời chính:** View of Participating Classes: các lớp tham gia hiện thực một use case. Boundary tiếp nhận/hiển thị (vd `SSE_ProgressView` , `WebUI_ConfirmDialog` ), control điều phối nghiệp vụ ( `NovelPipeline` , `AutoRunManager` , `QualityGate` ), entity lưu trạng thái bền ( `Chapter` , `Glossary` , `Job` ).
- **Tra ở:** Báo cáo 3.6

## 3.14 Lớp `StateScanner` , `ContentValidator` , `QualityGate` trong VOPC có trong code không?
- **Mức:** ★★★
- **Ý trả lời chính:** Là lớp khái niệm ở mức phân tích, ánh xạ vào hàm/lớp thật: `StateScanner` → `StorageManager.scan_chapters` ; `ContentValidator` → kiểm leak trong `translator/base.py` ; `QualityGate` → `alpha_coverage` + `MatteQualityError` trong Studio. Báo cáo mục 4.10 có bảng đối chiếu thiết kế với hiện thực.
- **Tra ở:** Báo cáo 3.6, 4.10

## 3.15 Biếu đồ trình tự UC07: ngoài ScenePlanner còn gì? Thông điệp 12 là gì?
- **Mức:** ★★
- **Ý trả lời chính:** NovelPipeline nhận Bước 3; ScenePlanner lập cảnh, chia độ dài WAV theo số từ, sinh SRT; mỗi cảnh sinh nền, nhân vật, tách nền qua QualityGate, ghép lớp; thông điệp 12 là chuyển Classic khi không đạt.
- **Tra ở:** Hình 3.32

## 3.16 Biếu đồ trình tự Trợ lý AI thể hiện khóa và mức GPU thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** ChatManager giữ khóa để mỗi lúc xử lý một câu (thông điệp 3), trả mức bận GPU (4–5); heavy thì chỉ tra cứu 0-VRAM; ngược lại lệnh cần xác nhận, câu hỏi gọi LLMClient, stream NDJSON.
- **Tra ở:** Hình 3.36

## 3.17 Phân biệt biểu đồ lớp miền và biểu đồ lớp triển khai trong báo cáo.
- **Mức:** ★★
- **Ý trả lời chính:** Miền (Hình 3.11): 6 lớp nghiệp vụ StoryProject, Chapter, StoryContext, Scene, CharacterLayer, CharacterProfile. Triển khai (Hình 3.12): lớp điều phối và phụ thuộc «use»: AutoRunManager, NovelPipeline, ProcessManager, StorageManager, BaseTTSEngine «interface», StorytellingPipeline, ChatManager.
- **Tra ở:** Báo cáo 3.5

## 3.18 Hợp thành (composition) và kết tập (aggregation) khác gì? Ví dụ trong mô hình lớp?
- **Mức:** ★★
- **Ý trả lời chính:** Composition (kim cương đặc): vòng đời con phụ thuộc cha — StoryProject◆Chapter, Chapter◆Scene, Scene◆CharacterLayer. Aggregation (kim cương rỗng): con tồn tại độc lập — StoryContext◇CharacterProfile vì hồ sơ nhân vật và LoRA tái sử dụng được.
- **Tra ở:** Báo cáo 3.5

## 3.19 Association, dependency, generalization, realization khác gì?
- **Mức:** ★★
- **Ý trả lời chính:** Association: quan hệ cấu trúc bền (CharacterLayer tham chiếu CharacterProfile). Dependency «use»: dùng tạm thời (NovelPipeline dùng ProcessManager). Generalization: kế thừa ( `Shuba69Parser` kế thừa `BaseSourceParser` ). Realization: cài đặt interface (các engine TTS cài `BaseTTSEngine` ).
- **Tra ở:** Báo cáo 3.5

## 3.20 Máy trạng thái (Hình 3.9) và trạng thái chương suy ra thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** Trạng thái truyện trong `story.json` ; *ING (tô xám) là bước đang chạy, dừng → CANCELLED, lỗi → *_FAILED. Trạng thái chương suy từ tệp: có `.mp4` là video, có `.wav` là tts, còn lại là text (ưu tiên video > tts > text).
- **Tra ở:** Báo cáo 3.4, UC13

## 3.21 Ràng buộc pháp lý được đưa vào yêu cầu thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** Mục 3.1.3: nguồn hợp lệ là tệp tự chuẩn bị (mặc định), public domain, nội dung AI sáng tác; nguồn web tùy chọn, trách nhiệm thuộc người vận hành; không phát tán, không lưu tập trung.
- **Tra ở:** Báo cáo 3.1.3

## 3.22 Thiết kế giao diện gồm những vùng nào? Sao ghi "Bước 4" nhưng endpoint step5?
- **Mức:** ★★
- **Ý trả lời chính:** Thanh điều hướng theo bước, vùng cấu hình giữa, log/tiến độ phải; nút AutoRun luôn hiển thị; widget Trợ lý AI nổi. Step4 là Autosub tách thành mục riêng, ghép video giữ tên step5.
- **Tra ở:** Báo cáo 3.8

## 3.23 Em thu thập yêu cầu từ đâu?
- **Mức:** ★
- **Ý trả lời chính:** Từ khảo sát nhóm giải pháp (dịch vụ online, ComfyUI, script rời — mục 1.3), từ trải nghiệm làm thủ công quy trình truyện → video, và ràng buộc phần cứng 6 GB. Không có khách hàng thật; nói thẳng điều này.
- **Tra ở:** Báo cáo 1.3–1.5
