# Câu hỏi của người mới bắt đầu

## Tôi không có API key trả phí thì dùng được không?
Được, và đây là cấu hình mặc định. Toàn bộ quy trình chạy được **hoàn toàn cục bộ,
không cần API key trả phí nào**:
- Dịch và sáng tác: **Gemini Local** qua proxy chạy trên máy ở cổng `7860`, hoặc **Ollama**.
- Sinh giọng đọc: **Kokoro / VieNeu / Piper** chạy offline. Edge-TTS là lựa chọn
  online nhưng miễn phí.
- Sinh ảnh: **Stable Diffusion** chạy trên GPU của bạn.

Ô "Gemini API Key" trong Cấu Hình Chung chỉ cần thiết nếu bạn chủ động chọn engine
**Gemini Online**. Bỏ trống thì các engine cục bộ vẫn chạy bình thường.

## Bắt buộc phải có GPU NVIDIA không?
Nên có. Cấu hình khuyến nghị là GPU NVIDIA từ 6GB VRAM trở lên. Không có GPU thì
vẫn chạy được nhờ cơ chế lùi về CPU, nhưng Bước 3 (dựng hoạt hình) sẽ chậm tới mức
khó dùng thực tế. Bước 1 và Bước 2 với engine nhẹ thì CPU vẫn kham được.

## Cần làm tối thiểu những gì để ra được một video?
Bốn bước, theo đúng thứ tự:
1. **Tạo truyện mới** ở thanh bên trái, đặt tên bất kỳ.
2. **Bước 1 — Nguồn & Dịch:** chọn nguồn truyện rồi chạy. Nhanh nhất để thử là chọn
   **Thư mục cục bộ** và trỏ vào một thư mục có sẵn file `.md`/`.txt`.
3. **Bước 2 — Sinh Giọng:** chạy để tạo file `.wav` cho từng chương.
4. **Bước 3 — Dựng Hoạt Hình:** chạy để sinh ảnh và ghép thành video từng chương.

Muốn nối các chương thành một video dài thì làm thêm **Bước 4 — Ghép Video**.
Nút **Chạy tự động 1→4** làm liền mạch cả chuỗi thay cho việc bấm từng bước.

## Nên thử bằng truyện nào cho an toàn bản quyền?
Dùng nguồn **Thư mục cục bộ** với truyện bạn tự viết hoặc tác phẩm thuộc phạm vi
công cộng, hoặc dùng nguồn **Sáng tác bằng AI** để máy tự viết truyện mới. Cả hai
cách đều không cào nội dung của người khác.

## Chạy hết một chương mất bao lâu?
Phụ thuộc máy và độ dài chương. Bước 1 và Bước 2 thường tính bằng phút. Bước 3 nặng
nhất vì phải sinh ảnh cho từng cảnh — trên GPU 6GB, một chương có thể mất từ vài
chục phút trở lên. Hãy thử với một chương trước khi chạy cả bộ truyện.

## Đang chạy giữa chừng có tắt ứng dụng được không?
Được, nhưng tiến trình đang chạy sẽ bị dừng. Phần đã làm xong vẫn giữ nguyên trên
đĩa, nên mở lại và chạy tiếp bước đó sẽ không phải làm lại từ đầu.

## Làm sao biết một chương đã có giọng đọc hay video chưa?
Hỏi trợ lý "truyện này có bao nhiêu chương, bao nhiêu audio, bao nhiêu video", hoặc
xem tab **Thống Kê**. Trên đĩa, file `.wav` nằm cạnh file `.md` trong
`storage/truyen/<slug>/raw/`, còn video nằm trong thư mục `video/` của truyện.

## Trợ lý AI này trả lời được những gì?
Hai nhóm: cách vận hành ứng dụng, và dữ liệu truyện đang có trên máy bạn. Nó không
tra cứu Internet và không trả lời các chủ đề ngoài phạm vi ứng dụng.
