# Chương 05. Bước 2 — TTS: tổng hợp giọng nói (Edge, Piper/VITS, Kokoro, VieNeu, voice clone)

- Mục tiêu chương: sau khi đọc xong, bạn giải thích được (1) âm thanh số là gì, (2) một hệ TTS biến chữ thành sóng âm như thế nào, (3) năm engine trong dự án khác nhau ở đâu về nguyên lý, (4) code của Bước 2 chạy ra sao từ lúc bấm nút trên WebUI đến lúc có file `.wav` nằm cạnh file chương truyện.

- Quy ước trích dẫn: `AIVoice/...` là submodule AIVoice; `orchestrator/...` , `webui/...` , `configs/...` là repo tổng. Số dòng lấy theo code hiện tại (commit `f219bd9` ).

## 1. Vai trò của Bước 2 trong hệ thống

### 1.1. Vị trí trong pipeline

Hệ thống có 5 bước (xem chương tổng quan). Bước 2 nhận chương truyện tiếng Việt dạng văn bản (đầu ra của Bước 1 — cào + dịch) và sinh ra file giọng đọc `.wav` cho từng chương. File `.wav` này là "xương sống thời gian" của video: Bước 3 (phân cảnh, sinh ảnh, ghép video) dùng độ dài giọng đọc để quyết định mỗi cảnh hiện bao lâu, và Whisper dùng chính audio này để khớp phụ đề.

### 1.2. Input / Output cụ thể (đọc từ code)

- **Hạng mục:** Thư mục input · **Giá trị thật:** `storage/<truyện>/translated/` nếu có file `.md` , ngược lại `raw/` · **Nguồn:** `orchestrator/pipeline.py:403-405`
- **Hạng mục:** Thư mục output · **Giá trị thật:** trùng thư mục input ( `--output-dir` = `tts_input_dir` ) → `.wav` nằm cạnh `.md` · **Nguồn:** `orchestrator/pipeline.py:430-431`
- **Hạng mục:** File được đọc · **Giá trị thật:** chỉ file `.md` / `.txt` có chuỗi `" - [VI] "` trong tên · **Nguồn:** `AIVoice/adapter_tts_cli.py:180`
- **Hạng mục:** Tên file output · **Giá trị thật:** `<tên file khôngđuôi>.wav` · **Nguồn:** `AIVoice/adapter_tts_cli.py:211-` `212`
- **Hạng mục:** Định dạng audio cuối · **Giá trị thật:** WAV, sample rate = max sample rate của các đoạn (Edge/Kokoro/XTTS → 24000 Hz, Piper → 22050 Hz), mono; ghi bằng `sf.write` không chỉ định `subtype` → mặc định của soundfile cho WAV là PCM 16-bit · **Nguồn:** `AIVoice/src/utils/audio.py:33-34,` `104`
- **Hạng mục:** Trạng thái truyện · **Giá trị thật:** `VOICE_GENERATING` → `VOICE_GENERATED` (exit 0) / `VOICE_FAILED` / `CANCELLED` · **Nguồn:** `orchestrator/pipeline.py:474-490`

### 1.3. Ranh giới tiến trình (process boundary)

Orchestrator không import code TTS. Nó spawn một tiến trình con bằng Python của venv riêng của AIVoice:

```
# orchestrator/pipeline.py:411-440 (rút gọn)
python_exe = os.path.abspath("AIVoice/.venv/Scripts/python.exe")
adapter_path = os.path.abspath("AIVoice/adapter_tts_cli.py")
cmd = [
    python_exe, adapter_path,
    "--input-dir", tts_input_dir,
    "--output-dir", tts_input_dir,
    "--engine", engine,
    "--voice", voice,
    "--speed", str(speed),
    ...
    "--device", tts_args.get("device") or "cuda"
]
```

và chạy với `cwd="AIVoice"` ( `orchestrator/pipeline.py:492-497` ). Lý do thiết kế:

1. Cô lập dependency: AIVoice cần `torch` , `coqui-tts` , `piper-tts` , `vieneu` , `onnxruntime-gpu` … (xem `AIVoice/requirements.txt` ) — nhiều gói xung đột phiên bản với FastAPI/orchestrator. 2. Giải phóng VRAM chắc chắn: khi process con thoát, driver CUDA thu hồi toàn bộ VRAM. Adapter còn chủ động gọi `torch.cuda.empty_cache()` + `ipc_collect()` + `gc.collect()` trong khối `finally` ( `AIVoice/adapter_tts_cli.py:260-` `267` ). 3. Log dạng JSON-lines: adapter in mỗi sự kiện ra stdout dưới dạng một dòng JSON ( `log_json` , `adapter_tts_cli.py:12-` `15` ), `ProcessManager` đọc từng dòng ( `orchestrator/process_manager.py` , `reader_thread` ) đẩy vào queue → SSE lên WebUI ( `GET /api/pipeline/logs/{task_key}` , `orchestrator/main.py:509-514` ). Lưu ý cho chính xác: `Popen` gộp `stderr=subprocess.STDOUT` ( `process_manager.py:48-57` ) và `process_single_file` còn `print(...)` văn bản thường, nên luồng log là trộn dòng JSON và dòng text — không phải 100% JSON.

## 2. Nền tảng lý thuyết từ gốc

### 2.1. Âm thanh số (digital audio)

Trực giác. Âm thanh là dao động áp suất không khí theo thời gian — một đường cong liên tục. Máy tính chỉ lưu được số rời rạc, nên ta lấy mẫu (sampling): cứ mỗi khoảng thời gian cố định đo độ cao đường cong một lần.

Sample rate (tần số lấy mẫu, Hz) = số mẫu mỗi giây. Ví dụ 24000 Hz = 24.000 con số cho mỗi giây âm thanh. Định lý Nyquist–Shannon: muốn tái tạo đúng tần số tối đa `f_max` , cần `sample_rate≥2·f_max` . Giọng nói có năng lượng chủ yếu dưới ~8–11 kHz, nên 22050 Hz (Piper) hay 24000 Hz (XTTSv2, Kokoro) là đủ cho tiếng nói; nhạc CD cần 44100 Hz. Bit depth: mỗi mẫu lưu bằng bao nhiêu bit. 16-bit → 2^16 = 65.536 mức, dải động ≈ 6,02 × 16 ≈ 96 dB. Trong Python, `soundfile` thường trả mảng `float32/float64` trong khoảng [-1, 1]. Kênh (channels): mono = 1, stereo = 2. Edge (MP3 mono), Piper ( `setnchannels(1)` ), Kokoro, XTTSv2 đều sinh mono; VieNeu ghi bằng `self.tts.save()` của thư viện nên số kênh không đọc được từ repo (chưa xác minh, nhiều khả năng mono). Dù sao `concatenate_wavs` vẫn xử lý được trường hợp lệch kênh. PCM (Pulse-Code Modulation): chính là dãy số mẫu "trần", không nén. WAV: container RIFF = header (sample rate, số kênh, bit depth) + dữ liệu PCM. Không nén → to nhưng đọc/ghi nhanh, không mất chất lượng, dễ nối.

Ví dụ trong code, Piper ghi WAV bằng module `wave` chuẩn với tham số tường minh:

```
# AIVoice/src/engines/piper.py:104-108
with wave.open(output_path, "wb") as wav_file:
    # Explicitly set WAV parameters (Piper is mono, 16-bit)
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
                                      # 2 byte = 16 bit
    wav_file.setframerate(self.voice.config.sample_rate)
```

File cấu hình giọng `AIVoice/models/piper/vi_VN-vais1000-medium.onnx.json` ghi `"audio": {"sample_rate": 22050, "quality":` `"medium"}` .

Resampling (đổi sample rate): nếu ghép đoạn 22050 Hz với đoạn 24000 Hz mà không đổi, đoạn thứ nhất sẽ phát nhanh và cao giọng lên (vì máy phát đọc 24000 mẫu/giây). Resampling = nội suy lại tín hiệu (lọc thông thấp chống aliasing + tính lại mẫu ở lưới thời gian mới). `concatenate_wavs` dùng `librosa.resample` khi phát hiện lệch ( `AIVoice/src/utils/audio.py:55-65` ).

Độ to cảm nhận — LUFS. Peak (đỉnh biên độ) không phản ánh tai người nghe to hay nhỏ. LUFS (Loudness Units relative to Full Scale, chuẩn ITU-R BS.1770) đo độ to trung bình có trọng số tần số (K-weighting mô phỏng độ nhạy tai) và có "gating" bỏ qua đoạn im lặng. -14 LUFS là mức chuẩn hoá phổ biến của YouTube/Spotify. Dự án dùng `pyloudnorm` với mặc định `target_lufs =` `-14.0` ( `configs/global_config.json` mục `tts` , `AIVoice/configs/default.json` ).

Fade-in/fade-out. Nếu tín hiệu bắt đầu/kết thúc đột ngột ở biên độ khác 0, loa sẽ phát ra tiếng "tách" (click) do bước nhảy gián đoạn. Nhân đầu/cuối với đường tuyến tính 0→1 và 1→0 trong 0,1 s sẽ triệt tiếng click ( `AIVoice/src/utils/audio.py:137-` `162` ).

### 2.2. Pipeline TTS cổ điển: 4 tầng

Trực giác: giống một người đọc sách: (1) hiểu chữ viết cần đọc thế nào ("12" đọc là "mười hai"), (2) biết phát âm từng âm tiết, (3) quyết định ngữ điệu, trường độ, cao độ, (4) cổ họng phát ra âm thanh.

- 1. Text normalization (chuẩn hoá văn bản): đổi số, ký hiệu, viết tắt thành chữ đọc được: `12` → "mười hai", `%` → "phần trăm", `SĐT` → "số điện thoại". 2. G2P (grapheme-to-phoneme): chữ viết → âm vị (phoneme), thường ở dạng IPA. Tiếng Việt khá "ngữ âm" (viết sao đọc vậy) nhưng vẫn có quy tắc: "gi", "d", "r" đọc khác nhau theo vùng; dấu thanh là một phần của âm vị. 3. Acoustic model: từ chuỗi phoneme dự đoán mel spectrogram — kèm trường độ (duration) mỗi âm vị, cao độ (F0), năng lượng. Ví dụ: Tacotron 2 (autoregressive + attention), FastSpeech 2 (non-autoregressive + duration predictor). 4. Vocoder: mel spectrogram → sóng âm. Ví dụ WaveNet (chậm), HiFi-GAN (nhanh, chất lượng cao).

Mel spectrogram là gì?

- Cắt tín hiệu thành các khung ngắn (~20–50 ms, chồng lấn), với mỗi khung tính STFT (Short-Time Fourier Transform) → biết năng lượng ở từng tần số → ảnh 2D thời gian × tần số (spectrogram). Tai người cảm nhận tần số theo thang logarit (phân biệt 100 Hz vs 200 Hz dễ hơn 10.000 vs 10.100 Hz). Thang mel: `m =` `2595 · log10(1 + f/700)` , trong đó `f` là tần số Hz, `m` là giá trị mel. Gom trục tần số vào ~80 "dải mel" → biểu diễn gọn, gần với cảm nhận. Mel spectrogram mất pha (phase), nên không thể đảo ngược trực tiếp thành sóng âm chất lượng cao → cần vocoder "đoán" lại pha.

HiFi-GAN (vocoder) hoạt động thế nào?

- Generator: nhận mel (ví dụ 1 khung ≈ 256 mẫu âm thanh), dùng các lớp transposed convolution để "phóng to" theo trục thời gian đến đúng số mẫu, xen kẽ các khối MRF (multi-receptive-field fusion — nhiều nhánh tích chập giãn với kích thước khác nhau) để nắm cả chi tiết ngắn lẫn chu kỳ dài. Discriminator (GAN): MPD (multi-period — nhìn tín hiệu theo chu kỳ 2,3,5,7,11 mẫu, bắt cấu trúc tuần hoàn của giọng) và MSD (multi-scale — nhìn ở nhiều độ phân giải). Discriminator học phân biệt thật/giả, generator học đánh lừa nó. Loss: `L_G = L_adv +λ_fm·L_feature_matching +λ_mel·L_mel` — ngoài "đánh lừa", generator còn phải khớp mel của sóng sinh ra với mel thật (L1). Hạn chế: mô hình 2 tầng (acoustic + vocoder) huấn luyện riêng → lỗi tích luỹ (mel dự đoán không hoàn hảo, vocoder chưa từng thấy mel "lỗi" lúc train).

### 2.3. VITS — mô hình end-to-end mà Piper sử dụng

VITS (Kim et al., 2021: Conditional Variational Autoencoder with Adversarial Learning for End-to-End TTS) gộp acoustic model + vocoder thành một mạng huấn luyện chung, bỏ mel làm trung gian cứng.

Trực giác bằng hình ảnh: tưởng tượng mọi câu nói nằm trong một "không gian ẩn" (latent) `z` . VITS học 3 việc: (a) nén sóng âm thật vào `z` (encoder), (b) giải nén `z` thành sóng âm (decoder), (c) từ văn bản đoán ra `z` nằm ở đâu (prior). Lúc suy luận chỉ dùng (c) + (b).

Ba thành phần lý thuyết:

1. VAE có điều kiện (conditional VAE)

- Posterior encoder `q(z|x_lin)` : nhận spectrogram tuyến tính của audio thật → phân phối Gauss của `z` . Decoder = generator kiểu HiFi-GAN: `z` → sóng âm. Prior `p(z|c)` : từ văn bản (phoneme `c` ) qua text encoder (Transformer) → mỗi phoneme một Gauss (μ, σ). Loss VAE: `L_recon` (L1 giữa mel của sóng sinh ra và mel thật) + `L_kl` = KL(q ‖ p), ép "điều encoder thấy" phải khớp "điều text đoán".

2. Normalizing flow `f` : chuỗi phép biến đổi khả nghịch (invertible) biến Gauss đơn giản của prior thành phân phối phức tạp hơn, để prior đủ "linh hoạt" khớp posterior. Vì khả nghịch nên lúc suy luận chạy ngược `f⁻¹` được. 3. GAN (như HiFi-GAN): `L_adv` + `L_fm` để sóng âm sắc nét.

Thêm hai cơ chế về thời gian:

MAS (Monotonic Alignment Search): khi train, không có nhãn "âm vị nào kéo dài bao nhiêu khung". MAS dùng quy hoạch động tìm cách gán khung→phoneme đơn điệu (không quay lui) có likelihood cao nhất. Stochastic Duration Predictor: học phân phối trường độ, nên cùng một câu có thể đọc với nhịp hơi khác nhau (tự nhiên hơn).

Tổng loss khi train: `L = L_recon + L_kl + L_dur + L_adv + L_fm` .

Suy luận (inference):

Ba "núm vặn" suy luận xuất hiện trong file cấu hình giọng Piper ( `vi_VN-vais1000-medium.onnx.json` , mục `inference` ):

- **Tham số:** `noise_scale` · **Giá trị thật:** 0.667 · **Ý nghĩa:** Độ "ngẫu nhiên" khi lấy mẫu `z` → biến thiên ngữ điệu; nhỏ quá thì đều đều, lớn quá thì méo
- **Tham số:** `length_scale` · **Giá trị thật:** 1 · **Ý nghĩa:** Nhân vào trường độ; >1 = đọc chậm, <1 = đọc nhanh
- **Tham số:** `noise_w` · **Giá trị thật:** 0.8 · **Ý nghĩa:** Độ ngẫu nhiên của duration predictor

Code dự án điều khiển tốc độ Piper đúng qua `length_scale = 1/speed` ( `AIVoice/src/engines/piper.py:85-86` ): speed 1.25 → length_scale 0.8 → mọi âm vị ngắn đi 20%.

### 2.4. Piper = VITS + eSpeak-ng + ONNX

Piper (dự án Rhasspy) huấn luyện VITS cho từng giọng, rồi export sang ONNX. G2P của Piper dùng eSpeak-ng: file config giọng ghi `"espeak": {"voice": "vi"}` , `num_symbols: 256` , `phoneme_id_map` có 154 mục, `num_speakers: 1` , `dataset: vais1000` (số liệu đọc trực tiếp từ `AIVoice/models/piper/vi_VN-vais1000-` `medium.onnx.json` ). Tức là: văn bản → eSpeak-ng → chuỗi IPA → tra bảng thành ID → mạng VITS. ONNX (Open Neural Network Exchange): định dạng lưu đồ thị tính toán + trọng số, độc lập framework. ONNX Runtime chạy đồ thị đó bằng các execution provider (CPU, CUDA…). Không cần PyTorch → nhẹ, khởi động nhanh. Model `vi_VN-` `vais1000-medium.onnx` nặng ≈ 63 MB (đo trên đĩa). Code tự bật GPU nếu ONNX Runtime có `CUDAExecutionProvider` ( `piper.py:25-26` ). Để onnxruntime-gpu tìm được DLL CUDA mà không cần cài CUDA Toolkit, `src/main.py:128-137` thêm thư mục `torch/lib` vào `PATH` và `os.add_dll_directory` .

### 2.5. Kokoro — dựa trên StyleTTS 2

Lưu ý nguồn: repo chỉ chứa adapter ( `AIVoice/src/engines/kokoro.py` ); gói `kokoro_vietnamese` được `setup.bat` cài từ `https://github.com/iamdinhthuan/Kokoro-Vietnamese` ( `AIVoice/setup.bat:325-343` ). Phần kiến trúc dưới đây là kiến thức về Kokoro gốc, không đọc được từ code dự án.

Kokoro-82M là mô hình TTS ~82 triệu tham số, kiến trúc dựa trên StyleTTS 2 và decoder kiểu iSTFTNet.

Ý tưởng StyleTTS: tách "nói cái gì" (phoneme) khỏi "nói theo phong cách nào" (một vector style — âm sắc, ngữ điệu, tốc độ, cảm xúc). Mỗi "giọng" của Kokoro thực chất là một voice pack = vector style đã tính sẵn. StyleTTS 2 gốc có thêm style diffusion (sinh vector style bằng diffusion từ văn bản) và huấn luyện đối kháng với discriminator dựa trên mô hình speech lớn (WavLM). Kokoro được mô tả là bỏ phần diffusion lúc suy luận, thay bằng voice pack tính sẵn → nhỏ và nhanh (kiến thức chung về Kokoro, không kiểm chứng được từ repo). iSTFTNet: thay vì generator phải "phóng to" mel qua nhiều tầng upsampling tới từng mẫu âm thanh (như HiFi-GAN), mạng chỉ upsample tới độ phân giải thấp hơn rồi dự đoán biên độ + pha của STFT, sau đó dùng inverse STFT (phép toán xác định, rất nhanh) để ra sóng âm → ít tầng hơn, nhẹ và nhanh. Hệ quả thấy được trong code: đổi giọng = đổi voice pack → adapter khởi tạo lại đối tượng khi `voice!=` `self.current_voice` ( `kokoro.py:46-51` ); output mono 24000 Hz ( `kokoro.py:56-57` ); `synthesize()` trả về cả `audio` lẫn `phonemes` ( `kokoro.py:54` ) — cho thấy thư viện tự làm G2P bên trong. Không xác minh được bản `Kokoro-Vietnamese` (iamdinhthuan) là fine-tune của Kokoro-82M hay train lại — nếu bị hỏi, nói rõ đây là thư viện bên thứ ba.

### 2.6. Edge TTS — neural TTS trên đám mây qua WebSocket

Thư viện `edge-tts` (≥ 7.2.8, `AIVoice/requirements.txt` ) mô phỏng tính năng "Read aloud" của trình duyệt Microsoft Edge: mở WebSocket tới dịch vụ speech của Microsoft, gửi cấu hình + SSML (Speech Synthesis Markup Language — XML mô tả giọng, tốc độ `rate` , cao độ…), nhận về các gói audio nhị phân theo luồng, ghép thành file. Giọng `vi-VN-NamMinhNeural` (nam), `vi-VN-HoaiMyNeural` (nữ) là Azure Neural TTS voices — mô hình neural lớn chạy trên server Microsoft; toàn bộ normalization/G2P/acoustic/vocoder diễn ra phía server. Ưu: chất lượng cao, 0 VRAM/CPU cục bộ. Nhược: cần Internet, không chính thức (không có SLA), có thể bị rate-limit. Định dạng trả về: trong gói `edge_tts` 7.2.8 cài ở venv AIVoice, `communicate.py` gửi `"outputFormat":"audio-24khz-` `48kbitrate-mono-mp3"` → dữ liệu là MP3 mono 24 kHz, 48 kbps. Trong dự án, file tạm có đuôi `.wav` ( `src/main.py:210` ) nhưng thực chất chứa byte MP3. `soundfile` (libsndfile 1.2.2 trong venv) nhận dạng định dạng theo nội dung header, không theo đuôi file: đã chạy thử ghi MP3 rồi đổi tên thành `.wav` , `sf.info` báo `MP3 24000 1` và `sf.read` đọc bình thường → `concatenate_wavs` ghép được, file cuối là WAV PCM thật. Hệ quả: audio Edge đã qua nén MP3 một lần (mất mát nhẹ).

### 2.7. Voice cloning: speaker embedding và zero-shot

Trực giác: một người bắt chước giọng người khác chỉ sau vài giây nghe. Họ nắm "dấu vân tay giọng" (âm sắc, độ trầm, cách nhả chữ) rồi áp lên nội dung mới.

Speaker embedding: một vector cố định chiều (ví dụ vài trăm số) tóm tắt đặc trưng giọng, học sao cho hai đoạn cùng người có cosine similarity cao, khác người thì thấp (d-vector, x-vector…). `cos(a,b) = (a·b) / (‖a‖·‖b‖)` . Zero-shot: model không cần train thêm cho giọng mới; chỉ cần đoạn audio tham chiếu (reference) lúc suy luận.

XTTSv2 (Coqui) — engine `clone` trong dự án. Các con số dưới đây đọc từ `AIVoice/models/xtts_v2/config.json` :

1. DVAE ( `dvae.pth` , discrete VAE / VQ-VAE): nén mel của audio thành chuỗi token âm thanh rời rạc từ codebook; `gpt_num_audio_tokens = 1026` (1024 mã + token start 1024 + stop 1025). 2. GPT (Transformer autoregressive): `gpt_layers = 30` , `gpt_n_model_channels = 1024` , `gpt_n_heads = 16` , `gpt_number_text_tokens = 7544` (từ điển BPE text, `vocab.json` ). Input = [conditioning latent của giọng mẫu] + [token văn bản]; mạng dự đoán lần lượt từng token âm thanh, giống LLM sinh chữ. 3. Perceiver resampler ( `gpt_use_perceiver_resampler = True` ): nén mel giọng mẫu dài tuỳ ý thành số lượng vector cố định → `gpt_cond_latent` . Cụ thể trong `coqui-tts` đã cài ( `TTS/tts/models/xtts.py` , `get_gpt_cond_latents` ): cắt `gpt_cond_len` giây đầu của audio mẫu thành các đoạn `gpt_cond_chunk_len` giây, mỗi đoạn tính mel (80 dải) → style embedding, rồi lấy trung bình. 4. Speaker encoder + Decoder HiFi-GAN: `speaker_embedding` được tính bởi speaker encoder của decoder trên audio mẫu resample về 16 kHz, chuẩn hoá L2 ( `get_speaker_embedding` ). Decoder HiFi-GAN nhận latent của GPT (không phải token rời rạc) và được "điều kiện" bằng `speaker_embedding` → output 24000 Hz ( `output_sample_rate` ). 5. Config liệt kê 18 ngôn ngữ, có `vi` . Bản XTTS-v2 gốc của Coqui công bố 17 ngôn ngữ, không có tiếng Việt → model trong `AIVoice/models/xtts_v2` nhiều khả năng là bản fine-tune tiếng Việt (nguồn cụ thể chưa xác minh). Việc `clone.py:56-70` phải monkeypatch `VoiceBpeTokenizer.preprocess_text` cho `vi` củng cố nhận định này (tokenizer gốc không có tiền xử lý tiếng Việt). File `model.pth` ≈ 5,6 GB trên đĩa. 6. Tốc độ: `speed` được XTTS áp dụng bằng cách nội suy tuyến tính chuỗi latent GPT theo `length_scale = 1/speed` trước decoder ( `F.interpolate` , `xtts.py` trong venv).

Vì GPT sinh token bằng lấy mẫu xác suất nên có các tham số sampling giống LLM:

- **Tham số (dự án):** `clone_temperature` · **Giá trị mặc định:** 0.75 · **Ý nghĩa:** Chia logits cho T trước softmax: T thấp = ổn định, T cao = đa dạng nhưng dễ lỗi
- **Tham số (dự án):** `clone_top_k` · **Giá trị mặc định:** 50 · **Ý nghĩa:** Chỉ xét 50 token xác suất cao nhất
- **Tham số (dự án):** `clone_top_p` · **Giá trị mặc định:** 0.85 · **Ý nghĩa:** Nucleus sampling: tập token nhỏ nhất có tổng xác suất ≥ 0,85
- **Tham số (dự án):** `clone_repetition_penalty` · **Giá trị mặc định:** 10.0 · **Ý nghĩa:** Phạt token lặp → chống "lặp tiếng", "kẹt âm"
- **Tham số (dự án):** `clone_length_penalty` · **Giá trị mặc định:** 1.0 · **Ý nghĩa:** Chỉ có tác dụng với beam search; `inference()` của XTTS mặc định `do_sample=True, num_beams=1` nên thực tế gần như không ảnh hưởng
- **Tham số (dự án):** `clone_gpt_cond_len` · **Giá trị mặc định:** 30 · **Ý nghĩa:** Số giây đầu của audio mẫu dùng tính `gpt_cond_latent`
- **Tham số (dự án):** `clone_gpt_cond_chunk_len` · **Giá trị mặc định:** 4 · **Ý nghĩa:** Cắt phần đó thành đoạn 4 s, mỗi đoạn một style embedding rồi lấy trung bình
- **Tham số (dự án):** `max_ref_length` · **Giá trị mặc định:** 60 (mặc định trong `clone.py:139` ) · **Ý nghĩa:** Cắt mỗi file mẫu tối đa 60 s trước khi tính

Nguồn: `AIVoice/configs/default.json` và `AIVoice/src/engines/clone.py:137-177` . Đối chiếu: các giá trị temperature 0.75 / top_k 50 / top_p 0.85 / repetition_penalty 10.0 / length_penalty 1.0 trùng với mặc định của hàm `Xtts.inference()` trong `coqui-tts` ; còn `config.json` của model ghi khác ( `temperature 0.85` , `repetition_penalty 2.0` , `gpt_cond_len 12` ) nhưng không được dùng vì code truyền tham số tường minh.

### 2.8. VieNeu — TTS kiểu "codec language model"

Lưu ý nguồn: adapter ở `AIVoice/src/engines/vieneu.py` , gói `vieneu==3.0.9` và `neucodec>=0.0.6` ( `AIVoice/requirements.txt` ). Kiến trúc bên trong thư viện không có trong repo; phần sau là mô tả họ mô hình nói chung.

Neural audio codec là gì? Giống MP3 nhưng học bằng mạng nơ-ron: encoder nén sóng âm thành chuỗi vector theo thời gian (vài chục khung/giây), quantizer thay mỗi vector bằng mã gần nhất trong một bảng mã (codebook — VQ/RVQ/FSQ tuỳ codec) → chuỗi số nguyên rời rạc, decoder dựng lại sóng âm từ các mã đó. Nhờ audio thành "chữ số", ta dùng được kỹ thuật của LLM. Ý tưởng "codec LM": dùng codec (ở đây NeuCodec của Neuphonic) mã hoá audio thành token rời rạc, rồi huấn luyện một language model sinh chuỗi token âm thanh từ văn bản (và từ token giọng mẫu nếu clone — giọng mẫu đóng vai "prompt"). Decoder của codec biến token ngược thành sóng âm. Về tư tưởng giống XTTSv2 (GPT + token âm thanh DVAE) nhưng dùng codec hiện đại hơn. Bằng chứng trong code: `max_new_frames: 800` — giới hạn số khung/token âm thanh LM được sinh ( `vieneu.py:58-63` ). `temperature` — tham số sampling của LM (mặc định dự án 0.3, xem mục 4.3; nếu không truyền, adapter tự dùng 0.8 — `vieneu.py:32-33` ). Mode `standard` chọn `codec_repo` : `"neuphonic/neucodec"` (bản PyTorch có encoder, cần khi clone vì phải mã hoá giọng mẫu) hoặc `"neuphonic/neucodec-onnx-decoder-int8"` (chỉ decoder, lượng tử int8, nhẹ khi dùng giọng có sẵn) ( `vieneu.py:39-41` ). Mode `v3turbo` không truyền `codec_repo` → để thư viện tự chọn. `emotion` : `natural` hoặc `storytelling` ( `src/main.py:964-969` ). Clone: truyền `ref_audio` (+ tuỳ chọn `ref_text` là transcript của audio mẫu) khi `voice=="ref_audio"` ( `vieneu.py:65-71` ).

### 2.9. Đặc thù tiếng Việt

1. Thanh điệu: 6 thanh (ngang, huyền, sắc, hỏi, ngã, nặng) là đường nét F0 (cao độ) khác nhau trên cùng âm tiết. Sai thanh = sai nghĩa ("ma/má/mà/mả/mã/mạ"). Mô hình phải học F0 theo phoneme — lý do cần dữ liệu tiếng Việt thật (VAIS1000 cho Piper, fine-tune `vi` cho XTTSv2). 2. Unicode NFC vs NFD: chữ "ế" có thể là 1 code point (U+1EBF, dạng NFC) hoặc 3 code point (e + dấu mũ + dấu sắc, NFD). Chạy thử: `len(NFC("ế")) = 1` , `len(NFD("ế")) = 3` . Tokenizer/phoneme map chỉ biết một dạng → dự án ép NFC ở 3 chỗ: đọc file ( `src/main.py:158-159` ), trong Piper ( `piper.py:80-81` ), trong `vietnamese_cleaners` ( `text.py:177` ). 3. Chuẩn hoá số: tiếng Việt có quy tắc "lẻ", "mốt", "lăm", "nghìn/ngàn"… Dự án dùng `num2words(lang='vi')` . Chạy thử trong venv AIVoice: `105` → "một trăm lẻ năm" (đúng), `2024` → "hai nghìn lẻ hai mươi bốn" (người Việt thường đọc "hai nghìn không trăm hai mươi tư" — đây là điểm chưa tự nhiên của `num2words` ). 4. Dấu phân cách nghìn: VN dùng dấu chấm ( `1.500.000` ), trùng với dấu kết câu → dễ cắt câu sai (xem Hạn chế).

## 3. Vì sao chọn công nghệ này (so sánh phương án)

### 3.1. Vì sao có nhiều engine thay vì một?

Máy mục tiêu là PC Windows + GPU NVIDIA tầm 6 GB VRAM. Bước 3 (Stable Diffusion) rất tốn VRAM. Không có engine nào tốt nhất ở mọi tiêu chí, nên thiết kế Adapter/Strategy pattern để người dùng chọn theo hoàn cảnh:

- **Engine:** `edge` (mặc định) · **Chạy ở đâu:** Cloud Microsoft · **Chất lượng tiếng Việt:** Cao, tự nhiên · **Tài nguyên cục bộ:** ~0 · **Clone giọng:** Không · **Khi nên dùng:** Có mạng, muốn nhanh, để dành VRAM cho SD
- **Engine:** `piper` · **Chạy ở đâu:** Local, ONNX (CPU/GPU) · **Chất lượng tiếng Việt:** Trung bình, hơi "máy" · **Tài nguyên cục bộ:** Rất nhẹ (model 63 MB) · **Clone giọng:** Không · **Khi nên dùng:** Offline, máy yếu
- **Engine:** `kokoro` · **Chạy ở đâu:** Local, PyTorch · **Chất lượng tiếng Việt:** Khá, 14 giọng Việt · **Tài nguyên cục bộ:** GPU/CPU (repo không có số đo VRAM) · **Clone giọng:** Không · **Khi nên dùng:** Offline, nhiều giọng
- **Engine:** `vieneu` · **Chạy ở đâu:** Local, PyTorch + codec · **Chất lượng tiếng Việt:** Tự nhiên, có biểu cảm · **Tài nguyên cục bộ:** GPU/CPU (repo không có số đo VRAM) · **Clone giọng:** Có ( `ref_audio` ) · **Khi nên dùng:** Offline, cần giọng kể chuyện
- **Engine:** `clone` (XTTSv2) · **Chạy ở đâu:** Local, GPU · **Chất lượng tiếng Việt:** Phụ thuộc giọng mẫu · **Tài nguyên cục bộ:** Nặng (model.pth ≈ 5,6 GB) · **Clone giọng:** Có (zero-shot) · **Khi nên dùng:** Cần giọng riêng của người dùng

Mặc định `edge` được chọn trong `configs/global_config.json` ( `tts.default_engine = "edge"` ), `orchestrator/config.py:57-` `59` , và fallback trong adapter ( `adapter_tts_cli.py:95-96` ).

### 3.2. So sánh với phương án khác

- Google Cloud TTS / Azure Speech chính thức / ElevenLabs: chất lượng tốt nhưng trả phí theo ký tự, cần API key — không hợp mục tiêu "chạy cục bộ, không phụ thuộc dịch vụ trả phí". Edge-tts dùng được miễn phí nhưng là API không chính thức → dự án bù bằng retry/backoff và có các engine offline dự phòng. gTTS (Google Translate TTS): miễn phí nhưng giọng kém tự nhiên, không chỉnh tốc độ mịn. Tacotron2 + HiFi-GAN tự train: phải tự thu/thuê dữ liệu, train nhiều GPU-giờ, pipeline 2 tầng. VITS/Piper đã có giọng Việt huấn luyện sẵn. Vì sao Piper thay vì tự chạy VITS PyTorch? ONNX nhẹ, không cần PyTorch lúc chạy, khởi động nhanh, có thể chạy CPU song song 6 luồng. Vì sao XTTSv2 cho clone? Zero-shot (chỉ cần một file mẫu), hỗ trợ `vi` sẵn, mã nguồn mở, chạy local.

### 3.3. Vì sao chạy qua subprocess + adapter CLI?

Đã nêu ở 1.3: cô lập venv, giải phóng VRAM, log JSON-lines phục vụ SSE, và có thể dừng (kill) tiến trình khi người dùng bấm Stop ( `ProcessManager.was_user_stopped` → trạng thái `CANCELLED` , `pipeline.py:481-482` ).

## 4. Hiện thực trong code

### 4.1. Bản đồ module

- **File:** `AIVoice/adapter_tts_cli.py` · **Dòng:** 270 · **Vai trò:** CLI non-interactive cho orchestrator: gộp cấu hình, chọn engine, lặp qua chương, log JSON
- **File:** `AIVoice/src/main.py` · **Dòng:** 1109 · **Vai trò:** Các monkey-patch tương thích Windows/PyTorch; `process_single_file()` (lõi); CLI/wizard độc lập
- **File:** `AIVoice/src/engines/base.py` · **Dòng:** 16 · **Vai trò:** `BaseTTSEngine` (ABC) với đúng 1 method `generate()`
- **File:** `AIVoice/src/engines/edge.py` · **Dòng:** 62 · **Vai trò:** `EdgeEngine` — edge-tts, retry 5 lần
- **File:** `AIVoice/src/engines/piper.py` · **Dòng:** 172 · **Vai trò:** `PiperEngine` — PiperVoice in-process, fallback `piper.exe` subprocess, tự tải model
- **File:** `AIVoice/src/engines/kokoro.py` · **Dòng:** 68 · **Vai trò:** `KokoroEngine` — 14 giọng, 24 kHz
- **File:** `AIVoice/src/engines/vieneu.py` · **Dòng:** 87 · **Vai trò:** `VieNeuEngine` — mode `v3turbo` / `standard` , emotion, clone
- **File:** `AIVoice/src/engines/clone.py` · **Dòng:** 311 · **Vai trò:** `CloneEngine` — XTTSv2, cache latent, FP16 + fallback FP32
- **File:** `AIVoice/src/utils/text.py` · **Dòng:** 217 · **Vai trò:** `clean_markdown` , `chunk_text` , `vietnamese_cleaners`
- **File:** `AIVoice/src/utils/phoneme.py` · **Dòng:** 30 · **Vai trò:** `phonemize_vietnamese` (viphoneme → IPA)
- **File:** `AIVoice/src/utils/audio.py` · **Dòng:** 235 · **Vai trò:** `concatenate_wavs` , `apply_audio_post_processing` , `chunk_audio_file`
- **File:** `AIVoice/src/utils/cache.py` · **Dòng:** 230 · **Vai trò:** `SemanticCacheManager` (FAISS + SentenceTransformer, fallback n-gram)
- **File:** `AIVoice/configs/default.json` · **Dòng:** 28 · **Vai trò:** Mặc định cấp thấp nhất
- **File:** `AIVoice/configs/tts_presets.json` · **Dòng:** 75 · **Vai trò:** 7 preset: `default` , `fast` , `female_reading` , `offline_cloning` , `offline_fast` , `kokoro_vi` , `vieneu`

- Lưu ý khi bảo vệ: `AIVoice/PROJECT_SUMMARY.md` còn liệt kê `rvc_engine.py` , `valtec.py` , `local_ai_spice.py` nhưng các file này không có trong `src/engines/` và `src/utils/` hiện tại. Đừng trình bày chúng như tính năng đang chạy.

### 4.2. Interface chung: Adapter pattern

```
# AIVoice/src/engines/base.py:3-16
class BaseTTSEngine(ABC):
    @abstractmethod
    def generate(self, text: str, output_path: str, **kwargs) -> bool:
        """Generates audio for a single text chunk and saves it.
        ...
        Returns:
            bool: Success status (True if successful, False otherwise).
        """
        pass
```

Hợp đồng rất nhỏ: một đoạn text → một file audio, trả `True/False` . Mọi tham số riêng (speed, voice, ref_audio, temperature…) đi qua `**kwargs` , engine nào không cần thì bỏ qua. Nhờ vậy `process_single_file` không cần biết engine là gì.

### 4.3. Gộp cấu hình: 4 tầng ưu tiên

`adapter_tts_cli.py` gộp cấu hình theo thứ tự (sau đè trước):

- 1. `AIVoice/configs/default.json` ( `adapter_tts_cli.py:66-73` ) 2. Preset từ `configs/tts_presets.json` nếu có `--preset` ( `:76-81` ) 3. Tham số dòng lệnh không phải `None` ( `:84-92` ) 4. `setdefault` cho khoá còn thiếu ( `:95-114` )

Còn phía orchestrator, `start_step_2_tts` luôn truyền `--engine` , `--voice` , `--speed` , `--target-lufs` , `--fade-in` , `--fade-out` , `--silence-duration` , `--device` , `--(no-)phonemize` , `--(no-)normalize` , `--(no-)cache` , `--vieneu-mode` ( `pipeline.py:428-`

`470` ); `--preset` , `--model` , `--ref-audio` , `--cache-threshold` , `--vieneu-emotion` , `--temperature` chỉ thêm khi có giá trị. `buildStep2Payload()` của WebUI ( `webui/app.js:266-287` ) không gửi trường `preset` , nên `Step2Schema.preset` luôn lấy mặc định `"default"` ( `orchestrator/main.py:128` ). Ô chọn preset trên WebUI chỉ điền sẵn form phía trình duyệt bằng một bảng preset hardcode trong `app.js:606-631` (và bảng này lệch với `tts_presets.json` , ví dụ `offline_fast` trong JS là speed 1.2, normalize false). Hệ quả: trong luồng WebUI, preset hầu như bị các cờ CLI ghi đè; giá trị thật do form WebUI / `global_config.json` quyết định. Riêng các khoá không có cờ CLI như `model` (khi form để trống), `ref_audio` , `max_words` , `clone_*` , `hardware_profile` thì lấy từ `AIVoice/configs/default.json` .

Giọng mặc định theo engine khi người dùng không chọn ( `pipeline.py:414-424` ):

- **Engine:** `kokoro` · **Voice mặc định:** `thuc_trinh` · **Nguồn:** `tts.kokoro_voice`
- **Engine:** `vieneu` · **Voice mặc định:** `Ngọc Lan` · **Nguồn:** `tts.vieneu_voice`
- **Engine:** còn lại · **Voice mặc định:** `vi-VN-NamMinhNeural` · **Nguồn:** `tts.default_voice`
- **Engine:** Bảng tham số hiệu lực trong luồng orchestrator (khi form để mặc định):
- **Engine:** Tham số Giá trị · **Voice mặc định:** Nguồn
- **Engine:** 30 `max_words` · **Voice mặc định:** `AIVoice/configs/default.json` , `adapter_tts_cli.py:114`
- **Engine:** 240 `max_chars` · **Voice mặc định:** mặc định hàm `chunk_text` ( `text.py:36` )
- **Engine:** 0.3 s `silence_duration` · **Voice mặc định:** `pipeline.py:438`
- **Engine:** `fade_in` / 0.1 s `fade_out` · **Voice mặc định:** `pipeline.py:436-437`
- **Engine:** -14.0 `target_lufs` · **Voice mặc định:** `pipeline.py:435`
- **Engine:** 0.3 (chỉ VieNeu dùng; XTTSv2 dùng `temperature` `clone_temperature` 0.75) · **Voice mặc định:** `adapter_tts_cli.py:111` , UI `s2Temperature` value 0.3, `main.py:243`
- **Engine:** False `use_cache` · **Voice mặc định:** `--no-cache` trừ khi bật, `pipeline.py:457-460`
- **Engine:** 0.95 `cache_threshold` · **Voice mặc định:** `global_config.json` , `adapter_tts_cli.py:108`
- **Engine:** `vieneu_mode` `v3turbo` · **Voice mặc định:** `pipeline.py:464`
- **Engine:** `device` `cuda` · **Voice mặc định:** `Step2Schema.device` ( `main.py:140` )

### 4.4. Chọn engine (factory đơn giản)

```
# AIVoice/adapter_tts_cli.py:121-141 (rút gọn)
if runner_args.engine == "piper":
    engine = PiperEngine(runner_args.model)
elif runner_args.engine == "edge":
    engine = EdgeEngine(runner_args.voice)
elif runner_args.engine == "clone":
    if not runner_args.ref_audio:
        log_json("tts_error", {"message": "ref_audio is required for the CloneEngine"})
        sys.exit(1)
    engine = CloneEngine(runner_args.model)
elif runner_args.engine == "kokoro":
    engine = KokoroEngine(runner_args.model)
elif runner_args.engine == "vieneu":
    engine = VieNeuEngine(runner_args.model)
else:
    log_json("tts_error", {"message": f"Unsupported tts engine: ..."})
    sys.exit(1)
```

Import engine nằm trong nhánh (lazy import): chọn `edge` thì không phải nạp `coqui-tts` / `kokoro` / `vieneu` . Tuy nhiên cần nói chính xác: `adapter_tts_cli.py:10` import `src.main` , mà phần đầu `src/main.py` (dòng 18-137) đã thử `import torch` , `transformers` , `TTS...` để monkeypatch — nên `torch` vẫn được nạp kể cả khi dùng Edge; lazy import chỉ tránh nạp model. Engine được tạo một lần và dùng lại cho mọi chương → model chỉ nạp 1 lần cho cả batch.

Chi tiết nhỏ: điều kiện `if not runner_args.ref_audio` gần như không bao giờ đúng vì `AIVoice/configs/default.json` đã có `"ref_audio": "data/voices/ref_voice.wav"` (file này tồn tại trong `AIVoice/data/voices/` ). Tức là chọn `clone` mà không đưa file mẫu thì hệ thống lặng lẽ dùng giọng mẫu mặc định.

### 4.5. Batch mode và logic "Tiếp tục" (resume)

`adapter_tts_cli.py:145-231` :

- 1. Liệt kê file trong `input_dir` (+ `output_dir` nếu khác) → tập tên file audio đã có ( `.mp3` / `.wav` ). 2. Chỉ nhận file `.md` / `.txt` có `" - [VI] "` trong tên (bản đã dịch). 3. Bỏ qua chương đã có audio — so theo cả tên đầy đủ lẫn phần tên chương trước `" - [VI] "` (tránh đọc lại khi có nhiều bản dịch cùng chương với tiêu đề khác nhau). 4. Nếu một chương có nhiều bản `[VI]` , chỉ đọc bản đầu tiên, log `tts_file_skip` . 5. Phân biệt 2 kiểu "danh sách rỗng":

- Có ứng viên nhưng đều đã có audio → `tts_batch_warn` , `exit(0)` (thành công, không làm gì). Không có ứng viên nào → `tts_error` , `exit(1)` kèm hướng dẫn chạy `scripts/fix_ten_chuong.py` .

- 6. Với từng file: `process_single_file(file_path, file_output_path, engine, runner_args)` rồi log `tts_file_success` (kèm `duration_s` = thời gian xử lý) hoặc `tts_file_failed` .

Ví dụ một dòng log thật được in ra stdout:

```
{"event": "tts_file_start", "index": 3, "total": 12, "file": "Chương 3 - [VI] Gặp lại.md"}
```

(Cấu trúc theo `adapter_tts_cli.py:214-218` ; tên file là ví dụ minh hoạ.)

4.6. Lõi: `process_single_file()` — 7 bước

`AIVoice/src/main.py:139-350` . Đây là hàm quan trọng nhất của chương.

Bước 1 — Đọc & NFC ( `main.py:155-159` ).

Bước 2 — `clean_markdown` ( `text.py:3-34` ): bằng regex bỏ code block, ảnh, link (giữ chữ), in đậm/nghiêng, heading `#` , bullet `-` , danh sách số `1.` , blockquote `>` , checkbox. Mục đích: không để TTS đọc "dấu thăng thăng".

Bước 3 — chuẩn hoá tiếng Việt, chỉ cho engine offline ( `main.py:169-173` ): `clone` (khi `voice=="vi"` ), `kokoro` , `vieneu` . `edge` và `piper` không qua bước này — Edge tự chuẩn hoá phía server; Piper dựa vào eSpeak-ng.

`vietnamese_cleaners` ( `text.py:168-216` ) làm theo thứ tự:

- 1. NFC + lowercase. 2. Ký hiệu: `&` →"và", `@` →"a còng", `%` →"phần trăm", `#` →"số", `+` →"cộng", `$` →"đô la", `₫` / số+ `đ` → "đồng". 3. Viết tắt: `SĐT` →"số điện thoại", `TP` →"thành phố", `HCM` →"hồ chí minh", `km` →"ki lô mét", `kg` →"ki lô gam", `m` →"mét", `đ/c` →"địa chỉ"…

- 4. Bỏ dấu phân cách nghìn: `1.500.000` → `1500000` . 5. Số thập phân → `num2words(float, lang='vi')` ; số nguyên → `num2words(int, lang='vi')` . 6. Tách dấu câu khỏi chữ (thêm khoảng trắng), `;` và `:` → `,` , `-` → khoảng trắng, xoá `<> ( ) [ ] "` , gộp khoảng trắng.

Ví dụ chạy thật trong venv AIVoice với đầu vào:

```
Lý Phàm mỉm cười. Hắn đã tu luyện 12 năm, tiêu tốn 1.500.000 linh thạch,
tức khoảng 3,5% gia sản; SĐT của sư phụ là gì? Trời đất!
```

đầu ra `vietnamese_cleaners` :

```
lý phàm mỉm cười . hắn đã tu luyện mười hai năm , tiêu tốn một triệu năm trăm
nghìn linh thạch , tức khoảng ba phẩy năm mươi phần trăm gia sản , số điện
thoại của sư phụ là gì ? trời đất !
```

Để ý "3,5" bị đọc thành "ba phẩy năm mươi" — đây là hành vi của `num2words` tiếng Việt (chạy thử `num2words(3.5, lang='vi')` ra đúng chuỗi này). Là một hạn chế có thật, nên chủ động nêu nếu được hỏi.

Bước 4 — `chunk_text` : thuật toán chia đoạn 2 chiều ( `text.py:36-138` )

Vì sao phải chia? (a) XTTSv2 tiếng Việt có giới hạn ~250 ký tự, vượt là crash CUDA assertion (docstring `text.py:46-47` ); (b) model autoregressive câu dài dễ "lạc" (lặp, nuốt chữ); (c) đoạn nhỏ cho phép sinh song song và retry cục bộ.

Thuật toán, với `max_words = 30` (từ config), `max_chars = 240` :

#### 1. Tách theo dòng (mỗi đoạn văn một dòng). 2. Trong mỗi dòng, `re.split(r'([.?

!;]+)', line)` tách câu, giữ lại dấu câu. 3. Chiều "bẻ": câu nào > 30 từ hoặc > 240 ký tự → duyệt từng từ, cắt khi sắp vượt ngưỡng hoặc khi gặp từ kết thúc bằng dấu phẩy. Một "từ" đơn lẻ > 240 ký tự bị cắt cụt + `"..."` . 4. Chiều "gộp": các câu ngắn liên tiếp trong cùng dòng được gộp lại chừng nào tổng ≤ 30 từ và ≤ 240 ký tự → ngữ điệu liền mạch hơn, ít lần gọi engine hơn. 5. Loại chunk không có ký tự chữ/số nào ( `any(char.isalnum()...)` ).

Kết quả chạy thật ( `max_words=30` ) khi thêm tiêu đề `# Chương 12: Gặp lại` ở đầu và câu `Đi thôi.` ở cuối đoạn văn trên, cho qua `clean_markdown` → `vietnamese_cleaners` → `chunk_text` (chú ý `:` thành `,` , `;` thành `,` nên câu chỉ còn được tách ở `. ?` `!` ):

```
29 từ | 122 ký tự | chương mười hai , gặp lại lý phàm mỉm cười . hắn đã tu luyện mười hai năm , tiêu tốn một triệu năm trăm nghìn linh thạch
,
26 từ | 101 ký tự | tức khoảng ba phẩy năm mươi phần trăm gia sản , số điện thoại của sư phụ là gì ? trời đất ! đi thôi .
```

Phòng thủ 2 lớp cho XTTSv2: ngoài `max_chars=240` ở đây, `CloneEngine` còn tự cắt còn 240 ký tự nếu text > 248 ( `clone.py:221-` `224` ).

Bước 5 — phonemize (tuỳ chọn) ( `main.py:183-190` , `phoneme.py` ): gọi `viphoneme.vi2IPA` đổi sang IPA; monkeypatch `vinorm.TTSnorm` thành hàm identity vì `vinorm` gọi binary Linux không chạy được trên Windows; lỗi hoặc thiếu thư viện thì trả lại text gốc (graceful fallback). Preset `offline_cloning` bật `phonemize: true` ; luồng WebUI mặc định tắt.

Bước 6 — sinh song song có ý thức phần cứng ( `main.py:208-294` ):

```
# AIVoice/src/main.py:249-254
if args.engine in ["clone", "kokoro", "vieneu"]:
    max_workers = 1
elif args.engine == "piper":
    max_workers = 6
else: # edge
    max_workers = 3
```

- Engine GPU PyTorch = 1 luồng → không bao giờ 2 chunk cùng chiếm VRAM (chống OOM), và các model này không an toàn đa luồng. Piper (ONNX, nhẹ) = 6 luồng.

Edge (mạng) = 3 luồng + stagger delay: `(idx%3) * 0.4 + random.uniform(0, 0.2)` giây trước mỗi request ( `main.py:269-273` ) → không bắn 3 request cùng lúc, né rate-limit. Mỗi chunk ghi vào file tạm riêng ( `tempfile.mkstemp(suffix=f"_segment_{idx}.wav")` ), thư mục temp bị chuyển về `AIVoice/storage/temp` ( `main.py:51-56` ). Kết quả gom bằng `as_completed` vào `success_map[idx]` → thứ tự hoàn thành có thể lộn xộn nhưng thứ tự ghép vẫn theo `idx` vì `temp_files` được tạo theo thứ tự trước khi chạy.

Bước 7 — "tất cả hoặc không" + ghép + hậu kỳ ( `main.py:297-333` ): nếu bất kỳ chunk nào thất bại → xoá file tạm, trả `FAILED` (không tạo audio thiếu đoạn). Nếu đủ: `concatenate_wavs` rồi `apply_audio_post_processing` .

### 4.7. Chi tiết từng engine

EdgeEngine ( `AIVoice/src/engines/edge.py` )

Đổi `speed` thành chuỗi `rate` kiểu SSML: `pct = int((speed - 1.0) * 100)` → ý đồ là speed 1.15 → `"+15%"` , speed 0.9 → `"-10%"` ; nhưng vì sai số dấu phẩy động và `int()` cắt về 0, chạy thật cho `int((1.15-1.0)*100) = 14` → `"+14%"` và `int((0.9-1.0)*100) = -9` → `"-9%"` (lệch 1%, không đáng kể nhưng đúng là hành vi thật) ( `edge.py:18-22` ). `main.py:218-` `219` chỉ truyền `speed` khi khác 1.0. `asyncio.run(_save())` chạy coroutine của edge-tts trong luồng worker (mỗi luồng tự tạo event loop riêng). Kiểm tra file tồn tại và > 0 byte, nếu không coi là lỗi. Retry 5 lần với backoff `[2.0, 5.0, 10.0, 15.0]` giây, xoá file hỏng giữa các lần:

```
# AIVoice/src/engines/edge.py:36-61 (rút gọn)
max_retries = 5
for attempt in range(max_retries):
    try:
        asyncio.run(_save())
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        else:
            raise ValueError("Output audio file is missing or empty.")
    except Exception as e:
        ...
        if attempt < max_retries - 1:
            backoff_time = [2.0, 5.0, 10.0, 15.0][attempt]
            time.sleep(backoff_time)
return False
```

Tổng thời gian chờ tối đa mỗi chunk ≈ 2+5+10+15 = 32 s trước khi bỏ cuộc.

PiperEngine ( `AIVoice/src/engines/piper.py` )

Tự tải model khi thiếu, chỉ với tên bắt đầu `vi_VN-vais1000-medium` , từ `https://huggingface.co/rhasspy/piper-` `voices/resolve/main/vi/vi_VN/vais1000/medium` , tải cả `.onnx` và `.onnx.json` , stream theo khối 256 KB, xoá file 0 byte nếu lỗi ( `piper.py:29-61` ). Đường chính: in-process `PiperVoice.load(path, use_cuda=...)` + `synthesize_wav(...)` với `SynthesisConfig(length_scale, speaker_id)` ( `piper.py:90-116` ). Comment giải thích: nhanh hơn, không phải spawn hàng trăm tiến trình. `voice` được thử ép `int` làm `speaker_id` (cho model nhiều giọng); không phải số thì bỏ qua. Đường dự phòng: gọi `piper.exe` bằng `subprocess.run(..., input=text, encoding='utf-8', env PYTHONIOENCODING=utf-` `8)` , thêm `--cuda` nếu có GPU ( `piper.py:118-172` ). Ép UTF-8 để tránh lỗi mã hoá tiếng Việt trên console Windows (cp1252).

KokoroEngine ( `AIVoice/src/engines/kokoro.py` )

14 giọng hợp lệ: `diem_trinh, hung_thinh, mai_linh, mai_loan, manh_dung, my_yen, ngoc_huyen, phat_tai, thanh_dat,` `thuc_trinh, tuan_ngoc, storyvert, duc_an, duc_duy` ; giọng lạ → `diem_trinh` ( `kokoro.py:30-37` ). WebUI hiển thị đúng 14 giọng này kèm vùng miền ( `webui/app.js` , nhánh `eng==="kokoro"` ). Cache trạng thái: chỉ khởi tạo lại `KokoroVietnamese(device, voice)` khi đổi GPU/CPU hoặc đổi giọng. `sf.write(output_path, audio, 24000)` . Không đọc `speed` trong `generate()` → tham số tốc độ không có tác dụng với Kokoro (quan sát từ code).

VieNeuEngine ( `AIVoice/src/engines/vieneu.py` )

`mode` mặc định `v3turbo` ; `standard` thì chọn `codec_repo` như mục 2.8. Khởi tạo lại `Vieneu(mode=..., codec_repo=...)` khi đổi mode/codec. `infer(text, emotion, temperature, max_new_frames=800, [voice|ref_audio, ref_text])` , lưu bằng `self.tts.save(audio, output_path)` . Voice đặc biệt: `"ref_audio"` = clone từ file mẫu; `"vi-VN-NamMinhNeural"` bị bỏ qua (tránh truyền nhầm tên giọng Edge sang VieNeu). Danh sách giọng trên WebUI: Ngọc Lan, Gia Bảo, Thái Sơn, Đức Trí, Mỹ Duyên, Trúc Ly, Xuân Vĩnh, Trọng Hữu, Bình An, Ngọc Linh + "ref_audio" ( `webui/app.js` , nhánh `eng==="vieneu"` ). Cũng không dùng `speed` .

CloneEngine — XTTSv2 ( `AIVoice/src/engines/clone.py` )

Luồng xử lý một chunk:

Các kỹ thuật đáng nói khi bảo vệ:

1. Cache speaker latent ( `clone.py:198-219` ): khoá cache = (danh sách file mẫu, `gpt_cond_len` , `gpt_cond_chunk_len` , `max_ref_length` , `sound_norm_refs` , `librosa_trim_db` ). Một chương 100 chunk chỉ tính latent 1 lần thay vì 100. 2. Nhiều file mẫu: `ref_audio` có thể là danh sách phân tách bằng `;` hoặc `,` ( `clone.py:97-106` ). Theo code `coqui-tts` đã cài: `speaker_embedding` của từng file được lấy trung bình, còn audio các file được nối lại rồi mới tính `gpt_cond_latent` . 3. Mixed precision FP16 + fallback: chạy `torch.amp.autocast(dtype=float16)` ; nếu output có NaN/Inf hoặc lỗi → chạy lại FP32 ( `clone.py:226-286` ). FP16 dùng 2 byte/số thay vì 4 → tiết kiệm VRAM, nhanh hơn trên Tensor Core; đổi lại dải số hẹp dễ tràn → NaN. 4. TF32: bật `allow_tf32` cho matmul/cuDNN ( `clone.py:127-129` ) — định dạng 19 bit của Ampere+, nhanh hơn FP32 mà gần như không mất chất lượng. 5. SDPA ( `scaled dot-product attention` hợp nhất của PyTorch): `torch.backends.cuda.sdp_kernel(enable_flash=True,` `enable_math=True, enable_mem_efficient=True)` ( `clone.py:183-188` ) — cho phép PyTorch chọn kernel attention tối ưu thay vì cài `flash-attn` khó build trên Windows. Lưu ý: context này chỉ có tác dụng nếu các lớp attention bên trong model

thực sự gọi `F.scaled_dot_product_attention` ; với GPT-2 của XTTS điều đó phụ thuộc phiên bản `transformers` (chưa xác minh), và API `sdp_kernel` đã bị PyTorch đánh dấu deprecated. 6. Monkeypatch: `torchaudio.load/save` thay bằng `soundfile` (tránh lỗi DLL FFmpeg/torchcodec); `torch.load` ép `weights_only=False` tạm thời để nạp checkpoint cũ trên PyTorch ≥ 2.6; `VoiceBpeTokenizer.preprocess_text` cho `vi` gọi `vietnamese_cleaners` của dự án ( `clone.py:38-88` ). 7. Dọn VRAM sau mỗi chunk với profile `rtx3060` (mặc định): `gc.collect()` + `torch.cuda.empty_cache()` ( `clone.py:297-` `304` ). 8. Ngôn ngữ lấy từ `voice` ( `"vi"` ), không hỗ trợ thì fallback `"en"` ( `clone.py:112-120` ). WebUI khi chọn `clone` chỉ có một option `vi` . Nhưng nếu gọi API mà không truyền `voice` , pipeline sẽ gán `vi-VN-NamMinhNeural` ( `pipeline.py:422` ) → XTTS fallback `en` và `main.py:170` bỏ qua `vietnamese_cleaners` → đọc tiếng Việt bằng luật tiếng Anh. 9. Với `vi` , văn bản thực ra qua `vietnamese_cleaners` hai lần: ở `main.py:173` và lần nữa trong tokenizer đã monkeypatch ( `clone.py:61-65` ). Hàm gần như idempotent nên vô hại.

Tài liệu `docs/trinh-bay-datn.md` ghi VRAM của XTTSv2 ≈ 3.5 GB FP32 → 2.0 GB FP16; repo không có số đo VRAM cho Kokoro/VieNeu.

4.8. Semantic cache ( `AIVoice/src/utils/cache.py` )

Ý tưởng: câu đã từng đọc (hoặc gần giống) thì lấy lại audio cũ, khỏi sinh lại.

Lưu ở `AIVoice/storage/cache/` : `metadata.json` (text, đường dẫn audio, vector) + `audio/<sha256(text)>.wav` . Đường neural: `SentenceTransformer("all-MiniLM-L6-v2")` → vector 384 chiều, chuẩn hoá L2, đưa vào `faiss.IndexFlatIP` (inner product của vector đã chuẩn hoá = cosine similarity). Tra top-1, trúng nếu `sim≥0.95` . Fallback lexical: cosine trên đếm n-gram ký tự bậc 3 ( `_compute_tfidf_similarity` , thực chất là bag-of-char-3gram, không có trọng số IDF). Nó chạy khi thiếu `faiss` / `sentence-transformers` , và cả khi tra FAISS không trúng: `get()` luôn duyệt tuyến tính mọi entry bằng n-gram nếu `matched_entry is None` ( `cache.py:146-152` ) → chi phí O(số entry) mỗi chunk. `set()` copy file tạm vào cache trước khi `concatenate_wavs` xoá file tạm (comment `main.py:277` ). Mặc định TẮT ( `use_cache: false` trong `global_config.json` , `--no-cache` trong `pipeline.py:460` ). Lý do nên tắt: "giống 95%" về nghĩa không có nghĩa là cùng chữ — ví dụ hai câu chỉ khác tên nhân vật có thể trúng cache và đọc sai. Thêm nữa `all-MiniLM-L6-v2` là model tiếng Anh, không tối ưu cho tiếng Việt.

4.9. Ghép và hậu kỳ audio ( `AIVoice/src/utils/audio.py` )

`concatenate_wavs(input_paths, output_path, silence_duration)` :

1. Quét header bằng `sf.info` lấy sample rate lớn nhất và số kênh lớn nhất (mặc định 24000 Hz, mono nếu không đọc được). 2. Đọc từng đoạn; lệch sample rate → `librosa.resample` ; mono mà đích nhiều kênh → nhân bản kênh. 3. Chèn mảng số 0 dài `int(silence_duration * samplerate)` mẫu giữa các đoạn (0,3 s × 24000 = 7200 mẫu) — khoảng lặng giúp người nghe "thở" giữa các câu. 4. `np.concatenate` , peak normalize về 0,95 (tránh clipping khi cộng dồn). 5. Ghi file, xoá các file tạm.

`apply_audio_post_processing(audio_path, target_lufs, fade_in, fade_out)` :

1. Fade tuyến tính `np.linspace(0,1,n)` / `np.linspace(1,0,n)` , `n = int(0.1 * sr)` . 2. `pyln.Meter(sr).integrated_loudness(data)` → `pyln.normalize.loudness(data, loudness, -14.0)` . 3. Nếu peak > 0,98 thì scale xuống 0,98 (chống clip số). 4. Không có `pyloudnorm` hoặc loudness không hữu hạn (ví dụ file toàn im lặng → `-inf` ) → peak normalize 0,95.

`chunk_audio_file()` (cắt audio thành đoạn 60 s, `audio.py:203` ) còn trong file nhưng không được gọi ở đâu trong repo (đã grep toàn bộ `*.py` ). Có thể là di sản của tính năng RVC được nhắc trong `PROJECT_SUMMARY.md` (suy đoán, chưa xác minh).

### 4.10. Sơ đồ tuần tự toàn bộ Bước 2

4.11. Các "bản vá môi trường" trong `src/main.py`

Không phải lý thuyết TTS, nhưng hội đồng có thể hỏi "vì sao file 1109 dòng": phần đầu `src/main.py` (dòng 9–137) chứa các monkeypatch để chạy được trên Windows + PyTorch mới:

- Import `datasets` trước để tránh crash khởi tạo PyTorch 2.6 trên Windows ( `:9-13` ). Vá `torch.utils._pytree.register_constant` , `functorch.compile` , tắt flex attention của `torchtune` ( `:18-41` ). `sys.stdout.reconfigure(encoding='utf-8')` chống `UnicodeEncodeError` tiếng Việt ( `:43-49` ). Vá `dataclasses._get_field` cho lỗi "mutable default" của fairseq/hydra trên Python 3.11 ( `:59-93` ). Giả `is_torchcodec_available` , expose `GPT2PreTrainedModel` cho coqui-tts ( `:95-120` ). Thêm `torch/lib` vào DLL search path cho onnxruntime-gpu ( `:126-137` ).

Phần còn lại là `process_single_file` , bảng tổng kết batch và wizard tương tác cho việc chạy AIVoice độc lập (không dùng trong luồng orchestrator).

## 5. Sơ đồ tổng hợp: một chương đi qua Bước 2

## 6. Hạn chế & hướng phát triển

Các điểm dưới đây rút ra từ việc đọc code; một số chưa chạy kiểm chứng end-to-end — nói rõ khi trình bày.

### 6.1. Hạn chế đã thấy trong code

#### 1. Cắt câu làm vỡ số có dấu chấm (Edge/Piper): `chunk_text` tách theo `[.?

!;]+` trước khi ghép lại bằng khoảng trắng. Chạy thử với text chưa chuẩn hoá: `1.500.000` → `"1. 500. 000"` . Với `edge` / `piper` (không qua `vietnamese_cleaners` ), engine có thể đọc thành ba số rời. Hướng sửa: bảo vệ mẫu `\d[.,]\d` trước khi tách câu, hoặc chuẩn hoá số cho mọi engine. 2. Số thập phân: `num2words(3.5, lang='vi')` → "ba phẩy năm mươi" (đúng ra "ba phẩy năm"). Dấu `,` vừa là thập phân vừa là phân cách nghìn nên `12,500` bị hiểu là 12500. 3. Viết tắt quá tham lam: regex `\bm\b` → "mét" sẽ đổi mọi chữ "m" đứng riêng (ví dụ "anh m" trong văn nói) thành "mét". 4. `vietnamese_cleaners` gộp mọi dòng thành một (vì `\s+` → `" "` ), nên với engine offline, `chunk_text` không còn ranh giới đoạn văn — tiêu đề chương bị gộp chung với câu đầu (thấy trong ví dụ chạy thật: "chương mười hai , gặp lại lý phàm..."). 5. Tốc độ không đồng nhất: `speed` có tác dụng với Edge (rate %), Piper ( `length_scale` ), XTTSv2 ( `speed` ), nhưng Kokoro và VieNeu bỏ qua. 6. Batch không fail khi chương lỗi: trong `--input-dir` , một chương `tts_file_failed` không làm adapter thoát mã khác 0 → orchestrator vẫn đặt `VOICE_GENERATED` . Bù lại, logic resume sẽ đọc lại chương thiếu ở lần chạy sau. 7. Semantic cache có thể trả nhầm audio (ngưỡng ngữ nghĩa 0,95, model tiếng Anh) — đã mặc định tắt. 8. Peak limit bằng scale tuyến tính: nếu peak > 0,98 sau LUFS, cả file bị hạ xuống → loudness thực tế thấp hơn -14 LUFS một chút. Limiter thật (nén đỉnh) sẽ giữ loudness tốt hơn. 9. Đường dẫn model tương đối từ WebUI (theo đọc code, chưa chạy kiểm chứng end-to-end):

- Piper: WebUI gán `s2Model = "models/piper/vi_VN-vais1000-medium.onnx"` , pipeline gọi `os.path.abspath(...)` với cwd của orchestrator (gốc repo, `pipeline.py:444` ), trong khi model thật nằm ở `AIVoice/models/piper/` (gốc repo không có thư mục `models/` ). Piper không thấy file và rơi vào nhánh tự tải về `<gốc repo>/models/piper/` — chạy được nhưng tải trùng 63 MB. Hai giọng còn lại trong dropdown ( `vi_VN-vivos-x_low` , `en_US-lessac-medium` ) không có file và không nằm trong danh sách tự tải → `FileNotFoundError` . Clone: WebUI gán `"models/xttsv2"` (thiếu dấu `_` , `webui/app.js:657` ) trong khi thư mục thật là `AIVoice/models/xtts_v2` → `clone.py:26-27` ném `FileNotFoundError` , mọi chunk lỗi, chương `FAILED` — trừ khi người dùng tự sửa ô đường dẫn. Piper khi không truyền `--model` : `model` rơi về `"models/xtts_v2"` của `default.json` (thư mục XTTS) → `PiperVoice.load` thất bại, fallback `piper.exe` cũng thất bại.

10. Edge phụ thuộc dịch vụ không chính thức: Microsoft có thể đổi giao thức/chặn; retry chỉ giảm chứ không loại bỏ rủi ro. 11. XTTSv2 cắt cụt text > 248 ký tự là mất chữ; hiện an toàn vì `chunk_text` đã giới hạn 240, nhưng nếu bật `phonemize` (IPA dài hơn chữ gốc) thì chunk có thể vượt và bị cắt.

### 6.2. Hướng phát triển

Module text normalization tiếng Việt đầy đủ (ngày tháng, giờ, số La Mã "Chương IV", đơn vị, số điện thoại) áp dụng cho mọi engine, có bộ test. Giọng theo nhân vật: LLM ở Bước 3 đã tách thoại; có thể gán mỗi nhân vật một giọng (Kokoro/VieNeu có nhiều giọng, clone có ref riêng). Điều khiển cảm xúc/ngữ điệu theo cảnh (VieNeu `emotion` , style vector Kokoro). Đo MOS (Mean Opinion Score) / CER qua Whisper (sinh audio → nhận dạng lại → so chữ) để so sánh engine một cách định lượng. Streaming TTS, song song hoá theo chương khi dùng engine online. Thay peak-scale bằng true-peak limiter; đo VRAM cho Kokoro/VieNeu.

## Câu hỏi hội đồng có thể hỏi

### 1. Bước 2 nhận gì và trả ra gì?

Nhận thư mục chương `.md` đã dịch (tên chứa `" - [VI] "` ) trong `storage/<truyện>/translated/` (fallback `raw/` ); trả về `.wav` cùng tên, nằm cùng thư mục ( `pipeline.py:403-431` , `adapter_tts_cli.py:180, 212` ).

### 2. Vì sao có 5 engine? Engine nào mặc định?

Vì đánh đổi giữa chất lượng, offline, tài nguyên và clone giọng; GPU 6 GB phải dành VRAM cho Stable Diffusion. Mặc định `edge` ( `global_config.json` → `tts.default_engine` ), vì chất lượng tốt và không tốn tài nguyên cục bộ; offline có `piper` , `kokoro` , `vieneu` , `clone` .

### 3. Thêm một engine mới cần sửa gì?

Tạo class kế thừa `BaseTTSEngine` cài `generate(text, output_path, **kwargs)->` `bool` , thêm nhánh khởi tạo trong `adapter_tts_cli.py:121-141` (và `src/main.py` nếu chạy độc lập), đặt `max_workers` phù hợp trong `main.py:249-254` , thêm option ở WebUI. Đây là Adapter/Strategy pattern — lõi `process_single_file` không đổi.

### 4. VITS khác pipeline Tacotron + HiFi-GAN thế nào?

VITS huấn luyện end-to-end một mạng duy nhất: VAE (posterior encoder + decoder HiFi-GAN), prior từ text encoder + normalizing flow, MAS để học alignment, stochastic duration predictor, loss GAN. Không có mel trung gian cứng giữa 2 model train riêng → ít lỗi tích luỹ, suy luận nhanh.

### 5. `length_scale` trong Piper là gì, dự án dùng ra sao?

Hệ số nhân trường độ âm vị của duration predictor. Dự án đặt `length_scale = 1/speed` ( `piper.py:85-86` ); speed 1,25 → 0,8 → đọc nhanh hơn 25%.

### 6. Voice cloning zero-shot hoạt động ra sao?

XTTSv2 tính từ audio mẫu hai thứ: `gpt_cond_latent` (qua perceiver resampler, điều kiện cho GPT) và `speaker_embedding` (điều kiện cho decoder HiFi-GAN). GPT sinh token âm thanh DVAE từ text + latent, decoder ra sóng 24 kHz. Không train thêm; dự án cache latent theo khoá (file mẫu + tham số) để 1 chương chỉ tính 1 lần ( `clone.py:198-219` ).

### 7. Vì sao chia văn bản thành chunk, con số 240 ở đâu ra?

XTTSv2 tiếng Việt giới hạn ~250 ký tự (vượt → CUDA assertion); model autoregressive câu dài dễ lặp/nuốt chữ; chunk nhỏ cho phép song song & retry. `max_chars=240` ( `text.py:36` ) chừa biên an toàn, `max_words=30` từ `default.json` . XTTS còn tự cắt ở 248 → phòng thủ 2 lớp.

### 8. Thuật toán chunk có gì đặc biệt?

Hai chiều: bẻ câu dài theo dấu phẩy/khoảng trắng khi vượt 30 từ hoặc 240 ký tự, và gộp câu ngắn liên tiếp trong cùng đoạn cho đến ngưỡng → vừa an toàn cho model vừa giữ ngữ điệu liền mạch.

### 9. Vì sao số luồng khác nhau theo engine?

GPU PyTorch ( `clone/kokoro/vieneu` ) = 1 để chống OOM và vì model không thread-safe; Piper ONNX nhẹ = 6; Edge online = 3 kèm stagger `(idx%3)*0.4 + U(0,0.2)` s để tránh rate-limit ( `main.py:249-273` ).

### 10. Nếu Edge bị lỗi mạng?

Mỗi chunk retry tối đa 5 lần, backoff 2/5/10/15 s, xoá file rỗng giữa các lần ( `edge.py:36-61` ). Nếu vẫn lỗi, chương đó `FAILED` (log `tts_file_failed` ), không tạo audio thiếu đoạn; các chương khác vẫn chạy tiếp và tiến trình vẫn thoát mã 0 (nên trạng thái truyện vẫn là `VOICE_GENERATED` — một hạn chế đã nêu ở 6.1); chạy lại sẽ chỉ đọc chương chưa có audio (resume). Muốn độc lập mạng thì chọn engine offline.

### 11. Chuẩn hoá tiếng Việt làm những gì? Có hạn chế gì?

NFC, lowercase, ký hiệu ( `%` →"phần trăm"…), viết tắt ( `SĐT` , `TP` , `HCM` , `km` …), bỏ phân cách nghìn, số → chữ bằng `num2words(lang='vi')` ( `text.py:168-216` ). Chỉ áp cho engine offline. Hạn chế: "3,5" → "ba phẩy năm mươi"; `m` đứng riêng bị đổi thành "mét"; chưa xử lý ngày tháng/số La Mã.

### 12. Vì sao ép Unicode NFC?

Một chữ có dấu có thể mã hoá 1 code point (NFC) hoặc nhiều code point (NFD); bảng phoneme/tokenizer chỉ nhận một dạng, lệch dạng → đọc sai hoặc bỏ ký tự. Code ép NFC khi đọc file ( `main.py:158-159` ), trong Piper và trong cleaners.

### 13. LUFS là gì, vì sao -14?

Đơn vị độ to cảm nhận theo ITU-R BS.1770 (K-weighting + gating). -14 LUFS là mức chuẩn phổ biến của nền tảng streaming; chuẩn hoá giúp các chương to đều nhau và cân với nhạc nền ở Bước 3. Dùng `pyloudnorm` , sau đó giới hạn đỉnh 0,98 ( `audio.py:164-193` ).

### 14. Semantic cache là gì, sao mặc định tắt?

Lưu audio theo câu, tra câu mới bằng cosine similarity trên embedding `all-` `MiniLM-L6-v2` (384 chiều, FAISS `IndexFlatIP` ), ngưỡng 0,95; fallback n-gram ký tự. Tắt vì "giống nghĩa" không đảm bảo "giống chữ" → có thể đọc sai câu, và model embedding là tiếng Anh.

### 15. Làm sao đảm bảo không tràn VRAM khi TTS?

Chạy trong process con riêng; engine GPU chỉ 1 worker; XTTSv2 dùng FP16 autocast + TF32 + SDPA, `empty_cache` sau mỗi chunk (profile `rtx3060` ) và sau mỗi file; adapter `empty_cache` + `ipc_collect` trong `finally` ; process thoát thì driver thu hồi hết VRAM. Khuyến nghị GPU 6 GB dùng `edge` / `piper` để chừa VRAM cho Bước 3.

## Tóm tắt 1 phút

"Bước 2 biến mỗi chương truyện tiếng Việt thành một file giọng đọc WAV. Orchestrator không import code TTS mà gọi `adapter_tts_cli.py` trong một tiến trình con dùng venv riêng của AIVoice, để cô lập thư viện và chắc chắn giải phóng VRAM; tiến độ được trả về bằng JSON-lines rồi đẩy lên giao diện qua SSE.

Bên trong, mỗi chương được ép Unicode NFC, bỏ markdown, với engine offline thì chuẩn hoá tiếng Việt: số thành chữ, viết tắt, ký hiệu. Sau đó thuật toán chunk hai chiều cắt văn bản thành đoạn tối đa 30 từ, 240 ký tự, con số này xuất phát từ giới hạn 250 ký tự của XTTSv2. Các đoạn được sinh song song theo phần cứng: 1 luồng cho engine GPU, 6 cho Piper, 3 cho Edge có giãn cách để tránh rate-limit. Cuối cùng các đoạn được ghép với 0,3 giây khoảng lặng, fade 0,1 giây và chuẩn hoá độ to về -14 LUFS.

Hệ thống có năm engine chung một interface `generate()` : Edge là neural TTS trên cloud, mặc định vì nhanh và không tốn VRAM; Piper là VITS xuất ONNX, chạy offline rất nhẹ; Kokoro dựa trên StyleTTS 2 với 14 giọng Việt; VieNeu là codec language model có biểu cảm; còn XTTSv2 nhân bản giọng zero-shot từ file mẫu nhờ speaker embedding, chạy FP16 có fallback FP32. Nhờ Adapter pattern, muốn thêm engine chỉ cần viết thêm một class."
