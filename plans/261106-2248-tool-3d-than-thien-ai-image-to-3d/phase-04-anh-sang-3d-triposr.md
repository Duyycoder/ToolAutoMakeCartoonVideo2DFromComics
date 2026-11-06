# Phase 04 — Ảnh → 3D (rembg + TripoSR)

**Ưu tiên:** P0 · **Trạng thái:** pending · **Effort:** 3–4 ngày · Cần Phase 01 + 03

## Flow
```
Ảnh (kéo thả / dán clipboard)
 → rembg tách nền (onnxruntime-gpu, model u2net/isnet) → preview cho user xác nhận/cắt lại
 → căn giữa + pad vuông + resize (foreground_ratio 0.85)
 → TripoSR → marching cubes → mesh màu đỉnh
 → (tuỳ chọn) bake texture (xatlas UV + moderngl) → GLB
 → hậu xử lý nhẹ bằng trimesh: xoá mảnh vụn, đặt đáy chạm sàn, scale ~1 m
 → nạp vào viewport
```

## Requirements
- 3 mức chất lượng thay vì tham số kỹ thuật:
  | Mức | mc_resolution | chunk_size | Ghi chú |
  |-----|---------------|-----------|---------|
  | Nhanh | 128 | 4096 | preview |
  | Cân bằng (mặc định) | 192–256 | theo spike Phase 01 | |
  | Chi tiết | 256–320 | 2048 | chậm hơn, dễ OOM → auto hạ cấp |
- Thứ tự giải phóng VRAM: rembg chạy xong mới load TripoSR (hoặc rembg chạy CPU — chỉ ~1–2 s).
- Gợi ý ảnh đầu vào tốt hiển thị trên UI: 1 vật thể, chụp chéo 3/4, nền đơn giản, đủ sáng.
- Batch: kéo nhiều ảnh → hàng đợi, mỗi ảnh 1 job.

## Files
```
workers/worker_image_to_3d.py      // entry, parse args, in JSON progress
workers/background_removal.py      // rembg wrapper
workers/triposr_inference.py       // load model, run, extract mesh (fallback mcubes)
workers/mesh_postprocess.py        // trimesh cleanup, ground, scale, export GLB
webui/js/image-to-3d-wizard.js     // UI 3 bước: chọn ảnh → xác nhận tách nền → kết quả
```

## Todo
- [ ] Wrapper rembg + sửa onnxruntime-gpu (tái dùng `sua_onnxruntime_gpu.py`)
- [ ] Inference TripoSR + 3 preset
- [ ] Bake texture
- [ ] Postprocess + GLB
- [ ] Wizard UI + batch
- [ ] Test với bộ 10 ảnh mẫu (đồ vật, nhân vật chibi, thú, đồ chơi)

## Success criteria
- Mức Cân bằng: ≤ 30 s/ảnh, không OOM trên 6 GB với bộ 10 ảnh mẫu.
- OOM ở mức Chi tiết → tự hạ xuống Cân bằng và báo user.

## Risks
- TripoSR yếu với người thật/vật mỏng (lá, tóc) và mặt sau vật thể → nói rõ trên UI; Phase 09 cân nhắc model mạnh hơn.
- Texture bake cần OpenGL context (moderngl) — nếu lỗi trên laptop thì dùng màu đỉnh.
