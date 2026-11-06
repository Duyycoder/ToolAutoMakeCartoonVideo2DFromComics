# Đợt 5 — Ghép xương (rigging dễ dùng)

**Ưu tiên:** P2 · **Trạng thái:** pending

- Nút **🦴 Ghép xương** cho vật đang chọn → chọn mẫu: Người (đầu, thân, 2 tay, 2 chân), Chuỗi (đuôi, dây, rắn), Tự đặt.
- Mẫu tự co giãn theo khung bao của model; người dùng kéo các khớp tròn cho khớp hình.
- "Gắn vào hình": tự tính trọng lượng theo khoảng cách tới đoạn xương (4 xương gần nhất) → SkinnedMesh.
- Chế độ "Tạo dáng": bấm khớp + xoay bằng gizmo; dùng với Đợt 4 để ghi tư thế theo thời gian.
- Xuất GLB có skin + animation (dùng được trong Unity/Godot).
- Files: `skeleton-templates.js`, `auto-skin-weights.js`, `rigging-mode-controller.js`.
- Rủi ro: trọng lượng theo khoảng cách cho kết quả thô ở nách/háng → có thanh "Độ mềm khớp"; Đợt 6 có thể dùng Blender auto-weights.
