# Tổng quan hệ thống và Quy trình 5 bước

## Tổng quan ứng dụng
Tool Auto Make Cartoon Video 2D From Comics là hệ thống tự động hoá việc tạo video hoạt hình 2D từ truyện chữ hoặc truyện tranh. Quy trình gồm 5 bước khép kín từ nội dung thô đến sản phẩm video hoàn chỉnh.

## Quy trình các bước trên giao diện WebUI
- **Bước 1 — Cào & Dịch / AI Sáng Tác:** Nhập nguồn truyện (cào web, thư mục cục bộ, hoặc dùng AI viết mới), dịch sang tiếng Việt chuẩn và chia chương.
- **Bước 2 — Sinh Âm Thanh (TTS):** Chuyển văn bản từng chương thành file đọc âm thanh (.wav) với 5 engine TTS lựa chọn.
- **Bước 3 — Dựng Hoạt Hình (SD & Animate):** Tạo prompt hình ảnh cho từng câu, dùng Stable Diffusion và các công cụ Animate để tạo video/ảnh theo phong cách chọn sẵn.
- **Tự Động Tạo Phụ Đề (Autosub):** Khớp thời gian âm thanh với chữ (Whisper), tạo file sub (.ass/.srt), tự động chèn nhạc nền và né tiếng (ducking).
- **Bước 4 — Ghép Video:** Ghép các đoạn video, âm thanh và phụ đề thành video hoàn chỉnh (.mp4).

## Cấu trúc lưu trữ dữ liệu (storage)
Mọi dữ liệu làm việc nằm trong thư mục `storage/stories/<slug_truyen>/`:
- `raw/`: Các file chương chữ thô (`chuong_0001.md`).
- `audio/`: Các file âm thanh đọc chương (`chuong_0001.wav`).
- `video/`: Các đoạn video cảnh lẻ và video tổng hợp (`TongHop_chuong_0001.mp4`).
- `story.json`: Metadata tổng quan của truyện (trạng thái, thể loại, tiến độ).
