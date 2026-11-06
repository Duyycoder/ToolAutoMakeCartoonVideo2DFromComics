# Đợt 3 — Nặn hình + sửa chi tiết trong khối

**Ưu tiên:** P1 · **Trạng thái:** pending

- Nút **✋ Nặn** → vào chế độ nặn cho vật đang chọn (thanh công cụ nổi, nút "Xong" để thoát).
- Cọ: Đắp (phồng theo pháp tuyến), Lõm, Kéo (grab), Làm mượt, Làm phẳng; Kích thước cọ, Độ mạnh; Đối xứng trái/phải.
- Cọ **Tô chọn**: tô vùng bề mặt → "Tách vùng đã tô thành vật riêng", "Xoá vùng", "Đổi màu vùng".
- Kỹ thuật: mergeVertices → indexed geometry; `three-mesh-bvh` raycast; mỗi nét cọ = 1 Undo (snapshot position attribute);
  khối có sẵn ít đỉnh → tự chia nhỏ (subdivide) khi vào chế độ nặn.
- Files: `sculpt-brush-engine.js`, `sculpt-mode-controller.js`, `face-paint-selection.js`.
