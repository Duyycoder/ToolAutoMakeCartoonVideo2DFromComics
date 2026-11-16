# Handoff: video editor on `game`

Updated 2026-11-17. Branches: `feat/editor` (deployed), `feat/device-export` (on-device export, in progress).

## Deployment

- Public URL: `https://game.ririmimivn.id.vn` (HTTPS page returned 200).
- Server SSH alias: `rr`; deployment directory: `/home/dev/game-editor`.
- User service: `systemctl --user status game-editor.service`; app listens on `127.0.0.1:8000`, Caddy/tunnel currently reaches it.
- Workspace: `/home/dev/CaoDichVideo`.
- Basic Auth username is `game`. Password is kept only in `/home/dev/game-editor/.env` (mode 600), never commit that file. Change it there, then run `systemctl --user restart game-editor.service`.
- User linger is currently off. To start the enabled user service automatically after reboot, server owner can run `sudo loginctl enable-linger dev`.

## Server capabilities

- 4 CPU cores, 7.2 GiB RAM, GTX 750 Ti with 2 GiB VRAM.
- Ollama serves `qwen2.5:0.5b-instruct`. The editor enables only translation (`EDITOR_AI_MODE=translate`); Whisper, OCR, voiceover and heavy AI actions return 503 and are hidden from the AI panel.
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
- Preview speed selector (`#tocDoXem`, `ui.toc_do_xem`, preview only). Mouse left-drag on empty timeline pans; Shift+drag box-selects. Selecting only audio clips cuts only them (linked video untouched). Double-click / double-tap a clip opens properties (audio-track clips open the Audio tab).

## Running on a local GPU machine

- `run.bat`: desktop window on that machine (full AI, NVENC export).
- `run-worker.bat` (`orchestrator/may_xuat.py`): remote export worker on the GPU laptop, reached over Tailscale on port 8300 with a bearer token (`configs/may_xuat_token.txt`, git-ignored). The editor machine picks "Laptop GPU qua Tailscale" in the export dialog; `orchestrator/editor/xuat_tu_xa.py` sends the ffmpeg command, uploads missing media once (content-keyed cache in `storage/may_xuat/`, kept 14 days) and downloads the result. Worker commands may only read cached files (`@tep:`) and write `@ra`. If the laptop is unreachable, export falls back to the local machine.
- `run-lan.bat` (`orchestrator/chay_mang_noi_bo.py`): serves on port 8200 for phones on the same Wi-Fi, Basic Auth user `game`, password generated into `configs/mat_khau_mang_noi_bo.txt` (git-ignored). Proxies use NVDEC/NVENC when available (`media.co_gpu`, disable with `EDITOR_NO_GPU=1`) and fall back to CPU.

## Exports, rotation and downloads

- Web/phone users download exports from the server: `GET /api/du-an/{pid}/xuat` lists `xuat/`, `GET …/xuat/tai?ten=` serves an attachment; the desktop app (page on 127.0.0.1) copies with `POST …/xuat/luu-ra` (folder picked by `/api/system/pick-files`). Export dialog shows "Bản đã xuất".
- Portrait phone videos carry a "Display Matrix" rotation. ffmpeg 9 copies it into outputs and CUDA-decoded frames are not auto-rotated, so exports came out sideways via the laptop (NVENC). Fix (deployed, `2b6f948`): `-hwaccel cuda` only when `media.xoay == 0` (probed and stored at import since this fix; older media → CPU decode), and every export ends with `sidedata=mode=delete:type=DISPLAYMATRIX`. Test: `tests/test_xuat_video_xoay.py`.
- Known: server x264 exports are ~3/255 darker than the source (on-device export matches the source better); not investigated yet.

## On-device export (experimental, merged into `feat/editor` 2026-11-17)

Exporter "Thiết bị này" in the export dialog (web only — hidden when the page runs on 127.0.0.1): the browser decodes the
ORIGINAL media, composites every frame and encodes with the device hardware (WebCodecs via Mediabunny), the server only
renders the audio track (exact same filters) which is copied into the MP4 without re-encoding. Plan: `plans/261116-2137-xuat-tren-thiet-bi/`.

- Library: `webui/editor/thu_vien_ngoai/mediabunny-1.65.1.min.js` (MPL-2.0, unmodified, renamed .mjs→.js so any server serves a JS MIME; provenance + SHA-256 in `NGUON.txt`). mp4-muxer is deprecated in favour of it.
- `xuat_thiet_bi/ho_so_may.js` device profile (isConfigSupported + real 45-frame encode benchmark per codec × resolution), `thu.html`/`thu.js` dev test page.
- `nguon_video.js` (Range-read original, sequential decode by timestamps; Mediabunny `draw()` applies phone rotation), `ghep_khung.js` (same math as preview: hopLop/giaTriTai/thoiDiemMedia/cssFilter, crop + rounded corners, opacity, blend; base-track transitions centred on the cut like `render.tinh_xfade`), `chuyen_canh_tb.js` (xfade directions measured from ffmpeg: wipeleft = B from the RIGHT edge, wipeup = from the BOTTOM…; exact: fade/dissolve/wipe*/slide*, others approximated + warned), `phan_loai.js` (blocks: subtitles, text/shapes, subtitle covers, advanced colour; warns: HDR→SDR, CSS-filter effects, approximated transitions), `tieng_server.js` (POST export `chi_am_thanh`, name contains `tieng-thiet-bi` → hidden from the export list and deleted after download via `DELETE …/xuat/tai`), `ghep_mp4.js` (OPFS streaming target, fastStart false, AAC packet copy), `vong_xuat.js` (orchestration, `kichThuocXuat` = `render.kich_thuoc_xuat`), `ui_xuat_tb.js` (dialog text, progress toast with Cancel, wake lock, save via share sheet on phones / download).
- Server fix included: audio-only export (`chi_am_thanh`) failed with "vc unconnected" → video branch now ends in `nullsink`.
- Verified in headless Chrome on this PC (no discrete GPU, software H.264): 720×1280 4 s with server audio OK; 2 clips + wipeleft + rotated/cropped/rounded overlay with keyframes matches the server render visually (mean diff 3–8/255, mostly the server darkening). Not yet tried on a real iPhone or the RTX laptop, and the export-dialog UI path was never clicked through in a browser (option is hidden on 127.0.0.1).

## Deleting projects/media, batch subtitles (2026-11-17)

- Project delete returned 500 on the server: `send2trash` was never in `orchestrator/requirements.txt` (now added; on Linux files go to `~/.local/share/Trash`).
- Media could only be removed via right-click (`contextmenu`), which phones never fire → every media card has a ⋮ button (always visible on touch). Removing media still used on the timeline now offers to delete those clips too (one undo step) instead of failing with "Media đang có trên timeline".
- Batch Whisper subtitles: `webui/editor/phu_de_hang_loat.js` — AI panel button "🎙 Nhiều video…" (also shown when the timeline is empty) and the media multi-select menu. Lists every ready video/audio in the project (need not be on the timeline: captions are anchored to media time), queues one `phu-de` job per video on the GPU queue (they run one after another); each result auto-applies to its own video.

## Git status and handoff

- `feat/editor` is pushed and deployed (last `2b6f948`). `AIVoice` is a third-party submodule and was not modified.
- `plans/` stays out of Git (local notes). Keep deployment credentials, `configs/global_config.json`, `configs/may_xuat_token.txt` out of Git.
