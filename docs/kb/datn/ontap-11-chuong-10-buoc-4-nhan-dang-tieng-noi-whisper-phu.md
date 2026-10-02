# Chương 10. Bước 4 — Nhận dạng tiếng nói Whisper, phụ đề SRT & đồng bộ thời gian

- Mục tiêu chương: hiểu từ gốc cách máy "nghe" tiếng nói và ghi ra chữ kèm thời điểm (ASR với Whisper), hiểu file phụ đề SRT/ASS, và nắm chính xác trong code dự án: Whisper được gọi ở đâu, với tham số gì, phụ đề được tạo – khớp cảnh – "đốt" (burn) vào video như thế nào.

- Mọi trích dẫn code đều đọc trực tiếp từ repo (commit `f219bd9` ). Đường dẫn MediaComposer viết tắt: `MC/` = `AIVoice/apps/MediaComposer/` .

## 0. Đính chính quan trọng trước khi học (đọc kỹ để không nói sai trước hội đồng)

Khi đọc code, có mấy điểm khác với các ghi chú trình bày cũ ( `docs/trinh-bay-datn.md` ) và KB chatbot ( `docs/kb/04-buoc4-` `autosub.md` ). Cần nắm để trả lời đúng:

- **Điều hay bị nói:** "Bước 4 là một bước trong chuỗi 4 bước tự động" · **Sự thật trong code:** Trong code, tab Autosub là task nội bộ `step4` nhưng là công cụ rời, KHÔNG nằm trong chuỗi auto-run. "Bước 4: Ghép Video" trên UI chuỗi tự động là task nội bộ `step5` · **Bằng chứng:** `orchestrator/auto_run.py:1-20` ( `CHAIN_STEPS` , `DISPLAY_NO =` `{1: 1, 2: 2, 3: 3, 5: 4}` )
- **Điều hay bị nói:** "Whisper nghe file .wav giọng đọc TTS để khớp phụ đề cho video hoạt hình" · **Sự thật trong code:** Trong pipeline dựng hoạt hình (Bước 3), Whisper bị tắt cưỡng bức (chính sách M1). Phụ đề được tự sinh từ kịch bản, thời gian chia theo tỷ lệ số từ · **Bằng chứng:** `MC/adapter_video_cli.py:222"use_whisper": False #` `Enforced... (M1 policy)` ; `MC/app/services/storytelling/orchestrator.py:266-297`
- **Điều hay bị nói:** "Whisper xuất file `.ass` / có hiệu ứng karaoke" · **Sự thật trong code:** `create_subtitle` chỉ ghi SRT. Khi burn, style ASS được áp qua tham số `force_style` của filter `subtitles` (libass) — không có karaoke · **Bằng chứng:** `MC/app/services/subtitle.py:94-104` ; `MC/app/services/video.py:1424-1581`
- **Điều hay bị nói:** "Whisper chạy trên GPU" · **Sự thật trong code:** Phụ thuộc cấu hình. File `config.toml` trên máy dev: `model_size="medium"` , `device="cpu"` , `compute_type="int8"` . Mặc định trong code (khi không có toml): `base` , `cuda+float16` nếu có GPU, ngược lại `cpu+int8` . Lưu ý: máy cài mới bằng `AIVoice/setup.bat` sẽ được copy `config.toml.example` → `medium / cuda /` `float32` (chạy GPU!) · **Bằng chứng:** `MC/config.toml:14-17` ; `MC/app/config.py:24-30` ; `AIVoice/setup.bat:350-359`

Nói ngắn gọn: Whisper trong dự án phục vụ chủ yếu cho tab "Tự Động Tạo Phụ Đề & Lồng Tiếng" (Autosub) — nhận một video bất kỳ (tiếng Anh/Trung), nghe, ra phụ đề gốc, dịch sang tiếng Việt, (tuỳ chọn) lồng tiếng, rồi burn phụ đề. Còn trong video hoạt hình từ truyện, khả năng dùng Whisper để đồng bộ vẫn có trong code ( `use_whisper=True` ) nhưng đang tắt vì lý do VRAM/thời gian — và đây là một quyết định thiết kế có lý do, sẽ phân tích ở mục 3.4.

## 1. Vai trò trong hệ thống

### 1.1 Hai "nơi" dùng tới phụ đề/thời gian

1.2 Input / Output của tab Autosub ( `step4` )

- **Nội dung:** Input `video_path` (file local) hoặc `download_url` (+ `platform` : bilibili/tiktok/douyin/youtube/generic) · **Nguồn:** `orchestrator/main.py:167-199` ( `Step4Schema` )
- **Nội dung:** Tuỳ `source_lang` (English/Chinese), `sub_source` ( `whisper` | `ocr` ), `clean_audio` chọn (Demucs), `enable_voiceover` , `tts_engine` , `ducking_ratio` , kiểu chữ (font, size, màu, viền, nền, vị trí) · **Nguồn:** cùng file
- **Nội dung:** Output `<tên>_autosub_<YYYYmmdd_HHMMSS>.mp4` trong `output_dir` ; trung gian trong `task_dir` : `extracted_audio.wav` , `source_subtitles.srt` , `vietnamese_subtitles.srt` , `translated_video.mp4` · **Nguồn:** `MC/adapter_autosub_cli.py:203-213` ; `MC/app/services/composer.py:315-437`

### 1.3 Input / Output của phần timing trong Bước 3

- Nội dung

- Input

- File `.md` kịch bản chương + file `.wav` giọng đọc từ Bước 2 (+ `.srt` nếu người dùng tự cung cấp)

- Output

- Mỗi `Scene` có `start_time` , `end_time` , `duration_sec` ; file `generated_from_script.srt` (hoặc `whisper_sync.srt` nếu bật Whisper)

## 2. Nền tảng lý thuyết từ gốc

### 2.1 Âm thanh trong máy tính: waveform và lấy mẫu

Trực giác. Âm thanh là dao động áp suất không khí. Micro biến nó thành điện áp thay đổi theo thời gian. Máy tính "chụp" giá trị điện áp đó rất nhiều lần mỗi giây — gọi là lấy mẫu (sampling). Chuỗi số thu được là waveform.

- Sample rate

- : số mẫu/giây. Dự án tách audio ở 16 000 Hz ( `"-ar", "16000"` , `MC/app/services/composer.py:338` ), vì

- Whisper được huấn luyện ở 16 kHz ( `sampling_rate=16000` trong `faster_whisper/feature_extractor.py` ).

- . Với 16 kHz → tới 8 kHz, đủ cho tiếng nói (năng lượng giọng

- Định lý Nyquist: lấy mẫu ở

- chỉ biểu diễn được tần số tới

- nói chủ yếu dưới ~4 kHz; phụ âm xát như "s" lên cao hơn nhưng 8 kHz vẫn đủ nhận dạng). Bit depth: `pcm_s16le` = mỗi mẫu là số nguyên 16 bit có dấu, little-endian. `-ac 1` = mono (Whisper chỉ cần 1 kênh).

```
# MC/app/services/composer.py:330-341
if has_audio:
    # We convert to mono, 16kHz PCM WAV for Whisper optimization
    audio_cmd = [
        ffmpeg_bin, "-y", "-i", video_path,
        "-vn",
                               # bỏ luồng hình
        "-ac", "1",
                               # mono
        "-ar", "16000",
                               # 16 kHz
        "-acodec", "pcm_s16le",
        audio_path
    ]
```

- Vì sao tự convert trước mà không đưa thẳng mp4 cho Whisper? faster-whisper vẫn tự decode được (qua PyAV), nhưng convert trước giúp: (1) file WAV dùng lại được cho Demucs và cho bước ducking, (2) kiểm soát chắc chắn định dạng, (3) phát hiện sớm video không có audio ( `has_audio` , `composer.py:318-327` ).

### 2.2 Từ waveform sang phổ: STFT

Vấn đề: waveform 1 giây = 16 000 con số dao động lên xuống, mắt người (và mạng nơ-ron) khó nhận ra "đây là âm /a/". Cái đặc trưng cho âm vị là nó gồm những tần số nào, và chúng thay đổi theo thời gian ra sao.

Biến đổi Fourier tách một đoạn tín hiệu thành tổng các sóng sin ở các tần số khác nhau — giống lăng kính tách ánh sáng trắng thành cầu vồng. Nhưng Fourier trên cả file thì mất thông tin thời gian. Giải pháp: STFT (Short-Time Fourier Transform) — cắt tín hiệu thành các cửa sổ ngắn chồng lấp, Fourier từng cửa sổ.

- : mẫu thứ của waveform. : hàm cửa sổ (Whisper dùng Hann) làm mềm hai đầu đoạn cắt, tránh "rò phổ". : độ dài cửa sổ = `n_fft = 400` mẫu = 25 ms ở 16 kHz. : bước nhảy = `hop_length = 160` mẫu = 10 ms. → mỗi giây có 100 frame. : chỉ số frame (thời gian); : chỉ số bin tần số. : năng lượng (power spectrum) — ảnh 2 chiều thời gian × tần số gọi là spectrogram.

(Các giá trị `n_fft=400` , `hop_length=160` , `chunk_length=30` đọc từ `faster_whisper/feature_extractor.py` trong `.venv` của AIVoice.)

### 2.3 Thang Mel và log-Mel spectrogram

Trực giác: tai người không cảm nhận tần số tuyến tính. Chênh 100 Hz → 200 Hz nghe "xa" hơn nhiều so với 8000 Hz → 8100 Hz. Thang Mel nén trục tần số theo cảm nhận của tai:

- : tần số Hz;

- : giá trị mel. Dưới ~1 kHz gần tuyến tính, trên đó gần logarit.

Thực hiện: nhân power spectrum với một bộ lọc tam giác (mel filterbank) — 80 bộ lọc (Whisper tiny→large-v2; large-v3 dùng 128), mỗi bộ lọc gom năng lượng một dải tần. Kết quả: mỗi frame 10 ms → vector 80 số.

Cuối cùng lấy log (vì cảm nhận độ to của tai cũng gần logarit, và log giúp dải giá trị gọn lại). Whisper còn kẹp (clamp) giá trị thấp hơn max − 8 và chuẩn hoá về khoảng nhỏ. Kết quả: log-Mel spectrogram kích thước

- cho mỗi đoạn 30 giây

(3000 frame × 10 ms).

- Câu tóm để nói: "Log-Mel spectrogram là một 'bức ảnh' của âm thanh — trục ngang là thời gian 10 ms/cột, trục dọc là 80 dải tần theo cảm nhận tai người, độ sáng là log năng lượng. Whisper đọc bức ảnh này."

### 2.4 Bài toán ASR và cách làm cổ điển vs hiện đại

ASR (Automatic Speech Recognition): cho chuỗi đặc trưng âm thanh

- , tìm chuỗi chữ

- có xác suất cao nhất:

- **Thế hệ:** Cổ điển (HMM-GMM, Kaldi) · **Cách làm:** Tách 3 mô hình: âm học (acoustic), phát âm (lexicon), ngôn ngữ (LM) + giải mã WFST · **Điểm yếu:** Pipeline phức tạp, cần từ điển phát âm cho từng ngôn ngữ
- **Thế hệ:** CTC (DeepSpeech, wav2vec2-CTC) · **Cách làm:** 1 mạng, xuất nhãn cho từng frame, cho phép ký tự "blank" rồi gộp · **Điểm yếu:** Giả định các frame độc lập có điều kiện → yếu về ngữ cảnh ngôn ngữ, thường cần LM ngoài
- **Thế hệ:** Encoder–decoder / seq2seq (Whisper) · **Cách làm:** Encoder "nghe" cả đoạn, decoder "viết" từng token như một mô hình ngôn ngữ có điều kiện · **Điểm yếu:** Có thể ảo giác (hallucination), chậm hơn do tự hồi quy (autoregressive)

### 2.5 Kiến trúc Whisper: encoder–decoder Transformer

Whisper (OpenAI, 2022, bài "Robust Speech Recognition via Large-Scale Weak Supervision") là một Transformer encoder– decoder chuẩn, gần như không có "mẹo" kiến trúc — sức mạnh đến từ dữ liệu.

Encoder. Hai lớp tích chập 1 chiều (kernel 3) làm "mắt nhìn cục bộ", lớp thứ hai stride 2 nên 3000 frame → 1500 vị trí (mỗi vị trí ≈ 20 ms). Sau đó các khối Transformer với self-attention: mỗi vị trí nhìn toàn bộ 30 giây để hiểu ngữ cảnh.

Self-attention, nhắc lại ngắn: với mỗi vị trí tạo 3 vector Query

- , Key

- , Value

- : độ "liên quan" giữa từng cặp vị trí; chia

- để giá trị không quá lớn; softmax biến thành trọng số tổng 1; nhân

- lấy trung bình có trọng số thông tin các vị trí liên quan.

Decoder. Là một mô hình ngôn ngữ: sinh từng token một (autoregressive). Mỗi bước có 2 loại attention:

- 1. Masked self-attention trên các token đã sinh (không nhìn tương lai). 2. Cross-attention: Query từ decoder, Key/Value từ 1500 vector của encoder — tức là "khi viết chữ này, nên nghe đoạn âm thanh nào". Chính trọng số cross-attention này về sau được dùng để suy ra thời điểm từng từ (mục 2.8).

Kích thước model (theo bài báo/model card Whisper):

- **Tên:** tiny · **Tham số:** 39 M · **Số lớp (enc/dec):** 4 · **Độ rộng:** 384
- **Tên:** base (mặc định code) · **Tham số:** 74 M · **Số lớp (enc/dec):** 6 · **Độ rộng:** 512
- **Tên:** small · **Tham số:** 244 M · **Số lớp (enc/dec):** 12 · **Độ rộng:** 768
- **Tên:** medium (config.toml dự án) · **Tham số:** 769 M · **Số lớp (enc/dec):** 24 · **Độ rộng:** 1024
- **Tên:** large (v1/v2/v3) · **Tham số:** 1 550 M · **Số lớp (enc/dec):** 32 · **Độ rộng:** 1280

### 2.6 Dữ liệu huấn luyện: 680 000 giờ "weakly supervised"

- 680 000 giờ audio có kèm transcript thu thập từ Internet. "Weak supervision" = nhãn không được con người gán sạch chuyên cho ASR — là phụ đề/transcript có sẵn trên mạng, có lỗi, có lệch. Đổi chất lượng nhãn lấy khối lượng và đa dạng (giọng, tạp âm, micro, ngôn ngữ). Trong đó khoảng 117 000 giờ thuộc 96 ngôn ngữ không phải tiếng Anh và khoảng 125 000 giờ dữ liệu dịch X→Anh. Đã lọc: bỏ transcript do máy ASR khác sinh (tránh học lỗi của máy), khử trùng lặp... Hệ quả: Whisper zero-shot tốt — dùng ngay, không cần fine-tune cho từng miền; bền (robust) với tạp âm hơn các model chỉ train trên LibriSpeech. large-v3 (2023) được train thêm lượng dữ liệu lớn hơn nhiều (bao gồm dữ liệu gán nhãn giả bằng large-v2) và dùng 128 mel bin.

### 2.7 Đa nhiệm bằng token đặc biệt, gồm cả token thời gian

Whisper làm nhiều việc (nhận dạng, dịch sang Anh, phát hiện ngôn ngữ, phát hiện không có tiếng nói, đánh dấu thời gian) trong một model bằng cách nhét lệnh vào đầu chuỗi token của decoder:

```
<|startoftranscript|> <|vi|> <|transcribe|> <|0.00|> Xin chào các bạn <|1.84|> <|2.10|> Hôm nay ... <|endoftext|>
```

- **Token:** `<|startoftranscript|>` · **Ý nghĩa:** Bắt đầu
- **Token:** `<|en|>` , `<|zh|>` , `<|vi|>` ... · **Ý nghĩa:** Ngôn ngữ. Nếu không truyền `language` , model tự dự đoán token này trước = language detection
- **Token:** `<|transcribe|>` / `<|translate|>` · **Ý nghĩa:** Chép lại nguyên ngôn ngữ / dịch sang tiếng Anh
- **Token:** `<|notimestamps|>` · **Ý nghĩa:** Không sinh token thời gian
- **Token:** `<|0.00|>` … `<|30.00|>` · **Ý nghĩa:** Token thời gian, lượng tử hoá bước 20 ms, tương đối trong cửa sổ 30 s — đánh dấu đầu/cuối mỗi segment
- **Token:** `<|nospeech|>` · **Ý nghĩa:** Đoạn không có tiếng nói

Từ vựng văn bản là byte-level BPE (giống họ GPT) — không cần từ điển phát âm, viết được mọi ngôn ngữ, kể cả tiếng Việt có dấu.

Audio dài hơn 30 s được xử lý theo cửa sổ trượt: giải mã 30 s, lấy token thời gian cuối cùng làm điểm bắt đầu cửa sổ tiếp theo; văn bản cửa sổ trước có thể được đưa làm "prompt" cho cửa sổ sau ( `condition_on_previous_text` , mặc định `True` trong faster-whisper).

### 2.8 Giải mã: beam search, temperature fallback, word-level timestamps

Beam search ( `beam_size=5` trong code, `MC/app/services/subtitle.py:39` ): thay vì mỗi bước chọn 1 token xác suất cao nhất (greedy — dễ đi vào ngõ cụt), giữ 5 giả thuyết tốt nhất song song, cuối cùng chọn chuỗi có tổng log-xác suất cao nhất. Tốn gấp ~5 lần tính toán ở decoder nhưng chính xác hơn.

Temperature fallback (mặc định thư viện, code không đổi): nếu kết quả bị nghi là rác — `compression_ratio > 2.4` (chữ lặp lại nhiều, nén gzip được quá tốt → dấu hiệu lặp vô hạn) hoặc `avg_logprob<-1.0` — thì giải mã lại với nhiệt độ lấy mẫu tăng dần `[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]` . Chỉ ở nhiệt độ 0 mới dùng beam search; ở nhiệt độ > 0 decoder chuyển sang lấy mẫu ngẫu nhiên (sampling, softmax chia cho

- — lớn thì phân phối "phẳng" hơn, dễ thoát vòng lặp) và lấy `best_of=5` mẫu.

`no_speech_threshold=0.6` : nếu xác suất `<|nospeech|>` cao và logprob thấp thì bỏ đoạn. (Giá trị đọc từ chữ ký `WhisperModel.transcribe` trong `faster_whisper/transcribe.py` bản 1.2.1.)

Word-level timestamps ( `word_timestamps=True` , `subtitle.py:40` ): token thời gian chỉ cho mốc segment (một câu dài vài giây). Để có mốc từng từ:

- 1. Lấy ma trận cross-attention của một số "alignment heads" (các head mà nghiên cứu thấy bám sát vị trí âm thanh) — cho biết mỗi token văn bản "nhìn" vào frame âm thanh nào. 2. Chạy DTW (Dynamic Time Warping) — thuật toán quy hoạch động tìm đường căn chỉnh đơn điệu (không quay lui) tốt nhất giữa chuỗi token và chuỗi frame. 3. Gộp token thành từ → mỗi từ có `start` , `end` (độ phân giải ~20 ms).

Kết quả trả về trong code là `segment.words` , mỗi `word` có `.word` , `.start` , `.end` — dự án dùng chính các trường này để tự cắt câu (mục 4.3).

### 2.9 VAD — Voice Activity Detection

Vấn đề: Whisper khi gặp đoạn im lặng/nhạc nền dài hay ảo giác (bịa ra câu kiểu "Thanks for watching!") vì dữ liệu train từ YouTube thường có câu đó ở cuối. VAD là bộ lọc nhỏ quyết định đoạn nào có người nói, chỉ đưa đoạn đó cho Whisper.

- faster-whisper dùng Silero VAD (mạng nơ-ron nhỏ, chạy ONNX; trong `.venv` có `faster_whisper/assets/silero_vad_v6.onnx` ). Nó xuất xác suất "đang nói" cho từng khung nhỏ; `threshold=0.5` (mặc định). Code dự án bật `vad_filter=True` (mặc định của `WhisperModel.transcribe` là `False` ) và đặt `min_silence_duration_ms=500` (mặc định thư viện là 2000). Nghĩa là: chỉ cần im lặng ≥ 0,5 s là tách thành đoạn nói mới — hợp với phụ đề (câu ngắn) hơn là chờ 2 s. Các tham số VAD khác giữ mặc định: `speech_pad_ms=400` (đệm 0,4 s hai đầu để không cắt cụt âm), `min_speech_duration_ms=0` . Timestamp sau VAD được faster-whisper ánh xạ ngược về thời gian gốc của file, nên SRT vẫn khớp video.

### 2.10 faster-whisper và CTranslate2: vì sao nhanh hơn

`faster-whisper` (SYSTRAN) là bản cài đặt lại Whisper trên CTranslate2 — một engine suy luận (inference) viết bằng C++ cho các model Transformer. Trọng số giống hệt model OpenAI (được convert), nên độ chính xác tương đương, nhưng:

- Hợp nhất phép toán (layer fusion), cache K/V của decoder hiệu quả, không mang theo overhead của PyTorch autograd. Lượng tử hoá (quantization) trọng số:

- `compute_type` · Ý nghĩa · Bộ nhớ trọng số model medium (≈769 M tham số)
- `float32` · 4 byte/tham số · ≈ 3,1 GB
- `float16` · 2 byte/tham số, chạy GPU tensor core · ≈ 1,5 GB
- `int8` · 1 byte/tham số + hệ số tỉ lệ · ≈ 0,8 GB
- `int8_float16` · trọng số int8, tính toán fp16 (GPU) · ≈ 0,8 GB

Nguyên lý int8: mỗi hàng trọng số

- được xấp xỉ

- , với

- là số nguyên 8 bit và

- là hệ số

tỉ lệ (scale). Phép nhân ma trận chạy bằng số nguyên (rất nhanh trên CPU có lệnh SIMD như AVX2/VNNI), rồi nhân lại . Để phép nhân thật sự chạy bằng số nguyên, activation (đầu vào mỗi lớp) cũng được lượng tử hoá int8 động lúc chạy (tính scale theo từng lần), còn trọng số được lượng tử hoá sẵn một lần khi nạp model (scale theo từng hàng/kênh đầu ra). Kết quả int32 được nhân lại với tích hai scale để trả về số thực. Sai số làm tròn nhỏ so với nhiễu tự nhiên của mạng nên WER gần như không đổi (theo benchmark công bố của faster-whisper; dự án không tự đo).

Dự án dùng gì (đọc từ code, 3 tầng):

- **Tầng:** Mặc định cứng trong code · **Giá trị:** `model_size="base"` ; `device="cuda"` nếu `torch.cuda.is_available()` ngược lại `"cpu"` ; `compute_type="float16"` nếu cuda, ngược lại `"int8"` · **Nguồn:** `MC/app/config.py:24-30`
- **Tầng:** Mẫu cấu hình (được `AIVoice/setup.bat` copy thành `config.toml` khi cài mới nếu chưa có) · **Giá trị:** `medium` , `cuda` , `float32` · **Nguồn:** `MC/config.toml.example:11-14` ; `AIVoice/setup.bat:350-359`
- **Tầng:** Cấu hình thực tế trên máy dev (file gitignored) · **Giá trị:** `medium` , `cpu` , `int8` · **Nguồn:** `MC/config.toml:14-17`
- **Tầng:** Fallback trong hàm nếu thiếu khoá · **Giá trị:** `base` , `cpu` , `int8` · **Nguồn:** `MC/app/services/subtitle.py:20-22`

→ Trả lời hội đồng (đúng với máy dev; máy cài mới từ file mẫu sẽ là `cuda/float32` cho tới khi sửa `config.toml` ): "Em chạy Whisper medium trên CPU với int8 qua faster-whisper, để nhường toàn bộ VRAM 6–8 GB cho Stable Diffusion/XTTS; int8 giúp model medium chỉ chiếm ~0,8 GB RAM và chạy đủ nhanh trên CPU 16 luồng."

- Lưu ý: `hardware_adapter.py` có tính `whisper_device` (cuda cho GPU ≥ 7 GB, cpu cho GPU nhỏ — `MC/app/services/storytelling/hardware_adapter.py:32,64,75` ) nhưng `create_subtitle` không đọc giá trị này; nó đọc `config.whisper["device"]` . Đây là một điểm chưa thống nhất trong code — nên nói thật nếu bị hỏi.

### 2.11 Đo chất lượng ASR: WER

- : số từ bị thay (substitution),

- : bị xoá (deletion), : bị chèn thêm (insertion),

- : số từ trong transcript chuẩn. Tính bằng

- khoảng cách Levenshtein ở mức từ. WER càng thấp càng tốt; có thể > 100% nếu chèn quá nhiều. Dự án không tự đo WER (không có bộ test WER trong repo) — dựa vào số liệu công bố của Whisper. Nói thẳng nếu bị hỏi.

### 2.12 Định dạng phụ đề: SRT và ASS

SRT (SubRip) — đơn giản nhất: các khối cách nhau dòng trống, mỗi khối = số thứ tự, dòng thời gian, 1–n dòng chữ.

```
1
00:00:00,100 --> 00:00:03,420
Đêm ấy, trăng sáng vằng vặc.
```

```
2
00:00:03,420 --> 00:00:07,050
Lâm Phong đứng lặng trước cổng tông môn.
```

- Thời gian dạng `HH:MM:SS,mmm` (dấu phẩy trước mili-giây — khác WebVTT dùng dấu chấm). Không có style chuẩn (chỉ vài thẻ HTML như `<i>` được một số player hiểu).

ASS/SSA (Advanced SubStation Alpha) — có phần `[V4+ Styles]` : `FontName` , `FontSize` , `PrimaryColour` , `OutlineColour` , `BackColour` , `BorderStyle` , `Outline` , `Alignment` , `MarginV` ... và hiệu ứng (karaoke `\k` , di chuyển...). Thư viện render là libass.

Cách dự án kết hợp: lưu phụ đề dạng SRT (đơn giản, dễ parse/dịch), khi burn thì dùng filter `subtitles` của FFmpeg (bên trong là libass: nó chuyển SRT → ASS nội bộ) và ghi đè style bằng `force_style='FontName=...,FontSize=...,...'` .

Một số chi tiết ASS cần thuộc:

- Màu ASS viết `&HAABBGGRR` — ngược thứ tự so với `#RRGGBB` của web, `AA` là độ trong suốt (00 = đục, FF = trong suốt hoàn toàn). Hai hàm `_hex_to_ass_color` trong dự án làm việc đảo này ( `MC/app/services/video.py:1413-1421` trả `&H00BBGGRR` — có sẵn alpha 00 để sau đó thay bằng độ trong suốt của hộp nền; `MC/app/services/storytelling/video_assembler.py:38-46` trả `&HBBGGRR` không có alpha, libass hiểu là đục). `Alignment` theo bố cục bàn phím số: `2` = giữa-dưới, `5` = giữa-giữa, `8` = giữa-trên. `BorderStyle=1` : viền + bóng; `BorderStyle=3` : hộp nền đục sau chữ.

Khi nguồn là SRT, FFmpeg tự sinh header ASS với hệ toạ độ script mặc định `PlayResX=384, PlayResY=288` (không phải độ phân giải thật của video), libass co giãn theo tỷ lệ chiều cao khung — nên `FontSize=28` là cỡ tương đối (≈ 28/288 ≈ 10% chiều cao khung), không phải 28 pixel trên video 1080p. `MarginV` cũng tính theo thang 288 này. Hệ quả cần biết: ở vị trí `custom` , code tính `MarginV` theo pixel thật ( `(100 - custom_y_ratio) * video_height /` `100` , `video.py:1563-1575` ) nhưng libass lại hiểu theo thang 288 → với video 1080p, giá trị có thể vượt khung và đẩy chữ lệch lên trên. Đây là suy luận từ cách FFmpeg/libass hoạt động, (chưa xác minh bằng chạy thực tế) — nếu bị hỏi, nói là điểm cần kiểm tra.

### 2.13 "Burn" (hardsub) vs softsub

- **Hardsub (burn) — dự án dùng:** Cách làm Vẽ chữ vào từng frame rồi encode lại video · **Softsub (track phụ đề riêng):** Nhúng file phụ đề như một luồng trong mp4/mkv
- **Hardsub (burn) — dự án dùng:** Ưu Hiện trên mọi nền tảng (TikTok, YouTube Shorts, Facebook...) · **Softsub (track phụ đề riêng):** Không phải encode lại, bật/tắt được, đổi ngôn ngữ được
- **Hardsub (burn) — dự án dùng:** Nhược Tốn thời gian encode, không tắt được · **Softsub (track phụ đề riêng):** Nhiều nền tảng/player không hiển thị
- **Hardsub (burn) — dự án dùng:** Dự án burn vì đầu ra nhắm tới đăng mạng xã hội.

## 3. Vì sao chọn công nghệ này (so sánh phương án)

### 3.1 Chọn Whisper thay vì các ASR khác

- **Phương án:** Whisper (faster- whisper) · **Ưu:** Offline, mã nguồn mở (MIT), đa ngôn ngữ (Anh, Trung, Việt), bền với tạp âm, có timestamp từng từ · **Nhược:** Model lớn chậm, có thể ảo giác · **Kết luận:** Chọn — khớp yêu cầu chạy local
- **Phương án:** Google Speech-to-Text / Azure / AWS · **Ưu:** Chính xác, nhanh · **Nhược:** Trả phí, cần mạng, gửi dữ liệu ra ngoài · **Kết luận:** Trái mục tiêu "chạy hoàn toàn cục bộ"
- **Phương án:** Vosk / Kaldi · **Ưu:** Nhẹ, chạy CPU tốt · **Nhược:** Độ chính xác thấp hơn rõ, mỗi ngôn ngữ một model · **Kết luận:** Không đủ tốt cho video mạng xã hội nhiều tạp âm
- **Phương án:** wav2vec2 / XLS-R + CTC · **Ưu:** Tốt nếu fine-tune · **Nhược:** Cần fine-tune theo ngôn ngữ, cần LM ngoài, không có dấu câu · **Kết luận:** Tốn công
- **Phương án:** PhoWhisper (Whisper fine-tune tiếng Việt) · **Ưu:** Tốt hơn cho tiếng Việt · **Nhược:** Tab Autosub chủ yếu nghe Anh/Trung · **Kết luận:** Hướng phát triển nếu cần nghe tiếng Việt

3.2 Chọn faster-whisper thay vì `openai-whisper`

Cùng trọng số → cùng chất lượng; nhanh hơn nhiều và dùng ít bộ nhớ hơn nhờ CTranslate2 + int8 (repo faster-whisper công bố nhanh tới ~4 lần). Tích hợp sẵn Silero VAD và `word_timestamps` . Chạy CPU int8 hiệu quả → không tranh VRAM với Stable Diffusion/XTTS. Đây là lý do quyết định trên máy GPU 6–8 GB. Phiên bản ghim: `faster-whisper==1.2.1` ( `AIVoice/requirements.txt:63` ); trong `.venv` có `ctranslate2-4.8.2` .

### 3.3 Chọn SRT + burn bằng FFmpeg thay vì MoviePy

Code có hai cách burn: `ffmpeg` (mặc định) và `moviepy` (dự phòng) — `--burn-method` ( `MC/adapter_autosub_cli.py:34` ). FFmpeg `subtitles` filter chạy bằng libass (C), encode một lượt, nhanh; MoviePy vẽ `TextClip` bằng Python từng frame, chậm hơn nhiều. Nếu FFmpeg lỗi → tự rơi xuống MoviePy ( `MC/app/services/composer.py:443-463` ).

### 3.4 Câu hỏi thiết kế lớn: có nên chạy Whisper trên chính audio TTS của mình?

Ý tưởng: audio Bước 2 do TTS đọc nguyên văn kịch bản. Ta đã biết chữ, chỉ thiếu thời điểm. Chạy Whisper trên audio đó sẽ cho timestamp thật (từng từ) → phụ đề và cảnh khớp tiếng rất sát. Đây gọi là dùng ASR làm công cụ căn chỉnh (alignment).

Code có sẵn đường này: `step1_generate_script(..., use_whisper=True)` gọi `create_subtitle(audio_path,` `"whisper_sync.srt", language="vi")` ( `MC/app/services/storytelling/orchestrator.py:278-287` ).

Nhưng đang TẮT, với lý do ghi thẳng trong code:

```
# MC/app/services/storytelling/orchestrator.py:275-277
# Whisper (medium/cuda) tốn ~2-3GB VRAM + ~60s/chương. Mặc định TẮT để
# tiết kiệm VRAM: khi không có SRT sẵn, dùng timing theo tỷ lệ từ (bên dưới)
# rồi tự tạo SRT từ kịch bản. Chỉ chạy Whisper khi use_whisper=True.
```

và adapter ép `"use_whisper": False # Enforced: Do not use Whisper globally (M1 policy)` ( `MC/adapter_video_cli.py:222` ).

- **Whisper alignment:** Độ chính xác timing Cao (từng từ, ~20 ms) · **Tỷ lệ số từ (đang dùng):** Xấp xỉ — giả định tốc độ đọc đều
- **Whisper alignment:** Chi phí ~60 s/chương + 2–3 GB VRAM (nếu GPU) theo comment code · **Tỷ lệ số từ (đang dùng):** Gần 0
- **Whisper alignment:** Rủi ro chữ Whisper có thể nghe sai chữ → phụ đề sai chính tả, lệch văn bản gốc · **Tỷ lệ số từ (đang dùng):** Chữ phụ đề đúng 100% vì lấy từ kịch bản
- **Whisper alignment:** Phụ thuộc Thêm model, thêm lỗi DLL/CUDA · **Tỷ lệ số từ (đang dùng):** Không

Vì TTS đọc với tốc độ tương đối đều, và mỗi cảnh được neo vào tổng thời lượng thật (đọc chính xác từ file WAV), sai số tích luỹ bị chặn trong phạm vi một cảnh. Đổi lại được tốc độ và ổn định. Hướng tốt hơn (chưa làm): forced alignment (căn chỉnh văn bản đã biết với audio), hoặc lấy mốc từ chính engine TTS (Edge-TTS có sự kiện `WordBoundary` ) — rẻ hơn chạy ASR mà vẫn chính xác.

## 4. Hiện thực trong code

### 4.1 Bản đồ module

- **File:** `orchestrator/main.py` · **Vai trò:** API `POST /api/pipeline/step4` , `POST /api/autosub/prepare` , SSE log `GET` `/api/pipeline/logs/{task_key}` · **Hàm chính:** `run_step4` , `autosub_prepare` , `stream_logs`
- **File:** `orchestrator/pipeline.py` · **Vai trò:** Dựng lệnh CLI, gọi subprocess · **Hàm chính:** `start_step_4_autosub` (dòng 614-748)
- **File:** `orchestrator/config.py` · **Vai trò:** Mặc định cấu hình `autosub` · **Hàm chính:** khối `"autosub"` (dòng 107-130)
- **File:** `MC/adapter_autosub_cli.py` · **Vai trò:** CLI adapter: tải video, OCR subprocess, gọi composer, copy kết quả, giải phóng VRAM · **Hàm chính:** `main`
- **File:** `MC/app/services/composer.py` · **Vai trò:** Luồng 6 bước Autosub · **Hàm chính:** `ComposerWorkflow.run_translation_workflow` (dòng 272-522)
- **File:** `MC/app/services/subtitle.py` · **Vai trò:** Lõi Whisper → SRT; SRT từ text; giải phóng model · **Hàm chính:** `create_subtitle` , `create_subtitle_from_text` , `read_srt_text` , `release_whisper_model`
- **File:** `MC/app/services/audio_cleaner.py` · **Vai trò:** Tách giọng khỏi nhạc nền bằng Demucs · **Hàm chính:** `isolate_vocals`
- **File:** `MC/app/services/subtitle_extractor.py` · **Vai trò:** Nhánh OCR phụ đề cứng (PaddleOCR) + lấy frame preview · **Hàm chính:** `grab_preview_frame` , `extract_hardsub_ocr_srt`
- **File:** `MC/app/services/translation.py` · **Vai trò:** Dịch SRT theo lô bằng LLM (API OpenAI-compatible) · **Hàm chính:** `translate_srt` , `parse_srt` , `build_srt`
- **File:** `MC/app/services/dubbing.py` · **Vai trò:** TTS từng câu phụ đề, tua nhanh, ghép timeline, ducking · **Hàm chính:** `generate_dubbed_audio`
- **File:** `MC/app/services/video.py` · **Vai trò:** Burn phụ đề bằng FFmpeg · **Hàm chính:** `burn_subtitles_ffmpeg` , `_hex_to_ass_color`
- **File:** `MC/app/services/storytelling/audio_utils.py` · **Vai trò:** Đọc thời lượng audio chính xác · **Hàm chính:** `get_audio_duration`
- **File:** `MC/app/services/storytelling/srt_mapper.py` · **Vai trò:** Parse SRT, map cảnh ↔ thời gian, sinh SRT từ kịch bản · **Hàm chính:** `parse_srt` , `map_scenes_to_timeline` , `map_semantic_scenes_to_srt` , `generate_srt_from_scenes` , `_fix_monotonic`
- **File:** `MC/app/services/storytelling/video_assembler.py` · **Vai trò:** Ghép ảnh + audio + burn SRT cho video hoạt hình · **Hàm chính:** `assemble_video` , `_build_subtitle_style`

### 4.2 Luồng gọi: từ WebUI tới Whisper

Chi tiết đáng nhớ:

`run_step4` từ chối nếu thiếu cả `video_path` lẫn `download_url` (HTTP 400) và nếu task cùng `task_key` đang chạy ( `orchestrator/main.py:583-599` ). `start_step_4_autosub` gọi Python của venv AIVoice ( `AIVoice/.venv/Scripts/python.exe` ), `cwd="AIVoice"` — tách hẳn tiến trình để VRAM/DLL của Whisper, Torch, Paddle không đè lên orchestrator ( `orchestrator/pipeline.py:633-748` ). Adapter in log dạng một dòng JSON mỗi sự kiện ( `log_json` , `MC/adapter_autosub_cli.py:16-19` ): `autosub_progress` , `autosub_warn` , `autosub_done` , `autosub_error` . `ProcessManager` đọc stdout từng dòng vào `queue` , endpoint SSE đẩy cho WebUI. Khi xong, callback cập nhật `meta["status"]` = `AUTOSUB_COMPLETED` / `AUTOSUB_FAILED` / `CANCELLED` ( `pipeline.py:723-` `733` ) — chỉ khi task gắn với một truyện ( `story_name` ); task Autosub rời ( `autosub_<id>_step4` ) không có meta truyện để cập nhật. Khối `finally` của adapter gọi `release_whisper_model()` , `torch.cuda.empty_cache()` , `gc.collect()` ở mọi lần chạy trừ chế độ `--prepare-only` ( `if not args.prepare_only` , `MC/adapter_autosub_cli.py:237-250` ) — kể cả khi workflow lỗi. Thiết bị mặc định cho OCR: `ocr_use_gpu` lấy từ request, nếu không có thì `video_cfg.get("ocr_use_gpu", True)` (mặc định `True` ) → thêm cờ `--use-gpu` ( `pipeline.py:644-646, 720-721` ).

4.3 Lõi: `create_subtitle` — Whisper → SRT ( `MC/app/services/subtitle.py:14-107` )

Bước 1 — nạp model một lần (singleton toàn cục):

```
# MC/app/services/subtitle.py:20-30
model_size = config.whisper.get("model_size", "base")
device = config.whisper.get("device", "cpu")
compute_type = config.whisper.get("compute_type", "int8")
```

```
if not model:
    logger.info(f"Loading faster-whisper model: {model_size} on {device}")
    try:
        model = WhisperModel(model_size_or_path=model_size, device=device, compute_type=compute_type)
    except Exception as e:
        logger.error(f"Failed to load whisper model: {e}")
        return None
```

`model` là biến global → trong cùng tiến trình, gọi nhiều lần không nạp lại. Nếu thư viện chưa cài ( `WhisperModel is None` ) → trả `""` và log cảnh báo (dòng 16-18) — không crash cả pipeline.

Bước 2 — gọi transcribe với tham số thật:

```
# MC/app/services/subtitle.py:37-44
segments, info = model.transcribe(
    audio_file,
    beam_size=5,
    word_timestamps=True,
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=500),
    language=language
)
```

- **Tham số:** `beam_size` · **Giá trị:** 5 · **Ý nghĩa:** Beam search 5 nhánh (= mặc định thư viện)
- **Tham số:** `word_timestamps` · **Giá trị:** True · **Ý nghĩa:** Lấy mốc từng từ bằng cross-attention + DTW
- **Tham số:** `vad_filter` · **Giá trị:** True · **Ý nghĩa:** Bật Silero VAD (mặc định là False)
- **Tham số:** `min_silence_duration_ms` · **Giá trị:** 500 · **Ý nghĩa:** Im lặng ≥ 0,5 s thì cắt đoạn (mặc định 2000)
- **Tham số:** `language` · **Giá trị:** `"en"` / `"zh"` / `None` (Autosub); `"vi"` (storytelling) · **Ý nghĩa:** `None` → tự nhận diện, log `info.language` và `info.language_probability` (dòng 46)

Chú ý: `segments` là generator (lười) — việc giải mã thật sự diễn ra khi vòng `for segment in segments` chạy. Vì vậy code đặt `timer()` ngay trước vòng lặp để đo thời gian phiên âm (dòng 48, 91-92).

Bước 3 — tự cắt lại câu theo dấu câu, dựa trên mốc từng từ:

Whisper trả về segment có thể dài (vài câu). Phụ đề đọc dễ cần ngắn. Code duyệt từng từ, cộng dồn chữ, và cắt khi gặp từ chứa dấu câu:

```
# MC/app/services/subtitle.py:64-89 (rút gọn)
for word in segment.words:
    if not is_segmented:
        seg_start = word.start
                                        # từ đầu tiên của câu mới
        is_segmented = True
    seg_end = word.end
    seg_text += word.word
    if utils.str_contains_punctuation(word.word):
        seg_text = seg_text[:-1]
                                        # bỏ ký tự dấu câu cuối
        if not seg_text:
            continue
        recognized(seg_text, seg_start, seg_end)
        is_segmented = False
        seg_text = ""
...
if seg_text:
                                               # phần dư cuối segment
    recognized(seg_text, seg_start, seg_end)
```

- Bộ dấu câu: `"`，。！？；：、`,.!?;:)]}`）】》」』`”’"` ( `MC/app/utils/utils.py:90-95` ) — gồm cả dấu câu tiếng Trung, vì Autosub nghe cả tiếng Trung. Điểm yếu nhỏ: `str_contains_punctuation` kiểm tra dấu câu ở bất kỳ vị trí nào trong từ, còn code luôn cắt ký tự cuối. Với từ như `3.5` hay `U.S.` câu bị cắt giữa chừng và có thể mất 1 ký tự (ví dụ `" 3.5"` → chốt câu với `" 3."` ). Với dấu nháy đóng sau dấu chấm ( `."` ), chỉ dấu nháy bị bỏ. `recognized` bỏ khoảng trắng thừa (Whisper thường để dấu cách ở đầu mỗi `word.word` ) và bỏ câu rỗng (dòng 51-55). Nhờ `word_timestamps=True` , mỗi câu phụ đề có mốc bắt đầu = đầu từ đầu tiên, kết thúc = cuối từ cuối cùng — chính xác hơn mốc segment.

Bước 4 — ghi SRT:

```
# MC/app/utils/utils.py:81-88
def text_to_srt(idx: int, msg: str, start_time: float, end_time: float) -> str:
    def format_time(t: float):
        h = int(t / 3600)
        m = int((t % 3600) / 60)
        s = int(t % 60)
        ms = int((t % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    return f"{idx}\n{format_time(start_time)} --> {format_time(end_time)}\n{msg}\n"
```

Các khối nối bằng `"\n"` → giữa các khối có dòng trống đúng chuẩn SRT; ghi UTF-8 (dòng 94-104). (Mili-giây ở đây cắt cụt bằng `int` ; hàm `_format_srt_time` trong `srt_mapper.py:474-484` thì làm tròn và xử lý tràn 1000 ms — hai cách khác nhau tối đa 1 ms, không ảnh hưởng thực tế.)

Bước 5 — giải phóng bộ nhớ ( `release_whisper_model` , dòng 167-189): `del model` , `model = None` , `gc.collect()` , `torch.cuda.empty_cache()` nếu có CUDA. Gọi ngay sau khi phiên âm xong ( `composer.py:390` ) để bước dịch/TTS/burn phía sau có đủ RAM/VRAM.

4.4 Luồng Autosub đầy đủ: `run_translation_workflow` ( `MC/app/services/composer.py:272-522` )

- Các con số thật cần nhớ:
- Chi tiết · Giá trị · Vị trí
- Map ngôn ngữ cho Whisper · `English/en→"en"` , `Chinese/zh→"zh"` , khác → `None` (tự nhận) · `composer.py:376-381`
- Demucs · model `htdemucs` , `--two-stems vocals` , `--jobs 2` ; lỗi thì trả lại audio gốc (không làm hỏng pipeline) · `audio_cleaner.py:23-31, 37-54`
- Demucs chỉ áp cho nhánh Whisper · `clean_audio_flag = args.clean_audio if args.sub_source=="whisper" else False` · `adapter_autosub_cli.py:177`
- Dịch SRT · lô `batch_size = 40` câu, gửi JSON `{"i","t"}` , `temperature=0.3` , `max_tokens=2048` , thử lại 3 lần; thiếu API key → copy nguyên SRT gốc · `translation.py:56-140`
- Cảnh báo dịch hỏng · Nếu SRT tiếng Việt trùng y SRT nguồn → log `autosub_warn` . Lưu ý: điều kiện `source_srt and...` chỉ đúng ở nhánh OCR (ở nhánh Whisper biến `source_srt` là chuỗi rỗng) → nhánh Whisper không có cảnh báo này · `adapter_autosub_cli.py:111,` `215-226`
- SRT rỗng · Ghi `1\n00:00:00,000--> 00:00:01,000\n \n` · `composer.py:415-418`
- Lồng tiếng: tua nhanh · Nếu TTS dài hơn khung câu quá `tolerance = 0.3` s → `atempo` = thực/đích, tối đa 1.4× (giữ cao độ) · `dubbing.py:355-371`
- Ducking · Hệ số âm lượng nền `duck_volume = 1 - ducking_ratio/100` (mặc định 90 → 0,10); cửa sổ mỗi câu nới ±0,1 s; biểu thức `between(t,s,e)` ghi vào `ducking_filter.txt` để tránh giới hạn độ dài dòng lệnh Windows · `dubbing.py:444-463`

Ở đây ta thấy vai trò then chốt của timestamp Whisper: mọi thứ phía sau — dịch theo từng câu, lồng tiếng đặt đúng chỗ ( `start_sample = int(start_time * sample_rate)` , `dubbing.py:422` ), vùng ducking, phụ đề hiển thị — đều treo trên mốc thời gian mà Whisper sinh ra. Sai timestamp thì cả chuỗi lệch.

4.5 Nhánh thay thế: OCR phụ đề cứng ( `sub_source="ocr"` )

Khi video đã có chữ in sẵn (hardsub, rất phổ biến ở video Trung Quốc) hoặc không có tiếng:

Adapter chạy `python -m app.services.subtitle_extractor` trong tiến trình con riêng "to avoid CUDA/cuDNN DLL conflicts with PyTorch" ( `adapter_autosub_cli.py:121-168` ). `subtitle_extractor.py` còn giả lập (mock) module `torch` ở đầu file (dòng 8-71, chỉ khi chạy như script `__main__` — đúng trường hợp tiến trình con này) để thư viện Paddle/modelscope không nạp DLL CUDA của PyTorch — xung đột DLL là vấn đề thực tế trên Windows. Gọi `videocr.save_subtitles_to_file` (PaddleOCR) với `conf_threshold=75` , `sim_threshold=80` , vùng cắt (crop) do người dùng chọn trên ảnh preview; GPU lỗi thì tự chuyển CPU ( `subtitle_extractor.py:123-202` ). Ảnh preview lấy bằng `grab_preview_frame` : frame ở giữa video ( `dur / 2.0` ) bằng `ffmpeg -ss... -frames:v 1 -q:v 3` (dòng 83-121); endpoint `POST /api/autosub/prepare` gọi nó với timeout 900 s ( `orchestrator/main.py:615-650` ).

So sánh để trả lời hội đồng: Whisper nghe tiếng, OCR đọc chữ trên hình. OCR chính xác về nội dung khi video có hardsub, nhưng timing phụ thuộc lúc chữ xuất hiện/biến mất trên hình (so khung liên tiếp theo `sim_threshold` ).

4.6 Burn phụ đề: `burn_subtitles_ffmpeg` ( `MC/app/services/video.py:1424-1650` )

Ba vấn đề kỹ thuật được xử lý:

1. Escape đường dẫn Windows trong filtergraph. Trong cú pháp filter FFmpeg, dấu `:` phân tách tham số, nên `C:\...` phá vỡ lệnh. Giải pháp: chạy FFmpeg với `cwd=work_dir` và truyền đường dẫn tương đối; nếu khác ổ đĩa ( `os.path.relpath` ném `ValueError` ) thì copy tạm file vào `work_dir` . 2. Font tuỳ chỉnh: thêm `:fontsdir='<thưmục font>'` để libass tìm được font kèm theo (Be Vietnam Pro, Montserrat, Charm...), có bảng ánh xạ tên file → tên họ font ( `"BeVietnamPro-Bold": "Be Vietnam Pro"` ...). 3. Style: ghép `force_style` :

```
# MC/app/services/video.py:1541-1561 (rút gọn)
if bg_style == "Box":
    force_style_parts.append("BorderStyle=3")
    ...
                                                      # alpha UI (đục) -> ASS (trong suốt)
    transparency = 255 - max(0, min(255, bg_alpha))
    ass_box_color = ass_box_color.replace("&H00", f"&H{alpha_hex}")
else:
    force_style_parts.append("BorderStyle=1")
    force_style_parts.append("BackColour=&HFF000000")
align = 2
if position == "top":
    align = 8
elif position in ("center", "middle"):
    align = 5
force_style_parts.append(f"Alignment={align}")
```

Vị trí `custom` : `MarginV = int((100 - custom_y_ratio) * video_height / 100)` (dòng 1574). Encode: `libx264 -crf 18 -preset veryfast` hoặc `h264_nvenc -cq 19 -preset slow` (dòng 1584-1588). NVENC lỗi → chạy lại bằng `libx264` . Có audio lồng tiếng: `-map 0:v:0 -map 1:a:0 -c:a aac` ; không có: `-c:a copy` (giữ nguyên audio gốc, không encode lại).

Mặc định kiểu chữ Autosub trong cấu hình chung: `font_size 45` , chữ `#ffffff` , viền `#000000` dày `1.5` , `bg_alpha 140` , `custom_position 70.0` ( `orchestrator/config.py:107-130` ).

### 4.7 Đồng bộ thời gian trong video hoạt hình (Bước 3)

Đây là phần "đồng bộ" quan trọng nhất cho sản phẩm chính: mỗi ảnh cảnh phải hiện đúng lúc giọng đọc kể tới cảnh đó.

(a) Nền móng: thời lượng audio chính xác — `get_audio_duration` ( `MC/app/services/storytelling/audio_utils.py:17-78` ). Docstring kể lại một lỗi thật: trước đây `pydub` không thấy ffmpeg → đọc duration hỏng → fallback 60 s âm thầm → audio 10 phút bị cắt còn video 60 s. Bản sửa: thử lần lượt

1. `wave` (thư viện chuẩn) cho `.wav` : `duration = frames / rate` — không cần ffmpeg; 2. ffmpeg của `imageio-ffmpeg` , parse `Duration: HH:MM:SS.xx` từ stderr (timeout 120 s); 3. `pydub` với converter trỏ về ffmpeg đó; 4. tất cả hỏng → `raise RuntimeError` rõ ràng, không đoán.

(b) Chọn nguồn timing ( `MC/app/services/storytelling/orchestrator.py:266-297` ):

- (c) Chia thời lượng theo tỷ lệ số từ — nhánh chạy thực tế khi không có SRT:
- `# MC/app/services/storytelling/srt_mapper.py:197-216` `effective_dur=total_duriftotal_dur>0elselen(scenes)*5.0` `word_counts=[max(len((scene.text_vior"").split()),1)forsceneinscenes]` `total_words=sum(word_counts)` `current=0.0` `forindex,(scene,word_count)inenumerate(zip(scenes,word_counts)):` · `duration=effective_dur*word_count/total_words` `end=effective_durifindex==len(scenes)-1elsecurrent+duration` `scene.start_time=current` `scene.end_time=end` `scene.duration_sec=end-current` `current=end`

Công thức:

- với là tổng thời lượng audio thật,

- số từ cảnh . Giả định: tốc độ đọc TTS gần như hằng số

- → không hụt/thừa cuối video.

(từ/giây). Cảnh cuối được ép kết thúc đúng

(d) So khớp văn bản khi có SRT — `map_semantic_scenes_to_srt` ( `srt_mapper.py:356-455` ):

- 1. Chuẩn hoá cả hai phía: `NFKD` + bỏ ký tự tổ hợp (bỏ dấu tiếng Việt), lowercase, bỏ dấu câu. 2. Nối toàn bộ SRT thành chuỗi từ, nhớ mỗi từ thuộc block nào ( `word_to_block` ). 3. Với mỗi cảnh (tiến tuyến tính bằng `cursor` , không quay lui): lấy cửa sổ `SEARCH_WINDOW = 2000` từ phía trước, `difflib.SequenceMatcher(None, scene_str, search_str)` . 4. `ratio>=0.5` → lấy block chứa từ khớp đầu/cuối làm start/end; ngược lại → gán theo tỷ lệ từ nối tiếp cảnh trước. 5. `_fix_monotonic` (dòng 335-349): start cảnh sau ≥ end cảnh trước; end ≤ start thì +1 s; cảnh cuối = tổng thời lượng.

Điểm yếu thật cần biết (tự phát hiện khi đọc code): `SequenceMatcher.ratio()` =

- với số ký tự khớp, và

luôn

- . Cửa sổ `search_str` dài `len(scene_words) + 2000` từ ( `srt_mapper.py:415` ), còn `scene_str` chỉ vài chục–vài

- . Muốn ratio ≥ 0,5 thì cần

trăm từ, nên

- — chỉ xảy ra khi phần SRT còn lại rất

ngắn (các cảnh gần cuối). Ví dụ cảnh 100 từ ≈ 500 ký tự, cửa sổ ≈ 2100 từ ≈ 10 000 ký tự → ratio ≤ 1000/10500 ≈ 0,1. Thêm nữa, với chuỗi `b` ≥ 200 phần tử, `SequenceMatcher` mặc định bật autojunk (coi các ký tự xuất hiện > 1% là "rác", như dấu cách và nguyên âm phổ biến) nên

- thực tế còn nhỏ hơn. Hệ quả: khi người dùng cung cấp SRT dài, phần lớn cảnh vẫn rơi

về nhánh tỷ lệ từ. Cách sửa: so với cửa sổ cỡ bằng độ dài cảnh (hoặc dùng `find_longest_match` /tỷ lệ theo

- ). Ngoài ra

hàm `map_semantic_scenes_to_srt` được định nghĩa hai lần trong file (dòng 219 và 356) — Python dùng bản sau, bản đầu là code chết.

(e) Nhánh cũ `map_scenes_to_timeline` (dùng khi tách cảnh semantic thất bại, `srt_mapper.py:53-177` ): gom các block SRT thành nhóm khi khoảng lặng giữa hai block > `silence_gap_threshold = 0.5` s, rồi map nhóm ↔ cảnh tuyến tính; thừa cảnh → mỗi cảnh thừa 5 s; thừa nhóm → cảnh cuối gộp hết. Không có SRT và `use_whisper=False` → chia theo số từ với lề `MARGIN_SECONDS =` `0.1` và mỗi đoạn tối thiểu 0,3 s.

(f) Sinh SRT từ kịch bản — `generate_srt_from_scenes` ( `srt_mapper.py:487-540` ): phụ đề chia theo câu (không theo cảnh — cảnh 15 s làm 1 dòng thì quá dài để đọc):

Tách câu bằng regex `(?<=[\.\!\?\…;])\s+` . Câu > 22 từ → cắt tiếp theo dấu phẩy, gom các vế lại sao cho mỗi khối ≤ 22 từ (nếu bản thân một vế giữa hai dấu phẩy đã > 22 từ thì khối đó vẫn dài hơn 22 — code không cắt tiếp). Trong mỗi cảnh, mỗi khối nhận thời lượng tỷ lệ số từ bên trong cảnh: `seg = scene_dur * w / total_w` (với `scene_dur =` `max(duration_sec, 0.2)` ), kẹp không vượt `scene.end_time` ; nếu bị kẹp thành độ dài ≤ 0 thì gán 0,2 s ( `srt_mapper.py:523-` `533` ). Thời gian ghi ra qua `_format_srt_time` (làm tròn mili-giây).

Vì chữ lấy nguyên văn kịch bản mà TTS đã đọc, phụ đề đúng chính tả 100%; timing là xấp xỉ nhưng được neo theo từng cảnh, nên sai số không cộng dồn qua cả chương.

(g) Burn trong video hoạt hình — `assemble_video` ( `video_assembler.py:117-213` ):

1. `ffmpeg -f concat` từ `duration.txt` (mỗi ảnh một `duration` = `scene.duration_sec` ) → `raw_video.mp4` , scale/pad về 1920×1080, `video_fps` 24. 2. Mix audio (+ BGM `amix` , BGM `volume=bgm_volume` , mặc định 0,15) và nếu `burn_subtitles` thì `-vf` `subtitles='temp_sub.srt':fontsdir=...:force_style='...'` . 3. Style từ `[storytelling]` : `subtitle_font="Arial"` , `subtitle_font_size=28` , `subtitle_color="white"` , `subtitle_border=2` , `subtitle_position="bottom"` ( `MC/config.toml:28-32` ; hàm `_build_subtitle_style` dòng 59-68). Font không có trong `C:\Windows\Fonts` → rơi về Arial. 4. `-t total_dur` với `total_dur = sum(duration_sec)` → video không dài hơn tổng cảnh.

Mặc định burn là TẮT: `"burn_subtitles": False` ( `orchestrator/config.py:86` ), `Step3Schema.burn_subtitles = False` ( `orchestrator/main.py:155` ); người dùng bật bằng ô `s3Subtitles` trên WebUI ( `webui/app.js:298` ). Nhớ tích khi quay demo.

### 4.8 Quản lý tài nguyên và thứ tự nạp DLL

`adapter_autosub_cli.py:9` đặt `KMP_DUPLICATE_LIB_OK=TRUE` để tránh lỗi `OMP: Error #15` khi torch và cv2 cùng nạp OpenMP trên Windows. `storytelling/orchestrator.py:3-9` ép thứ tự import `torch→faster_whisper→cv2` để tránh crash DLL CUDA/OpenMP. Model Whisper là singleton, nạp lười (lazy), giải phóng ngay khi xong; adapter import nặng ( `composer` ) chỉ sau khi qua bước `--prepare-only` (dòng 78-98).

## 5. Sơ đồ tổng hợp dòng dữ liệu thời gian

Điểm mấu chốt: bản dịch giữ nguyên mốc thời gian của câu nguồn (dịch theo chỉ số `i` , `translation.py:95-161` ) — nên phụ đề tiếng Việt và giọng lồng tiếng vẫn khớp hình dù ngôn ngữ đã đổi.

## 6. Hạn chế & hướng phát triển

# Hạn chế (có bằng chứng)

- Hướng phát triển

1 Video hoạt hình dùng timing tỷ lệ số từ (giả định tốc độ đọc đều); câu

- Lấy mốc `WordBoundary` từ Edge-TTS hoặc ghép audio theo từng

có nhiều dấu ngắt/đoạn nghỉ dài sẽ lệch vài trăm ms–1 s trong cảnh

- câu để biết chính xác; hoặc forced alignment (WhisperX, MFA)

- So khớp với cửa sổ ≈ độ dài cảnh, hoặc DTW ở mức từ

2 `map_semantic_scenes_to_srt` gần như luôn ratio < 0,5 do cửa sổ so khớp quá dài; hàm bị định nghĩa trùng

3 `hardware_adapter` tính `whisper_device` nhưng `create_subtitle`

- Đọc chung một nguồn cấu hình thiết bị

không dùng

4 Whisper có thể ảo giác trên nhạc nền/im lặng; VAD giảm nhưng không

- Bật `clean_audio` (Demucs) cho video nhiều nhạc; đặt

triệt tiêu

- `hallucination_silence_threshold` ; dùng large-v3 / turbo khi có GPU

Câu phụ đề chỉ cắt theo dấu câu; câu dài không có dấu → một dòng 5

- Thêm giới hạn ký tự/giây (CPS) và số ký tự/dòng như chuẩn phụ

rất dài

- đề (~42 ký tự/dòng)

6 Không có đánh giá WER/độ lệch timing định lượng trong repo

- Tạo bộ test nhỏ có SRT chuẩn, đo WER và sai số start/end trung bình

7 Không có hiệu ứng karaoke / highlight từ đang đọc dù đã có mốc từng

- Xuất ASS với thẻ `\k` từ `word.start/end`

từ

8 Dịch LLM theo lô 40 câu có thể trả JSON sai → câu đó giữ nguyên bản

- Kiểm tra số lượng câu, gửi lại phần thiếu

gốc

9 Burn cứng phải encode lại video

- Xuất thêm file `.srt` rời (softsub) cho nền tảng hỗ trợ

10 Cảnh báo "bản dịch trùng bản gốc" chỉ chạy ở nhánh OCR; nhánh

- So với `source_subtitles.srt` trong `task_dir` cho cả hai nhánh

Whisper dịch hỏng (thiếu API key) thì không cảnh báo ( `adapter_autosub_cli.py:217` )

11 Cấu hình Whisper không đồng nhất giữa file mẫu ( `cuda/float32` ) và

- Đồng bộ file mẫu hoặc để `hardware_adapter` quyết định thiết bị

máy dev ( `cpu/int8` )

## Câu hỏi hội đồng có thể hỏi

### 1. Whisper nhận đầu vào là gì và biến đổi thế nào?

Audio 16 kHz mono (dự án tự convert bằng ffmpeg `-ac 1 -ar 16000` `pcm_s16le` , `composer.py:330-341` ). Whisper cắt thành cửa sổ 25 ms bước 10 ms, FFT, qua 80 bộ lọc Mel, lấy log → ma trận 80×3000 cho mỗi 30 s. Encoder Transformer đọc ma trận này, decoder sinh token chữ và token thời gian.

### 2. Vì sao dùng thang Mel và log?

Tai người cảm nhận tần số và độ to gần theo thang logarit; Mel nén vùng tần số cao, giữ chi tiết vùng thấp — nơi chứa thông tin âm vị; log thu hẹp dải giá trị, giúp mạng học ổn định.

### 3. Whisper khác các ASR truyền thống ở đâu?

Là một mạng encoder–decoder end-to-end, không cần từ điển phát âm hay LM riêng; train trên 680 000 giờ dữ liệu weakly supervised đa ngôn ngữ, đa nhiệm bằng token đặc biệt; zero-shot tốt, bền với tạp âm. Đổi lại có thể ảo giác và chậm hơn CTC.

### 4. Timestamp từng từ lấy từ đâu?

Token thời gian chỉ cho mốc segment (bước 20 ms). Mốc từng từ lấy từ trọng số cross- attention của các alignment head, căn bằng DTW. Code bật `word_timestamps=True` ( `subtitle.py:40` ) và dùng `word.start/word.end` để tự cắt câu theo dấu câu.

### 5. VAD là gì, em đặt tham số gì?

Silero VAD lọc đoạn không có tiếng nói trước khi đưa vào Whisper, giảm ảo giác và tiết kiệm thời gian. Code bật `vad_filter=True` và `min_silence_duration_ms=500` (mặc định thư viện là 2000) để cắt đoạn ở khoảng lặng 0,5 s — hợp với phụ đề câu ngắn.

### 6. faster-whisper khác openai-whisper thế nào? int8 là gì?

Cùng trọng số, nhưng chạy trên CTranslate2 (C++), hợp nhất phép toán, hỗ trợ lượng tử hoá. int8 lưu mỗi trọng số bằng 1 byte cộng hệ số scale:

- — model medium còn

~0,8 GB, nhanh trên CPU, sai số không đáng kể. Máy dev cấu hình `medium / cpu / int8` ( `config.toml:14-17` ).

### 7. Tại sao chạy Whisper trên CPU trong khi có GPU?

Để không tranh VRAM với Stable Diffusion, RealESRGAN, XTTS trên card 6–8 GB. Comment trong code ghi Whisper medium trên cuda tốn ~2–3 GB VRAM. Sau khi phiên âm còn gọi `release_whisper_model()` để giải phóng ngay. Thiết bị do `[whisper]` trong `config.toml` quyết định (máy dev: `cpu/int8` ); nếu hỏi thêm thì nói rõ file mẫu `config.toml.example` đang để `cuda/float32` , nên máy cài mới cần chỉnh lại cho khớp.

### 8. Trong video hoạt hình, phụ đề khớp tiếng bằng cách nào? Có dùng Whisper không?

Hiện không — `adapter_video_cli.py:222` ép `use_whisper=False` . Vì TTS đọc nguyên văn kịch bản nên chữ đã biết; thời lượng mỗi cảnh = tổng thời lượng thật × tỷ lệ số từ; phụ đề sinh từ kịch bản, chia câu ≤ 22 từ, timing tỷ lệ trong cảnh. Chữ đúng 100%, tiết kiệm ~60 s/chương và VRAM; đánh đổi là timing xấp xỉ. Đường dùng Whisper vẫn có sẵn ( `use_whisper=True` ).

### 9. Nếu timing theo số từ bị lệch thì sai số có cộng dồn không?

Không cộng dồn ra toàn chương vì tổng thời lượng lấy chính xác từ file WAV ( `get_audio_duration` ) và cảnh cuối bị ép kết thúc đúng tổng đó; phụ đề thì được neo trong từng cảnh. Sai số chỉ nằm trong nội bộ cảnh.

### 10. SRT và ASS khác gì, dự án dùng cái nào?

SRT chỉ có chỉ số, thời gian `HH:MM:SS,mmm` , chữ. ASS có style (font, màu `&HAABBGGRR` , viền, hộp nền, căn lề, hiệu ứng). Dự án lưu SRT, khi burn dùng filter `subtitles` của FFmpeg (libass) với `force_style` để áp style kiểu ASS ( `video.py:1424-1581` , `video_assembler.py:59-68` ).

### 11. Vì sao burn cứng thay vì nhúng phụ đề mềm?

Video đăng TikTok/YouTube Shorts/Facebook — nhiều nền tảng không đọc track phụ đề trong mp4. Hardsub hiện ở mọi nơi. Đổi lại phải encode lại (dùng `libx264 -crf 18` hoặc `h264_nvenc -cq` `19` ).

### 12. Nếu video không có tiếng hoặc có chữ in sẵn thì sao?

Chọn `sub_source="ocr"` : chạy PaddleOCR (videocr) trong tiến trình con riêng, có mock `torch` để tránh xung đột DLL; ngưỡng `conf_threshold=75` , `sim_threshold=80` . Video không audio mà chọn Whisper → báo lỗi rõ ràng khuyên dùng OCR ( `composer.py:347-359` ).

### 13. Nhạc nền to làm Whisper nghe sai thì xử lý thế nào?

Bật `clean_audio` : Demucs `htdemucs--two-stems vocals` tách giọng khỏi nhạc trước khi đưa Whisper; nếu Demucs lỗi thì dùng lại audio gốc để pipeline không dừng ( `audio_cleaner.py` ).

### 14. Sau khi dịch sang tiếng Việt, timing lấy từ đâu?

Giữ nguyên mốc của SRT nguồn: LLM chỉ dịch trường text theo chỉ số `i` (lô 40 câu, `translation.py` ). Lồng tiếng đặt từng câu TTS vào đúng `start_time` , nếu dài quá khung +0,3 s thì tăng tốc bằng `atempo` tối đa 1,4×; nhạc gốc bị giảm xuống 10% (ducking 90%) trong khung ±0,1 s quanh mỗi câu.

### 15. Hạn chế lớn nhất của phần này là gì?

Timing video hoạt hình là xấp xỉ theo số từ; hàm so khớp SRT–cảnh có ngưỡng ratio gần như không đạt với cửa sổ 2000 từ; chưa đo WER/độ lệch định lượng. Hướng sửa: lấy mốc WordBoundary từ TTS hoặc forced alignment, và bộ đánh giá có SRT chuẩn.

## Tóm tắt 1 phút

"Phần này giải quyết câu hỏi: chữ nào hiện lúc nào. Công cụ chính là Whisper — một mạng Transformer encoder–decoder của OpenAI, train trên 680 nghìn giờ âm thanh có phụ đề từ Internet. Âm thanh được đưa về 16 kHz mono, biến thành log-Mel spectrogram — một bức ảnh thời gian–tần số theo cảm nhận của tai — encoder đọc bức ảnh đó, decoder viết ra chữ kèm token thời gian; bật word timestamps thì có mốc cho từng từ qua cross-attention và DTW.

Em dùng faster-whisper chạy trên CTranslate2, cấu hình model medium, CPU, int8 để nhường VRAM cho Stable Diffusion; bật VAD với khoảng lặng 500 ms, beam size 5; rồi tự cắt câu theo dấu câu dựa trên mốc từng từ và ghi ra SRT. Ở tab Autosub, SRT này là xương sống: dịch sang tiếng Việt giữ nguyên mốc, lồng tiếng đặt đúng thời điểm, ducking nhạc nền, rồi burn phụ đề bằng FFmpeg với style ASS.

Còn trong video hoạt hình, vì giọng đọc TTS đọc nguyên văn kịch bản, em không cần Whisper nữa: đọc chính xác thời lượng audio, chia thời gian cho các cảnh theo số từ, và sinh phụ đề thẳng từ kịch bản — chữ đúng 100%, nhanh hơn khoảng một phút mỗi chương. Hạn chế là timing xấp xỉ; hướng phát triển là lấy mốc từ chính engine TTS hoặc dùng forced alignment."
