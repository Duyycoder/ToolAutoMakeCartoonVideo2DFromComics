---
name: tool-3d-than-thien-ai-image-to-3d
status: in-progress
created: 2026-11-06
mode: auto
blockedBy: []
blocks: []
---

# Easy3D — Tool 3D thân thiện người mới + AI local (image → 3D)

**Mục tiêu:** App desktop Windows cho người chưa biết gì về 3D: kéo thả ảnh → ra model 3D, chỉnh bằng nút bấm dễ hiểu hoặc gõ lệnh tiếng Việt, xuất GLB/OBJ/STL/FBX. Mọi AI chạy local trên **RTX 3060 Laptop 6 GB VRAM**.

## Giả định đã chốt (user chưa phản hồi → dùng mặc định khuyến nghị)
- **Repo mới riêng** (`Easy3D`), chỉ tái sử dụng *pattern* từ AutoCartoon, không import code chéo.
- **Kiến trúc:** pywebview + Three.js (UI/viewport) ⟷ FastAPI backend ⟷ worker subprocess (TripoSR / Blender headless / Ollama).
- **MVP AI:** ảnh → 3D (rembg + TripoSR) + trợ lý ra lệnh bằng chữ (Ollama → danh sách thao tác whitelist).
- **Để sau:** text → ảnh → 3D, AI texture, model 3D chất lượng cao hơn (SF3D/Hunyuan3D-mini).

## Kiến trúc
```
pywebview window (WebView2)
  └─ webui/ (HTML/JS thuần + Three.js: viewport, gizmo, undo, outliner)
        │ REST + SSE tiến độ
  FastAPI :8200 (backend/, KHÔNG import torch)
        ├─ job_queue + gpu_lock (1 job GPU tại 1 thời điểm)
        ├─ worker_image_to_3d.py   (subprocess, venv-ai: torch cu121, TripoSR, rembg)
        ├─ blender --background --python ops/*.py  (mesh ops, export)
        └─ Ollama HTTP :11434 (keep_alive=0 trước job GPU khác)
  Project = folder: project.json (scene graph) + assets/*.glb
```
Pattern tái dùng từ AutoCartoon: subprocess-per-heavy-step tự nhả VRAM, giao thức JSON progress trên stdout, `setup.bat` tự nhận GPU theo tên card NVIDIA, sửa `onnxruntime-gpu` bị ghi đè (cho rembg), `ollama_manager`, pywebview fallback ra trình duyệt.

## Phases
| # | Phase | Ưu tiên | Trạng thái |
|---|-------|---------|-----------|
| 01 | [Setup môi trường + spike TripoSR 6 GB](phase-01-setup-moi-truong-va-spike-triposr.md) | P0 | in-progress (khung xong, chờ chạy spike trên RTX 3060) |
| 02 | [Viewport 3D cơ bản (Three.js)](phase-02-viewport-3d-co-ban.md) | P0 | pending |
| 03 | [Backend job runner + quản lý GPU](phase-03-backend-job-runner-gpu.md) | P0 | pending |
| 04 | [Ảnh → 3D (rembg + TripoSR)](phase-04-anh-sang-3d-triposr.md) | P0 | pending |
| 05 | [Công cụ mesh qua Blender headless](phase-05-cong-cu-mesh-blender-headless.md) | P1 | pending |
| 06 | [Trợ lý AI ra lệnh bằng chữ (Ollama)](phase-06-tro-ly-ai-ra-lenh-bang-chu.md) | P1 | pending |
| 07 | [UX cho người mới](phase-07-ux-cho-nguoi-moi.md) | P1 | pending |
| 08 | [Đóng gói + test](phase-08-dong-goi-va-test.md) | P1 | pending |
| 09 | [Mở rộng AI (sau MVP)](phase-09-mo-rong-ai-sau-mvp.md) | P2 | pending |

Thứ tự: 01 → (02 ∥ 03) → 04 → (05 ∥ 06) → 07 → 08 → 09.

## Phụ thuộc chính
- Python 3.11, PyTorch CUDA 12.1, TripoSR (MIT), rembg (onnxruntime-gpu), Blender 4.2 LTS portable, Ollama (qwen2.5:3b/7b-q4), Three.js r16x, pywebview.

## Rủi ro lớn nhất
1. TripoSR mặc định ~6 GB VRAM → phải hạ `chunk_size`/`mc_resolution` (spike Phase 01 quyết định cấu hình).
2. `torchmcubes` cần compile CUDA trên Windows → fallback PyMCubes/skimage.
3. Ollama + TripoSR không cùng nằm trong 6 GB → bắt buộc unload Ollama trước job GPU.

## Câu hỏi chưa chốt
- Có tích hợp ngược vào AutoCartoon (dùng model 3D làm nhân vật/bối cảnh) không?
- Mục đích chính của model đầu ra: asset game / in 3D / xem? → ảnh hưởng preset mặc định.
- Có dùng model license không thương mại (SF3D, Hunyuan3D) ở Phase 09 không?
