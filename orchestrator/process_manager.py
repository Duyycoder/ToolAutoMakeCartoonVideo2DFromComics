import os
import subprocess
import threading
import queue
from typing import Dict, Optional, Callable

class ProcessManager:
    def __init__(self):
        self.active_processes: Dict[str, subprocess.Popen] = {}
        self.log_queues: Dict[str, queue.Queue] = {}
        self.completed_exit_codes: Dict[str, int] = {}
        self.finalizing_tasks: Dict[str, int] = {}
        self.manual_running_tasks: set[str] = set()
        self._lock = threading.Lock()

    def start_process(self, task_key: str, cmd: list, cwd: str, env_override: Optional[dict] = None, on_completed: Optional[Callable[[int], None]] = None, close_queue_on_exit: bool = True, reuse_queue: bool = False) -> bool:
        """Starts a subprocess in the background and sets up non-blocking log capture."""
        with self._lock:
            if (task_key in self.active_processes
                    or (task_key in self.manual_running_tasks and not reuse_queue)
                    or (self.finalizing_tasks.get(task_key, 0) and not reuse_queue)):
                # Process is already running
                return False

            if reuse_queue and task_key in self.log_queues:
                log_queue = self.log_queues[task_key]
            else:
                log_queue = queue.Queue()
                self.log_queues[task_key] = log_queue
            self.completed_exit_codes.pop(task_key, None)

            # Windows-specific: run without showing console window if desired,
            # but keep it standard so subprocess.Popen works cleanly.
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                if env_override:
                    env.update(env_override)
                
                # Run the process
                proc = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, # Redirect stderr to stdout to capture everything in order
                    text=True,
                    encoding="utf-8",
                    env=env,
                    bufsize=1 # Line buffered
                )
                self.active_processes[task_key] = proc
                self.manual_running_tasks.discard(task_key)
            except Exception as e:
                log_queue.put(f"[ERROR] Failed to start process: {e}\n")
                return False

        # Thread to read stdout line-by-line and push to the queue
        def reader_thread(process: subprocess.Popen, q: queue.Queue):
            try:
                for line in iter(process.stdout.readline, ''):
                    if line:
                        q.put(line)
            except Exception as ex:
                q.put(f"[ERROR] Log reader thread exception: {ex}\n")
            finally:
                process.stdout.close()
                exit_code = process.wait()

                # Xóa active trước callback để callback có thể chain process mới
                # cùng task_key/reuse_queue (luồng crawl -> translate).
                with self._lock:
                    # Chỉ reader sở hữu đúng process này mới được nhả slot.
                    # Nếu một lệnh mới đã được đăng ký trong khe thời gian rất
                    # nhỏ sau khi child exit, reader cũ không được xóa nhầm nó.
                    if self.active_processes.get(task_key) is process:
                        del self.active_processes[task_key]
                    if on_completed:
                        self.finalizing_tasks[task_key] = (
                            self.finalizing_tasks.get(task_key, 0) + 1)

                # Callback hậu xử lý (vd merge video) phải hoàn tất và ghi log
                # TRƯỚC sentinel; nếu không SSE sẽ báo xong quá sớm.
                final_exit_code = exit_code
                callback_failed = False
                if on_completed:
                    try:
                        callback_result = on_completed(exit_code)
                        if callback_result is False and final_exit_code == 0:
                            final_exit_code = 1
                    except Exception as e:
                        callback_failed = True
                        q.put(f"[Orchestrator] callback on_completed failed: {e}\n")
                        if final_exit_code == 0:
                            final_exit_code = 1

                with self._lock:
                    count = self.finalizing_tasks.get(task_key, 0)
                    if count <= 1:
                        self.finalizing_tasks.pop(task_key, None)
                    else:
                        self.finalizing_tasks[task_key] = count - 1
                    if close_queue_on_exit or callback_failed:
                        self.completed_exit_codes[task_key] = final_exit_code
                if close_queue_on_exit or callback_failed:
                    q.put(None)  # Sentinel chỉ được đặt sau callback.

        t = threading.Thread(target=reader_thread, args=(proc, log_queue), daemon=True)
        t.start()
        return True

    def stop_process(self, task_key: str) -> bool:
        """Terminates an active subprocess."""
        with self._lock:
            proc = self.active_processes.get(task_key)
            if not proc:
                return False
            
            try:
                proc.terminate()
                # Wait up to 3 seconds for graceful shutdown, then force kill
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return True
            except Exception:
                return False

    def is_running(self, task_key: str) -> bool:
        with self._lock:
            if (self.finalizing_tasks.get(task_key, 0)
                    or task_key in self.manual_running_tasks):
                return True
            proc = self.active_processes.get(task_key)
            if not proc:
                return False
            # Reader vẫn sở hữu task cho tới khi thu log, wait và callback xong.
            # Kể cả poll() vừa thấy child exit, trả False ở đây sẽ mở race cho
            # một process mới chen vào trước khi reader cũ dọn bookkeeping.
            return True

    def register_manual_task(self, task_key: str, log_queue: queue.Queue) -> bool:
        """Đăng ký task chạy bằng thread thay vì subprocess (vd Bước 5)."""
        with self._lock:
            if (task_key in self.active_processes
                    or self.finalizing_tasks.get(task_key, 0)
                    or task_key in self.manual_running_tasks):
                return False
            self.log_queues[task_key] = log_queue
            self.manual_running_tasks.add(task_key)
            self.completed_exit_codes.pop(task_key, None)
            return True

    def mark_completed(self, task_key: str, exit_code: int) -> None:
        """Ghi terminal state cho task manual/callback tự quản lý sentinel."""
        with self._lock:
            self.manual_running_tasks.discard(task_key)
            self.completed_exit_codes[task_key] = int(exit_code)

    def get_task_status(self, task_key: str) -> dict:
        """Trạng thái nhỏ gọn cho frontend phân biệt SSE rớt và task đã xong."""
        with self._lock:
            proc = self.active_processes.get(task_key)
            running = bool(
                proc is not None
                or self.finalizing_tasks.get(task_key, 0) > 0
                or task_key in self.manual_running_tasks
            )
            exit_code = self.completed_exit_codes.get(task_key)
            return {
                "task_key": task_key,
                "running": running,
                "completed": exit_code is not None,
                "exit_code": exit_code,
                "has_log_queue": task_key in self.log_queues,
            }

    @staticmethod
    def _sse_data(payload) -> str:
        """Mỗi dòng SSE phải có prefix data:, kể cả log nhiều dòng/dict cũ."""
        if isinstance(payload, dict):
            payload = payload.get("line", str(payload))
        text = str(payload).strip("\r\n")
        lines = text.splitlines() or [""]
        return "".join(f"data: {line}\n" for line in lines) + "\n"

    def _completed_event(self, task_key: str) -> str:
        exit_code = self.get_task_status(task_key).get("exit_code")
        suffix = "" if exit_code is None else f" (exit_code={exit_code})"
        return self._sse_data(f"[SYSTEM] Process completed{suffix}.")

    def get_logs_generator(self, task_key: str):
        """Returns a generator that yields log lines as they arrive (ideal for Server-Sent Events)."""
        q = self.log_queues.get(task_key)
        if q is None:
            if self.get_task_status(task_key)["completed"]:
                yield self._completed_event(task_key)
                return
            yield "data: [SYSTEM] No active log queue found for this task.\n\n"
            return

        while True:
            try:
                # Sentinel có thể đã được một kết nối cũ consume. Completion
                # record giúp reconnect kết thúc ngay thay vì PING vô hạn.
                if q.empty() and self.get_task_status(task_key)["completed"]:
                    yield self._completed_event(task_key)
                    break
                # Wait with timeout to allow checking if process ended or checking connection
                line = q.get(timeout=1.0)
                if line is None:
                    # End of process logs
                    yield self._completed_event(task_key)
                    break
                # Yield formatted as SSE event
                yield self._sse_data(line)
            except queue.Empty:
                # Keep-alive signal for SSE
                yield "data: [PING]\n\n"
            except Exception as e:
                yield f"data: [SYSTEM ERROR] Log generation error: {e}\n\n"
                break
