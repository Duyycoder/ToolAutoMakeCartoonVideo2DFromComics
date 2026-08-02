# Bước 2 — Sinh Âm Thanh (TTS)

## Các Engine TTS hỗ trợ
Hệ thống hỗ trợ 5 bộ máy đọc giọng nói:
1. **Edge-TTS:** Miễn phí, giọng đọc tự nhiên của Microsoft, không tốn VRAM. (Khuyên dùng mặc định).
2. **Piper-TTS:** Đọc siêu nhanh offline, nhẹ, không tốn GPU.
3. **XTTS v2:** Giọng đọc đa dạng, hỗ trợ clone giọng, chiếm ~2GB VRAM.
4. **Kokoro-TTS:** Giọng chất lượng cao, nhẹ.
5. **VieNeu-TTS:** Engine giọng tiếng Việt chuyên sâu.

## Khuyến nghị GPU 6GB
Với GPU 6GB (RTX 2060/3050/3060 6GB), nên chọn **Edge-TTS** hoặc **Piper-TTS** để giữ VRAM rảnh cho Bước 3 sinh ảnh/video.

## Cân bằng âm lượng (LUFS) và Cache
- Âm thanh sinh ra được chuẩn hoá LUFS tự động để âm lượng các chương đồng đều.
- Các câu đã đọc được lưu cache trong thư mục câu, giúp chạy lại không tốn thời gian sinh lại.
