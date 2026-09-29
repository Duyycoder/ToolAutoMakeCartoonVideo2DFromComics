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


def _env_ollama() -> dict:
    """Môi trường cho `ollama serve` do app tự bật.

    OLLAMA_NUM_PARALLEL / OLLAMA_MODELS lấy bản MỚI NHẤT trong registry (HKCU\\Environment): tiến trình app kế thừa
    môi trường từ lúc mở, người dùng đổi sau đó (vd NUM_PARALLEL 1 → 4 để dịch song song) thì app vẫn giữ giá trị cũ.
    """
    env = os.environ.copy()
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                for ten in ("OLLAMA_NUM_PARALLEL", "OLLAMA_MODELS"):
                    try:
                        env[ten] = str(winreg.QueryValueEx(k, ten)[0])
                    except OSError:
                        pass
        except OSError:
            pass
    env.setdefault("OLLAMA_NUM_PARALLEL", "8")
    return env


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
                env=_env_ollama(),
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


# Model dịch chuyên dụng HY-MT2 KHÔNG có trên kho Ollama: phải pull GGUF từ HuggingFace rồi `ollama create` với Modelfile có
# template đã sửa (template tự sinh khi convert bị hỏng → model chỉ trả "onse"). Tên hiển thị → nguồn GGUF.
HY_MT2_NGUON = {
    "hy-mt2:1.8b-q4": "hf.co/tencent/Hy-MT2-1.8B-GGUF:Q4_K_M",   # 1,1 GB, nhanh hơn ~1,3× Q8 nhưng sai nghĩa gấp đôi (đo 29/09) — không làm mặc định
    "hy-mt2:1.8b": "hf.co/tencent/Hy-MT2-1.8B-GGUF:Q8_0",
}
MODELFILE_HY_MT2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ollama_models", "Modelfile.hy-mt2")


def _tao_hy_mt2(model: str, nguon: str) -> bool:
    """`ollama create <model>` từ GGUF `nguon` đã pull, dùng template trong Modelfile.hy-mt2 (chỉ thay dòng FROM)."""
    import re
    import tempfile
    exe = find_ollama_exe()
    if not exe or not os.path.exists(MODELFILE_HY_MT2):
        logger.error("[Ollama] Thiếu ollama.exe hoặc Modelfile.hy-mt2 — không tạo được model dịch.")
        return False
    noi_dung = open(MODELFILE_HY_MT2, encoding="utf-8").read()
    noi_dung = re.sub(r"(?m)^FROM .*$", f"FROM {nguon}", noi_dung, count=1)
    with tempfile.NamedTemporaryFile("w", suffix=".Modelfile", delete=False, encoding="utf-8") as tmp:
        tmp.write(noi_dung)
    try:
        kq = subprocess.run([exe, "create", model, "-f", tmp.name], capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=_env_ollama(), timeout=600,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if kq.returncode != 0:
            logger.error(f"[Ollama] create '{model}' lỗi: {(kq.stderr or kq.stdout)[-300:]}")
        return kq.returncode == 0
    finally:
        os.unlink(tmp.name)


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
        nguon = HY_MT2_NGUON.get(model)
        ten_pull = nguon or model
        if nguon and has_model(nguon, root):
            return _tao_hy_mt2(model, nguon) and has_model(model, root)

        _emit(progress_cb, f"Đang tải model '{model}' (lần đầu có thể mất vài phút)...", 0)
        logger.info(f"[Ollama] Bắt đầu pull model '{model}'.")
        last_percent = -1
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0)) as client:
                with client.stream(
                    "POST", f"{root}/api/pull", json={"model": ten_pull, "stream": True}
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
        if nguon:
            _emit(progress_cb, f"Đang tạo model '{model}'…", 99)
            _tao_hy_mt2(model, nguon)
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
