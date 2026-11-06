# Ghép xương v2 — tự khớp hình, chỉnh dễ, cây xương, tên Unity, xuất cho game

**Trạng thái:** DONE · **Repo:** Easy3D · **Model test:** `C:\Users\Hello\Downloads\test.fbx` (golem Tripo, quay mặt ±X, tay buông thấp)

## Vấn đề (đã tái hiện)
1. Mẫu xương dựng theo trục local + giả định mặt trước +Z -> model quay mặt ±X bị xương vuông góc 90°.
2. Mẫu theo tỉ lệ khung bao cố định, z = 0 -> không khớp nhân vật tay buông / to ngang.
3. Chỉ dời 1 khớp bằng mũi tên trục; không kéo thẳng, không dời cả nhánh, không xoay cả bộ xương, không Undo ở bước đặt khớp.
4. Tên xương tiếng Việt -> Unity Humanoid không tự map. Không có cây xương / đổi tên / thêm-xoá khớp / lưu mẫu / thư mục xuất cho game.

## Phases
| # | Việc | Trạng thái |
|---|------|-----------|
| 1 | Khung thân (up = world Y, ngang = trục ngang dài hơn, trước = mũi chân/camera) + tự khớp theo lát cắt (`rig-body-frame.js`, `skeleton-auto-fit.js`) | DONE |
| 2 | Tên Unity Humanoid + nhãn VN (`skeleton-templates.js`), đổi tên rig cũ | DONE |
| 3 | Kéo thẳng chấm khớp + tự vào giữa bề dày (raycast trước/sau), kéo cả nhánh, Undo bước 1 (`rig-joint-drag.js`) | DONE |
| 4 | Biến đổi cả bộ xương: xoay 90°, quay 180°, gizmo dời/xoay/co giãn (`rig-place-editing.js` setWhole) | DONE |
| 5 | Panel cây xương: chọn, đổi tên, thêm/xoá khớp, toạ độ số, tên nhân vật; "Sửa khớp" sau khi gắn (`rig-bone-tree-panel.js`) | DONE |
| 6 | Lưu/nạp mẫu xương (backend `library/rigs/*.json`) + Xuất nhân vật vào `output/game/<Tên>/<Tên>.glb` | DONE |
| 7 | Smoke test + pytest | DONE |

## Sau đó (user yêu cầu, làm tiếp)
| Việc | Trạng thái |
|------|-----------|
| Mở file `.blend` (Blender ẩn -> GLB, `--disable-autoexec`, kiểm tra header plain/zstd/gzip) | DONE |
| Camera khi xuất ảnh: góc nhanh, xoay/độ cao/khoảng cách/ống kính, vừa khung, xem trước đúng khung, Huỷ trả camera | DONE |
| Ánh sáng: FBX/OBJ Phong -> PBR, panel chỉnh (nắng, nền, phản chiếu, phơi sáng, màu, bóng đổ, Undo, lưu project), nắng + vùng bóng ôm cảnh, đèn mới đặt theo cỡ cảnh, Cycles theo màu trời + phơi sáng | DONE |

## Kết quả
- Golem `test.fbx`: nhận đúng mặt trước +X, 2 chân + tay buông, tự khớp ~115 ms (60k điểm mẫu).
- Quy ước trái/phải đổi theo glTF/Unity (nhìn +Z thì trái = +X) — bản cũ bị ngược.
- File mới: `rig-body-frame.js`, `skeleton-auto-fit.js`, `rig-place-editing.js`, `rig-joint-drag.js`, `rig-joint-structure.js`,
  `rig-pose-stage.js`, `rig-bone-naming.js`, `rig-bone-tree-panel.js`, `rig-template-library.js`.
- Backend: thư mục `library/rigs` (.json, list/read) + `output/game/<Tên>/` (.glb). `/library/` không đưa lên git.
- Test: smoke UI 126/126, pytest 34 passed.

## Câu hỏi mở
- Unity đọc GLB cần package glTFast/UnityGLTF; muốn FBX gốc cho Unity Humanoid thì có thể xuất qua Blender ẩn (làm cùng đợt mở .blend).
