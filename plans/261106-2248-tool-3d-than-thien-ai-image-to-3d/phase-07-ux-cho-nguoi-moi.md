# Phase 07 — UX cho người mới

**Ưu tiên:** P1 · **Trạng thái:** pending · **Effort:** 3–4 ngày

## Nguyên tắc
- Không thuật ngữ 3D trên UI chính ("Giảm chi tiết" thay vì "Decimate"); thuật ngữ gốc chỉ hiện trong tooltip phụ.
- Mỗi màn hình tối đa ~7 nút chính; tính năng nâng cao gập trong "Nâng cao".
- Mọi thao tác đều Undo được → người mới dám thử.
- Không cần internet sau khi setup.

## Requirements
- Màn hình chào: 3 thẻ lớn — **Tạo từ ảnh** · **Bắt đầu từ khối có sẵn** · **Mở file**.
- Hướng dẫn lần đầu (5 bước, có thể bỏ qua): xoay camera, chọn vật, di chuyển, đổi màu, xuất file.
- Thư viện mẫu: 10–15 model có sẵn (GLB nhẹ, license CC0) để tập.
- Preset xuất theo mục đích: **Cho game (GLB, ≤ 20k tam giác)** · **Để in 3D (STL, sửa lỗi, mm)** · **Để chia sẻ (GLB + ảnh 360°)**.
- Thanh trạng thái VRAM/GPU + tiến độ job bằng lời ("Đang tách nền... 2/4").
- Thông báo lỗi tiếng Việt kèm cách khắc phục.
- Toàn bộ UI tiếng Việt (chuẩn bị file i18n để thêm EN sau).

## Files
```
webui/js/welcome-screen.js
webui/js/first-run-tutorial.js
webui/js/export-purpose-presets.js
webui/js/gpu-status-bar.js
webui/i18n/vi.json
webui/samples/*.glb
```

## Todo
- [ ] Welcome + tutorial
- [ ] Sample library
- [ ] Export presets
- [ ] GPU status bar + thông báo lỗi
- [ ] Test với 3 người chưa từng dùng 3D (quan sát, ghi lại chỗ vướng)

## Success criteria
- Người mới tạo model từ ảnh và xuất file trong < 5 phút, không hỏi ai.
