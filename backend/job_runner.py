"""Hàng đợi job AI: chạy worker trong subprocess (.venv-ai), mỗi lần 1 job (GPU chỉ có 6 GB).

- Worker in JSON từng dòng ra stdout (progress/done/error) -> lưu vào job.events cho SSE.
- Thiếu VRAM (CUDA_OOM) hoặc crash native -> tự chạy lại ở mức chất lượng nhẹ hơn.
- Trước mỗi job gọi `before_gpu_job` (unload Ollama) để nhả VRAM.
"""
import json
import os
import queue
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
QUALITY_ORDER = ("detailed", "balanced", "fast")  # nặng -> nhẹ
RETRYABLE_PREFIXES = ("CUDA_OOM", "EXIT_")
FRIENDLY_ERRORS = {
    "CUDA_OOM": "GPU không đủ bộ nhớ. Hãy đóng bớt game/trình duyệt rồi thử mức \"Nhanh\".",
    "CANCELLED": "Đã huỷ.",
}


@dataclass
class Job:
    id: str
    work_dir: Path
    quality: str
    model: str = "triposr"
    command: list | None = None  # job lệnh tuỳ ý (Blender) — chạy 1 lần, không thử lại
    status: str = "queued"  # queued | running | done | error | cancelled
    events: list = field(default_factory=list)
    result: dict | None = None
    error: str | None = None
    proc: subprocess.Popen | None = None
    cancel_requested: bool = False

    @property
    def finished(self) -> bool:
        return self.status in ("done", "error", "cancelled")

    def emit(self, **event):
        self.events.append(event)

    def public(self) -> dict:
        return {"id": self.id, "status": self.status, "quality": self.quality, "model": self.model,
                "result": self.result, "error": self.error}


class JobRunner:
    def __init__(self, python_exe: Path, worker_script: Path, jobs_dir: Path, presets: dict,
                 env: dict | None = None, before_gpu_job: Callable[[], object] | None = None,
                 extra_models: dict | None = None):
        """Model mặc định "triposr" = python_exe/worker_script/presets. `extra_models`:
        {"hunyuan": {"python_exe", "worker_script", "presets"}} — mỗi model 1 venv riêng, chung 1 hàng đợi GPU."""
        self.models = {"triposr": {"python_exe": Path(python_exe), "worker_script": Path(worker_script), "presets": presets}}
        for name, spec in (extra_models or {}).items():
            self.models[name] = {"python_exe": Path(spec["python_exe"]), "worker_script": Path(spec["worker_script"]),
                                 "presets": spec["presets"]}
        self.jobs_dir = Path(jobs_dir)
        self.env = {**os.environ, "PYTHONUTF8": "1", **(env or {})}
        self.before_gpu_job = before_gpu_job
        self.jobs: dict[str, Job] = {}
        self._queue: queue.Queue[Job] = queue.Queue()
        threading.Thread(target=self._loop, daemon=True, name="job-runner").start()

    # ---------- API ----------
    def submit_image_to_3d(self, image_bytes: bytes, ext: str, quality: str, model: str = "triposr") -> Job:
        if model not in self.models:
            raise ValueError(f"Model không hợp lệ: {model}")
        if quality not in self.models[model]["presets"]:
            raise ValueError(f"Mức chất lượng không hợp lệ: {quality}")
        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id, work_dir=self.jobs_dir / job_id, quality=quality, model=model)
        job.work_dir.mkdir(parents=True, exist_ok=True)
        (job.work_dir / f"input{ext}").write_bytes(image_bytes)
        self.jobs[job.id] = job
        job.emit(type="status", status="queued", msg="Đang xếp hàng...")
        self._queue.put(job)
        return job

    def submit_command(self, build_command: Callable[[Path, Path], list], input_bytes: bytes, input_name: str,
                       kind: str = "blender") -> Job:
        """Job chạy 1 lệnh (vd. Blender): build_command(work_dir, input_path) -> argv. Chung hàng đợi GPU."""
        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id, work_dir=self.jobs_dir / job_id, quality="-", model=kind)
        job.work_dir.mkdir(parents=True, exist_ok=True)
        input_path = job.work_dir / input_name
        input_path.write_bytes(input_bytes)
        job.command = [str(x) for x in build_command(job.work_dir, input_path)]
        self.jobs[job.id] = job
        job.emit(type="status", status="queued", msg="Đang xếp hàng...")
        self._queue.put(job)
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job is None or job.finished:
            return False
        job.cancel_requested = True
        if job.proc and job.proc.poll() is None:
            _kill_tree(job.proc)
        return True

    # ---------- nội bộ ----------
    def _loop(self):
        while True:
            job = self._queue.get()
            try:
                self._run_job(job)
            except Exception as exc:  # không để 1 job lỗi làm chết cả hàng đợi
                self._finish(job, "error", error=f"Lỗi nội bộ: {exc}")

    def _run_job(self, job: Job):
        if job.cancel_requested:
            return self._finish(job, "cancelled", error=FRIENDLY_ERRORS["CANCELLED"])
        job.status = "running"
        job.emit(type="status", status="running", msg="Bắt đầu...")
        if self.before_gpu_job:
            self.before_gpu_job()
        if job.command:
            last = self._spawn(job, job.command)
            if job.cancel_requested:
                return self._finish(job, "cancelled", error=FRIENDLY_ERRORS["CANCELLED"])
            if last.get("type") == "done":
                job.result = last.get("stats", {})
                return self._finish(job, "done")
            return self._finish(job, "error", error=_friendly(last))
        levels = list(QUALITY_ORDER[QUALITY_ORDER.index(job.quality):])
        while levels:
            level = levels.pop(0)
            last = self._run_attempt(job, self.models[job.model]["presets"][level])
            if job.cancel_requested:
                return self._finish(job, "cancelled", error=FRIENDLY_ERRORS["CANCELLED"])
            if last.get("type") == "done":
                job.result = {**last.get("stats", {}), "quality_used": level}
                return self._finish(job, "done")
            code = str(last.get("code", ""))
            if levels and code.startswith(RETRYABLE_PREFIXES):
                job.emit(type="progress", pct=0,
                         msg=f"Thiếu bộ nhớ GPU — thử lại ở mức nhẹ hơn ({levels[0]})...")
                continue
            return self._finish(job, "error", error=_friendly(last))

    def _run_attempt(self, job: Job, preset: dict) -> dict:
        image = next(job.work_dir.glob("input.*"))
        spec = self.models[job.model]
        cmd = [str(spec["python_exe"]), str(spec["worker_script"]), "--image", str(image), "--out-dir", str(job.work_dir)]
        for key, value in preset.items():  # {"mc_resolution": 192} -> --mc-resolution 192
            cmd += [f"--{key.replace('_', '-')}", str(value)]
        return self._spawn(job, cmd)

    def _spawn(self, job: Job, cmd: list) -> dict:
        """Chạy tiến trình, chuyển dòng JSON progress vào job.events; trả về dòng JSON cuối (done/error)."""
        with open(job.work_dir / "worker.log", "a", encoding="utf-8") as log:
            job.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log, env=self.env,
                                        text=True, encoding="utf-8", errors="replace",
                                        creationflags=NO_WINDOW)
            last: dict = {}
            for line in job.proc.stdout:
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(msg, dict) or "type" not in msg:  # Blender in cả số/chuỗi lẻ là JSON hợp lệ
                    continue
                last = msg
                if msg.get("type") == "progress":
                    job.emit(**msg)
            code = job.proc.wait()
        if not last or last.get("type") == "progress":  # chết giữa chừng, không kịp báo
            last = {"type": "error", "code": f"EXIT_{code}", "msg": "Tiến trình xử lý dừng đột ngột"}
        return last

    def _finish(self, job: Job, status: str, error: str | None = None):
        job.status, job.error, job.proc = status, error, None
        job.emit(type="status", status=status, msg=error or "Xong!", result=job.result)


def _friendly(last: dict) -> str:
    code = str(last.get("code", ""))
    if code in FRIENDLY_ERRORS:
        return FRIENDLY_ERRORS[code]
    if code.startswith("EXIT_"):
        return "Tiến trình AI bị dừng đột ngột (có thể do thiếu RAM/VRAM). Thử mức \"Nhanh\"."
    return f"Tạo mô hình thất bại: {last.get('msg', 'không rõ lỗi')}"


def _kill_tree(proc: subprocess.Popen):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True, creationflags=NO_WINDOW)
    else:
        proc.kill()
