# Đợt 6 — Tính năng chạy bằng Blender headless

**Ưu tiên:** P2 · **Trạng thái:** DONE · Thay Phase 05 của plan gốc.

- Tải Blender 4.2 LTS portable vào `tools/blender/` khi bấm tính năng lần đầu (có thanh tiến độ, kiểm SHA256).
- Mỗi nút = 1 script `bpy` trong whitelist, chạy qua JobRunner (backend) như worker AI:
  Bo tròn cạnh (bevel), Làm lưới đều (voxel remesh), Sửa lỗi để in 3D (merge, fill holes, manifold), Tạo UV,
  Render đẹp (Cycles, 128 samples, GPU nếu có), Gắn xương tự động (Blender auto weights).
- Giao tiếp: UI xuất GLB vật đang chọn → backend → Blender → GLB → thay geometry (Undo được).
- Files: `blender_ops/run_op.py`, `blender_ops/op_*.py`, `backend/blender_environment.py`, `webui/js/blender-tools-panel.js`.

## Đã làm
- `scripts/setup-blender.bat`: Blender 4.2.23 LTS portable, ghim SHA256 chính thức, giải nén vào tools/blender/ (gitignore).
- `blender_ops/run_op.py` (+ `op_render.py`): bevel (chỉ cạnh > 30°), voxel remesh, repair (gộp điểm, bỏ mặt suy biến,
  khép lỗ, sửa pháp tuyến — báo số cạnh lỗi trước/sau), render Cycles (camera/nắng/nền từ app, shadow catcher, nền trong suốt
  rồi app lót màu nền, tự chọn OPTIX/CUDA/HIP).
- `backend/routes_blender.py`: whitelist thao tác + giới hạn mọi tham số; dùng chung hàng đợi job GPU (`submit_command`).
- UI: nhóm "🟠 Blender (chất lượng cao)" trong Sửa hình; ô "Render đẹp bằng Blender (Cycles)" trong Xuất ảnh.
- Kiểm thử trên máy AMD: bevel 12 -> 188 tam giác (0.2 s), repair 4 -> 0 cạnh lỗi, render HD bằng HIP.
- Chưa làm: Tạo UV tự động, gắn xương tự động bằng Blender (YAGNI tới khi cần).
