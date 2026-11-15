# Handoff: video editor on `game`

Updated 2026-11-15. Worktree: `feat/editor` at `F:\programfiles\ToolAutoMakeCartoonVideo2DFromComics\.codex-worktrees\editor`.

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

## Latest issue: iPhone Cinematic import

The user selected a Cinematic-mode iPhone video and received **HTTP 408**. Record this for a later fix; no speculative picker change was kept or deployed. Investigate upload size and duration through Cloudflare Tunnel/Caddy, browser upload timeout behavior, and whether resumable/chunked upload is needed. Keep the phone video server-side only after a complete upload.

The upload route accepts `.MOV`/other supported media and stores files under the project cache; the project remains on the server. If upload succeeds but the preview is black, investigate HEVC proxy decoding separately.

## Git status and handoff

- Changes belong to the parent repo branch `feat/editor`; `AIVoice` is a third-party submodule and was not modified.
- Commits already on local worktree: mobile layout, server AI mode/browser upload/auth, server/Caddy templates, and translate-only mode. Commit this handoff, then push `feat/editor`.
- Local GitHub push via this workstation failed (SSH key denied; HTTPS stalled). The server has `gh` authenticated as the repo owner; transfer a Git bundle there and push with its credential if needed.
- Keep deployment credentials and runtime `configs/global_config.json` out of Git.
