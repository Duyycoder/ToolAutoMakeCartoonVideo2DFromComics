# Đợt 1 — Công cụ sửa hình

**Ưu tiên:** P0 · **Trạng thái:** DONE

## UI
Nút **🛠 Sửa hình** trên toolbar trái → panel phải hiện nhóm "Sửa hình" khi có vật được chọn:
| Nút | Làm gì | Tham số (thanh trượt) |
|-----|--------|----------------------|
| Làm mượt | Taubin smoothing, tự chia nhỏ lưới ít đỉnh | Mức độ 1–10 |
| Giảm chi tiết | `SimplifyModifier` | Giữ lại 10–90% tam giác |
| Nhân đối xứng | Bản lật gương ở phía bên kia (trái ↔ phải) | – |
| Nhân mảng | N bản sao theo hàng / vòng tròn | Số lượng, khoảng cách |
| Ghép / Khoét / Phần chung | CSG giữa vật đang chọn và 1 vật khác (chọn từ danh sách) | Phép toán |
| Tách phần rời | Mỗi mảnh không dính nhau → 1 vật riêng | – |
| Gộp vật | Gộp nhiều vật thành 1 lưới | chọn vật cần gộp |

## Kiến trúc (đã làm)
- `webui/js/mesh-subdivide-smooth.js` — chia nhỏ, làm mượt, giảm chi tiết (hàm thuần).
- `webui/js/mesh-split-merge-operations.js` — bake toạ độ thế giới, tách phần rời, gộp, CSG (three-bvh-csg).
- `webui/js/mesh-tools-actions.js` (Undo) + `webui/js/mesh-tools-panel.js` (UI trong panel Tuỳ chỉnh).
- "Tách phần rời" trên nhóm (vd. kết quả Nhân mảng) = tách nhóm thành từng vật.

## Todo
- [x] mesh-geometry-operations + test trong ui-smoke-test
- [x] CSG
- [x] Panel UI + Undo
- [x] Smoke test các nút

## Rủi ro
- CSG cần lưới kín; model AI hở → báo lỗi thân thiện + gợi ý Đợt 6 "Sửa lỗi".
- Simplify trên mesh 200k tam giác chậm (vài giây) → hiện "Đang xử lý...".
