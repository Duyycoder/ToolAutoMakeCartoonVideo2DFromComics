# Đợt 6 — Tính năng chạy bằng Blender headless

**Ưu tiên:** P2 · **Trạng thái:** pending · Thay Phase 05 của plan gốc.

- Tải Blender 4.2 LTS portable vào `tools/blender/` khi bấm tính năng lần đầu (có thanh tiến độ, kiểm SHA256).
- Mỗi nút = 1 script `bpy` trong whitelist, chạy qua JobRunner (backend) như worker AI:
  Bo tròn cạnh (bevel), Làm lưới đều (voxel remesh), Sửa lỗi để in 3D (merge, fill holes, manifold), Tạo UV,
  Render đẹp (Cycles, 128 samples, GPU nếu có), Gắn xương tự động (Blender auto weights).
- Giao tiếp: UI xuất GLB vật đang chọn → backend → Blender → GLB → thay geometry (Undo được).
- Files: `blender_ops/run_op.py`, `blender_ops/op_*.py`, `backend/blender_environment.py`, `webui/js/blender-tools-panel.js`.
