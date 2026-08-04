"""Tự động bảo đảm Ollama sẵn sàng khi chạy.

Máy mới chỉ cần `git clone` + `setup.bat` là chạy được. Nhưng người dùng vẫn có
thể đổi model trên giao diện sang một model chưa pull, hoặc tắt Ollama đi. Module
này lo phần đó lúc RUNTIME:

- `ensure_server()`  : Ollama chưa chạy thì tự khởi động (tìm ollama.exe ở PATH
                       và các thư mục cài mặc định trên Windows).
- `ensure_model()`   : model chưa có trên đĩa thì tự `pull` qua HTTP /api/pull,
                       báo tiến độ theo phần trăm.
- `ensure_ready()`   : gộp cả hai, dùng trước mọi lời gọi Ollama.

Cố ý KHÔNG dùng `ollama` CLI để pull: gọi thẳng HTTP API cho ra tiến độ dạng số
và không đẻ thêm cửa sổ console khi chạy dưới pythonw.
"""
import os
import shutil
import subprocess
import threading
import time
import logging
from typing import Callable, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_ROOT = "http://localhost:11434"

# Mỗi model chỉ được pull bởi MỘT luồng; các luồng khác chờ rồi dùng lại kết quả.
_pull_locks: dict[str, threading.Lock] = {}
_pull_locks_guard = threading.Lock()
_server_lock = threading.Lock()

ProgressCb = Optional[Callable[[str, int], None]]


def _emit(progress_cb: ProgressCb, message: str, percent: int = -1) -> None:
    if progress_cb:
        try:
            progress_cb(message, percent)
        except Exception:
            pass


def to_root(base_url: str = "") -> str:
    """Chuẩn hoá base_url (có thể là dạng OpenAI `.../v1`) về gốc Ollama."""
    root = (base_url or DEFAULT_ROOT).rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    return root or DEFAULT_ROOT


def same_tag(a: str, b: str) -> bool:
    """Ollama coi 'foo' và 'foo:latest' là một."""
    def norm(s: str) -> str:
        s = (s or "").strip()
        return s if ":" in s else f"{s}:latest"
    return norm(a) == norm(b)


def is_server_up(root: str = DEFAULT_ROOT, timeout: float = 2.0) -> bool:
    try:
        with httpx.Client(timeout=timeout) as client:
            return client.get(f"{root}/api/tags").status_code == 200
    except Exception:
        return False


def find_ollama_exe() -> Optional[str]:
    """Tìm ollama.exe: PATH trước, rồi các thư mục cài mặc định trên Windows."""
    found = shutil.which("ollama")
    if found:
        return found

    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Ollama", "ollama.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Ollama", "ollama.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def ensure_server(
    base_url: str = "",
    autostart: bool = True,
    wait_seconds: float = 30.0,
    progress_cb: ProgressCb = None,
) -> bool:
    """True nếu Ollama đang phục vụ (tự khởi động nếu cần và được phép)."""
    root = to_root(base_url)
    if is_server_up(root):
        return True
    if not autostart:
        return False

    # Chỉ một luồng được phép khởi động server; luồng khác chờ rồi kiểm tra lại.
    with _server_lock:
        if is_server_up(root):
            return True

        exe = find_ollama_exe()
        if not exe:
            _emit(progress_cb, "Chưa cài Ollama trên máy này (tải tại https://ollama.com).")
            logger.warning("[Ollama] Không tìm thấy ollama.exe để khởi động.")
            return False

        _emit(progress_cb, "Ollama chưa chạy — đang tự khởi động...", 0)
        logger.info(f"[Ollama] Khởi động server bằng: {exe}")
        try:
            subprocess.Popen(
                [exe, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as e:
            logger.warning(f"[Ollama] Không khởi động được server: {e}")
            _emit(progress_cb, f"Không khởi động được Ollama: {e}")
            return False

        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if is_server_up(root, timeout=1.5):
                logger.info("[Ollama] Server đã sẵn sàng.")
                _emit(progress_cb, "Ollama đã sẵn sàng.", 100)
                return True
            time.sleep(1.0)

    logger.warning(f"[Ollama] Server không phản hồi sau {wait_seconds}s.")
    _emit(progress_cb, "Ollama khởi động quá lâu, bỏ qua.")
    return False


def list_installed(base_url: str = "", timeout: float = 5.0) -> List[str]:
    """Danh sách model đã pull về đĩa. Lỗi kết nối trả về danh sách rỗng."""
    root = to_root(base_url)
    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.get(f"{root}/api/tags")
            res.raise_for_status()
            return [m.get("name", "") for m in res.json().get("models", []) if m.get("name")]
    except Exception:
        return []


def has_model(model: str, base_url: str = "") -> bool:
    if not model:
        return False
    return any(same_tag(model, name) for name in list_installed(base_url))


def pull_model(
    model: str,
    base_url: str = "",
    progress_cb: ProgressCb = None,
    timeout: float = 3600.0,
) -> bool:
    """Pull model qua /api/pull (stream) và báo tiến độ. True nếu đã có/pull xong."""
    if not model:
        return False

    root = to_root(base_url)

    with _pull_locks_guard:
        lock = _pull_locks.setdefault(model, threading.Lock())

    # Luồng thứ hai cùng model sẽ chờ ở đây rồi thấy model đã có -> không pull lại.
    with lock:
        if has_model(model, root):
            return True

        _emit(progress_cb, f"Đang tải model '{model}' (lần đầu có thể mất vài phút)...", 0)
        logger.info(f"[Ollama] Bắt đầu pull model '{model}'.")
        last_percent = -1
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0)) as client:
                with client.stream(
                    "POST", f"{root}/api/pull", json={"model": model, "stream": True}
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        line = (line or "").strip()
                        if not line:
                            continue
                        try:
                            import json as _json
                            data = _json.loads(line)
                        except Exception:
                            continue

                        if data.get("error"):
                            logger.error(f"[Ollama] Pull '{model}' lỗi: {data['error']}")
                            _emit(progress_cb, f"Tải model thất bại: {data['error']}")
                            return False

                        total = data.get("total") or 0
                        completed = data.get("completed") or 0
                        if total > 0:
                            percent = int(completed * 100 / total)
                            # Chỉ báo mỗi khi nhích 5% để không spam log/SSE.
                            if percent >= last_percent + 5:
                                last_percent = percent
                                _emit(progress_cb, f"Đang tải model '{model}'... {percent}%", percent)
        except Exception as e:
            logger.error(f"[Ollama] Pull '{model}' thất bại: {e}")
            _emit(progress_cb, f"Tải model '{model}' thất bại: {e}")
            return False

        # Ollama báo "success" ở dòng cuối, nhưng vẫn xác nhận lại bằng /api/tags
        # để không báo thành công khi stream đứt giữa chừng.
        ok = has_model(model, root)
        if ok:
            logger.info(f"[Ollama] Đã tải xong model '{model}'.")
            _emit(progress_cb, f"Đã tải xong model '{model}'.", 100)
        else:
            logger.warning(f"[Ollama] Pull '{model}' kết thúc nhưng model vẫn chưa có.")
            _emit(progress_cb, f"Model '{model}' vẫn chưa sẵn sàng sau khi tải.")
        return ok


def ensure_ready(
    model: str,
    base_url: str = "",
    autostart: bool = True,
    auto_pull: bool = True,
    progress_cb: ProgressCb = None,
) -> dict:
    """Bảo đảm server chạy + model đã có. Trả về {ok, server, model_installed, reason}."""
    root = to_root(base_url)
    result = {"ok": False, "server": False, "model_installed": False, "reason": ""}

    if not ensure_server(root, autostart=autostart, progress_cb=progress_cb):
        result["reason"] = (
            "Không kết nối được Ollama. Hãy mở ứng dụng Ollama, "
            "hoặc cài tại https://ollama.com rồi thử lại."
        )
        return result
    result["server"] = True

    if not model:
        result["ok"] = True
        return result

    if has_model(model, root):
        result["model_installed"] = True
        result["ok"] = True
        return result

    if not auto_pull:
        result["reason"] = f"Model '{model}' chưa được tải về."
        return result

    if pull_model(model, root, progress_cb=progress_cb):
        result["model_installed"] = True
        result["ok"] = True
    else:
        result["reason"] = f"Không tải được model '{model}'."
    return result
