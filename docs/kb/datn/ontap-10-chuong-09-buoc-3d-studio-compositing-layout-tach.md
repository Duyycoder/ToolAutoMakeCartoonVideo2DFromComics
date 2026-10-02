# Chương 09. Bước 3d — Studio compositing: layout, tách nền (matting), ghép lớp, unify pass

- Phạm vi chương: toàn bộ package `AIVoice/apps/MediaComposer/app/services/storytelling/studio/` (7 module), cấu hình `[storytelling]` trong `app/config.py` , điểm gọi trong `app/services/storytelling/orchestrator.py` , schema layout trong `llm_prompter.py` , và 11 file test `tests/test_studio_*.py` (66 test function).

- Tài liệu gốc để đối chiếu: `docs/PLAN-studio-compositing.md` , `docs/HANDOFF-studio-phases.md` , `docs/PLAN-quality-speed-` `v2.md` .

- Mọi số liệu trong chương này đọc trực tiếp từ code. Chỗ nào code và tài liệu mâu thuẫn, chương sẽ ghi rõ.

## 0. Đọc nhanh: chương này trả lời câu hỏi gì?

Ở chương sinh ảnh (Stable Diffusion) ta đã biết chế độ mặc định classic: mỗi cảnh truyện → một prompt → SD vẽ cả người lẫn cảnh trong một lượt → một ảnh `scene_XXX.png` .

Chế độ Studio làm khác: nó dựng mỗi frame giống một xưởng phim hoạt hình 2D truyền thống — vẽ phông nền riêng, vẽ từng nhân vật riêng trên nền phẳng, cắt nhân vật ra (matting), rồi dán (composite) lên phông theo một bố cục (layout), cuối cùng "tô lại" nhẹ cả khung (unify pass) để các lớp ăn khớp ánh sáng.

- **Khái niệm:** Layout planning · **Một câu:** Quyết định mỗi nhân vật đứng đâu, to bao nhiêu, ai đứng trước · **Module:** `layout_planner.py`
- **Khái niệm:** Background rendering + cache · **Một câu:** Sinh phông nền không có người, lưu lại theo địa điểm để tái dùng · **Module:** `background_renderer.py`
- **Khái niệm:** Character rendering · **Một câu:** Sinh riêng từng nhân vật trên nền xám phẳng, khung dọc 512x768 · **Module:** `character_renderer.py`
- **Khái niệm:** Matting · **Một câu:** Tạo kênh alpha (mặt nạ trong suốt) để tách nhân vật khỏi nền · **Module:** `matting.py`
- **Khái niệm:** Compositing · **Một câu:** Ghép các lớp RGBA lên nền theo công thức alpha "over" · **Module:** `compositor.py`
- **Khái niệm:** Unify pass · **Một câu:** img2img strength thấp trên cả frame để hòa ánh sáng · **Module:** `unify_pass.py`
- **Khái niệm:** Điều phối · **Một câu:** Chạy cả batch, quyết định fallback classic, cổng chất lượng · **Module:** `studio_pipeline.py`

Điều quan trọng nhất cần nói thật với hội đồng: Studio là chế độ opt-in, thử nghiệm. Mặc định hệ thống là `classic` ( `app/config.py:86` : `"render_mode": "classic"` ), và thực nghiệm đã chỉ ra Studio không hợp với phong cách mặc định thủy mặc (xem mục 6). Đây là một quyết định kỹ thuật có bằng chứng, không phải phần làm dở.

## 1. Vai trò trong hệ thống

### 1.1. Vị trí trong pipeline

Trong luồng tổng (Bước 3 — "hoạt hình hóa"), MediaComposer chạy các "trạm":

- Trạm 1: tách cảnh ngữ nghĩa + LLM viết prompt ( `llm_prompter.py` ) → mỗi `Scene` có `image_prompt` , `shot_type` , `characters_in_scene` , và (cho Studio) `_llm_background_prompt` , `_llm_layout` , `_llm_action` , `_semantic_meta` . Trạm 2: sinh ảnh storyboard → đây là nơi rẽ nhánh classic / studio. Sau đó: TTS, phụ đề, dựng video (các chương khác).

Điểm rẽ nhánh nằm ở `AIVoice/apps/MediaComposer/app/services/storytelling/orchestrator.py:354` :

```
if st_config.get("render_mode", "classic") == "studio" and reroll_index is None:
    from app.services.llm import unload_local_llm
    unload_local_llm()
    from app.services.storytelling.studio.studio_pipeline import StudioPipeline
    StudioPipeline(self.ctx_mgr, self.context).run_batch(scenes, draft_dir, update_prog)
    state = self.load_state() or {}
    self.save_state("STORYBOARD_READY", scenes, task_dir, ...)
    update_prog("Hoàn thành Trạm 2 (Studio): Storyboard đã sẵn sàng!", 100)
    return scenes
```

Ba điểm cần nhớ:

- 1. Chỉ khi `render_mode=="studio"` và không phải reroll ( `reroll_index is None` ) — tức là "vẽ lại 1 cảnh" vẫn luôn đi đường classic. 2. Trước khi nạp SD, gọi `unload_local_llm()` để giải phóng VRAM của Ollama (GPU 6 GB không chứa nổi cả LLM lẫn SD). 3. Kết quả cuối cùng giống hệt classic: file `draft_frames/scene_XXX.png` + `scene.frame_path` , state chuyển `STORYBOARD_READY` . Các bước sau (TTS, video) không cần biết frame được làm bằng cách nào — đây là thiết kế "thay thế được" (drop-in).

### 1.2. Cách bật chế độ Studio (và một chi tiết cần biết)

Có 5 nơi liên quan tới `render_mode` :

- **Nơi:** WebUI · **Giá trị:** dropdown `s3RenderMode` : `classic` / `studio` · **Nguồn:** `webui/index.html:544-547`
- **Nơi:** Orchestrator (FastAPI :8100) · **Giá trị:** schema mặc định `"auto"` · **Nguồn:** `orchestrator/main.py:159` , `orchestrator/config.py:102`
- **Nơi:** Pipeline gọi subprocess · **Giá trị:** chỉ truyền `--render-mode` khi giá trị là `classic` hoặc `studio` · **Nguồn:** `orchestrator/pipeline.py:582-584`
- **Nơi:** CLI MediaComposer · **Giá trị:** `--render-mode` default `"classic"` , choices `classic/studio` , rồi ghi vào config · **Nguồn:** `adapter_video_cli.py:59,74`
- **Nơi:** Điểm rẽ nhánh · **Giá trị:** chỉ nhận đúng chuỗi `"studio"` · **Nguồn:** `orchestrator.py:354`

Comment ở `orchestrator/main.py:159` ghi `"auto" (CPU->classic, CUDA->studio)` . Nhưng khi đọc code thực tế: với `"auto"` , `pipeline.py` không truyền cờ → `adapter_video_cli.py` dùng default `"classic"` và ghi `config.storytelling["render_mode"] =` `"classic"` → `orchestrator.py:354` không vào nhánh Studio. Tức là `auto` hiện tại chạy như `classic` , không có đoạn code nào dò CUDA để chọn studio. Nếu hội đồng hỏi, trả lời trung thực: "auto hiện tương đương classic; Studio phải chọn rõ trên UI".

### 1.3. Input / Output

Input (cho mỗi cảnh, đọc từ đối tượng `Scene` + `context` ):

- **Trường:** `image_prompt` · **Ý nghĩa:** Prompt tổng của cảnh (dùng cho classic và làm nguồn dự phòng) · **Sinh ở đâu:** `llm_prompter.py`
- **Trường:** `shot_type` · **Ý nghĩa:** `close` / `medium` / `wide` (giá trị lạ → ép về `wide` ) · **Sinh ở đâu:** `llm_prompter.py:200-201`
- **Trường:** `characters_in_scene` , `primary_character` · **Ý nghĩa:** Tên nhân vật trong cảnh · **Sinh ở đâu:** `llm_prompter.py:196-197`
- **Trường:** `_llm_background_prompt` · **Ý nghĩa:** Prompt nền sạch cho render riêng · **Sinh ở đâu:** `llm_prompter.py:204`
- **Trường:** `_llm_layout` · **Ý nghĩa:** List JSON `{name, anchor_x, anchor_y, scale, z, prompt}` · **Sinh ở đâu:** `llm_prompter.py:205`
- **Trường:** `_llm_action` · **Ý nghĩa:** Hành động chính của cảnh · **Sinh ở đâu:** `llm_prompter.py:194`
- **Trường:** `_semantic_meta` · **Ý nghĩa:** `{location, time_of_day,...}` từ semantic splitter · **Sinh ở đâu:** `orchestrator.py:181-185`
- **Trường:** `context.characters` · **Ý nghĩa:** Danh sách nhân vật: `name` , `slug` , `keywords_en` · **Sinh ở đâu:** Context manager

Output: `draft_frames/scene_{i:03d}.png` kích thước `image_width x image_height` (mặc định `config.toml` : 768x432), gán vào `scene.frame_path` . Phụ phẩm: `bg_cache/<location_id>.png` trong thư mục context của truyện.

## 2. Nền tảng lý thuyết từ gốc

### 2.1. Vì sao "ghép lớp" thay vì "vẽ một lượt"?

Trực giác. Hãy nghĩ tới cách làm phim hoạt hình cel (Doraemon, Ghibli thời trước): họa sĩ phông nền vẽ căn phòng một lần; họa sĩ nhân vật vẽ nhân vật trên tấm nhựa trong (cel); quay phim đặt cel lên phông. Căn phòng xuất hiện trong 50 cảnh thì chỉ vẽ 1 lần. Nhân vật được vẽ bởi người chuyên vẽ nhân vật, ở kích thước đủ lớn để vẽ mặt cho đẹp.

Vấn đề của "vẽ một lượt" với Stable Diffusion 1.5 (lý do kỹ thuật cụ thể):

- 1. Mặt nhỏ thì xấu. SD 1.5 làm việc trong latent space nén 8 lần mỗi chiều: ảnh 768x432 → latent 96x54. Một nhân vật toàn thân trong cảnh rộng có khuôn mặt cao ~20-30 pixel → chỉ còn khoảng 3x3 ô latent. Không thể "vẽ" mắt, mũi, miệng rõ ràng trong 9 ô. Đó là lý do mặt trong cảnh rộng hay méo. 2. Không nhất quán nền. Cùng một "sân học viện" ở cảnh 3 và cảnh 7 sẽ bị vẽ thành hai sân khác nhau vì seed và prompt khác nhau. 3. Khó kiểm soát bố cục. Prompt "A đứng trái, B đứng phải" gần như bị SD bỏ qua — text encoder CLIP không mã hóa tốt quan hệ không gian. 4. Nhân vật lẫn đặc điểm (attribute leakage). Hai nhân vật trong một prompt hay bị trộn màu tóc/quần áo của nhau.

Ghép lớp giải quyết:

- **Vấn đề:** Mặt nhỏ · **Cách Studio xử lý:** Sinh nhân vật riêng ở khung 512x768, mặt to → rồi mới thu nhỏ · **Code:** `studio_pipeline.py:39_CHAR_SIZE = (512, 768)`
- **Vấn đề:** Nền không nhất quán · **Cách Studio xử lý:** Cache nền theo `location + time_of_day` · **Code:** `background_renderer.py` , `studio_pipeline.py:239-` `247`
- **Vấn đề:** Bố cục · **Cách Studio xử lý:** Vị trí/scale/z-order là số trong `LayerPlan` , đặt bằng toán, không nhờ SD · **Code:** `layout_planner.py` , `compositor.py`
- **Vấn đề:** Lẫn đặc điểm · **Cách Studio xử lý:** Mỗi lần sinh chỉ 1 nhân vật ( `"solo", "1 person"` ), gắn đúng LoRA/IP-Adapter của người đó · **Code:** `character_renderer.py:104-107` , `studio_pipeline.py:621-622`

Cái giá phải trả: ghép lớp tạo ra "vẻ dán sticker" — ánh sáng nhân vật không khớp nền, không có bóng, mép cắt sắc. Phần 2.5 và 2.6 (harmonize, shadow, unify pass) là để trả món nợ này.

### 2.2. Ảnh số, kênh alpha và ảnh RGBA

Một ảnh RGB là lưới pixel, mỗi pixel 3 số 0-255 (đỏ, lục, lam). Ảnh RGBA thêm kênh thứ tư alpha (α): độ "đục" của pixel, 0 = trong suốt hoàn toàn, 255 (hay 1.0 khi chuẩn hóa) = đục hoàn toàn. Giá trị giữa (ví dụ 0.4) nghĩa là "pixel này 40% thuộc nhân vật, 60% để lộ phía sau" — xảy ra ở sợi tóc, mép áo mỏng, vùng mờ chuyển động.

Trong code, kênh alpha của lớp nhân vật chính là "mặt nạ nhân vật": interface `Matter` được định nghĩa đúng như vậy ( `matting.py:31-36` ): "RGB → RGBA (kênh alpha là mặt nạ nhân vật)".

### 2.3. Phương trình compositing và bài toán matting

Phương trình compositing (Porter & Duff, 1984 — toán tử "over"). Với mỗi pixel:

- : màu pixel kết quả (3 kênh). : màu tiền cảnh (foreground — nhân vật). : màu hậu cảnh (background — phông nền).

- : độ đục của tiền cảnh tại pixel đó.

- ở sợi tóc → trộn nửa-nửa.

Ví dụ:

- (thấy nhân vật).

- (thấy nền).

Khi cả lớp dưới cũng có alpha (

- ), công thức tổng quát của "over" là:

Trong code, nền luôn đục (

- , vì `canvas = background.convert("RGBA")` ở `compositor.py:84` ) nên công thức rút gọn đúng

về

- . Phép này được thực hiện bởi `PIL.Image.alpha_composite` ( `compositor.py:109` :

`canvas.alpha_composite(c, dest=(x, y))` ).

Matting là bài toán ngược: cho ảnh

- (nhân vật trên nền), tìm ,

- , . Mỗi pixel có 3 phương trình (R, G, B) nhưng 7 ẩn (3 của

F, 3 của B, 1 của α) → bài toán thiếu điều kiện (ill-posed), vô số nghiệm. Mọi kỹ thuật matting đều là cách thêm giả thiết để thu hẹp nghiệm:

- **Kỹ thuật:** Chroma-key (phông xanh) · **Giả thiết thêm vào:** Biết trước = một màu cố định · **Có trong project?:** Có — `ChromaMatter`
- **Kỹ thuật:** Trimap-based matting · **Giả thiết thêm vào:** Người dùng vẽ trimap: vùng chắc chắn FG, chắc chắn BG, vùng chưa biết · **Có trong project?:** Không dùng trực tiếp
- **Kỹ thuật:** GrabCut · **Giả thiết thêm vào:** Viền ảnh là nền; màu FG/BG mỗi bên theo một phân phối (GMM); biên đi qua chỗ màu thay đổi mạnh · **Có trong project?:** Có — `GrabCutMatter`
- **Kỹ thuật:** Deep segmentation/matting · **Giả thiết thêm vào:** Mạng nơ-ron đã học "nhân vật trông như thế nào" từ dữ liệu · **Có trong project?:** Có — `RembgMatter` (isnet- anime)

Trimap là gì: một ảnh 3 mức — trắng (chắc chắn nhân vật), đen (chắc chắn nền), xám (chưa biết, thường là dải mép). Thuật toán matting cổ điển (Closed-form matting, KNN matting...) chỉ phải giải α ở vùng xám. Thư viện `pymatting` (khai báo ở `AIVoice/requirements.txt:84` như dependency của rembg cho alpha matting) cài các thuật toán này, nhưng code project không bật chế độ alpha matting của rembg — `RembgMatter.cutout` chỉ gọi `remove(..., post_process_mask=...)` ( `matting.py:122-123` ).

### 2.4. Segmentation khác matting thế nào?

- **Segmentation (phân vùng):** Output Nhãn rời rạc mỗi pixel: 0 hoặc 1 (hoặc xác suất rồi cắt ngưỡng) · **Matting (tách alpha):** Giá trị liên tục α ∈ [0,1]
- **Segmentation (phân vùng):** Mép tóc Răng cưa, hoặc "cắt cụt" sợi tóc · **Matting (tách alpha):** Mềm, sợi tóc bán trong suốt
- **Segmentation (phân vùng):** Câu hỏi trả lời "Pixel này thuộc vật thể nào?" · **Matting (tách alpha):** "Pixel này bao nhiêu % là tiền cảnh?"

Project dùng segmentation + làm mềm mép (feather) như một xấp xỉ rẻ của matting: model isnet-anime cho mặt nạ, rồi `GaussianBlur(feather_px)` lên kênh alpha để tạo dải chuyển tiếp mềm ( `matting.py:125-128` ). Đây là xấp xỉ, không phải matting đúng nghĩa — nên ở mép vẫn có thể còn viền mờ (fringe). `docs/PLAN-studio-compositing.md:115-116` ghi nhận: "vài frame còn fringe mép mờ nhẹ".

### 2.5. Ba kỹ thuật matting trong code — nguyên lý chi tiết

(a) Chroma-key theo khoảng cách màu ( `ChromaMatter` , `matting.py:39-83` )

Trực giác: phông xanh ở trường quay. Biết nền là màu (ví dụ `#00B140` = (0,177,64)), pixel càng gần màu này thì càng là nền.

Cơ chế:

- 1. Khoảng cách Euclid trong không gian RGB, chuẩn hóa về [0,1]:

- là khoảng cách xa nhất có thể giữa hai màu, từ đen tới trắng — hằng `_MAX_RGB_DIST` , `matting.py:17` .) 2. Hàm

"dốc" tuyến tính (ramp) biến khoảng cách thành alpha:

với ngưỡng = `threshold` = 0.18 (config `studio_matte_threshold` ) và độ dốc = `ramp` = 0.10 (default tham số,

- → nền (α=0);

- → nhân vật (α=1); giữa → chuyển mượt. 3. Despill (khử ám màu): ánh

`matting.py:41` ). Nghĩa là: xanh của nền hắt lên mép tóc/áo. Code ( `_despill` , `matting.py:67-83` ) xác định kênh "trội" của màu nền (kênh cao hơn kênh thấp nhất > 64), rồi ở các pixel mép (α thấp) kéo kênh trội xuống không vượt quá max các kênh còn lại. Trộn theo `edge_strength = 1 - alpha` → giữa nhân vật (α≈1) gần như không bị đổi màu. 4. Feather: `GaussianBlur(feather_px)` lên alpha (config `studio_matte_feather_px` = 3).

```
dist = np.linalg.norm(rgb - self.bg_rgb, axis=2) / _MAX_RGB_DIST
alpha = np.clip((dist - self.threshold) / self.ramp, 0.0, 1.0)
if self.despill:
    rgb = self._despill(rgb, alpha)
```

( `matting.py:52-57` )

Hạn chế: chỉ đúng khi nền thật sự phẳng đúng màu. SD 1.5 không tuân thủ "flat green background" tuyệt đối (thường vẽ gradient, bóng, vật trang trí). Tài liệu `PLAN-studio-compositing.md:98-101` ghi lại root cause: chroma-key "giữ nguyên nền (coverage=1.0) hoặc ăn vào nhân vật". Đây là lý do chroma bị hạ xuống làm lưới an toàn.

Chi tiết tinh tế: màu nền mặc định hiện là xám `#9CA3AF` ( `config.py:95` ). Với màu xám (156,163,175), không kênh nào cao hơn kênh thấp nhất > 64 → `dominant.any()` là False → despill không làm gì ( `matting.py:74-75` ). Đó đúng là mục đích: đổi sang xám để khỏi "green spill" lên áo trắng ( `PLAN-studio-compositing.md:104-105` ).

(b) GrabCut ( `GrabCutMatter` , `matting.py:132-190` )

Trực giác: "Tôi chỉ biết viền ảnh chắc chắn là nền. Hãy tự học màu nền trông ra sao, màu nhân vật trông ra sao, rồi vẽ đường biên đi qua chỗ màu đổi đột ngột."

Cơ chế (Rother, Kolmogorov, Blake — 2004):

- 1. Mô hình màu: mỗi phía (FG, BG) được mô tả bằng một Gaussian Mixture Model (GMM) 5 thành phần trong không gian RGB. Mỗi thành phần có 1 trọng số + 3 giá trị trung bình + ma trận hiệp phương sai 3x3 = 9 số → 13 số x 5 = 65 số. Đó chính là lý do code khởi tạo `bg_model = np.zeros((1, 65))` ( `matting.py:170-171` ) — con số 65 không phải tùy ý. 2. Hàm năng lượng cho một cách gán nhãn

- (data term): chi phí gán pixel là FG/BG =

- xác suất màu của nó dưới GMM tương ứng. - Số hạng thứ hai

(smoothness): phạt khi hai pixel kề nhau có nhãn khác nhau, nhưng phạt ít nếu màu chúng khác nhau nhiều → biên được "khuyến khích" chạy dọc cạnh màu. được chọn theo độ tương phản trung bình của ảnh, cân bằng hai số hạng. 3. Min-cut / max- flow trên đồ thị pixel: mỗi pixel là một nút, nối với hai nút nguồn/đích (FG/BG) bằng cạnh có trọng số = data term, và nối với pixel kề bằng cạnh có trọng số = smoothness term. Nhát cắt nhỏ nhất tách đồ thị thành hai phần = cách gán nhãn có

- nhỏ

nhất. Với GMM cố định, min-cut cho nghiệm tối ưu toàn cục của bước đó; nhưng thuật toán lặp (gán nhãn → học lại GMM → cắt lại, `iterations` = 5) nên tổng thể chỉ hội tụ về cực tiểu cục bộ — phụ thuộc cách khởi tạo.

Cách code áp dụng:

- Thu nhỏ ảnh để phân tích tối đa 384 px cạnh dài ( `max_analysis_size` , `matting.py:136,159-164` ) → nhanh trên CPU. Khởi tạo bằng hình chữ nhật chừa viền 1px: `rect = (1, 1, aw - 2, ah - 2)` với cờ `cv2.GC_INIT_WITH_RECT` ( `matting.py:168-173` ). Lưu ý tinh tế: code tạo sẵn mask toàn `GC_PR_BGD` , nhưng ở chế độ `GC_INIT_WITH_RECT` OpenCV tự ghi đè mask: ngoài rect = `GC_BGD` (chắc chắn nền — ở đây là viền 1px), trong rect = `GC_PR_FGD` ("có thể là tiền cảnh"), rồi GrabCut tự tinh chỉnh. Comment trong code ("phần trong là vùng GrabCut tự phân loại") đúng về ý, nhưng giá trị khởi tạo `GC_PR_BGD` thực tế không được dùng. Lấy pixel `GC_FGD|GC_PR_FGD` thành alpha 255. Morphology open rồi close kernel 3x3: open xóa đốm nền lẻ tẻ, close lấp lỗ nhỏ trong nhân vật ( `matting.py:179-181` ). Phóng alpha về kích thước gốc, feather. Có "đường tắt": nếu ảnh gần như phẳng hoàn toàn (độ lệch chuẩn màu < 2.0) → trả mặt nạ rỗng ngay, không chạy GrabCut ( `matting.py:154-157` ).

Hạn chế: GrabCut không hiểu "hình người", chỉ hiểu màu. Nhân vật mặc áo cùng tông nền sẽ bị cắt hỏng. Kết quả là mặt nạ nhị phân (thô hơn matting thật).

(c) Deep segmentation — rembg + IS-Net anime ( `RembgMatter` , `matting.py:86-129` ) — engine CHÍNH

rembg là thư viện Python mã nguồn mở, bọc nhiều model tách nền dưới dạng ONNX, chạy bằng `onnxruntime` . Code tạo session bằng `new_session(model_name)` và gọi `remove(image, session=..., post_process_mask=True)` .

Model được dùng: `studio_matte_model = "isnet-anime"` ( `config.py:92` ). Đây là mạng IS-Net (Intermediate Supervision Network, từ bài "Highly Accurate Dichotomous Image Segmentation" — Qin et al., ECCV 2022) được huấn luyện trên dữ liệu nhân vật anime (bộ anime-segmentation). Kiến trúc IS-Net kế thừa họ U²-Net (cùng tác giả, 2020 — cũng là model mặc định `u2net` của rembg).

Nguyên lý U²-Net / IS-Net (mức trực giác → cơ chế):

- Encoder–decoder hình chữ U: nửa trái (encoder) liên tục thu nhỏ ảnh, học đặc trưng từ chi tiết (cạnh, màu) tới ngữ nghĩa ("đây là tóc", "đây là người"). Nửa phải (decoder) phóng to dần để trả về mặt nạ đúng độ phân giải. Skip connection nối encoder sang decoder cùng tầng để không mất chi tiết mép. "U lồng U" (RSU block): mỗi khối của U²-Net lại là một U-Net nhỏ, giúp nắm ngữ cảnh đa tỷ lệ ngay trong một tầng — vừa thấy hình dáng toàn thân, vừa thấy sợi tóc. Output: bản đồ xác suất mỗi pixel thuộc tiền cảnh (qua sigmoid, ∈ [0,1]). IS-Net thêm "intermediate supervision": trong huấn luyện, dùng một autoencoder mặt nạ (ground-truth encoder) để giám sát cả các đặc trưng trung gian, không chỉ output cuối → mặt nạ chi tiết hơn ở cấu trúc mảnh. Vì sao "anime": model đã học hình dáng nhân vật vẽ kiểu anime (đường viền đậm, mảng màu phẳng). Nó không cần biết màu nền là gì → giải thích tại sao nó bền hơn chroma-key khi SD vẽ nền không phẳng.

Code comment ghi lợi ích và chi phí thực đo: "isnet-anime hiểu HÌNH DÁNG nhân vật anime nên cắt sạch tóc/tay/viền và tự bỏ mảnh nền rời. Chạy CPU (~0.9s/ảnh 512x768)" ( `matting.py:89-92` ).

Kỹ thuật tối ưu trong code: session được cache ở mức class ( `_sessions: dict = {}` , `matting.py:95,104-113` ) → model ONNX chỉ nạp một lần cho cả batch dù tạo nhiều `RembgMatter` . `import rembg` là lazy — không cài rembg thì app vẫn chạy (rơi về chroma, `studio_pipeline.py:544-546` ).

`post_process_mask=True` : rembg tự hậu xử lý mặt nạ. Đọc mã nguồn rembg đang cài trong `AIVoice/.venv` ( `rembg/bg.py` , hàm `post_process` ): morphology open → `GaussianBlur` 5x5 σ=2 → cắt ngưỡng 127 thành 0/255. Tức là sau bước này mặt nạ là nhị phân hoàn toàn; độ mềm mép duy nhất đến từ bước feather mà code tự làm thêm ( `studio_matte_feather_px` = 3). Model `isnet-anime` trong rembg nhận ảnh đã resize về 1024x1024 rồi phóng mặt nạ về kích thước gốc ( `rembg/sessions/dis_anime.py` ). Lưu ý: bản rembg đang cài trong `.venv` là 2.0.69, trong khi `AIVoice/requirements.txt:83` khai `rembg>=2.0.77` — chi tiết nội bộ có thể khác giữa phiên bản, nên khi bảo vệ chỉ cần nói "rembg làm sạch mặt nạ bằng morphology rồi nhị phân hóa, sau đó em feather mép".

Chế độ `alpha_matting=True` của rembg (dùng trimap sinh từ mặt nạ + pymatting) không được bật — `remove()` mặc định `alpha_matting=False` .

Hạn chế đã đo: isnet-anime học trên nhân vật anime màu; với tranh mực thủy mặc đơn sắc nó không nhận ra người → alpha coverage chỉ 0.003 ( `docs/PLAN-quality-speed-v2.md` , đoạn "Studio compositing phải TẮT với phong cách thủy mặc").

### 2.6. Làm cho các lớp "ăn" vào nhau: harmonize, shadow, unify pass

Harmonize — dịch trung bình màu

`compositor._harmonize` ( `compositor.py:114-125` ) gọi `_match_color_mean_only` ( `face_detailer.py:194-208` ): với mỗi kênh c,

tức là dịch màu nhân vật về gần tông trung bình của nền, tối đa ±18/255 mỗi kênh để không ám màu. Chỉ dịch mean, không kéo độ lệch chuẩn (comment giải thích: kéo std khuếch đại tương phản gây vá màu loang lổ). Alpha được giữ nguyên (test `test_harmonize_preserves_alpha` ).

Chi tiết đọc từ code:

- là trung bình của toàn bộ nền (nền được resize về kích thước lớp, `compositor.py:120` ), không phải

vùng nền quanh chỗ đặt nhân vật; còn

- tính trên mọi pixel của lớp sau khi trim — kể cả pixel trong suốt (RGB của chúng vẫn

được tính vào mean). Đây là một xấp xỉ thô, đủ cho mục đích "kéo tông gần nhau".

Hạn chế: đây là chỉnh màu toàn cục, không mô phỏng hướng sáng, bóng đổ, ánh viền — nên vẫn "dán sticker".

Shadow — bóng chân giả lập

`_draw_shadow` ( `compositor.py:53-76` ): vẽ một ellipse đen rộng 80% chiều rộng nhân vật, cao 8% chiều cao nhân vật, tâm ở chân, rồi Gaussian blur bán kính `shadow_h// 2 + 1` , ghép với độ đục `opacity` . Bóng đặt trước khi ghép nhân vật ( `compositor.py:106-109` ) nên nằm dưới chân. Mặc định tắt: `studio_shadow_opacity = 0.0` ( `config.py:107` ).

Ý nghĩa: bóng tiếp xúc (contact shadow) là tín hiệu thị giác mạnh nhất cho não người biết "vật này đứng trên mặt đất", thiếu nó nhân vật trông như lơ lửng.

Unify pass — img2img denoise thấp (phần hay nhất về lý thuyết)

Trực giác: sau khi ghép, ta có một bức tranh "cắt dán". Hãy đưa nó cho một họa sĩ và bảo: "đừng đổi bố cục, chỉ tô lại bề mặt cho cả tranh cùng một nét cọ và ánh sáng". Họa sĩ đó là Stable Diffusion ở chế độ img2img với strength thấp.

Nhắc lại diffusion (xem chương sinh ảnh): SD học cách khử nhiễu. Text2img bắt đầu từ nhiễu thuần ở bước

- và khử dần về

ảnh. Img2img (kỹ thuật SDEdit, Meng et al. 2021) thì:

- 1. Mã hóa ảnh đầu vào bằng VAE encoder → latent

- 2. Thêm nhiễu tới một mức trung gian

- ở đây khác hẳn α của

( là hệ số "còn giữ tín hiệu" của lịch nhiễu — nhỏ thì

- gần 1, ảnh gốc gần như nguyên vẹn. Lưu ý:

compositing.) 3. Chạy U-Net khử nhiễu từ về 0 theo prompt, rồi VAE decoder ra ảnh.

Vì sao strength thấp giữ bố cục: diffusion vẽ cấu trúc thô (bố cục, hình khối) ở các bước nhiễu cao, và chi tiết bề mặt (nét, texture, tông sáng) ở các bước nhiễu thấp. Strength = 0.28 nghĩa là chỉ "quay lại" 28% quãng đường — vùng mà model chỉ còn sửa bề mặt. Nhân vật vẫn ở đúng chỗ, nhưng mép cắt, ánh sáng, chất liệu được vẽ lại trong cùng một lần → thống nhất.

Tham số thật ( `config.py:125-128` , `unify_pass.py` ):

- **Tham số:** `studio_unify_pass` · **Giá trị:** `True` · **Ý nghĩa:** Bật/tắt
- **Tham số:** `studio_unify_strength` · **Giá trị:** 0.28 · **Ý nghĩa:** Mức nhiễu thêm vào
- **Tham số:** `MAX_SAFE_STRENGTH` · **Giá trị:** 0.45 · **Ý nghĩa:** Trần cứng; cao hơn sẽ "vẽ lại luôn bố cục (mất nhân vật đã ghép)" ( `unify_pass.py:25-26` )
- **Tham số:** `studio_unify_steps` · **Giá trị:** 16 (tối thiểu 4) · **Ý nghĩa:** Số bước lịch; bước chạy thật = `int(16 * 0.28)` = 4 bước
- **Tham số:** `studio_unify_guidance` · **Giá trị:** 5.0 · **Ý nghĩa:** CFG scale

Chi phí: 4 bước U-Net thay vì 16-20 bước sinh mới → rẻ (docstring `unify_pass.py:14-15` ).

Prompt của unify cố tình KHÔNG nhắc nhân vật ( `build_unify_prompt` , `unify_pass.py:40-54` ): chỉ gồm style + prompt nền (đã lọc tag style trôi) + `"coherent lighting, unified color grading, seamless composition"` . Lý do (comment code): nhắc nhân vật khiến model "cố sinh thêm người thứ hai ở vùng nền trống".

Tắt IP-Adapter tạm thời: IP-Adapter đã gắn vào U-Net để giữ mặt nhân vật. Nếu để nguyên trong unify, nó kéo khuôn mặt tham chiếu đè lên cả khung. Code đặt `set_ip_adapter_scale(0.0)` + ảnh xám trung tính 224x224, rồi khôi phục scale trong `finally` ( `unify_pass.py:88-96, 116-123` ).

Không tốn VRAM thêm: `_get_img2img` dùng `AutoPipelineForImage2Image.from_pipe(pipeline._pipe)` — tạo pipeline img2img dùng chung U-Net/VAE/text encoder với pipeline text2img đang nạp, cache vào `pipeline._img2img` ( `face_detailer.py:476-` `491` ). Docstring của `_get_img2img` nói rõ pipeline này "giữ nguyên IP-Adapter + LoRA" — vì vậy mới cần tắt IP-Adapter thủ công như trên.

Một hệ quả suy ra từ code (chưa đo bằng thực nghiệm): `unify_frame` không gọi `set_character_lora(None)` , nên nếu nhân vật vừa render cuối cùng có LoRA thì LoRA đó vẫn đang gắn vào U-Net khi unify chạy. Ở strength 0.28 ảnh hưởng này nhỏ, nhưng nếu hội đồng hỏi "LoRA có ảnh hưởng nền trong unify không?" thì câu trả lời trung thực là "có thể có, chưa đo".

An toàn: mọi lỗi → trả frame gốc ( `unify_pass.py:113-115` ); không bao giờ chặn render.

Chỉ chạy khi có nhân vật: `if unify_fn is not None and layers:` ( `studio_pipeline.py:422` ) — cảnh toàn nền vốn đã liền mạch, không cần tốn 4 bước.

### 2.7. Layout planning — rule-based và LLM-based

Bài toán: với N nhân vật, chọn cho mỗi người: vị trí ngang, vị trí dọc, tỷ lệ (chiều cao so với khung), thứ tự trước-sau (z-order).

Rule-based (heuristic) — `layout_planner.build_layer_plan` ( `layout_planner.py:31-57` ). Bảng tra theo cỡ cảnh ( `_SHOT_DEFAULTS` , dòng 12-16):

- **`shot_type`:** `close` · **scale:** 1.0 · **anchor_y:** `middle` · **framing:** `close` · **Ý nghĩa điện ảnh:** Cận: nửa người, ngang tầm mắt
- **`shot_type`:** `medium` · **scale:** 0.8 · **anchor_y:** `bottom` · **framing:** `medium` · **Ý nghĩa điện ảnh:** Trung: 3/4 người, đứng đáy khung
- **`shot_type`:** `wide` · **scale:** 0.45 · **anchor_y:** `bottom` · **framing:** `full` · **Ý nghĩa điện ảnh:** Rộng: toàn thân nhỏ trong bối cảnh

Vị trí ngang ( `_distribute_anchor_x` ): 1 người → `center` ; 2 người → `left` , `right` ; ≥3 → lặp `left, center, right` . z_order = thứ tự trong danh sách. Ưu điểm: xác định (deterministic), test được, không bao giờ hỏng.

LLM-based — `build_layer_plan_from_llm` ( `layout_planner.py:60-143` ). Trạm 1 yêu cầu LLM trả thêm trường `layout` ( `llm_prompter.py:102-104` ):

```
"layout": [
  {"name": "Name1", "anchor_x": 0.5, "anchor_y": 0.9, "scale": 0.8, "z": 0,
   "prompt": "short English pose and expression tags for this character"}
]
```

và quy tắc số 9: "Include every listed scene character exactly once in `layout` " ( `llm_prompter.py:131` ). LLM hiểu nội dung ("A quỳ trước B") nên có thể đặt bố cục có ý nghĩa kể chuyện hơn heuristic.

Parser phòng thủ — LLM không đáng tin: hàm trả `None` (→ fallback heuristic cho cả cảnh) nếu:

- `layout` không phải list, rỗng, hoặc phần tử không phải dict; `anchor_x` , `anchor_y` ngoài [0,1] hoặc `scale` ngoài (0,1]; một nhân vật xuất hiện 2 lần; thiếu bất kỳ nhân vật nào ( `seen_slugs!= required_slugs` , dòng 135) — comment: "nếu không nhân vật đó sẽ biến mất âm thầm khỏi frame".

Tên LLM trả về được chuẩn hóa (bỏ dấu tiếng Việt NFKD, bỏ khoảng trắng, gạch dưới, lowercase) để khớp cả display name lẫn slug cũ.

Kết hợp hai nguồn: ngay cả khi vị trí dùng heuristic, pose/action riêng của từng nhân vật từ LLM vẫn được giữ ( `studio_pipeline.py:363-374` ). Nguồn chọn qua `studio_layout_source` ( `config.py:88` , default `"llm"` ).

Ý nghĩa tọa độ float ( `compositor.py:14-35` ): `anchor_x` là tâm ngang của nhân vật (x trái = `anchor*frame_w - layer_w/2` ); `anchor_y` là vị trí chân (y trên = `anchor*frame_h - layer_h` ). Tất cả được kẹp (clamp) để lớp không ra ngoài khung.

## 3. Vì sao chọn công nghệ này (so sánh phương án)

### 3.1. Classic vs Studio vs các phương án khác

- **Phương án:** Classic (1 prompt, 1 ảnh) · **Ưu:** Đơn giản, nhanh, ánh sáng tự nhiên liền mạch · **Nhược:** Mặt nhỏ xấu, nền không nhất quán, bố cục khó điều khiển · **Quyết định:** Mặc định
- **Phương án:** Studio (ghép lớp) · **Ưu:** Mặt to đẹp, nền tái dùng, bố cục bằng số, mỗi nhân vật có LoRA riêng · **Nhược:** Chậm hơn (N+1 lần sinh + matte + unify), vẻ dán sticker, phụ thuộc chất lượng matte · **Quyết định:** Opt-in
- **Phương án:** Regional prompting / attention couple · **Ưu:** Một lượt, chia vùng prompt · **Nhược:** Cần extension, khó ổn định trên SD1.5 + GPU 6GB · **Quyết định:** Không làm
- **Phương án:** ControlNet OpenPose / layout · **Ưu:** Điều khiển tư thế/vị trí chính xác · **Nhược:** Thêm model (~700 MB tải theo `PLAN-quality-` `speed-v2.md:306` ), VRAM sát trần ở cảnh nhiều nhân vật · **Quyết định:** `PLAN-quality-speed-v2.md` ghi là "Giai đoạn 2", chưa làm
- **Phương án:** SDXL / Pony (tự vẽ tốt hơn) · **Ưu:** Chất lượng cao hơn SD1.5 · **Nhược:** Trên 6 GB VRAM "quá chậm, phá mục tiêu tốc độ" · **Quyết định:** Loại ( `PLAN-studio-` `compositing.md:165` )
- **Phương án:** Model API cloud · **Ưu:** Chất lượng cao nhất · **Nhược:** Trái mục tiêu chạy local/miễn phí · **Quyết định:** Không dùng

### 3.2. Vì sao rembg/isnet-anime làm engine matte chính

- **Engine:** `ChromaMatter` · **Cần nền đúng màu?:** Có (bắt buộc) · **Hiểu hình dáng người?:** Không · **Tốc độ:** Rất nhanh (numpy) · **Vai trò:** Lưới an toàn cuối
- **Engine:** `GrabCutMatter` · **Cần nền đúng màu?:** Không, nhưng cần nền khác màu nhân vật · **Hiểu hình dáng người?:** Không (chỉ màu + biên) · **Tốc độ:** Nhanh (CPU, ảnh ≤384px) · **Vai trò:** Fallback thích nghi
- **Engine:** `RembgMatter` isnet- anime · **Cần nền đúng màu?:** Không · **Hiểu hình dáng người?:** Có (đã học) · **Tốc độ:** ~0.9s/ảnh CPU · **Vai trò:** Chính
- **Engine:** BiRefNet, InSPyReNet · **Cần nền đúng màu?:** Không · **Hiểu hình dáng người?:** Có, mép tốt hơn · **Tốc độ:** Nặng hơn · **Vai trò:** Không dùng (docstring `matting.py:7-8` chỉ nêu InSPyReNet là hướng thay thế)

Ghi chú: bản rembg đã cài có sẵn các session `birefnet-*` (thư mục `rembg/sessions/` ). Vì `RembgMatter` chỉ truyền `model_name` vào `new_session` , về nguyên tắc đổi sang BiRefNet chỉ là đổi `studio_matte_model` — nhưng chưa được thử trong project (chưa xác minh chất lượng/tốc độ). BiRefNet không phải model anime chuyên biệt.

Lý do quyết định (bằng chứng GPU trong `PLAN-studio-compositing.md:98-103` ): SD1.5 hiếm khi vẽ được nền chroma phẳng tuyệt đối → chroma giữ nguyên nền (coverage 1.0) hoặc ăn vào nhân vật. isnet-anime không phụ thuộc màu nền. Thiết kế interface `Matter` (abstract class, 1 method `cutout` ) cho phép đổi engine mà không sửa compositor — đúng nguyên lý Strategy pattern / Open-Closed.

### 3.3. Vì sao unify bằng img2img thay vì kỹ thuật khác

- **Cách:** Chỉ harmonize mean màu · **Nhận xét:** Đã có, nhưng không sửa được mép cắt và ánh sáng ( `PLAN-quality-speed-v2.md` : "harmonize chỉ khớp trung bình màu")
- **Cách:** Poisson blending (seamless clone) · **Nhận xét:** Hòa gradient ở mép, nhưng không thống nhất nét vẽ/phong cách
- **Cách:** Image harmonization network (ví dụ DoveNet) · **Nhận xét:** Cần thêm model, VRAM
- **Cách:** img2img low-denoise · **Nhận xét:** Dùng lại chính SD đang nạp (0 VRAM thêm), ~4 bước, thống nhất cả nét vẽ lẫn ánh sáng → chọn

## 4. Hiện thực trong code

### 4.1. Bản đồ module và phụ thuộc

- **File:** `studio/__init__.py` · **Dòng:** 8 · **Thuần (không GPU)?:** – · **Vai trò:** Docstring package
- **File:** `studio/layout_planner.py` · **Dòng:** 163 · **Thuần (không GPU)?:** Có · **Vai trò:** `build_layer_plan` , `build_layer_plan_from_llm` , `needs_classic_fallback`
- **File:** `studio/background_renderer.py` · **Dòng:** 54 · **Thuần (không GPU)?:** Có (render_fn tiêm vào) · **Vai trò:** `safe_location_id` , `BackgroundRenderer.get_or_render`
- **File:** `studio/character_renderer.py` · **Dòng:** 164 · **Thuần (không GPU)?:** Prompt builder thuần · **Vai trò:** `bg_color_name` , `build_character_prompt` , `build_character_negative_prompt` , `CharacterRenderer.render`
- **File:** `studio/matting.py` · **Dòng:** 198 · **Thuần (không GPU)?:** Chroma thuần numpy · **Vai trò:** `Matter` , `ChromaMatter` , `RembgMatter` , `GrabCutMatter` , `alpha_coverage`
- **File:** `studio/compositor.py` · **Dòng:** 125 · **Thuần (không GPU)?:** Có · **Vai trò:** `anchor_x_pos` , `anchor_y_pos` , `fit_layer_size` , `trim_transparent` , `_draw_shadow` , `composite` , `_harmonize`
- **File:** `studio/unify_pass.py` · **Dòng:** 137 · **Thuần (không GPU)?:** Không (img2img) · **Vai trò:** `clamp_strength` , `build_unify_prompt` , `unify_frame` , `resolve_unify_settings`
- **File:** `studio/studio_pipeline.py` · **Dòng:** 673 · **Thuần (không GPU)?:** `render_plan` thuần; `run_batch` nạp SD · **Vai trò:** `StudioPipeline` , `MatteQualityError` , `_face_too_small_to_detail`

Dữ liệu trung gian là hai dataclass trong `models.py:158-180` :

```
@dataclass
class CharacterLayer:
    slug: str
                                 # ngoại hình (KHÔNG mô tả nền)
    prompt: str
    action: str = ""
                                 # hành động riêng, đưa lên đầu prompt
    anchor_x: Union[str, float] = "center"
    anchor_y: Union[str, float] = "bottom"
    scale: float = 0.9
    z_order: int = 0
    flip: bool = False
    framing: str = "full"
                                 # close | medium | full
```

```
@dataclass
class LayerPlan:
    location_id: str
    background_prompt: str
    characters: List[CharacterLayer] = field(default_factory=list)
    render_mode: str = "studio"
```

Comment ở `models.py:154-156` : các dataclass này không nhúng vào `Scene` → không làm phình `state.json` ; `LayerPlan` được tính lại mỗi lần render.

Nguyên tắc thiết kế nổi bật: tiêm phụ thuộc (dependency injection). `render_plan` nhận `bg_render_fn` , `char_render_fn` , `matter` , `unify_fn` qua tham số ( `studio_pipeline.py:386-398` ). Vì vậy test có thể truyền hàm giả trả ảnh màu đơn sắc, không cần GPU/torch — ví dụ `tests/test_studio_pipeline_smoke.py` dùng `_bg_blue` (nền lam) và `_char_red_on_green` (khối đỏ trên nền lục).

4.2. `run_batch` — khởi tạo một lần cho cả batch ( `studio_pipeline.py:494-597` )

Thứ tự khởi tạo:

- 1. `load_storytelling_config()` ; `unload_local_llm()` (giải phóng VRAM Ollama). 2. Auto-train LoRA nhân vật chính nếu `studio_auto_train_leads` (code default `True` , nhưng `config.toml` cục bộ đang đặt `false` ). Nhân vật chính = xuất hiện nhiều cảnh nhất ( `_detect_lead_slugs` , tối đa `studio_auto_train_max_leads = 2` ), `studio_auto_train_steps = 700` . Idempotent: đã có LoRA khớp checkpoint thì bỏ qua. Làm trước khi nạp SD vì train sẽ release pipeline. (Chi tiết LoRA thuộc chương riêng.)

- 3. `StorytellingPipeline(self.context).warmup()` ; đặt `ip_adapter_scale` = 0.6. 4. `size = (image_width, image_height)` — `config.toml` : 768x432. 5. Tạo matter theo `studio_matte_engine` (default `"rembg"` ):

```
ChromaMatter(bg_color, threshold=0.18, feather_px=3, despill=True)
```

- `GrabCutMatter(feather_px=3)` nếu `studio_matte_adaptive_fallback` (True) Nếu rembg: `matter = RembgMatter("isnet-anime", feather_px)` , `fallback_matter = grabcut or chroma` . Nếu rembg lỗi import → `matter = chroma` , `fallback = grabcut` .

- 6. `BackgroundRenderer(<context_dir>/bg_cache, enabled=studio_bg_cache)` — cache nằm ở thư mục context của truyện ( `studio_pipeline.py:549-553` ), tức là sống qua nhiều chương. 7. `q_steps` , `q_guidance` từ `studio_render_steps` / `studio_render_guidance` (0 = dùng giá trị chung). 8. `unify_fn = make_unify_fn()` (None nếu tắt). 9. `bg_render_fn` : tắt character LoRA trước ( `pipe.set_character_lora(None)` ) rồi `generate_draft` không có face embedding — nếu quên, nền sẽ bị LoRA nhân vật "nhiễm" (test `test_run_batch_resets_lora_before_background` ).

### 4.3. Vòng lặp mỗi cảnh — cây quyết định

```
slugs = self._resolve_slugs(scene)
reason = self._unresolved_character_reason(scene, slugs)
if not reason:
    reason = needs_classic_fallback(
        len(slugs), getattr(scene, "image_prompt", ""),
        int(cfg.get("studio_fallback_max_chars", 3)),
        cfg.get("studio_fallback_interaction_tags", []))
if reason:
    logger.info(f"[Studio] Cảnh {i}: fallback classic ({reason}).")
    self._render_classic_single(pipe, scene, out_path, size, cfg)
else:
    plan = self.plan_scene(scene, slugs)
    ...
    self.render_plan(plan, size, out_path, ...)
```

( `studio_pipeline.py:605-654` , rút gọn)

Các lý do lùi về classic (mỗi lý do là một tình huống ghép lớp sẽ sai):

- **Lý do:** `unresolved_characters:...` · **Điều kiện:** LLM khai báo tên nhân vật không có trong context · **Vì sao:** Nếu bỏ qua, nhân vật sẽ biến mất khỏi frame
- **Lý do:** `person_prompt_without_resolved_character` · **Điều kiện:** Không phân giải được nhân vật nào nhưng prompt có từ chỉ người ( `_PERSON_PROMPT_RE` : girl, man, people, crowd, soldiers, monks...) · **Vì sao:** Tránh xuất frame chỉ có nền cho cảnh có người
- **Lý do:** `too_many_chars(n>3)` · **Điều kiện:** > `studio_fallback_max_chars` = 3 · **Vì sao:** Ghép nhiều lớp rối, chồng lấn
- **Lý do:** `interaction_tag:<tag>` · **Điều kiện:** Prompt chứa `hug, embrace, fight, holding hands,` `carry, kiss` · **Vì sao:** Hai lớp vẽ riêng không thể "chạm" nhau đúng
- **Lý do:** Exception bất kỳ (kể cả `MatteQualityError` ) · **Điều kiện:** `except Exception` ở dòng 655 · **Vì sao:** Studio lỗi → thử classic; classic cũng lỗi → raise `RuntimeError` , không ghi frame xám giả

Nguyên tắc "không che lỗi" được test bởi `test_double_render_failure_is_not_hidden_by_gray_frame` .

Phân giải nhân vật ( `_resolve_slugs` , dòng 109-151): ưu tiên danh sách `characters_in_scene` của LLM (giữ thứ tự), rồi tìm tên trong `image_prompt` theo ranh giới từ — có thêm khoảng trắng hai đầu `f" {phrase} "` để tránh lỗi kinh điển "Lan" khớp trong "landscape" (test `test_resolver_uses_word_boundaries_and_declared_order` ), cuối cùng thêm `primary_character` .

4.4. `plan_scene` — dựng prompt từng phần (dòng 320-381)

Với mỗi nhân vật, dict gồm:

- `prompt` = ngoại hình ( `keywords_en` sau khi bỏ tag ép chân dung như `upper body` , `looking at viewer` , `close up` , `portrait` ... — `_APPEARANCE_BLACKLIST` dòng 34-37) + style (đã bỏ tag phong cảnh: `background` , `environment` , `scenery` ,

- `landscape` , `setting` — `_CHARACTER_STYLE_BLOCKLIST` ). `action` = pose riêng từ LLM layout nếu có; nếu cảnh chỉ 1 nhân vật thì dùng `_llm_action` hoặc động từ dò trong `image_prompt` ( `_ACTION_CUE_RE` : holding, walking, sitting, casting, wielding...).

Prompt nền ( `_background_prompt` , dòng 249-292), thứ tự ưu tiên:

- 1. `_llm_background_prompt` từ LLM; 2. `location, time_of_day` từ `_semantic_meta` ; 3. lọc `image_prompt` : bỏ tag chứa từ chỉ người, tên nhân vật, tag ngoại hình.

Rồi thêm style ở đầu và luôn nối `"no humans, no people, scenery, empty background"` — để nền không tự vẽ người (nếu vẽ, Studio ghép thêm nhân vật đè lên thành "hai người").

Khóa cache nền ( `_scene_location` , dòng 239-247): `safe_location_id(location + "_" + time_of_day)` — ví dụ `ancient_scholar_courtyard_day` . Có `time_of_day` để "cùng nơi nhưng ngày/đêm khác nhau không được dùng nhầm một nền". Không có metadata → `scene_XXX` (mỗi cảnh một nền, không tái dùng). `safe_location_id` ( `background_renderer.py:16-21` ): NFKD bỏ dấu, thay ký tự lạ bằng `_` , lowercase, cắt 60 ký tự.

4.5. `CharacterRenderer` — sinh nhân vật trên nền phẳng

Prompt được xếp có chủ đích theo thứ tự ( `build_character_prompt` , `character_renderer.py:82-107` ):

```
return ", ".join(part for part in (
    pose, appearance, "solo", "1 person", framing_tags,
    "simple background", f"flat {color_name} background", "plain backdrop",
) if part)
```

- `pose` = `weight_action(action, 1.35)` → mỗi tag bọc thành `(tag:1.35)` (cú pháp trọng số A1111, xử lý bằng thư viện compel) — `style_lock.py:88-100` . Không có action → `"standing, relaxed pose"` . Vì sao action đứng đầu: CLIP text encoder của SD1.5 có cửa sổ 77 token và dùng causal mask (mỗi token chỉ "nhìn" các token trước nó), nên token đứng đầu ảnh hưởng tới embedding của mọi token sau; thực tế cộng đồng quan sát tag đầu prompt được "nghe lời" hơn. Đây là kinh nghiệm thực nghiệm, không phải quy tắc toán học — comment code viết "SD1.5 đọc token theo thứ tự và loãng dần về cuối" ( `character_renderer.py:88` ). Project encode prompt qua thư viện compel ( `image_generator.py:591-600` ), nên prompt dài hơn 77 token không bị cắt cụt mà được chia khúc, và cú pháp `(tag:1.35)` mới có tác dụng. Comment kể lại lỗi cũ: tag cứng `"front view, centered subject"` + `"standing"` "triệt tiêu mọi tư thế nên nhân vật luôn đứng trơ nhìn thẳng" (test `test_no_tag_forces_static_front_facing_pose` ). Ngoại hình cắt tối đa 14 tag. `framing_tags` : close → `"upper body, waist up, portrait framing"` ; medium → `"three-quarter body, cowboy shot"` ; full → `"full body"` . Tên màu nền: `bg_color_name` đổi hex → tên màu mà text encoder hiểu (chuyển HSV: độ bão hòa < 0.15 → `gray` / `white` ; theo hue → red/orange/.../magenta). Với `#9CA3AF` : S ≈ 0.11 → `"gray"` .

Negative prompt thêm `NEG_ADD` (dòng 23-29): `complex background, scenery, multiple people, crowd, floating ribbon,`

```
scarf, flowing cloth, magic effects, glowing particles, energy aura, sparkles, reference sheet, character sheet, text,
```

`watermark...` . Lý do: SD anime hay tự vẽ khăn/ruy băng bay, hào quang trên nền trống → matte giữ lại thành "rác" quanh nhân vật. Với close/medium, bỏ các negative `cropped, out of frame, cut off` vì cắt khung là cố ý ( `build_character_negative_prompt` ).

Kích thước sinh: `_CHAR_SIZE = (512, 768)` — khung dọc, "SD1.5 an toàn ≤768" ( `studio_pipeline.py:38-39` ). SD 1.5 huấn luyện ở 512x512; giữ một cạnh = 512 và cạnh kia ≤ 768 giảm nguy cơ lặp thân/đầu đôi.

### 4.6. Face-detail gate — không phí thời gian cho mặt 20 pixel

Face detailer (chương khác) là bước img2img vẽ lại vùng mặt. Trong Studio, trước khi chạy detailer cho một lớp, code ước lượng mặt còn bao nhiêu pixel sau khi thu nhỏ vào frame ( `_face_too_small_to_detail` , `studio_pipeline.py:65-78` ):

- px ( `_MIN_FACE_PX_TO_DETAIL` ) → bỏ detailer.

với = 0.42 (close), 0.20 (medium), 0.12 (full). Nếu

Tính với khung 432 px:

- **shot:** wide · **scale:** 0.45 · **framing:** 0.45 x 432 x 0.12 ≈ 23.3 px full (0.12) · **Detailer?:** Bỏ
- **shot:** medium · **scale:** 0.8 · **framing:** medium (0.20) 0.8 x 432 x 0.20 ≈ 69 px · **Detailer?:** Chạy
- **shot:** close · **scale:** 1.0 · **framing:** 432 x 0.42 ≈ 181 px close (0.42) · **Detailer?:** Chạy

Test `tests/test_studio_face_detail_gate.py` kiểm đúng 3 trường hợp này, thêm trường hợp "khung cao hơn cứu được wide shot" và "scale lỗi không làm bỏ detailer". Ngoài ra, nhân vật đã có LoRA cũng bỏ detailer ( `studio_lora_skip_detailer = True` , comment config: tiết kiệm ~40% thời gian).

Bootstrap ảnh ref ( `_try_bootstrap_ref` , dòng 213-237): nếu nhân vật chưa có ảnh tham chiếu IP-Adapter, lấy mặt lớn nhất ( `detect_faces` trả mặt lớn nhất trước; cạnh ngắn ≥ 110 px) từ lớp nhân vật đầu tiên, nới hộp `pad_ratio=0.7` , nếu crop có cạnh < 512 thì resize về đúng 512x512 (có thể lệch tỉ lệ), rồi lưu làm ref cho các cảnh sau — tận dụng việc Studio sinh mặt to.

4.7. `render_plan` — lõi ghép một cảnh (dòng 386-425)

```
bg = bg_renderer.get_or_render(plan.location_id, plan.background_prompt, size, bg_render_fn)
layers = []
for layer in plan.characters:
                                         # RGB trên nền phẳng
    raw = char_render_fn(layer)
    rgba = matter.cutout(raw)
                                         # tách nền → RGBA
    cov = alpha_coverage(rgba)
    if ((cov < _MIN_COVERAGE or cov > _MAX_COVERAGE)
            and fallback_matter is not None):
        rgba = fallback_matter.cutout(raw)
        cov = alpha_coverage(rgba)
    if cov < _MIN_COVERAGE or cov > _MAX_COVERAGE:
        raise MatteQualityError(layer.slug, cov)
    layers.append((rgba, layer))
frame = composite(bg, layers, harmonize=harmonize, shadow_opacity=shadow_opacity)
if unify_fn is not None and layers:
    frame = unify_fn(frame, plan.background_prompt)
frame.save(out_path)
```

Cổng chất lượng matte (alpha coverage gate):

( `alpha_coverage` , `matting.py:193-198` ; ngưỡng đục 16/255). Hợp lệ khi 0.05 ≤ coverage ≤ 0.95 ( `_MIN_COVERAGE` , `_MAX_COVERAGE` , dòng 31-32). Logic: một nhân vật trong khung 512x768 phải chiếm một phần hợp lý. Coverage ≈ 1.0 → key không cắt được gì (nền còn nguyên); coverage ≈ 0 → key ăn mất nhân vật. Đây là kiểm định rẻ, không cần model, nhưng bắt được hai kiểu hỏng phổ biến nhất. Chuỗi xử lý: engine chính → fallback matter → raise → classic.

Ví dụ bằng chứng thực ( `PLAN-studio-compositing.md:72-74` ): trên RTX 3060 6GB, "chroma coverage 1.0 được nhận diện là hỏng, GrabCut thích nghi cắt được chủ thể và compositor xuất frame Studio, không rơi sang classic".

4.8. `composite` — toán đặt lớp ( `compositor.py:79-111` )

Cho từng lớp, theo z_order tăng dần (vẽ sau = đứng trước — "thuật toán họa sĩ", painter's algorithm):

- 1. `trim_transparent` : cắt lề alpha trống theo bounding box của alpha. Tại sao quan trọng: nếu không cắt, `scale` sẽ áp vào cả canvas 512x768 gồm khoảng trống → nhân vật nhỏ hơn dự kiến và lệch khỏi mặt đất (test `test_trim_transparent_makes_scale_apply_to_visible_character` ). 2. `flip` nếu cần ( `ImageOps.mirror` ). 3. `fit_layer_size` : chiều cao đích = `round(scale * frame_h)` kẹp ≤ `frame_h` ; chiều rộng giữ tỉ lệ. Resize bằng LANCZOS (bộ lọc sinc có cửa sổ — giữ nét khi thu nhỏ, ít răng cưa). 4. Lớp rộng hơn khung → crop giữa. 5. `_harmonize` (nếu bật — mặc định `harmonize=True` ).

- 6. Tính `x, y` từ anchor (có clamp). 7. Vẽ bóng nếu `shadow_opacity > 0` . 8. `canvas.alpha_composite(c, dest=(x, y))` — phép over.

Ví dụ số (medium, 1 nhân vật, khung 768x432): nhân vật sau trim giả sử 300x700 → chiều cao 0.8 x 432 ≈ 346, rộng ≈ 300 x 346/700 ≈ 148 → x = (768-148)//2 = 310 ( `center` ), y = 432 - 346 = 86 ( `bottom` ).

4.9. `BackgroundRenderer.get_or_render` — cache đơn giản trên đĩa

```
path = self.cache_path(location_id) if location_id else ""
if self.enabled and path and os.path.exists(path):
    return Image.open(path).convert("RGB")
img = render_fn(prompt, size).convert("RGB")
if self.enabled and path:
    img.save(path)
return img
```

( `background_renderer.py:38-54` , rút gọn)

Đây là memoization theo khóa `location_id` lưu PNG. Cache lỗi đọc → render lại; lưu lỗi → chỉ warning. Test `test_studio_bg_cache.py` đếm số lần render_fn được gọi: cùng location → 1 lần; khác location → 2 lần; tắt cache → luôn render.

Bằng chứng thực: batch 4 cảnh / 2 location / 1 nhân vật = 63.5s, "bg-cache tái dùng đúng" ( `PLAN-studio-compositing.md:110-` `111` ).

### 4.10. Bảng tổng hợp tham số thật

- **Khóa config ( `app/config.py` ):** `render_mode` · **Default code:** `classic` · **`config.toml` cục bộ:** `auto` (→ thực tế classic) · **Dùng ở:** `orchestrator.py:354`
- **Khóa config ( `app/config.py` ):** `studio_bg_cache` · **Default code:** True · **`config.toml` cục bộ:** true · **Dùng ở:** `run_batch`
- **Khóa config ( `app/config.py` ):** `studio_layout_source` · **Default code:** `llm` (nhưng `plan_scene` dùng `"heuristic"` nếu khóa vắng, `studio_pipeline.py:349` ) · **`config.toml` cục bộ:** `llm` · **Dùng ở:** `plan_scene`
- **Khóa config ( `app/config.py` ):** `studio_matte_engine` · **Default code:** `rembg` · **`config.toml` cục bộ:** `rembg` · **Dùng ở:** `run_batch`
- **Khóa config ( `app/config.py` ):** `studio_matte_model` · **Default code:** `isnet-anime` · **`config.toml` cục bộ:** `isnet-anime` · **Dùng ở:** `RembgMatter`
- **Khóa config ( `app/config.py` ):** `studio_matte_bg_color` · **Default code:** `#9CA3AF` · **`config.toml` cục bộ:** `#9CA3AF` · **Dùng ở:** prompt + chroma
- **Khóa config ( `app/config.py` ):** `studio_matte_threshold` · **Default code:** 0.18 · **`config.toml` cục bộ:** 0.18 · **Dùng ở:** `ChromaMatter`
- **Khóa config ( `app/config.py` ):** `studio_matte_feather_px` · **Default code:** 3 · **`config.toml` cục bộ:** 3 · **Dùng ở:** cả 3 matter
- **Khóa config ( `app/config.py` ):** `studio_matte_despill` · **Default code:** True · **`config.toml` cục bộ:** true · **Dùng ở:** `ChromaMatter`
- **Khóa config ( `app/config.py` ):** `studio_matte_adaptive_fallback` · **Default code:** True · **`config.toml` cục bộ:** true · **Dùng ở:** `GrabCutMatter`
- **Khóa config ( `app/config.py` ):** `studio_char_use_detailer` / `_ip_adapter` · **Default code:** True / True · **`config.toml` cục bộ:** true / true · **Dùng ở:** `char_render_fn`
- **Khóa config ( `app/config.py` ):** `studio_fallback_max_chars` · **Default code:** 3 · **`config.toml` cục bộ:** 3 · **Dùng ở:** `needs_classic_fallback`
- **Khóa config ( `app/config.py` ):** `studio_fallback_interaction_tags` · **Default code:** hug, embrace, fight, holding hands, carry, kiss · **`config.toml` cục bộ:** như code · **Dùng ở:** như trên
- **Khóa config ( `app/config.py` ):** `studio_shadow_opacity` · **Default code:** 0.0 · **`config.toml` cục bộ:** 0.0 · **Dùng ở:** `composite`
- **Khóa config ( `app/config.py` ):** `studio_auto_train_leads` · **Default code:** True · **`config.toml` cục bộ:** false · **Dùng ở:** `run_batch`
- **Khóa config ( `app/config.py` ):** `studio_lora_skip_detailer` · **Default code:** True · **`config.toml` cục bộ:** true · **Dùng ở:** `char_render_fn`
- **Khóa config ( `app/config.py` ):** `studio_render_steps` / `_guidance` · **Default code:** 0 / 0.0 · **`config.toml` cục bộ:** 0 / 0.0 · **Dùng ở:** ghi đè chất lượng
- **Khóa config ( `app/config.py` ):** `studio_action_weight` · **Default code:** 1.35 · **`config.toml` cục bộ:** 1.35 · **Dùng ở:** trọng số pose
- **Khóa config ( `app/config.py` ):** `studio_unify_pass` / `_strength` / `_steps` / `_guidance` · **Default code:** True / 0.28 / 16 / 5.0 · **`config.toml` cục bộ:** như code · **Dùng ở:** `unify_pass`
- **Khóa config ( `app/config.py` ):** `ip_adapter_scale` · **Default code:** 0.6 ( `config.py:67` ) · **`config.toml` cục bộ:** 0.6 · **Dùng ở:** `run_batch` , khôi phục sau unify

Lưu ý nhỏ về `docs/PLAN-studio-compositing.md:48-60` : bảng config ở đó còn ghi `studio_matte_bg_color = "#00B140"` (bản cũ trước quality boost); code hiện tại là `#9CA3AF` . Docstring đầu `matting.py` và `studio_pipeline.py` cũng còn mô tả "chroma- key" như cách chính — là mô tả lịch sử, code thật dùng rembg làm mặc định.

### 4.11. Kiểm thử

11 file, 66 hàm test, tất cả GPU-free (nhờ tiêm phụ thuộc và import lazy):

- **File:** `test_studio_layout.py` · **Kiểm cái gì:** Bảng `_SHOT_DEFAULTS` , phân bố anchor, fallback quá nhiều người / tag tương tác
- **File:** `test_studio_llm_layout.py` · **Kiểm cái gì:** Parse layout LLM hợp lệ/hỏng/thiếu nhân vật, chuẩn hóa tên, prompter đọc trường layout
- **File:** `test_studio_matting.py` · **Kiểm cái gì:** hex→RGB, nền → trong suốt, FG → đục, despill xanh và magenta, GrabCut trên nền không phải chroma
- **File:** `test_studio_compositor.py` · **Kiểm cái gì:** Toán anchor, giữ tỉ lệ, đặt bottom-center, z-order, trim
- **File:** `test_studio_shadow.py` · **Kiểm cái gì:** Bóng mặc định tắt, bóng xuất hiện đúng dưới chân, harmonize giữ alpha
- **File:** `test_studio_bg_cache.py` · **Kiểm cái gì:** Đếm số lần render nền
- **File:** `test_studio_character_renderer.py` · **Kiểm cái gì:** Action đứng đầu có trọng số, không còn tag ép tư thế, framing, negative cho close/medium
- **File:** `test_studio_face_detail_gate.py` · **Kiểm cái gì:** Cổng mặt nhỏ
- **File:** `test_studio_unify_pass.py` · **Kiểm cái gì:** Trần strength, công tắc tắt, prompt không nhắc nhân vật, unify chỉ chạy khi có lớp
- **File:** `test_studio_pipeline_smoke.py` · **Kiểm cái gì:** `render_plan` với ảnh giả, cổng coverage (tham số hóa), fallback matter
- **File:** `test_studio_runtime.py` · **Kiểm cái gì:** Resolver, fallback classic, reset LoRA trước nền, lỗi kép không bị che, orchestrator lưu state

## 5. Sơ đồ luồng

### 5.1. Classic vs Studio ở Trạm 2

### 5.2. Xử lý một cảnh trong Studio

### 5.3. Trình tự gọi (sequence) cho một cảnh 1 nhân vật

## 6. Hạn chế và hướng phát triển

### 6.1. Hạn chế đã có bằng chứng

1. Không hợp phong cách thủy mặc (mặc định của project). isnet-anime không nhận ra hình mực đơn sắc → coverage 0.003. Và sâu hơn: Studio sinh ra để bù điểm yếu SD1.5 (mặt nhỏ, tay hỏng) mà phong cách mực đã tự che. Kết luận trong `docs/PLAN-quality-speed-v2.md` : `render_mode` quay về `"classic"` . Đây là câu trả lời mạnh khi bị hỏi "làm ra rồi sao không dùng?" — thực nghiệm dẫn dắt quyết định. 2. Vẻ "dán sticker" chưa hết hoàn toàn. Harmonize chỉ dịch mean; bóng mặc định tắt; unify pass giảm nhưng không mô phỏng hướng sáng thật. Vẫn còn fringe mép ( `PLAN-studio-compositing.md:115-116` ). 3. Không có tương tác vật lý. Hai lớp vẽ riêng không thể ôm, nắm tay, đánh nhau → phải fallback classic theo danh sách tag. Danh sách tag là so khớp chuỗi con đơn giản ( `tag.lower() in low` ), có thể bỏ sót từ đồng nghĩa ("grab", "punch"). 4. Chậm hơn classic: N nhân vật = N+1 lần sinh (trừ khi cache nền hit) + matte + unify. Lần đầu của truyện còn có thể thêm auto-train LoRA ~6 phút/nhân vật ( `PLAN-studio-compositing.md:136-137` ). 5. Cache nền chỉ khóa theo `location_id` . Không đưa checkpoint, style, prompt hay kích thước vào khóa. Đổi phong cách giữa chừng có thể tái dùng nền cũ sai style; ảnh nền khác kích thước chỉ được `resize` ( `studio_pipeline.py:400-401` ). Cache nằm ở cấp truyện nên hiệu ứng này kéo sang các chương sau. 6. Phối cảnh không được mô hình hóa. Layout chỉ có anchor/scale 2D; không có đường chân trời, điểm tụ → nhân vật có thể "đứng trên tường" nếu nền là cảnh nhìn từ trên cao. 7. Coverage gate chỉ bắt lỗi thô. Một mask cắt mất cánh tay nhưng coverage vẫn 30% sẽ lọt. 8. Nhãn "auto" trên orchestrator mô tả chọn theo GPU nhưng code hiện tại không làm vậy (mục 1.2). 9. Mới có smoke test GPU. `PLAN-studio-compositing.md:79-81` : "Đây là smoke một cảnh, chưa phải nghiệm thu trọn 82 cảnh". Definition of Done còn các ô chưa tick (dòng 173-176). 10. Giá trị `studio_unify_strength = 0.28` chưa được chốt bằng mắt trên GPU. `PLAN-quality-speed-v2.md:340,357` còn để mở câu hỏi "0.28 có phải điểm rơi đúng không" và ô việc "chốt `studio_unify_strength` " chưa tick. Nói với hội đồng: 0.28 nằm trong khoảng 0.25-0.32 mà docstring `unify_pass.py` nêu là thông lệ, và có trần cứng 0.45.

11. Mô tả trên UI còn lạc hậu: help-text ở `webui/index.html:548` vẫn viết "tách nền chroma", trong khi engine mặc định đã là rembg.

### 6.2. Hướng phát triển

- **Hướng:** ControlNet OpenPose cho lớp nhân vật · **Giải quyết:** Tư thế chính xác theo LLM · **Ghi chú:** Đã ghi là Giai đoạn 2 trong `PLAN-` `quality-speed-v2.md`
- **Hướng:** ControlNet depth / normal cho nền · **Giải quyết:** Ánh sáng và phối cảnh nhất quán · **Ghi chú:** Tốn VRAM
- **Hướng:** Matting model tốt hơn (BiRefNet, InSPyReNet) hoặc bật alpha matting với trimap của rembg/pymatting · **Giải quyết:** Mép tóc mềm thật · **Ghi chú:** `Matter` interface cho phép thay không sửa compositor
- **Hướng:** Fine-tune segmentation trên tranh mực · **Giải quyết:** Mở Studio cho phong cách thủy mặc · **Ghi chú:** Cần dataset
- **Hướng:** Khóa cache = hash(location, style, checkpoint, size) · **Giải quyết:** Tránh nền sai style · **Ghi chú:** Thay đổi nhỏ trong `_scene_location`
- **Hướng:** Inpainting vùng mép thay vì img2img toàn khung · **Giải quyết:** Hòa mép mà không đụng phần còn lại
- **Hướng:** Hiện thực đúng `auto` (dò CUDA → studio) · **Giải quyết:** Khớp mô tả UI
- **Hướng:** Layer animation (parallax, nhân vật di chuyển trên nền) · **Giải quyết:** Tận dụng việc đã có lớp tách rời để làm video động hơn Ken Burns · **Ghi chú:** Lợi thế độc nhất của kiến trúc lớp

Điểm cuối rất đáng nói với hội đồng: vì đã có lớp nền và lớp nhân vật tách rời, Studio mở đường cho hoạt hình 2.5D (parallax, nhân vật trượt, nhân vật khác nhau vào/ra khung) — điều classic không thể làm vì nhân vật "dính" vào nền.

## Câu hỏi hội đồng có thể hỏi

### 1. Tại sao phải tách nhân vật và nền rồi ghép, sao không để Stable Diffusion vẽ một lần?

SD 1.5 làm việc trên latent nén 8 lần; mặt nhân vật trong cảnh rộng chỉ còn vài ô latent nên méo. Ghép lớp cho phép sinh nhân vật ở khung 512x768 ( `_CHAR_SIZE` ) mặt to, nền được cache theo địa điểm để nhất quán giữa các cảnh, và bố cục được đặt bằng số trong `LayerPlan` thay vì mong SD hiểu "đứng bên trái". Cái giá là vẻ dán sticker, được giảm bằng harmonize, shadow và unify pass.

### 2. Matting khác segmentation thế nào? Project dùng cái nào?

Segmentation gán nhãn rời rạc (thuộc/không thuộc vật thể); matting ước lượng α liên tục [0,1] theo phương trình C = αF + (1−α)B, cần cho sợi tóc bán trong suốt. Project dùng segmentation bằng isnet-anime (qua rembg) rồi feather Gaussian 3 px để xấp xỉ matting — nhanh, chạy CPU, đủ tốt với tranh anime nét đậm, nhưng không phải matting đúng nghĩa.

### 3. Vì sao matting là bài toán khó?

Mỗi pixel có 3 phương trình (R,G,B) nhưng 7 ẩn (F 3 kênh, B 3 kênh, α) → ill-posed. Phải thêm giả thiết: chroma-key biết trước B; GrabCut giả thiết viền là nền và màu theo GMM; mạng nơ-ron dùng tri thức học từ dữ liệu về hình dáng nhân vật.

### 4. Tại sao bỏ chroma-key làm engine chính?

Chroma-key chỉ đúng khi nền thật sự phẳng đúng màu, mà SD 1.5 không đảm bảo "flat green background". Thực nghiệm trên RTX 3060 ghi nhận coverage = 1.0 (không cắt được gì). isnet-anime nhận diện hình dáng nhân vật nên không phụ thuộc màu nền. Chroma và GrabCut được giữ làm lưới an toàn. Nền sinh nhân vật đổi sang xám `#9CA3AF` để không bị ám xanh lên áo.

### 5. Làm sao biết matte bị hỏng?

Hàm `alpha_coverage` đếm tỉ lệ pixel có α > 16/255. Hợp lệ khi nằm trong [0.05, 0.95]. Dưới 5% là key ăn mất nhân vật, trên 95% là key không tách được nền. Hỏng thì thử fallback matter (GrabCut), vẫn hỏng thì raise `MatteQualityError` và render classic cảnh đó.

### 6. GrabCut hoạt động thế nào?

Mô hình màu nền và tiền cảnh bằng hai GMM 5 thành phần (65 tham số mỗi model — đúng kích thước mảng `np.zeros((1, 65))` trong code), định nghĩa năng lượng gồm chi phí màu và chi phí biên, giải bằng min- cut, lặp 5 lần. Code khởi tạo bằng hình chữ nhật chừa viền 1 px, phân tích ở ảnh thu nhỏ ≤384 px, rồi morphology open/close để khử đốm.

### 7. Công thức ghép lớp là gì, code thực hiện ở đâu?

Toán tử "over" của Porter–Duff: C = αF + (1−α)B. `compositor.composite` chuyển nền sang RGBA (α=1), với mỗi lớp theo z_order tăng dần thì trim, scale LANCZOS, harmonize, tính anchor rồi gọi `canvas.alpha_composite(c, dest=(x, y))` .

### 8. Unify pass là gì, sao không làm hỏng bố cục đã ghép?

Đó là img2img với strength 0.28 trên toàn frame: thêm nhiễu tới 28% lịch rồi khử nhiễu 4 bước (16 × 0.28). Diffusion quyết định bố cục ở các bước nhiễu cao và chi tiết bề mặt ở bước nhiễu thấp, nên strength thấp chỉ vẽ lại bề mặt: ánh sáng, nét, mép cắt. Có trần cứng 0.45 ( `MAX_SAFE_STRENGTH` ). Prompt unify không nhắc nhân vật để tránh sinh thêm người, và IP-Adapter được đặt scale 0 trong lúc chạy.

### 9. Unify pass có tốn thêm VRAM không?

Không. `_get_img2img` tạo `AutoPipelineForImage2Image.from_pipe(pipeline._pipe)` , dùng chung U-Net, VAE, text encoder với pipeline text2img đang nạp. Mọi lỗi đều trả frame gốc.

### 10. Layout do ai quyết định? Nếu LLM trả sai thì sao?

Mặc định `studio_layout_source = "llm"` : LLM trả mảng `layout` (anchor_x, anchor_y, scale, z, pose). Parser `build_layer_plan_from_llm` trả None nếu JSON sai kiểu, giá trị ngoài [0,1], trùng nhân vật hoặc thiếu nhân vật → rơi về heuristic `build_layer_plan` (close: scale 1.0 giữa; medium 0.8 đáy; wide 0.45 đáy; 1 người giữa, 2 người trái-phải). Pose riêng của LLM vẫn được giữ.

### 11. Background cache hoạt động thế nào? Có rủi ro gì?

Khóa là `safe_location_id(location + "_" + time_of_day)` từ metadata semantic splitter, lưu PNG trong `<context_dir>/bg_cache` — tồn tại xuyên chương của truyện. Có `time_of_day` để ngày và đêm không dùng chung nền. Rủi ro: khóa không chứa style/checkpoint nên đổi phong cách có thể dùng lại nền cũ.

### 12. Khi nào Studio tự lùi về classic?

Khi tên nhân vật LLM khai báo không có trong context; prompt có người nhưng không phân giải được nhân vật; hơn 3 nhân vật; prompt có tag tương tác (hug, embrace, fight, holding hands, carry, kiss); matte không qua cổng coverage; hoặc bất kỳ exception nào. Nếu cả classic cũng lỗi thì raise lỗi thật, không ghi frame xám giả.

### 13. Face-detail gate là gì?

Trước khi chạy face detailer cho một lớp, code ước lượng chiều cao mặt trong frame cuối = scale × chiều cao khung × tỉ lệ mặt theo framing (0.42/0.20/0.12). Dưới 30 px thì bỏ. Với khung 432 px, wide shot cho ~23 px nên bỏ; medium ~69 px và close ~181 px thì chạy. Nhân vật đã có LoRA cũng bỏ detailer.

### 14. Vì sao Studio không phải mặc định?

Thực nghiệm với phong cách mặc định thủy mặc: isnet-anime chỉ giữ được 0.3% pixel (coverage 0.003) vì không nhận ra hình mực đơn sắc; đồng thời phong cách mực đã che đi điểm yếu mặt/tay của SD1.5 mà Studio sinh ra để khắc phục. Nên `render_mode` mặc định `classic` , Studio để opt-in cho phong cách anime màu.

### 15. Kiểm thử phần này thế nào khi không có GPU?

`render_plan` nhận hàm render và matter qua tham số (dependency injection), SD và rembg import lazy. 66 test ở 11 file `test_studio_*.py` dùng ảnh tổng hợp (khối đỏ trên nền lục, nền lam) để kiểm toán anchor, z-order, cache, cổng coverage, fallback, không cần GPU.

### 16. Sao không dùng model tách nền mạnh hơn như BiRefNet hay SAM?

isnet-anime là model chuyên cho nhân vật anime, chạy CPU ~0.9s/ảnh 512x768 nên không tranh VRAM với Stable Diffusion trên GPU 6 GB. BiRefNet tổng quát và nặng hơn; SAM cần prompt điểm/hộp và cũng nặng. Nhờ interface `Matter` và việc `RembgMatter` nhận `model_name` , đổi model chỉ là đổi cấu hình `studio_matte_model` — nhưng em chưa đo các model khác, nên đó là hướng phát triển.

### 17. Mặt nạ cuối cùng có "mềm" thật không?

Không hoàn toàn. `post_process_mask=True` của rembg làm sạch mặt nạ bằng morphology rồi cắt ngưỡng nên mặt nạ gần như nhị phân; độ mềm mép đến từ bước `GaussianBlur` 3 px do code tự thêm, và từ unify pass vẽ lại mép. Vì vậy đây là segmentation + feather, không phải alpha matting có trimap; tóc mảnh vẫn có thể còn fringe.

## Tóm tắt 1 phút

"Ở bước sinh ảnh, ngoài chế độ classic vẽ cả cảnh trong một lượt, em làm thêm chế độ Studio theo cách xưởng hoạt hình 2D: vẽ phông nền riêng, vẽ từng nhân vật riêng rồi ghép. Lý do là Stable Diffusion 1.5 nén ảnh 8 lần vào latent, nên mặt nhân vật trong cảnh rộng chỉ còn vài ô và bị méo; sinh riêng nhân vật ở khung 512 nhân 768 thì mặt to và đẹp, còn nền được cache theo địa điểm và thời điểm trong ngày để các cảnh cùng nơi nhất quán. Bố cục do LLM đề xuất, nếu sai thì dùng luật theo cỡ cảnh. Để tách nhân vật, em dùng model isnet-anime qua thư viện rembg, có GrabCut và chroma-key làm dự phòng, và một cổng kiểm tra tỉ lệ pixel giữ lại từ 5 đến 95 phần trăm. Ghép theo công thức alpha C bằng alpha F cộng một trừ alpha B, sau đó chạy img2img cường độ 0.28, tức khoảng 4 bước, để hòa ánh sáng mà không đổi bố cục. Cảnh đông người hay có tương tác vật lý

thì tự lùi về classic. Thực nghiệm cho thấy Studio không hợp phong cách thủy mặc mặc định, nên em để nó là tùy chọn — đây là quyết định dựa trên số liệu đo được."
