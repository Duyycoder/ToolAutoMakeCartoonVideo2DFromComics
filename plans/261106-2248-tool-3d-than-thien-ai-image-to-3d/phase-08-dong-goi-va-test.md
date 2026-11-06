# Phase 08 — Đóng gói + test

**Ưu tiên:** P1 · **Trạng thái:** pending · **Effort:** 2–3 ngày

## Requirements
- Test:
  - pytest backend: job queue, runner, path validation, assistant planner (Ollama mock ở unit test; bộ eval thật chạy riêng).
  - Test tích hợp GPU (đánh dấu `@pytest.mark.gpu`, không chạy trên CI): ảnh mẫu → GLB, kiểm số tam giác > 0, peak VRAM ≤ 5.2 GB.
  - Test Blender ops trên file mẫu (`@pytest.mark.blender`).
  - Smoke test UI thủ công theo checklist.
- CI GitHub Actions: lint + pytest không GPU (giống `ci.yml` AutoCartoon).
- Installer Inno Setup (tái dùng `installer/AutoCartoon.iss` làm mẫu): cài app + gọi `setup.bat` lần đầu; weights/Blender tải khi cài hoặc khi dùng lần đầu.
- `CAP-NHAT.bat` cập nhật qua git pull.
- Docs: `README.md`, `HUONG-DAN-KHOI-DONG.md` cho người không rành kỹ thuật.

## Todo
- [ ] Unit + integration tests
- [ ] CI
- [ ] Installer
- [ ] Docs người dùng

## Success criteria
- Cài trên máy Windows sạch có RTX 6 GB → dùng được full MVP; CI xanh.
