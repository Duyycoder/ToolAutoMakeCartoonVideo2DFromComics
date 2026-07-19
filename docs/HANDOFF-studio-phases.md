# HANDOFF — Studio Compositing

Tài liệu cũ mô tả các phase P1–P4 như việc chưa làm. Tính đến 2026-07-18, phần
code của các phase đó đã hoàn tất; tài liệu này chỉ còn là checklist vận hành và
phát hành.

## Trạng thái hiện tại

- Nhánh ở cả hai tầng: `feat/studio-compositing`.
- Studio vẫn opt-in; classic là mặc định.
- LLM layout + heuristic fallback, story-level background cache, multi-character
  z-order, chroma/despill, adaptive GrabCut, harmonize, shadow và classic fallback
  đều đã có test.
- Local gate gần nhất: MediaComposer 84 test, repo tổng 32 test, lint/compile sạch.
- GPU thật đã xuất một frame Studio đạt smoke gate và tái dùng background cache.
- Chưa chạy trọn batch 82 cảnh/video trong phiên này.

Chi tiết kiến trúc, config và bằng chứng nằm ở
[`PLAN-studio-compositing.md`](PLAN-studio-compositing.md).

## Gate vận hành còn lại

1. Bật `render_mode = "studio"` và `studio_layout_source = "llm"` trong config cục
   bộ; không commit file này.
2. Chọn batch đại diện có cảnh nền-only, 1 người, 2–3 người, tương tác vật lý và
   hai cảnh cùng location/time.
3. Đọc log để xác nhận các nhánh: cache hit, LLM/heuristic layout, adaptive matte,
   classic fallback và lỗi kép không bị che.
4. Xem frame ở 100%: tóc/viền, ám màu, crop close/medium, chân/bóng, z-order.
5. Chạy Pass B, kiểm video/audio/subtitle và state `STORYBOARD_READY` -> `DONE`.
6. Chạy một batch classic đại diện trước merge để có bằng chứng regression thực.

## Lệnh kiểm định

```powershell
cd AIVoice/apps/MediaComposer
../../.venv/Scripts/python.exe -m pytest tests -q
../../.venv/Scripts/python.exe -m ruff check app/config.py app/services/storytelling/llm_prompter.py app/services/storytelling/models.py app/services/storytelling/orchestrator.py app/services/storytelling/studio tests/test_studio_*.py tests/test_scene_state_metadata.py
../../.venv/Scripts/python.exe -m compileall -q app tests

cd ../../..
AIVoice/.venv/Scripts/python.exe -m pytest -q
AIVoice/.venv/Scripts/python.exe -m ruff check orchestrator tests
```

## Quy tắc git/submodule

1. Publish commit `toolCaoTruyen` mà repo tổng đang trỏ tới.
2. Commit và push AIVoice (code + workflow) trên `feat/studio-compositing`.
3. Ở repo tổng, stage gitlink AIVoice mới cùng CI/release/docs; không stage
   `.claude/settings.local.json`.
4. Push repo tổng sau khi hai commit con đã reachable.
5. Chờ Actions xanh; chưa tạo tag release nếu bất kỳ child CI nào chưa xanh.

Commit chứa workflow cần credential có quyền Workflows write. Không đưa PAT vào
command/URL qua `ghfast`; ưu tiên SSH hoặc GitHub trực tiếp.

## Khi gate GPU phát hiện lỗi

- Matte 5–95% hỏng: xem raw character, thử màu chroma khác; adaptive GrabCut và
  classic fallback phải giữ pipeline an toàn.
- Layout thiếu/trùng character: sửa output/schema LLM, không nới parser để nhân vật
  biến mất âm thầm.
- Cache sai ngày/đêm: kiểm `_semantic_meta.location` + `time_of_day` trong state.
- Hai renderer cùng lỗi: giữ exception; không khôi phục placeholder xám.
