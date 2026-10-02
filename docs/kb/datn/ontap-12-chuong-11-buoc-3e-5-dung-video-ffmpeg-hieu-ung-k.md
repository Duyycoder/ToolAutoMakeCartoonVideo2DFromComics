# Chương 11. Bước 3e & 5 — Dựng video: ffmpeg, hiệu ứng Ken Burns, ghép audio, hợp nhất

Mục tiêu chương. Sau chương này bạn phải trả lời được: (1) một file `.mp4` thực chất là gì, (2) ffmpeg biến một danh sách ảnh PNG + một file `.wav` thành video như thế nào, (3) chính xác thì code của đồ án gọi ffmpeg với lệnh gì, tham số nào, vì sao, (4) cơ chế resume của batch và bước hợp nhất ( `TongHop_*.mp4` ) hoạt động ra sao, (5) những gì không có trong code (Ken Burns, crossfade, loudnorm ở bước video) để không bị hội đồng "bắt bài".

Lưu ý trung thực — đọc trước. Tên chương có "Ken Burns", nhưng sau khi grep toàn bộ mã nguồn ( `zoompan` , `xfade` , `ken` `burns` ), pipeline chính (Bước 3 → 5) KHÔNG áp dụng hiệu ứng Ken Burns hay chuyển cảnh. Mỗi cảnh là một ảnh tĩnh được giữ trên màn hình đúng số giây của cảnh đó. Chương này vẫn dạy Ken Burns đầy đủ (nguyên lý + toán + cách làm bằng ffmpeg) vì (a) hội đồng rất hay hỏi "sao video không chuyển động?", (b) trong repo có đoạn code zoom tuyến tính kiểu MoviePy ở module kế thừa ( `app/services/video.py:1279` ) nhưng không được gọi, và (c) đây là hướng phát triển chi phí thấp nhất. File `docs/trinh-bay-datn.md:570` cũng đã ghi nhận điều này.

## 1. Vai trò trong hệ thống

### 1.1. Vị trí trong pipeline

Hệ thống có 5 bước ở tầng orchestrator (xem `orchestrator/pipeline.py` ): Bước 1 cào/dịch, Bước 2 TTS, Bước 3 sinh video, Bước 4 autosub (luồng phụ cho video có sẵn), Bước 5 hợp nhất. Chương này phụ trách:

- **Phần:** Bước 3e — Dựng video từng chương · **Nằm ở đâu:** `AIVoice/apps/MediaComposer/app/services/storytelling/video_assembler.py` → `assemble_video()` · **Làm gì:** Ảnh cảnh (PNG đã upscale) + audio `.wav` (+ SRT, + BGM) → `final_video.mp4`
- **Phần:** Điều phối batch + resume · **Nằm ở đâu:** `.../storytelling/batch_video_runner.py` → `run_batch()` · **Làm gì:** Chạy N chương, 2-pass tiết kiệm VRAM, lưu `batch_state.json` để chạy tiếp khi bị ngắt
- **Phần:** Bước 5 — Hợp nhất · **Nằm ở đâu:** `orchestrator/video_merger.py` → `merge_videos()` · **Làm gì:** Các `<chương>.mp4` → `TongHop_YYYYMMDD_HHMMSS.mp4` bằng concat stream-copy
- **Phần:** (Kế thừa, luồng phụ) · **Nằm ở đâu:** `app/services/video.py` , `composer.py` , `services/utils/video_effects.py` · **Làm gì:** Module gốc kiểu "MoneyPrinterTurbo" (comment tiếng Trung): ghép stock footage, burn phụ đề cho luồng dịch video. Không nằm trên đường Bước 3 → 5 của truyện.

Ghi chú đánh số. `README.md` mô tả "pipeline 4 bước" và gọi hợp nhất là "4. Hợp nhất"; nhưng trong API/UI thì hợp nhất là step5 ( `orchestrator/main.py:685@app.post("/api/pipeline/step5")` , `pipeline.py:750start_step_5_merge` ), còn step4 là autosub. File KB `docs/kb/05-buoc5-ghep.md` còn ghi "phụ đề `.ass` " — không khớp code: code dùng file `.srt` , style ASS chỉ được áp qua `force_style` . Tương tự, `docs/trinh-bay-datn.md:565-566` liệt kê "audio ducking" và "hiệu ứng karaoke" cho bước ghép — `assemble_video` không có hai tính năng này (chỉ `volume` + `amix` , phụ đề SRT thường). Khi trình bày, hãy dùng số liệu của code.

### 1.2. Input / Output cụ thể

Đầu vào của `assemble_video()` ( `video_assembler.py:117-125` ):

- **Tham số:** `frames:` `List[FrameInfo]` · **Nguồn:** `orchestrator.py:603` — mỗi scene → `FrameInfo(frame_path,` `duration_sec)` · **Ví dụ:** `final_frames/scene_000.png` , `6.42` giây
- **Tham số:** `audio_path` · **Nguồn:** file `.wav` của chương (từ Bước 2 TTS) · **Ví dụ:** `.../translated/Chuong 1 - [VI]` `....wav`
- **Tham số:** `srt_path` · **Nguồn:** SRT có sẵn hoặc SRT sinh từ kịch bản ( `generated_from_script.srt` , `orchestrator.py:294` )
- **Tham số:** `bgm_path` , `bgm_volume` · **Nguồn:** CLI `--bgm-path` , `--bgm-volume` (mặc định `0.15` )
- **Tham số:** `burn_subtitles` · **Nguồn:** CLI; mặc định orchestrator `False` ( `orchestrator/config.py:86` )

Đầu ra: `<task_dir>/final_video.mp4` → được copy thành `storage/truyen/<slug>/video/<stem>.mp4` ( `batch_video_runner.py:512-514` ) → Bước 5 gộp thành `storage/truyen/<slug>/video/TongHop_<timestamp>.mp4` .

### 1.3. Thời lượng cảnh đến từ đâu?

Dựng video chỉ "tiêu thụ" `duration_sec` ; con số này được tính ở Bước 3a (chương về tách cảnh/SRT). Điểm mấu chốt cần nhớ để trả lời câu hỏi đồng bộ hình-tiếng:

Tổng thời lượng audio được đọc chính xác bởi `get_audio_duration` ( `audio_utils.py:17` ): với `.wav` dùng module `wave` ( `frames / rate` , `:28-37` ), nếu không được thì thử ffmpeg của imageio-ffmpeg rồi pydub; thất bại hết thì raise `RuntimeError` — không còn fallback âm thầm 60 s như bản cũ (comment `orchestrator.py:238-240` ). Không có SRT (trường hợp mặc định của luồng truyện, vì Bước 2 chỉ xuất `.wav` ): `map_semantic_scenes_to_srt` rơi vào `_fallback_proportional_duration` ( `srt_mapper.py:372-375` ) — chia liền mạch tổng thời lượng theo tỉ lệ số từ → `sum(duration_sec) =độdài audio` . Có SRT: mỗi cảnh lấy `start` của block SRT đầu và `end` của block cuối ( `srt_mapper.py:436-438` ), sau đó `_fix_monotonic()` ( `srt_mapper.py:335-349` ) ép các cảnh tăng dần, không chồng lấn, và cảnh cuối kết thúc đúng bằng `total_duration` . Lưu ý tinh tế (đọc từ code, chưa đo thực tế): `_fix_monotonic` chỉ sửa chồng lấn, không lấp khoảng trống giữa hai cảnh (khoảng lặng giữa hai block SRT) hay khoảng trống trước cảnh đầu. Concat demuxer chỉ biết `duration` , không biết `start_time` , nên nếu SRT có khoảng trống thì `sum(duration_sec)` < độ dài audio: ảnh sẽ chuyển sớm hơn lời đọc một chút, lệch tích luỹ dần, và `-t total_dur` ở lượt 2 có thể cắt mất đuôi audio. Với nhánh không SRT thì không có vấn đề này.

## 2. Nền tảng lý thuyết từ gốc

### 2.1. Video số là gì? Frame, fps, độ phân giải

Trực giác. Video là một cuốn "sách lật" (flipbook): nhiều bức ảnh tĩnh (frame) hiện liên tiếp đủ nhanh thì não người cảm nhận thành chuyển động liên tục (hiện tượng beta movement / phi phenomenon; cách giải thích cũ "lưu ảnh võng mạc" nay được coi là chưa đủ).

Frame: một ảnh raster = ma trận pixel. Ảnh 1920×1080 có 2.073.600 pixel. fps (frames per second): số frame mỗi giây. 24 fps là chuẩn điện ảnh, 25 là PAL, 30 là NTSC/web. Đồ án dùng `video_fps` `= 24` ( `config.toml.example:28` , đọc tại `video_assembler.py:146` ). Độ phân giải đầu ra: `output_width = 1920` , `output_height = 1080` ( `config.toml.example:26-27` ; mặc định trong code `video_assembler.py:132-133` ). Aspect ratio: 16:9 ( `aspect_ratio = "16:9"` ).

Vì sao phải nén? Tính kích thước video thô (không nén) ở định dạng yuv420p (giải thích ở 2.2):

Một chương 10 phút sẽ là ~44 GB. Sau khi nén H.264 thường chỉ còn vài chục MB → tỉ lệ nén hàng trăm đến hàng nghìn lần. Đó là việc của codec.

2.2. Không gian màu YUV và `yuv420p`

Trực giác. Mắt người nhạy với độ sáng hơn nhiều so với màu sắc. Vậy ta tách ảnh thành 1 kênh sáng + 2 kênh màu, rồi giữ độ sáng ở độ phân giải đầy đủ, còn màu thì lưu "thô" hơn.

- Y (luma, độ sáng) ≈ `0.299R + 0.587G + 0.114B` (BT.601; BT.709 dùng hệ số hơi khác). U (Cb), V (Cr): độ lệch màu xanh dương / đỏ so với Y. Chroma subsampling 4:2:0: mỗi khối 2×2 pixel dùng chung 1 mẫu U và 1 mẫu V. Số mẫu = `W·H` (Y) + `W·H/4` (U) + `W·H/4` (V) = `1,5·W·H` → đây là nguồn của hệ số 1,5 ở trên. `p` trong `yuv420p` = planar: 3 mặt phẳng Y, U, V lưu tách nhau.

Vì sao code luôn ép `-pix_fmt yuv420p` ( `video_assembler.py:153` , `:194` )? Ảnh PNG đầu vào là RGB; nếu không ép, libx264 có thể chọn `yuv444p` (giữ màu đầy đủ) → nhiều trình phát (Windows Media Player cũ, trình duyệt, điện thoại, TV) không phát được vì chỉ hỗ trợ H.264 High profile 4:2:0. Ép `yuv420p` = đổi một chút chất lượng màu lấy tính tương thích tối đa. Hệ quả phụ: 4:2:0 yêu cầu chiều rộng/cao chẵn — đó là lý do `generate_draft_video` có đoạn `if draft_w%2!= 0: draft_w -= 1` ( `video_assembler.py:222-223` ).

### 2.3. Container vs Codec — phân biệt bắt buộc phải nắm

- **Khái niệm:** Codec (coder- decoder) · **Ví dụ:** H.264 (libx264, h264_nvenc), AAC, PCM · **Vai trò:** Thuật toán nén/giải nén một luồng (stream) · **Ẩn dụ:** Cách "gấp quần áo" cho gọn
- **Khái niệm:** Container (format) · **Ví dụ:** MP4, MKV, WAV, MOV · **Vai trò:** "Hộp" chứa nhiều stream + metadata + timestamp + index · **Ẩn dụ:** Cái vali

- File `.mp4` của đồ án = container MP4 (ISO BMFF) chứa 1 stream video H.264 + 1 stream audio AAC. File `.wav` từ TTS = container RIFF/WAV chứa stream PCM (không nén). Container giữ timestamp (PTS — presentation timestamp) cho từng gói dữ liệu; nhờ đó video và audio được đồng bộ khi phát. Hệ quả thực tế: có thể đổi container mà không đổi codec (remux, `-c copy` ), rất nhanh vì không giải nén. Bước 5 khai thác đúng điều này.

### 2.4. H.264 hoạt động thế nào (mức đủ để bảo vệ)

H.264/AVC (chuẩn ITU-T H.264, 2003) nén dựa trên 2 loại dư thừa:

(a) Dư thừa không gian (trong 1 frame) — intra prediction + biến đổi.

- 1. Chia frame thành macroblock 16×16 (luma). 2. Intra prediction: đoán khối hiện tại từ các pixel biên của khối lân cận đã mã hoá (ví dụ "kéo dài theo chiều dọc"). Chỉ lưu phần dư (residual) = thực tế − dự đoán. 3. Biến đổi DCT nguyên (4×4 hoặc 8×8): chuyển residual sang miền tần số. Ảnh tự nhiên có năng lượng dồn về tần số thấp → nhiều hệ số cao tần gần 0. 4. Lượng tử hoá (quantization): chia hệ số cho bước lượng tử `Qstep` rồi làm tròn:

- . Đây là bước mất

- thông tin duy nhất và là "núm vặn chất lượng". `Qstep` phụ thuộc QP (0–51); QP tăng 6 thì `Qstep` gấp đôi. 5. Entropy coding (CAVLC hoặc CABAC): mã hoá không mất các hệ số đã lượng tử, ký hiệu hay gặp dùng ít bit.

(b) Dư thừa thời gian (giữa các frame) — inter prediction / motion compensation.

- Với mỗi khối, bộ mã hoá tìm khối giống nhất trong frame tham chiếu → lưu motion vector + residual. Loại frame: I-frame (intra): tự đứng một mình, như ảnh JPEG. Keyframe (IDR) là I-frame mà decoder có thể bắt đầu giải mã từ đó → cần cho tua (seek) và cho cắt/ghép stream-copy.

- P-frame: dự đoán từ frame trước. B-frame: dự đoán hai chiều (trước và sau). GOP (Group of Pictures): chuỗi từ một keyframe đến keyframe tiếp theo. libx264 mặc định `keyint=250` (tối đa 250 frame giữa hai keyframe, ≈10,4 s ở 24 fps); code đồ án không đặt `-g` , nên dùng mặc định. Bình thường x264 còn tự chèn keyframe khi phát hiện "đổi cảnh" ( `scenecut` ), nhưng preset `ultrafast` mà code dùng đặt `scenecut=0` → frame đầu của cảnh mới thường là P-frame gồm toàn macroblock intra. Liên hệ Bước 5: frame đầu tiên của mọi file do encoder tạo ra luôn là IDR, nên khi nối các file chương bằng stream copy, mỗi ranh giới file đều bắt đầu bằng keyframe → decoder giải mã được ngay.

Liên hệ với đồ án — vì sao video "slideshow" nén cực tốt: một cảnh giữ nguyên ảnh 6 giây ở 24 fps = 144 frame giống hệt nhau. Sau frame đầu, các P-frame gần như chỉ ghi "không đổi" (skip macroblock) → tốn rất ít bit.

### 2.5. Rate control: CRF, CQ, VBR

"Rate control" quyết định mỗi frame được bao nhiêu bit.

- **Chế độ:** CRF (Constant Rate Factor, libx264) · **Ý nghĩa:** Giữ chất lượng cảm nhận ổn định; bitrate tự dao động. Thang 0– 51, mặc định 23; giảm 6 ≈ gấp đôi bitrate. 18 ≈ "gần như không phân biệt bằng mắt". · **Dùng trong code:** `assemble_video` với libx264 không đặt `-crf` → mặc định 23. Fallback của merger: `-crf 20` ( `video_merger.py:68` ). `burn_subtitles_ffmpeg` : `-crf` `18` ( `video.py:1586` ).
- **Chế độ:** CQ + VBR (NVENC) · **Ý nghĩa:** `-rc vbr -cq 23` : VBR nhắm mức chất lượng hằng ~23, tương tự tinh thần CRF (thang CQ của NVENC không tương đương 1:1 với CRF của x264). Nhiều hướng dẫn khuyên thêm `-b:v 0` để trần bitrate mặc định không giới hạn CQ — code không đặt (ảnh hưởng thực tế chưa xác minh). · **Dùng trong code:** `_get_video_codec_args()` ( `video_assembler.py:79` )
- **Chế độ:** Preset · **Ý nghĩa:** Đánh đổi tốc độ ↔ hiệu suất nén (cùng chất lượng, preset chậm → file nhỏ hơn). libx264: `ultrafast … veryslow` ; NVENC: `p1` (nhanh nhất) … `p7` (chất lượng nhất). · **Dùng trong code:** `ultrafast` (libx264), `p4` (NVENC, mức giữa)

Cần phân biệt: `preset` không thay đổi chất lượng mục tiêu (do CRF/CQ quyết định), mà thay đổi dung lượng file và thời gian mã hoá. `ultrafast` tắt CABAC, B-frame, nhiều chế độ tìm chuyển động → file to hơn đáng kể nhưng nhanh nhất.

2.6. `-tune stillimage`

Tune là bộ tinh chỉnh tâm lý thị giác của x264 cho loại nội dung. `stillimage` dành cho nội dung kiểu slideshow: theo tài liệu x264 nó đặt `deblock=-3:-3` (lọc khối nhẹ hơn), `psy-rd=2.0:0.7` , `aq-strength=1.2` để giữ chi tiết nét của ảnh tĩnh. Về ý tưởng thì hợp với "mỗi cảnh một ảnh" của đồ án ( `video_assembler.py:80` ).

Điểm cần trung thực: code ghép `-tune stillimage` với `-preset ultrafast` . Preset `ultrafast` tắt hẳn deblocking ( `no-` `deblock` ), đặt `subme=0` (psy-rd chỉ có tác dụng khi `subme` đủ cao) và `aq-mode=0` — nên phần lớn tinh chỉnh của `stillimage` gần như không còn tác dụng. Nói cách khác, lựa chọn thực chất là "nhanh nhất có thể"; nếu muốn `stillimage` phát huy thì cần preset chậm hơn (ví dụ `veryfast` / `medium` ).

### 2.7. Âm thanh số: PCM, sample rate, AAC

PCM: lấy mẫu biên độ sóng âm `sr` lần/giây (sample rate, ví dụ 24 kHz, 44,1 kHz, 48 kHz), mỗi mẫu 16 bit. WAV từ TTS là PCM, không nén. Theo định lý Nyquist, sample rate `sr` biểu diễn được tần số tới `sr/2` . AAC (Advanced Audio Coding): codec có mất mát, là "MP3 thế hệ sau", codec audio chuẩn đi kèm H.264 trong MP4. Biến đổi MDCT sang miền tần số. Mô hình tâm lý âm học (psychoacoustic model): bỏ các thành phần tai không nghe được (tần số bị che lấp — masking, dưới ngưỡng nghe). Lượng tử hoá + mã Huffman. Code dùng `-c:a aac -b:a 192k` ( `video_assembler.py:195` ): 192 kbps là mức rất dư cho giọng đọc (giọng nói thường ổn ở 64–128 kbps), đảm bảo không có "tiếng kim loại" do nén. Module kế thừa cũng dùng `audio_bitrate = "192k"` ( `video.py:71` ).

### 2.8. Loudness (độ lớn cảm nhận) và chuẩn hoá

Trực giác. "Âm lượng" mà tai cảm nhận không phải biên độ đỉnh (peak). Một đoạn có một tiếng "bụp" lớn nhưng còn lại rất nhỏ vẫn nghe nhỏ.

- LUFS (Loudness Units relative to Full Scale) theo ITU-R BS.1770: lọc K-weighting (mô phỏng độ nhạy tai: giảm bass, tăng nhẹ vùng cao) → tính năng lượng trung bình theo khối 400 ms → gating (bỏ khối quá nhỏ, ngưỡng tuyệt đối −70 LUFS và ngưỡng tương đối −10 LU) → ra integrated loudness. Các nền tảng như YouTube/Spotify chuẩn hoá quanh −14 LUFS.

Trong đồ án chuẩn hoá loudness nằm ở đâu? Ở Bước 2 (TTS), không phải ở bước dựng video:

- `AIVoice/src/utils/audio.py:120-194apply_audio_post_processing(target_lufs=-14.0, fade_in=0.1, fade_out=0.1)` : fade tuyến tính 0,1 s hai đầu (chống tiếng "click") → đo bằng `pyloudnorm.Meter(sr).integrated_loudness` → `pyln.normalize.loudness(..., -14)` → giới hạn peak 0,98; nếu thiếu `pyloudnorm` thì fallback peak-normalize về 0,95. Orchestrator bật mặc định: `pipeline.py:426` ( `normalize` mặc định `True` ), `--target-lufs -14.0` ( `pipeline.py:435` ).

Bước dựng video không chạy `loudnorm` / `dynaudnorm` của ffmpeg (grep 0 kết quả). Nó chỉ trộn giọng + nhạc nền bằng `volume` + `amix` (mục 4.3).

### 2.9. Kiến trúc ffmpeg — "dây chuyền 5 trạm"

ffmpeg là một chương trình CLI dựng trên các thư viện `libavformat` , `libavcodec` , `libavfilter` , `libswscale` , `libswresample` . Mỗi lệnh ffmpeg là một dây chuyền:

Các khái niệm cú pháp cần đọc được lệnh của code:

- **Cú pháp:** `-i X` · **Ý nghĩa:** thêm input; đánh số từ 0 theo thứ tự
- **Cú pháp:** `-f concat` · **Ý nghĩa:** ép demuxer "concat" cho input kế tiếp
- **Cú pháp:** `0:v` , `1:a` · **Ý nghĩa:** stream specifier: video của input 0, audio của input 1
- **Cú pháp:** `-map` · **Ý nghĩa:** chọn stream nào đưa vào output (không có `-map` ffmpeg tự chọn)
- **Cú pháp:** `-vf` · **Ý nghĩa:** filtergraph đơn giản (1 vào 1 ra) cho video
- **Cú pháp:** `-filter_complex` · **Ý nghĩa:** filtergraph phức (nhiều vào/ra), dùng nhãn `[1:a]` , `[voice]` , `[aout]`
- **Cú pháp:** `-c:v` , `-c:a` · **Ý nghĩa:** codec cho video/audio; `-c copy` = stream copy
- **Cú pháp:** `-r 24` · **Ý nghĩa:** fps đầu ra (nhân bản/bỏ frame để ra CFR 24)
- **Cú pháp:** `-t 123.4` · **Ý nghĩa:** giới hạn thời lượng đầu ra
- **Cú pháp:** `-shortest` · **Ý nghĩa:** dừng khi stream ngắn nhất hết
- **Cú pháp:** `-y` · **Ý nghĩa:** ghi đè file đầu ra không hỏi

### 2.10. Concat: demuxer vs filter vs re-encode

- **Cách:** Concat demuxer ( `-f` `concat -i list.txt` ) · **Cơ chế:** Đọc tuần tự các file trong danh sách như một input liền mạch, dịch timestamp nối đuôi · **Ưu:** Kết hợp `-c copy` → không mã hoá lại, nhanh cỡ tốc độ ổ đĩa, không mất chất lượng · **Nhược:** Các file phải cùng codec, độ phân giải, pix_fmt, timebase, tham số audio. Nếu khác nhau, ffmpeg không phải lúc nào cũng báo lỗi — có thể vẫn trả mã 0 nhưng file ra phát sai từ đoạn thứ hai
- **Cách:** Concat filter ( `concat=n=..:v=1:a=1` ) · **Cơ chế:** Giải mã tất cả rồi nối ở mức frame · **Ưu:** Chịu được file khác nhau · **Nhược:** Bắt buộc re-encode → chậm, giảm chất lượng
- **Cách:** Concat protocol ( `concat:a.ts|b.ts` ) · **Cơ chế:** Nối byte · **Ưu:** Chỉ hợp với MPEG-TS · **Nhược:** Không dùng được cho MP4

Đồ án dùng concat demuxer ở cả hai chỗ:

- 1. Bước 3e — danh sách ảnh kèm `duration` (biến ảnh tĩnh thành timeline video), sau đó phải encode vì ảnh PNG không phải H.264. 2. Bước 5 — danh sách file mp4 + `-c copy` (không encode), có fallback re-encode.

### 2.11. GPU encoding — NVENC

- GPU NVIDIA có một khối phần cứng riêng tên NVENC (ASIC mã hoá video), tách biệt với CUDA core mà Stable Diffusion dùng. Nên encode bằng NVENC gần như không chiếm tài nguyên tính toán của SD và giải phóng CPU. Đánh đổi: ở cùng bitrate, NVENC thường kém libx264 preset chậm một chút về hiệu suất nén; nhưng nhanh hơn nhiều lần. Encoder tên `h264_nvenc` trong ffmpeg; cần driver đủ mới. Nếu driver cũ/không có GPU → ffmpeg báo lỗi → code fallback libx264 (mục 4.4).

### 2.12. Hiệu ứng Ken Burns — nguyên lý và toán

Trực giác. Đặt tên theo nhà làm phim tài liệu Ken Burns: dùng ảnh tĩnh nhưng camera "ảo" từ từ phóng to (zoom) và lia (pan) trên ảnh → người xem có cảm giác chuyển động, không nhàm chán như slideshow.

Cơ chế. Mỗi frame đầu ra là một cửa sổ cắt (crop window) trên ảnh nguồn lớn, được phóng về kích thước đầu ra. Cửa sổ thay đổi mượt theo thời gian.

Ký hiệu: ảnh nguồn kích thước

- ; video đầu ra

- ; cảnh dài

- giây;

- ; tiến độ

- 1. Hệ số zoom nội suy tuyến tính từ

- đến (ví dụ 1,0 → 1,15):

- 1. Kích thước cửa sổ cắt (zoom càng lớn cửa sổ càng nhỏ):

- 1. Vị trí góc trái-trên (pan) nội suy từ điểm đầu

- tới điểm cuối

- , rồi kẹp để không vượt biên:

Zoom vào tâm:

- . 4. Phóng cửa sổ

- về

- (nội suy bicubic/lanczos).

5. Easing (tuỳ chọn) để mượt đầu-cuối: thay bằng

- (ease-in-out).

Vấn đề thực tế — "rung" (jitter). Nếu toạ độ cửa sổ bị làm tròn về số nguyên mỗi frame, ảnh sẽ giật từng pixel. Mẹo phổ biến: phóng ảnh nguồn lên lớn (ví dụ gấp 2–4 lần) trước khi zoompan, hoặc dùng nội suy dấu phẩy động. Trùng hợp là đồ án đã có ảnh upscale 4× (RealESRGAN) — trước khi bị `ImageOps.fit` cắt về 1920×1080 ( `postprocess.py:148` ) — nên nếu làm Ken Burns thì nên chèn vào trước bước fit đó.

Trong ffmpeg hiệu ứng này là filter `zoompan` (biến mỗi ảnh đầu vào thành `d` frame, với biểu thức `z` , `x` , `y` tính theo frame). Ví dụ minh hoạ — KHÔNG có trong code — zoom vào tâm 1,0 → ~1,15 trong 6 giây ở 24 fps (144 frame):

```
# MINH HOẠ, không phải lệnh của đồ án
ffmpeg -i scene_000.png -vf "scale=3840:-1,zoompan=z='min(zoom+0.00105,1.15)':d=144:x='iw/2-(iw/zoom/2)':y='ih/2-
(ih/zoom/2)':s=1920x1080:fps=24" -c:v libx264 -pix_fmt yuv420p scene_000.mp4
```

Ở đây `0.00105≈(1.15 − 1.0) / 143` là bước zoom mỗi frame, `iw/zoom` chính là

- trong công thức. Lưu ý: `zoompan` sinh `d`

frame cho mỗi frame đầu vào, nên với một ảnh tĩnh chỉ cần 1 frame vào (không dùng `-loop 1` , nếu không mỗi frame lặp lại sẽ sinh thêm 144 frame). Công thức cửa sổ

- giả định ảnh nguồn cùng tỉ lệ khung với đầu ra (ở đây 16:9), nếu khác tỉ lệ

thì ảnh bị méo.

Thứ gần nhất với Ken Burns có trong repo là trong module kế thừa `video.py:1279-1281` (hàm `preprocess_video` , dùng MoviePy):

```
zoom_clip = clip.resized(
    lambda t: 1 + (clip_duration * 0.03) * (t / clip.duration)
)
```

- → zoom 1,00 → 1,12 (comment trong code ghi "120%" là không khớp

Với `clip_duration=4` (mặc định): hệ số

công thức). Đây là "zoom-only", không pan, không crop về khung (chỉ resize + composite). Quan trọng: `preprocess_video` không được gọi ở đâu trong repo (grep `preprocess_video` chỉ ra chính định nghĩa) → không ảnh hưởng video truyện.

### 2.13. Chuyển cảnh (transition) và MoviePy

- MoviePy là thư viện Python dựng video ở mức "clip": mỗi clip là một hàm `t→frame (numpy array)` ; nó gọi ffmpeg ở dưới (qua `imageio-ffmpeg` ) để đọc/ghi. Ưu: lập trình linh hoạt (hàm theo thời gian). Nhược: mỗi frame đi qua Python/numpy → chậm hơn ffmpeg filter thuần nhiều lần, tốn RAM. `services/utils/video_effects.py` cài 4 hiệu ứng bằng MoviePy: `fadein_transition` , `fadeout_transition` (dùng `vfx.FadeIn/FadeOut` ), `slidein_transition` , `slideout_transition` (tự tính vị trí tuyến tính `progress = t / T` trên nền `ColorClip` đen, `video_effects.py:21-40` ). Chúng chỉ được gọi trong `combine_videos()` ( `video.py:655-674` ) khi `video_transition_mode` khác None; nhưng lời gọi duy nhất trong `composer.py:182-192` truyền `video_transition_mode=None` . → Trong các luồng hiện tại, không có chuyển cảnh nào được áp. Video truyện dùng cắt cứng (hard cut) giữa các cảnh. `xfade` (crossfade của ffmpeg) không được dùng (grep 0 kết quả).

## 3. Vì sao chọn công nghệ này (so sánh phương án)

- 3.1. ffmpeg CLI qua `subprocess` vs MoviePy vs OpenCV
- Tiêu chí · ffmpeg CLI (đồ án chọn cho Bước 3e & 5) · MoviePy · OpenCV `VideoWriter`
- Tốc độ · Nhanh nhất: C thuần, đa luồng, hỗ trợ NVENC · Chậm (mỗi frame qua Python) · Trung bình
- Audio · Đầy đủ (mix, AAC, map) · Có (nhưng qua file tạm, hay lỗi khoá file trên Windows — xem `video.py:246-261` ) · Không xử lý audio
- Phụ đề · Filter `subtitles` (libass) render đẹp, hỗ trợ tiếng Việt, font riêng · Tự vẽ `TextClip` · Tự vẽ
- Bộ nhớ · Streaming, RAM thấp · Có thể tốn RAM · Thấp
- Độ phức tạp · Phải học cú pháp, escape path · Dễ viết · Dễ

Với ~40 cảnh/chương, chỉ cần "hiện ảnh X trong Y giây + trộn audio + phụ đề" → ffmpeg với concat demuxer là lời giải tối giản, không phải mở từng frame trong Python.

3.2. Lấy ffmpeg từ `imageio-ffmpeg`

`video_assembler.py:139-143` và `video_merger.py:19-21` : dùng `imageio_ffmpeg.get_ffmpeg_exe()` — gói pip có kèm binary ffmpeg tĩnh (comment ở `app/utils/utils.py:36` nhắc tên `ffmpeg-win-x86_64-v7.1.exe` ). Lợi ích: người dùng Windows không cần tự cài ffmpeg/sửa PATH; phiên bản cố định → hành vi lặp lại. Fallback: nếu import lỗi thì dùng `"ffmpeg"` trong PATH. Riêng `video_merger.py` chèn `AIVoice/.venv/Lib/site-packages` vào `sys.path` ( `video_merger.py:19` ) vì orchestrator chạy ở venv khác, không cài `imageio-ffmpeg` .

### 3.3. Slideshow ảnh tĩnh vs Ken Burns vs AI video (AnimateDiff/SVD)

- **Phương án:** Ảnh tĩnh + concat demuxer · **Chi phí:** Gần 0 (encode 1 ảnh/cảnh) · **Tính "hoạt hình":** Thấp · **Tình trạng:** Đang dùng
- **Phương án:** Ken Burns ( `zoompan` ) · **Chi phí:** Thấp (CPU, vài giây/cảnh) · **Tính "hoạt hình":** Trung bình · **Tình trạng:** Hướng phát triển
- **Phương án:** AnimateDiff / Stable Video Diffusion · **Chi phí:** Rất cao: nhiều GB VRAM, hàng phút/cảnh · **Tính "hoạt hình":** Cao · **Tình trạng:** Không khả thi trên GPU phổ thông với hàng chục cảnh/chương

Lựa chọn slideshow là ưu tiên độ ổn định và tốc độ trên phần cứng cá nhân. Khi trả lời, nói rõ đánh đổi này thay vì né.

### 3.4. H.264 + AAC + MP4 thay vì H.265/AV1/MKV

- H.264/AAC/MP4 là tổ hợp tương thích rộng nhất (mọi trình duyệt, YouTube, điện thoại, TV). H.265/AV1 nén tốt hơn 30–50% nhưng encode chậm hơn, một số thiết bị/Windows cần codec bổ sung. Với nội dung slideshow vốn đã nén rất tốt, lợi ích dung lượng không đáng.

### 3.5. Stream copy ở Bước 5

Các video chương cùng được tạo bởi một hàm `assemble_video` với cùng độ phân giải, fps, pix_fmt, codec audio → thoả điều kiện concat `-c copy` . Kết quả: thời gian gộp chỉ phụ thuộc tốc độ đọc/ghi đĩa (thường vài giây đến vài chục giây cho hàng chục chương — ước lượng, chưa đo trong repo), không mất chất lượng (không có "generation loss" do mã hoá lại).

## 4. Hiện thực trong code

### 4.1. Sơ đồ gọi hàm

- `pipeline.py:538-559` dựng lệnh `adapter_video_cli.py` với `--bgm-path` , `--bgm-volume` , `--enable-upscale/--no-upscale` , `--burn-subtitles/--no-subtitles` . `pipeline.py:598-600` : callback `on_video_completed` → `_finalize_video_task` ( `pipeline.py:99-133` ) → nếu `exit_code` `==0` thì tự động gọi `merge_videos` .

4.2. `step3_render_final` — cầu nối upscale → dựng video

`orchestrator.py:543-619` :

1. Nếu `enable_upscaling` → `StorytellingPipeline().release()` để nhả VRAM của SD cho RealESRGAN ( `:564-570` ). 2. `PostProcessor.process_all(...)` ( `:582` ) upscale từng ảnh; bên trong `run_realesrgan` kết thúc bằng `ImageOps.fit(upscaled, (1920, 1080), LANCZOS)` ( `postprocess.py:148` ) → ảnh ra đúng 1920×1080 (cắt vừa khung, không viền đen). Khi tắt upscale: `ImageOps.fit(image, (target_w, target_h))` ( `postprocess.py:93-94` ).

- Hệ quả cần biết: ở Bước 3b, cảnh `close` được sinh khung dọc 576×704 và cảnh `medium` khung 4:3 704×528 ( `orchestrator.py:457-461` ). Comment tại `orchestrator.py:454-456` nói "video assembler sẽ pad về 16:9", nhưng thực tế `ImageOps.fit` ở hậu kỳ đã cắt giữa (center crop) về 16:9 trước đó — nên cảnh cận bị cắt bớt phần trên/dưới chứ không có viền đen. `scale+pad` của assembler hầu như không bao giờ phải làm việc. Chế độ `render_mode="studio"` ( `orchestrator.py:350-357` ) cũng cho ra một PNG `scene_XXX.png` cho mỗi cảnh ( `studio_pipeline.py:600` ), nên bước dựng video không đổi.

3. Dựng `FrameInfo` cho từng scene ( `:603` ) và gọi `assemble_video` ( `:605-613` ), đầu ra `task_dir/final_video.mp4` . 4. `save_state("DONE",...)` ( `:617` ) — mốc quan trọng cho resume.

4.3. `assemble_video` — hai lượt ffmpeg

Bước chuẩn bị: file danh sách concat có `duration`

`video_assembler.py:104-115` :

```
def _create_duration_txt(frames: List[FrameInfo], output_txt: str) -> None:
    with open(output_txt, "w", encoding="utf-8") as f:
        for frame in frames:
            abs_path = os.path.abspath(frame.frame_path)
            safe_path = abs_path.replace("\\", "/")
            f.write(f"file '{safe_path}'\n")
            f.write(f"duration {frame.duration_sec:.3f}\n")
        if frames:
            abs_path = os.path.abspath(frames[-1].frame_path)
            safe_path = abs_path.replace("\\", "/")
            f.write(f"file '{safe_path}'\n")
```

Nội dung `duration.txt` sinh ra có dạng:

```
file 'C:/.../final_frames/scene_000.png'
duration 6.420
file 'C:/.../final_frames/scene_001.png'
duration 4.180
...
file 'C:/.../final_frames/scene_040.png'
duration 5.900
file 'C:/.../final_frames/scene_040.png'
```

Giải thích từng chi tiết:

`duration` : chỉ thị của concat demuxer, cho biết file đó "chiếm" bao nhiêu giây trên timeline. Một ảnh PNG đối với demuxer là một "video 1 frame"; `duration` kéo dài timestamp của nó. Lặp lại dòng `file` cuối (không có `duration` ): mẹo kinh điển — concat demuxer bỏ qua `duration` của mục cuối cùng, nên nếu không lặp thì ảnh cuối chỉ hiện 1 frame. Lặp lại để cảnh cuối được giữ đủ thời lượng. Đổi `\` → `/` : `\` là ký tự escape trong cú pháp file list của ffmpeg. Theo quy tắc quoting của ffmpeg, bên trong cặp nháy đơn `'...'` ký tự `\` được giữ nguyên văn, nên đây chủ yếu là biện pháp phòng thủ: Windows chấp nhận `/` , và dùng `/` thì không phụ thuộc chi tiết escape. Ký tự thật sự nguy hiểm là dấu `'` trong đường dẫn — hàm này không escape nó (xem mục 6). `:.3f` : độ chính xác mili-giây. `-safe 0` (trong lệnh): cho phép đường dẫn tuyệt đối (mặc định demuxer từ chối để an toàn).

Lượt 1 — ảnh → `raw_video.mp4` (chỉ hình)

`video_assembler.py:149-157` :

- `cmd1=[` `]+codec_args+[` `]` `_run_ffmpeg_with_nvenc_fallback(cmd1,work_dir)` · `ffmpeg_exe,"-y","-f","concat","-safe","0","-i",os.path.abspath(duration_txt),` `"-vf",f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2",` `"-r",str(video_fps),"-pix_fmt","yuv420p",` `os.path.abspath(raw_video)`
- Lệnh thực tế với giá trị mặc định (libx264):
- `ffmpeg -y -f concat -safe 0 -i<task_dir>/duration.txt` · `-vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"` `-c:v libx264 -preset ultrafast -tune stillimage` `-r 24 -pix_fmt yuv420p<task_dir>/raw_video.mp4`

Với NVENC, phần codec đổi thành `-c:v h264_nvenc -preset p4 -rc vbr -cq 23` .

Giải thích filter:

`scale=1920:1080:force_original_aspect_ratio=decrease` : co (hoặc giãn, nếu ảnh nhỏ hơn) ảnh sao cho vừa lọt khung 1920×1080 mà giữ tỉ lệ (cạnh nào chạm trước thì dừng). Công thức: hệ số

- , kích thước mới

`pad=1920:1080:(ow-iw)/2:(oh-ih)/2` : đặt ảnh vào giữa canvas 1920×1080, phần thừa tô đen (letterbox/pillarbox). `ow,` `oh` = kích thước đầu ra, `iw, ih` = kích thước đầu vào của filter. Vì ảnh đã được `ImageOps.fit` về đúng 1920×1080 ở hậu kỳ, trong trường hợp thường `scale+pad` gần như no-op; nó là lưới an toàn khi ảnh sai kích thước (ví dụ ảnh gốc chưa upscale, tỉ lệ khác). `-r 24` : concat demuxer ảnh sinh timestamp "thưa" (mỗi ảnh 1 frame với PTS cách nhau `duration` ); `-r 24` bắt ffmpeg nhân bản frame để ra video tốc độ khung hình không đổi (CFR) 24 fps — chuẩn mà mọi trình phát/nền tảng ưa thích.

Lượt 2 — ghép audio (+BGM) + burn phụ đề → `final_video.mp4`

`video_assembler.py:164-171` (phần audio):

```
cmd2 = [ffmpeg_exe, "-y", "-i", os.path.abspath(raw_video), "-i", abs_audio]
if bgm_path and os.path.exists(bgm_path):
    cmd2.extend(["-i", os.path.abspath(bgm_path)])
    filter_complex = f"[1:a]volume=1.0[voice];[2:a]volume={bgm_volume}[bgm];[voice][bgm]amix=inputs=2:duration=first[aout]"
    cmd2.extend(["-filter_complex", filter_complex, "-map", "0:v", "-map", "[aout]"])
else:
    cmd2.extend(["-map", "0:v", "-map", "1:a"])
```

Không có BGM: `-map 0:v -map 1:a` → hình lấy từ `raw_video` , tiếng lấy nguyên từ `.wav` (sau đó encode AAC). Có BGM: filtergraph phức: `[1:a]volume=1.0[voice]` — giọng giữ nguyên. `[2:a]volume=0.15[bgm]` — nhạc nền nhân biên độ 0,15 (mặc định). Đổi sang dB:

- dB.

- `amix=inputs=2:duration=first` — cộng 2 luồng; `duration=first` → độ dài bằng input đầu tiên (giọng); BGM dài hơn bị cắt; nếu BGM ngắn hơn thì phần sau chỉ còn giọng (không lặp BGM, không fade). Lưu ý kỹ thuật: theo tài liệu FFmpeg, `amix` mặc định chuẩn hoá (chia tổng cho số input đang hoạt động; tuỳ chọn `normalize` mặc định bật — binary đi kèm là FFmpeg 7.1) → khi có BGM, giọng bị nhân ~1/2, tức nhỏ đi ~6 dB (

- ). Nếu BGM hết trước, amix tăng dần hệ số trở lại (tham số `dropout_transition` , mặc định 2 s) →

- âm lượng giọng thay đổi giữa chừng. Code không đặt `normalize=0` . Nếu hội đồng hỏi về độ lớn giọng khi có nhạc nền, đây là điểm có thể cải tiến. Dùng đồng thời `-filter_complex` (cho audio) và `-vf` (cho video, khi burn phụ đề) là hợp lệ vì luồng video `0:v` được map thẳng từ input, không đi ra từ filtergraph phức.

`video_assembler.py:173-189` (phụ đề, chỉ khi `burn_subtitles` và có SRT):

```
temp_srt_path = os.path.join(work_dir, "temp_sub.srt")
if burn_subtitles and srt_path and os.path.exists(srt_path):
    shutil.copyfile(srt_path, temp_srt_path)
    sub_style = _build_subtitle_style(st_config)
    from app.utils import utils
    font_dir_abs = utils.font_dir()
    try:
        rel_fonts = os.path.relpath(font_dir_abs, start=work_dir).replace("\\", "/")
    except ValueError:
        rel_fonts = font_dir_abs
    rel_fonts = _escape_filter_path(rel_fonts)
    fonts_dir_opt = f":fontsdir='{rel_fonts}'"
    vf = f"subtitles='temp_sub.srt'{fonts_dir_opt}:force_style='{sub_style}'"
    cmd2.extend(["-vf", vf])
```

Ba mẹo kỹ thuật đáng kể (hay bị hỏi):

- 1. Copy SRT vào `work_dir` với tên cố định `temp_sub.srt` và chạy ffmpeg với `cwd=work_dir` ( `video_assembler.py:85` ) → trong filtergraph chỉ cần tên tương đối, tránh escape đường dẫn Windows ( `C:` có dấu `:` là ký tự phân tách option trong filtergraph; tên file tiếng Việt có dấu, khoảng trắng, `[VI]` ...). 2. `fontsdir` : trỏ libass tới `MediaComposer/resource/fonts` ( `app/utils/utils.py:16-17` ) để dùng font đóng gói kèm (có đủ dấu tiếng Việt). Nếu khác ổ đĩa, `os.path.relpath` ném `ValueError` → dùng đường dẫn tuyệt đối và escape dấu `:` bằng `_escape_filter_path` ( `video_assembler.py:49-57` : `replace(":", r"\:")` , `replace("'", r"\'")` ). 3. `force_style` : ghi đè style ASS mà libass dùng để render SRT. Được build bởi `_build_subtitle_style` ( `video_assembler.py:59-68` ) từ config:

- **Khoá config ( `[storytelling]` ):** `subtitle_font` · **Mặc định ( `config.toml.example:30-34` ):** `"Arial"` · **Chuyển thành ASS:** `FontName=Arial` (kiểm tra có trong `C:\Windows\Fonts` , không thì về Arial — `_get_valid_font` , `:15-36` )
- **Khoá config ( `[storytelling]` ):** `subtitle_font_size` · **Mặc định ( `config.toml.example:30-34` ):** `28` · **Chuyển thành ASS:** `FontSize=28`
- **Khoá config ( `[storytelling]` ):** `subtitle_color` · **Mặc định ( `config.toml.example:30-34` ):** `"white"` · **Chuyển thành ASS:** `PrimaryColour=&HFFFFFF`
- **Khoá config ( `[storytelling]` ):** `subtitle_border` · **Mặc định ( `config.toml.example:30-34` ):** `2` · **Chuyển thành ASS:** `Outline=2`
- **Khoá config ( `[storytelling]` ):** `subtitle_position` · **Mặc định ( `config.toml.example:30-34` ):** `"bottom"` · **Chuyển thành ASS:** `Alignment=2` ( `middle/center` →5, `top` →8)

Màu ASS là `&HBBGGRR` (dạng đầy đủ `&HAABBGGRR` , `AA` là độ trong suốt, bỏ qua thì = `00` = đục hoàn toàn; thứ tự ngược so với HTML `#RRGGBB` ) — `_hex_to_ass_color` ( `video_assembler.py:38-47` ) đảo `rr, gg, bb` thành `&H{bb}{gg}{rr}` . Ví dụ `#FF0000` (đỏ) → `&H0000FF` . `Alignment` theo bố cục bàn phím số (numpad): 1-2-3 dưới, 4-5-6 giữa, 7-8-9 trên.

`video_assembler.py:191-200` (encode cuối):

- `total_dur=sum(f.duration_secforfinframes)` `cmd2.extend(codec_args+[` `])` `_run_ffmpeg_with_nvenc_fallback(cmd2,work_dir)` · `"-r",str(video_fps),"-pix_fmt","yuv420p",` `"-c:a","aac","-b:a","192k",` `"-t",f"{total_dur:.3f}",` `abs_output`
- Lệnh thực tế đầy đủ (có BGM, có phụ đề, libx264):

```
ffmpeg -y -i <task_dir>/raw_video.mp4 -i <chapter>.wav -i <bgm>.mp3
  -filter_complex "[1:a]volume=1.0[voice];[2:a]volume=0.15[bgm];[voice][bgm]amix=inputs=2:duration=first[aout]"
  -map 0:v -map "[aout]"
  -vf
"subtitles='temp_sub.srt':fontsdir='<rel>/resource/fonts':force_style='FontName=Arial,FontSize=28,PrimaryColour=&HFFFFFF,Outline=2,Alignment=2
  -c:v libx264 -preset ultrafast -tune stillimage -r 24 -pix_fmt yuv420p
  -c:a aac -b:a 192k -t <tổng duration> <task_dir>/final_video.mp4
```

`-t total_dur` : cắt output đúng tổng thời lượng cảnh (≈ độ dài audio), tránh đuôi thừa do frame lặp cuối hoặc audio dài hơn vài ms. Mặt trái: nếu `total_dur` ngắn hơn audio (trường hợp SRT có khoảng lặng, mục 1.3) thì phần đuôi audio bị cắt. Cuối cùng xoá file tạm `duration.txt` , `raw_video.mp4` , `temp_sub.srt` ( `:202-207` ).

Vì sao chia 2 lượt thay vì 1? Lượt 1 làm việc "khó chịu" với concat demuxer ảnh + scale/pad; lượt 2 làm audio/phụ đề trên một input video "chuẩn". Tách ra giúp mỗi lệnh đơn giản, dễ debug. Cái giá: video bị mã hoá 2 lần (lượt 2 luôn re-encode vì có `-vf` hoặc do `codec_args` được thêm vào cả khi không có phụ đề). Với nội dung ảnh tĩnh + CRF 23, suy giảm chất lượng thấp nhưng vẫn là điểm có thể tối ưu (xem mục 6).

### 4.4. Chọn codec và fallback NVENC → libx264

`video_assembler.py:70-80` :

```
def _get_video_codec_args() -> list:
    codec = ""
    try:
        from app.config import config as _app_config
        codec = _app_config.app.get("video_codec", "")
    except Exception:
        pass
    if codec == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23"]
    return ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage"]
```

Khoá `[app] video_codec` trong `MediaComposer/config.toml` . File mẫu `config.toml.example:9` đặt `"h264_nvenc"` ; file `config.toml` cục bộ đang có trên máy tại thời điểm viết đặt `"libx264"` (file cấu hình máy, có thể khác ở máy bạn — hãy kiểm tra trước khi demo). WebUI Streamlit của MediaComposer chỉ hiện lựa chọn `h264_nvenc` khi `torch.cuda.is_available()` ( `webui/Main.py:484` ). Fallback ( `video_assembler.py:82-102` ): chạy lệnh; nếu `CalledProcessError` và lệnh có `h264_nvenc` → log cảnh báo, dựng lại lệnh: thay `h264_nvenc` bằng `libx264 -preset ultrafast -tune stillimage` , và lọc bỏ các cặp `-preset<v>` , `-rc` `<v>` , `-cq<v>` còn lại phía sau (vì `-rc` / `-cq` là option riêng của NVENC, libx264 không hiểu). Chạy lại một lần. Fallback này không nhớ kết quả: nếu NVENC hỏng ở lượt 1 thì lượt 2 (và chương sau) vẫn thử NVENC trước rồi mới lùi — tốn thêm một lần chạy hỏng mỗi lệnh, nhưng vẫn ra đúng kết quả. Module kế thừa `video.py` có cơ chế tinh vi hơn: whitelist codec ( `_SUPPORTED_VIDEO_CODECS` , `video.py:79-86` ), kiểm tra `ffmpeg -encoders` có chứa encoder không ( `_ffmpeg_encoder_exists` , cache bằng `lru_cache` , `video.py:175-204` ), và "đánh dấu tắt" codec lỗi cho cả tiến trình ( `_runtime_disabled_video_codecs` ) — chỉ tắt khi libx264 retry thành công (để phân biệt lỗi do GPU với lỗi IO chung).

4.5. `generate_draft_video` — bản nháp (không được dùng)

`video_assembler.py:212-277` tạo video nháp một lượt: concat ảnh + audio, `scale=image_width:image_height` (mặc định code 896×512; làm chẵn), phụ đề cỡ `max(14, 0.6·font_size)` , `-c:v libx264 -r 25 -preset ultrafast -shortest` . Grep cho thấy không có nơi nào gọi hàm này → coi là code dự phòng/di sản. Lưu ý nó còn hardcode `-r 25` .

4.6. `batch_video_runner` — 2-pass và resume

Quét đầu vào

`scan_batch_dir` ( `batch_video_runner.py:101-174` ) ghép `.md` + audio ( `.wav .mp3 .m4a .flac .ogg .aac` , `:45` ) + `.srt` theo stem (tên file bỏ đuôi). Nếu thư mục có bản dịch đánh dấu `" - [VI] "` thì chỉ ghép bản VI ( `:126-137` ). Hỗ trợ thêm layout thư mục con `ep01/script.md + ep01/audio.wav` .

Kiến trúc 2-pass tối ưu VRAM

`run_batch` ( `:216-355` ):

Pass A ( `:242-287` ): với mọi chương: tạo kịch bản + sinh ảnh SD. Giữ SD "nóng" trên GPU suốt vòng → không nạp lại model nhiều lần. Giải phóng SD ( `:289-295` ): `StorytellingPipeline().release()` .

- Pass B ( `:297-349` ): với mọi chương: upscale + `step3_render_final` → `assemble_video` . Giữ RealESRGAN "nóng". Nếu gặp OOM ở Pass A ( `"OutOfMemoryError"` hoặc `"CUDA out of memory"` trong thông điệp), release SD rồi retry 1 lần ( `:268-284` ). Lỗi một chương → ghi `failed` , tiếp chương sau (không làm chết cả batch).

Ý nghĩa: GPU 6–8 GB không chứa nổi đồng thời SD + ESRGAN; chia 2 pass là cách "xếp lịch" để mỗi thời điểm chỉ một model lớn nằm trên VRAM. Bản thân ffmpeg (libx264) chạy trên CPU; NVENC dùng khối phần cứng riêng, chỉ cần ít VRAM cho bộ đệm frame → bước dựng video gần như không tranh VRAM.

Máy trạng thái (state machine) của một chương

Trạng thái ( `:38-43` ): `pending→script_done→images_done→(upscale_done)→video_done` , cộng `failed` . Lưu ở `<output_dir>/batch_state.json` ( `_BatchState` , `:177-213` ), ghi file ngay sau mỗi lần cập nhật ( `update_item` gọi `save()` ), nên dù tiến trình bị kill giữa chừng, lần chạy sau vẫn biết tiến độ.

Resume "không tin mù quáng" — `_reconcile_video_done`

`batch_video_runner.py:74-98` . Tình huống: `batch_state.json` ghi `video_done` nhưng người dùng đã xoá/di chuyển file mp4.

- 1. Nếu `<output_dir>/<stem>.mp4` tồn tại và size > 0 ( `_is_valid_video` , `:48-53` ) → giữ `video_done` . 2. Nếu không, nhưng `task_dir/final_video.mp4` còn → copy phục hồi ( `shutil.copy2` ) và giữ `video_done` .

3. Nếu mất cả hai → đọc `task_dir/state.json` → hạ trạng thái theo bước đã xong ( `_resume_status_from_task_state` , `:56-` `71` ): `DONE→upscale_done` , `STORYBOARD_READY→images_done` , `SCRIPT_READY→script_done` , còn lại `pending` . Pass B sau đó chỉ dựng lại video mà không sinh lại ảnh (tiết kiệm hàng chục phút GPU).

Hàm này có test: `AIVoice/apps/MediaComposer/tests/test_batch_video_resume.py` — `test_stale_video_done_recovers_final_video_from_task_dir` và `test_stale_video_done_without_any_video_is_downgraded` (kỳ vọng hạ về `STATUS_UPSCALE_DONE` ).

Một số chi tiết resume khác ở Pass A ( `_process_single_item_pass_a` , `:358-462` ):

`failed` → reset `pending` để chạy lại từ đầu ( `:374-376` ). Có `task_dir` nhưng thiếu `state.json` → coi là "rác", `shutil.rmtree` rồi tạo `task_dir` mới `batch_<uuid4>` ( `:384-405` ). Sửa lỗi lệch vị trí `state.json` giữa Pass A/B ( `:427-439` ).

Báo cáo và mã thoát

`batch_report.json` ghi `stem, status, video_path, error, time_seconds` cho mỗi chương ( `:351-353` ). `adapter_video_cli.count_incomplete_items` ( `adapter_video_cli.py:29-38` ) đếm chương không có file video thật (tồn tại, size > 0) → nếu > 0 thì `SystemExit(1)` ( `:244-245` ). Có test `test_adapter_counts_missing_reported_video_as_incomplete` . Hệ quả quan trọng: exit ≠ 0 → orchestrator không tự hợp nhất ( `pipeline.py:107` ), trạng thái truyện thành `VIDEO_FAILED` hoặc `CANCELLED` (nếu người dùng bấm dừng).

4.7. Bước 5 — `merge_videos`

`orchestrator/video_merger.py` (96 dòng). Có hai đường gọi:

1. Tự động sau Bước 3 thành công: `_finalize_video_task` ( `pipeline.py:99-133` ) → `merge_videos(video_output_dir,` `TongHop_<ts>.mp4)` → thành công mới đặt `status = "VIDEO_GENERATED"` , `pipeline_step = 3` . Được test ở `tests/test_pipeline_video_completion.py` (merge lỗi → `VIDEO_FAILED` ; merge ok → `VIDEO_GENERATED` ). 2. Thủ công qua API `POST /api/pipeline/step5` → `start_step_5_merge(story_name, selected_files)` ( `pipeline.py:750-` `797` ): chạy trong thread (không phải subprocess, vì chỉ là một lệnh ffmpeg CPU nhẹ), chuyển `print` của merger vào hàng đợi log bằng `contextlib.redirect_stdout(QueueWriter(q))` → stream về UI qua SSE.

Chọn file an toàn — `_select_files`

`video_merger.py:6-13` :

```
def _select_files(mp4_files: list[str], only_files: list[str] | None) -> list[str]:
    filtered = [f for f in mp4_files if not os.path.basename(f).startswith("TongHop_")]
    if only_files:
        # CHỐNG PATH TRAVERSAL: chỉ nhận basename thuần, phải nằm trong danh sách quét được
        wanted = {name for name in only_files if os.path.basename(name) == name}
        filtered = [f for f in filtered if os.path.basename(f) in wanted]
    return filtered
```

Loại mọi `TongHop_*` → không bao giờ gộp file tổng hợp cũ vào file mới (nếu không, lần chạy thứ 2 sẽ nhân đôi nội dung). `only_files` đến từ client → chỉ chấp nhận basename thuần ( `"../secret.mp4"` hay `"/etc/passwd.mp4"` bị loại) và phải nằm trong danh sách `glob` của chính thư mục video → chống path traversal. Thứ tự gộp = `sorted(glob("*.mp4"))` ( `:26` ) → thứ tự từ điển của tên file. Tên chương được chuẩn hoá ở Bước 1 (xem chương về crawler/ `chapter_naming` ), nên thứ tự chương phụ thuộc vào quy tắc đặt tên đó. 4 test trong `tests/test_video_merger.py` : không lọc, lọc theo `only_files` , chống path traversal, loại `TongHop_` ngay cả khi được yêu cầu.

Lệnh ffmpeg của Bước 5

`video_merger.py:33-52` : viết `concat_list.txt` (đường dẫn tuyệt đối, `\` →`/` , và escape dấu nháy đơn theo cú pháp concat `'` → `'\''` ), rồi:

```
ffmpeg -y -f concat -safe 0 -i <video_dir>/concat_list.txt -c copy <video_dir>/TongHop_20260929_231500.mp4
```

Nếu mã thoát ≠ 0 (thường do các file không cùng thông số), fallback re-encode đúng 1 tầng ( `:58-71` ):

```
ffmpeg -y -f concat -safe 0 -i concat_list.txt -c:v libx264 -preset veryfast -crf 20 -c:a aac TongHop_....mp4
```

Nếu vẫn lỗi → in `stderr` và thông điệp `[SYSTEM_MSG]` gợi ý chọn video cùng nguồn ( `:74-78` ). Khối `finally` luôn xoá `concat_list.txt` ( `:85-90` ). `creationflags=CREATE_NO_WINDOW` ( `:56` ) để không bật cửa sổ console đen trên Windows.

### 4.8. Module kế thừa (tóm tắt để không bị hỏi bất ngờ)

`app/services/video.py` (1659 dòng, comment tiếng Trung — kế thừa dự án mã nguồn mở MoneyPrinterTurbo, được sửa thêm): `combine_videos` (cắt stock clip ≤ `max_clip_duration` , resize + nền đen, ghi từng clip tạm bằng MoviePy ở `fps =` `30` , rồi `concat_video_clips_with_ffmpeg` encode một lần với `-pix_fmt yuv420p -c:a aac` ), `generate_video` (ghép audio, BGM có `AudioFadeOut(3)` + `AudioLoop` , phụ đề `TextClip` ), `split_video_file` (cắt `-ss/-t -c copy -avoid_negative_ts` `make_zero` , fallback re-encode), `burn_subtitles_ffmpeg` ( `-crf 18 -preset veryfast` hoặc NVENC `-cq 19 -preset` `slow` , `BorderStyle=3` cho nền hộp, `MarginV` theo tỉ lệ). Dùng cho Composer (ghép stock footage) và Bước 4 autosub/dịch video. `composer.py` — `ComposerWorkflow.run_workflow` (Whisper → LLM trích từ khoá → tải stock video → `combine_videos` → `generate_video` ), có "fast path" stream copy khi không cần phụ đề/BGM ( `composer.py:148-172` ); `run_translation_workflow` (trích audio mono 16 kHz PCM cho Whisper, dịch SRT, lồng tiếng, burn phụ đề). Không thuộc luồng truyện → video. `material.py` — tìm/tải video stock từ Pexels, Pixabay, Coverr ( `search_videos_pexels` , `search_videos_pixabay` , `search_videos_coverr` , `download_videos` ); chỉ dùng cho Composer.

5. Sơ đồ luồng tổng hợp của `assemble_video`

## 6. Hạn chế & hướng phát triển

- **#:** 1 · **Hạn chế (có dẫn chứng code):** Không có chuyển động/Ken Burns, không chuyển cảnh (hard cut) — grep `zoompan` , `xfade` = 0 · **Ảnh hưởng:** Video giống slideshow · **Hướng cải tiến:** Thêm `zoompan` theo từng cảnh (hướng zoom/pan chọn theo `shot_type` từ LLM: close → zoom in chậm, wide → pan ngang), `xfade=transition=fade:duration=0.5` giữa các cảnh
- **#:** 2 · **Hạn chế (có dẫn chứng code):** Mã hoá 2 lần (lượt 1 và lượt 2 đều encode) · **Ảnh hưởng:** Tốn thời gian, suy giảm nhỏ chất lượng · **Hướng cải tiến:** Gộp thành 1 lệnh (concat ảnh + audio + filter_complex cho cả video lẫn audio), hoặc lượt 1 dùng codec lossless/intra rồi lượt 2 encode cuối
- **#:** 3 · **Hạn chế (có dẫn chứng code):** libx264 `ultrafast` + CRF mặc định 23, không đặt `-` `crf` tường minh · **Ảnh hưởng:** File to hơn cần thiết · **Hướng cải tiến:** `-preset veryfast/medium -crf 20` tường minh; thêm `-movflags +faststart` để phát web ngay khi tải
- **#:** 4 · **Hạn chế (có dẫn chứng code):** `amix` không đặt `normalize=0` , không ducking, BGM không lặp/không fade ( `video_assembler.py:168` ) · **Ảnh hưởng:** Giọng có thể nhỏ đi khi có BGM; nhạc dừng đột ngột · **Hướng cải tiến:** `amix=...:normalize=0` , `aloop` / `-stream_loop -1` cho BGM, `afade` ở cuối, `sidechaincompress` để ducking; hoặc `loudnorm` 2-pass cho bản cuối
- **#:** 5 · **Hạn chế (có dẫn chứng code):** Lỗi ffmpeg bị nuốt: `stdout=DEVNULL, stderr=STDOUT` ( `video_assembler.py:85` ) · **Ảnh hưởng:** Khó chẩn đoán khi lỗi · **Hướng cải tiến:** Bắt `stderr` ( `capture_output=True` ) và log dòng cuối
- **#:** 6 · **Hạn chế (có dẫn chứng code):** `_create_duration_txt` không escape dấu `'` trong đường dẫn (merger thì có) · **Ảnh hưởng:** Hỏng nếu đường dẫn task có dấu nháy (thực tế task dir là `batch_<uuid>` nên hiếm) · **Hướng cải tiến:** Dùng chung hàm escape như `video_merger.py:40`
- **#:** 7 · **Hạn chế (có dẫn chứng code):** `PostProcessor.process_all` bỏ qua frame không tồn tại ( `postprocess.py:164-166` ) nhưng `step3_render_final` truy cập `final_paths[i]` theo chỉ số cảnh ( `orchestrator.py:584-585` ) · **Ảnh hưởng:** Nếu thiếu 1 ảnh → lệch chỉ số hoặc `IndexError` · **Hướng cải tiến:** Giữ đúng độ dài danh sách (ảnh thay thế) hoặc báo lỗi rõ
- **#:** 8 · **Hạn chế (có dẫn chứng code):** Bước 5 gộp theo thứ tự tên file ( `sorted(glob)` ) · **Ảnh hưởng:** Sai thứ tự nếu tên chương không chuẩn hoá · **Hướng cải tiến:** Sắp theo số chương trích từ metadata
- **#:** 9 · **Hạn chế (có dẫn chứng code):** Stream-copy yêu cầu cùng thông số; nếu các chương được encode khác nhau (ví dụ một số chương NVENC, một số libx264 do fallback) thì concat `-c copy` có thể vẫn trả mã 0 nhưng phát lỗi từ chương khác thông số → fallback re-encode (chỉ kích hoạt khi returncode ≠ 0) không chạy · **Ảnh hưởng:** File tổng hợp có thể hỏng âm thầm · **Hướng cải tiến:** Kiểm tra thông số bằng `ffprobe` trước khi copy; chuẩn hoá codec/profile/level; hoặc ép re-encode khi phát hiện khác nhau
- **#:** 9b · **Hạn chế (có dẫn chứng code):** Khoảng lặng giữa các block SRT không được cộng vào `duration_sec` ( `_fix_monotonic` , `srt_mapper.py:335-` `349` ) · **Ảnh hưởng:** Khi có SRT: ảnh lệch sớm dần so với tiếng, `-t` có thể cắt đuôi audio · **Hướng cải tiến:** Kéo `end_time` của mỗi cảnh tới `start_time` của cảnh sau, cảnh đầu bắt đầu từ 0
- **#:** 10 · **Hạn chế (có dẫn chứng code):** Tự động hợp nhất gộp mọi `*.mp4` trong thư mục (không riêng lần chạy này) · **Ảnh hưởng:** File tổng hợp có thể chứa chương cũ · **Hướng cải tiến:** Là hành vi thiết kế; có Bước 5 thủ công với `selected_files`
- **#:** 11 · **Hạn chế (có dẫn chứng code):** `generate_draft_video` và `preprocess_video` không được gọi · **Ảnh hưởng:** Code chết · **Hướng cải tiến:** Xoá hoặc nối vào UI "xem nháp"

## Câu hỏi hội đồng có thể hỏi

### 1. Video của em có phải là hoạt hình thật không? Sao nhân vật không chuyển động?

Không phải animation từng khung. Mỗi cảnh là một ảnh do Stable Diffusion sinh, giữ trên màn hình đúng thời lượng câu thoại tương ứng, có lồng tiếng và phụ đề. Em chọn vậy vì AnimateDiff/SVD cần nhiều VRAM và hàng phút mỗi cảnh, không khả thi với hàng chục cảnh mỗi chương trên GPU cá nhân. Hướng cải tiến rẻ nhất là thêm Ken Burns bằng filter `zoompan` của ffmpeg.

### 2. Ken Burns là gì, em sẽ cài đặt thế nào?

Là mô phỏng camera zoom/pan trên ảnh tĩnh. Mỗi frame cắt một cửa sổ kích thước `W/z(t) × H/z(t)` với `z(t)` tăng tuyến tính (ví dụ 1,0→1,15), vị trí nội suy từ điểm đầu tới điểm cuối, rồi phóng về

1920×1080. Trong ffmpeg dùng `zoompan=z=...:x=...:y=...:d=<sốframe>:s=1920x1080:fps=24` , nên áp lên ảnh 4× trước bước `ImageOps.fit` để tránh rung.

### 3. ffmpeg ghép ảnh thành video bằng cách nào?

Dùng concat demuxer với file `duration.txt` : mỗi ảnh một dòng `file` `'...'` và `duration<giây>` ; ảnh cuối lặp lại vì demuxer bỏ qua duration của mục cuối. Sau đó `scale+pad` về 1920×1080, `-` `r 24` để nhân bản frame thành video 24 fps cố định, `-pix_fmt yuv420p` , encode H.264 ( `video_assembler.py:104-157` ).

### 4. Làm sao đảm bảo hình và tiếng khớp nhau?

Độ dài audio được đọc chính xác (module `wave` , lỗi thì raise chứ không đoán). Khi không có SRT — trường hợp mặc định — thời lượng các cảnh được chia liền mạch theo tỉ lệ số từ trên đúng tổng độ dài đó, nên tổng `duration_sec` bằng độ dài audio. Khi có SRT, cảnh lấy mốc của block SRT và `_fix_monotonic` ép tăng dần, cảnh cuối kết thúc đúng độ dài audio. Khi dựng, lượt 2 dùng `-t total_dur` để cắt đúng tổng thời lượng, còn `amix` `duration=first` giữ độ dài theo giọng đọc. Em cũng biết một hạn chế: với SRT có khoảng lặng giữa các câu, khoảng lặng không được cộng vào cảnh nên có thể lệch nhẹ — cách sửa là kéo cuối mỗi cảnh tới đầu cảnh sau.

### 5. Container và codec khác nhau thế nào? Video của em dùng gì?

Codec là thuật toán nén một luồng (H.264, AAC). Container là "hộp" chứa các luồng, timestamp và metadata (MP4, WAV). Video đầu ra là container MP4 chứa luồng H.264 (yuv420p, 24 fps, 1920×1080) và luồng AAC 192 kbps.

### 6. Vì sao ép `yuv420p` ?

Ảnh PNG là RGB; nếu không ép, x264 có thể xuất 4:4:4, nhiều trình phát và thiết bị không phát được. 4:2:0 giữ độ sáng đầy đủ, giảm độ phân giải màu 4 lần, đúng với đặc điểm mắt người, và là định dạng tương thích rộng nhất.

### 7. CRF là gì, em đặt bao nhiêu?

CRF là chế độ giữ chất lượng cảm nhận không đổi, bitrate tự dao động; thang 0–51, thấp là đẹp hơn. Lượt dựng chương dùng libx264 không đặt `-crf` nên là mặc định 23, với `-preset ultrafast -tune` `stillimage` (thực tế `ultrafast` tắt deblock/AQ và hạ `subme` nên `stillimage` gần như không còn tác dụng — ưu tiên là tốc độ). Với NVENC là `-rc vbr -cq 23 -preset p4` . Fallback re-encode của bước hợp nhất dùng `-crf 20 -preset` `veryfast` .

### 8. Keyframe/GOP liên quan gì tới đồ án?

Keyframe (I-frame) là frame giải mã độc lập, cần cho tua và cho cắt ghép bằng stream copy. Code không đặt `-g` nên dùng mặc định của encoder (libx264 `keyint=250` ). Vì mỗi cảnh là ảnh tĩnh, các P- frame sau keyframe gần như "không đổi" nên video nén rất nhỏ.

### 9. Vì sao dùng NVENC? Nếu máy không có GPU NVIDIA thì sao?

NVENC là khối mã hoá phần cứng riêng trên GPU, nhanh và không tranh CUDA core với Stable Diffusion, giải phóng CPU. Nếu driver không hỗ trợ, `_run_ffmpeg_with_nvenc_fallback` bắt lỗi, thay bằng `libx264 -preset ultrafast -tune stillimage` , loại bỏ các option riêng NVENC ( `-rc` , `-cq` , `-preset p4` ) rồi chạy lại.

### 10. Ghép nhạc nền thế nào? Có chuẩn hoá âm lượng không?

Có BGM thì dùng `filter_complex` : giọng `volume=1.0` , nhạc `volume=0.15` (≈ −16,5 dB), `amix=inputs=2:duration=first` . Chuẩn hoá loudness −14 LUFS theo ITU-R BS.1770 (thư viện `pyloudnorm` ) thực hiện ở Bước 2 TTS ( `AIVoice/src/utils/audio.py` ), bước dựng video không chạy `loudnorm` . Hạn chế: `amix` mặc định chuẩn hoá theo số input nên giọng có thể nhỏ đi khi có BGM; có thể cải tiến bằng `normalize=0` và ducking.

### 11. Bước hợp nhất khác gì bước dựng? Vì sao nhanh?

Hợp nhất dùng concat demuxer với `-c copy` : chỉ demux và mux lại, không giải mã/mã hoá, nên nhanh cỡ tốc độ đọc ghi đĩa và không mất chất lượng. Điều kiện là các file cùng thông số; bình thường được đảm bảo vì mọi chương đều do cùng `assemble_video` với cùng config tạo ra, và file nào cũng bắt đầu bằng keyframe. Nếu ffmpeg trả lỗi thì fallback re-encode libx264 CRF 20. Trường hợp biên: nếu vài chương bị fallback từ NVENC sang libx264, stream copy có thể không báo lỗi mà ra file phát sai, đây là điểm em sẽ bổ sung kiểm tra bằng `ffprobe` .

### 12. Làm sao tránh gộp file tổng hợp cũ và chống tấn công đường dẫn?

`_select_files` loại mọi file bắt đầu bằng `TongHop_` , và với danh sách do người dùng chọn chỉ chấp nhận basename thuần nằm trong danh sách quét được của thư mục, nên `../secret.mp4` bị loại. Có 4 unit test trong `tests/test_video_merger.py` .

### 13. Nếu đang chạy 20 chương mà mất điện thì sao?

`batch_state.json` được ghi ngay sau mỗi lần đổi trạng thái ( `pending/script_done/images_done/video_done/failed` ). Chạy lại thì chương `video_done` được bỏ qua, chương đang dở chạy tiếp từ bước đã xong. `_reconcile_video_done` còn kiểm tra file mp4 thật: mất file thì copy lại từ `final_video.mp4` hoặc hạ trạng thái để Pass B dựng lại mà không cần sinh lại ảnh.

### 14. Vì sao chia Pass A / Pass B?

GPU 6–8 GB không chứa đồng thời Stable Diffusion và RealESRGAN. Pass A sinh ảnh cho mọi chương khi SD đang nằm trên GPU, sau đó giải phóng SD, rồi Pass B upscale và dựng video khi ESRGAN nằm trên GPU. Mỗi model chỉ nạp một lần. Ngoài ra lỗi OOM ở Pass A được retry một lần sau khi release.

### 15. Vì sao chạy ffmpeg với `cwd=work_dir` và copy SRT thành `temp_sub.srt` ?

Trong filtergraph, dấu `:` là ký tự phân tách option, nên đường dẫn Windows `C:\...` và tên file tiếng Việt, có khoảng trắng dễ làm hỏng cú pháp. Copy SRT vào thư mục làm việc với tên cố định và chạy ffmpeg tại đó thì chỉ cần tên tương đối. Nếu thư mục font khác ổ đĩa thì `_escape_filter_path` escape `:` và `'` .

## Tóm tắt 1 phút

"Bước dựng video của em dùng ffmpeg, gọi qua subprocess, lấy binary đóng gói sẵn từ imageio-ffmpeg nên người dùng không phải cài gì thêm. Mỗi chương được dựng trong hai lượt. Lượt một dùng concat demuxer: một file danh sách ghi mỗi ảnh cảnh kèm số giây của nó, ảnh cuối lặp lại để không bị mất thời lượng. Ảnh được scale và pad về 1920×1080, xuất 24 fps, yuv420p, codec H.264 bằng libx264 hoặc NVENC trên GPU, NVENC lỗi thì tự lùi về libx264. Lượt hai gắn giọng đọc; nếu có nhạc nền thì trộn bằng amix với nhạc ở mức 0,15; nếu bật phụ đề thì burn SRT bằng libass với font và style lấy từ config. Audio là AAC 192 kbps, video được cắt đúng bằng tổng thời lượng cảnh, vốn đã được căn khớp với độ dài audio. Batch chạy theo hai pass để tiết kiệm VRAM, có batch_state.json để chạy tiếp khi bị ngắt và tự kiểm tra file video thật. Cuối cùng, Bước 5 gộp các chương bằng concat -c copy, không mã hoá lại nên vừa nhanh vừa không mất chất lượng, có chống path traversal và loại file tổng hợp cũ. Em nói thẳng một hạn chế: video hiện là slideshow ảnh tĩnh, chưa có Ken Burns hay chuyển cảnh. Hướng phát triển là dùng filter zoompan và xfade của ffmpeg, chi phí gần như bằng không."
