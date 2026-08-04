"""Tự kiểm tra và tải mọi mô hình còn thiếu ngay khi mở ứng dụng.

Mục tiêu: máy mới `git clone` + `setup.bat` + `run.bat` là dùng được. Nếu vì lý
do gì đó setup bỏ sót (mất mạng giữa chừng, người dùng bấm --skip-models, đổi
model trên giao diện...) thì lần mở app kế tiếp sẽ tự tải nốt phần thiếu thay vì
để bước 2/3 chết giữa chừng.

Chạy nền trong một luồng riêng nên KHÔNG làm chậm lúc khởi động. Trạng thái đọc
qua `get_state()` (endpoint `/api/models/preflight`).

Các mô hình nặng của AIVoice/MediaComposer được tải bằng SUBPROCESS dùng venv của
AIVoice — orchestrator cố ý không import torch/huggingface_hub.
"""
import os
import subprocess
import threading
import time
import logging
from typing import Optional

from orchestrator import ollama_manager
from orchestrator.config import load_global_config

logger = logging.getLogger(__name__)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AIVOICE_DIR = os.path.join(REPO_ROOT, "AIVoice")
AIVOICE_PY = os.path.join(AIVOICE_DIR, ".venv", "Scripts", "python.exe")
MC_DIR = os.path.join(AIVOICE_DIR, "apps", "MediaComposer")

# Đánh dấu "đã tải đủ model MediaComposer" để lần mở app sau bỏ qua ngay, không
# phải gọi HuggingFace kiểm tra ETag mỗi lần khởi động.
MC_MARKER = os.path.join(MC_DIR, "models", ".preflight_ok")

PIPER_ONNX = os.path.join(AIVOICE_DIR, "models", "piper", "vi_VN-vais1000-medium.onnx")

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_state = {
    "running": False,
    "finished": False,
    "started_at": 0.0,
    "finished_at": 0.0,
    "steps": [],
}
_state_lock = threading.Lock()
_thread: Optional[threading.Thread] = None


def get_state() -> dict:
    with _state_lock:
        return {
            "running": _state["running"],
            "finished": _state["finished"],
            "started_at": _state["started_at"],
            "finished_at": _state["finished_at"],
            "steps": list(_state["steps"]),
        }


def _set_step(name: str, status: str, message: str = "", percent: int = -1) -> None:
    """status: pending | running | ok | skipped | failed"""
    with _state_lock:
        for step in _state["steps"]:
            if step["name"] == name:
                step.update(status=status, message=message, percent=percent)
                return
        _state["steps"].append(
            {"name": name, "status": status, "message": message, "percent": percent}
        )


def _wanted_ollama_models(cfg: dict) -> list:
    """Chỉ pull những model Ollama mà cấu hình HIỆN TẠI thực sự dùng đến.

    Không pull sẵn cả bộ: mỗi model vài GB, tải thứ người dùng không chọn là phí
    băng thông lẫn ổ đĩa.
    """
    models = []

    chatbot = cfg.get("chatbot", {}) or {}
    if chatbot.get("enabled", True) and chatbot.get("model"):
        models.append(chatbot["model"])

    translate = cfg.get("translate", {}) or {}
    if (translate.get("default_engine") or "").lower() == "ollama" and translate.get("ollama_model"):
        models.append(translate["ollama_model"])

    video = cfg.get("video", {}) or {}
    if (video.get("default_llm_engine") or "").lower() == "ollama" and video.get("default_llm_model"):
        models.append(video["default_llm_model"])

    seen, unique = set(), []
    for m in models:
        key = m.strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def _run_ollama_step(cfg: dict) -> None:
    wanted = _wanted_ollama_models(cfg)
    if not wanted:
        _set_step("ollama", "skipped", "Cấu hình hiện tại không dùng Ollama.")
        return

    chatbot = cfg.get("chatbot", {}) or {}
    base_url = (
        chatbot.get("base_url")
        or (cfg.get("crawler", {}) or {}).get("ollama_base_url")
        or ollama_manager.DEFAULT_ROOT
    )
    autostart = chatbot.get("autostart_ollama", True)

    _set_step("ollama", "running", "Đang kiểm tra Ollama...")
    if not ollama_manager.ensure_server(base_url, autostart=autostart):
        _set_step(
            "ollama", "failed",
            "Không kết nối được Ollama. Cài tại https://ollama.com rồi mở lại ứng dụng.",
        )
        return

    failed = []
    for model in wanted:
        if ollama_manager.has_model(model, base_url):
            continue

        def cb(msg: str, pct: int, _m=model):
            _set_step("ollama", "running", msg, pct)

        if not ollama_manager.pull_model(model, base_url, progress_cb=cb):
            failed.append(model)

    if failed:
        _set_step("ollama", "failed", f"Chưa tải được model: {', '.join(failed)}")
    else:
        _set_step("ollama", "ok", f"Sẵn sàng: {', '.join(wanted)}")


def _run_subprocess_step(name: str, label: str, cmd: list, cwd: str, timeout: float) -> bool:
    _set_step(name, "running", f"Đang tải {label}...")
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        _set_step(name, "failed", f"Tải {label} quá lâu, đã dừng.")
        return False
    except Exception as e:
        _set_step(name, "failed", f"Không chạy được bước tải {label}: {e}")
        return False

    if proc.returncode == 0:
        _set_step(name, "ok", f"{label} đã sẵn sàng.", 100)
        return True

    tail = (proc.stdout or "").strip().splitlines()[-3:]
    _set_step(name, "failed", f"Tải {label} chưa xong: {' | '.join(tail)[:300]}")
    logger.warning(f"[Preflight] {label} lỗi (exit {proc.returncode}).")
    return False


def _run_tts_step() -> None:
    if os.path.isfile(PIPER_ONNX):
        _set_step("tts", "skipped", "Giọng đọc Piper đã có.")
        return
    _run_subprocess_step(
        "tts", "giọng đọc Piper",
        [AIVOICE_PY, os.path.join("src", "download_models.py"), "--engine", "piper"],
        cwd=AIVOICE_DIR, timeout=1800,
    )


def _run_mediacomposer_step() -> None:
    if os.path.isfile(MC_MARKER):
        _set_step("video", "skipped", "Model sinh ảnh/upscale đã có.")
        return

    ok = _run_subprocess_step(
        "video", "model sinh ảnh & upscale",
        [AIVOICE_PY, os.path.join("app", "services", "model_downloader.py"), "--download"],
        cwd=MC_DIR, timeout=7200,
    )
    if ok:
        try:
            os.makedirs(os.path.dirname(MC_MARKER), exist_ok=True)
            with open(MC_MARKER, "w", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass


def _worker() -> None:
    try:
        cfg = load_global_config()
        _run_ollama_step(cfg)

        if os.path.isfile(AIVOICE_PY):
            _run_tts_step()
            _run_mediacomposer_step()
        else:
            msg = "Chưa chạy setup.bat nên chưa có môi trường AIVoice."
            _set_step("tts", "skipped", msg)
            _set_step("video", "skipped", msg)
    except Exception as e:
        logger.error(f"[Preflight] Lỗi không mong đợi: {e}")
    finally:
        with _state_lock:
            _state["running"] = False
            _state["finished"] = True
            _state["finished_at"] = time.time()
        logger.info("[Preflight] Hoàn tất kiểm tra mô hình.")


def start(force: bool = False) -> bool:
    """Chạy preflight nền. False nếu đang có một lượt chạy dở."""
    global _thread
    with _state_lock:
        if _state["running"]:
            return False
        if _state["finished"] and not force:
            return False
        _state.update(running=True, finished=False, started_at=time.time(), finished_at=0.0)
        _state["steps"] = []

    logger.info("[Preflight] Bắt đầu kiểm tra & tải mô hình còn thiếu (chạy nền).")
    _thread = threading.Thread(target=_worker, name="model-preflight", daemon=True)
    _thread.start()
    return True
