# Sự Cố Thường Gặp (FAQ & Troubleshooting)

## Lỗi Hết Bộ Nhớ GPU (CUDA Out of Memory - OOM)
- **Nguyên nhân:** Chạy đồng thời Stable Diffusion Bước 3 và LLM Ollama hoặc Whisper trên GPU 6GB.
- **Cách khắc phục:** 
  1. Bật `auto_unload_before_pipeline` trong Cấu Hình Chung.
  2. Dùng model Ollama 3B thay vì 7B.
  3. Chọn engine Edge-TTS ở Bước 2 (không tốn VRAM).

## Ollama Ngoại Tuyến (Badge Xám / Offline)
- **Nguyên nhân:** Dịch vụ Ollama chưa được bật hoặc chưa cài đặt.
- **Cách khắc phục:** Mở Terminal và gõ `ollama serve`. Nếu chưa cài, tải Ollama từ trang chủ và chạy `ollama pull qwen2.5:3b`.

## Video sinh ra không có tiếng
- **Nguyên nhân:** Bước 2 chưa được chạy hoặc bị lỗi không tạo ra file `.wav` trong `storage/stories/<slug>/audio/`.
- **Cách khắc phục:** Kiểm tra tab Bước 2, bấm chạy lại TTS cho các chương bị thiếu âm thanh trước khi chạy Bước 5.
