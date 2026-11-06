# Phase 01 — Setup môi trường + spike TripoSR trên 6 GB

**Ưu tiên:** P0 · **Trạng thái:** in-progress · **Effort:** 1–2 ngày

## Context
- Tham khảo: `setup.bat`, `scripts/sua_onnxruntime_gpu.py`, `orchestrator/desktop.py`, `orchestrator/process_manager.py` của repo AutoCartoon.
- TripoSR: https://github.com/VAST-AI-Research/TripoSR (README: mặc định ~6 GB VRAM với 1 ảnh).

## Key insights
- Spike **trước** mọi việc khác: nếu TripoSR không chạy ổn trên 6 GB thì cả kiến trúc AI phải đổi.
- Tách 2 venv: `.venv` (backend nhẹ: fastapi, pywebview, trimesh) và `.venv-ai` (torch cu121, TripoSR, rembg). Backend không bao giờ import torch → khởi động nhanh, không giữ VRAM.

## Requirements
- `setup.bat`: tìm/cài Python 3.11, tạo 2 venv, cài torch cu121, clone TripoSR vào `third_party/`, tải Blender 4.2 LTS portable zip vào `tools/blender/`, kiểm tra Ollama, tải weights `stabilityai/TripoSR` từ HF.
- Nhận GPU theo tên card NVIDIA (bê logic từ commit `6a6262a`), fallback CPU kèm cảnh báo "rất chậm".
- `run.bat`: mở pywebview, fallback trình duyệt.

## Implementation steps
1. Tạo repo `Easy3D`, cấu trúc: `backend/ workers/ blender_ops/ webui/ configs/ third_party/ tools/ tests/`.
2. Script spike `workers/spike_triposr.py`: chạy 1 ảnh với ma trận cấu hình `chunk_size ∈ {8192, 4096, 2048}` × `mc_resolution ∈ {256, 192, 128}`, ghi `torch.cuda.max_memory_allocated()`, thời gian, số tam giác → `plans/reports/spike-triposr-vram.md`.
3. Thử `torchmcubes`; nếu compile lỗi → dùng `PyMCubes` (CPU) hoặc `skimage.measure.marching_cubes`; ghi lại cách nào chạy được.
4. Thử `--bake-texture` (xatlas + moderngl) trên laptop.
5. Chốt cấu hình mặc định vào `configs/config.example.json` (`triposr.chunk_size`, `mc_resolution`, `device`).

## Todo
- [x] Skeleton repo + `.gitignore` (venv, weights, tools, project output)
- [x] `setup.bat` / `run.bat` (Blender để Phase 05)
- [ ] Spike VRAM + report
- [ ] Chốt fallback marching cubes
- [ ] Config mặc định

## Success criteria
- 1 ảnh → `.obj`/`.glb` trên RTX 3060 6 GB, peak VRAM ≤ 5.2 GB (chừa cho Windows/WebView), ≤ 30 s.
- `setup.bat` chạy trên máy sạch không cần thao tác tay (trừ cài Ollama).

## Risks
- OOM → giảm `chunk_size` (đánh đổi tốc độ), giảm `mc_resolution` (đánh đổi chi tiết).
- Laptop dùng iGPU cho màn hình: WebView2 vẫn chạy iGPU, không tranh VRAM — tốt.
- Blender zip ~350 MB: cho phép bỏ qua lúc setup, tải khi dùng tính năng Phase 05 lần đầu.

## Security
- Tải Blender/weights chỉ từ URL chính thức, kiểm SHA256.
