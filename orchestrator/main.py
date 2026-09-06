"""API của công cụ Cào & Dịch Video (FastAPI, cổng 8100).

Ba tác vụ nặng dùng ba `task_key` CỐ ĐỊNH: "download", "translate", "merge" —
mỗi loại chỉ chạy một lần một (GPU 6GB không kham nổi song song), đổi lại giao
diện nối lại luồng log sau khi F5 mà không cần nhớ mã tác vụ.
"""
import json
import logging
import os
import subprocess
import sys
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator.config import (  # noqa: E402
    load_global_config, save_global_config, load_ui_settings, save_ui_settings,
)
from orchestrator.storage import VideoLibrary  # noqa: E402
from orchestrator.process_manager import ProcessManager  # noqa: E402
from orchestrator.pipeline import VideoPipeline, AIVOICE_DIR, AUTOSUB_ADAPTER, PYTHON_EXE  # noqa: E402
from orchestrator import ollama_manager  # noqa: E402

TASK_DOWNLOAD = "download"
TASK_TRANSLATE = "translate"
TASK_MERGE = "merge"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

app = FastAPI(title="Cào & Dịch Video — Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8100", "http://localhost:8100"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


class ProbeSchema(BaseModel):
    urls: List[str]
    platform: Optional[str] = "generic"
    cookies_file: Optional[str] = None
    max_items: Optional[int] = 0


class TranslateParams(BaseModel):
    """Tham số dịch/gắn phụ đề — dùng chung cho tab Dịch và ô 'dịch luôn sau khi tải'."""
    source_lang: Optional[str] = "English"
    target_lang: Optional[str] = "Vietnamese"
    sub_source: Optional[str] = "whisper"   # whisper | ocr | import
    source_srt: Optional[str] = None        # dùng khi sub_source = import
    translate_only: Optional[bool] = False  # chỉ xuất .srt, không ghi vào video
    no_translate: Optional[bool] = False    # ghi thẳng phụ đề nguồn, bỏ bước dịch
    burn_method: Optional[str] = "ffmpeg"
    clean_audio: Optional[bool] = False
    enable_voiceover: Optional[bool] = False
    tts_engine: Optional[str] = "edge"
    tts_voice: Optional[str] = ""
    auto_clone: Optional[bool] = False
    ducking_ratio: Optional[float] = 90.0
    llm_engine: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_offline_base_url: Optional[str] = None
    llm_offline_model: Optional[str] = None
    crop_x: Optional[int] = -1
    crop_y: Optional[int] = -1
    crop_w: Optional[int] = -1
    crop_h: Optional[int] = -1
    ocr_use_gpu: Optional[bool] = None
    font_name: Optional[str] = None
    font_size: Optional[int] = None
    text_color: Optional[str] = None
    stroke_color: Optional[str] = None
    stroke_width: Optional[float] = None
    bg_style: Optional[str] = None
    bg_color: Optional[str] = None
    bg_alpha: Optional[int] = None
    sub_position: Optional[str] = None
    custom_position: Optional[float] = None


class DownloadSchema(ProbeSchema):
    skip_existing: Optional[bool] = True
    stop_on_error: Optional[bool] = False
    auto_translate: Optional[bool] = False
    translate: Optional[TranslateParams] = None


class TranslateSchema(TranslateParams):
    entry_ids: List[str]


class ImportSchema(BaseModel):
    path: str
    title: Optional[str] = ""
    copy_file: Optional[bool] = False


class SubSaveSchema(BaseModel):
    name: str
    content: str


class MergeItem(BaseModel):
    entry_id: str
    kind: Optional[str] = "output"   # output | source
    name: Optional[str] = ""


class MergeSchema(BaseModel):
    items: List[MergeItem]
    output_name: Optional[str] = ""


class PrepareSchema(BaseModel):
    entry_id: Optional[str] = None
    video_path: Optional[str] = None
    download_url: Optional[str] = None
    platform: Optional[str] = "generic"
    cookies_file: Optional[str] = None


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


@app.get("/api/stats")
def get_stats():
    stats = library.stats()
    stats["running_tasks"] = process_mgr.list_running()
    return stats


@app.post("/api/maintenance/cleanup-tasks")
def cleanup_tasks_api(dry_run: bool = True, days: float = 0):
    """Dọn thư mục làm việc tạm (ảnh xem trước OCR, video tải thử...)."""
    return library.cleanup_tasks(keep_days=days, dry_run=dry_run)


# ------------------------------------------------------------- Thư viện
@app.get("/api/videos")
def list_videos():
    return library.list_entries()


@app.get("/api/videos/{entry_id}")
def get_video(entry_id: str):
    entry = library.read_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Không có video '{entry_id}' trong thư viện.")
    return entry


@app.delete("/api/videos/{entry_id}")
def delete_video(entry_id: str):
    if not library.read_entry(entry_id):
        raise HTTPException(status_code=404, detail=f"Không có video '{entry_id}' trong thư viện.")
    if library.delete_entry(entry_id):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Không xoá được thư mục video (file đang mở?).")


@app.post("/api/videos/import")
def import_video(body: ImportSchema):
    """Đưa video có sẵn trên máy vào thư viện để dịch (mặc định không chép file)."""
    try:
        entry = library.register_local(body.path, body.title or "", bool(body.copy_file))
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Đọc W/H/thời lượng để thư viện hiện đủ thông tin như video tải về. Không đọc
    # được (file hỏng, thiếu codec) thì vẫn giữ mục lại — người dùng vẫn dịch được.
    meta = pipeline.probe_media(entry["file"])
    if meta:
        entry.update(meta)
        library.write_entry(entry["entry_id"], entry)
        entry = library.read_entry(entry["entry_id"])
    return entry


def _reveal_in_file_manager(path: str) -> None:
    """Mở thư mục bằng trình quản lý tệp của hệ điều hành (app chạy cục bộ)."""
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - đường dẫn do server tự dựng
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


@app.post("/api/videos/{entry_id}/open-folder")
def open_video_folder(entry_id: str, kind: str = "root"):
    entry = library.read_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Không có video '{entry_id}' trong thư viện.")
    path = {"output": library.output_dir(entry_id),
            "subs": library.subs_dir(entry_id)}.get(kind, library.entry_dir(entry_id))
    try:
        os.makedirs(path, exist_ok=True)
        _reveal_in_file_manager(path)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Không mở được thư mục '{path}': {e}")
    return {"status": "success", "path": path}


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


@app.get("/api/videos/{entry_id}/play")
def play_video(entry_id: str, kind: str = "source", name: str = ""):
    """Phát video ngay trong giao diện (FileResponse của Starlette có hỗ trợ Range)."""
    try:
        path = library.find_file(entry_id, kind, name)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    return FileResponse(path, media_type="video/mp4", filename=os.path.basename(path))


@app.get("/api/videos/{entry_id}/sub")
def read_sub(entry_id: str, name: str, download: bool = False):
    """Nội dung một file phụ đề — để sửa tay trên giao diện hoặc tải về."""
    try:
        path = library.find_file(entry_id, "sub", name)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    if download:
        return FileResponse(path, media_type="application/x-subrip", filename=os.path.basename(path))
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return PlainTextResponse(fh.read())
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Không đọc được file phụ đề: {e}")


@app.post("/api/videos/{entry_id}/sub")
def save_sub(entry_id: str, body: SubSaveSchema):
    """Lưu phụ đề đã sửa/tải lên; dùng lại được ngay ở chế độ 'phụ đề có sẵn'."""
    try:
        saved = library.add_sub(entry_id, body.name, body.content)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", **saved}


# ------------------------------------------------------------- Cào video
@app.post("/api/download/probe")
def download_probe(body: ProbeSchema):
    urls = [u.strip() for u in body.urls if u and u.strip()]
    if not urls:
        raise HTTPException(status_code=400, detail="Chưa nhập link video nào.")
    try:
        return pipeline.probe(urls, body.model_dump())
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Quá 5 phút vẫn chưa đọc xong danh sách — kiểm tra mạng/link.")
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/download/start")
def download_start(body: DownloadSchema):
    urls = [u.strip() for u in body.urls if u and u.strip()]
    if not urls:
        raise HTTPException(status_code=400, detail="Chưa nhập link video nào.")
    if process_mgr.is_running(TASK_DOWNLOAD):
        raise HTTPException(status_code=400, detail="Đang có lượt tải khác chạy — dừng nó trước.")

    then_translate = None
    if body.auto_translate:
        if process_mgr.is_running(TASK_TRANSLATE):
            raise HTTPException(status_code=400,
                                detail="Đang có tác vụ dịch chạy — không thể bật 'dịch luôn sau khi tải'.")
        params = body.translate or TranslateParams()
        then_translate = params.model_dump()

    if not pipeline.start_download(TASK_DOWNLOAD, urls, body.model_dump(), then_translate):
        raise HTTPException(status_code=500, detail="Không khởi động được tiến trình tải.")
    return {"status": "success", "task_key": TASK_DOWNLOAD}


# ------------------------------------------------------------- Dịch video
@app.post("/api/translate/start")
def translate_start(body: TranslateSchema):
    if not body.entry_ids:
        raise HTTPException(status_code=400, detail="Chưa chọn video nào để dịch.")
    if process_mgr.is_running(TASK_TRANSLATE):
        raise HTTPException(status_code=400, detail="Tác vụ dịch đang chạy — dừng nó trước.")

    jobs = []
    for entry_id in body.entry_ids:
        entry = library.read_entry(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail=f"Không có video '{entry_id}' trong thư viện.")
        if not entry.get("exists"):
            raise HTTPException(status_code=400,
                                detail=f"File video của '{entry.get('title')}' không còn trên đĩa.")
        jobs.append(pipeline.make_job(entry))

    args = body.model_dump()
    if args.get("sub_source") == "import":
        # Phụ đề nạp vào phải áp cho ĐÚNG một video: dùng chung một file .srt cho
        # cả hàng đợi thì mọi video sau đều lệch tiếng.
        if len(jobs) > 1:
            raise HTTPException(
                status_code=400,
                detail="Chế độ 'phụ đề có sẵn' chỉ áp dụng cho một video mỗi lượt.")
        srt = (args.get("source_srt") or "").strip()
        if not srt or not os.path.exists(srt):
            raise HTTPException(status_code=400, detail=f"Không tìm thấy file phụ đề: {srt or '(trống)'}")

    try:
        started = pipeline.start_translate(TASK_TRANSLATE, jobs, args)
    except ValueError as e:  # thiếu API key cho engine đã chọn
        raise HTTPException(status_code=400, detail=str(e))
    if not started:
        raise HTTPException(status_code=500, detail="Không khởi động được tác vụ dịch.")
    return {"status": "success", "task_key": TASK_TRANSLATE, "count": len(jobs)}


@app.post("/api/autosub/prepare")
def autosub_prepare(body: PrepareSchema):
    """Tải/đọc video rồi trả một khung hình để người dùng khoanh vùng phụ đề (OCR)."""
    import base64
    import uuid

    video_path = body.video_path
    if body.entry_id:
        entry = library.read_entry(body.entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail=f"Không có video '{body.entry_id}' trong thư viện.")
        video_path = entry.get("file")
    if not video_path and not body.download_url:
        raise HTTPException(status_code=400, detail="Cần chọn video trong thư viện, hoặc nhập đường dẫn/link.")

    task_id = uuid.uuid4().hex[:8]
    work_dir = os.path.join(library.tasks_dir, f"prepare_{task_id}")
    os.makedirs(work_dir, exist_ok=True)

    cmd = [PYTHON_EXE, AUTOSUB_ADAPTER, "--prepare-only", "--output-dir", work_dir]
    if body.download_url:
        cmd += ["--download-url", body.download_url, "--platform", body.platform or "generic"]
    else:
        cmd += ["--video-path", video_path]
    g_config = load_global_config()
    cookies = (body.cookies_file
               or (g_config.get("download") or {}).get("cookies_file")
               or (g_config.get("video") or {}).get("downloader_cookies") or "")
    if cookies:
        cmd += ["--cookies-file", cookies]

    try:
        res = subprocess.run(cmd, cwd=AIVOICE_DIR, capture_output=True, text=True,
                             encoding="utf-8", timeout=900, creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Tải/chuẩn bị video quá 15 phút — kiểm tra link hoặc mạng.")

    info = None
    for line in (res.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("event") == "prepare_done":
            info = data
            break
    if not info:
        detail = (res.stderr or res.stdout or "không có output")[-1000:]
        raise HTTPException(status_code=500, detail=f"Không chuẩn bị được video. Log: {detail}")

    preview = info.get("preview_image")
    if not preview or not os.path.exists(preview):
        raise HTTPException(status_code=500, detail="Không tạo được ảnh xem trước.")
    with open(preview, "rb") as fh:
        img_b64 = base64.b64encode(fh.read()).decode("utf-8")
    return {
        "prepared_path": info.get("prepared_path"),
        "width": info.get("width"),
        "height": info.get("height"),
        "duration": info.get("duration"),
        "preview_b64": f"data:image/jpeg;base64,{img_b64}",
    }


# ------------------------------------------------------------- Ghép video
@app.post("/api/merge/start")
def merge_start(body: MergeSchema):
    if not body.items:
        raise HTTPException(status_code=400, detail="Chưa chọn video nào để ghép.")
    if process_mgr.is_running(TASK_MERGE):
        raise HTTPException(status_code=400, detail="Tác vụ ghép đang chạy.")

    files = []
    for item in body.items:
        try:
            files.append(library.find_file(item.entry_id, item.kind or "output", item.name or ""))
        except (FileNotFoundError, ValueError) as e:
            raise HTTPException(status_code=400, detail=str(e))

    if not pipeline.start_merge(TASK_MERGE, files, body.output_name or ""):
        raise HTTPException(status_code=500, detail="Không khởi động được tác vụ ghép.")
    return {"status": "success", "task_key": TASK_MERGE, "count": len(files)}


@app.get("/api/merged")
def list_merged():
    return library._list_files(library.merged_dir, (".mp4",))


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
    raise HTTPException(status_code=404, detail=f"Không có tác vụ '{task_key}' đang chạy.")


# Giao diện web (đặt CUỐI để không nuốt mất các route /api/*)
webui_dir = os.path.abspath("webui")
if os.path.exists(webui_dir):
    app.mount("/", StaticFiles(directory=webui_dir, html=True), name="webui")
