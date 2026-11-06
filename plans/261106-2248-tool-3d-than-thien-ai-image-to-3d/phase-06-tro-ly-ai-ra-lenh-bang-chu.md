# Phase 06 — Trợ lý AI ra lệnh bằng chữ (Ollama)

**Ưu tiên:** P1 · **Trạng thái:** pending · **Effort:** 3 ngày

## Overview
Ô chat: "làm mượt con mèo rồi giảm còn 5 nghìn tam giác, tô màu cam" → LLM trả **danh sách lệnh JSON** → UI hiện kế hoạch dạng thẻ → user bấm "Làm" → thực thi tuần tự (có Undo).

## Key insights
- Dùng **structured output** của Ollama (`format: <JSON schema>`) hoặc tool calling → không parse văn bản tự do.
- LLM chỉ được chọn từ **whitelist** (ops Phase 05 + thao tác viewport: thêm khối, đổi màu, di chuyển/xoay/scale, ẩn, xoá, xuất file, chạy ảnh→3D). Không sinh code bpy.
- Model: `qwen2.5:3b` (~2.5 GB, nhanh) mặc định, `qwen2.5:7b-q4` nếu cần hiểu câu khó. Unload trước job TripoSR (Phase 03).
- Ngữ cảnh gửi LLM: danh sách vật thể (tên, id, số tam giác, màu) — không gửi mesh.
- Tái dùng kinh nghiệm chatbot AutoCartoon (`orchestrator/chatbot.py`, `chat_reasoning.py`).

## Schema lệnh (rút gọn)
```json
{"steps":[
  {"op":"smooth","target":"obj_3","params":{"strength":0.5}},
  {"op":"decimate","target":"obj_3","params":{"target_tris":5000}},
  {"op":"set_color","target":"obj_3","params":{"hex":"#FF8C00"}}
],
 "reply":"Mình sẽ làm mượt, giảm chi tiết và tô màu cam cho 'Con mèo'."}
```

## Files
```
backend/assistant_command_planner.py   // prompt + schema + gọi Ollama
backend/assistant_op_registry.py       // whitelist op, mô tả cho prompt, validate params
webui/js/assistant-chat-panel.js
tests/test_assistant_planner.py        // bộ ~30 câu lệnh tiếng Việt → kỳ vọng steps
```

## Todo
- [ ] Op registry (nguồn duy nhất cho cả UI, Blender và LLM — DRY)
- [ ] Planner + schema + retry khi JSON sai
- [ ] UI thẻ kế hoạch + xác nhận
- [ ] Bộ eval 30 câu, đo tỉ lệ đúng

## Success criteria
- ≥ 85% câu trong bộ eval ra đúng op/target; phản hồi ≤ 4 s với 3B.
- Câu ngoài khả năng ("làm cho nó biết đi") → trả lời lịch sự là chưa hỗ trợ, không bịa op.

## Security
- Validate từng step bằng pydantic trước khi chạy; luôn cần user xác nhận với op phá huỷ (xoá, boolean).
