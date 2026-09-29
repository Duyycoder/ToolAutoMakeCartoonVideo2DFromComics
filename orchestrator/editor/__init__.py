"""Trình edit video: dự án = thư mục thật + dữ liệu editor trong `.duan/`.

Xem docs/PLAN-editor.md. Các module:
- `luu_tru`   ghi nguyên tử, phiên bản timeline, khoá dự án, lịch sử, nâng cấp schema 1→2
- `hang_doi`  hàng đợi tác vụ (mỗi hàng chạy 1 việc một lúc) + trạng thái tác vụ trong dự án
- `workspace` Nơi làm việc: quét/tạo/xoá dự án
- `media`     đọc thông số bằng `ffmpeg -i`, nhập (chép) media, thumbnail, sóng âm, proxy
- `api`       các route FastAPI `/api/workspace`, `/api/du-an/...`, `/api/hang-doi`
"""
