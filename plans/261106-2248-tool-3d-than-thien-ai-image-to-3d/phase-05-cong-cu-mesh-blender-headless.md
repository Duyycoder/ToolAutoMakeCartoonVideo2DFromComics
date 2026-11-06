# Phase 05 — Công cụ mesh qua Blender headless

**Ưu tiên:** P1 · **Trạng thái:** pending · **Effort:** 3–4 ngày · Chạy song song Phase 06

## Key insight
Người dùng **không bao giờ thấy Blender**. Mỗi nút trên UI = 1 script `bpy` chạy `blender --background --factory-startup --python blender_ops/run_op.py -- --op <name> --in a.glb --out b.glb --params '{...}'`. Blender là "động cơ xử lý mesh".

## Bộ thao tác (tên thân thiện → thao tác Blender)
| Nút trên UI | Blender |
|-------------|---------|
| Làm mượt bề mặt | Smooth modifier / Corrective smooth + shade smooth |
| Giảm chi tiết (thanh trượt % hoặc số tam giác) | Decimate (collapse) |
| Làm lưới đều lại | Voxel remesh (+ giữ màu bằng Data Transfer) |
| Sửa lỗi để in 3D | merge by distance, fill holes, make manifold, recalc normals |
| Đối xứng trái/phải | Mirror + bisect |
| Tạo UV tự động | Smart UV project |
| Bake màu đỉnh → texture | Cycles bake (CPU/GPU) |
| Khoét rỗng (in 3D) | Solidify ngược + boolean |
| Ghép / cắt 2 vật | Boolean union/difference |
| Xuất FBX / GLB / STL (mm) / OBJ | exporters chuẩn |

## Requirements
- Mỗi op: preview trước/sau trong viewport, có Undo (giữ file cũ trong `assets/history/`).
- Cache tiến trình: op ngắn mất ~2–3 s do khởi động Blender — chấp nhận ở MVP; nếu chậm, Phase sau chạy 1 Blender server giữ sống nhận lệnh qua socket.
- Ops nhẹ (đặt sàn, scale, căn giữa, thống kê tam giác) dùng trimesh trong backend, không cần Blender.

## Files
```
blender_ops/run_op.py           // dispatch theo --op, in JSON progress
blender_ops/op_smooth_decimate_remesh.py
blender_ops/op_print_repair.py
blender_ops/op_uv_bake.py
blender_ops/op_boolean_mirror.py
blender_ops/op_export_formats.py
webui/js/mesh-tools-panel.js
```

## Todo
- [ ] run_op dispatcher + whitelist op
- [ ] Từng nhóm op + test bằng file mẫu
- [ ] Panel UI + preview trước/sau
- [ ] Undo qua history

## Success criteria
- Mỗi op < 10 s với mesh 100k tam giác; STL xuất ra mở được trong slicer (Cura/Prusa) không lỗi manifold.

## Security
- Chỉ chạy op có trong whitelist; params validate bằng pydantic; không bao giờ chạy code Python do client/LLM gửi.
