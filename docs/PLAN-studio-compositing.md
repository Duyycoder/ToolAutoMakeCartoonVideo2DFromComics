# PLAN — Studio Compositing: render ảnh theo lớp (nền + nhân vật) rồi ghép

> **Nhánh:** `feat/studio-compositing` (2 tầng: repo tổng + submodule AIVoice), tách từ `dev/feat-media-workflows` / AIVoice `master`.
> **Mục tiêu:** nâng chất lượng ảnh bằng cách **sinh nền và nhân vật RIÊNG** rồi **ghép lớp** (compositing), thay cho lối "1 cảnh = 1 ảnh SD vẽ chung".
> **Trạng thái:** DRAFT — đã chốt 3 quyết định lớn (xem §0), chưa viết code lõi.
> **Phần lớn code nằm trong submodule `AIVoice/apps/MediaComposer/`** → theo quy trình con-trước-tổng-sau (README).
> **Nguyên tắc chạy:** mỗi task xong → `python -m py_compile <file>`; task đụng logic thuần → `pytest -q` (AIVoice + repo tổng) phải xanh trước khi cập nhật con trỏ submodule.
> **Ràng buộc đã biết:** PAT thiếu scope `workflow` → mọi thay đổi `.github/workflows/*` phải push tay (memory: `git-push-workflow-scope`).

---

## 0. Quyết định đã chốt

| # | Quyết định | Lựa chọn |
|---|-----------|----------|
| 1 | Nhánh tách từ đâu | `dev/feat-media-workflows` (kế thừa media-workflows) |
| 2 | Phạm vi vòng đầu | **Studio đầy đủ**: cache nền theo location + đa nhân vật + z-order + layout do LLM gợi ý |
| 3 | Kỹ thuật tách nền | **Nền phẳng + chroma/threshold** (ép nhân vật sinh trên nền màu đồng nhất rồi key theo ngưỡng màu) |

**Nguyên tắc bao trùm:** giữ nguyên pipeline classic; studio là **chế độ opt-in qua feature flag** `render_mode` (mặc định `classic`) → merge vào main không đổi hành vi cũ, giảm rủi ro CI/CD.

---

## 1. Bối cảnh code hiện tại (điểm mở rộng)

- Auto-pipeline 3 trạm: [`StorytellingOrchestrator`](../AIVoice/apps/MediaComposer/app/services/storytelling/orchestrator.py) — `step1` (prompt+shot_type+location), `step2_generate_images` (**mỗi cảnh → 1 ảnh** qua `generate_draft` + `detail_faces`), `step3_render_final` (upscale + ghép video).
- Engine SD: [`StorytellingPipeline.generate_draft()`](../AIVoice/apps/MediaComposer/app/services/storytelling/image_generator.py) — IP-Adapter (CLIP/FaceID) + LoRA nhân vật, singleton tự release/reload khi đổi checkpoint.
- Face Detailer nặng: [`detail_faces()`](../AIVoice/apps/MediaComposer/app/services/storytelling/face_detailer.py) — img2img từng mặt (~14s/mặt). **Chính là khâu sẽ dồn về lớp nhân vật** (sinh mặt to → bớt phụ thuộc).
- Identity/ref: [`ContextManager`](../AIVoice/apps/MediaComposer/app/services/storytelling/context_manager.py) — `get_ref_image_path`, `has_identity`, `set_ref_from_image`, `get_face_embedding_path`.
- Metadata sẵn có: `Scene.shot_type` (close/medium/wide) và `location` (từ semantic split, gắn ở `scene._semantic_meta["location"]`) → **nền tảng cho layout + cache nền**.
- Tiện ích tái dùng: `_match_color_mean_only()` (hòa màu khi dán), Studio thủ công [`ImageGenOrchestrator`](../AIVoice/apps/MediaComposer/app/services/storytelling/image_gen_service.py) (mẫu điều phối sinh ảnh theo batch).

---

## 2. Kiến trúc Studio Compositing

```
step2 (render_mode="studio")
  ├─ layout_planner   : Scene → LayerPlan (nền + danh sách CharacterLayer: anchor/scale/z)
  ├─ background_render : sinh NỀN (no-face, no-detailer) — cache theo location_id, tái dùng
  ├─ character_render  : mỗi nhân vật sinh RIÊNG trên NỀN PHẲNG (khung to, IP-Adapter/LoRA/detailer)
  ├─ matting (chroma)  : key nền phẳng → RGBA (despill + feather alpha)
  └─ compositor        : resize/anchor/paste theo z-order + hòa màu + bóng đổ nhẹ → frame cảnh
```

Ánh xạ yêu cầu người dùng: nền riêng ↔ background_render; nhân vật chất lượng cao ↔ character_render (mặt to, isolate); "1 ảnh cho nhiều cảnh" ↔ cache nền theo location; "1 cảnh nhiều nhân vật" ↔ nhiều CharacterLayer; "vẫn kiểm soát khuôn mặt" ↔ IP-Adapter/LoRA/detailer dồn vào lớp nhân vật.

---

## 3. Thay đổi data model  [SUBMODULE `models.py`]

```python
@dataclass
class CharacterLayer:
    slug: str                 # nhân vật (khớp ContextManager)
    prompt: str               # prompt riêng (toàn thân/nửa người), KHÔNG mô tả nền
    anchor_x: str = "center"  # trục ngang: left | center | right
    anchor_y: str = "bottom"  # trục dọc: bottom | middle — TÙY BỐI CẢNH (LLM/heuristic chọn)
    scale: float = 0.9        # tỉ lệ chiều cao lớp so với khung (0-1)
    z_order: int = 0          # lớn = phía trước
    flip: bool = False        # lật ngang cho đa dạng hướng nhìn

@dataclass
class LayerPlan:
    location_id: str          # khoá cache nền (chuẩn hoá từ location)
    background_prompt: str     # prompt nền, "no humans, scenery"
    characters: list           # List[CharacterLayer], rỗng = cảnh thuần nền
    render_mode: str = "studio"  # "studio" | "classic" (fallback cảnh khó)
```

- `Scene` thêm `layer_plan: Optional[LayerPlan] = None` (mất sau resume vẫn tái tạo được từ scene fields — chấp nhận như `_semantic_meta`).
- Cập nhật `scene_from_dict` giữ tương thích state cũ (bỏ qua key lạ như hiện tại).

---

## 4. Module mới  [SUBMODULE `app/services/storytelling/studio/`]

| Module | Trách nhiệm | Test GPU-free? |
|--------|-------------|----------------|
| `layout_planner.py` | Scene(shot_type, #chars, location) → `LayerPlan`. Nguồn layout: **LLM** (mở rộng schema JSON của `llm_prompter`) với **fallback heuristic** theo shot_type | ✅ (heuristic + parse JSON) |
| `background_renderer.py` | Sinh nền no-face; **cache** `bg_cache/{story_slug}/{location_id}.png`; trả path (tái dùng nếu có) | ✅ (cache-key/reuse; render monkeypatch) |
| `character_renderer.py` | Sinh nhân vật RIÊNG trên **nền phẳng** (ép màu nền qua prompt/negative), khung to; IP-Adapter/LoRA/detailer tùy cờ | — (cần SD) |
| `matting.py` | Interface `Matter`; impl `ChromaMatter`: key theo khoảng cách màu tới `matte_bg_color`, **despill** + **feather alpha** → RGBA | ✅ (ảnh synthetic) |
| `compositor.py` | resize theo `scale`, đặt theo `anchor_x`+`anchor_y` (bottom/middle tùy bối cảnh), dán theo `z_order`; hòa màu (`_match_color_mean_only`). **Bóng đổ: chưa làm (P4)** → frame | ✅ (kiểm pixel xác định) |
| `studio_pipeline.py` | Điều phối: plan → bg(cache) → chars → matte → composite → lưu `scene_{i}.png` | ✅ (renderer/matte monkeypatch) |

**Tích hợp:** `step2_generate_images` rẽ nhánh đầu hàm:
`if load_storytelling_config().get("render_mode")=="studio": StudioPipeline(...).run(scenes, task_dir, cb) else <giữ nguyên khối classic>`.
Không đụng step1/step3 (studio vẫn xuất `scene.frame_path` như classic → upscale + ghép video dùng lại nguyên).

---

## 5. Chroma-key matting — thiết kế & rủi ro

**Đây là mắt xích yếu nhất** (mọi lớp ghép dựa vào chất lượng cắt). Cách làm chắc tay:
- **Ép nền phẳng khi sinh:** thêm vào prompt nhân vật `simple background, flat <color> background, solo, full body` và **negative** loại nền phức tạp; chọn `matte_bg_color` màu ít trùng da/tóc (mặc định xanh lá `#00B140`, cho đổi sang magenta cho tóc xanh).
- **Key:** khoảng cách màu trong không gian phù hợp (chroma > threshold ⇒ giữ), **KHÔNG** chỉ threshold RGB thô.
- **Despill:** trừ ám màu nền ở viền tóc; **feather alpha** (`matte_feather_px`) để mép mềm.
- **Cổng chất lượng:** nếu alpha giữ lại <5% hoặc >95% diện tích ⇒ coi như key hỏng → **fallback classic** cho cảnh đó (không ghép ẩu).
- **Trừu tượng hoá:** `Matter` là interface ⇒ sau này thay `ChromaMatter` bằng model tốt hơn (isnet-anime/InSPyReNet) **không phải sửa compositor**.

> Rủi ro cần theo dõi khi test thật: lẹm tóc/viền, ám màu nền, nhân vật có màu trùng nền. Ghi nhận trong §8 gate P2.

---

## 6. Layout do LLM gợi ý

- Mở rộng schema JSON của [`llm_prompter`](../AIVoice/apps/MediaComposer/app/services/storytelling/llm_prompter.py): thêm `background_prompt` và `layout: [{name, anchor, scale, z}]`.
- **Fallback heuristic** khi LLM thiếu/sai (đảm bảo pipeline không chết):
  - `close` → 1 nhân vật, scale ~1.0, anchor_x center, **anchor_y middle** (mặt/nửa người ngang tầm mắt).
  - `medium` → 1–2 nhân vật, scale ~0.8, anchor_x left/right, anchor_y bottom.
  - `wide` → 0–N nhân vật, scale ~0.45, dàn ngang, anchor_y bottom (đứng trên nền).
- **Neo dọc tùy bối cảnh:** `anchor_y` = `bottom` (đứng trong cảnh) hoặc `middle` (chân dung/cận) — LLM gợi ý, heuristic trên là mặc định an toàn.
- Toán đặt lớp (anchor→toạ độ, scale→kích thước, chống tràn khung) là **hàm thuần** → test xác định (§8).

---

## 7. Config flags mới  [SUBMODULE `config.py` → `storytelling`]

```
render_mode            = "classic"   # "classic" | "studio"  (mặc định giữ hành vi cũ)
studio_bg_cache        = true        # tái dùng nền theo location
studio_layout_source   = "llm"       # "llm" | "heuristic"
studio_matte_bg_color  = "#00B140"
studio_matte_threshold = 0.18
studio_matte_feather_px = 3
studio_matte_despill   = true
studio_char_use_detailer   = true    # detailer chỉ chạy ở lớp nhân vật
studio_char_use_ip_adapter = true
# Auto-fallback về classic cho cảnh khó (quyết định #4)
studio_fallback_max_chars  = 3       # > ngưỡng này → render classic cả cảnh
studio_fallback_interaction_tags = ["hug","embrace","fight","holding hands","carry","kiss"]
# Bóng đổ: CHƯA làm ở P1 (quyết định #2), dời P4. Giữ khoá, mặc định tắt.
studio_shadow_opacity  = 0.0         # 0 = tắt; >0 sẽ bật ở P4
```

Đồng bộ `config.example.json` repo tổng nếu cần expose lên UI (Global Settings).

---

## 8. CI/CD & test  (mục tiêu: phủ hàm "âm thầm sai thì hỏng nặng", KHÔNG cần GPU)

CI hiện tại ([`ci.yml`](../.github/workflows/ci.yml)) chỉ chạy trên push/PR vào `main`, lint+compile+pytest orchestrator (Ubuntu, no GPU). Submodule có CI cú pháp riêng. Bổ sung test **thuần Python** trong `AIVoice/apps/MediaComposer/tests/`:

| Test | Ca kiểm | Gate phase |
|------|---------|-----------|
| `test_layout_planner.py` | shot_type/#chars → anchor/scale/z đúng; parse LLM JSON; fallback heuristic khi JSON hỏng | P1 |
| `test_matting.py` | ảnh synthetic (nhân vật đặc trên nền `matte_bg_color`) → alpha đúng; despill; cổng key-hỏng | P2 |
| `test_compositor.py` | đặt lớp đúng toạ độ/kích thước theo anchor+scale; z-order; không tràn khung; pixel xác định | P1 |
| `test_bg_cache.py` | cache-key ổn định theo location; lần 2 KHÔNG gọi render (đếm lời gọi mock) | P2 |
| `test_studio_pipeline_smoke.py` | monkeypatch renderer/matte (ảnh giả) → chạy hết, xuất frame, không đụng SD | P1 |

**Gate CI/CD chung:** `pytest -q` (AIVoice + repo tổng) xanh **trước** khi bump con trỏ submodule ở repo tổng. Feature flag `classic` mặc định ⇒ test pipeline cũ không đổi.

---

## 9. Phases & cổng kiểm

| Phase | Nội dung | Cổng kiểm |
|-------|----------|-----------|
| **P0** | Skeleton: `studio/` package rỗng có interface; thêm config flags; nhánh step2 theo `render_mode` (studio = NotImplemented an toàn); doc này | `py_compile` sạch; `render_mode=classic` chạy y hệt cũ; test cũ xanh |
| **P1** | Lõi 1 nhân vật: layout heuristic + character_render + chroma matte + compositor; xuất frame | 5 test §8 (P1) xanh; 1 cảnh 1 nhân vật ra frame ghép hợp lý (chạy tay GPU) |
| **P2** | Cache nền theo location + cổng key-hỏng→fallback classic | test bg_cache + matting gate xanh; nhiều cảnh cùng location tái dùng nền |
| **P3** | Đa nhân vật + z-order + layout LLM (schema mở rộng + fallback) | cảnh 2–3 nhân vật ghép đúng thứ tự/vị trí; parse LLM có fallback |
| **P4** | Hòa màu/bóng đổ nâng cao; auto-fallback classic cho cảnh khó; tinh chỉnh chất lượng | so sánh A/B classic vs studio; không "sticker"; VRAM trong ngưỡng |

**Quy trình commit mỗi phase (2 tầng):**
1. Code + test trong `AIVoice/` → `pytest -q` xanh → commit → push `AIVoice feat/studio-compositing`.
2. Repo tổng: `git add AIVoice` (bump con trỏ) + doc/config → commit → push `feat/studio-compositing`.
3. Khi ổn định: PR `feat/studio-compositing` → `main` (kích CI). Merge sau khi CI xanh.

---

## 10. Quyết định bổ sung (chốt 2026-07-18)

1. **Neo dọc lớp nhân vật:** TÙY BỐI CẢNH — `anchor_y` = `bottom` (đứng trong cảnh) hoặc `middle` (chân dung/cận), LLM/heuristic chọn. → §3, §4, §6 đã cập nhật.
2. **Bóng đổ:** CHƯA làm — dời hẳn P4 (`studio_shadow_opacity=0.0` mặc định). → §7, §9 đã cập nhật.
3. **UI điều khiển:** dùng `config.toml` trước (mục `[storytelling]`); expose lên webui Global Settings ở P3/P4 khi lõi ổn định. P0–P2 đọc flag từ config nên không phụ thuộc UI.
4. **Auto-fallback classic:** CÓ. Kích hoạt khi (a) matte key hỏng (§5), (b) số nhân vật > `studio_fallback_max_chars` (mặc định 3), (c) cảnh chứa tag trong `studio_fallback_interaction_tags`. Cảnh fallback render bằng khối classic hiện có → vẫn ra `scene.frame_path` bình thường.
