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
from typing import Any, Callable, Dict, List, Optional

from orchestrator import project
from orchestrator.config import load_global_config
from orchestrator.llm import resolve_llm
from orchestrator.process_manager import ProcessManager
from orchestrator.storage import VideoLibrary, batch_order, slugify

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
        # Số thứ tự trong lô đi KÈM từng link (adapter ghép 1-1 theo thứ tự) —
        # có vậy lô lẫn file-trên-máy với link mới ghép đúng thứ tự người dùng sắp.
        indexes = list(args.get("batch_index") or [])
        for i, u in enumerate(urls):
            cmd += ["--url", u]
            cmd += ["--batch-index", str(float(indexes[i] if i < len(indexes) else i + 1))]
        if args.get("batch_id"):
            cmd += ["--batch-id", args["batch_id"]]
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
                       then_translate: Optional[dict] = None,
                       then_merge: Optional[dict] = None) -> bool:
        """Tải hàng loạt vào thư viện, rồi (tuỳ chọn) dịch và ghép luôn.

        Cả chuỗi tải → dịch → ghép chạy dưới MỘT task_key: giao diện chỉ theo dõi
        một luồng log, và chỉ được đóng SSE (`finish_manual`) đúng một lần ở cuối.
        """
        g_config = load_global_config()
        cmd = self.build_download_cmd(urls, args, g_config)
        batch_id = args.get("batch_id") or ""
        known_before = {e["entry_id"] for e in self.library.list_entries()}

        project_folder = args.get("project_folder") or ""

        def on_done(exit_code: int):
            new_entries = [e for e in self.library.list_entries()
                           if e["entry_id"] not in known_before]
            self.process_mgr.emit(
                task_key,
                f"[HỆ THỐNG] Tải xong {len(new_entries)} video.")

            if project_folder:
                try:
                    them = self._dua_ban_tai_vao_du_an(task_key, project_folder,
                                                       new_entries, batch_id)
                except Exception as e:
                    self.process_mgr.emit(task_key, f"[LỖI] Không đưa được video vào dự án: {e}")
                    self.process_mgr.finish_manual(task_key, 1)
                    return False
                self.chain_du_an_sau_lo(task_key, project_folder, batch_id, exit_code,
                                        then_translate, then_merge, them)
                return exit_code == 0

            entries = new_entries
            if then_translate and batch_id:
                entries = self._them_muc_lo_chua_dich(batch_id, new_entries)
            self.chain_after_entries(task_key, entries, exit_code,
                                     then_translate, then_merge, batch_id)
            return exit_code == 0

        started = self.process_mgr.start_process(
            task_key=task_key, cmd=cmd, cwd=AIVOICE_DIR,
            on_completed=on_done, close_queue_on_exit=False)
        return started

    def chain_after_entries(self, task_key: str, entries: List[dict], exit_code: int,
                            then_translate: Optional[dict], then_merge: Optional[dict],
                            batch_id: str) -> None:
        """Đi tiếp sau khi video đã nằm trong thư viện: dịch từng cái rồi ghép cả lô.

        Dùng chung cho hai kiểu đầu vào (tải theo link và nhập file trên máy) để
        chỉ có MỘT chỗ quyết định lúc nào đóng SSE.
        """
        if then_translate and not self.process_mgr.was_user_stopped(task_key):
            if not entries:
                self.process_mgr.emit(task_key, "[HỆ THỐNG] Không có video mới để dịch.")
            else:
                jobs = [self.make_job(e) for e in entries]
                self.process_mgr.emit(
                    task_key, f"[HỆ THỐNG] Chuyển sang dịch {len(jobs)} video.")
                # Chạy trong callback của khúc tải/nhập: để exception (vd thiếu API
                # key) bay ra là không ai đóng SSE — giao diện treo "đang chạy" mãi.
                try:
                    started = self._launch_chain(task_key, jobs, then_translate,
                                                 reuse_queue=True, then_merge=then_merge,
                                                 batch_id=batch_id)
                    loi = ""
                except Exception as e:
                    started, loi = False, f": {e}"
                if started:
                    return
                self.process_mgr.emit(task_key, f"[LỖI] Không khởi động được bước dịch{loi}")
                exit_code = 1
        self._finish_or_merge(task_key, exit_code, then_merge, batch_id)

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

    # ------------------------------------------------------------------ NHẬP
    def start_import(self, task_key: str, items: List[dict], copy_file: bool = False,
                     batch_id: str = "",
                     then: Optional[Callable[[int, List[dict]], None]] = None) -> bool:
        """Nhập nhiều video có sẵn trên máy vào thư viện, giữ nguyên thứ tự đã sắp.

        Chạy nền kèm log SSE chứ không làm thẳng trong request: đọc W/H mỗi file
        là một tiến trình con (~vài giây), nhập 50 file kiểu đồng bộ là giao diện
        đứng hình vài phút mà không biết đang tới đâu.

        `then(exit_code, entries)` != None thì nó chịu trách nhiệm đóng SSE (dùng
        khi nối tiếp sang dịch/ghép); ngược lại hàm này tự `finish_manual`.
        """
        if not items:
            return False
        if not self.process_mgr.register_manual_task(task_key, queue.Queue()):
            return False

        total = len(items)

        def _run():
            ok = fail = 0
            entries: List[dict] = []
            self.process_mgr.emit(task_key, f"[HỆ THỐNG] Nhận {total} file vào thư viện.")
            try:
                for i, item in enumerate(items):
                    if self.process_mgr.was_user_stopped(task_key):
                        self.process_mgr.emit(task_key, "[HỆ THỐNG] Đã dừng theo yêu cầu.")
                        break
                    path = (item.get("path") or "").strip()
                    name = os.path.basename(path) or path or "(trống)"
                    self.process_mgr.emit(task_key, f"[HỆ THỐNG] ({i + 1}/{total}) Đang đọc: {name}")
                    try:
                        entry = self.library.register_local(
                            path, item.get("title") or "", copy_file,
                            batch_id=batch_id,
                            batch_index=float(item.get("index") or (i + 1)))
                    except (FileNotFoundError, ValueError, OSError) as e:
                        fail += 1
                        self.process_mgr.emit(task_key, f"[LỖI] ({i + 1}/{total}) {name}: {e}")
                        continue
                    # Thiếu W/H chỉ làm thư viện hiện "—"; vẫn dịch/ghép được
                    # nên không để nó giết cả lượt nhập.
                    meta = self.probe_media(entry["file"])
                    if meta:
                        entry.update(meta)
                        self.library.write_entry(entry["entry_id"], entry)
                        entry = self.library.read_entry(entry["entry_id"])
                    else:
                        self.process_mgr.emit(
                            task_key, f"[HỆ THỐNG] Không đọc được thông số của {name} — vẫn nhập.")
                    entries.append(entry)
                    ok += 1
                    self.process_mgr.emit(
                        task_key, f"[THÀNH CÔNG] ({i + 1}/{total}) {entry.get('title')}")
            except Exception as e:  # không để SSE treo vĩnh viễn vì một lỗi lạ
                fail += 1
                self.process_mgr.emit(task_key, f"[LỖI] Nhập hàng loạt hỏng giữa chừng: {e}")
            self.process_mgr.emit(
                task_key,
                f"[HỆ THỐNG] Nhập xong: {ok} thành công, {fail} lỗi trên tổng {total} file.")
            code = 0 if (ok and not fail) else 1
            if then:
                then(code, entries)
            else:
                self.process_mgr.finish_manual(task_key, code)

        threading.Thread(target=_run, daemon=True).start()
        return True

    def start_import_project(self, task_key: str, folder: str, items: List[dict],
                             batch_id: str,
                             then: Optional[Callable[[int], None]] = None) -> bool:
        """Chép video trên máy vào MỘT dự án, đánh số nối tiếp theo thứ tự hàng đợi.

        Luôn CHÉP (không chuyển): file gốc nằm ngoài dự án là của người dùng. Chạy
        nền kèm SSE vì chép video lớn có thể mất cả phút. `then(exit_code)` != None
        thì nó chịu trách nhiệm đóng SSE, không thì hàm này tự `finish_manual`.
        """
        if not items:
            return False
        if not self.process_mgr.register_manual_task(task_key, queue.Queue()):
            return False
        total = len(items)
        ten = (project.doc(folder) or {}).get("name") or os.path.basename(folder)

        def _run():
            ok = fail = 0
            self.process_mgr.emit(task_key, f"[HỆ THỐNG] Chép {total} file vào dự án '{ten}'.")
            try:
                for i, item in enumerate(items):
                    if self.process_mgr.was_user_stopped(task_key):
                        self.process_mgr.emit(task_key, "[HỆ THỐNG] Đã dừng theo yêu cầu.")
                        break
                    path = (item.get("path") or "").strip()
                    name = os.path.basename(path) or path or "(trống)"
                    try:
                        video = project.them_video(
                            folder, path, item.get("title") or "", chep=True,
                            batch_id=batch_id, batch_index=float(item.get("index") or (i + 1)))
                    except (ValueError, OSError) as e:
                        fail += 1
                        self.process_mgr.emit(task_key, f"[LỖI] ({i + 1}/{total}) {name}: {e}")
                        continue
                    ok += 1
                    self.process_mgr.emit(
                        task_key, f"[THÀNH CÔNG] ({i + 1}/{total}) {name} → {video['file']}")
            except Exception as e:  # không để SSE treo vĩnh viễn vì một lỗi lạ
                fail += 1
                self.process_mgr.emit(task_key, f"[LỖI] Chép vào dự án hỏng giữa chừng: {e}")
            self.process_mgr.emit(
                task_key, f"[HỆ THỐNG] Chép xong: {ok} thành công, {fail} lỗi trên tổng {total} file.")
            code = 0 if (ok and not fail) else 1
            if then:
                then(code)
            else:
                self.process_mgr.finish_manual(task_key, code)

        threading.Thread(target=_run, daemon=True).start()
        return True

    def _dua_ban_tai_vao_du_an(self, task_key: str, folder: str, entries: List[dict],
                               batch_id: str) -> List[str]:
        """Chuyển video vừa tải (đang nằm tạm trong thư viện) vào dự án.

        Adapter tải chỉ biết ghi vào thư viện; thay vì sửa adapter, tải xong thì
        chuyển file sang dự án theo đúng thứ tự hàng đợi rồi xoá mục tạm — để
        lại là thư viện chung hiện một đống mục trỏ vào file đã đi mất.
        """
        them = []
        for entry in sorted(entries, key=batch_order):
            try:
                video = project.them_video(
                    folder, entry.get("file") or "", entry.get("title") or "", chep=False,
                    batch_id=batch_id, batch_index=batch_order(entry))
            except (ValueError, OSError) as e:
                self.process_mgr.emit(
                    task_key, f"[LỖI] Không đưa được '{entry.get('title')}' vào dự án: {e}")
                continue
            self.library.delete_entry(entry["entry_id"], delete_source_file=False)
            them.append(video["file"])
            self.process_mgr.emit(task_key, f"[HỆ THỐNG] Vào dự án: {video['file']}")
        return them

    def chain_du_an_sau_lo(self, task_key: str, folder: str, batch_id: str,
                           exit_code: int, then_translate: Optional[dict],
                           then_merge: Optional[dict], them: Optional[List[str]] = None) -> None:
        """Khúc cuối của một lô đổ vào dự án: sub → ghép → đánh dấu, đúng thứ tự hàng đợi.

        Lấy video theo `batch_id` chứ không chỉ theo khúc cuối: lô trộn (file trên
        máy + link) chạy thành HAI khúc, video của khúc nhập phải được sub cùng.
        Video đã có bản sub (chạy lại lô) thì không sub lại, nhưng vẫn được ghép.
        Mọi nhánh đều kết thúc qua `_ket_thuc_du_an` — chốt đóng SSE duy nhất.
        """
        try:
            da_ghep = {v["file"] for v in project.danh_sach_video(folder, ke_ca_da_ghep=True)
                       if v.get("merged_into")}
            lo = project.video_theo_lo(folder, batch_id) if batch_id else []
            files = [f for f in (lo or them or []) if f not in da_ghep]
            can_sub = [f for f in files
                       if not os.path.exists(project.duong_dan_da_sub(folder, f))]
            dung = self.process_mgr.was_user_stopped(task_key)
            if then_translate and can_sub and not dung:
                self.process_mgr.emit(
                    task_key, f"[HỆ THỐNG] Chuyển sang sub {len(can_sub)} video của dự án.")
                jobs = [self.make_project_job(folder, f) for f in can_sub]
                try:
                    if self._launch_chain(
                            task_key, jobs, then_translate, reuse_queue=True,
                            on_finish=lambda code: self._ket_thuc_du_an(
                                task_key, folder, files, code, then_translate, then_merge)):
                        return
                    loi = ""
                except Exception as e:
                    loi = f": {e}"
                self.process_mgr.emit(task_key, f"[LỖI] Không khởi động được bước sub{loi}")
                exit_code = 1
            self._ket_thuc_du_an(task_key, folder, files, exit_code,
                                 then_translate or {}, then_merge)
        except Exception as e:
            self.process_mgr.emit(task_key, f"[LỖI] Khúc cuối của lô hỏng: {e}")
            self.process_mgr.finish_manual(task_key, 1)

    def _them_muc_lo_chua_dich(self, batch_id: str, entries: List[dict]) -> List[dict]:
        """Video cần dịch ở khúc cuối của một lô trong thư viện chung.

        Lô trộn chạy thành hai khúc (nhập file → tải link) và chỉ khúc CUỐI mang
        phần dịch. Trước đây khúc tải chỉ dịch video vừa tải: file nhập ở khúc
        trước bị bỏ qua mà vẫn bị đem ghép (rơi về bản gốc không phụ đề). Giờ gom
        thêm các mục cùng lô chưa có bản dịch, theo đúng thứ tự lô.
        """
        co_roi = {e["entry_id"] for e in entries}
        them = [e for e in self.library.list_batch(batch_id)
                if e["entry_id"] not in co_roi and not e.get("outputs")]
        return sorted(list(entries) + them, key=batch_order)

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

    @staticmethod
    def make_project_job(folder: str, file: str) -> Dict[str, Any]:
        """Một video trong thư mục dự án -> một 'việc' cho adapter autosub.

        Mọi đầu ra nằm ngay trong dự án (quyết định đã chốt): phụ đề vào
        `phu_de/`, bản đã sub vào `da_sub/`.
        """
        folder = os.path.abspath(folder)
        ten = os.path.basename(file)
        return {
            "title": ten,
            "video_path": os.path.join(folder, ten),
            "output_dir": os.path.join(folder, project.OUT_DIR),
            "srt_dir": os.path.join(folder, project.SUB_DIR),
            "project_folder": folder,
        }

    def _chot_ban_da_sub(self, task_key: str, job: dict) -> None:
        """Đổi bản adapter vừa xuất (`<tên>_autosub_<giờ>.mp4`) về `da_sub/<tên>.mp4`.

        Chỉ nhận file sinh ra SAU lúc bắt đầu việc này — bản cũ từ lượt trước
        không được đội tên bản mới. Không có file nào (chế độ chỉ xuất .srt)
        thì thôi, không phải lỗi.
        """
        stem = os.path.splitext(os.path.basename(job["video_path"]))[0]
        out_dir = job["output_dir"]
        moc = job.get("_bat_dau", 0) - 2
        try:
            ung_vien = [os.path.join(out_dir, f) for f in os.listdir(out_dir)
                        if f.startswith(stem + "_autosub_") and f.lower().endswith(".mp4")]
        except OSError:
            return
        ung_vien = [p for p in ung_vien if os.path.getmtime(p) >= moc]
        if not ung_vien:
            return
        moi_nhat = max(ung_vien, key=os.path.getmtime)
        dich = project.duong_dan_da_sub(job["project_folder"], job["video_path"])
        try:
            os.replace(moi_nhat, dich)
            self.process_mgr.emit(
                task_key, f"[HỆ THỐNG] Bản đã sub: {project.OUT_DIR}/{os.path.basename(dich)}")
        except OSError as e:
            self.process_mgr.emit(
                task_key, f"[CẢNH BÁO] Không đổi tên được bản đã sub ({e}) — "
                          f"giữ nguyên {os.path.basename(moi_nhat)}.")

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
        # OCR đọc N khung/giây (mặc định 10) + cỡ model — trước 29/09 đọc 30 khung/s, 1 phút video mất ~220 s.
        ocr_fps = args.get("ocr_fps") or video_cfg.get("ocr_fps")
        if ocr_fps:
            cmd += ["--ocr-fps", str(ocr_fps)]
        ocr_model = args.get("ocr_model") or video_cfg.get("ocr_model")
        if ocr_model:
            cmd += ["--ocr-model", str(ocr_model)]
        return cmd

    def start_translate(self, task_key: str, jobs: List[dict], args: dict) -> bool:
        """Dịch/gắn phụ đề cho 1..n video, chạy lần lượt trong cùng một luồng log."""
        if not jobs:
            return False
        if not self.process_mgr.register_manual_task(task_key, queue.Queue()):
            return False
        self.process_mgr.emit(
            task_key, f"[HỆ THỐNG] Nhận {len(jobs)} video vào hàng đợi dịch.")
        return self._start_chain_or_release(task_key, jobs, args)

    def start_translate_project(self, task_key: str, folder: str, files: List[str],
                                args: dict, merge_opts: Optional[dict] = None) -> bool:
        """Chạy video của MỘT dự án theo đúng thứ tự đã sắp: sub từng video →
        (tuỳ chọn) ghép theo đúng thứ tự đó → đánh dấu các video đã ghép.

        Cả chuỗi chung một task_key với tab Dịch nên nút Dừng và khung log dùng
        lại được nguyên vẹn.
        """
        jobs = [self.make_project_job(folder, f) for f in files]
        if not jobs:
            return False
        if not self.process_mgr.register_manual_task(task_key, queue.Queue()):
            return False
        ten = (project.doc(folder) or {}).get("name") or os.path.basename(folder)
        self.process_mgr.emit(
            task_key, f"[HỆ THỐNG] Dự án '{ten}': {len(jobs)} video, xử lý theo đúng thứ tự đã sắp.")
        return self._start_chain_or_release(
            task_key, jobs, args,
            on_finish=lambda code: self._ket_thuc_du_an(
                task_key, folder, files, code, args, merge_opts))

    def _start_chain_or_release(self, task_key: str, jobs: List[dict], args: dict,
                                on_finish: Optional[Callable[[int], None]] = None) -> bool:
        """Khởi động chuỗi; hỏng ngay từ đầu thì NHẢ task đã đăng ký.

        `build_translate_cmd` ném ValueError khi engine LLM thiếu API key. Không
        nhả task ở đây thì nó kẹt ở trạng thái "đang chạy" mãi: mọi lần bấm dịch
        sau đó đều bị từ chối "Tác vụ dịch đang chạy" dù chẳng có gì chạy.
        """
        try:
            started = self._launch_chain(task_key, jobs, args, reuse_queue=True,
                                         on_finish=on_finish)
        except Exception:
            self.process_mgr.finish_manual(task_key, 1)
            raise
        if not started:
            self.process_mgr.finish_manual(task_key, 1)
        return started

    def _ket_thuc_du_an(self, task_key: str, folder: str, files: List[str],
                        exit_code: int, args: dict, merge_opts: Optional[dict]) -> None:
        """Khúc cuối chuỗi dự án: ghép theo thứ tự rồi đánh dấu — hoặc đóng SSE.

        Chốt chặn DUY NHẤT gọi `finish_manual` cho chuỗi dự án (trực tiếp, hoặc
        qua `_merge_in_thread`): gọi hai lần là giao diện mất log của khúc sau.
        """
        emit = lambda msg: self.process_mgr.emit(task_key, msg)  # noqa: E731
        try:
            if not merge_opts or not merge_opts.get("enabled"):
                self.process_mgr.finish_manual(task_key, exit_code)
                return
            if self.process_mgr.was_user_stopped(task_key):
                self.process_mgr.finish_manual(task_key, exit_code)
                return
            if exit_code != 0:
                # Ghép lẫn bản đã sub với bản gốc (của video lỗi) rồi đánh dấu
                # "đã ghép" là giấu mất video lỗi khỏi danh sách — tệ hơn không ghép.
                emit("[HỆ THỐNG] Có video xử lý lỗi — BỎ QUA bước ghép để khỏi ra bản "
                     "thiếu phụ đề. Sửa lỗi rồi chạy lại các video đó.")
                self.process_mgr.finish_manual(task_key, exit_code)
                return
            prefer = merge_opts.get("prefer") or "output"
            if args.get("translate_only") and prefer != "source":
                emit("[HỆ THỐNG] Chế độ chỉ xuất .srt không tạo bản đã sub — bỏ qua bước ghép.")
                self.process_mgr.finish_manual(task_key, exit_code)
                return

            ghep, thieu = project.file_de_ghep(folder, files, prefer)
            for ten in thieu:
                emit(f"[BỎ QUA] {ten} — không còn file để ghép.")
            if len(ghep) < 2:
                emit("[HỆ THỐNG] Cần ít nhất 2 video để ghép — bỏ qua bước ghép.")
                self.process_mgr.finish_manual(task_key, exit_code)
                return

            from orchestrator.video_merger import probe_sizes
            paths = [g["path"] for g in ghep]
            sizes = probe_sizes(paths) or None
            out = project.duong_dan_ban_ghep(folder, merge_opts.get("output_name") or "")
            emit(f"[HỆ THỐNG] Ghép {len(paths)} video của dự án theo đúng thứ tự đã sắp"
                 + (" (bản đã gắn phụ đề)." if prefer != "source" else " (bản gốc)."))

            def danh_dau():
                project.danh_dau_da_ghep(folder, [g["file"] for g in ghep], out)
                emit(f"[HỆ THỐNG] Đã đánh dấu {len(ghep)} video là đã ghép vào "
                     f"{project.MERGE_DIR}/{os.path.basename(out)}.")

            self._merge_in_thread(task_key, paths, out, sizes,
                                  "auto" if merge_opts.get("normalize", True) else "never",
                                  exit_code, on_success=danh_dau)
        except Exception as e:
            emit(f"[LỖI] Không ghép được dự án: {e}")
            self.process_mgr.finish_manual(task_key, 1)

    def _launch_chain(self, task_key: str, jobs: List[dict], args: dict,
                      reuse_queue: bool, then_merge: Optional[dict] = None,
                      batch_id: str = "",
                      on_finish: Optional[Callable[[int], None]] = None) -> bool:
        """Khởi động video đầu tiên; các video sau được nối trong callback.

        `on_finish(exit_code)` thay cho `_finish_or_merge` khi chuỗi có khúc
        cuối riêng (chuỗi dự án) — bên đó chịu trách nhiệm đóng SSE.
        """
        g_config = load_global_config()
        total = len(jobs)
        state = {"ok": 0, "fail": 0}

        def summary(exit_code: int):
            self.process_mgr.emit(
                task_key,
                f"[HỆ THỐNG] Xong hàng đợi: {state['ok']} thành công, {state['fail']} lỗi "
                f"trên tổng {total} video.")
            if on_finish is not None:
                on_finish(exit_code)
            else:
                self._finish_or_merge(task_key, exit_code, then_merge, batch_id)

        def on_item_done(idx: int, exit_code: int):
            job = jobs[idx]
            if exit_code == 0:
                state["ok"] += 1
                if job.get("project_folder"):
                    self._chot_ban_da_sub(task_key, job)
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
            job["_bat_dau"] = time.time()
            return self.process_mgr.start_process(
                task_key=task_key, cmd=cmd, cwd=AIVOICE_DIR,
                on_completed=lambda code, i=idx: on_item_done(i, code),
                close_queue_on_exit=False, reuse_queue=True)

        return launch(0)

    # ------------------------------------------------------------------ GHÉP
    def merged_path(self, output_name: str = "") -> str:
        name = slugify(output_name) if output_name else f"ghep_{time.strftime('%Y%m%d_%H%M%S')}"
        return os.path.join(self.library.merged_dir, name + ".mp4")

    def start_merge(self, task_key: str, files: List[str], output_name: str = "",
                    sizes: Optional[List[tuple]] = None, normalize: str = "auto") -> bool:
        """Ghép danh sách file video đã chọn thành một file trong storage/merged/."""
        files = [f for f in files if f and os.path.exists(f)]
        if not files:
            return False
        if not self.process_mgr.register_manual_task(task_key, queue.Queue()):
            return False
        self._merge_in_thread(task_key, files, self.merged_path(output_name), sizes, normalize)
        return True

    def start_merge_batch(self, task_key: str, batch_id: str, opts: dict,
                          prev_code: int = 0) -> bool:
        """Ghép mọi video của một lô theo đúng `batch_index`.

        Dùng cho khúc cuối của chuỗi tải → dịch → ghép nên KHÔNG mở task mới
        (cả chuỗi chung một task_key) và tự đóng SSE khi xong. Trả False khi
        không đủ video để ghép — lúc đó bên gọi phải tự đóng SSE.
        """
        prefer = opts.get("prefer") or "output"
        files, sizes = [], []
        for entry in self.library.list_batch(batch_id):
            path = ""
            if prefer != "source":
                outputs = entry.get("outputs") or []
                if outputs:
                    # Bản mới nhất, không phải bản đầu bảng chữ cái.
                    path = max(outputs, key=lambda o: o.get("mtime", ""))["path"]
            path = path or (entry.get("file") or "")
            if not path or not os.path.exists(path):
                self.process_mgr.emit(
                    task_key, f"[BỎ QUA] {entry.get('title')} — không còn file để ghép.")
                continue
            files.append(path)
            sizes.append((entry.get("width") or 0, entry.get("height") or 0))

        if len(files) < 2:
            self.process_mgr.emit(
                task_key, "[HỆ THỐNG] Không đủ video trong lô để ghép (cần ít nhất 2).")
            return False

        self.process_mgr.emit(
            task_key,
            f"[HỆ THỐNG] Ghép {len(files)} video của lô theo đúng thứ tự đã sắp"
            + (" (bản đã gắn phụ đề)." if prefer != "source" else " (bản gốc)."))
        self._merge_in_thread(task_key, files, self.merged_path(opts.get("output_name") or ""),
                              sizes, "auto" if opts.get("normalize", True) else "never",
                              prev_code)
        return True

    def _finish_or_merge(self, task_key: str, exit_code: int,
                         then_merge: Optional[dict], batch_id: str) -> None:
        """Đóng SSE — hoặc chạy nốt khúc ghép rồi mới đóng.

        Chốt chặn duy nhất bảo đảm `finish_manual` được gọi ĐÚNG MỘT LẦN cho cả
        chuỗi; gọi hai lần là giao diện mất sạch log của khúc sau.
        """
        if (then_merge and batch_id
                and not self.process_mgr.was_user_stopped(task_key)
                and self.start_merge_batch(task_key, batch_id, then_merge, exit_code)):
            return
        self.process_mgr.finish_manual(task_key, exit_code)

    def _merge_in_thread(self, task_key: str, files: List[str], out: str,
                         sizes: Optional[List[tuple]] = None, normalize: str = "auto",
                         prev_code: int = 0,
                         on_success: Optional[Callable[[], None]] = None) -> None:
        """Chạy ffmpeg ở thread riêng, đẩy mọi dòng in của video_merger vào log SSE.

        `on_success()` chỉ chạy khi ghép THÀNH CÔNG, trước khi đóng SSE — dùng để
        ghi nhận kết quả (vd đánh dấu video dự án đã ghép).
        """
        process_mgr = self.process_mgr
        tasks_dir = self.library.tasks_dir

        class TaskWriter:
            def write(self, message):
                if message.strip():
                    process_mgr.emit(task_key, message.strip())

            def flush(self):
                pass

        def _run():
            ok = False
            try:
                from orchestrator.video_merger import merge_files
                process_mgr.emit(task_key, f"[HỆ THỐNG] Ghép {len(files)} video vào {out}...")
                with contextlib.redirect_stdout(TaskWriter()):
                    ok = merge_files(files, out, sizes=sizes, normalize=normalize,
                                     work_dir=tasks_dir)
                process_mgr.emit(task_key, f"[HỆ THỐNG] Ghép xong: {out}" if ok
                                 else "[HỆ THỐNG] Ghép thất bại — xem chi tiết phía trên.")
                if ok and on_success is not None:
                    try:
                        on_success()
                    except Exception as e:
                        process_mgr.emit(
                            task_key, f"[LỖI] Ghép xong nhưng không ghi nhận được kết quả: {e}")
            except Exception as e:
                process_mgr.emit(task_key, f"[LỖI] {e}")
            finally:
                # Ghép xong mà khúc trước có video lỗi thì cả lượt vẫn tính là lỗi.
                process_mgr.finish_manual(task_key, prev_code if ok else 1)

        threading.Thread(target=_run, daemon=True).start()
