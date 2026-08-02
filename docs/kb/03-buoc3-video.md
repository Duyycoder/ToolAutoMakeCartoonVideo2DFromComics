# Bước 3 — Sinh Hình Ảnh / Video

## Checkpoint & Style có sẵn
Tab Bước 3 tích hợp các checkpoint Stable Diffusion phổ biến:
- **Anything V5:** Phong cách Anime / Manga hoạt hình Nhật Bản sắc nét.
- **DreamShaper 8:** Đa dụng, cân bằng giữa nghệ thuật và tả thực.
- **MajicMix Realistic:** Phong cách ảnh người thật 3D / Chân thực.
- **Cetus-Mix:** Chuyên hoạt hình 2D/3D đẹp mắt.
- **RPG v4:** Chuyên game nhập vai, tiên hiệp, huyền ảo.
- **MeinaMix:** Chuyên anime 2D sắc nét.

## Chế độ Render (Render Mode)
- **classic:** Chế độ nối tiếp truyền thống (tạo prompt, sinh ảnh SD và Animate video từng cảnh).
- **studio:** Chế độ Studio Compositing chuyên nghiệp (hỗ trợ nhiều layer nhân vật, hậu kỳ nâng cao).

## Khuyến nghị GPU 6GB
- Nên dùng model `3b` cho Ollama nếu chạy cùng lúc.
- Chọn resolution `512x768` hoặc `768x512`, bật VRAM Optimization trong Cấu hình.
- Bật cờ `auto_unload_before_pipeline` để tự nhả LLM khỏi GPU trước khi Stable Diffusion bắt đầu render.
