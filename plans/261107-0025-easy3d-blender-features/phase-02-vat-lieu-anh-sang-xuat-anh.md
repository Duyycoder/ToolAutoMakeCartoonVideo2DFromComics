# Đợt 2 — Vật liệu, ánh sáng, xuất ảnh

**Ưu tiên:** P0 · **Trạng thái:** DONE

## Vật liệu
- Thêm preset: Cao su, Vàng, Chrome, Gốm sứ, Vải, Ngọc (trong mờ).
- "Nâng cao" (gập sẵn): thanh trượt Độ bóng, Kim loại, Trong suốt, Phát sáng.
- Vân bề mặt sinh bằng canvas (không cần file ảnh): Gỗ, Gạch, Ca-rô, Sọc, Đá hoa, Chấm bi + "Ảnh của bạn…" (chọn file ảnh).
- Model không có UV (AI) → tự tạo UV hình hộp (box projection) trước khi gán vân.

## Ánh sáng & nền
- Nút **💡 Ánh sáng** trên topbar: preset Studio, Ngoài trời, Hoàng hôn, Ban đêm, Sân khấu (đổi đèn, nền, môi trường).
- Thêm đèn vào cảnh như 1 vật thể: Đèn tròn (point), Đèn rọi (spot) — chọn, kéo, đổi màu/độ sáng.
- Bật/tắt lưới sàn.

## Xuất ảnh
- Hộp thoại "Xuất ảnh": độ phân giải (HD, Full HD, 4K), nền trong suốt, ẩn lưới tự động.

## Files
- `webui/js/material-preset-library.js` (mở rộng), `webui/js/procedural-texture-library.js`, `webui/js/appearance-actions.js`, `webui/js/appearance-panel-sections.js`
- `webui/js/lighting-presets.js`, `webui/js/scene-light-objects.js`, `webui/js/image-export-dialog.js`

## Todo
- [x] Preset + nâng cao + vân + ảnh texture
- [x] Ánh sáng preset + đèn
- [x] Xuất ảnh HD/trong suốt
- [x] Smoke test
