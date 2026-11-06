---
name: easy3d-blender-features
status: in-progress
created: 2026-11-07
blockedBy: []
blocks: []
---

# Easy3D — Thêm tính năng kiểu Blender (bản dễ dùng)

**Yêu cầu user:** công cụ sửa hình, nặn hình bằng cọ, animation, ánh sáng & render, ghép xương, xuất ảnh,
sửa chi tiết trong khối, tách khối, vật liệu, các tính năng nâng cao — **bản cho người không biết gì về 3D**.

## Nguyên tắc
- Làm trong trình duyệt (Three.js) khi được → chạy mọi máy, test được bằng `tests/ui-smoke-test.mjs`.
- Blender headless chỉ cho việc JS làm kém: bo cạnh (bevel), remesh, sửa lỗi in 3D, render Cycles (Đợt 6).
- Tên nút = kết quả người dùng muốn ("Làm mượt"), không phải tên thuật toán ("Laplacian").
- Mọi thao tác: Undo được, có thanh trượt mức độ, xem trước rồi mới áp dụng nếu chậm.
- Kế thừa plan gốc: [261106-2248](../261106-2248-tool-3d-than-thien-ai-image-to-3d/plan.md) — Phase 05 (Blender) gộp vào Đợt 6.

## Các đợt
| # | Đợt | Nội dung | Trạng thái |
|---|-----|----------|-----------|
| 1 | [Công cụ sửa hình](phase-01-cong-cu-sua-hinh.md) | Làm mượt, Giảm chi tiết, Đối xứng, Nhân mảng, Ghép/Cắt/Giao 2 vật (CSG), Tách phần rời, Gộp vật | DONE |
| 2 | [Vật liệu + ánh sáng + xuất ảnh](phase-02-vat-lieu-anh-sang-xuat-anh.md) | Thêm preset, chỉnh nâng cao, texture vân (gỗ, gạch, ca-rô...), ảnh làm texture; preset ánh sáng/nền, thêm đèn; xuất ảnh HD/nền trong suốt | DONE |
| 3 | [Nặn hình + sửa chi tiết](phase-03-nan-hinh-sua-chi-tiet.md) | Chỉnh điểm (Edit Mode) + **Nặn hình** (phím N): Đắp, Lõm (Shift đảo chiều), Kéo, Làm mượt, Làm phẳng, đối xứng trái↔phải | DONE |
| 4 | [Chuyển động](phase-04-chuyen-dong-animation.md) | Thanh thời gian, "Ghi tư thế" (keyframe), Bàn xoay 360°, phát/dừng, xuất video + GLB có animation | pending |
| 5 | [Ghép xương](phase-05-ghep-xuong.md) | Mẫu xương người/đuôi/chuỗi, đặt khớp bằng kéo, tự gán trọng lượng theo khoảng cách, chỉnh tư thế, dùng với Đợt 4 | pending |
| 6 | [Blender headless](phase-06-blender-headless.md) | Bo tròn cạnh, Làm lưới đều, Sửa lỗi in 3D, Tạo UV, Render đẹp (Cycles) | pending |

### Làm thêm theo yêu cầu (2026-11-07)
| Tính năng | Trạng thái |
|-----------|-----------|
| Chọn nhiều vật (Shift + bấm, Ctrl+A): gộp N vật giữ màu từng phần, ghép liền, nhóm lại (Ctrl+G), kéo/xoay cả nhóm, tô cùng màu | DONE |
| Tô vẽ (phím B): cọ Tô / Làm nhoè / Hút màu, cỡ + độ đậm, Tô hết, **Dán ảnh** lên mặt vật | DONE |
| Chỉnh điểm: sửa lỗi vào lần 2 không thấy điểm/lưới; "Xem tối giản" (mặt lì, vật khác mờ) | DONE |
| Hunyuan3D-2mini (chất lượng cao): `.venv-hunyuan` riêng, `scripts/setup-hunyuan3d.bat`, worker + tự dò hướng + chiếu màu ảnh, chọn model trong wizard | DONE — **chưa chạy thật trên GPU** |

Thứ tự làm: 1 → 2 → 3 → 4 → 5 → 6 (mỗi đợt xong là chạy + test được).

## Thư viện thêm (vendor, offline)
- `three-bvh-csg@0.0.17` (MIT) — ghép/cắt khối; `three-mesh-bvh@0.9.1` (MIT) — raycast nhanh cho cọ nặn + CSG.
- `three/addons/modifiers/SimplifyModifier.js` — giảm chi tiết.

## Câu hỏi mở
- Đợt 6 cần tải Blender ~350 MB: tải lúc setup hay khi bấm tính năng lần đầu? (mặc định: lần đầu dùng).
