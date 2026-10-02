# Chương 08. Bước 3c — LoRA, style lock & nhất quán nhân vật (training, face detail)

- Quy ước đường dẫn trong chương này. `MC/` = `AIVoice/apps/MediaComposer/` . Ví dụ `MC/app/services/storytelling/face_detailer.py:246` nghĩa là file đó, dòng 246. Mọi con số (rank, learning rate, trọng số, ngưỡng...) đều được đọc trực tiếp từ code/config, có trích dòng. Chỗ nào code chưa rõ hoặc có điểm lệch, chương này nói thẳng ra.

## 1. Vai trò trong hệ thống

### 1.1. Bài toán: "cùng một nhân vật, mỗi cảnh một khuôn mặt"

Chương 07 đã giải thích Stable Diffusion (SD1.5) sinh ảnh bằng cách khử nhiễu dần một latent ngẫu nhiên, được điều khiển bởi text prompt. Vấn đề là prompt chỉ mô tả được "loại" người, không mô tả được "đúng người đó". Prompt `1boy, black hair, red` `eyes, dark robe` khớp với hàng nghìn khuôn mặt; mỗi seed sẽ rút ra một khuôn mặt khác nhau. Với video kể chuyện 50–100 cảnh, khán giả sẽ thấy nhân vật chính "thay mặt" liên tục. Đây là vấn đề character consistency, vấn đề khó nhất khi làm truyện tranh/video bằng diffusion.

Ngoài ra còn có vấn đề thứ hai, ít người nghĩ tới nhưng dự án gặp thật: style drift. Mỗi frame ra một phong cách vì trong cùng một prompt có ba "tuyên bố style" chọi nhau (tag chất lượng chèn cứng, tag LLM tự viết, file style của truyện). Docstring `MC/app/services/storytelling/style_lock.py:1-19` ghi rõ đây là "nguyên nhân chính của ảnh không đồng nhất, chứ không phải seed".

Dự án xử lý hai bài toán này bằng bốn lớp cơ chế chồng lên nhau:

- **Lớp:** 1. Style lock mức prompt · **Giải quyết:** Style drift · **Cơ chế:** Ghép prompt theo thứ tự cố định, lọc tag style do LLM tự thêm · **File chính:** `style_lock.py` , `llm_prompter.py`
- **Lớp:** 2. Style LoRA · **Giải quyết:** Style drift (mức trọng số) · **Cơ chế:** LoRA phong cách "thủy mặc", bật cho MỌI ảnh · **File chính:** `scripts/train_style_lora.py` , `image_generator.py`
- **Lớp:** 3. Identity: IP-Adapter + Character LoRA · **Giải quyết:** Nhất quán khuôn mặt · **Cơ chế:** IP-Adapter nhận ảnh ref; LoRA nhân vật học riêng từng nhân vật chính · **File chính:** `character_bootstrap.py` , `lora_trainer.py` , `scripts/train_character_lora.py`
- **Lớp:** 4. Face Detailer · **Giải quyết:** Mặt nhỏ bị nát, lệch identity · **Cơ chế:** Detect mặt → crop → img2img độ phân giải cao → dán lại (giống ADetailer) · **File chính:** `face_detailer.py` , `scripts/detect_faces_cli.py`

Phụ trợ: `dataset_collector.py` (tự thu thập ảnh tốt vào dataset), `face_extractor.py` (InsightFace embedding cho engine FaceID).

### 1.2. Vị trí trong pipeline

Bước 3 (tạo video) chạy trong MediaComposer qua subprocess `adapter_video_cli.py` do orchestrator gọi. Trong Bước 3, chương này nằm ở khoảng giữa "LLM viết prompt" và "upscale/lắp video".

Input của khối này: danh sách `Scene` (có `image_prompt` , `characters_in_scene` , `primary_character` , `shot_type` ), `StoryContext` (checkpoint, danh sách `Character` với `keywords_en` , ảnh ref), file style preset ( `MC/resource/image_presets/*.txt` ).

Output: ảnh frame đã đồng nhất style và nhân vật; phụ phẩm là file LoRA `MC/resource/character_loras/<slug>.safetensors` + `<slug>.json` , dataset `characters/<slug>/dataset/*.png` ( `context_manager.py:302-306` ).

## 2. Nền tảng lý thuyết từ gốc

### 2.1. Nhắc lại: SD học gì khi train?

Trực giác: SD là một "người phục chế tranh". Ta đưa cho nó một bức tranh bị phủ nhiễu ở mức `t` , kèm mô tả bằng chữ, và bắt nó đoán lớp nhiễu đã phủ lên là gì. Đoán đúng nhiễu thì trừ nhiễu đi là ra tranh sạch.

Cơ chế (làm trong latent space, không phải pixel):

- 1. Ảnh `x` (512×512×3) qua VAE encoder → latent `z0` (64×64×4), nhân với `scaling_factor` của VAE (SD1.5 là 0.18215). 2. Chọn ngẫu nhiên timestep `t` ∈ `[0, T)` , `T` = `num_train_timesteps` (SD1.5 = 1000).

- 3. Sinh nhiễu Gauss `ε~N(0, I)` , tạo latent nhiễu:

```
z_t = sqrt(ᾱ_t) · z0 + sqrt(1 − ᾱ_t) · ε
```

- `ᾱ_t =Π_{s=1..t} (1 −β_s)` : tích lũy "lượng tín hiệu còn lại" tới bước `t` , với `β_s` là lịch nhiễu (noise schedule) cố định của scheduler; `t` nhỏ → `ᾱ_t≈1` (gần ảnh sạch), `t` lớn → `ᾱ_t≈0` (gần nhiễu thuần). Nhờ công thức đóng này, khi train ta nhảy thẳng tới bước `t` bất kỳ mà không phải thêm nhiễu tuần tự. 4. U-Net `ε_θ(z_t, t, c)` dự đoán nhiễu, với `c` là text embedding (CLIP text encoder, 77 token × 768 chiều). 5. Loss = MSE giữa nhiễu thật và nhiễu đoán:

```
L = || ε − ε_θ(z_t, t, c) ||²
```

Code dự án làm chính xác 5 bước này, xem `MC/scripts/train_character_lora.py:144,157-163` :

```
latent = vae.encode(px).latent_dist.sample() * vae.config.scaling_factor
...
noise = torch.randn_like(latent)
timestep = torch.randint(0, noise_scheduler.config.num_train_timesteps, (1,), device=device)
noisy_latent = noise_scheduler.add_noise(latent, noise, timestep)
```

```
with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=(device == "cuda")):
    noise_pred = unet(noisy_latent, timestep, encoder_hidden_states=encoder_hidden_states).sample
    loss = F.mse_loss(noise_pred.float(), noise.float()) / args.grad_accum
```

`noise_scheduler.add_noise` là công thức ở bước 3; `F.mse_loss` là loss ở bước 5. Như vậy fine-tune để học nhân vật mới chính là tiếp tục bài toán đoán nhiễu, nhưng trên ảnh của nhân vật đó, kèm prompt mô tả nhân vật đó. Sau khi train, khi gặp prompt đó, U-Net "kéo" quá trình khử nhiễu về phía khuôn mặt đã học.

### 2.2. Vì sao không fine-tune toàn bộ model?

U-Net SD1.5 có khoảng 860 triệu tham số. Fine-tune toàn bộ (full fine-tuning) nghĩa là:

- Cần lưu trọng số + gradient + trạng thái optimizer AdamW (2 moment) cho 860M tham số: ở fp32 là 4 × 3,4GB ≈ 14GB chỉ riêng phần này, chưa tính activation, VAE, text encoder → không vừa GPU 6GB của sinh viên. Mỗi nhân vật ra một bản model ~2–4GB → 10 nhân vật = 40GB đĩa, và mỗi lần đổi nhân vật phải nạp lại cả model. Dễ catastrophic forgetting: 15 ảnh mà cập nhật 860M tham số thì model quên cách vẽ thứ khác.

Cần một cách "chỉnh ít mà trúng". Đó là LoRA.

### 2.3. LoRA — Low-Rank Adaptation

Trực giác/ẩn dụ. Tưởng tượng một ma trận trọng số `W` là một bảng tra cứu khổng lồ 320×320. Để dạy model một khuôn mặt mới, ta không cần viết lại cả bảng; ta chỉ cần "một vài hướng điều chỉnh" — ví dụ "kéo đặc trưng mắt về phía đỏ", "tóc về phía bạc". Số hướng cần thiết rất ít so với kích thước bảng. LoRA chính là giả thuyết: phần thay đổi ΔW khi fine-tune có "rank thấp" (Hu et al., 2021), tức có thể biểu diễn bằng tích của hai ma trận mỏng.

Cơ chế. Với một lớp tuyến tính `h = W0 · x` , với `W0` ∈ `R^{d×k}` bị đóng băng, LoRA thêm một nhánh song song:

```
h = W0 · x + (α / r) · B · A · x
```

- `A` ∈ `R^{r×k}` : ma trận "nén" (down-projection), chiếu input `k` chiều xuống `r` chiều. `B` ∈ `R^{d×r}` : ma trận "giãn" (up-projection), chiếu từ `r` chiều lên `d` chiều. `r` (rank): số "hướng điều chỉnh", thường 4–32, rất nhỏ so với `d, k` (320–1280). `α` (alpha): hệ số scale; hệ số thực tế nhân vào là `α/ r` . Khởi tạo: `A` ngẫu nhiên Gauss, `B = 0` → lúc bắt đầu `B·A = 0` , model y hệt bản gốc, train từ từ "mở" nhánh LoRA ra. Code dùng `init_lora_weights="gaussian"` ( `train_character_lora.py:114` ) — trong PEFT tuỳ chọn này khởi tạo `A~N(0, 1/r)` và `B = 0` (mặc định `True` của PEFT dùng Kaiming-uniform cho `A` ; cả hai đều giữ `B = 0` ).

Vì sao ít tham số? Ma trận đầy đủ `d×k` có `d·k` tham số; LoRA chỉ có `r·(d + k)` . Ví dụ thật lấy từ file `thuy_mac.safetensors` của dự án (tôi đã đọc header safetensors): lớp `down_blocks.0...attn1.to_q` có `lora.down.weight` shape `[8, 320]` và `lora.up.weight` shape `[320, 8]` :

- Số tham số

- Ma trận gốc `to_q` 320×320

- 102.400

- LoRA rank 8: 8×320 + 320×8

- 5.120 (5%)

Toàn bộ file `thuy_mac.safetensors` (rank 8): 256 tensor = 128 cặp (A, B), tổng 1.594.368 tham số, dtype F32, file 6.414.992 byte (≈ 1,59M × 4 byte). So với 860M tham số U-Net, đó là ≈ 0,19%. LoRA nhân vật rank 16 gấp đôi: ≈ 3,19M tham số (≈ 0,37%), file ≈ 12–13MB — khớp README "rank 16 chỉ ~10–40MB → commit thẳng vào git" ( `MC/resource/character_loras/README.md` ).

Gắn vào lớp nào? Code: `target_modules=["to_k", "to_q", "to_v", "to_out.0"]` ( `train_character_lora.py:115` , `train_style_lora.py:274` ). Đây là 4 phép chiếu của attention trong các `transformer_blocks` của U-Net:

- `attn1` = self-attention: pixel latent "nhìn" các pixel latent khác → quyết định bố cục, nét vẽ, texture (quan trọng cho style).

- `attn2` = cross-attention: Query từ ảnh, Key/Value từ text embedding → đây là chỗ chữ gặp hình, nơi token "silver hair" được ánh xạ thành đặc trưng thị giác (quan trọng cho nhân vật). Ở `attn2` , `to_k` / `to_v` nhận input 768 chiều (text), nên LoRA ở đây trực tiếp đổi "từ này nghĩa là hình gì".

Đếm từ header: 64 tensor cho mỗi loại `to_q` , `to_k` , `to_v` , `to_out.0` → 16 transformer block × 2 attention (attn1 + attn2) × 4 projection × 2 ma trận (A, B) = 256 tensor. Khớp.

Chỉ attention (không đụng ResNet/conv) là lựa chọn chuẩn của recipe diffusers/PEFT: attention là nơi conditioning đi vào, đủ để học identity/style, file nhỏ, ít phá khả năng vẽ tổng quát.

Vì sao rank thấp vẫn đủ? Học một khuôn mặt hay một nét vẽ là "chỉnh hướng" trong không gian đặc trưng đã có sẵn — model gốc đã biết vẽ tóc, mắt, mực; chỉ cần dịch chuyển trong một không gian con nhỏ. Dự án chọn rank khác nhau có chủ đích:

- Nhân vật rank 16 ( `train_character_lora.py:48` ) — cần chi tiết khuôn mặt. Phong cách rank 8 ( `train_style_lora.py:81-82` ) — docstring: "Phong cách là tín hiệu tần số thấp; rank 8 là đủ và ít bám nội dung hơn rank 16-32" ( `train_style_lora.py:16-17` ).

Alpha trong dự án: `lora_alpha=args.rank` (cả hai script) → `α/r = 1` . Nghĩa là hệ số scale khi train bằng 1; mức "mạnh/yếu" được điều khiển hoàn toàn bởi adapter weight lúc inference (mục 2.6).

### 2.4. Vòng lặp training: dataset, caption, trigger word, learning rate

Dataset và caption. LoRA học mối liên hệ "caption → hình". Caption quyết định LoRA học CÁI GÌ:

- Nhân vật dùng một caption chung cho mọi ảnh: `f"masterpiece, best quality, {args.instance_prompt}"` ( `train_character_lora.py:132` ). Vì mọi ảnh cùng một nhân vật với cùng một mô tả, mọi thứ chung giữa các ảnh (khuôn mặt, tóc, trang phục) sẽ được "gắn" vào đúng các tag đó. Đây là tinh thần DreamBooth ("instance prompt"). Phong cách dùng caption riêng cho từng ảnh, luôn mở đầu bằng trigger token chung: `samples.append((img, f"` `{style_token}, {caption}"))` ( `train_style_lora.py:124` ). Lý do (docstring `train_style_lora.py:7-12` ): nếu dùng chung caption, model học luôn NỘI DUNG. Khi mỗi caption đã mô tả nội dung riêng ("a man walking on a stone bridge..."), phần duy nhất không được caption giải thích là cách vẽ → phần đó dồn vào trigger token `thuymac ink wash style` .

Đây là nguyên lý quan trọng để trả lời hội đồng: "cái gì không được caption mô tả thì model gán vào trigger/tag chung".

Trigger word. `instance_prompt` của nhân vật được tự sinh bởi `build_instance_prompt` ( `lora_trainer.py:17-28` ): lấy `keywords_en` , bỏ các tag góc máy ( `upper body` , `portrait` , `close up` , `full body` ...), lấy tối đa 12 tag; nếu trống thì `"1person"` . Bỏ tag góc máy để LoRA không học "nhân vật này luôn là chân dung". Lưu ý: dự án không dùng rare token kiểu `sks` như DreamBooth gốc — trigger chính là tổ hợp tag ngoại hình.

Tiền xử lý ảnh. Resize cạnh ngắn về 512 giữ tỉ lệ, center-crop 512×512 ( `train_character_lora.py:64-71` ). Latent được encode một lần trước rồi VAE chuyển về CPU ( `:139-147` ) — tiết kiệm VRAM vì trong loop không cần VAE.

Augmentation: lật ngang ngẫu nhiên 50% ở mức latent ( `torch.flip(latent, dims=[3])` , `:154-155` ). Đây là xấp xỉ (VAE gần như đồng biến với phép lật), rẻ hơn encode lại.

Siêu tham số thật:

- **Tham số:** Base checkpoint mặc định · **LoRA nhân vật:** `stablediffusionapi/anything-v5` (hoặc checkpoint của context) · **LoRA phong cách:** `stablediffusionapi/anything-v5` · **Nguồn:** `train_character_lora.py:37` , `train_style_lora.py:63`
- **Tham số:** Rank / alpha · **LoRA nhân vật:** 16 / 16 · **LoRA phong cách:** 8 / 8 · **Nguồn:** `:48,113` / `:81,273`
- **Tham số:** Learning rate · **LoRA nhân vật:** 1e-4 · **LoRA phong cách:** 8e-5 · **Nguồn:** `:49` / `:83`
- **Tham số:** Optimizer · **LoRA nhân vật:** AdamW, weight_decay 1e-2 · **LoRA phong cách:** AdamW, weight_decay 1e-2 · **Nguồn:** `:128` / `:298`
- **Tham số:** Resolution · **LoRA nhân vật:** 512 · **LoRA phong cách:** 512 · **Nguồn:** `:50` / `:84`
- **Tham số:** Batch / grad_accum · **LoRA nhân vật:** 1 / 4 (batch hiệu dụng 4) · **LoRA phong cách:** 1 / 4 · **Nguồn:** `:51` / `:85`
- **Tham số:** Steps · **LoRA nhân vật:** mặc định script 800; `train_character` tự chọn 600/800/1000 theo số ảnh; Studio auto-train 700 · **LoRA phong cách:** 1500 · **Nguồn:** `lora_trainer.py:68-74` , `config.py:113` , `train_style_lora.py:79`
- **Tham số:** Grad clipping · **LoRA nhân vật:** 1.0 · **LoRA phong cách:** 1.0 · **Nguồn:** `:169` / `:327`
- **Tham số:** Mixed precision · **LoRA nhân vật:** UNet fp32 + autocast fp16 + GradScaler · **LoRA phong cách:** UNet fp16, LoRA params ép fp32, autocast + GradScaler · **Nguồn:** `:129,161` / `:282-290,299,317`
- **Tham số:** Gradient checkpointing · **LoRA nhân vật:** bật · **LoRA phong cách:** bật · **Nguồn:** `:118` / `:277`
- **Tham số:** Seed · **LoRA nhân vật:** 42 · **LoRA phong cách:** 42 · **Nguồn:** `:52` / `:86`
- **Tham số:** Số ảnh tối thiểu · **LoRA nhân vật:** 5 (khuyến nghị 10–20) · **LoRA phong cách:** 15 (khuyến nghị 40–80) · **Nguồn:** `:60` / `:65`

Chú ý: vì `grad_accum=4` , cứ 4 step mới cập nhật trọng số một lần ( `if step%args.grad_accum==0` , `:167` ). 700 step = 175 lần cập nhật optimizer, mỗi lần dùng gradient trung bình của 4 mẫu.

Learning rate — trực giác. LR là "độ dài bước chân" khi đi xuống dốc loss. LoRA dùng LR (1e-4) cao hơn full fine-tune (DreamBooth full thường khoảng 1e-6 – 5e-6) vì chỉ có vài triệu tham số mới, `B` bắt đầu từ 0, cần bước đủ lớn để học kịp trong vài trăm cập nhật; còn full fine-tune đụng vào trọng số đã tốt sẵn nên bước phải rất nhỏ để không phá model. Phong cách dùng LR thấp hơn (8e-5) nhưng train nhiều bước hơn (1500): docstring chỉ ghi "Rank thấp hơn, LR thấp hơn" ( `train_style_lora.py:16` ), lý do cụ thể cho LR không được ghi — cách hiểu hợp lý là học chậm, đều trên dataset đa dạng để không "nhớ" từng ảnh.

Gradient checkpointing ( `unet.enable_gradient_checkpointing()` , `train_character_lora.py:118` , `train_style_lora.py:277` ): không lưu toàn bộ activation của forward pass mà tính lại khi backward → đổi thêm ~20–30% thời gian lấy lượng VRAM activation giảm mạnh. Đây là một trong các lý do train được trên GPU 6GB.

Mixed precision & bài học VRAM. Docstring `train_style_lora.py:40-46` ghi lại một bài học thực tế: nạp UNet fp32 (~3,4GB) + VAE + text encoder trên GPU 6GB → tràn sang shared memory, chậm hàng chục lần mà không crash. Giải pháp: pha 1 encode latent + caption rồi xoá hẳn VAE/text encoder ( `:261-265` ), pha 2 chỉ UNet fp16 (~1,7GB), riêng tham số LoRA ép lại fp32 ( `cast_training_params` , `:285-290` ) vì "để fp16 thì bước cập nhật của AdamW mất chính xác và loss sẽ đứng yên". Có thêm `SingleRunLock` ( `:140-176` ) chặn 2 tiến trình train cùng lúc. Script nhân vật thì vẫn nạp UNet fp32 + autocast (docstring ghi ~5GB, `train_character_lora.py:20` ).

Lưu kết quả. `get_peft_model_state_dict(unet)` → `convert_state_dict_to_diffusers` → `StableDiffusionPipeline.save_lora_weights(..., safe_serialization=True)` ( `train_character_lora.py:179-188` ). Định dạng `.safetensors` (chỉ chứa tensor, không chứa code pickle → an toàn khi chia sẻ).

### 2.5. Các phương án khác để giữ identity

(a) Full fine-tuning / DreamBooth. DreamBooth (Ruiz et al., 2022) fine-tune U-Net (thường toàn bộ) với 3–5 ảnh, gắn nhân vật vào một rare token ( `sks` ), thêm prior preservation loss: đồng thời train trên ảnh do chính model gốc sinh cho lớp chung ("a man") để model không quên lớp đó. Chất lượng cao nhưng nặng. Dự án gọi LoRA nhân vật là "DreamBooth-style" ( `train_character_lora.py:41` ) vì dùng instance prompt chung — nhưng không có prior preservation và không dùng rare token. Đây là LoRA + tinh thần DreamBooth.

(b) Textual Inversion. Chỉ học một embedding mới cho một token giả (với SD1.5, vector 768 chiều), toàn bộ model đóng băng. Cực nhẹ (vài KB) nhưng sức biểu đạt thấp: chỉ "tìm một từ" trong không gian model đã có, khó ghi lại chi tiết khuôn mặt anime cụ thể.

(c) IP-Adapter (dự án đang dùng song song). Không train gì cho từng nhân vật. Một adapter đã train sẵn nhận ảnh tham chiếu, mã hoá bằng CLIP image encoder, rồi đưa vào U-Net qua decoupled cross-attention: ngoài cặp Key/Value từ text, mỗi lớp cross-attention có thêm cặp Key/Value riêng cho đặc trưng ảnh:

```
Z = Attention(Q, K_text, V_text) + λ · Attention(Q, K_img, V_img)
```

với `λ` = `ip_adapter_scale` . Chỉ các ma trận chiếu `W_k', W_v'` cho nhánh ảnh (và bộ chiếu đặc trưng ảnh) được train khi làm ra adapter; U-Net và text encoder giữ nguyên, nên cùng một adapter dùng được cho mọi nhân vật. Bản Plus không dùng một vector ảnh duy nhất mà lấy đặc trưng mức patch của CLIP ViT-H (lớp áp chót) rồi nén qua một resampler kiểu Perceiver thành 16 token ảnh → giữ chi tiết tốt hơn; bản plus-face được train trên ảnh crop mặt. Dự án nạp `h94/IP-Adapter` , `models/ip-` `adapter-plus-face_sd15.safetensors` ( `image_generator.py:256-260` ), `λ` mặc định 0.6 ( `config.py:67` ). Ưu: zero-shot, dùng ngay. Nhược: giữ "cảm giác" khuôn mặt nhưng không chắc chắn chi tiết; `λ` cao thì cứng pose/ép bố cục theo ảnh ref.

(d) IP-Adapter FaceID / InstantID / PhotoMaker. Dùng face-recognition embedding (ArcFace) thay vì CLIP. Rất tốt với mặt người thật, kém với anime vì model nhận dạng mặt được train trên ảnh người thật. Dự án có engine `faceid` ( `image_generator.py:218-251` , nạp thêm FaceID LoRA với trọng số 0.65), nhưng mặc định `identity_engine = "clip"` ( `config.py:56` ) với ghi chú "faceid chỉ hiệu quả với ảnh mặt người thật".

(e) ControlNet reference / inpainting reference. Điều khiển bằng bản đồ cấu trúc (pose, canny...) — kiểm soát tư thế tốt nhưng không mang identity. Dự án không dùng.

### 2.6. LoRA lúc inference: weight và ghép nhiều LoRA

Khi nạp nhiều LoRA, trọng số hiệu dụng của mỗi lớp là:

```
W = W0 + Σ_i w_i · (α_i / r_i) · B_i · A_i
```

- `w_i` là adapter weight truyền vào `set_adapters` . `w = 0` = tắt, `w = 1` = đúng như lúc train, `w > 1` = khuếch đại. Các ΔW cộng tuyến tính. Vì vậy hai LoRA có thể "giằng co" trên cùng một lớp — style LoRA quá mạnh có thể nuốt identity và ngược lại.

Fuse vs set_adapters. "Merge/fuse" nghĩa là cộng hẳn ΔW vào `W0` (nhanh hơn một chút khi chạy). Dự án cố ý không fuse, dùng `set_adapters` để bật/tắt động — docstring `image_generator.py:383-386` : "Dùng set_adapters (bật/tắt) thay cho fuse/unfuse để chuyển chế độ an toàn, không làm hỏng trọng số UNet khi chuyển qua lại Fast <-> Quality". Cách giải thích kỹ thuật (suy luận, docstring không nói chi tiết): fuse là `W0←W0 +ΔW` , unfuse là trừ ngược lại; làm lặp đi lặp lại trong fp16 thì sai số làm tròn tích lũy dần vào `W0` . Với `set_adapters` , `W0` không bao giờ bị ghi đè — nhánh LoRA chỉ được cộng vào lúc forward, đổi trọng số/tắt bật gần như tức thì.

### 2.7. Phát hiện khuôn mặt

LBP cascade (dự án dùng cho mặt anime). Detector là `lbpcascade_animeface.xml` của nagadomi ( `face_detailer.py:27-31` ), chạy bằng OpenCV `CascadeClassifier` .

- LBP (Local Binary Pattern): với mỗi pixel, so sánh với 8 pixel lân cận: lân cận ≥ tâm → bit 1, ngược lại → 0 → được mã 8 bit mô tả "texture cục bộ" (cạnh, góc, vùng phẳng). Vì chỉ so sánh lớn/nhỏ nên bất biến với thay đổi độ sáng đơn điệu (cả ảnh sáng lên/tối đi không đổi mã). Chính xác hơn: cascade LBP của OpenCV dùng biến thể Multi-Block LBP — so sánh trung bình của các khối chữ nhật 3×3 thay vì từng pixel, tính nhanh bằng integral image. Cascade (khung Viola–Jones): một chuỗi các tầng (stage), mỗi tầng là tổ hợp boosting của nhiều bộ phân loại yếu (cây quyết định nhỏ trên đặc trưng LBP). Cửa sổ trượt khắp ảnh; tầng đầu rất rẻ loại nhanh vùng "chắc chắn không phải mặt", chỉ vùng khó mới đi tới tầng sau → nhanh, chạy CPU. File `resource/models/lbpcascade_animeface.xml` trên máy là

- 253.638 byte (~250KB). Viola–Jones gốc dùng đặc trưng Haar; LBP thay Haar bằng đặc trưng nhị phân, train và chạy nhanh hơn. Multi-scale: ảnh được thu nhỏ dần theo hệ số `scaleFactor` (image pyramid), mỗi mức chạy cửa sổ kích thước cố định → phát hiện mặt nhiều kích thước. Tham số thật ( `MC/scripts/detect_faces_cli.py:43-45` ): chuyển xám, `equalizeHist` (cân bằng histogram), `detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5, minSize=(28, 28))` . `scaleFactor=1.08` = mỗi mức pyramid chia kích thước cho 1,08 (nhỏ đi ~7–8%; mịn, chính xác hơn, chậm hơn mức phổ biến 1.1–1.3); `minNeighbors=5` = một ứng viên phải có ít nhất 5 cửa sổ "hàng xóm" chồng lên nhau (ở các vị trí/tỉ lệ lân cận) mới được giữ (giảm false positive); `minSize` 28×28px. Script còn gọi `cv2.setNumThreads(1)` ( `:31` ) để giảm rủi ro xung đột luồng. Output: JSON list bbox `[x, y, w, h]` sắp theo diện tích giảm dần ( `:51-56` ). Hạn chế: cascade là kỹ thuật cổ điển (trước deep learning), hay miss với style phẳng/góc nghiêng — code tự thừa nhận ở `character_bootstrap.py:82-84` .

Vì sao chạy trong subprocess? `face_detailer.py:90-93` và `detect_faces_cli.py:1-9` : OpenCV `detectMultiScale` và PyTorch cùng nạp OpenMP runtime ( `libiomp5md.dll` ) trong một process trên Windows → crash native, process bị kill không traceback. Giải pháp: script con chỉ import `cv2` / `numpy` , giao tiếp bằng file PNG tạm + JSON trên stdout, timeout 60s ( `face_detailer.py:106-118` ). "Tiến trình con có chết cũng chỉ mất bước detect, app không sập."

InsightFace (cho engine FaceID). `face_extractor.py:12-26` nạp `FaceAnalysis(name='buffalo_l')` với `det_size=(640, 640)` (bộ model `buffalo_l` của InsightFace gồm detector SCRFD và model nhận dạng ResNet-50 train bằng loss ArcFace; ArcFace là additive angular margin loss, ép các embedding cùng người tụm lại trên mặt cầu đơn vị). Lấy mặt lớn nhất, lưu `face.normed_embedding` (vector 512 chiều đã chuẩn hoá L2) ra `face.ipadpt.npy` ( `MC/webui/Main.py:1090-1092` ). Chỉ dùng khi `identity_engine="faceid"` .

### 2.8. Face Detailer — vì sao mặt nhỏ bị nát và cách sửa

Nguyên nhân gốc. SD1.5 làm việc trên latent 1/8 kích thước ảnh. Ảnh 768×432 → latent 96×54. Một khuôn mặt cao 60px trong ảnh chỉ chiếm ~7×7 ô latent — không đủ "chỗ" để vẽ mắt, mũi, miệng rõ ràng. Kết quả: mặt méo, mắt lệch.

Ý tưởng (giống ADetailer của A1111): crop vùng mặt, phóng lên 512×512 (giờ mặt chiếm cả latent 64×64), cho SD vẽ lại ở độ phân giải cao, rồi thu nhỏ và dán về chỗ cũ.

img2img và strength. Thay vì bắt đầu từ nhiễu thuần, img2img encode ảnh crop thành latent `z0` , thêm nhiễu tới timestep ứng với `strength` (dùng đúng công thức `z_t` ở mục 2.1), rồi chỉ chạy phần cuối của lịch khử nhiễu. `strength = 0.45` nghĩa là bỏ qua ~55% đầu của lịch (phần quyết định bố cục thô) và chỉ chạy ~45% cuối (phần vẽ chi tiết) → bố cục, hướng mặt, màu chính được giữ, nét mắt/mũi/miệng được vẽ lại. Lưu ý đây không phải "giữ đúng 55% pixel" — quan hệ giữa strength và độ giống ảnh gốc là phi tuyến. Trong diffusers số bước thực chạy = `int(steps × strength)` (14 × 0.45 → 6 bước). Strength thấp → sửa nhẹ; cao → vẽ lại nhiều, dễ lệch khỏi ảnh gốc.

Dán lại không lộ vết. Dùng feather mask: ellipse trắng, làm mờ Gauss ở mép → vùng giữa lấy mặt mới 100%, mép chuyển dần sang ảnh cũ. Kèm color matching để mặt mới không lệch tông.

### 2.9. CLIP similarity — thước đo "giống nhau"

CLIP image encoder biến một ảnh thành vector embedding; hai ảnh có nội dung/đặc điểm thị giác giống nhau cho vector gần nhau. Độ giống đo bằng cosine similarity:

`sim(a, b) = (a · b) / (||a||·||b||)` ∈ [−1, 1]

Dự án dùng CLIP image encoder đi kèm IP-Adapter đang nạp sẵn ( `pipe._pipe.image_encoder` + `feature_extractor` ) — không nạp thêm model chỉ để đo ( `dataset_collector.py:137-155` , `face_detailer.py:154-177` ). Công thức ở `dataset_collector.py:178-181` và `face_detailer.py:174` (thêm `1e-8` tránh chia 0). Cần hiểu hạn chế: CLIP đo "tương đồng ngữ nghĩa/thị giác" chung, không phải model nhận dạng khuôn mặt chuyên dụng — nên các ngưỡng (0.55, 0.60) là ngưỡng thực nghiệm.

## 3. Vì sao chọn các công nghệ này

- **Phương án:** Chỉ prompt · **Chi phí train:** 0 · **Kích thước:** 0 · **Identity anime:** Kém · **Linh hoạt pose:** Tốt · **Hợp GPU 6GB:** Có · **Dự án dùng?:** Là nền
- **Phương án:** Full fine-tune / DreamBooth · **Chi phí train:** Rất cao · **Kích thước:** 2–4GB/nhân vật · **Identity anime:** Rất tốt · **Linh hoạt pose:** Tốt · **Hợp GPU 6GB:** Không · **Dự án dùng?:** Không
- **Phương án:** Textual Inversion · **Chi phí train:** Thấp · **Kích thước:** vài KB · **Identity anime:** Trung bình-kém · **Linh hoạt pose:** Tốt · **Hợp GPU 6GB:** Có · **Dự án dùng?:** Không
- **Phương án:** IP-Adapter Plus Face (CLIP) · **Chi phí train:** 0 (zero-shot) · **Kích thước:** adapter ~100MB + CLIP image encoder ViT- H (cỡ GB) dùng chung (số MB chưa đo trên máy) · **Identity anime:** Khá · **Linh hoạt pose:** Hơi cứng · **Hợp GPU 6GB:** Có · **Dự án dùng?:** Có (mặc định)
- **Phương án:** IP-Adapter FaceID · **Chi phí train:** 0 · **Kích thước:** dùng chung · **Identity anime:** Kém với anime · **Linh hoạt pose:** Khá · **Hợp GPU 6GB:** Có · **Dự án dùng?:** Có (tuỳ chọn)
- **Phương án:** LoRA nhân vật · **Chi phí train:** Trung bình (vài phút–chục phút) · **Kích thước:** ~12MB · **Identity anime:** Tốt · **Linh hoạt pose:** Tốt · **Hợp GPU 6GB:** Có (~5GB) · **Dự án dùng?:** Có
- **Phương án:** LoRA phong cách · **Chi phí train:** 35–50 phút (1500 step, RTX 3060) · **Kích thước:** ~6MB · **Identity anime:** — (style) · **Linh hoạt pose:** — · **Hợp GPU 6GB:** Có (~3,5GB) · **Dự án dùng?:** Có

Lập luận để trình bày:

1. Kết hợp IP-Adapter + LoRA thay vì chọn một: IP-Adapter dùng được ngay từ cảnh đầu tiên (chưa có dữ liệu), LoRA mạnh hơn khi đã có dữ liệu. Chú thích trong code: "LoRA nhân vật (nếu đã train) — giữ identity mạnh hơn IP-Adapter" ( `orchestrator.py:450` , `image_gen_service.py:116` ). 2. LoRA thay DreamBooth full: vừa GPU 6GB, file nhỏ commit được vào git, swap nhân vật chỉ là đổi adapter không reload model ( `image_generator.py:348-357` ). 3. IP-Adapter CLIP thay FaceID: truyện là anime/tranh vẽ; ArcFace không nhận dạng tốt mặt vẽ. 4. LBP cascade thay detector deep learning: chạy CPU, ~250KB, tự tải, chuyên cho mặt anime; đánh đổi là hay miss — code có fallback ở mọi chỗ gọi. 5. Style LoRA + style lock prompt: prompt chỉ "đề nghị" style, LoRA "khoá" style ở mức trọng số.

## 4. Hiện thực trong code

### 4.1. Bản đồ module

- **File:** `MC/app/services/storytelling/style_lock.py` (127 dòng) · **Vai trò:** Khoá style mức prompt, hàm thuần · **Hàm chính:** `strip_style_drift` , `dedupe_against` , `weight_action` , `build_locked_prompt`
- **File:** `MC/app/services/storytelling/character_bootstrap.py` (228) · **Vai trò:** Tự sinh ref + dataset + train cho nhân vật chính · **Hàm chính:** `has_trained_lora` , `generate_seed_ref` , `generate_dataset` , `bootstrap_and_train` , `auto_train_leads`
- **File:** `MC/app/services/storytelling/lora_trainer.py` (151) · **Vai trò:** Bọc script train thành subprocess, quản trạng thái · **Hàm chính:** `build_instance_prompt` , `get_trainable_characters` , `train_character`
- **File:** `MC/scripts/train_character_lora.py` (198) · **Vai trò:** Script train LoRA nhân vật · **Hàm chính:** `main`
- **File:** `MC/scripts/train_style_lora.py` (375) · **Vai trò:** Script train LoRA phong cách · **Hàm chính:** `load_dataset` , `SingleRunLock` , `main`
- **File:** `MC/scripts/build_style_dataset.py` (380) · **Vai trò:** Dựng dataset thủy mặc từ Met Open Access (CC0) · **Hàm chính:** `is_usable` , `build_caption` , `tile_reject_reason` , `tiles_from`
- **File:** `MC/scripts/style_weight_sweep.py` (87) · **Vai trò:** Quét trọng số style LoRA · **Hàm chính:** `main`
- **File:** `MC/app/services/storytelling/face_detailer.py` (491) · **Vai trò:** Detect + vẽ lại mặt · **Hàm chính:** `detect_faces` , `detail_faces` , `_expand_box` , `_make_feather_mask` , `_match_color_mean_only`
- **File:** `MC/scripts/detect_faces_cli.py` (67) · **Vai trò:** Detect mặt trong process riêng · **Hàm chính:** `main`
- **File:** `MC/app/services/storytelling/dataset_collector.py` (202) · **Vai trò:** Cổng chất lượng thu thập dataset · **Hàm chính:** `precheck_similarity` , `maybe_collect` , `_compute_clip_similarity`
- **File:** `MC/app/services/storytelling/face_extractor.py` (65) · **Vai trò:** InsightFace embedding · **Hàm chính:** `extract_and_save_face_embedding`
- **File:** `MC/app/services/storytelling/image_generator.py` (934) · **Vai trò:** Nạp & kích hoạt LoRA · **Hàm chính:** `set_character_lora` , `set_style_lora` , `_configure_mode`

4.2. Style lock mức prompt ( `style_lock.py` )

Ba hàm thuần (không cần GPU → có unit test `MC/tests/test_style_lock.py` ):

- 1. `strip_style_drift(prompt)` ( `:62-78` ): tách prompt theo dấu phẩy, chuẩn hoá từng tag ( `_normalize` bỏ cú pháp `(tag:1.3)` ), loại tag nằm trong `_STYLE_DRIFT_TERMS` ( `:24-42` : `masterpiece` , `best quality` , `anime` , `cinematic` `lighting` , `depth of field` , `8k` ...) hoặc chứa tên model ( `_MODEL_NAME_HINTS` : `anything v5` , `dreamshaper` , `sdxl` ...). So khớp nguyên tag chứ không phải substring — test `test_strip_style_drift_keeps_content_that_merely_contains_a_style_word` đảm bảo `candlelight` không bị cắt dù chứa "light". 2. `weight_action(action, 1.35)` ( `:88-100` ): bọc từng tag hành động thành `(running:1.35)` ; tag đã có trọng số giữ nguyên. 3. `build_locked_prompt(style, content, action)` ( `:103-127` ): thứ tự cố định style → (hành động có trọng số) → nội dung → extra, dedupe tag trùng.

```
style = ", ".join(_split_tags(style_positive))
content = strip_style_drift(content_prompt)
content = dedupe_against(content, style)
```

```
parts = [style]
if action.strip():
    weighted = weight_action(strip_style_drift(action), action_weight)
    parts.append(weighted)
    # Hành động đã lên đầu thì bỏ bản không trọng số còn sót trong nội dung.
    content = dedupe_against(content, strip_style_drift(action))
parts.append(content)
```

Vì sao thứ tự quan trọng: CLIP text encoder SD1.5 xử lý cửa sổ 77 token với causal attention (token sau "nhìn" được token trước nhưng không ngược lại), và thực nghiệm cộng đồng cho thấy token đứng đầu ảnh hưởng mạnh hơn. Dự án encode prompt qua thư viện compel ( `image_generator.py:591-627` ): compel chuyển cú pháp A1111 `(tag:1.35)` sang cú pháp của nó rồi khuếch đại ảnh hưởng embedding của các token đó, đồng thời nối nhiều đoạn 77 token ( `truncate_long_prompts=False` ) nên prompt dài không bị cắt. Nếu thiếu compel thì code bỏ toàn bộ cú pháp trọng số ( `_strip_weights` ) và prompt > 77 token bị cắt — tức `weight_action` chỉ có tác dụng khi compel hoạt động. Docstring `:108-113` giải thích hành động trước đây "bị chôn ở cuối prompt nên model bỏ qua — nhân vật lúc nào cũng chỉ đứng yên".

Nguồn style duy nhất: `llm_prompter._locked_style(context)` ( `llm_prompter.py:58-71` ) lấy `context.get_positive_prompt()` — tức phần trên `---` của file preset, ví dụ `MC/resource/image_presets/thuy_mac.txt` bắt đầu bằng trigger token `thuymac ink` `wash style, (masterpiece, best quality:1.2), ink wash painting, monochrome grayscale,...` . System prompt cho LLM cấm viết tag style ( `llm_prompter.py:119` , luật "NEVER WRITE STYLE TAGS"). Kết quả LLM đi qua `build_locked_prompt(locked_style, raw_prompt, action=raw_action, action_weight=action_weight)` ( `:189-191` ), `action_weight` đọc từ `studio_action_weight` = 1.35 ( `llm_prompter.py:162` , mặc định ở `config.py:81` , comment "1.25-1.45 hợp lý"). Lọc tương tự cũng dùng ở `studio/character_renderer.py:100` và `studio/unify_pass.py:50` . Đây là phòng thủ hai lớp: cấm ở prompt LLM + lọc ở code (LLM không luôn nghe lời).

### 4.3. Style LoRA: dataset → train → sweep → dùng

Dataset ( `build_style_dataset.py` ): tải từ The Metropolitan Museum of Art Open Access API, chỉ nhận object `isPublicDomain` `=True` (CC0), ghi `manifest.json` truy vết từng ảnh (objectID, tiêu đề, license, link). Các lớp lọc:

- Metadata: chất liệu phải có "ink" ( `MEDIUM_OK` ), loại gốm/đồng/dệt ( `MEDIUM_REJECT` ), loại thư pháp ( `TITLE_REJECT` , `CLASSIFICATION_REJECT` ) vì "LoRA sẽ học phong cách này = có chữ rồi rắc chữ lên mọi khung hình" ( `:63-66` ), chỉ giữ tranh Trung Hoa ( `CULTURE_REJECT` ). Pixel ( `tile_reject_reason` , `:191-229` ): ô trắng trơn (std độ sáng < 12), tranh màu (saturation TB > 0.32), triện son đỏ (> 4,5% pixel), trang chữ (> 55 connected components nhỏ 20–1500 px sau ngưỡng Otsu). Cắt ô trượt (tiling) thay vì center-crop: tranh cuộn dài 8000×600, center-crop sẽ mất 95% bức tranh; trượt dọc cạnh dài cho 1–8 ô 512×512, tối đa 3 ô/bức ( `--max_tiles_per_work` ). Caption: `"{style_token}, {title}, {classification}, {medium}"` ( `build_caption` , `:168-188` ) — title viết thường và bỏ phần trong ngoặc, bỏ classification nếu là `"paintings"` , medium chỉ lấy đoạn trước dấu phẩy; nếu không còn gì thì dùng `"a traditional chinese painting"` . Kết quả ghi ra `storage/style_datasets/thuy_mac/` (ảnh 512×512 + `.txt` caption cùng tên + `manifest.json` ) — đúng định dạng `train_style_lora.load_dataset` đọc ( `train_style_lora.py:117-124` ).

Train: kết quả thật `MC/resource/style_loras/thuy_mac.json` :

```
{
  "checkpoint": "stablediffusionapi/anything-v5",
  "style_token": "thuymac ink wash style",
  "steps": 1500,
  "rank": 8,
  "lr": 8e-05,
  "n_images": 46
}
```

Sweep trọng số ( `style_weight_sweep.py` ): cùng prompt nhân vật + nền, cùng `SEED = 7777` , các mức `WEIGHTS = [0.0, 0.25,` `0.4, 0.55, 0.7]` , xuất bảng so sánh `_sweep_char.png` . Kết luận được ghi trong `config.py:73-75` : "0.40–0.55 dùng được,

>=0.70 tan chi tiết bàn tay/bàn chân, <=0.25 gần như không khác base model" → mặc định `style_lora_weight = 0.45` . Đây là ví dụ tốt về thực nghiệm có kiểm soát (cố định seed, chỉ đổi một biến) để trình bày với hội đồng.

Lưu ý cấu hình (cần nói đúng khi bị hỏi): giá trị mặc định trong code `MC/app/config.py:77-78` là `style_lora = "thuy_mac"` , `style_lora_weight = 0.45` . Nhưng `config.toml` (file cục bộ, gitignored) ghi đè các giá trị này qua `self.storytelling.update(data["storytelling"])` ( `config.py:160` ). Trên máy hiện tại `MC/config.toml:44-45` là `style_lora =` `""` , `style_lora_weight = 0.7` → style LoRA đang tắt; `config.toml.example:54-55` cũng để `""` / `0.8` . Tức là style LoRA là tính năng có sẵn, bật bằng cấu hình.

4.4. Kích hoạt LoRA lúc sinh ảnh ( `image_generator.py` )

Hằng số ( `image_generator.py:22-38` ): `QUALITY_MODE_MIN_STEPS = 15` , `FACEID_LORA_WEIGHT = 0.65` , `CHARACTER_LORA_WEIGHT =` `0.8` , `CHARACTER_LORA_DIR = resource/character_loras` , `STYLE_LORA_DIR = resource/style_loras` .

- `set_character_lora(slug)` ( `:348-357` ): chỉ nhận slug nếu file `<slug>.safetensors` tồn tại; đổi slug thì reset `_active_mode` để lần sinh sau cấu hình lại. Không nạp ngay (lazy). `set_style_lora(name, weight)` ( `:359-379` ): clamp weight vào [0, 1.5]; thiếu file thì cảnh báo "ảnh sẽ sinh KHÔNG có style lock". `warmup()` đọc lại style từ config mỗi lần, trừ khi đã đặt tay ( `_style_lora_explicit` ) — bug từng gặp: sweep chạy 5 mức nhưng thực tế cùng một mức ( `:134-141` ). `_configure_mode(num_steps, guidance)` ( `:381-481` ) dựng danh sách adapter đang bật theo thứ tự:

- **Thứ tự:** 1 · **Adapter:** `faceid_lora` · **Weight:** 0.65 · **Điều kiện:** engine `faceid` đã nạp
- **Thứ tự:** 2 · **Adapter:** `hyper_...` (Hyper-SD) · **Weight:** 1.0 · **Điều kiện:** Fast mode: steps < 15
- **Thứ tự:** 3 · **Adapter:** `style_<name>` · **Weight:** `style_lora_weight` · **Điều kiện:** có style LoRA
- **Thứ tự:** 4 · **Adapter:** `char_<slug>` · **Weight:** 0.8 · **Điều kiện:** có LoRA nhân vật chính của cảnh

Rồi gọi `self._pipe.set_adapters(active_adapters, adapter_weights)` ( `:474-475` ). `mode_key` là tuple `(mode, hyper_name,` `char_slug, (style_name, style_weight))` — cảnh sau giống cảnh trước thì bỏ qua cấu hình lại (cache).

```
if self._char_lora_slug:
    char_adapter = f"char_{self._char_lora_slug}"
    if char_adapter not in self._loaded_loras:
        lora_path = get_character_lora_path(self._char_lora_slug)
        try:
            self._pipe.load_lora_weights(lora_path, adapter_name=char_adapter)
            self._loaded_loras.add(char_adapter)
        except Exception as e:
            ...
    if char_adapter in self._loaded_loras:
        active_adapters.append(char_adapter)
        adapter_weights.append(CHARACTER_LORA_WEIGHT)
```

Tính trạng thái (stateful) và cách xử lý: LoRA nhân vật là trạng thái của pipeline singleton. Khi sinh nền trong Studio phải tắt đi: `pipe.set_character_lora(None)` trong `bg_render_fn` ( `studio/studio_pipeline.py:589-591` ), nếu không nền sẽ bị "nhiễm" khuôn mặt nhân vật. Mỗi lớp nhân vật gọi `pipe.set_character_lora(layer.slug)` ( `:622` ).

4.5. Bootstrap + train nhân vật chính ( `character_bootstrap.py` )

Bài toán con gà – quả trứng ( `:4-10` ): muốn nhân vật đồng nhất thì cần LoRA; muốn train LoRA thì cần sẵn 10–20 ảnh đồng nhất. Lời giải tự khởi tạo (bootstrap):

- 1. Seed ref — `generate_seed_ref` ( `:99-120` ): prompt `"{keywords_en}, solo, 1 person, portrait, close up face, front` `view, neutral expression, simple background, {style}"` , không IP-Adapter, khung dọc 512×640 (mặt to). Crop mặt rồi lưu làm `ref.png` qua `set_ref_from_image(..., source="auto_bootstrap")` — không ghi đè ref user upload tay ( `context_manager.py:221-233` ). 2. Dataset — `generate_dataset` ( `:123-165` ): nâng `ip_adapter_scale` lên 0.7 ("ưu tiên giữ khuôn mặt cho dataset train", `:138` ); xoay vòng 14 biến thể trong `_VARIATIONS` (chân dung chính diện, ¾, profile, toàn thân, đang đi, ngạc nhiên...) để

dataset đa dạng góc/pose/biểu cảm; mục tiêu `_TARGET_IMAGES = 14` , tối đa `_MAX_ATTEMPTS = 26` . Mỗi ảnh crop mặt 512; biến thể `full body` lưu thêm bản toàn khung 512×512 để LoRA học cả dáng người. 3. Train — `bootstrap_and_train` ( `:168-205` ): chỉ tự sinh khi dataset < 8 ảnh (tôn trọng ảnh user có sẵn); < 5 ảnh thì không train; ngược lại gọi `train_character` .

`_face_crop` ( `:79-96` ): detect mặt, yêu cầu cạnh ngắn ≥ 96px, nới box `pad_ratio=0.7` ; nếu cascade miss thì fallback center- crop (lệch lên trên 1/3 cho hợp chân dung) vì "mọi ảnh đều đã được IP-Adapter ghim theo cùng ref".

Vài chi tiết cần nói đúng khi bị hỏi sâu:

Vì `generate_dataset` gọi `_face_crop(img)` với `allow_fallback=True` mặc định, crop không bao giờ là `None` → trong thực tế mỗi lần sinh thành công đều được lưu; `_MAX_ATTEMPTS = 26` chỉ phát huy khi `generate_draft` ném exception. Nghĩa là không có cổng chất lượng CLIP trong dataset bootstrap (khác với `dataset_collector` ). 3/14 biến thể có `full body` ( `:38-39,43` ) → lưu thêm bản toàn khung, nên dataset thường có ~17 ảnh. Bản toàn khung là ảnh 512×640 bị `resize((512, 512))` ( `:161` ) → bị nén dọc nhẹ (không giữ tỉ lệ) — một điểm có thể cải thiện. Ảnh bootstrap được lưu với `source="approved"` ( `:158,162` ) → theo `add_dataset_image` sẽ không bao giờ bị tự xoá khi dataset chạm trần 40. Với ≥ 10 ảnh, nếu không truyền `steps` thì `train_character` chọn 800; Studio truyền `studio_auto_train_steps = 700` .

Luồng classic cũng có "bootstrap ref" nhẹ hơn ( `orchestrator.py:110-135` , `_try_bootstrap_ref` ): nếu cảnh có nhân vật chưa có ảnh ref, ảnh draft đầu tiên (sau face detailer) có mặt ≥ 110px được crop ( `pad_ratio=0.7` ) và lưu làm `ref.png` → các cảnh sau dùng IP-Adapter theo ref đó. Classic không tự train LoRA.

Nhân vật chính là ai? Studio: `_detect_lead_slugs` đếm số cảnh mỗi slug xuất hiện, lấy `most_common(max_leads)` với `studio_auto_train_max_leads = 2` ( `studio_pipeline.py:466-473` , `config.py:112` ). Train diễn ra trước khi nạp SD để render, vì `train_character` sẽ `release()` pipeline ( `studio_pipeline.py:505-512` ).

Idempotent — "train 1 lần mỗi truyện": `has_trained_lora(slug, checkpoint)` ( `:52-68` ) trả True nếu file tồn tại và checkpoint trong `<slug>.json` khớp checkpoint hiện tại. Nếu đổi checkpoint → LoRA cũ bị coi như chưa có (vì LoRA là ΔW tương đối với W0 của đúng base model đó; gắn sang base khác cho kết quả không đoán trước được).

4.6. `lora_trainer.train_character` — gọi train an toàn

```
n_images = ctx_mgr.count_dataset_images(slug)
if steps is None:
    if n_images < 10:
        steps = 600
    elif n_images < 20:
        steps = 800
    else:
        steps = 1000
```

```
# 1. Release SD pipeline — BẮT BUỘC giải phóng VRAM
try:
    from app.services.storytelling.image_generator import StorytellingPipeline
    StorytellingPipeline().release()
except Exception as e:
    logger.warning(f"Could not release pipeline: {e}")
```

( `lora_trainer.py:67-81` ). Các điểm kỹ thuật:

Release VRAM trước khi train: SD inference + training không cùng vừa GPU 6GB. Chạy train trong subprocess `sys.executable scripts/train_character_lora.py--character--images_dir--` `instance_prompt--steps [--checkpoint]` ( `:93-102` ): cô lập bộ nhớ CUDA; process kết thúc là VRAM được trả sạch. `stderr=subprocess.STDOUT` để gộp một stream, tránh deadlock khi buffer stderr đầy ( `:106-110` ); đọc từng dòng stdout để đẩy tiến độ qua `progress_cb` . Máy trạng thái `Character.lora_status` : `none→training→trained|failed` ( `models.py:61` ; comment ở đó còn liệt kê `queued` nhưng `lora_trainer.py` không đặt giá trị này), lưu `lora_trained_at` . Xác minh output bằng sự tồn tại file `.safetensors` (không chỉ tin return code), rồi ghi metadata `<slug>.json` gồm `checkpoint, steps, n_images, trained_at, instance_prompt` ( `:129-147` ) — dùng cho kiểm tra checkpoint mismatch. `get_trainable_characters` ( `:31-52` ) coi nhân vật "eligible" khi có ≥ 8 ảnh; đây là hàm hỗ trợ UI pre-flight — trong `AIVoice/apps/MediaComposer` hàm này chỉ được import ở `tests/test_storytelling_smoke.py` , không có nơi gọi trong

- code chạy thật. Docstring đầu file ( `lora_trainer.py:4` : "Không train tự động khi tạo nhân vật. Chỉ train khi user tick chọn trong pre-flight check") đã cũ so với cơ chế auto-train của Studio ở mục 4.5 — nên trình bày theo code, không theo docstring này.

4.7. Tự thu thập dataset có cổng chất lượng ( `dataset_collector.py` )

Luồng classic batch: ảnh sinh ra cho cảnh có đúng 1 nhân vật được xem xét đưa vào dataset — nhưng tránh "nhiễm độc dữ liệu" (ảnh xấu vào dataset → LoRA học cái xấu → ảnh sau xấu hơn → vòng luẩn quẩn). Hằng số ( `:19-22` ):

- **Hằng:** `FACE_MIN_PX` · **Giá trị:** 160 · **Ý nghĩa:** Cạnh ngắn của mặt (trên ảnh đã upscale) phải ≥ 160px
- **Hằng:** `SIM_THRESHOLDS` · **Giá trị:** approved 0.55, auto 0.60 · **Ý nghĩa:** Ngưỡng CLIP sim crop mặt vs ref; auto chặt hơn vì không có người duyệt
- **Hằng:** `AUTO_MAX_IMAGES` · **Giá trị:** 15 · **Ý nghĩa:** Nguồn auto chỉ bổ sung khi dataset < 15 ảnh
- **Hằng:** `CLOSEUP_FACE_RATIO` · **Giá trị:** 0.25 · **Ý nghĩa:** Mặt > 25% chiều cao → lưu thêm ảnh full khung

Ngoài ra `add_dataset_image` áp trần 40 ảnh, vượt thì xoá `auto_*` cũ nhất (FIFO), không bao giờ tự xoá `approved_*` ( `context_manager.py:317-321` ).

Chi tiết thời điểm đo: upscale (step 3) chạy sau khi SD đã `release()` → CLIP encoder không còn trên VRAM. Nên orchestrator đo trước similarity ở step 2 bằng `precheck_similarity` ngay sau face detailer ( `orchestrator.py:500-507` ), lưu vào `scene._collect_sim` , rồi step 3 truyền vào `maybe_collect(..., precomputed_sim=...)` ( `orchestrator.py:590-596` ). Nếu không đo được: nguồn `approved` cho qua (đã có mắt người), nguồn `auto` từ chối ( `dataset_collector.py:108-113` ). Embedding ảnh ref được cache ở `dataset/.ref_emb.npy` , tự invalidate khi ref mới hơn cache ( `:160-172` ).

- 4.8. Face Detailer chi tiết ( `face_detailer.detail_faces` ) Tham số (từ `config.py:58-65` và code):
- Tham số · Giá trị · Nguồn
- `face_detailer_strength` · 0.45 (thích ứng 0.30–0.55) · `config.py:59` , `face_detailer.py:348-354`
- `face_detailer_steps` · 14 · `config.py:63` , `face_detailer.py:276`
- CFG bước mặt · 6.0 (hard-code) · `face_detailer.py:277`
- `face_detailer_max_faces` · 1 · `config.py:61`
- Scheduler bước mặt · DPM++ multistep, Karras sigmas · `face_detailer.py:434-438`
- Nới box · `pad_ratio=0.65` , ép vuông · `_expand_box` , `:132-141`
- Kích thước vẽ lại · 512×512, LANCZOS · `:339`

Các bước (log trong code đánh số "Bước 2/5 … 5/5"):

1. Detect ( `detect_faces` , subprocess). Không thấy mặt → trả ảnh gốc. 2. Tạo img2img pipeline chia sẻ component — `AutoPipelineForImage2Image.from_pipe(pipeline._pipe)` ( `_get_img2img` , `:476-491` ): dùng chung U-Net/VAE/text encoder/IP-Adapter/LoRA đã nạp → không tốn thêm VRAM, cache vào `pipeline._img2img` . 3. Chuyển sang "quality face mode" ( `_switch_to_quality_face_mode` , `:431-459` ): đổi scheduler sang DPM++ Karras và tắt Hyper-SD LoRA, chỉ giữ `faceid_lora` (0.65) và `char_<slug>` (0.8); nếu không có hai adapter đó thì gọi `disable_lora()` tắt hết LoRA (kể cả style LoRA) cho bước mặt ( `:454-457` ). Lý do ( `:269-275` ): Hyper-SD là LoRA chưng cất cho khử nhiễu từ nhiễu thuần trong vài bước; dùng cho img2img khử nhiễu một phần thì "cho ra mặt nát + màu loang lổ". 4. Chọn mặt nhận identity: khi có nhiều mặt và có ảnh ref, tính CLIP sim từng mặt với ref, mặt giống nhất nhận IP-Adapter identity; mặt khác vẽ generic (scale 0) — tránh "poster trên tường bị nhập vai nhân vật" ( `:286-302` ). Mặc định chỉ vẽ mặt nhân vật chính ( `face_detailer_all_faces=False` , `:307` ). Lưu ý: việc chọn mặt chỉ duyệt `faces[:max_faces]` ( `:295` ) mà config mặc định `face_detailer_max_faces = 1` → trên thực tế chỉ xét mặt lớn nhất; logic "chọn mặt giống ref nhất" chỉ có tác dụng khi tăng `max_faces` ≥ 2. 5. Lọc kích thước: mặt > 45% chiều cao ảnh → bỏ (SD đã vẽ tốt); < 3% → bỏ (nhân vật nền) ( `:314-319` ). Chống chồng lấn: vùng giao > 15% với mặt đã vẽ → bỏ ( `:323-334` ). 6. Strength thích ứng theo tỉ lệ mặt `fh/img_h` : < 0.12 → `min(0.55, s+0.08)` ; > 0.30 → `max(0.30, s−0.05)` ( `:348-354` ). Mặt càng nhỏ càng cần vẽ đậm. 7. img2img với `face_prompt` = `"masterpiece, best quality, extremely detailed face, sharp clear eyes, " +≤14 tag` `ngoại hình` (bỏ tag bối cảnh như `background` , `street` , `sky` ...; `_build_face_prompt` , `:212-223` ). 8. Ba cổng kiểm định — mặt vẽ lại hỏng thì VỨT, giữ mặt gốc ( `:387-406` ):

- Gate 1: output phải detect được mặt. Gate 2: `sim(out, crop_512)≥0.55` — không được lệch cấu trúc quá xa bản gốc. Gate 3: với mặt identity, `sim(out, ref)≥sim(crop, ref)` — độ giống nhân vật không được giảm. Nếu CLIP encoder không khả dụng ( `_clip_similarity` trả `None` , ví dụ engine `faceid` không nạp CLIP image encoder) thì Gate 2 và Gate 3 được bỏ qua, chỉ còn Gate 1. Gate 1 gọi `detect_faces` thêm một lần (thêm một subprocess).

9. Dán lại ( `:408-417` ): resize về kích thước crop, cân màu dịu `_match_color_mean_only` (chỉ dịch mean từng kênh, kẹp ±18 — bản match cả std cũ "khuếch đại tương phản cục bộ → vá màu loang lổ", `:194-209` ), feather mask ellipse với `feather =` `max(4, crop_w// 14)` + GaussianBlur, `result.paste(out_resized, (x0, y0), mask)` . 10. Khôi phục chế độ chính trong `finally` ( `_restore_main_mode` , `:462-473` ): `enable_lora()` , reset `_active_mode` , gọi `_configure_mode` lại.

Mọi lỗi ở bất kỳ bước nào → `return image` (ảnh gốc) ( `:426-428` ). Nguyên tắc: detailer không bao giờ được chặn luồng.

Khi nào detailer thực sự chạy?

Classic batch trong MediaComposer: `if st_config.get("enable_face_detailer", True)` ( `orchestrator.py:476-486` ). Studio: chỉ ở lớp nhân vật ( `studio_char_use_detailer=True` ), bỏ khi nhân vật đã có LoRA ( `studio_lora_skip_detailer=True` — "LoRA đã giữ nhận dạng", tiết kiệm ~40% thời gian, `config.py:114-116` ), và bỏ khi mặt trong frame cuối < `_MIN_FACE_PX_TO_DETAIL = 30` px ( `_face_too_small_to_detail` , `studio_pipeline.py:65-78` , có test `MC/tests/test_studio_face_detail_gate.py` ). Qua orchestrator của toàn dự án: `enable_face_detailer` mặc định False ( `orchestrator/config.py:89` , `configs/global_config.json:56` ) → `orchestrator/pipeline.py:570-573` truyền `--no-face-detailer` , và `AIVoice/apps/MediaComposer/adapter_video_cli.py:73` ghi `config.storytelling["enable_face_detailer"] =` `args.enable_face_detailer` (tức `False` khi nhận `--no-face-detailer` , `:56-57` ). Nghĩa là khi chạy qua WebUI chính, face detailer tắt mặc định, người dùng bật bằng checkbox `s3FaceDetailer` ở Bước 3 ( `webui/app.js:301` ). Thêm nữa, `MC/config.toml` cục bộ trên máy hiện tại cũng ghi `enable_face_detailer = false` ( `:38` ), dù default trong `config.py:58` là `True` . Lý do hợp lý: mỗi mặt tốn thêm một lượt img2img (~14s theo comment `face_detailer.py:305` ).

### 4.9. Sơ đồ tổng hợp: bootstrap → train → dùng lại

## 5. Sơ đồ ngăn xếp điều kiện lúc sinh một cảnh có nhân vật

Có ba kênh điều kiện độc lập: text (style lock), ảnh (IP-Adapter), trọng số (các LoRA). Đây là câu tóm gọn nhất để nói với hội đồng về "nhất quán".

## 6. Hạn chế & hướng phát triển

Hạn chế (trung thực, đều kiểm được trong code):

1. LoRA nhân vật train trên dữ liệu tự sinh. Dataset bootstrap do chính SD + IP-Adapter tạo → LoRA học lại cả lỗi của IP- Adapter (ví dụ cùng một kiểu ánh sáng). Chất lượng LoRA bị chặn trên bởi chất lượng seed ref. 2. Không có prior preservation, không rare token. Instance prompt là tag ngoại hình thông thường ( `black hair` , `red` `eyes` ) → có nguy cơ "language drift": sau khi bật LoRA, các nhân vật khác cùng tag `black hair` cũng bị kéo về khuôn mặt đó. Giảm nhẹ bằng việc chỉ bật LoRA cho nhân vật chính của cảnh/lớp và tắt khi vẽ nền. 3. Không có validation set / early stopping. Số bước chọn theo heuristic (600/700/800/1000), không đo overfit. 4. Cảnh nhiều nhân vật: ở classic mode chỉ bật LoRA của `primary_character` ; nhiều LoRA nhân vật cùng lúc sẽ "trộn mặt" vì ΔW cộng tuyến tính trên cùng lớp. Studio né được bằng cách render từng nhân vật thành lớp riêng. 5. LBP cascade hay miss với style phẳng/mặt nghiêng/mặt nhỏ < 28px — mất cơ hội detail và thu thập dataset. 6. CLIP sim không phải face recognition — ngưỡng 0.55/0.60/0.62 là thực nghiệm. 7. Điểm lệch trong code cần biết:

`face_detailer_skip_sim` (0.62) được đọc vào biến `skip_sim` ở `face_detailer.py:279` nhưng không được dùng ở đâu trong hàm — tính năng "bỏ qua nếu mặt draft đã đủ giống" hiện chưa có hiệu lực. Trong `_switch_to_quality_face_mode` ( `:442-457` ) chỉ bật lại `faceid_lora` và `char_<slug>` — style LoRA bị tắt trong bước vẽ mặt. Khi style LoRA bật, mặt vẽ lại có thể lệch style nhẹ so với phần còn lại (đã có cân màu giảm bớt). Style LoRA mặc định trong code là bật ( `thuy_mac` , 0.45) nhưng `config.toml` cục bộ đang tắt; nếu hội đồng hỏi "đang chạy có style LoRA không" thì trả lời theo config đang dùng khi demo. Thông điệp cuối của `train_style_lora.py` ( `:35,367` ) và `config.toml.example` vẫn gợi ý `style_lora_weight = 0.8` , trong khi kết quả sweep chọn 0.45 — hai chỗ này chưa được cập nhật theo sweep. `_expand_box` ép vùng thành hình vuông trước khi kẹp vào biên ảnh ( `face_detailer.py:132-141` ); mặt sát mép ảnh sẽ cho crop chữ nhật, rồi `resize((512, 512))` làm méo tỉ lệ nhẹ trước img2img.

8. Chi phí thời gian: train style ~35–50 phút/1500 bước trên RTX 3060 6GB ( `train_style_lora.py:38` ); train nhân vật chạy đồng bộ, UI phải cảnh báo ( `lora_trainer.py:60` ).

Hướng phát triển:

- Thêm prior preservation hoặc rare token cho LoRA nhân vật; tự caption từng ảnh bằng tagger (WD14) thay vì caption chung. Thay LBP cascade bằng detector deep learning cho anime (YOLO anime face, như ADetailer `face_yolov8` ). Regional prompting / attention masking để dùng nhiều LoRA nhân vật trong một khung. Đo identity bằng model nhận dạng mặt anime thay CLIP; thêm early stopping theo sim trên tập validation. Chuyển sang SDXL + LoRA khi phần cứng cho phép. Nối `face_detailer_skip_sim` vào logic và giữ style LoRA trong face mode.

## Câu hỏi hội đồng có thể hỏi

### 1. LoRA là gì, vì sao chỉ train rất ít tham số mà vẫn học được nhân vật?

LoRA đóng băng trọng số gốc `W0` và học thêm `ΔW = B·A` với rank `r` nhỏ. Giả thuyết là thay đổi cần thiết khi fine-tune nằm trong không gian con chiều thấp. Ví dụ thật: `to_q` 320×320 = 102.400 tham số, LoRA rank 8 chỉ 5.120. File `thuy_mac.safetensors` rank 8 có 1,59M tham số ≈ 0,19% U- Net; LoRA nhân vật rank 16 ≈ 3,19M.

### 2. LoRA gắn vào lớp nào, vì sao?

`target_modules=["to_k","to_q","to_v","to_out.0"]` — bốn phép chiếu của cả self- attention (attn1) và cross-attention (attn2) trong 16 transformer block của U-Net. Cross-attention là nơi text embedding tác động lên ảnh, nên sửa ở đây trực tiếp đổi "tag này vẽ ra hình gì"; self-attention ảnh hưởng nét vẽ/bố cục, hữu ích cho style.

### 3. Loss khi train LoRA là gì?

Giống pre-training SD: thêm nhiễu Gauss vào latent tại timestep ngẫu nhiên bằng `noise_scheduler.add_noise` , U-Net dự đoán nhiễu, loss = `F.mse_loss(noise_pred, noise)` ( `train_character_lora.py:157-163` ). Gradient chỉ chảy vào tham số LoRA vì VAE, text encoder, U-Net gốc đều `requires_grad_(False)` .

### 4. Rank, alpha, learning rate, số bước dự án dùng là bao nhiêu?

Nhân vật: rank 16, alpha 16, LR 1e-4, AdamW wd 1e-2, 512px, grad_accum 4, 600/800/1000 bước theo số ảnh (Studio auto-train 700). Phong cách: rank 8, alpha 8, LR 8e-5, 1500 bước, 46 ảnh ( `thuy_mac.json` ). Alpha = rank nên scale = 1; độ mạnh chỉnh bằng adapter weight lúc inference.

### 5. Vì sao LoRA phong cách dùng caption riêng từng ảnh còn LoRA nhân vật dùng caption chung?

Model gán những gì caption không giải thích vào tag/trigger chung. Nhân vật: ta MUỐN mọi đặc điểm chung (khuôn mặt) gắn vào instance prompt → caption chung. Phong cách: caption mô tả nội dung riêng từng ảnh, phần còn lại không được giải thích là cách vẽ → dồn vào trigger `thuymac ink wash style` mà không học luôn nội dung.

### 6. Dữ liệu train LoRA nhân vật lấy từ đâu khi truyện mới chưa có ảnh nào?

Bootstrap ( `character_bootstrap.py` ): sinh 1 ảnh seed chân dung từ `keywords_en` làm ref → dùng IP-Adapter (scale 0.7) sinh 14 biến thể góc/pose/biểu cảm có cùng khuôn mặt (tối đa 26 lần thử) → crop mặt 512 (cascade miss thì center-crop) → train (Studio: 700 bước). Chỉ tự sinh khi dataset có < 8 ảnh, và chỉ train khi có ≥ 5 ảnh. Chỉ làm cho 2 nhân vật xuất hiện nhiều cảnh nhất, và chỉ một lần mỗi truyện (idempotent theo file + checkpoint).

### 7. Nếu đổi checkpoint thì LoRA cũ còn dùng được không?

Không đảm bảo, vì LoRA là ΔW tương đối với `W0` của đúng base model đã train. `has_trained_lora` đọc `<slug>.json` , nếu `checkpoint` khác thì coi như chưa có LoRA và train lại ( `character_bootstrap.py:57-66` ).

### 8. Khác nhau giữa LoRA, DreamBooth, Textual Inversion, IP-Adapter?

DreamBooth fine-tune (thường toàn bộ) U-Net với rare token + prior preservation — mạnh nhưng nặng GB. Textual Inversion chỉ học một vector token mới — nhẹ nhưng yếu. LoRA học ΔW rank thấp trên attention — cân bằng, file MB. IP-Adapter không train, đưa ảnh ref vào qua decoupled cross-attention — dùng ngay nhưng giữ identity kém chắc hơn. Dự án dùng IP-Adapter từ đầu và LoRA khi đã có dữ liệu.

### 9. Nhiều LoRA cùng bật thì kết hợp thế nào? Có fuse không?

`set_adapters(names, weights)` — ΔW cộng tuyến tính có trọng số: FaceID 0.65 (nếu có), Hyper-SD 1.0 (fast mode), style `style_lora_weight` , nhân vật 0.8. Không fuse vì chuyển Fast/Quality và đổi nhân vật liên tục; fuse/unfuse lặp lại có thể làm hỏng trọng số U-Net ( `image_generator.py:383-386` ).

### 10. Vì sao style LoRA dùng weight 0.45?

Chạy `style_weight_sweep.py` với cùng seed 7777 ở các mức 0; 0.25; 0.4; 0.55; 0.7. Kết luận ghi trong `config.py:73-75` : 0.40–0.55 dùng được, ≥ 0.70 tan chi tiết tay/chân, ≤ 0.25 gần như không khác base → chọn 0.45.

### 11. Style lock hoạt động thế nào?

Hai mức. Prompt: preset truyện là nguồn style duy nhất, LLM bị cấm viết tag style, `strip_style_drift` lọc tag style/chất lượng/tên model khỏi nội dung, `build_locked_prompt` xếp style → `(action:1.35)` → nội dung. Trọng số: style LoRA (khi bật trong config) áp cho mọi ảnh sinh qua `_configure_mode` — nền, nhân vật, unify pass — riêng bước vẽ lại mặt thì tắt. Lọc tag là so khớp nguyên tag sau chuẩn hoá, không phải substring (test `candlelight` không bị cắt). Có unit test `MC/tests/test_style_lock.py` (9 test). Trọng số `(action:1.35)` chỉ có hiệu lực vì prompt được encode qua compel.

### 12. Face detector dùng gì? Vì sao chạy trong subprocess?

`lbpcascade_animeface` (LBP + cascade kiểu Viola–Jones) qua OpenCV, `scaleFactor=1.08, minNeighbors=5, minSize=28` . Chạy subprocess `detect_faces_cli.py` vì OpenCV và PyTorch cùng nạp OpenMP trên Windows gây crash native không traceback; cô lập process thì lỗi chỉ mất bước detect.

### 13. Face detailer làm gì, khác gì chạy lại cả ảnh?

Mặt nhỏ chỉ chiếm vài ô latent nên bị nát. Detailer crop mặt (nới 65%, vuông), phóng 512×512, img2img strength 0.45 (thích ứng 0.30–0.55), 14 bước DPM++ Karras, CFG 6.0, tắt Hyper-SD, giữ LoRA nhân vật + IP-Adapter; qua 3 cổng kiểm định; dán lại bằng feather mask và cân màu mean ±18. Chỉ vẽ lại vùng mặt nên rẻ và giữ nguyên bố cục.

### 14. Làm sao biết mặt vẽ lại tốt hơn chứ không tệ hơn?

Ba gate: output phải detect được mặt; CLIP sim giữa mặt mới và mặt cũ ≥ 0.55 (không lệch cấu trúc); CLIP sim với ảnh ref không được giảm. Rớt gate nào thì giữ mặt gốc ( `face_detailer.py:387-406` ).

### 15. Làm sao tránh ảnh xấu lọt vào dataset làm LoRA tệ dần?

`maybe_collect` chỉ nhận ảnh sau upscale, cảnh 1 nhân vật, mặt ≥ 160px, CLIP sim với ref ≥ 0.55 (approved) / 0.60 (auto); auto chỉ bổ sung khi < 15 ảnh; trần 40 ảnh, xoá auto cũ trước, không xoá ảnh approved.

## Tóm tắt 1 phút

"Vấn đề lớn nhất khi làm truyện bằng Stable Diffusion là nhân vật mỗi cảnh một mặt và style mỗi cảnh một kiểu. Em giải quyết bằng ba kênh điều kiện. Kênh chữ: style lock — style lấy từ một file preset duy nhất, LLM bị cấm viết tag style, code lọc lại và xếp prompt theo thứ tự style, hành động có trọng số 1.35, rồi nội dung. Kênh ảnh: IP-Adapter Plus Face nhận ảnh tham chiếu nhân vật với scale 0.6, dùng được ngay từ cảnh đầu. Kênh trọng số: LoRA — thay vì fine-tune 860 triệu tham số, em chỉ học ma trận hạng thấp B nhân A trên các phép chiếu attention q, k, v, out; LoRA nhân vật rank 16 khoảng 3 triệu tham số, LoRA phong cách thủy mặc rank 8 chỉ 1,6 triệu, train từ 46 ảnh CC0 của bảo tàng Met. Để có dữ liệu train cho truyện mới, hệ thống tự bootstrap: sinh ảnh seed, dùng IP-Adapter sinh 14 biến thể cùng khuôn mặt, rồi train một lần cho hai nhân vật chính, dùng lại cho mọi chương. Lúc sinh ảnh, các LoRA được ghép bằng set_adapters với trọng số 0.8 cho nhân vật và 0.45 cho phong cách, chọn qua thực nghiệm quét trọng số. Cuối cùng face detailer phát hiện mặt bằng LBP cascade, vẽ lại mặt ở 512 pixel bằng img2img, qua ba cổng kiểm định rồi mới dán lại."
