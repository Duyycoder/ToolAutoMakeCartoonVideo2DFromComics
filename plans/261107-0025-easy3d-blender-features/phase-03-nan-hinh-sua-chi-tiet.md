# Đợt 3 — Nặn hình + sửa chi tiết trong khối

**Ưu tiên:** P1 · **Trạng thái:** DONE

- Nút **✋ Nặn** → vào chế độ nặn cho vật đang chọn (thanh công cụ nổi, nút "Xong" để thoát).
- Cọ: Đắp (phồng theo pháp tuyến), Lõm, Kéo (grab), Làm mượt, Làm phẳng; Kích thước cọ, Độ mạnh; Đối xứng trái/phải.
- Cọ **Tô chọn**: tô vùng bề mặt → "Tách vùng đã tô thành vật riêng", "Xoá vùng", "Đổi màu vùng".
- Kỹ thuật: mergeVertices → indexed geometry; `three-mesh-bvh` raycast; mỗi nét cọ = 1 Undo (snapshot position attribute);
  khối có sẵn ít đỉnh → tự chia nhỏ (subdivide) khi vào chế độ nặn.
- Files: `sculpt-brush-engine.js`, `sculpt-mode-controller.js`, `face-paint-selection.js`.

## Đã làm: Chỉnh điểm (Edit Mode bản dễ dùng)
- Vào: nút ✏ "Chỉnh điểm" / phím Tab. Thoát: "Xong" / Tab / Esc → cả lượt = 1 bước Undo của app; trong chế độ Undo riêng từng bước.
- Chọn: Điểm (1) / Mặt (2); Bấm chọn (Shift thêm/bỏ) hoặc Kéo khung (mặc định bỏ mặt sau, tuỳ chọn "Xuyên qua"); Chọn hết (A), Chọn rộng thêm.
- Biến đổi: gizmo W/E/R tại tâm vùng chọn; "Kéo mềm" (proportional editing, smoothstep).
- Thao tác: Đùn ra (giữ lưới kín), Làm mượt vùng, Dồn vào giữa, Tô màu (vertex color), Tách ra vật mới, Xoá, Thêm điểm (chia nhỏ).
- Thoát: `toCreasedNormals` 30° → cạnh sắc giữ sắc, mặt cong giữ mượt.
- Files: `edit-mode-controller.js`, `edit-mode-operations.js`, `edit-mode-geometry.js`, `edit-mode-selection.js`,
  `edit-mode-transform.js`, `edit-mode-overlays.js`, `edit-mode-input.js`, `edit-mode-toolbar.js`.
- Giới hạn: tối đa 100k điểm; vật nhiều mesh con phải Gộp/Tách trước; UV mất sau khi chỉnh (vân dùng chiếu hộp).

## Đã làm: Nặn hình
- Phím N / nút 🗿. Cọ: Đắp, Lõm (Shift đảo chiều), Kéo (theo mặt phẳng song song màn hình), Làm mượt, Làm phẳng (phím 1-5);
  cỡ cọ ([ ]), độ mạnh, đối xứng trái↔phải (phím X, mặt phẳng = giữa khung bao vật). Vật khác mờ đi khi nặn.
- Dùng chung với Tô vẽ: `surface-session.js` (vào/thoát, chia nhỏ lưới, BVH, Undo theo nét) + `surface-input.js` (chuột/phím).
- Files: `sculpt-brush-engine.js`, `sculpt-mode-controller.js`, `sculpt-mode-toolbar.js`, `scene-ghosting.js`.
- Chưa có: nặn động (thêm điểm tự động chỗ đang nặn) — hiện chia nhỏ lưới 1 lần khi vào chế độ (≥ 40k điểm).
