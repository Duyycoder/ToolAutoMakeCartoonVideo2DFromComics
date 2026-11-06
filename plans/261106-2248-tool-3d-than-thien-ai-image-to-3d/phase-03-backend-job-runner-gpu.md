# Phase 03 — Backend job runner + quản lý GPU

**Ưu tiên:** P0 · **Trạng thái:** pending · **Effort:** 2–3 ngày

## Context
- Bê pattern từ AutoCartoon `orchestrator/process_manager.py`, `ollama_manager.py`, `model_preflight.py`: subprocess + JSON progress stdout + tự nhả VRAM khi tiến trình kết thúc.

## Requirements
- FastAPI `:8200`, chỉ bind `127.0.0.1`.
- `POST /jobs` (type: `image_to_3d` | `mesh_op` | `export` | ...), `GET /jobs/{id}`, `GET /jobs/{id}/events` (SSE), `POST /jobs/{id}/cancel`.
- Hàng đợi: job GPU chạy tuần tự (`gpu_lock`), job CPU (Blender) chạy song song tối đa 1–2.
- Trước job GPU: gọi Ollama `keep_alive: 0` để unload model; preflight kiểm VRAM trống qua `nvidia-smi`.
- Worker crash native (exit code ≠ 0, không có JSON `done`) → tự retry 1 lần với cấu hình nhẹ hơn (học từ fix step3 commit `6234574`).
- Log `logs/app.log`, mỗi job có log riêng.

## Files
```
backend/main.py                   // FastAPI app, routes
backend/job_queue.py              // hàng đợi job, ưu tiên, huỷ
backend/gpu_manager.py            // lock, preflight VRAM, unload Ollama
backend/worker_process_runner.py  // spawn subprocess, parse JSON progress
backend/project_storage.py        // đường dẫn project/assets, chống path traversal
backend/config.py
```
Giao thức stdout worker (giống AutoCartoon):
```json
{"type":"progress","pct":42,"msg":"Đang tạo lưới 3D..."}
{"type":"done","output":"assets/abc.glb","stats":{"tris":48211}}
{"type":"error","code":"CUDA_OOM","msg":"..."}
```

## Todo
- [ ] Routes + SSE
- [ ] Job queue + gpu_lock
- [ ] Runner + retry
- [ ] Ollama unload + VRAM preflight
- [ ] pytest cho queue/runner (worker giả lập bằng script Python nhỏ in JSON)

## Success criteria
- Huỷ job giết sạch cây tiến trình con; sau job GPU `nvidia-smi` về mức ban đầu.
- Lỗi `CUDA_OOM` hiện thông báo tiếng Việt kèm gợi ý ("Thử chế độ Nhẹ").

## Security
- Chỉ localhost; validate mọi path nằm trong project dir; không nhận lệnh shell từ client.
