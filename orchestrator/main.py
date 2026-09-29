"""API của công cụ Cào & Dịch Video (FastAPI, cổng 8100).

Ba tác vụ nặng dùng ba `task_key` CỐ ĐỊNH: "download", "translate", "merge" —
mỗi loại chỉ chạy một lần một (GPU 6GB không kham nổi song song), đổi lại giao
diện nối lại luồng log sau khi F5 mà không cần nhớ mã tác vụ.
"""
import datetime
import json
import logging
import os
import subprocess
import sys
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator.config import (  # noqa: E402
    load_global_config, save_global_config, load_ui_settings, save_ui_settings,
)
from orchestrator.storage import VideoLibrary, new_batch_id, scan_video_files  # noqa: E402
from orchestrator.process_manager import ProcessManager  # noqa: E402
from orchestrator.pipeline import (  # noqa: E402
    VideoPipeline, AIVOICE_DIR, AUTOSUB_ADAPTER, PYTHON_EXE, REPO_ROOT,
)
from orchestrator import ollama_manager, project  # noqa: E402

TASK_DOWNLOAD = "download"
TASK_TRANSLATE = "translate"
TASK_MERGE = "merge"
TASK_IMPORT = "import"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

app = FastAPI(title="Cào & Dịch Video — Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8100", "http://localhost:8100"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def khong_cache_giao_dien(request, call_next):
    """App chạy cục bộ nên không cache file giao diện — đọc lại từ đĩa vài mili-giây.

    Thiếu dòng này thì sau mỗi lần cập nhật, cửa sổ WebView2 vẫn hiện giao diện
    CŨ cho tới khi người dùng tự xoá cache: lỗi rất khó đoán vì code đã đúng mà
    màn hình thì không đổi.
    """
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response

_cfg = load_global_config()
_storage_dir = (_cfg.get("storage_dir") or "storage").strip() or "storage"
library = VideoLibrary(base_storage_dir=_storage_dir)
process_mgr = ProcessManager()
pipeline = VideoPipeline(library, process_mgr)


# ----------------------------------------------------------------- Schemas
class GlobalConfigSchema(BaseModel):
    # extra="allow": giữ nguyên mọi mục cấu hình mới mà không phải khai báo cứng.
    model_config = ConfigDict(extra="allow")
    api_keys: dict
    storage_dir: str


























class PickFilesSchema(BaseModel):
    # files = chọn nhiều video | folder = chọn cả thư mục | media = video/âm thanh/ảnh/phụ đề (editor)
    mode: Optional[str] = "files"










# ------------------------------------------------------------- Cấu hình
@app.get("/api/config")
def get_config():
    return load_global_config()


@app.post("/api/config")
def update_config(config: GlobalConfigSchema):
    if save_global_config(config.model_dump()):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Không ghi được configs/global_config.json.")


@app.get("/api/ui-settings")
def get_ui_settings():
    return load_ui_settings()


@app.post("/api/ui-settings")
def update_ui_settings(settings: dict):
    if save_ui_settings(settings):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Không ghi được configs/ui_settings.json.")


@app.get("/api/system/gpu-info")
def get_gpu_info():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, creationflags=NO_WINDOW)
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().splitlines()[0].split(", ")
            return {"name": parts[0], "vram": parts[1] if len(parts) > 1 else "N/A"}
    except (OSError, subprocess.SubprocessError):
        pass
    return {"name": "Không thấy GPU NVIDIA", "vram": "N/A"}


@app.get("/api/ollama/models")
def get_ollama_models():
    """Model Ollama đã cài + vài model dịch khuyến nghị (nhẹ, hợp GPU 6GB)."""
    curated = {
        "qwen2.5:3b-instruct": "Nhẹ ~2-3GB VRAM — mặc định cho dịch phụ đề",
        "hy-mt2:1.8b": "Chuyên dịch Trung/Anh → Việt, siêu nhẹ",
        "translategemma:4b": "Chuyên dịch, 55 ngôn ngữ",
        "qwen2.5:7b-instruct": "Chất lượng cao hơn, ~5GB VRAM",
    }
    base_url = (load_global_config().get("translate") or {}).get("ollama_base_url", "")
    installed = ollama_manager.list_installed(base_url)
    online = ollama_manager.is_server_up(ollama_manager.to_root(base_url))
    models = [{"name": n, "label": curated.get(n, ""), "installed": True} for n in installed]
    for name, label in curated.items():
        if name not in installed:
            models.append({"name": name, "label": label, "installed": False})
    return {"ollama_online": online, "models": models}




@app.post("/api/maintenance/cleanup-tasks")
def cleanup_tasks_api(dry_run: bool = True, days: float = 0):
    """Dọn thư mục làm việc tạm (ảnh xem trước OCR, video tải thử...)."""
    return library.cleanup_tasks(keep_days=days, dry_run=dry_run)


# ------------------------------------------------------------- Thư viện














# ------------------------------------------------------------- Dự án video
























def _reveal_in_file_manager(path: str) -> None:
    """Mở thư mục bằng trình quản lý tệp của hệ điều hành (app chạy cục bộ)."""
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - đường dẫn do server tự dựng
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])






@app.post("/api/system/open-folder")
def open_storage_folder(kind: str = "storage"):
    path = {"videos": library.videos_dir, "merged": library.merged_dir,
            "tasks": library.tasks_dir}.get(kind, library.base_dir)
    try:
        os.makedirs(path, exist_ok=True)
        _reveal_in_file_manager(path)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Không mở được thư mục '{path}': {e}")
    return {"status": "success", "path": path}


@app.post("/api/system/pick-files")
def pick_files(body: PickFilesSchema):
    """Mở hộp thoại chọn video của hệ điều hành, trả về đường dẫn thật.

    Trình duyệt không cho biết đường dẫn file người dùng chọn, và video vài GB
    thì không upload được — nên hộp thoại phải mở ở phía máy chủ. Chạy tiến
    trình riêng vì tkinter đòi luồng chính (xem `orchestrator/file_picker.py`).
    """
    mode = body.mode if (body.mode or "") in ("folder", "media") else "files"
    env = os.environ.copy()
    env["PYTHONPATH"] = REPO_ROOT
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        res = subprocess.run(
            [sys.executable, "-m", "orchestrator.file_picker", "--mode", mode],
            cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
            timeout=600, creationflags=NO_WINDOW, env=env)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504,
                            detail="Hộp thoại chọn file mở quá 10 phút chưa chọn gì — thử lại.")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Không mở được hộp thoại chọn file: {e}")

    data = None
    for line in (res.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
    if data is None:
        detail = (res.stderr or "")[-400:] or "không đọc được kết quả"
        raise HTTPException(status_code=500,
                            detail=f"Không mở được hộp thoại chọn file. Chi tiết: {detail}")
    if data.get("error"):
        raise HTTPException(status_code=500, detail=f"Hộp thoại chọn file lỗi: {data['error']}")

    paths = data.get("paths") or []
    folder = ""
    cancelled = not paths
    if mode == "folder" and paths:
        folder = paths[0]
        paths = scan_video_files(folder)
        # Thư mục rỗng KHÔNG phải là lỗi: lúc tạo dự án trống để tải video về,
        # thư mục cha đương nhiên chưa có video nào. Bên gọi tự quyết định.
        cancelled = False
    return {"paths": paths, "folder": folder, "cancelled": cancelled}








# ------------------------------------------------------------- Cào video








# ------------------------------------------------------------- Dịch video




# ------------------------------------------------------------- Ghép video




# ------------------------------------------------------------- Tác vụ chung
@app.get("/api/tasks/logs/{task_key}")
def stream_logs(task_key: str):
    return StreamingResponse(process_mgr.get_logs_generator(task_key),
                             media_type="text/event-stream")


@app.get("/api/tasks/status/{task_key}")
def task_status(task_key: str):
    return process_mgr.get_task_status(task_key)


@app.get("/api/tasks/running")
def running_tasks():
    return {"running": process_mgr.list_running()}


@app.post("/api/tasks/stop")
def stop_task(task_key: str):
    if process_mgr.stop_process(task_key):
        return {"status": "success", "message": f"Đã dừng tác vụ '{task_key}'."}
    # Task chạy bằng thread (nhập hàng loạt, ghép) không có tiến trình con để
    # giết — chỉ đặt cờ, vòng lặp của nó tự thoát sau việc đang dở.
    if process_mgr.request_stop(task_key):
        return {"status": "success",
                "message": f"Đã yêu cầu dừng '{task_key}' — sẽ dừng sau khi xong việc đang dở."}
    raise HTTPException(status_code=404, detail=f"Không có tác vụ '{task_key}' đang chạy.")


# ------------------------------------------------------------- Editor (GĐ 0)
from orchestrator.editor import api as editor_api  # noqa: E402

editor_router = editor_api.tao_router(process_mgr, pipeline)
app.include_router(editor_router)


@app.get("/", include_in_schema=False)
def trang_chu():
    """Mở app là vào trang chủ dự án; giao diện cũ đã bị gỡ."""
    return RedirectResponse("/home.html")


# Giao diện web (đặt CUỐI để không nuốt mất các route /api/*)
webui_dir = os.path.abspath("webui")
if os.path.exists(webui_dir):
    app.mount("/", StaticFiles(directory=webui_dir, html=True), name="webui")
