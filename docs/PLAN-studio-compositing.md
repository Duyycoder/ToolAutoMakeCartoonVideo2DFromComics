# Studio Compositing — hồ sơ triển khai và nghiệm thu

> **Nhánh:** `feat/studio-compositing` ở repo tổng và submodule `AIVoice`.
> **Trạng thái code:** lõi P1–P4 đã triển khai và harden ngày 2026-07-18.
> **Tương thích:** `render_mode = "classic"` vẫn là mặc định; Studio là opt-in.
> **Trạng thái vận hành:** GPU smoke một cảnh đã qua. Gate cả chương/video và CI từ
> GitHub vẫn phải xanh trước khi merge hoặc gắn tag phát hành.

## 1. Kết quả cần đạt

Studio không yêu cầu Stable Diffusion vẽ cả người và cảnh trong một lượt. Mỗi frame
được dựng theo lớp:

```text
Scene + metadata đã lưu
  -> layout LLM (fallback heuristic)
  -> background riêng (cache theo story/location/time)
  -> từng character riêng (IP-Adapter/LoRA/detailer tùy config)
  -> ChromaMatter; nếu chroma hỏng thì GrabCutMatter CPU
  -> crop theo alpha + scale/anchor/z-order + harmonize/shadow
  -> scene_XXX.png
```

Cảnh đông người, cảnh tương tác vật lý, nhân vật không phân giải được hoặc matte
không đạt cổng chất lượng sẽ chạy lại bằng classic. Nếu cả Studio lẫn classic lỗi,
pipeline báo lỗi thật thay vì ghi frame xám và đánh dấu thành công.

## 2. Những phần đã triển khai

| Thành phần | Hành vi hiện tại |
|---|---|
| State | `scene_to_dict`/`scene_from_dict` giữ `_semantic_meta`, `_llm_background_prompt`, `_llm_layout` qua resume/WebUI. |
| Resolver | Khớp tên/slug chính xác, giữ thứ tự cảnh, không còn false-positive kiểu `Lan` trong `landscape`; `primary_character` dạng display name vẫn phân giải được. |
| Layout | LLM là mặc định trong Studio; layout thiếu, trùng hoặc thiếu nhân vật sẽ fallback toàn cảnh sang heuristic. Pose riêng được giữ. |
| Background | Prompt nền ưu tiên output LLM; state cũ dùng location/time hoặc prompt đã lọc person/appearance. Cache nằm ở context của story và không ghi khi cache tắt. |
| Character | Có framing close/medium/full, action cue tiếng Anh, art style đã lọc tag phong cảnh, reset LoRA trước khi render nền, và bootstrap ref tùy điều kiện. |
| Matte | Chroma RGB + feather + despill đa kênh; custom matte color được mô tả đúng họ màu; adaptive GrabCut CPU khi model không tạo nền phẳng đúng màu. |
| Quality gate | Alpha coverage phải nằm trong 5–95%; ngoài ngưỡng sẽ thử matte thích nghi rồi classic. |
| Composite | Cắt lề alpha trước scale, đặt theo anchor/z-order, giữ alpha khi harmonize, hỗ trợ bóng chân qua `studio_shadow_opacity`. |
| Failure | Không bỏ âm thầm character layer, không xuất background-only cho prompt có người, không tạo placeholder xám khi hai renderer cùng lỗi. |
| Resume/SSE | `video_done` luôn kiểm tra MP4, tự phục hồi từ task dir hoặc hạ phase để chạy lại; callback merge hoàn tất trước terminal SSE và merge lỗi không còn bị ghi `VIDEO_GENERATED`. |

## 3. Config

Các khóa thuộc `[storytelling]` trong `AIVoice/apps/MediaComposer/config.toml`:

```toml
render_mode = "classic"                 # classic | studio
studio_bg_cache = true
studio_layout_source = "llm"            # tự fallback heuristic
studio_matte_bg_color = "#00B140"
studio_matte_threshold = 0.18
studio_matte_feather_px = 3
studio_matte_despill = true
studio_matte_adaptive_fallback = true
studio_char_use_detailer = true
studio_char_use_ip_adapter = true
studio_fallback_max_chars = 3
studio_fallback_interaction_tags = ["hug", "embrace", "fight", "holding hands", "carry", "kiss"]
studio_shadow_opacity = 0.0
```

File config cũ có giá trị `studio_layout_source = "heuristic"` sẽ tiếp tục tôn
trọng giá trị đó; muốn dùng layout LLM cần đổi rõ sang `"llm"`. Không commit
`config.toml` vì file có thể chứa khóa dịch vụ cục bộ.

## 4. Bằng chứng kiểm định 2026-07-18

- MediaComposer: `84 passed`; repo tổng: `32 passed`.
- Ruff theo phạm vi CI của repo tổng và toàn bộ tệp Studio/tệp tích hợp đã sạch.
- `compileall app tests` đã sạch.
- GPU thật RTX 3060 6 GB đã đi qua `StudioPipeline.run_batch`: cache nền được dùng,
  chroma coverage 1.0 được nhận diện là hỏng, GrabCut thích nghi cắt được chủ thể và
  compositor xuất frame Studio, không rơi sang classic.
- Frame GPU: `storage/tasks/studio_g0_codex_20260718_130759/draft_frames/scene_000.png`.
- Cache nền đã tái sử dụng:
  `storage/tasks/contexts/nguoi_tren_van_nguoi/bg_cache/ancient_scholar_courtyard_day.png`.

Đây là smoke một cảnh, chưa phải nghiệm thu trọn 82 cảnh. Trước merge/release cần
chạy một batch đại diện có ít nhất: cảnh không người, một người, 2–3 người, cảnh
tương tác fallback classic, hai cảnh cùng location, rồi chạy Pass B dựng video.

## 5. CI/CD và thứ tự xuất bản

- Repo tổng chạy ruff, compileall và 27 unit test trên `main`, `feat/**`, `dev/**`.
- AIVoice có workflow GPU-free riêng: critical lint, compile storytelling và toàn
  bộ 84 test với OpenCV headless.
- Release checkout submodule recursive, verify trước rồi đóng gói cả `AIVoice`,
  `toolCaoTruyen` và `.gitmodules`; không còn ZIP chứa gitlink rỗng.
- Thứ tự bắt buộc: `toolCaoTruyen` -> `AIVoice` -> repo tổng -> tag `v*`.
- Không gửi credential GitHub qua URL proxy. Dùng SSH hoặc URL GitHub trực tiếp và
  quyền Workflows write khi commit có `.github/workflows/*`.

## 6. Definition of Done trước merge

- [x] Unit test/lint/compile cục bộ xanh ở cả hai tầng.
- [x] GPU smoke đi đúng plan -> bg cache -> char -> adaptive matte -> composite.
- [x] Classic vẫn là mặc định và có fallback rõ ràng.
- [x] Metadata Studio sống qua save/load state.
- [ ] Commit của mọi submodule reachable trên remote.
- [ ] GitHub Actions xanh ở `toolCaoTruyen`, `AIVoice` và repo tổng.
- [ ] Batch đại diện chạy hết Pass A/Pass B và xem tay các frame biên.
- [ ] Chỉ sau các gate trên mới merge và gắn tag release.
