# Phase 09 — Mở rộng AI (sau MVP)

**Ưu tiên:** P2 · **Trạng thái:** pending · Chỉ làm sau khi MVP ổn định. Mỗi mục là 1 plan con riêng.

| Tính năng | Cách làm trên 6 GB | Lưu ý |
|-----------|-------------------|-------|
| Text → ảnh → 3D | SDXL-Turbo / SD1.5 fp16 (≈ 3–4 GB) sinh ảnh vật thể nền trắng → unload → TripoSR | Chạy tuần tự, prompt template "single object, white background, 3/4 view" |
| Model 3D chất lượng hơn | Stable Fast 3D (SF3D, có UV + texture, ~6 GB) hoặc Hunyuan3D-2mini (shape, fp16 + offload) | Kiểm **license** (SF3D: Stability Community License; Hunyuan: Tencent license, giới hạn khu vực) trước khi đưa vào |
| Nhiều ảnh → 3D tốt hơn | Cho upload 2–4 góc chụp; chọn model hỗ trợ multi-view | Cần spike VRAM riêng |
| AI texture / tô lại màu | Chiếu ảnh SD (ControlNet depth) lên mesh từ vài góc rồi bake | Khó nhất; rất sát giới hạn VRAM |
| Tự gắn xương + animation đơn giản | Mixamo-like: auto-rig humanoid qua Blender (Rigify) | Chỉ cho nhân vật hình người |
| Kết nối AutoCartoon | Xuất nhân vật/bối cảnh 3D → render frame làm cảnh cho video 2D | Nếu user muốn tích hợp |

## Nguyên tắc
- Mọi model mới đi qua cùng `gpu_manager` + worker subprocess (Phase 03) → không đổi kiến trúc.
- Mỗi model mới phải có spike VRAM report trước khi code UI.
