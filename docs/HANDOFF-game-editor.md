# Handoff: video editor on `game`

Updated 2026-11-17. Branch `feat/editor` (deployed; `feat/device-export` kept equal to it).

## Deployment

- Public URL: `https://game.ririmimivn.id.vn` (HTTPS page returned 200).
- Server SSH alias: `rr`; deployment directory: `/home/dev/game-editor`.
- User service: `systemctl --user status game-editor.service`; app listens on `127.0.0.1:8000`, Caddy/tunnel currently reaches it.
- Workspace: `/home/dev/CaoDichVideo`.
- Basic Auth username is `game`. Password is kept only in `/home/dev/game-editor/.env` (mode 600), never commit that file. Change it there, then run `systemctl --user restart game-editor.service`.
- User linger is currently off. To start the enabled user service automatically after reboot, server owner can run `sudo loginctl enable-linger dev`.

## Server capabilities

- 4 CPU cores, 7.2 GiB RAM, GTX 750 Ti with 2 GiB VRAM.
- Ollama serves `qwen2.5:0.5b-instruct`. The editor enables translation + Whisper subtitles (`EDITOR_AI_MODE=translate,phu-de`, a comma list; `all`/`off` also work). OCR, voiceover and other heavy AI actions return 503 and their cards are hidden from the AI panel. With no AIVoice (Linux), `phu-de` runs `orchestrator/editor/whisper_truc_tiep.py`: faster-whisper on CPU int8 (GTX 750 Ti is unusable for CTranslate2), model kept loaded between jobs, PhoWhisper → Whisper small, Demucs skipped with a warning.
- A Qwen 1.5B pull timed out without installing the model. The 0.5B model answered a sample but its translation quality was weak; treat it as experimental.
- FFmpeg is provided by the `imageio-ffmpeg` wheel, so export uses CPU. NVIDIA NVENC is not available on this GPU/server setup.

## Phone uploads and media formats (fixed, deployed 2026-11-15)

- Uploads go in 8 MB chunks, 3 in parallel (`orchestrator/editor/tai_len.py`, `webui/editor/tai_len.js`). Chunk state is saved in `.part.json`, so picking the same file again resumes after Safari is suspended or the server restarts. Max 8 GB per file. A screen Wake Lock is held during upload.
- Any file type can be picked on phones. `chuan_hoa_file.py` probes the content with ffmpeg: HEIC/HEIF/AVIF/TIFF become JPG, CAF/AMR/AC3/AIFF become M4A, camera containers (MTS/MXF/3GP/…) always get an H.264 proxy.
- FFmpeg 9 removed `-filter_complex_script`; `render.tham_so_file_loc` picks the option by ffmpeg version. Fonts for burned-in text: `fonts/tai-font-xuat-video.sh` + `fonts/fonts.conf`.

## Pro editing features

- Color (clip `mau`): 18 presets (`webui/editor/preset_mau.json`), `.cube` LUT import (`<project>/luts/`), curves, 8-range HSL, sharpen, denoise. Presets/LUT/curves/HSL merge into one 33³ LUT per clip: `mau_nang_cao.py` (export, ffmpeg `lut3d`) and `mau_nang_cao.js` (WebGL2 preview in `xem_mau_gl.js`) share the same math; `tests/test_editor_mau_nang_cao.py` checks they match.
- Audio (clip `xu_ly_am`): noise reduction (highpass + `afftdn`) and 3-band EQ (`xu_ly_am.py`; Web Audio preview in `am_xu_ly.js`, FFT denoise is export-only). "Extract audio" creates an `.m4a` media.
- Touch timeline (`timeline_cam_ung.js`): one-finger scroll with inertia, pinch zoom, long-press to move a clip, wide trim handles on the selected clip.
- Export option "Keep HDR": HLG 10-bit BT.2020 HEVC (`media.loc_sang_hlg`); default export stays SDR 8-bit H.264.
- "Màu Pro" tab (`bang_mau_pro.js`): scopes (histogram/waveform/RGB parade/vectorscope, `scopes_mau.js`), Lift/Gamma/Gain/Offset wheels (`banh_xe_mau.js`), Blacks/Shadows/Highlights/Whites, white-balance eyedropper, split before/after compare (`preview.datSoSanh`), copy/paste grade across clips. New keys `mau.can_trang`, `mau.tong`, `mau.banh_xe` are applied first inside the same merged LUT (py + js, parity test covers them).
- "Âm thanh" tab (`bang_am_thanh.js`): per-clip effects `hieu_ung_am` (pitch, robot, phone/radio/megaphone band, distortion, bitcrush, tremolo, compressor, echo, convolution reverb with generated room IRs, reverse, loudnorm) in `hieu_ung_am.py` → `render._tieng_clip`; Web Audio preview in `am_hieu_ung.js` (pitch/robot/reverse/loudnorm are export-only). Tests: `tests/test_hieu_ung_am.py` (real ffmpeg).
- Built-in sound library `assets/thu_vien_am/` (all CC0: wyzowl/sfx-kit, Freesound CC0, HoliznaCC0, Komiku) — rebuild with `scripts/xay_thu_vien_am.py`; API `/api/thu-vien-am` (`thu_vien_am.py`); add at playhead or drag to timeline (`timeline.themTuThuVien`).
- "My library": user sounds in `<workspace>/_thu_vien_am/` (ids `toi-…`, files served as `rieng/…`), shared by all projects. `POST /api/du-an/{pid}/media/{mid}/vao-thu-vien` saves a media's audio (video → audio only), `DELETE /api/thu-vien-am/rieng/{id}`. The audio tab has a "Project audio" pane (audio media + video sound) with import and ⭐ save-to-library.
- Layers: `timeline.themLopTaiDauPhat(m)` puts media on a free overlay video / audio track at the playhead, creating a new track when none is free (media card ＋ menu, media context menu).
- Clip speed (`bang_toc_do.js`, properties tab "Tốc độ", also clip right-click → "Chỉnh tốc độ…"): "Thường" = log slider 0.1×–10× + quick steps; "Đồ thị" = speed ramp `clip.toc_do_cong = [{q, v}]` (q = normalized position on the retimed clip, linear between points), presets in `toc_do_cong.js › MAU_DO_THI`, click an empty spot to add a point and drag it, "＋ Thêm điểm" button, double-click a point to remove it. `clip.toc_do` is kept equal to the curve's average speed, so clip length stays `(ra − vao) / toc_do` everywhere. Time mapping: `store.thoiDiemMedia` / `veTimeline` / `tocDoTai` (JS) and `toc_do_cong.py` + `quy_doi.ve_timeline` (py), shared cases `tests/js/ca_toc_do_cong.json`. Export: video uses a `setpts` expression (inverse mapping), audio is cut into ≤0.25 s chunks each with its own `atempo` (`render._tieng_doi_toc`). Split / trim-to-playhead cut the curve; edge-drag trimming keeps the curve shape stretched over the new length.
- Preview speed selector (`#tocDoXem`, `ui.toc_do_xem`, preview only). Mouse left-drag on empty timeline pans; Shift+drag box-selects. Selecting only audio clips cuts only them (linked video untouched). Double-click / double-tap a clip opens properties (audio-track clips open the Audio tab).

## Running on a local GPU machine

- `run.bat`: desktop window on that machine (full AI, NVENC export).
- `run-worker.bat` (`orchestrator/may_xuat.py`): remote export worker on the GPU laptop, reached over Tailscale on port 8300 with a bearer token (`configs/may_xuat_token.txt`, git-ignored). The editor machine picks "Laptop GPU qua Tailscale" in the export dialog; `orchestrator/editor/xuat_tu_xa.py` sends the ffmpeg command, uploads missing media once (content-keyed cache in `storage/may_xuat/`, kept 14 days) and downloads the result. Worker commands may only read cached files (`@tep:`) and write `@ra`. If the laptop is unreachable, export falls back to the local machine.
- `run-lan.bat` (`orchestrator/chay_mang_noi_bo.py`): serves on port 8200 for phones on the same Wi-Fi, Basic Auth user `game`, password generated into `configs/mat_khau_mang_noi_bo.txt` (git-ignored). Proxies use NVDEC/NVENC when available (`media.co_gpu`, disable with `EDITOR_NO_GPU=1`) and fall back to CPU.

## Exports, rotation and downloads

- Web/phone users download exports from the server: `GET /api/du-an/{pid}/xuat` lists `xuat/`, `GET …/xuat/tai?ten=` serves an attachment; the desktop app (page on 127.0.0.1) copies with `POST …/xuat/luu-ra` (folder picked by `/api/system/pick-files`). Export dialog shows "Bản đã xuất".
- Portrait phone videos carry a "Display Matrix" rotation. ffmpeg 9 copies it into outputs and CUDA-decoded frames are not auto-rotated, so exports came out sideways via the laptop (NVENC). Fix (deployed, `2b6f948`): `-hwaccel cuda` only when `media.xoay == 0` (probed and stored at import since this fix; older media → CPU decode), and every export ends with `sidedata=mode=delete:type=DISPLAYMATRIX`. Test: `tests/test_xuat_video_xoay.py`.
- Known: server x264 exports are ~3/255 darker than the source (on-device export matches the source better); not investigated yet.

## On-device export ("Thiết bị này", merged into `feat/editor`)

Exporter "Thiết bị này" in the export dialog (web only — hidden when the page runs on 127.0.0.1): the browser decodes the
ORIGINAL media, composites every frame and encodes with the device hardware (WebCodecs); the server does what the device
cannot (it is always reachable anyway). Plan: `plans/261116-2137-xuat-tren-thiet-bi/` (local, not in git).

- Split of work (`xuat_thiet_bi/phan_loai.js`, frames numbered on the export fps grid, n = t × fps):
  - **Audio**: always server (`tieng_server.js`, POST export `chi_am_thanh`, file name contains `tieng-thiet-bi`, deleted after download); AAC packets copied, never re-encoded.
  - **Text / shapes / subtitles** (one `.ass`, `chu_hinh.tao_ass`): the server renders the libass layer to transparent PNGs (`orchestrator/editor/nuong.py`; libass in ffmpeg writes no alpha, so it renders on black and on white and derives alpha, then `unpremultiply`). One PNG per run of frames with the same active events, one per frame under `\fad`/`\move`. The device draws them on top → pixel-identical text.
  - **Baked segments**: advanced colour (LUT/curves/HSL…), transitions without an exact device version (anything but fade/dissolve/wipe*/slide*), sources the device cannot decode → the server renders those frame ranges of the full timeline (`render` option `doan_nuong`: `select` the frames, concatenated, H.264 crf 12 / NVENC cq 14, no audio, no ASS) and the device copies them in.
  - **Device**: everything else — transforms/keyframes, crop, rounded corners, opacity, blend, basic colour + effects (CSS filters, may differ slightly), subtitle covers (`che_tb.js`: colour exact, blur/mosaic/delogo approximated).
  - Endpoints: `POST /api/du-an/{pid}/nuong` {n0, n1, lop_chu, doan, tuy_chon} → GPU-queue job `nuong`; files `GET …/nuong/{id}/{file}` from `.duan/cache/nuong/<id>/`, `DELETE …/nuong/{id}`; leftovers older than 1 day are removed on the next bake.
  - Baked share > 50 % → the dialog suggests exporting on the server (button); it never switches by itself.
- Device profile (`ho_so_may.js`, "Đo máy" button in the dialog): measured encode speed per codec × resolution. `ui_ho_so.js` disables codecs the device cannot encode, writes an estimate next to each resolution ("~3 phút", "quá chậm" when > 10× the duration, "máy không mã hoá được") and blocks the Export button for those. Codecs H.264 / HEVC / AV1 (`ma_hoa_khuc.chuoiCodec` picks the level from W×H×fps). FPS choices now include 120 (server too).
- Encoding and resume (`ma_hoa_khuc.js`, `khuc_opfs.js`): one `VideoEncoder` per run, 10 s chunks starting with a keyframe (plus one every 2 s), each chunk written to OPFS `xuat_do/<pid>/khuc_NNN.bin/.json` as soon as it finishes; `phien.json` holds a SHA-256 of timeline + media + options and the decoder config. Exporting again after the tab was killed/locked continues from the last finished chunk (the dialog shows the pending session and a "Làm lại từ đầu" box); it restarts automatically when the hash differs, < 10 % was done, or the new encoder produces a different decoderConfig. Cancel deletes the session; sessions expire after 3 days. Browsers without `createWritable` keep chunks in RAM (no resume).
- Final file (`ghep_mp4.js`): Mediabunny `EncodedVideoPacketSource` + AAC packets → MP4 in OPFS (fastStart false); saved via the share sheet on phones, `showSaveFilePicker` (streamed) on desktop Chrome, else a download link. Option "Đưa bản xuất lên dự án": chunked upload (`tai_len.js`, `vaoXuat`) finished by `POST …/media/tai-len/{uid}/vao-xuat` → `xuat/<name>.mp4` (unique name, not imported as media).
- Library: `webui/editor/thu_vien_ngoai/mediabunny-1.65.1.min.js` (MPL-2.0, unmodified; provenance + SHA-256 in `NGUON.txt`).
- Server fixes found while matching frames: audio-only export ended with "vc unconnected" (now `nullsink`); every transition whose second clip starts at media time 0 made the rest of the server video one frame early (start-only `tpad` + `trim` + `fps` dropped the last frame) — now padded with one extra frame (`tests/test_editor_render.py::test_chuyen_canh_khong_lam_hinh_sau_som_mot_khung`).
- Verified in headless Chrome on this PC (no GPU): 10 s 1080p project with subtitle, animated text, colour cover, advanced colour, circleopen → 30 % baked, 300 frames + AAC, per-frame PSNR vs the server export 42 dB mean / 35.8 dB min (baked parts ~46 dB). Resume: 24 s project killed in chunk 2 → exported again, continued from 0:10, 720 frames, join frames ~38.7 dB like the rest. AV1 works (software); HEVC is not available on this PC. The headless test scripts were throwaway; pytest covers `nuong.py`, `phanLoai`, estimates and bitrate.
- Not yet tried on a real iPhone or the RTX laptop. Untagged test sources decode with different colour matrices in Chrome vs ffmpeg (~25 dB); BT.709-tagged sources (phones) match.

## Deleting projects/media, batch subtitles (2026-11-17)

- Project delete returned 500 on the server: `send2trash` was never in `orchestrator/requirements.txt` (now added; on Linux files go to `~/.local/share/Trash`).
- Media could only be removed via right-click (`contextmenu`), which phones never fire → every media card has a ⋮ button (always visible on touch). Removing media still used on the timeline now offers to delete those clips too (one undo step) instead of failing with "Media đang có trên timeline".
- Batch Whisper subtitles: `webui/editor/phu_de_hang_loat.js` — AI panel button "🎙 Nhiều video…" (also shown when the timeline is empty) and the media multi-select menu. Lists every ready video/audio in the project (need not be on the timeline: captions are anchored to media time), queues one `phu-de` job per video on the GPU queue (they run one after another); each result auto-applies to its own video.

## Whisper on the GPU laptop (run-worker.bat)

- The remote export worker also runs AI jobs: `orchestrator/may_ai.py` adds `GET/POST /ai`, `GET/DELETE /ai/{id}` to `may_xuat.py` (same bearer token, same `@tep` content-keyed cache). Only `phu-de` is accepted (result = caption list, no file output). The laptop runs the full AIVoice pipeline (PhoWhisper, Demucs, CUDA) through `ai_bridge` + its own `hang_doi` queue in a throwaway project folder.
- Server side: AI panel "Chạy trên: Máy chủ / Laptop GPU" (shown once a laptop address + token is saved in Export > Máy xuất) sends `tham_so.may = "laptop"`; `api.xep_ai` calls `xuat_tu_xa.MayXuat.chay_ai` and falls back to the server's own Whisper when the laptop is unreachable. Batch subtitles use the same choice.
- The laptop must run the updated code (old worker → 404 on `/ai`, reported as "cập nhật code trên laptop").

## Whisper in the browser ("Máy này")

- AI panel "Chạy trên: Máy này (trình duyệt)": `webui/editor/whisper_trinh_duyet.js` fetches `GET /api/du-an/{pid}/media/{mid}/tieng-16k` (mono 16 kHz WAV cut by the server, cached in `.duan/cache/tieng16k/`, so phones never download the original video) and runs `whisper_worker.js` (transformers.js 4.3.1 from jsDelivr `dist/transformers.min.js` — NOT `transformers.web.min.js`, which has a bare `onnxruntime-web/webgpu` import browsers cannot resolve). WebGPU when available, else WASM q8. Models `onnx-community/whisper-{tiny,base,small}` (medium/large/PhoWhisper → small), downloaded from Hugging Face once and cached by the browser; the model stays loaded in the worker for batch runs. Results go through `BangAi.apDung` (`tren_may: true` skips the server task ack).
- Needs internet on the device (CDN + Hugging Face). Verified in headless Chrome: 7 s English clip → 15 s first run including model download, 1 s second run.

## Git status and handoff

- `feat/editor` is pushed and deployed (see `git log`). `AIVoice` is a third-party submodule and was not modified.
- `plans/` stays out of Git (local notes). Keep deployment credentials, `configs/global_config.json`, `configs/may_xuat_token.txt` out of Git.
