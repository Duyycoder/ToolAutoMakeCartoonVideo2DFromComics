"""Điều phối 3 tác vụ của công cụ: CÀO video → DỊCH/gắn phụ đề → GHÉP video.

Mọi việc nặng (yt-dlp, Whisper, PaddleOCR, ffmpeg, TTS) chạy trong tiến trình con
dùng `AIVoice/.venv` để tự nhả VRAM khi xong; orchestrator chỉ dựng dòng lệnh, đọc
stdout (mỗi dòng một JSON) rồi đẩy qua SSE.

Hàng đợi nhiều video được nối bằng callback `on_completed` của ProcessManager: mỗi
video là một tiến trình con riêng, cùng một `task_key` nên giao diện chỉ theo dõi
một luồng log duy nhất và nút Dừng vẫn giết đúng tiến trình đang chạy.
"""
import contextlib
import json
import os
import queue
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from orchestrator.config import load_global_config
from orchestrator.llm import resolve_llm
from orchestrator.process_manager import ProcessManager
from orchestrator.storage import VideoLibrary, slugify

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AIVOICE_DIR = os.path.join(REPO_ROOT, "AIVoice")
PYTHON_EXE = os.path.join(AIVOICE_DIR, ".venv", "Scripts", "python.exe")
MC_DIR = os.path.join(AIVOICE_DIR, "apps", "MediaComposer")
DOWNLOAD_ADAPTER = os.path.join(MC_DIR, "adapter_download_cli.py")
AUTOSUB_ADAPTER = os.path.join(MC_DIR, "adapter_autosub_cli.py")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class VideoPipeline:
    def __init__(self, library: VideoLibrary, process_mgr: ProcessManager):
        self.library = library
        self.process_mgr = process_mgr

    # ------------------------------------------------------------------ CÀO
    def build_download_cmd(self, urls: List[str], args: dict, g_config: dict) -> list:
        cmd = [PYTHON_EXE, DOWNLOAD_ADAPTER, "--output-dir", self.library.videos_dir,
               "--platform", args.get("platform") or "generic"]
        for u in urls:
            cmd += ["--url", u]
        if args.get("max_items"):
            cmd += ["--max-items", str(int(args["max_items"]))]
        if args.get("skip_existing", True):
            cmd.append("--skip-existing")
        if args.get("stop_on_error"):
            cmd.append("--stop-on-error")
        cookies = (args.get("cookies_file")
                   or (g_config.get("video") or {}).get("downloader_cookies") or "").strip()
        if cookies:
            cmd += ["--cookies-file", cookies]
        return cmd

    def probe(self, urls: List[str], args: dict, timeout: float = 300.0) -> dict:
        """Giải link thành danh sách video (đồng bộ) để giao diện hiện hàng đợi trước khi tải."""
        g_config = load_global_config()
        cmd = self.build_download_cmd(urls, args, g_config) + ["--probe-only"]
        res = subprocess.run(cmd, cwd=AIVOICE_DIR, capture_output=True, text=True,
                             encoding="utf-8", timeout=timeout, creationflags=NO_WINDOW)
        for line in (res.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("event") == "probe_done":
                return data
        detail = (res.stdout or "")[-800:] or (res.stderr or "")[-800:] or "không có output"
        raise RuntimeError(f"Không đọc được danh sách video từ link đã nhập. Chi tiết: {detail}")

    def start_download(self, task_key: str, urls: List[str], args: dict,
                       then_translate: Optional[dict] = None) -> bool:
        """Tải hàng loạt vào thư viện. `then_translate` != None thì dịch luôn video vừa tải."""
        g_config = load_global_config()
        cmd = self.build_download_cmd(urls, args, g_config)
        known_before = {e["entry_id"] for e in self.library.list_entries()}

        def on_done(exit_code: int):
            new_entries = [e for e in self.library.list_entries()
                           if e["entry_id"] not in known_before]
            self.process_mgr.emit(
                task_key,
                f"[HỆ THỐNG] Tải xong, thư viện có thêm {len(new_entries)} video.")
            if not then_translate:
                self.process_mgr.finish_manual(task_key, exit_code)
                return exit_code == 0
            if self.process_mgr.was_user_stopped(task_key) or not new_entries:
                if not new_entries:
                    self.process_mgr.emit(task_key, "[HỆ THỐNG] Không có video mới để dịch.")
                self.process_mgr.finish_manual(task_key, exit_code)
                return exit_code == 0
            jobs = [self.make_job(e) for e in new_entries]
            self.process_mgr.emit(
                task_key, f"[HỆ THỐNG] Chuyển sang dịch {len(jobs)} video vừa tải.")
            if not self._launch_chain(task_key, jobs, then_translate, reuse_queue=True):
                self.process_mgr.emit(task_key, "[LỖI] Không khởi động được bước dịch.")
                self.process_mgr.finish_manual(task_key, 1)
                return False
            return exit_code == 0

        started = self.process_mgr.start_process(
            task_key=task_key, cmd=cmd, cwd=AIVOICE_DIR,
            on_completed=on_done, close_queue_on_exit=False)
        return started

    def probe_media(self, path: str, timeout: float = 120.0) -> Dict[str, Any]:
        """W/H/thời lượng của một file video. Trả {} nếu không đọc được.

        Chạy qua adapter trong venv AIVoice (chứ không tự đọc) vì orchestrator cố
        ý không có ffmpeg/torch. Lỗi ở đây không được chặn luồng: thiếu thông số
        chỉ làm thư viện hiển thị "—", vẫn dịch được bình thường.
        """
        cmd = [PYTHON_EXE, DOWNLOAD_ADAPTER, "--output-dir", self.library.videos_dir,
               "--probe-file", os.path.abspath(path)]
        try:
            res = subprocess.run(cmd, cwd=AIVOICE_DIR, capture_output=True, text=True,
                                 encoding="utf-8", timeout=timeout, creationflags=NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            return {}
        for line in (res.stdout or "").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("event") == "probe_file_done":
                return {k: data[k] for k in ("width", "height", "duration") if k in data}
        return {}

    # ----------------------------------------------------------------- DỊCH
    def make_job(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Một mục thư viện -> một 'việc' cho adapter autosub."""
        entry_id = entry["entry_id"]
        return {
            "entry_id": entry_id,
            "title": entry.get("title") or entry_id,
            "video_path": entry.get("file") or "",
            "output_dir": self.library.output_dir(entry_id),
            "srt_dir": self.library.subs_dir(entry_id),
        }

    def build_translate_cmd(self, job: dict, args: dict, g_config: dict) -> list:
        video_cfg = g_config.get("video") or {}
        autosub_cfg = g_config.get("autosub") or {}

        llm_engine = args.get("llm_engine") or autosub_cfg.get("llm_engine") or "gemini_api"
        api_key, base_url, model = resolve_llm(
            llm_engine, args, g_config,
            autosub_cfg.get("llm_model") or video_cfg.get("default_llm_model"))

        cmd = [
            PYTHON_EXE, AUTOSUB_ADAPTER,
            "--video-path", job["video_path"],
            "--output-dir", job["output_dir"],
            "--srt-out-dir", job["srt_dir"],
            "--source-lang", args.get("source_lang") or "English",
            "--target-lang", args.get("target_lang") or "Vietnamese",
            "--sub-source", args.get("sub_source") or "whisper",
            "--burn-method", args.get("burn_method") or "ffmpeg",
            "--tts-engine", args.get("tts_engine") or "edge",
            "--tts-voice", args.get("tts_voice") or "",
            "--ducking-ratio", str(args.get("ducking_ratio", 90.0)),
            "--llm-api-key", api_key,
            "--llm-base-url", base_url,
            "--llm-model", model,
        ]

        if (args.get("sub_source") or "") == "import":
            cmd += ["--source-srt", args.get("source_srt") or job.get("source_srt") or ""]
        if args.get("translate_only"):
            cmd.append("--translate-only")
        if args.get("no_translate"):
            cmd.append("--no-translate")
        if args.get("clean_audio"):
            cmd.append("--clean-audio")
        if args.get("enable_voiceover"):
            cmd.append("--enable-voiceover")
        if args.get("auto_clone"):
            cmd.append("--auto-clone")

        crop = (args.get("crop_x", -1), args.get("crop_y", -1),
                args.get("crop_w", -1), args.get("crop_h", -1))
        if crop[0] >= 0 and crop[1] >= 0 and crop[2] > 0 and crop[3] > 0:
            cmd += ["--crop-x", str(crop[0]), "--crop-y", str(crop[1]),
                    "--crop-w", str(crop[2]), "--crop-h", str(crop[3])]

        for flag, key in (("--font-name", "font_name"), ("--font-size", "font_size"),
                          ("--text-color", "text_color"), ("--stroke-color", "stroke_color"),
                          ("--stroke-width", "stroke_width"), ("--bg-style", "bg_style"),
                          ("--bg-color", "bg_color"), ("--bg-alpha", "bg_alpha"),
                          ("--sub-position", "sub_position"),
                          ("--custom-position", "custom_position")):
            value = args.get(key)
            if value not in (None, ""):
                cmd += [flag, str(value)]

        ocr_gpu = args.get("ocr_use_gpu")
        if ocr_gpu is None:
            ocr_gpu = video_cfg.get("ocr_use_gpu", True)
        if ocr_gpu:
            cmd.append("--use-gpu")
        return cmd

    def start_translate(self, task_key: str, jobs: List[dict], args: dict) -> bool:
        """Dịch/gắn phụ đề cho 1..n video, chạy lần lượt trong cùng một luồng log."""
        if not jobs:
            return False
        if not self.process_mgr.register_manual_task(task_key, queue.Queue()):
            return False
        self.process_mgr.emit(
            task_key, f"[HỆ THỐNG] Nhận {len(jobs)} video vào hàng đợi dịch.")
        if not self._launch_chain(task_key, jobs, args, reuse_queue=True):
            self.process_mgr.finish_manual(task_key, 1)
            return False
        return True

    def _launch_chain(self, task_key: str, jobs: List[dict], args: dict,
                      reuse_queue: bool) -> bool:
        """Khởi động video đầu tiên; các video sau được nối trong callback."""
        g_config = load_global_config()
        total = len(jobs)
        state = {"ok": 0, "fail": 0}

        def summary(exit_code: int):
            self.process_mgr.emit(
                task_key,
                f"[HỆ THỐNG] Xong hàng đợi: {state['ok']} thành công, {state['fail']} lỗi "
                f"trên tổng {total} video.")
            self.process_mgr.finish_manual(task_key, exit_code)

        def on_item_done(idx: int, exit_code: int):
            job = jobs[idx]
            if exit_code == 0:
                state["ok"] += 1
                self.process_mgr.emit(task_key, f"[THÀNH CÔNG] ({idx + 1}/{total}) {job['title']}")
            else:
                state["fail"] += 1
                self.process_mgr.emit(
                    task_key,
                    f"[LỖI] ({idx + 1}/{total}) {job['title']} — xem chi tiết phía trên.")

            if self.process_mgr.was_user_stopped(task_key):
                self.process_mgr.emit(task_key, "[HỆ THỐNG] Đã dừng hàng đợi theo yêu cầu.")
                summary(1)
                return False
            nxt = idx + 1
            if nxt >= total:
                summary(0 if state["fail"] == 0 else 1)
                return state["fail"] == 0
            if not launch(nxt):
                self.process_mgr.emit(
                    task_key, f"[LỖI] Không khởi động được tiến trình cho video {nxt + 1}.")
                state["fail"] += 1
                summary(1)
                return False
            return exit_code == 0

        def launch(idx: int) -> bool:
            job = jobs[idx]
            self.process_mgr.emit(
                task_key, f"[HỆ THỐNG] ({idx + 1}/{total}) Đang xử lý: {job['title']}")
            if not job.get("video_path") or not os.path.exists(job["video_path"]):
                self.process_mgr.emit(
                    task_key, f"[LỖI] Không tìm thấy file video: {job.get('video_path')}")
                return False
            os.makedirs(job["output_dir"], exist_ok=True)
            os.makedirs(job["srt_dir"], exist_ok=True)
            cmd = self.build_translate_cmd(job, args, g_config)
            return self.process_mgr.start_process(
                task_key=task_key, cmd=cmd, cwd=AIVOICE_DIR,
                on_completed=lambda code, i=idx: on_item_done(i, code),
                close_queue_on_exit=False, reuse_queue=True)

        return launch(0)

    # ------------------------------------------------------------------ GHÉP
    def start_merge(self, task_key: str, files: List[str], output_name: str = "") -> bool:
        """Ghép danh sách file video đã chọn thành một file trong storage/merged/."""
        files = [f for f in files if f and os.path.exists(f)]
        if not files:
            return False
        q = queue.Queue()
        if not self.process_mgr.register_manual_task(task_key, q):
            return False

        name = slugify(output_name) if output_name else f"ghep_{time.strftime('%Y%m%d_%H%M%S')}"
        out = os.path.join(self.library.merged_dir, name + ".mp4")

        class QueueWriter:
            def write(self, message):
                if message.strip():
                    q.put(message.strip() + "\n")

            def flush(self):
                pass

        def _run():
            ok = False
            try:
                from orchestrator.video_merger import merge_files
                q.put(f"[HỆ THỐNG] Ghép {len(files)} video vào {out}...\n")
                with contextlib.redirect_stdout(QueueWriter()):
                    ok = merge_files(files, out)
                q.put(f"[HỆ THỐNG] Ghép xong: {out}\n" if ok
                      else "[HỆ THỐNG] Ghép thất bại — xem chi tiết phía trên.\n")
            except Exception as e:
                q.put(f"[LỖI] {e}\n")
            finally:
                self.process_mgr.finish_manual(task_key, 0 if ok else 1)

        threading.Thread(target=_run, daemon=True).start()
        return True
