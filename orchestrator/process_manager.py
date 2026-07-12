import os
import sys
import subprocess
import threading
import queue
import time
from typing import Dict, Any, Optional, Callable

class ProcessManager:
    def __init__(self):
        self.active_processes: Dict[str, subprocess.Popen] = {}
        self.log_queues: Dict[str, queue.Queue] = {}
        self._lock = threading.Lock()

    def start_process(self, task_key: str, cmd: list, cwd: str, env_override: Optional[dict] = None, on_completed: Optional[Callable[[int], None]] = None, close_queue_on_exit: bool = True, reuse_queue: bool = False) -> bool:
        """Starts a subprocess in the background and sets up non-blocking log capture."""
        with self._lock:
            if task_key in self.active_processes:
                # Process is already running
                return False

            if reuse_queue and task_key in self.log_queues:
                log_queue = self.log_queues[task_key]
            else:
                log_queue = queue.Queue()
                self.log_queues[task_key] = log_queue

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
                if close_queue_on_exit:
                    q.put(None) # Sentinel to mark end of logs
                
                with self._lock:
                    if task_key in self.active_processes:
                        del self.active_processes[task_key]
                
                if on_completed:
                    try:
                        on_completed(exit_code)
                    except Exception:
                        pass

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
            proc = self.active_processes.get(task_key)
            if not proc:
                return False
            # Check if process has terminated (poll returns exit code)
            if proc.poll() is not None:
                del self.active_processes[task_key]
                return False
            return True

    def get_logs_generator(self, task_key: str):
        """Returns a generator that yields log lines as they arrive (ideal for Server-Sent Events)."""
        q = self.log_queues.get(task_key)
        if not q:
            yield "data: [SYSTEM] No active log queue found for this task.\n\n"
            return

        while True:
            try:
                # Wait with timeout to allow checking if process ended or checking connection
                line = q.get(timeout=1.0)
                if line is None:
                    # End of process logs
                    yield "data: [SYSTEM] Process completed.\n\n"
                    break
                # Yield formatted as SSE event
                yield f"data: {line.strip()}\n\n"
            except queue.Empty:
                # Keep-alive signal for SSE
                yield "data: [PING]\n\n"
            except Exception as e:
                yield f"data: [SYSTEM ERROR] Log generation error: {e}\n\n"
                break
