# Phase 02 — Viewport 3D cơ bản (Three.js)

**Ưu tiên:** P0 · **Trạng thái:** pending · **Effort:** 4–6 ngày · Chạy song song Phase 03

## Overview
Editor tối thiểu nhưng đủ dùng, **không có "mode"** như Blender (không Edit/Object/Sculpt mode) — người mới chỉ thao tác trên vật thể nguyên khối.

## Requirements
- Viewport: lưới sàn, ánh sáng mặc định đẹp (HDRI nhẹ), OrbitControls (chuột trái xoay, phải kéo, cuộn zoom — ghi chú ngay trên màn hình).
- Thêm khối có sẵn: hộp, cầu, trụ, nón, mặt phẳng, chữ 3D.
- Gizmo TransformControls: 3 nút lớn Di chuyển / Xoay / Phóng to (+ phím W/E/R), snap lưới bật mặc định.
- Outliner đơn giản: danh sách vật thể, ẩn/hiện, khoá, đổi tên, xoá, nhân bản.
- Vật liệu: bảng màu + preset (Nhựa, Kim loại, Gỗ, Kính, Hoạt hình/toon) — map sang `MeshStandardMaterial`/`MeshToonMaterial`.
- Undo/Redo (Ctrl+Z/Y) bằng command pattern.
- Import: GLB/GLTF/OBJ/STL/FBX (loaders của Three.js). Export nhanh GLB/OBJ/STL bằng exporter Three.js (FBX để Phase 05 qua Blender).
- Lưu/mở project: `project.json` + `assets/`.
- Chụp ảnh viewport (PNG) + xoay 360° xuất GIF/MP4 (ffmpeg phía backend).

## Architecture (webui/, mỗi file < 200 dòng)
```
webui/
  index.html
  js/viewport-scene-setup.js      // renderer, camera, light, grid
  js/transform-gizmo-controls.js
  js/scene-outliner-panel.js
  js/material-preset-panel.js
  js/undo-redo-command-stack.js
  js/model-import-export.js
  js/project-save-load.js
  js/backend-api-client.js        // REST + SSE
  vendor/three/                   // bundle sẵn, không cần internet
```
Không dùng framework/bundler (giống webui AutoCartoon) → ES modules + importmap.

## Todo
- [ ] Scene + controls + primitives
- [ ] Gizmo + snap
- [ ] Outliner
- [ ] Material presets
- [ ] Undo/redo
- [ ] Import/export + project save/load
- [ ] Screenshot / turntable

## Success criteria
- Mở model 200k tam giác vẫn ≥ 30 fps trên laptop.
- Người mới làm được "thêm hộp → đổi màu → xoay → xuất GLB" không cần đọc hướng dẫn.

## Risks
- FBX loader của Three.js không ổn với mọi file → báo lỗi thân thiện, đề nghị chuyển qua Blender.
