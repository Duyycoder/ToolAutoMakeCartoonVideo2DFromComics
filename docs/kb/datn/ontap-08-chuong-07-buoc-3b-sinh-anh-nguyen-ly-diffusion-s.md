# Chương 07. Bước 3b — Sinh ảnh: nguyên lý Diffusion & Stable Diffusion (phần lý thuyết cốt lõi)

- Mục tiêu chương: sau khi đọc xong, bạn giải thích được (1) một mô hình diffusion "vẽ" ảnh từ nhiễu như thế nào, (2) vì sao Stable Diffusion chạy được trên GPU 6–8 GB, (3) từng tham số trong code ( `num_inference_steps` , `guidance_scale` , seed, scheduler, fp16, CPU offload, VAE tiling…) có ý nghĩa gì về mặt lý thuyết và dự án đang đặt giá trị bao nhiêu, ở dòng nào.

- Các phần liên quan nhưng trình bày chi tiết ở chương khác: tách cảnh + sinh prompt bằng LLM (Bước 3a), IP-Adapter / LoRA nhân vật / Face Detailer / Studio compositing (các chương sau). Ở đây chỉ nhắc chúng khi cần để hiểu luồng sinh ảnh.

## 1. Vai trò trong hệ thống

### 1.1 Vị trí trong pipeline

Hệ thống có 4 bước lớn: (1) crawl + dịch truyện → (2) TTS lồng tiếng → (3) dựng video (tách cảnh, sinh prompt, sinh ảnh, ghép video) → (4) autosub. "Bước 3b" là khâu biến một câu mô tả cảnh bằng tiếng Anh thành một bức ảnh 2D.

- Orchestrator (FastAPI) gọi subprocess `adapter_video_cli.py` của MediaComposer và truyền checkpoint qua tham số `--` `checkpoint` ( `orchestrator/pipeline.py:545` , mặc định `"anything-v5"` ). Trước khi chạy, orchestrator ghi các tham số `sd_*` từ Cấu Hình Chung xuống `[storytelling]` trong `AIVoice/apps/MediaComposer/config.toml` ( `orchestrator/mediacomposer_config.py` , bảng `SD_PARAM_MAP` , có kẹp giá trị bằng `LIMITS` , ví dụ `num_inference_steps` ∈ [1, 60], `guidance_scale` ∈ [0, 20]). Trong MediaComposer, vòng lặp sinh ảnh cho từng cảnh nằm ở `app/services/storytelling/orchestrator.py` (khoảng dòng 365–471): nạp `StorytellingPipeline` , `warmup()` , rồi gọi `pipe.generate_draft(...)` cho mỗi cảnh. Lõi Stable Diffusion là class singleton `StorytellingPipeline` trong `app/services/storytelling/image_generator.py` . Nếu `render_mode = "studio"` thì `orchestrator.py:354-364` rẽ sang `StudioPipeline` (render nền + nhân vật theo lớp rồi ghép). Nhánh Studio vẫn dùng chung `StorytellingPipeline.generate_draft` ( `studio/studio_pipeline.py:444, 592` , `studio/character_renderer.py:142` ), nên toàn bộ lý thuyết và tham số trong chương này áp dụng cho cả hai nhánh.

### 1.2 Input / Output

- **Nội dung:** Input chính `scene.image_prompt` (đã ghép style khóa + hành động có trọng số + nội dung) · **Nguồn trong code:** `style_lock.build_locked_prompt` gọi từ `llm_prompter.py:189,217`
- **Nội dung:** Negative Phần sau dấu `---` của file style truyện prompt · **Nguồn trong code:** `models.py:111get_negative_prompt()`
- **Nội dung:** Identity (tuỳ Ảnh tham chiếu nhân vật (IP-Adapter CLIP) hoặc embedding 512- chọn) d (FaceID) · **Nguồn trong code:** `orchestrator.py` ~dòng 420–440
- **Nội dung:** Kích thước Theo `shot_type` : close 576×704, medium 704×528, wide = `image_width×image_height` (768×432) · **Nguồn trong code:** `orchestrator.py:457-464`
- **Nội dung:** Output `PIL.Image` + seed thực tế đã dùng · **Nguồn trong code:** `generate_draft` trả `Tuple[Image, int]` ( `image_generator.py:676-747` )

Sau đó ảnh draft được (tuỳ cấu hình) Face Detailer vẽ lại mặt, rồi upscale bằng Real-ESRGAN ×4 (768×432 → 3072×1728) và `ImageOps.fit` về 1920×1080 ( `postprocess.py:71-148` , `output_width/height` ), rồi mới vào khâu ghép video. Real-ESRGAN chạy fp32 và dùng tile 256 cho an toàn trên GPU 6 GB ( `postprocess.py:36-43` ).

- Lưu ý (chưa xác minh bằng chạy thật): `ImageOps.fit` cắt giữa để khớp tỉ lệ 16:9, trong khi comment ở `orchestrator.py:455-456` nói khung dọc 576×704 sẽ được video assembler pad. Nếu frame cận đi qua `run_realesrgan` thì có thể bị cắt trên/dưới thay vì pad. Nên kiểm tra thực tế trước khi bảo vệ.

### 1.3 Tham số thật đang dùng (đọc từ code/config)

- **Tham số:** Checkpoint mặc định · **Giá trị hiệu lực:** `anything-v5` → `stablediffusionapi/anything-v5` · **Nơi đặt:** `orchestrator/config.py:78` , alias ở `image_generator.py:172-178`
- **Tham số:** Checkpoint có trong UI · **Giá trị hiệu lực:** anything-v5, dreamshaper-8, majicmix-realistic, cetus-mix, meinamix · **Nơi đặt:** `webui/index.html:464-470`
- **Tham số:** `num_inference_steps` · **Giá trị hiệu lực:** 8 · **Nơi đặt:** `config.toml` , `app/config.py:45` , `orchestrator/config.py:15`
- **Tham số:** `guidance_scale` (CFG) · **Giá trị hiệu lực:** 5.0 · **Nơi đặt:** `config.toml` , `app/config.py:51`
- **Tham số:** Độ phân giải sinh · **Giá trị hiệu lực:** 768×432 (16:9) · **Nơi đặt:** `app/config.py:33-34`
- **Tham số:** Độ phân giải xuất · **Giá trị hiệu lực:** 1920×1080 (Real-ESRGAN `RealESRGAN_x4plus_anime_6B` ) · **Nơi đặt:** `app/config.py:36-38`
- **Tham số:** Scheduler · **Giá trị hiệu lực:** 8 bước → `EulerDiscreteScheduler` + Hyper-SD LoRA; ≥15 bước → `DPMSolverMultistepScheduler(use_karras_sigmas=True)` · **Nơi đặt:** `image_generator.py:23, 381-419`
- **Tham số:** dtype · **Giá trị hiệu lực:** fp16 nếu có CUDA, fp32 nếu CPU · **Nơi đặt:** `hardware_adapter.py` , `image_generator.py:162`
- **Tham số:** Attention · **Giá trị hiệu lực:** PyTorch 2 SDPA (không dùng xformers) · **Nơi đặt:** `image_generator.py:272`
- **Tham số:** Style mặc định · **Giá trị hiệu lực:** preset `thuy_mac` (tranh thủy mặc) · **Nơi đặt:** `context_manager.py:31` , `orchestrator/config.py:76`
- **Tham số:** `diffusers` · **Giá trị hiệu lực:** `==0.38.0` (kèm `accelerate>=1.0.0` , `peft>=0.19.0` , `compel>=2.0.0` ) · **Nơi đặt:** `AIVoice/requirements.txt:76-80`

- Lưu ý trung thực: `app/config.py:77-78` khai báo mặc định `style_lora = "thuy_mac"` , weight 0.45, nhưng cả `config.toml.example:54-55` ( `""` , 0.8) lẫn `config.toml` cục bộ ( `""` , 0.7) đều đặt `style_lora = ""` . Vì `load_config()` dùng `update()` từ file TOML đè lên mặc định ( `app/config.py:151-160` ), giá trị hiệu lực là style LoRA TẮT (chỉ khóa style bằng prompt), dù file `resource/style_loras/thuy_mac.safetensors` có tồn tại.

- `config.toml` là file cục bộ, không commit (bị bỏ qua ở `AIVoice/.gitignore:116` ); orchestrator ghi các khoá `sd_*` vào đó trước mỗi lần chạy. Riêng `enable_face_detailer` thì code mặc định `True` , nhưng thực tế do cờ dòng lệnh quyết định: orchestrator truyền `--enable-face-detailer` / `--no-face-detailer` ( `orchestrator/pipeline.py:570-573` , mặc định `False` theo `orchestrator/config.py:89` ), `adapter_video_cli.py:73` gán vào `config.storytelling` rồi `save_config()` — nên khi chạy qua WebUI, Face Detailer mặc định tắt.

## 2. Nền tảng lý thuyết từ gốc

### 2.1 Bài toán "mô hình sinh" (generative model) là gì?

Hãy tưởng tượng mọi bức ảnh 512×512 màu là một điểm trong không gian 786.432 chiều (512·512·3). Gần như toàn bộ không gian đó là nhiễu vô nghĩa; ảnh "trông có nghĩa" chỉ nằm trên một vùng cực nhỏ, gọi là phân phối dữ liệu

- . Mô hình sinh

học cách lấy mẫu (sample) ra điểm mới thuộc vùng đó.

Ba họ mô hình chính:

- **Họ:** GAN (Generator vs Discriminator) · **Ý tưởng:** Generator tạo ảnh, Discriminator phân biệt thật/giả, hai mạng "đấu" nhau (minimax) · **Ưu:** Sinh 1 lần forward → rất nhanh, ảnh sắc · **Nhược:** Huấn luyện bất ổn, mode collapse (chỉ sinh vài kiểu), khó điều kiện hoá bằng văn bản tự do
- **Họ:** VAE (Variational Autoencoder) · **Ý tưởng:** Encoder nén ảnh vào latent có phân phối Gauss, decoder tái tạo; tối ưu ELBO · **Ưu:** Ổn định, có latent đẹp · **Nhược:** Ảnh mờ (do loss tái tạo kiểu MSE lấy "trung bình")
- **Họ:** Diffusion · **Ý tưởng:** Học cách khử nhiễu từng chút ngược lại quá trình làm nhiễu · **Ưu:** Huấn luyện ổn định (chỉ là hồi quy MSE), đa dạng, điều kiện hoá bằng text rất tốt · **Nhược:** Sinh chậm vì phải lặp nhiều bước

Stable Diffusion kết hợp VAE (để nén ảnh) và diffusion (để sinh trong không gian nén). Đây là chìa khoá của cả chương.

### 2.2 Trực giác: điêu khắc từ khối đá nhiễu

Phép so sánh dễ nhớ: nhỏ một giọt mực vào cốc nước, mực khuếch tán (diffuse) cho tới khi đều màu — quá trình này dễ, có thể mô tả chính xác. Diffusion model học quay ngược đoạn phim đó: từ cốc nước đều màu, từng chút một gom mực về hình giọt ban đầu.

Với ảnh: ta lấy ảnh thật, thêm nhiễu Gauss dần dần qua

- bước (thường

- ) đến khi thành nhiễu thuần. Mạng nơ-ron

được dạy: "nhìn ảnh bị nhiễu ở mức , đoán xem nhiễu trong đó là gì". Biết nhiễu thì trừ đi được một ít → ảnh sạch hơn một chút. Lặp lại từ nhiễu thuần → ảnh.

### 2.3 Forward process (quá trình làm nhiễu)

Mỗi bước thêm một chút nhiễu Gauss:

- : ảnh sạch;

- : ảnh ở bước .

- (noise schedule): lượng nhiễu thêm ở bước , số nhỏ (ví dụ 0.0001 → 0.02 với DDPM gốc). Nhân

- để thu nhỏ tín

- hiệu cũ, giữ cho phương sai tổng không nổ.

- : phân phối chuẩn.

Đặt

- và

- (tích luỹ). Vì tổng các biến Gauss độc lập vẫn là Gauss, ta có công thức đóng (closed form)

nhảy thẳng từ

- tới bất kỳ nào:

- → gần ảnh gốc. Khi

Ý nghĩa:

- là pha trộn giữa ảnh gốc (hệ số

- ) và nhiễu (hệ số

- ). Khi nhỏ,

→ gần như nhiễu thuần. Công thức này là lý do huấn luyện rẻ: không cần mô phỏng 1000 bước, chỉ bốc ngẫu nhiên một và tính ngay

Vì sao nhiễu Gauss? (1) Tổng các Gauss độc lập vẫn là Gauss → có công thức đóng ở trên; (2) khi

- nhỏ, bước ngược

- cũng xấp xỉ Gauss, nên mạng chỉ cần dự đoán trung bình của nó; (3) điểm cuối

- dễ lấy mẫu.

Ghi chú về SD1.5: scheduler của các checkpoint SD1.5 thường dùng

- và lịch `scaled_linear` (

- tăng tuyến tính, từ

0.00085 tới 0.012). SD1.5 là mô hình epsilon-prediction ( `prediction_type = "epsilon"` ), tức U-Net xuất ra nhiễu — khác với SD2.x-768 dùng v-prediction. Code dự án không tự đặt các số này mà kế thừa `scheduler.config` của checkpoint ( `dict(self._pipe.scheduler.config)` ở `image_generator.py:400` ), rồi chỉ đổi thuật toán lấy mẫu.

### 2.4 Reverse process và mục tiêu huấn luyện

Quá trình ngược

- không có công thức đóng (phụ thuộc toàn bộ phân phối ảnh), nên ta học nó bằng mạng nơ-ron.

Ho et al. (DDPM, 2020) chỉ ra một cách tham số hoá rất đơn giản: cho mạng

- dự đoán nhiễu đã được thêm vào.

Thuật toán huấn luyện (một vòng):

- 1. Lấy ảnh

- từ dataset (và caption nếu có điều kiện text).

- 2. Chọn ngẫu nhiên

- và

- 3. Tính

- 4. Tối ưu:

Chỉ là MSE giữa nhiễu thật và nhiễu đoán. Không có đối thủ như GAN → huấn luyện ổn định. Đây là câu hội đồng rất hay hỏi: "Model học cái gì?" → học dự đoán nhiễu.

### 2.5 Vì sao "đoán nhiễu" lại sinh được ảnh? (trực giác score matching)

Từ công thức đóng, nếu đoán đúng thì suy ra được ảnh sạch:

Sâu hơn: người ta chứng minh (denoising score matching, Vincent 2011; Song & Ermon 2019) rằng nhiễu dự đoán tỷ lệ với score — gradient của log mật độ xác suất:

Trực giác: score là mũi tên chỉ về phía "ảnh hợp lý hơn". Đi ngược hướng nhiễu = leo dốc về vùng dữ liệu. Ở lớn (nhiều nhiễu) mô hình quyết định bố cục thô, màu mảng lớn; ở nhỏ nó quyết định chi tiết, đường nét. Điều này giải thích vì sao img2img với strength thấp chỉ đổi "bề mặt" mà giữ bố cục (mục 2.12).

### 2.6 Thuật toán lấy mẫu (sampler / scheduler)

Huấn luyện dùng 1000 bước, nhưng khi sinh không ai chạy đủ 1000. Các scheduler là các cách giải bài toán "đi từ nhiễu về ảnh" với ít bước.

DDPM (ngẫu nhiên, cần nhiều bước ~1000):

DDIM (Song 2020, tất định khi

- ): đoán

- rồi "trộn lại" ở mức nhiễu thấp hơn, cho phép nhảy cóc:

Góc nhìn ODE / sigma (Karras et al. 2022): chia

- cho

- ta được

- với

- (đây là cách

`EulerDiscreteScheduler` quy đổi 1000 timestep sang dãy ; với SD1.5, lớn nhất ≈ 14.6). Quá trình khử nhiễu là một phương trình vi phân thường (probability-flow ODE) theo ; mỗi scheduler là một bộ giải số cho ODE đó. Khi đó:

- Euler ( `EulerDiscreteScheduler` ): bước bậc 1,

- . Giống đi xuống dốc theo hướng

- tiếp tuyến. DPM-Solver++ 2M ( `DPMSolverMultistepScheduler` ): bộ giải bậc 2 multistep — tận dụng dự đoán của bước trước để ước lượng độ cong → ít bước hơn mà vẫn chính xác (~20–25 bước cho ảnh tốt). Karras sigmas ( `use_karras_sigmas=True` ): phân bố các mức dày ở vùng nhiễu thấp (nơi chi tiết hình thành), thưa ở vùng nhiễu cao → chất lượng tốt hơn với cùng số bước.

Trade-off số bước: mỗi bước = 1 lần chạy U-Net (2 lần nếu có CFG, xem 2.10). Ít bước → nhanh nhưng lỗi tích luỹ lớn (ảnh nhoè, thiếu chi tiết). Vì vậy dự án dùng Hyper-SD (ByteDance) — một LoRA được chưng cất (distillation) để mô hình đi được quãng đường khử nhiễu trong 1–8 bước. Code chọn biến thể theo số bước và CFG ( `image_generator.py:339-346` ):

```
def _select_hyper_lora(self, num_steps: int, guidance_scale: float) -> str:
    if num_steps <= 2:
        return "Hyper-SD15-2steps-lora.safetensors"
    if num_steps <= 4:
        return "Hyper-SD15-4steps-lora.safetensors"
    if guidance_scale > 1.2:
        return "Hyper-SD15-8steps-CFG-lora.safetensors"
    return "Hyper-SD15-8steps-lora.safetensors"
```

Với cấu hình thật (8 bước, CFG 5.0) → `Hyper-SD15-8steps-CFG-lora.safetensors` + `EulerDiscreteScheduler` . `config.toml.example:35-36` ghi chú: "8 steps + guidance 5.0 tự kích hoạt Hyper-SD CFG-lora, ~3x nhanh hơn 25 steps" (con số 3x là ghi chú của tác giả, chưa có benchmark kèm trong repo).

Chưng cất (distillation) là gì? Ý tưởng "thầy – trò": mô hình thầy (SD gốc) cần nhiều bước nhỏ để đi từ nhiễu về ảnh; mô hình trò được huấn luyện để với một bước lớn nhảy tới gần đúng chỗ mà thầy phải đi nhiều bước mới tới. Hyper-SD (ByteDance, 2024) dùng trajectory segmented consistency distillation: chia quỹ đạo khử nhiễu thành các đoạn và dạy trò nhất quán trong từng đoạn, kết hợp học từ phản hồi con người. Kết quả được đóng gói thành LoRA gắn vào bất kỳ checkpoint SD1.5 nào — nên dự án đổi checkpoint (anything-v5, dreamshaper-8…) mà vẫn giữ được chế độ 8 bước. Họ tương tự: LCM-LoRA, SDXL- Turbo/Lightning. Biến thể "CFG" của Hyper-SD được chưng cất sao cho vẫn chịu được guidance ~5–8 (có negative prompt), còn bản thường giả định CFG ≈ 1.

- Ghi chú (chưa xác minh trong repo): tài liệu Hyper-SD trên HuggingFace minh hoạ SD1.5 LoRA với `DDIMScheduler` / `TCDScheduler` và `timestep_spacing="trailing"` . Code dự án dùng `EulerDiscreteScheduler` kế thừa `timestep_spacing` từ config checkpoint. Chưa có phép đo trong repo so sánh hai cách; nếu hội đồng hỏi, nói đây là lựa chọn thực nghiệm của nhóm.

### 2.7 Latent Diffusion: vì sao Stable Diffusion chạy được trên GPU phổ thông

Chạy diffusion trực tiếp trên pixel 512×512×3 rất đắt: U-Net phải xử lý 786k giá trị mỗi bước. Rombach et al. (2022, "Latent Diffusion Models") đề xuất: nén ảnh trước bằng VAE, rồi khuếch tán trong không gian nén.

- → latent

- VAE encoder: ảnh

- (giảm 8 lần mỗi chiều, 4 kênh). Latent được nhân hệ số scale (0.18215

- với SD1.x) để có phương sai ~1. Diffusion chạy hoàn toàn trên latent. VAE decoder: latent cuối → ảnh pixel. Chỉ chạy một lần ở cuối.

Áp số liệu dự án (ảnh wide 768×432):

- **Kích thước:** Pixel 768 × 432 × 3 · **Số giá trị:** 995.328
- **Kích thước:** Latent 96 × 54 × 4 · **Số giá trị:** 20.736

→ U-Net xử lý ít hơn 48 lần số giá trị. Đây là lý do SD1.5 chạy được trên GPU 6 GB. Hệ quả kỹ thuật: diffusers bắt chiều rộng/cao chia hết cho 8 (768, 432, 576, 704, 528 đều thoả). Lý tưởng là bội số của 64 vì U-Net còn giảm thêm 8 lần nữa; 432 không chia

hết cho 64 (latent cao 54 → 27 → 14 → 7), U-Net của diffusers vẫn chạy được nhờ upsample theo đúng kích thước của skip connection, nhưng mép ảnh đôi khi kém hơn chút.

Thêm một điểm lý thuyết: VAE của SD là KL-VAE — encoder cho ra phân phối (trung bình, phương sai) và chỉ có một phạt KL rất nhẹ, nên latent gần như tất định; hệ số 0.18215 đưa phương sai latent về ≈ 1 để khớp với giả định

- của diffusion.

Vì sao nén mà không mất chất lượng? VAE được huấn luyện với loss perceptual + adversarial để giữ chi tiết cảm nhận (texture, cạnh); phần "thông tin thừa" tần số cao gần như không nhìn thấy được bỏ đi. Diffusion chỉ phải lo phần ngữ nghĩa (bố cục, vật thể).

Điểm yếu cần biết (liên quan trực tiếp đến một bug của dự án, mục 4.8): decoder VAE ở fp16 có thể tràn số (overflow) → vùng ảnh đen/trắng tuyền.

### 2.8 Kiến trúc U-Net — "bộ não" dự đoán nhiễu

U-Net là mạng hình chữ U:

- Nhánh xuống (down blocks / encoder): 4 tầng, mỗi tầng 2 ResNet block; 3 tầng đầu có thêm Transformer block (attention) và downsample. Độ phân giải latent giảm (96×54 → 48×27 → 24×14 → 12×7), số kênh tăng (320 → 640 → 1280 → 1280 với SD1.5). Tầng thứ 4 (1280 kênh, 12×7) chỉ có ResNet, không attention. Nắm ngữ cảnh toàn cục. Bottleneck (mid block): độ phân giải thấp nhất, có attention. Nhánh lên (up blocks / decoder): upsample trả lại độ phân giải gốc. Skip connections: nối feature map từ nhánh xuống sang nhánh lên cùng độ phân giải → giữ chi tiết vị trí, tránh mất thông tin khi nén. ResNet block:

- — học phần dư giúp mạng sâu vẫn huấn luyện được.

- Time embedding: bước được mã hoá bằng sinusoidal embedding (giống positional encoding của Transformer) rồi qua MLP, cộng vào mọi ResNet block → mạng biết "đang ở mức nhiễu nào" để khử bao nhiêu. Transformer block trong nhiều tầng: self-attention (các vùng ảnh "nhìn" nhau) + cross-attention (ảnh "nhìn" văn bản, mục 2.9).

SD1.5 U-Net có khoảng 860 triệu tham số. Đầu vào: latent 4 kênh; đầu ra: nhiễu dự đoán cùng shape.

(Sơ đồ đơn giản hoá: thực tế time embedding và text embedding đi vào mọi block có ResNet/attention tương ứng.)

### 2.9 Điều kiện hoá bằng văn bản: CLIP + cross-attention

CLIP (OpenAI 2021) gồm text encoder và image encoder được huấn luyện contrastive trên ~400 triệu cặp ảnh–caption: embedding ảnh và caption khớp nhau thì gần nhau. Vì vậy text embedding của CLIP "hiểu" nội dung thị giác.

SD1.5 dùng text encoder CLIP ViT-L/14:

- 1. Tokenizer BPE tách prompt thành token; độ dài cố định 77 token (gồm token bắt đầu/kết thúc). Dài hơn bị cắt. 2. Transformer 12 tầng → ma trận 77 × 768 (mỗi token một vector 768 chiều, có ngữ cảnh).

Cross-attention trong U-Net:

- (query) đến từ feature ảnh

- : mỗi vị trí pixel-latent hỏi "tôi nên vẽ gì?".

- (key, value) đến từ text embedding

- : mỗi token trả lời.

- Trọng số softmax cho biết vị trí nào "chú ý" token nào; kết quả là thông tin văn bản được bơm vào đúng vùng ảnh.

Hệ quả thực tế dự án xử lý:

- Giới hạn 77 token: dự án dùng thư viện compel với `truncate_long_prompts=False` — chia prompt dài thành nhiều đoạn 77 token, encode từng đoạn rồi nối embedding ( `image_generator.py:589-627` ). Trọng số token `(tag:1.3)` : compel nhân/khuếch đại embedding của token đó. Nếu truyền chuỗi thường vào diffusers, cú pháp này thành token rác → code luôn đi qua compel, fallback thì `_strip_weights` bỏ sạch cú pháp ( `image_generator.py:580-587` ). Token đầu prompt quan trọng hơn: vì thế `style_lock.build_locked_prompt` đặt style trước, hành động có trọng số 1.35 ngay sau ( `style_lock.py:103-127` , `app/config.py:81` ).

### 2.10 Classifier-Free Guidance (CFG) và negative prompt

Vấn đề: mô hình có điều kiện text thường "nghe lời" chưa đủ. Ho & Salimans (2022) đề xuất CFG: khi huấn luyện, thỉnh thoảng (≈10%) bỏ caption (thay bằng chuỗi rỗng) để cùng một mạng học cả dự đoán có điều kiện và không điều kiện. Khi sinh, chạy U-Net hai lần mỗi bước:

- = guidance scale (tham số `guidance_scale` , dự án = 5.0). Hiệu

- là "hướng mà caption kéo ảnh đi"; nhân để phóng đại hướng đó.

- : không tăng cường;

- : mặc định phổ biến của SD1.5; quá lớn (>12): màu cháy, bão hoà, méo hình.

- Chi phí: batch nhân đôi (diffusers ghép uncond + cond thành batch 2). Trong diffusers, CFG chỉ bật khi `guidance_scale >` `1` ; nếu

- pipeline chạy một nhánh và bỏ qua negative prompt.

- Hệ quả trong code: với engine `faceid` , embedding IP-Adapter tự chuẩn bị phải có shape `[2, 1, 512]` (ghép zero- negative + positive) khi CFG bật ( `image_generator.py:516-518` ). Với engine mặc định `clip` , code chỉ truyền ảnh `ip_adapter_image` , diffusers tự tạo cặp negative/positive.

Negative prompt: thay

- (chuỗi rỗng) bằng embedding của negative prompt

→ ảnh bị đẩy ra xa khái niệm trong negative (ví dụ preset `thuy_mac` có negative `saturated colors, colorful, 3d,` `photorealistic, text, watermark…` ). Negative prompt chỉ có tác dụng khi CFG bật (

Về mối liên hệ CFG với Hyper-SD trong dự án: comment ở `app/config.py:46-50` ghi rằng từng đặt `guidance_scale = 1.5` với 8 bước khiến "gần như bỏ qua prompt: model tự do liên tưởng và trả về mảng texture trừu tượng thay vì chủ thể", nên nâng lên 5.0 và dùng biến thể Hyper-SD CFG-lora vốn được chưng cất để chịu CFG.

### 2.11 Seed và tính tất định (determinism)

- là nhiễu Gauss sinh từ bộ sinh số giả ngẫu nhiên. Seed cố định bộ sinh → cùng

Điểm xuất phát

- . Với cùng seed + cùng

prompt + cùng checkpoint/LoRA + cùng scheduler/steps/CFG + cùng kích thước, ảnh sẽ (gần như) giống hệt. "Gần như" vì khác GPU/driver/phiên bản thư viện hoặc kernel fp16 không tất định có thể lệch nhỏ.

Trong code: `seed==-1` → random `torch.randint(0, 2147483647)` ; mỗi lần sinh tạo `torch.Generator(device).manual_seed(seed)` ( `image_generator.py:709-720` ). Seed thực tế được trả về cùng ảnh để có thể tái tạo/reroll. Lưu ý: nếu ảnh bị lỗi "dải chết", code đổi seed và sinh lại (mục 4.8), nên seed trả về là seed của lần thành công.

Scheduler Euler "ancestral" mới thêm nhiễu ngẫu nhiên mỗi bước; `EulerDiscreteScheduler` và DPM++ 2M dùng trong dự án là dạng tất định sau khi đã cố định

### 2.12 img2img và denoising strength

Thay vì bắt đầu từ nhiễu thuần, img2img:

- 1. Encode ảnh có sẵn qua VAE →

- 2. Thêm nhiễu tới mức

- bằng công thức đóng ở 2.3.

- 3. Chỉ khử nhiễu từ

- về 0.

- strength ≈ 0 → gần như giữ nguyên ảnh; strength = 1 → bằng text2img. Số bước thực chạy ≈ `int(steps * strength)` . Theo trực giác 2.5: strength thấp chỉ đi qua vùng nhỏ (nơi quyết định chi tiết) → giữ bố cục, sửa bề mặt.

Dự án dùng img2img ở hai chỗ, đều qua `AutoPipelineForImage2Image.from_pipe(pipeline._pipe)` — chia sẻ UNet/VAE/text encoder, không tốn thêm VRAM ( `face_detailer.py:476-488` ):

- Face Detailer: crop mặt, img2img strength mặc định 0.45 ( `face_detailer_strength` ), thích ứng theo tỉ lệ chiều cao mặt/ ảnh: mặt < 12% → `min(0.55, strength + 0.08)` = 0.53; mặt > 30% → `max(0.30, strength - 0.05)` = 0.40 ( `face_detailer.py:347-354` ); `face_detailer_steps` = 14 bước DPM++ Karras, CFG cố định 6.0 ( `face_detailer.py:276-` `277, 431-441` ). Unify pass (Studio): strength 0.28, 16 bước → ~4 bước thật; chặn trần `MAX_SAFE_STRENGTH = 0.45` ( `studio/unify_pass.py:14-26` , `app/config.py:125-128` ).

### 2.13 Inpainting

Inpainting = img2img có mask: chỉ vùng mask được khử nhiễu lại, vùng ngoài mask ở mỗi bước được thay bằng latent gốc đã thêm nhiễu tương ứng (hoặc dùng checkpoint inpainting chuyên dụng có U-Net 9 kênh: 4 latent + 4 latent ảnh bị che + 1 mask).

Trong dự án: không có pipeline inpainting thật. `PostProcessor.run_adetailer` chỉ là stub log "Inpainting is simulated in this MVP" ( `postprocess.py:68` ) và đã bị bỏ khỏi luồng ( `postprocess.py:170-172` ). Thay vào đó Face Detailer làm "inpainting thủ công": crop vùng mặt → img2img → dán lại. Nếu hội đồng hỏi, trả lời đúng như vậy.

### 2.14 SD1.5 vs SDXL

- **SD 1.5:** Độ phân giải huấn luyện 512×512 · **SDXL 1.0:** 1024×1024
- **SD 1.5:** Text encoder CLIP ViT-L/14 (768-d) · **SDXL 1.0:** CLIP ViT-L + OpenCLIP ViT-bigG (nối lại, 2048-d)
- **SD 1.5:** U-Net ~860M tham số · **SDXL 1.0:** ~2.6B tham số
- **SD 1.5:** Điều kiện phụ Không · **SDXL 1.0:** Kích thước gốc, toạ độ crop, (refiner tuỳ chọn)
- **SD 1.5:** VRAM thực tế fp16 chạy tốt 4–6 GB · **SDXL 1.0:** cần ~8–12 GB, chậm hơn nhiều
- **SD 1.5:** Hệ sinh thái anime/LoRA/IP-Adapter/Hyper-SD Rất lớn · **SDXL 1.0:** Lớn nhưng ít hơn cho anime cũ

Dự án chọn SD1.5 ( `StableDiffusionPipeline` , không có `StableDiffusionXLPipeline` trong code; mọi LoRA/adapter đều bản `sd15` : `ip-adapter-plus-face_sd15` , `Hyper-SD15-*` ). Lý do: GPU mục tiêu 6–8 GB ( `hardware_adapter.py:50` ), cần sinh hàng chục cảnh mỗi chương, và hệ sinh thái checkpoint anime SD1.5 phong phú.

Hệ quả của SD1.5 phải biết: sinh ở 768×432 là lệch khỏi 512 huấn luyện → đôi khi lặp chủ thể/bố cục lạ; mặt nhỏ vẽ tệ. Dự án bù bằng: khung dọc 576×704 cho cảnh cận ( `orchestrator.py:453-464` , comment "SD1.5 vẽ mặt nhỏ rất tệ"), Face Detailer, và upscale Real-ESRGAN thay vì sinh trực tiếp 1080p.

### 2.15 Checkpoint và fine-tune

Checkpoint = bộ trọng số đầy đủ (U-Net + VAE + text encoder). Các checkpoint cộng đồng là SD1.5 được fine-tune (hoặc merge nhiều model) trên dữ liệu phong cách riêng:

- **Alias trong code:** `anything-v5` (mặc định) · **Repo HuggingFace ( `image_generator.py:172-178` ):** `stablediffusionapi/anything-v5` · **Đặc trưng:** Anime, hiểu tag kiểu Danbooru
- **Alias trong code:** `dreamshaper-8` · **Repo HuggingFace ( `image_generator.py:172-178` ):** `lykon/dreamshaper-8` · **Đặc trưng:** Bán thực (semi-realistic), điện ảnh; nhãn UI gợi ý dùng kèm preset `dreamshaper_cinematic` (không tự động ghép cặp)
- **Alias trong code:** `majicmix-` `realistic` · **Repo HuggingFace ( `image_generator.py:172-178` ):** `emilianJR/majicMIX_realistic_v6` · **Đặc trưng:** Người thật
- **Alias trong code:** `cetus-mix` · **Repo HuggingFace ( `image_generator.py:172-178` ):** `stablediffusionapi/cetus-mix-v4` · **Đặc trưng:** Anime
- **Alias trong code:** `meinamix` · **Repo HuggingFace ( `image_generator.py:172-178` ):** `Meina/MeinaMix_V11` · **Đặc trưng:** Anime

Khác biệt với LoRA (Low-Rank Adaptation): LoRA không thay cả checkpoint mà thêm ma trận hạng thấp vào các lớp (chủ yếu là các phép chiếu Q/K/V/out của attention):

- ; trọng số adapter trong

`set_adapters` nhân thêm vào phần

- này); file chỉ vài chục MB, bật/tắt và trộn nhiều cái với trọng số. Dự án dùng cơ chế

`set_adapters(names, weights)` của diffusers + peft để trộn Hyper-SD (1.0), style LoRA (theo config), LoRA nhân vật (0.8), FaceID LoRA (0.65) ( `image_generator.py:404-475` ). Chi tiết LoRA xem chương riêng.

### 2.16 fp16 và tối ưu VRAM

fp16 (half precision): 16 bit thay vì 32 → trọng số và activation bằng một nửa bộ nhớ, Tensor Core chạy nhanh hơn nhiều. Rủi ro: dải biểu diễn hẹp (max ~65504) → tràn số ở vài lớp (điển hình VAE decoder) sinh NaN/đen. Dự án: `torch_dtype =` `float16 if use_fp16` ( `image_generator.py:162` ); còn Real-ESRGAN thì cố tình để fp32 vì fp16 gây khung đen ( `postprocess.py:41-43` ). Attention hiệu quả: attention chuẩn tạo ma trận

- (N = số vị trí latent); SDPA

( `torch.nn.functional.scaled_dot_product_attention` , PyTorch 2) dùng kernel kiểu FlashAttention/memory-efficient, không vật chất hoá toàn bộ ma trận → tiết kiệm bộ nhớ, nhanh. diffusers dùng SDPA mặc định; code chỉ log điều này ( `image_generator.py:272` ), không cài xformers, không bật attention slicing. Attention slicing: tính attention theo từng lát → ít bộ nhớ, chậm hơn. Không dùng (SDPA đã đủ). Model CPU offload ( `enable_model_cpu_offload` , cần `accelerate` ): giữ các module (text encoder, U-Net, VAE) trên RAM, chỉ đẩy module đang chạy lên GPU. Tiết kiệm VRAM đáng kể, chậm hơn một chút. (Khác "sequential CPU offload" đẩy từng lớp — rất chậm; dự án không dùng.) VAE slicing: decode từng ảnh trong batch một → an toàn, dự án bật khi offload ( `image_generator.py:279` ). VAE tiling: chia latent thành các ô chồng lấn, decode từng ô rồi trộn → cho phép decode ảnh rất lớn. Rủi ro: một ô tràn fp16 → cả dải đen. Dự án chỉ bật khi cạnh ≥ 1024 (mục 4.8).

## 3. Vì sao chọn công nghệ này (so sánh phương án)

- **Phương án:** SD1.5 local + diffusers (chọn) · **Chất lượng:** Tốt cho anime/2D sau khi fine-tune · **Chi phí:** Miễn phí, GPU 6–8 GB · **Chạy offline:** Có · **Kiểm soát (seed, LoRA, IP- Adapter, img2img):** Đầy đủ · **Lý do chọn / loại:** Phù hợp mục tiêu "chạy local trên Windows + NVIDIA", dữ liệu không rời máy
- **Phương án:** SDXL local · **Chất lượng:** Tốt hơn, 1024 px · **Chi phí:** VRAM 8–12 GB, chậm ~2–4 lần · **Chạy offline:** Có · **Kiểm soát (seed, LoRA, IP- Adapter, img2img):** Đầy đủ · **Lý do chọn / loại:** Vượt tầm GPU mục tiêu 6 GB; hệ sinh thái Hyper- SD/IP-Adapter bản sd15 đã tích hợp
- **Phương án:** API đóng (DALL·E, Midjourney, Gemini) · **Chất lượng:** Rất tốt · **Chi phí:** Trả phí theo ảnh, phụ thuộc mạng · **Chạy offline:** Không · **Kiểm soát (seed, LoRA, IP- Adapter, img2img):** Hạn chế (khó khóa nhân vật, seed) · **Lý do chọn / loại:** Dự án vẫn có nhánh `"Local Gemini (API)"` ( `image_generator.py:637-670` ) qua endpoint OpenAI-compatible, nhưng không phải mặc định
- **Phương án:** GAN (StyleGAN…) · **Chất lượng:** Sắc nhưng hẹp miền · **Chi phí:** Nhanh · **Chạy offline:** Có · **Kiểm soát (seed, LoRA, IP- Adapter, img2img):** Không điều kiện hoá text tự do · **Lý do chọn / loại:** Không sinh cảnh tuỳ ý theo câu truyện
- **Phương án:** Automatic1111 / ComfyUI làm backend · **Chất lượng:** Tốt · **Chi phí:** Thêm một server, phụ thuộc HTTP · **Chạy offline:** Có · **Kiểm soát (seed, LoRA, IP- Adapter, img2img):** Qua API · **Lý do chọn / loại:** Thêm tiến trình phải quản lý; dùng diffusers trực tiếp cho phép kiểm soát VRAM, LoRA, retry trong cùng process

Vì sao diffusers (HuggingFace) thay vì tự viết: cung cấp sẵn pipeline, scheduler đổi được bằng `from_config` , LoRA qua peft, IP-Adapter, CPU offload qua accelerate; dự án khoá phiên bản `diffusers==0.38.0` để tránh vỡ API.

Vì sao Hyper-SD 8 bước + CFG 5 thay vì 25 bước DPM++: một chương truyện có hàng chục cảnh, mỗi cảnh còn có thể có Face Detailer + upscale. Giảm bước khử nhiễu là đòn bẩy tốc độ lớn nhất. Chế độ "quality" (≥15 bước, DPM++ Karras, không Hyper- SD) vẫn giữ để chọn khi cần đẹp hơn ( `image_generator.py:391-414` ; `generate_batch(quality_mode=True)` ép ≥25 bước, CFG 7.0 ở `image_generator.py:828-830` ).

## 4. Hiện thực trong code

### 4.1 Bản đồ module

- **File:** `app/services/storytelling/image_generator.py` · **Vai trò:** `StorytellingPipeline` (singleton): nạp checkpoint, chọn chế độ scheduler/LoRA, encode prompt qua compel, sinh ảnh, phát hiện ảnh hỏng, giải phóng VRAM
- **File:** `app/services/storytelling/hardware_adapter.py` · **Vai trò:** Dò VRAM → chọn profile `cuda_high` / `cuda_low` /cpu → quyết định device, fp16, CPU offload
- **File:** `app/services/storytelling/style_lock.py` · **Vai trò:** Hàm thuần ghép prompt: style → hành động có trọng số → nội dung; lọc tag style LLM tự thêm
- **File:** `app/services/storytelling/orchestrator.py` · **Vai trò:** Vòng lặp sinh cảnh (luồng classic): chọn kích thước theo shot, lấy identity, gọi `generate_draft`
- **File:** `app/services/storytelling/image_gen_service.py` · **Vai trò:** `ImageGenOrchestrator` cho màn hình sinh ảnh riêng (3 "trạm": chuẩn bị prompt → sinh draft → upscale/xuất)
- **File:** `app/services/storytelling/postprocess.py` · **Vai trò:** Real-ESRGAN upscale ×4 rồi fit về 1920×1080
- **File:** `app/services/storytelling/face_detailer.py` · **Vai trò:** img2img vẽ lại mặt
- **File:** `app/config.py` · **Vai trò:** Mặc định `[storytelling]` , đọc đè từ `config.toml`

### 4.2 Hardware adapter: chọn cấu hình theo VRAM

`get_hardware_config()` ( `hardware_adapter.py:16-84` ):

```
if profile == "auto":
    ...
    vram_gb = vram_bytes / (1024 ** 3)
    if vram_gb >= 7.0:
                        # RTX 5060 8GB (hoặc các dòng GPU >= 8GB VRAM)
        resolved_profile = "cuda_high"
    else:
        resolved_profile = "cuda_low"
```

- **Profile:** Không CUDA, hoặc profile `"cpu"` · **sd_device:** cpu · **fp16:** False · **CPU offload:** False · **face / esrgan / whisper device:** cpu / cpu / cpu
- **Profile:** `cuda_high` (VRAM ≥ 7 GB) · **sd_device:** cuda · **fp16:** True · **CPU offload:** False (giữ model trên VRAM, nhanh) · **face / esrgan / whisper device:** cuda / cuda / cuda
- **Profile:** `cuda_low` (< 7 GB, hoặc lỗi khi dò VRAM) · **sd_device:** cuda · **fp16:** True · **CPU offload:** True · **face / esrgan / whisper device:** cpu / cuda / cpu (chừa VRAM cho SD)

Comment ở dòng 50 chỉ ghi "RTX 5060 8GB (hoặc các dòng GPU >= 8GB VRAM)"; việc đặt ngưỡng 7.0 thay vì 8.0 có thể là để chừa sai số vì `total_memory` của card "8 GB" thường báo dưới 8 GiB (đây là suy luận, code không ghi lý do). `hardware_profile` đọc từ config, mặc định `"auto"` ; orchestrator truyền `--hardware-profile` ( `orchestrator/pipeline.py:575-576` ).

4.3 Nạp pipeline: `_load_base_pipeline`

Các bước ( `image_generator.py:149-289` ):

- 1. Lấy `hw_config` , chọn `dtype` . 2. Ánh xạ alias checkpoint → repo-id; tên lạ không có `/` và không phải thư mục → `ValueError` rõ ràng (tránh lỗi 401 khó hiểu từ Hub). 3. Cache model ở `HF_HOME` hoặc `MediaComposer/storage/models` ; tắt `HF_HUB_ENABLE_HF_TRANSFER` .

- 4. `StableDiffusionPipeline.from_pretrained(checkpoint, torch_dtype=dtype, safety_checker=None, cache_dir=...)` — tắt safety checker (bộ lọc NSFW) để khỏi tốn VRAM và tránh ảnh đen do lọc nhầm. 5. Nạp IP-Adapter theo `identity_engine` (mặc định `"clip"` → `ip-adapter-plus-face_sd15.safetensors` , scale 0.6). 6. Nếu offload: `enable_model_cpu_offload()` + `vae.enable_slicing()` + `vae.disable_tiling()` ; nếu không: `.to(device)` .

Class là singleton có `threading.Lock` ( `image_generator.py:74-81` ): model ~2 GB chỉ nạp một lần cho cả batch; đổi checkpoint thì `release()` rồi nạp lại ( `image_generator.py:84-96` ). `image_gen_service.py:174-177` ghi rõ: không release sau mỗi batch nữa vì nạp lại tốn "~30-60s".

Trước khi nạp SD, luồng classic gọi `unload_local_llm()` để đẩy Ollama ra khỏi VRAM ( `orchestrator.py:366-369` ): trên GPU 6 GB, LLM (~3–5 GB) và SD không cùng tồn tại được.

4.4 Chọn chế độ Fast / Quality: `_configure_mode`

```
if num_steps >= QUALITY_MODE_MIN_STEPS:
                                          # 15
    mode_key = ("quality", None, self._char_lora_slug, style_key)
else:
    hyper_name = self._select_hyper_lora(num_steps, guidance_scale)
    mode_key = ("fast", hyper_name, self._char_lora_slug, style_key)
if mode_key == self._active_mode:
    return
```

( `image_generator.py:390-398` ). Ý tưởng: chỉ cấu hình lại khi "chìa khoá chế độ" đổi. Quality → `DPMSolverMultistepScheduler.from_config(..., use_karras_sigmas=True)` ; Fast → `EulerDiscreteScheduler` + nạp lazy Hyper- SD LoRA từ `ByteDance/Hyper-SD` . Sau đó gom danh sách adapter đang bật và gọi `set_adapters(active_adapters,` `adapter_weights)` .

Vì sao `set_adapters` thay vì `fuse_lora` : docstring nói rõ — bật/tắt adapter không ghi đè trọng số U-Net, nên chuyển qua lại Fast ↔ Quality an toàn ( `image_generator.py:383-386` ). Face Detailer lợi dụng điều này: tạm tắt Hyper-SD (vì Hyper-SD "chỉ hợp full-denoise từ nhiễu", `face_detailer.py:271` ), đổi sang DPM++ rồi `_restore_main_mode` sau đó.

Với giá trị thật (8, 5.0): Fast, Euler, `Hyper-SD15-8steps-CFG-lora.safetensors` .

### 4.5 Xây prompt: từ chuỗi đến embedding

- 1. Khóa style ( `style_lock.build_locked_prompt` , gọi ở `llm_prompter.py:189` ; fallback `"scenery, wide landscape, no` `humans"` ở dòng 217): `[style của truyện] + [(hànhđộng:1.35)] + [nội dungđã lọc]` . Sau đó `llm_prompter.py:209-211`

- còn chặn trần 75 từ ( `_clamp_prompt_words` ) để LLM không viết lan man. `strip_style_drift` loại các tag như `masterpiece` , `anime` , `cinematic lighting` , tên model… mà LLM tự chèn vào từng cảnh — docstring `style_lock.py:4-12` giải thích đây là "nguyên nhân chính của ảnh không đồng nhất chứ không phải seed". 2. Quality tags ( `_ensure_quality_tags` , `image_generator.py:556-569` ): chỉ thêm `"masterpiece, best quality, highres, "` nếu 120 ký tự đầu chưa có — tránh lặp và tránh đẩy tag không trọng số lên trước tag có trọng số. 3. Chuyển cú pháp A1111 `(tag:1.3)` → compel `(tag)1.3` ( `_a1111_to_compel` ). 4. Encode bằng compel, pad positive/negative cùng độ dài, truyền `prompt_embeds` + `negative_prompt_embeds` vào pipeline:

```
self._compel = Compel(
    tokenizer=self._pipe.tokenizer,
    text_encoder=self._pipe.text_encoder,
    truncate_long_prompts=False,
    device=str(exec_device),
)
pos_embeds = self._compel(prompt)
neg_embeds = self._compel(negative_prompt or "")
[pos_embeds, neg_embeds] = self._compel.pad_conditioning_tensors_to_same_length(
    [pos_embeds, neg_embeds]
)
return {"prompt_embeds": pos_embeds, "negative_prompt_embeds": neg_embeds}
```

( `image_generator.py:616-627` ). Chi tiết đáng nói: với CPU offload, `text_encoder.device` báo `cpu` lúc rảnh nên phải ép compel dùng `_execution_device` ( `image_generator.py:612-615` ). Pad cùng độ dài là bắt buộc vì CFG ghép positive/negative thành một batch.

Ví dụ style preset thật `resource/image_presets/thuy_mac.txt` :

```
thuymac ink wash style, (masterpiece, best quality:1.2), ink wash painting, monochrome grayscale, heavy black ink, dry brush strokes, bold
silhouette, high contrast, misty atmosphere, rice paper texture, generous negative space
---
(worst quality, low quality:1.4), 3d, photorealistic, photograph, saturated colors, colorful, rainbow, pastel, neon, bright even lighting,
cel shading, flat vector, glossy, plastic, busy background, cluttered, text, watermark, signature, logo, border, frame, letters, jpeg
artifacts
```

Phần trước `---` là positive ( `models.py:99-109` ), phần sau là negative ( `models.py:111-122` ); cả hai còn được nối thêm `learned_corrections` (tag người dùng đã "dạy" thêm/bớt). Có 16 preset trong `resource/image_presets/` , gồm `dreamshaper_cinematic` (tối ưu cho DreamShaper 8, UI `webui/index.html:445` ). Test `AIVoice/apps/MediaComposer/tests/test_style_preset_applied.py` đảm bảo preset mặc định tồn tại và mọi option trong dropdown UI khớp một file preset thật.

4.6 Sinh ảnh: `generate_draft`

Luồng ( `image_generator.py:676-747` ):

```
self.warmup(num_steps=num_steps, guidance_scale=guidance_scale)
if seed == -1:
    seed = torch.randint(0, 2147483647, (1,)).item()
self._set_vae_tiling(width, height)
kwargs = self._build_identity_kwargs(face_embedding, face_image, guidance_scale)
prompt_kwargs = self._build_prompt_kwargs(self._ensure_quality_tags(prompt), negative_prompt)
for attempt in range(DEAD_REGION_RETRIES + 1):
    generator = torch.Generator(device=self.device).manual_seed(seed)
    result = self._pipe(
        num_inference_steps=num_steps,
        guidance_scale=guidance_scale,
        width=width, height=height,
        generator=generator,
        **prompt_kwargs, **kwargs
    ).images[0]
    if not self.has_dead_region(result):
        break
    ...
         # đổi seed, thử lại tối đa DEAD_REGION_RETRIES = 2 lần
```

(rút gọn). Bên trong lời gọi `self._pipe(...)` diffusers thực hiện đúng lý thuyết mục 2:

- 1. Tạo latent nhiễu

- shape `[1, 4, H/8, W/8]` từ `generator` .

- 2. `scheduler.set_timesteps(8)` → chọn 8 mức . 3. Mỗi bước: nhân đôi latent (CFG) → U-Net dự đoán cho [negative, positive] (cross-attention với `prompt_embeds` , cộng thêm luồng IP-Adapter) → công thức CFG với

- → `scheduler.step` ra latent kế tiếp.

- 4. Chia latent cho scaling factor, `vae.decode` → ảnh pixel, chuyển sang `PIL` .

Giá trị fallback trong hàm ( `896×512` , `steps=2` , `guidance=0.0` , dòng 697–704) chỉ dùng khi config thiếu khoá; thực tế config luôn có `768×432` , `8` , `5.0` .

### 4.7 Identity khi cảnh không có nhân vật

Khi IP-Adapter đã gắn vào U-Net, pipeline bắt buộc nhận input ảnh. Nếu cảnh không có nhân vật, code truyền ảnh xám 224×224 và đặt scale = 0 ( `image_generator.py:544-546` ) — tức "tắt" ảnh hưởng mà không phải gỡ adapter. Engine FaceID thì truyền vector zero 512-d ( `image_generator.py:552-554` ). Đây là một chi tiết hay để khoe hiểu sâu.

### 4.8 Bug có thật: dải đen do VAE tiling + fp16

Docstring `_set_vae_tiling` ( `image_generator.py:291-304` ) ghi lại sự cố: batch 41 cảnh, 9 frame hỏng (22%), vùng đen luôn là dải dọc rộng đúng 512 hoặc 384 px trên khung 768. Phân tích: latent rộng 768/8 = 96, ô tiling 64 latent, chồng lấn 25% → bước 48 → hai ô pixel 0–512 và 384–768; khớp chính xác biên ô. Không có dải ngang → không phải model vẽ hỏng mà là một ô decode tràn số fp16 (đây là kết luận của nhóm dựa trên hình dạng lỗi, không có log NaN kèm theo).

Giải thích thêm vì sao chỉ có dải dọc: diffusers chỉ chia ô theo chiều nào vượt 64 latent. Chiều cao latent là 432/8 = 54 < 64 nên không bị cắt theo hàng; chỉ chiều rộng 96 > 64 bị cắt thành 2 ô → mọi lỗi của một ô đều hiện ra thành một dải dọc. Hình dạng lỗi vì vậy khớp hoàn toàn với hình học tiling.

Cách sửa gồm hai lớp:

- 1. Nguyên nhân gốc: chỉ bật tiling khi cạnh lớn nhất ≥ `VAE_TILING_MIN_EDGE = 1024` ( `image_generator.py:32, 308` ). Mọi kích thước dự án dùng (768×432, 576×704, 704×528) đều tắt tiling. 2. Lưới an toàn: `has_dead_region` ( `image_generator.py:317-337` ) — đổi ảnh sang xám, tìm cột/hàng mà mọi pixel ≤ 4 hoặc ≥ 251; nếu các cột (hoặc hàng) đó chiếm ≥ 4% chiều tương ứng → hỏng → sinh lại với seed mới, tối đa 2 lần; vẫn hỏng thì đẩy cảnh báo lên UI.

Vì sao "toàn bộ cột" mà không phải "nhiều pixel đen": tranh thủy mặc có mảng mực rất tối nhưng hiếm khi phủ kín trọn một cột từ trên xuống dưới. Test `AIVoice/apps/MediaComposer/tests/test_vae_dead_region.py` kiểm chứng cả hai: phát hiện dải 512/384 px, dải ngang, dải trắng; không báo nhầm ảnh mực tối; bỏ qua dải mảnh 8 px (~1% < 4%); và tiling tắt ở các kích thước dự án, bật ở 1024.

### 4.9 Giải phóng VRAM

- `free_vram_cache()` : `gc.collect()` + `torch.cuda.empty_cache()` giữa các batch, giữ model ( `image_generator.py:885-` `894` ). `release()` : gỡ LoRA, xoá `_pipe` , gc 2 lần, `torch.cuda.synchronize()` rồi `empty_cache()` + `ipc_collect()` ( `image_generator.py:896-933` ) — synchronize để tránh lỗi "CUDA illegal memory access" khi kernel còn chạy ngầm. `log_vram()` cảnh báo khi reserved > 92% VRAM vì driver Windows có thể "spill" sang RAM, chậm 2–3 lần ( `image_generator.py:865-883` ).

### 4.10 Sơ đồ toàn luồng text → image

### 4.11 Sequence diagram: một cảnh

## 5. Hạn chế & hướng phát triển

- **Hạn chế:** SD1.5 sinh ở 768×432, lệch độ phân giải huấn luyện 512; chi tiết kém khi mặt nhỏ · **Bằng chứng trong code:** `orchestrator.py:453-464` phải đổi khung cho cảnh cận · **Hướng phát triển:** SDXL / SD3 / FLUX khi có GPU mạnh hơn; hoặc hires-fix (sinh nhỏ → img2img ở kích thước lớn)
- **Hạn chế:** 8 bước Hyper-SD đánh đổi chi tiết lấy tốc độ · **Bằng chứng trong code:** `_select_hyper_lora` · **Hướng phát triển:** Cho người dùng chọn Quality mode (≥15 bước) trên UI cho cảnh quan trọng
- **Hạn chế:** CLIP 77 token + hiểu ngôn ngữ yếu (không đếm, không hiểu quan hệ không gian tốt) · **Bằng chứng trong code:** compel chỉ nối đoạn, không làm CLIP hiểu tốt hơn · **Hướng phát triển:** Model có text encoder lớn (T5 trong SD3/FLUX); ControlNet/pose để khóa bố cục
- **Hạn chế:** Đồng nhất nhân vật giữa các cảnh chưa tuyệt đối · **Bằng chứng trong code:** Nhiều lớp bù: IP-Adapter, LoRA nhân vật, Face Detailer · **Hướng phát triển:** Train LoRA nhân vật sớm hơn, dùng ControlNet reference
- **Hạn chế:** Không có inpainting thật · **Bằng chứng trong code:** `postprocess.py:68` stub · **Hướng phát triển:** Pipeline inpainting với mask từ detector để sửa tay/mặt
- **Hạn chế:** Tất định không tuyệt đối giữa máy khác nhau; seed đổi khi retry · **Bằng chứng trong code:** `image_generator.py:733-738` · **Hướng phát triển:** Lưu seed + toàn bộ tham số vào metadata cảnh
- **Hạn chế:** fp16 có nguy cơ tràn số VAE · **Bằng chứng trong code:** Bug dải đen 22% · **Hướng phát triển:** Dùng VAE fp16-fix (ví dụ `madebyollin/sdxl-vae-` `fp16-fix` cho SDXL, hoặc VAE chuẩn của SD1.5 ở fp32)
- **Hạn chế:** Không có benchmark tốc độ/chất lượng chính thức trong repo · **Bằng chứng trong code:** Chỉ có ghi chú "~3x" · **Hướng phát triển:** Bổ sung đo thời gian/cảnh, FID/CLIP-score trên tập cảnh mẫu
- **Hạn chế:** Cấu hình mặc định lệch nhau giữa `app/config.py` và `config.toml` (style LoRA, face detailer) · **Bằng chứng trong code:** mục 1.3 · **Hướng phát triển:** Hợp nhất một nguồn sự thật

## Câu hỏi hội đồng có thể hỏi

### 1. Diffusion model học cái gì?

Học dự đoán nhiễu đã được thêm vào ảnh ở mức , bằng loss MSE

Nhờ công thức đóng

- nên huấn luyện chỉ cần bốc ngẫu nhiên. Dự án không huấn luyện lại

SD, chỉ dùng checkpoint có sẵn (và LoRA).

### 2. "Stable Diffusion" khác diffusion thường ở điểm nào?

Là latent diffusion: khuếch tán trên latent VAE nén 8 lần mỗi chiều, 4 kênh. Ảnh 768×432 → latent 96×54×4, ít hơn ~48 lần giá trị → chạy được trên GPU 6 GB.

### 3. Text ảnh hưởng đến ảnh bằng cơ chế nào?

CLIP text encoder biến prompt thành 77×768; U-Net dùng cross- attention với Q từ feature ảnh, K/V từ text. Dự án encode qua compel để hỗ trợ trọng số `(tag:1.3)` và prompt > 77 token ( `image_generator.py:589-627` ).

### 4. CFG scale là gì, sao chọn 5.0?

- , càng lớn càng bám prompt nhưng dễ cháy màu. Dự án

dùng 5.0 với Hyper-SD CFG-LoRA; comment `app/config.py:46-50` ghi rằng 1.5 làm model bỏ qua prompt, ra texture trừu tượng.

### 5. Negative prompt hoạt động thế nào?

Thay nhánh "không điều kiện" trong CFG bằng embedding negative → đẩy ảnh ra xa khái niệm đó. Chỉ có tác dụng khi CFG > 1. Negative lấy từ phần sau `---` của file style preset.

### 6. Steps ảnh hưởng gì? Vì sao chỉ 8 bước?

Mỗi bước = 1 lần U-Net (x2 vì CFG). Ít bước thì nhanh nhưng mất chi tiết; dự án bù bằng Hyper-SD LoRA (chưng cất cho 1–8 bước) + Euler. Từ 15 bước trở lên, code tự chuyển sang DPM++ 2M Karras và bỏ Hyper-SD ( `QUALITY_MODE_MIN_STEPS = 15` ).

### 7. Euler và DPM++ khác nhau thế nào?

Cả hai giải ODE khử nhiễu. Euler bậc 1 (đi theo tiếp tuyến); DPM++ 2M bậc 2 multistep (dùng thêm bước trước để ước lượng độ cong), chính xác hơn với cùng số bước. Karras sigmas dồn bước vào vùng nhiễu thấp.

### 8. Seed có đảm bảo tái lập không?

Cùng seed + cùng mọi tham số + cùng phần cứng/phiên bản → gần như giống hệt. Code trả seed thực tế cùng ảnh. Nếu ảnh có dải chết, seed được đổi và sinh lại (tối đa 2 lần).

### 9. Vì sao chọn SD1.5 chứ không phải SDXL?

Mục tiêu GPU 6–8 GB (ngưỡng 7 GB trong `hardware_adapter.py:50` ); SDXL ~2.6B tham số U-Net, chạy 1024 px, nặng và chậm hơn nhiều. Hệ sinh thái anime + Hyper-SD + IP-Adapter bản sd15 sẵn có.

### 10. Làm sao chạy được trên GPU 6 GB?

fp16 (nửa bộ nhớ), SDPA attention, `enable_model_cpu_offload` + VAE slicing khi VRAM < 7 GB, unload Ollama trước khi nạp SD, sinh tuần tự từng ảnh, `empty_cache` giữa các batch.

### 11. Ảnh bị dải đen là do đâu, xử lý thế nào?

VAE tiling chia latent thành ô; một ô tràn số fp16 → cả dải đen (9/41 frame, dải rộng đúng 512/384 px khớp biên ô). Sửa: chỉ tiling khi cạnh ≥ 1024, thêm `has_dead_region` + retry với seed mới; có unit test `test_vae_dead_region.py` .

### 12. img2img và strength?

Encode ảnh → thêm nhiễu tới mức strength → khử nhiễu từ đó. Strength thấp giữ bố cục. Face Detailer dùng 0.45 (mặt nhỏ tăng lên 0.53, mặt to giảm còn 0.40; kẹp trong [0.30, 0.55]), unify pass 0.28, trần 0.45. Img2img pipeline dùng `from_pipe` chia sẻ component, không tốn thêm VRAM.

### 13. Dự án có dùng inpainting không?

Không có inpainting pipeline thật; stub ADetailer đã bỏ. Face Detailer thay thế bằng crop mặt → img2img → dán lại.

### 14. Checkpoint khác LoRA thế nào?

Checkpoint là toàn bộ trọng số (U-Net+VAE+text encoder, ~2 GB fp16); LoRA là phần bù hạng thấp

- vài chục MB, trộn được nhiều cái với trọng số qua `set_adapters` . Dự án có 5

checkpoint trong UI, mặc định anything-v5.

### 15. Vì sao tắt safety checker?

`safety_checker=None` ( `image_generator.py:204` ): tiết kiệm VRAM/thời gian và tránh ảnh bị bôi đen do lọc nhầm; nội dung đầu vào là truyện do người dùng kiểm soát. Cần nêu đây là đánh đổi có chủ ý.

### 16. Hyper-SD là gì, sao 8 bước vẫn ra ảnh?

Là LoRA được chưng cất từ SD1.5: mô hình "trò" học nhảy những bước khử nhiễu lớn mà mô hình "thầy" phải đi nhiều bước nhỏ. Vì là LoRA nên gắn được vào mọi checkpoint SD1.5. Code chọn biến thể 2/4/8 bước theo `num_steps` , và bản `8steps-CFG` khi `guidance_scale > 1.2` ( `image_generator.py:339-346` ).

### 17. U-Net biết đang ở bước nhiễu nào bằng cách nào?

Bước được mã hoá bằng sinusoidal embedding, qua MLP rồi cộng vào mọi ResNet block. Nhờ vậy cùng một mạng dùng được cho mọi mức nhiễu: ở lớn khử mạnh, quyết định bố cục; ở nhỏ tinh chỉnh chi tiết.

### 18. Vì sao dải đen chỉ là dải dọc?

Latent 96×54: chỉ chiều rộng 96 vượt kích thước ô 64 nên VAE tiling chỉ cắt theo cột; một ô hỏng hiện ra thành dải dọc 512 hoặc 384 px. Hình dạng này khớp đúng hình học tiling, nên nhóm kết luận lỗi nằm ở khâu decode chứ không phải ở U-Net.

## Tóm tắt 1 phút

"Khâu sinh ảnh của em dùng Stable Diffusion 1.5 chạy local qua thư viện diffusers. Nguyên lý của diffusion là: khi huấn luyện, người ta thêm nhiễu Gauss dần vào ảnh và dạy mạng U-Net đoán lại nhiễu đó bằng loss MSE; khi sinh, mô hình bắt đầu từ nhiễu thuần và khử nhiễu từng bước cho ra ảnh. Stable Diffusion làm việc này trong không gian latent của VAE, nén ảnh 8 lần mỗi chiều, nên ảnh 768×432 chỉ còn latent 96×54×4, nhờ vậy chạy được trên GPU 6 đến 8 GB. Prompt đi qua text encoder CLIP thành 77 vector, được bơm vào U-Net bằng cross-attention; em dùng compel để hỗ trợ trọng số và prompt dài. Classifier-free guidance với scale 5.0 giúp ảnh bám prompt, negative prompt đẩy ảnh khỏi các lỗi như chữ, watermark hay sai style. Để nhanh, em dùng 8 bước Euler kèm Hyper-SD LoRA; nếu tăng từ 15 bước trở lên thì hệ thống tự chuyển sang DPM++ Karras. Module hardware adapter đọc VRAM: từ 7 GB trở lên thì giữ model trên GPU ở fp16, dưới 7 GB thì bật CPU offload. Em cũng đã tìm ra và sửa lỗi dải đen do VAE tiling tràn số fp16, có unit test kiểm chứng. Ảnh draft sau đó được vẽ lại mặt nếu bật, rồi upscale bằng Real-ESRGAN lên 1080p để ghép video."
