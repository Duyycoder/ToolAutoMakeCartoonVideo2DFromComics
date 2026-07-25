# Nghiên cứu: nâng chất lượng + tốc độ sinh video

> **Nhánh:** `feat/studio-quality-boost`
> **Ngày:** 2026-07-24
> **Phần cứng đích:** RTX 3060 Laptop **6 GB** VRAM (driver 566.07) — mọi phương án
> dưới đây đều bị ràng buộc bởi con số này.
> **Câu hỏi được đặt ra:** (1) chất lượng hình chưa chấp nhận được; (2) có fine-tune
> được cho một thể loại cố định không, kiểu thủy mặc; (3) tỷ lệ ảnh lỗi còn cao;
> (4) chưa lột tả được hành động nhân vật.

---

## 0. ĐÍNH CHÍNH sau thực nghiệm GPU 24/07 chiều

Bản nghiên cứu bên dưới được viết TRƯỚC khi chạy GPU. Thực nghiệm buổi chiều lật
lại hai kết luận chính của nó. Đọc mục này trước.

**Nguyên nhân số 1 của "chất lượng chưa chấp nhận được" là `guidance_scale`, không
phải style hay compositing.** `app/config.py` để mặc định `1.5` trong khi
`config.toml.example` ghi `5.0`. Với 8 bước + Hyper-SD CFG-lora, guidance 1.5 khiến
model gần như bỏ qua prompt và trả về mảng texture trừu tượng. Chuỗi loại trừ:
sweep trọng số LoRA (weight 0.00 hỏng y hệt 0.70) → bỏ dần tag style tới rỗng (vẫn
hỏng) → A/B guidance (1.5 hỏng, ≥3.5 ra nhân vật rõ ràng, đúng tư thế hành động).
Lỗi này ẩn lâu vì **ảnh nền vẫn trông ổn** — chỉ ảnh nhân vật có hành động mới lộ.
Đã sửa mặc định trong `config.py`.

**Studio compositing phải TẮT với phong cách thủy mặc.** rembg (isnet-anime) được
train trên nhân vật anime màu; nó không nhận ra hình mực đơn sắc → alpha coverage
**0.003**, lớp nhân vật rỗng, frame chỉ còn nền. Sâu hơn: Studio sinh ra để bù
điểm yếu SD1.5 (mặt nhỏ xấu, tay hỏng) mà phong cách mực đã che chính những điểm
yếu đó — giữ Studio là trả giá cho một vấn đề không còn tồn tại. `render_mode`
quay về `"classic"`.

**Style LoRA vẫn có giá trị, nhưng ở vai trò nhỏ hơn dự kiến.** Nó đóng góp chất
liệu (biến vệt mực cứng kiểu anime thành chuyển sắc loang thật), không đóng góp
cách dựng hình. Vùng dùng được 0.40-0.55; ≥0.70 tan chi tiết bàn tay/bàn chân.
Chốt **0.45**. Dataset 46 ảnh gần như toàn sơn thủy/trúc/mai, rất ít tranh nhân
vật — muốn LoRA mạnh hơn thì phải bổ sung tranh người rồi train lại.

**Hai lỗi tự gây trong lần triển khai này, đã sửa:**
`warmup()` đọc config đè lên mọi lời gọi `set_style_lora()` runtime (làm sweep đầu
tiên vô hiệu — 5 mức trọng số cho ra 5 ảnh giống hệt nhau); và trainer LoRA nạp
UNet fp32 chạm trần 6GB gây tràn sang shared memory + paging (không crash, chỉ
chậm hàng chục lần — rất dễ chẩn đoán nhầm thành "máy yếu").

**Nghiệm thu end-to-end đã chạy** (`scripts/e2e_chapter_probe.py`): Tây Du Ký hồi 1
nguyên tác Hán (Project Gutenberg, public domain) → dịch Việt qua Gemini cục bộ →
tách 8 cảnh ngữ nghĩa → sinh prompt có action → 8 frame. Tổng ~3 phút LLM + 85 giây
ảnh. Phong cách đồng nhất cả 8 frame; nội dung khớp đúng hồi 1. **Chưa chạy TTS và
ghép video.** Hồi 1 thiên về cảnh (6/8 là wide shot) nên nhánh nhân vật + hành động
mới chỉ được thử nhẹ — cần một hồi nhiều đối thoại để kết luận.

## 1. Kết luận ngắn

| Câu hỏi | Trả lời |
|---|---|
| Fine-tune cho 1 thể loại cố định? | **Được, và đây là đòn bẩy lớn nhất.** LoRA phong cách SD1.5, 40-80 ảnh, ~40 phút train trên chính GPU 6 GB này. Đã dựng sẵn hạ tầng ở Giai đoạn 0. |
| Vì sao ảnh mỗi frame một kiểu? | Không phải do seed. **Mỗi prompt đang mang ba tuyên bố phong cách đánh nhau**, và LLM được tự viết lại tag style ở từng cảnh. Đã sửa. |
| Vì sao nhân vật không có hành động? | Prompt sinh nhân vật chèn cứng `front view, centered subject, standing` — ba tag này triệt tiêu mọi tư thế mà LLM mô tả. Đã sửa; muốn dứt điểm cần ControlNet OpenPose (Giai đoạn 2). |
| Vì sao ảnh trông như dán sticker? | Studio vẽ nhân vật và nền riêng rồi ghép, `harmonize` chỉ khớp **trung bình màu**. Cần một lượt img2img hòa trộn cả frame. Đã làm. |
| Nâng chất lượng có phải hy sinh tốc độ? | **Không, phần lớn là đổi chỗ ngân sách.** Pipeline đang tiêu thời gian để cứu một ảnh gốc tồi (face detailer, upscale, matte) thay vì làm ảnh gốc đúng ngay từ đầu. |

Nguyên tắc xuyên suốt bản nghiên cứu này: **SD1.5 ở 6 GB không giỏi lên. Nhưng nó
rất giỏi lặp lại một thứ nó đã được dạy.** Toàn bộ chiến lược là thu hẹp không
gian mà model được phép sáng tác — khóa phong cách, khóa tư thế, khóa bố cục —
thay vì đòi nó vẽ đẹp tự do.

---

## 2. Chẩn đoán, kèm bằng chứng

Bằng chứng lấy từ frame thật đã render: `storage/quicktest/batch/scene_00*.png`.

### 2.1. Phong cách chưa bao giờ được khóa

Một prompt sinh ra ở Trạm 1 mang **ba** tuyên bố phong cách, viết bởi ba nơi khác nhau:

| Nguồn | Nội dung | Ý muốn |
|---|---|---|
| `image_generator.generate_draft` | `masterpiece, best quality, highres` (chèn cứng đầu MỌI prompt) | chất lượng chung |
| `llm_prompter._build_system_prompt` | `(highly detailed background, cinematic lighting, Anything V5:1.1)` (chèn cứng) | **nhiều chi tiết, ánh sáng điện ảnh** |
| file style của truyện, vd `storyboard.txt` | `flat vector illustration, minimal shading, limited color palette` | **phẳng, ít chi tiết, ít sắc độ** |

Hai dòng cuối **mâu thuẫn trực tiếp**. Model nhận cả hai và mỗi seed lại nghiêng
về một bên → mỗi frame một kiểu. Tệ hơn: LLM còn được lệnh tự viết thêm tag style
ở từng cảnh (rule cũ số 3 và 5 trong system prompt), nên phương sai được cộng thêm
một tầng nữa.

Chuỗi `masterpiece, best quality` không trọng số lại bị đặt **trước**
`(masterpiece, best quality:1.2)` của style preset — vừa lặp, vừa vô hiệu hoá
chính trọng số mà preset đặt ra, vừa ăn mất những token đầu prompt vốn có ảnh
hưởng lớn nhất với CLIP.

### 2.2. Kiến trúc Studio về mặt cấu trúc không thể diễn tả hành động

`character_renderer.build_character_prompt` (bản cũ) ráp prompt như sau:

```
<ngoại hình>, solo, 1 person, <framing>, front view, centered subject,
simple background, flat gray background, plain backdrop
```

với `framing="full"` → `full body, standing`.

Nghĩa là mọi nhân vật đều được vẽ **đứng yên, nhìn thẳng, đặt giữa khung, trên nền
trơn**. Hành động mà LLM mô tả được planner nhét vào *trước* phần ngoại hình, rồi
bị cắt còn 14 tag đầu, rồi bị bốn tag chèn cứng phía sau kéo ngược về tư thế mặc
định. Đây là lý do gốc của "chưa có gì lột tả được hành động nhân vật".

Ràng buộc sâu hơn: nhân vật được vẽ **cô lập** nên về nguyên tắc không thể tương
tác với bối cảnh (không tựa được vào bàn có sẵn trong nền, không bước lên bậc thềm
trong nền) và cảnh có tương tác vật lý bị `needs_classic_fallback` đẩy hẳn sang
classic.

### 2.3. Ghép lớp lộ vết

`compositor._harmonize` chỉ gọi `_match_color_mean_only` — dịch trung bình màu của
lớp về phía nền. Nó không xử lý được: hướng sáng, độ tương phản, nhiệt màu cục bộ,
bóng đổ tiếp xúc, độ nhoè khí quyển, và độ sắc của mép matte. Frame
`scene_003.png` cho thấy đúng bốn thứ đó: nhân vật sáng phẳng đứng trước phố cổ
nắng xiên, tóc dính vào chiếc đèn lồng phía sau, không có bóng chân.

`studio_shadow_opacity` mặc định `0.0` nên bóng chân cũng đang tắt.

### 2.4. Ngân sách thời gian đặt sai chỗ

Đo thực tế đã ghi trong `PLAN-studio-compositing.md`: `run_batch` 4 cảnh / 2
location / 1 nhân vật = **63.5 s**, tức ~16 s/cảnh.

Ngân sách đó đang chia như sau (ước lượng theo cấu hình mặc định):

| Hạng mục | Chi phí | Đóng góp vào chất lượng |
|---|---|---|
| Sinh nền (cache theo location) | ~1 lần / location | cao |
| Sinh nhân vật 512×768, 8 bước | ~1 lần / nhân vật / cảnh | cao |
| **Face detailer** (img2img 14 bước) | **~1 lần / nhân vật / cảnh** | **cao ở cảnh cận, gần bằng 0 ở cảnh rộng** |
| Matte rembg | ~0.9 s | trung bình |
| RealESRGAN ×4 | mỗi frame | trung bình |
| Auto-train LoRA nhân vật chính | 700 bước × 2 người, 1 lần/truyện | cao |

Điểm lãng phí rõ nhất: ở cảnh rộng (`_SHOT_DEFAULTS["wide"]` → `scale = 0.45`),
lớp nhân vật 512×768 bị thu về ~194 px trong khung cao 432 px, khuôn mặt còn
khoảng **23 px**. Chạy một lượt img2img 14 bước để vẽ lại 23 pixel đó là ném
thời gian đi. Đã bịt ở Giai đoạn 0.

### 2.5. Không có cổng chất lượng nào cho ảnh

Cổng duy nhất đang tồn tại là `alpha_coverage` trong khoảng 5-95% — nó chỉ bắt
lỗi *tách nền*, không bắt lỗi *ảnh xấu*. Không có gì kiểm tra: ảnh có đúng nội
dung prompt không, có thừa người không, mặt có méo không, khung có trống trơn
không. Nên "tỷ lệ ảnh bị lỗi còn rất nhiều" là điều đương nhiên — hiện chưa có
cơ chế nào phát hiện và làm lại.

---

## 3. Fine-tune cho một thể loại cố định

### 3.1. Chọn tầng can thiệp nào

| Cách | VRAM train | Thời gian | Độ khóa phong cách | Kết luận |
|---|---|---|---|---|
| Đổi checkpoint SD1.5 khác | 0 (chỉ tải) | 0 | thấp — vẫn trôi theo prompt | bổ trợ, không đủ |
| Prompt/preset (đang dùng) | 0 | 0 | thấp | cần, nhưng không đủ |
| **LoRA phong cách SD1.5** | **~5 GB** | **~40 phút** | **cao** | **chọn cái này** |
| Fine-tune full checkpoint SD1.5 | >12 GB | nhiều giờ | rất cao | quá tầm 6 GB |
| LoRA SDXL | 12 GB tối thiểu | — | rất cao | **không khả thi ở 6 GB** |

Về SDXL và Flux: với 6 GB, SDXL đã chật ngay ở khâu *chạy*, còn *train* LoRA SDXL
cần tối thiểu ~12 GB. Trong khi đó SD1.5 cộng một chồng LoRA được tuyển chọn vẫn
là lựa chọn thực dụng nhất cho tranh minh hoạ/anime ở phân khúc VRAM này. Kết
luận: **ở lại SD1.5, đầu tư vào LoRA thay vì đổi model nền.**

### 3.2. Vì sao LoRA phong cách giải quyết được cả "tỷ lệ ảnh lỗi"

Đây là điểm ít người để ý. Một phong cách **tối, tương phản cao, ít chi tiết,
nhiều mảng đặc** — đúng kiểu thủy mặc trong ảnh tham chiếu — che được gần hết
điểm yếu của SD1.5:

- bàn tay hỏng biến thành mảng mực, không còn là năm ngón sai;
- mặt ở xa không cần chi tiết vì phong cách vốn không vẽ chi tiết ở xa;
- nền rối thành mảng sương và khoảng trống;
- bố cục đọc bằng **bóng dáng (silhouette)**, mà silhouette lại là thứ SD1.5 làm
  tốt — và cũng chính là thứ diễn tả hành động rõ nhất.

Nói cách khác: chọn phong cách này không chỉ vì thẩm mỹ, mà vì nó **đưa yêu cầu
về đúng vùng năng lực của model**. Một style phẳng-pastel-nhiều-chi-tiết như
`storyboard.txt` hiện tại thì làm ngược lại — nó phơi bày mọi lỗi.

### 3.3. Quy trình cụ thể

Hạ tầng đã có sẵn sau Giai đoạn 0:

```bash
AIVoice/.venv/Scripts/python.exe AIVoice/apps/MediaComposer/scripts/train_style_lora.py --style thuy_mac --images_dir "D:\dataset\thuymac" --style_token "thuymac ink wash style" --steps 1500
```

Yêu cầu dataset — **đây là phần quyết định thành bại, không phải tham số train**:

- **40-80 ảnh**, cùng một cách vẽ, **khác nhau về nội dung** (người/cảnh/vật, xa/gần,
  sáng/tối). Ít ảnh mà cùng nội dung sẽ ra LoRA *nội dung*, không phải LoRA *phong cách*.
- **Mỗi ảnh kèm một file `.txt` cùng tên** mô tả nội dung ảnh đó bằng tag tiếng Anh.
  Đây là khác biệt cốt lõi so với LoRA nhân vật: nếu mọi ảnh dùng chung một caption,
  model không có cách nào tách phong cách ra khỏi nội dung. Script sẽ cảnh báo nếu
  thiếu caption.
- `rank = 8` (thấp hơn LoRA nhân vật), `lr = 8e-5`, 1500 bước.

Bật lên trong `config.toml`:

```toml
[storytelling]
style_lora        = "thuy_mac"
style_lora_weight = 0.8
```

LoRA phong cách được bật cho **mọi** lượt sinh — nền, nhân vật, và cả unify pass —
nên toàn chương có cùng art direction ở mức trọng số chứ không chỉ mức prompt.
Thứ tự adapter: `hyper → style → character`.

Nguồn dataset hợp pháp cho đồ án: tự vẽ, ảnh public-domain (tranh thủy mặc cổ hết
hạn bản quyền là nguồn rất tốt và rất đúng phong cách), hoặc ảnh do chính pipeline
sinh ra rồi tuyển tay. **Không** dùng ảnh cào từ tác phẩm còn bản quyền — mục
"chế độ trình diễn sạch bản quyền" trong README sẽ mất giá trị.

---

## 4. Lột tả hành động nhân vật

Hai tầng, làm theo thứ tự.

### Tầng 1 — prompt (đã làm ở Giai đoạn 0, không tốn thêm thời gian chạy)

- Bỏ hẳn `front view`, `centered subject`, `standing` khỏi prompt nhân vật.
- Tách hành động thành trường riêng `CharacterLayer.action`, không trộn vào ngoại hình.
- Đặt hành động **lên đầu prompt** kèm trọng số `(…:1.35)` — SD1.5 đọc token theo
  thứ tự và loãng dần về cuối, nên vị trí quan trọng ngang trọng số.
- Thêm trường `action` vào schema JSON của LLM, kèm hướng dẫn viết động từ cụ thể
  và **cấm** `standing` / `looking at viewer`.

Giới hạn còn lại: prompt chỉ *gợi ý* tư thế. Với 8 bước lấy mẫu, tỷ lệ trúng tư
thế phức tạp (vung kiếm, ngã, nhảy) vẫn không cao.

### Tầng 2 — ControlNet OpenPose + thư viện tư thế (đề xuất, Giai đoạn 2)

Đây mới là thứ đảm bảo hành động **luôn** đúng.

- Model: `lllyasviel/control_v11p_sd15_openpose` (~700 MB fp16). Nạp thêm vào
  `StableDiffusionControlNetPipeline`; với `enable_model_cpu_offload` đang bật cho
  profile `cuda_low` thì vẫn vừa 6 GB.
- **Không chạy pose detector lúc render.** Thay vào đó ship sẵn thư viện ~30 ảnh
  skeleton OpenPose ở `resource/pose_library/` (chạy, quỳ, vung kiếm, chỉ tay,
  ngồi, ngã, ôm đầu…). LLM chỉ phải chọn **một tên tư thế trong enum cố định** —
  vừa xác định, vừa dễ kiểm định, vừa không tốn thêm một model detector.
- Chi phí: +15-25% thời gian mỗi lớp nhân vật. Đổi lại tư thế đúng gần như 100%
  và bố cục ổn định giữa các frame.

Lợi ích cộng thêm: có skeleton thì **cảnh hai người tương tác không cần fallback
classic nữa** — dựng một skeleton hai người là ghép được đúng.

---

## 5. Hạ tỷ lệ ảnh lỗi

Đề xuất một cổng kiểm định rẻ + reroll có giới hạn (Giai đoạn 3). Điểm mấu chốt:
**mọi tín hiệu dưới đây đều dùng model đã nằm sẵn trên VRAM**, không tải thêm gì.

| Tín hiệu | Lấy từ đâu | Bắt được lỗi gì |
|---|---|---|
| CLIP similarity giữa frame và prompt | CLIP image encoder của IP-Adapter (đã nạp); `dataset_collector.precheck_similarity` đã có sẵn cách gọi | ảnh lạc đề hoàn toàn |
| Số mặt phát hiện được | `face_detailer.detect_faces` (cascade, đã có) | thừa người, mất người |
| Độ lệch chuẩn độ sáng | numpy | frame trống trơn / cháy sáng |
| Alpha coverage | `alpha_coverage` (đã có) | matte hỏng |

Chính sách: cảnh nào dưới ngưỡng thì sinh lại **tối đa 1 lần** với seed khác. Chi
phí bị chặn trên ở mức +1 lượt sinh cho đúng phần ảnh hỏng, thay vì tăng steps cho
toàn bộ. Ghi lại tỷ lệ reroll vào báo cáo batch để có số đo khách quan cho việc
"tỷ lệ lỗi đã giảm chưa".

---

## 6. Tốc độ

Nguyên tắc: **không tăng steps**. Đổi chỗ ngân sách.

| Việc | Tác động | Trạng thái |
|---|---|---|
| Bỏ face detailer ở cảnh rộng (mặt < 30 px trong frame cuối) | −1 lượt img2img 14 bước / nhân vật / cảnh rộng | ✅ đã làm |
| Unify pass thay vì tăng steps toàn cục | +~4 bước thật / cảnh, đổi lấy hết vẻ sticker | ✅ đã làm |
| LoRA phong cách thay cho việc "sửa sau" | ảnh gốc đã đúng → bớt phụ thuộc detailer/upscale | hạ tầng ✅, chờ dataset |
| Cache nền theo location | đã có, đang chạy đúng | ✅ có sẵn |
| ControlNet pose | +15-25% / lớp nhân vật | đề xuất |
| Cổng chất lượng + reroll | +1 lượt sinh cho phần ảnh hỏng | đề xuất |

Về unify pass: img2img chỉ chạy `int(steps × strength)` bước thật. Với
`steps=16, strength=0.28` là ~4 bước — rẻ hơn nhiều so với sinh mới một ảnh, và rẻ
hơn hẳn so với nâng steps của mọi lượt sinh. `strength` bị chặn trần ở 0.45 vì cao
hơn ngưỡng đó model bắt đầu vẽ lại cả bố cục và làm mất nhân vật vừa ghép.

---

## 7. Lộ trình

| Giai đoạn | Nội dung | Chi phí | Rủi ro |
|---|---|---|---|
| **0 — đã làm** | Khóa style; hành động lên đầu prompt có trọng số; unify pass; bỏ detailer cảnh rộng; hạ tầng + script train LoRA phong cách | — | thấp, có test |
| **1 — kế tiếp** | Dựng dataset 40-80 ảnh + caption, train `thuy_mac`, bật `style_lora`, chạy 1 chương thật để so | ~1 buổi gom ảnh + 40 phút train | dataset yếu → LoRA bám nội dung |
| **2** | ControlNet OpenPose + `resource/pose_library/` + enum tư thế cho LLM | ~1 ngày code + 700 MB tải | VRAM sát trần ở cảnh nhiều nhân vật |
| **3** | Cổng chất lượng + reroll có giới hạn + thống kê vào báo cáo batch | ~0.5 ngày | ngưỡng đặt sai gây reroll thừa |
| **4** | Bóng chân + khử nét mép + nhoè nền theo chiều sâu | ~0.5 ngày | thấp |

Thứ tự này có chủ ý: **Giai đoạn 1 phải xong trước Giai đoạn 2-3.** Chưa khóa được
phong cách thì không có đường cơ sở ổn định để đo xem ControlNet hay cổng chất
lượng có thực sự cải thiện gì không.

---

## 8. Giai đoạn 0 — những gì đã thay đổi

| Tệp | Thay đổi |
|---|---|
| `storytelling/style_lock.py` *(mới)* | `strip_style_drift`, `weight_action`, `build_locked_prompt` — hàm thuần, khóa thứ tự `style → hành động có trọng số → nội dung` |
| `storytelling/studio/unify_pass.py` *(mới)* | img2img strength thấp trên frame đã ghép; dùng lại img2img pipeline chia sẻ component nên **không tốn thêm VRAM**; tắt IP-Adapter trong lượt này để khỏi kéo mặt tham chiếu đè cả khung |
| `scripts/train_style_lora.py` *(mới)* | Train LoRA phong cách SD1.5, caption riêng từng ảnh, rank 8 |
| `resource/image_presets/thuy_mac.txt` *(mới)* | Preset mực tàu tương phản cao, positive/negative không tự mâu thuẫn |
| `llm_prompter.py` | Bỏ style prefix chèn cứng mâu thuẫn với style truyện; thêm trường `action` vào schema; **cấm** LLM viết tag style |
| `image_generator.py` | `_ensure_quality_tags` chỉ thêm tag chất lượng khi prompt chưa có; thêm `set_style_lora` + `get_style_lora_path`, style LoRA bật cho mọi lượt sinh |
| `studio/character_renderer.py` | Bỏ `front view` / `centered subject` / `standing`; hành động lên đầu kèm trọng số |
| `studio/layout_planner.py`, `models.py` | `CharacterLayer.action` tách khỏi `prompt` |
| `studio/studio_pipeline.py` | Nối unify pass; ưu tiên `_llm_action`; cổng `_face_too_small_to_detail` |
| `config.py`, `config.toml.example` | `style_lora`, `style_lora_weight`, `studio_action_weight`, `studio_unify_*` |
| `webui/index.html` | Thêm `thuy_mac` + hai preset storyboard; sửa nhãn `watercolor` (đang bị ghi nhầm là "Tranh Thủy Mặc") |

Kiểm định: **106 test MediaComposer + 46 test repo tổng xanh**; ruff phạm vi CI
(`E9,F63,F7,F82`) sạch; `compileall` sạch.

### Chưa được kiểm chứng trên GPU

Toàn bộ Giai đoạn 0 mới chỉ qua test đơn vị. Ba thứ **bắt buộc phải xem tận mắt**
trước khi tin:

1. `studio_unify_strength = 0.28` có phải điểm rơi đúng không, hay còn lộ mép /
   đã bắt đầu ăn vào nhân vật. Đây là tham số nhạy nhất trong lần thay đổi này.
2. Hành động ở trọng số 1.35 có làm méo giải phẫu không.
3. Việc bỏ face detailer ở cảnh rộng có làm mặt tệ đi ở mức nhìn thấy được không.

Cách xem nhanh (script đã cập nhật để xuất cả `04_composite_rembg.png` ghép thô và
`05_composite_unified.png` đã hòa trộn, cạnh nhau):

```bash
cd AIVoice/apps/MediaComposer && ../../.venv/Scripts/python.exe scripts/studio_quicktest.py thuy_mac
```

---

## 9. Nghiệm thu

- [x] Test đơn vị + lint + compile xanh cả hai tầng.
- [ ] GPU: chạy `studio_quicktest.py`, so `04_*` với `05_*` bằng mắt, chốt `studio_unify_strength`.
- [ ] GPU: chạy `studio_batch_smoke.py` nhiều cảnh, kiểm tra hành động có đọc được không.
- [ ] Dựng dataset và train `thuy_mac`, chạy lại cùng một chương để so trước/sau.
- [ ] Chạy trọn một chương thật (Pass A + Pass B) rồi xem tay các frame biên.
- [ ] Chỉ sau các gate trên mới merge.

## Nguồn tham khảo

- [SDXL vs SD 1.5 vs Flux: Which Image Model Should You Run Locally?](https://insiderllm.com/guides/sdxl-vs-sd-1-5-vs-flux/)
- [Image Generation VRAM Requirements 2026 — Flux, SDXL, SD 3.5](https://willitrunai.com/blog/image-generation-vram-guide-2026)
- [Hardware Requirements for Training Your Own Stable Diffusion LoRA in 2026](https://vrlatech.com/stable-diffusion-lora-training-hardware-requirements/)
- [Train an Image LoRA Locally (2026): Kohya, SDXL & FLUX](https://localaimaster.com/blog/image-lora-training-local-guide)
