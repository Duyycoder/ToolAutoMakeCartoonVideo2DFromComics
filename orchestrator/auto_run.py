"""Chuỗi chạy tự động Bước 1→4 (nội bộ: step1 → step2 → step3 → step5).

Lưu ý đánh số: trên UI "Bước 4: Ghép Video" là task nội bộ `step5` (merge);
tab autosub (`step4`) là công cụ rời, KHÔNG nằm trong chuỗi. Chuỗi chạy hoàn
toàn ở backend (thread daemon) nên reload trang không làm gián đoạn; restart
server orchestrator thì chuỗi dừng (chấp nhận ở v1).
"""
import threading
import time
import datetime

# (số nội bộ, nhãn hiển thị) theo đúng sidebar webui
CHAIN_STEPS = [
    (1, "Cào & Dịch"),
    (2, "Sinh Giọng"),
    (3, "Dựng Hoạt Hình"),
    (5, "Ghép Video"),
]
# map số nội bộ -> số hiển thị "Bước X/4" trên UI
DISPLAY_NO = {1: 1, 2: 2, 3: 3, 5: 4}


class AutoRunManager:
    def __init__(self, storage_mgr, process_mgr, pipeline):
        self.storage_mgr = storage_mgr
        self.process_mgr = process_mgr
        self.pipeline = pipeline
        self.poll_interval = 1.0             # giây; test chỉnh nhỏ để chạy nhanh
        self._states: dict[str, dict] = {}   # slug -> state
        self._cancels: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ utils
    def _slug(self, story_name: str) -> str:
        meta = self.storage_mgr.read_story_meta(story_name)
        return meta["story_slug"] if meta else ""

    def is_chain_running(self, slug: str) -> bool:
        with self._lock:
            st = self._states.get(slug)
            return bool(st and st.get("running"))

    def list_running_chains(self) -> list[str]:
        """Trả về danh sách slug của các chuỗi chạy tự động đang hoạt động."""
        with self._lock:
            return sorted([slug for slug, st in self._states.items() if st and st.get("running")])

    def status(self, story_name: str) -> dict:
        slug = self._slug(story_name)
        with self._lock:
            st = self._states.get(slug)
            if not st:
                return {"running": False, "current_step": None, "error": None,
                        "finished": False, "step_label": None, "total_steps": len(CHAIN_STEPS)}
            return dict(st)

    # ------------------------------------------------------------------ API
    def start(self, story_name: str, step1_args: dict | None,
              step2_args: dict, step3_args: dict) -> tuple[bool, str]:
        """step1_args = {"crawl_args": ..., "trans_args": ...}; trả (ok, message)."""
        meta = self.storage_mgr.read_story_meta(story_name)
        if not meta:
            return False, f"Không tìm thấy truyện '{story_name}'."
        slug = meta["story_slug"]

        with self._lock:
            st = self._states.get(slug)
            if st and st.get("running"):
                return False, "Chuỗi tự động đang chạy cho truyện này."

        # Không chen vào khi có bước lẻ đang chạy tay
        for n, _ in CHAIN_STEPS:
            if self.process_mgr.is_running(f"{slug}_step{n}"):
                return False, f"Đang có tiến trình Bước {DISPLAY_NO[n]} chạy — dừng nó trước khi chạy tự động."

        cancel = threading.Event()
        with self._lock:
            self._cancels[slug] = cancel
            self._states[slug] = {
                "running": True,
                "current_step": DISPLAY_NO[1],
                "step_label": CHAIN_STEPS[0][1],
                "total_steps": len(CHAIN_STEPS),
                "error": None,
                "finished": False,
                "started_at": datetime.datetime.now().isoformat(),
                "finished_at": None,
            }

        threading.Thread(
            target=self._run_chain,
            args=(story_name, slug, step1_args, step2_args, step3_args, cancel),
            daemon=True,
        ).start()
        return True, "Đã bắt đầu chuỗi tự động Bước 1→4."

    def stop(self, story_name: str) -> bool:
        slug = self._slug(story_name)
        with self._lock:
            st = self._states.get(slug)
            cancel = self._cancels.get(slug)
        if not st or not st.get("running") or cancel is None:
            return False
        cancel.set()
        # Dừng bước đang chạy (nếu có tiến trình thật); chuỗi sẽ tự thoát
        for n, _ in CHAIN_STEPS:
            self.process_mgr.stop_process(f"{slug}_step{n}")
        return True

    # ------------------------------------------------------------------ chain
    def _set_state(self, slug: str, **kw):
        with self._lock:
            if slug in self._states:
                self._states[slug].update(kw)

    def _finish(self, slug: str, error: str | None):
        self._set_state(slug, running=False, finished=True, error=error,
                        current_step=None, step_label=None,
                        finished_at=datetime.datetime.now().isoformat())

    def _wait_step(self, slug: str, step_no: int, cancel: threading.Event) -> tuple[bool, str]:
        """Chờ task step_no kết thúc. Trả (ok, error_message)."""
        task_key = f"{slug}_step{step_no}"
        while True:
            if cancel.is_set() and not self.process_mgr.is_running(task_key):
                return False, "Đã hủy theo yêu cầu."
            st = self.process_mgr.get_task_status(task_key)
            if st["completed"]:
                if st["exit_code"] == 0:
                    return True, ""
                if cancel.is_set() or self.process_mgr.was_user_stopped(task_key):
                    return False, "Đã hủy theo yêu cầu."
                return False, (f"Bước {DISPLAY_NO[step_no]} thất bại "
                               f"(mã lỗi {st['exit_code']}). Xem log của bước để biết chi tiết.")
            time.sleep(self.poll_interval)

    def _run_chain(self, story_name, slug, step1_args, step2_args, step3_args, cancel):
        starters = {
            1: lambda: self.pipeline.start_step_1_crawl_translate(
                story_name, step1_args["crawl_args"], step1_args["trans_args"]),
            2: lambda: self.pipeline.start_step_2_tts(story_name, step2_args),
            3: lambda: self.pipeline.start_step_3_video(story_name, step3_args),
            5: lambda: self.pipeline.start_step_5_merge(story_name, None),
        }
        try:
            for step_no, label in CHAIN_STEPS:
                if cancel.is_set():
                    self._finish(slug, "Đã hủy theo yêu cầu.")
                    return
                self._set_state(slug, current_step=DISPLAY_NO[step_no], step_label=label)
                try:
                    started = starters[step_no]()
                except ValueError as e:      # vd thiếu API key khi resolve LLM Bước 3
                    self._finish(slug, f"Bước {DISPLAY_NO[step_no]}: {e}")
                    return
                if not started:
                    self._finish(slug, f"Không khởi động được Bước {DISPLAY_NO[step_no]}.")
                    return
                ok, err = self._wait_step(slug, step_no, cancel)
                if not ok:
                    self._finish(slug, err)
                    return
            self._finish(slug, None)
        except Exception as e:
            self._finish(slug, f"Lỗi chuỗi tự động: {e}")
