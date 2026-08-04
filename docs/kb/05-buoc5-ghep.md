# Bước 4 — Ghép Video (Video Merger)

## Chức năng ghép video
Bước 4 dùng FFmpeg ghép các đoạn video cảnh lẻ, file âm thanh thuyết minh và file phụ đề `.ass` thành video sản phẩm hoàn chỉnh `.mp4` trong thư mục `storage/truyen/<slug>/video/`.

## Tối ưu hiệu năng ghép
- Quá trình ghép bằng FFmpeg chỉ chạy trên CPU / NVENC phần cứng ghép video, không chiếm dung lượng VRAM của Stable Diffusion hay LLM.
- Tên video tổng hợp xuất ra có tiền tố `TongHop_chuong_XXXX.mp4`.
