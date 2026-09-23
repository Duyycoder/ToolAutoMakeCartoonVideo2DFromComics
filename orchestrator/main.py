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
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
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


class MergeAfterSchema(BaseModel):
    """Khúc ghép nối vào cuối chuỗi tải/nhập → dịch → ghép."""
    enabled: Optional[bool] = False
    output_name: Optional[str] = ""
    prefer: Optional[str] = "output"    # output = ưu tiên bản đã gắn phụ đề | source = bản gốc
    normalize: Optional[bool] = True    # tự chuẩn hoá khi các video khác cỡ nhau


class DownloadSchema(ProbeSchema):
    skip_existing: Optional[bool] = True
    stop_on_error: Optional[bool] = False
    auto_translate: Optional[bool] = False
    translate: Optional[TranslateParams] = None
    batch_id: Optional[str] = ""
    batch_name: Optional[str] = ""
    batch_index: Optional[List[float]] = None   # chỗ đứng của từng link trong lô
    merge_after: Optional[MergeAfterSchema] = None


class TranslateSchema(TranslateParams):
    entry_ids: List[str]


class ImportSchema(BaseModel):
    path: str
    title: Optional[str] = ""
    copy_file: Optional[bool] = False


class ProjectFolderSchema(BaseModel):
    folder: str


class ProjectInitSchema(BaseModel):
    folder: str
    name: Optional[str] = ""
    doi_ten: Optional[bool] = True   # False = chỉ đánh dấu dự án, giữ nguyên tên file


class ProjectCreateSchema(BaseModel):
    thu_muc_cha: str
    ten: str


class ImportBatchItem(BaseModel):
    path: str
    title: Optional[str] = ""
    index: Optional[float] = None   # chỗ đứng trong lô; để trống = theo thứ tự gửi lên


class ImportBatchSchema(BaseModel):
    items: List[ImportBatchItem]
    copy_file: Optional[bool] = False
    batch_id: Optional[str] = ""    # có sẵn = nhập thêm vào lô đang dựng
    batch_name: Optional[str] = ""
    auto_translate: Optional[bool] = False
    translate: Optional[TranslateParams] = None
    merge_after: Optional[MergeAfterSchema] = None


class PickFilesSchema(BaseModel):
    mode: Optional[str] = "files"   # files = chọn nhiều video | folder = chọn cả thư mục


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
    normalize: Optional[bool] = True   # tự chuẩn hoá khi các video khác cỡ nhau


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


@app.post("/api/videos/import-batch")
def import_batch(body: ImportBatchSchema):
    """Nhập nhiều video có sẵn trên máy vào thư viện, giữ đúng thứ tự đã sắp.

    Chạy nền (task_key "import") vì mỗi file phải đọc W/H bằng một tiến trình
    con; giao diện theo dõi qua SSE như các tác vụ nặng khác.
    """
    items = [it for it in body.items if (it.path or "").strip()]
    if not items:
        raise HTTPException(status_code=400, detail="Chưa chọn file video nào.")
    if process_mgr.is_running(TASK_IMPORT):
        raise HTTPException(status_code=400, detail="Đang có lượt nhập khác chạy — chờ nó xong đã.")

    then_translate = _chain_translate(body.auto_translate, body.translate)
    then_merge = _chain_merge(body.merge_after)
    batch_id = (body.batch_id or "").strip() or new_batch_id(body.batch_name or "")

    then = None
    if then_translate or then_merge:
        def then(exit_code: int, entries: List[dict]):
            """Nhập xong thì đi tiếp: dịch từng video rồi ghép cả lô."""
            pipeline.chain_after_entries(TASK_IMPORT, entries, exit_code,
                                         then_translate, then_merge, batch_id)

    if not pipeline.start_import(TASK_IMPORT, [it.model_dump() for it in items],
                                 bool(body.copy_file), batch_id, then):
        raise HTTPException(status_code=500, detail="Không khởi động được tác vụ nhập.")
    return {"status": "success", "task_key": TASK_IMPORT,
            "batch_id": batch_id, "count": len(items)}


@app.get("/api/batches")
def list_batches():
    """Các lô đã chạy — để tab Ghép nạp lại cả lô đúng thứ tự."""
    return library.list_batches()


@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: str):
    entries = library.list_batch(batch_id)
    if not entries:
        raise HTTPException(status_code=404, detail=f"Không có lô '{batch_id}'.")
    return entries


# ------------------------------------------------------------- Dự án video
def _nho_du_an(folder: str, name: str) -> None:
    """Ghi vào danh sách dự án gần đây để sidebar chọn lại nhanh."""
    cfg = load_global_config()
    du_an = cfg.get("du_an") or {}
    gan_day = [r for r in (du_an.get("gan_day") or [])
               if (r.get("folder") or "").lower() != folder.lower()]
    gan_day.insert(0, {"folder": folder, "name": name,
                       "at": datetime.datetime.now().isoformat(timespec="seconds")})
    du_an["gan_day"] = gan_day[:10]
    du_an["hien_tai"] = folder
    cfg["du_an"] = du_an
    save_global_config(cfg)


def _quen_du_an(folder: str) -> None:
    cfg = load_global_config()
    du_an = cfg.get("du_an") or {}
    du_an["gan_day"] = [r for r in (du_an.get("gan_day") or [])
                        if (r.get("folder") or "").lower() != folder.lower()]
    if (du_an.get("hien_tai") or "").lower() == folder.lower():
        du_an["hien_tai"] = ""
    cfg["du_an"] = du_an
    save_global_config(cfg)


@app.post("/api/project/inspect")
def project_inspect(body: ProjectFolderSchema):
    """Nhìn một thư mục TRƯỚC khi động vào nó.

    Chỉ đọc: trả về có video không, đã là dự án chưa, và bảng đổi tên dự kiến để
    giao diện cho người dùng duyệt. Đổi tên file là việc không Ctrl+Z được nên
    không bao giờ làm mà chưa hỏi.
    """
    try:
        return project.xem_xet(body.folder)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/project/init")
def project_init(body: ProjectInitSchema):
    """Biến thư mục thành dự án — đổi tên file THẬT khi `doi_ten` bật."""
    try:
        data = project.init(body.folder, body.name or "", bool(body.doi_ten))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Không đổi tên được file: {e}")
    _nho_du_an(data["folder"], data["name"])
    return data


@app.post("/api/project/create")
def project_create(body: ProjectCreateSchema):
    """Tạo thư mục dự án rỗng để tải video về (luồng dán link)."""
    try:
        data = project.tao_moi(body.thu_muc_cha, body.ten)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Không tạo được thư mục dự án: {e}")
    _nho_du_an(data["folder"], data["name"])
    return data


@app.post("/api/project/open")
def project_open(body: ProjectFolderSchema):
    data = project.doc(body.folder)
    if not data:
        raise HTTPException(status_code=404,
                            detail=f"Thư mục '{body.folder}' chưa phải là dự án.")
    _nho_du_an(data["folder"], data.get("name") or "")
    return data


@app.post("/api/project/undo-rename")
def project_undo_rename(body: ProjectFolderSchema):
    """Trả tên file về y như trước khi init, rồi bỏ đánh dấu dự án."""
    try:
        res = project.hoan_tac(body.folder)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Không trả lại tên file được: {e}")
    _quen_du_an(res["folder"])
    return res


@app.get("/api/project/videos")
def project_videos(folder: str, ke_ca_da_ghep: bool = False):
    if not project.da_init(folder):
        raise HTTPException(status_code=404, detail=f"Thư mục '{folder}' chưa phải là dự án.")
    return project.danh_sach_video(folder, ke_ca_da_ghep)


@app.get("/api/project/recent")
def project_recent():
    """Dự án gần đây — bỏ qua cái đã bị xoá hoặc chuyển đi chỗ khác."""
    du_an = (load_global_config().get("du_an") or {})
    gan_day = [r for r in (du_an.get("gan_day") or [])
               if r.get("folder") and project.da_init(r["folder"])]
    hien_tai = du_an.get("hien_tai") or ""
    if hien_tai and not project.da_init(hien_tai):
        hien_tai = ""
    return {"hien_tai": hien_tai, "gan_day": gan_day}


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


@app.post("/api/system/pick-files")
def pick_files(body: PickFilesSchema):
    """Mở hộp thoại chọn video của hệ điều hành, trả về đường dẫn thật.

    Trình duyệt không cho biết đường dẫn file người dùng chọn, và video vài GB
    thì không upload được — nên hộp thoại phải mở ở phía máy chủ. Chạy tiến
    trình riêng vì tkinter đòi luồng chính (xem `orchestrator/file_picker.py`).
    """
    mode = "folder" if (body.mode or "") == "folder" else "files"
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
def _chain_translate(enabled: bool, params: Optional[TranslateParams]) -> Optional[dict]:
    """Tham số cho khúc dịch nối sau khi tải/nhập (None = không bật)."""
    if not enabled:
        return None
    if process_mgr.is_running(TASK_TRANSLATE):
        raise HTTPException(
            status_code=400,
            detail="Đang có tác vụ dịch chạy — không thể bật 'dịch luôn sau khi tải'.")
    return (params or TranslateParams()).model_dump()


def _chain_merge(opts: Optional[MergeAfterSchema]) -> Optional[dict]:
    """Tham số cho khúc ghép ở cuối chuỗi (None = không bật).

    Chặn ngay tại đây nếu đang có lượt ghép khác: cả chuỗi chạy dưới task_key
    của khúc đầu nên tới lúc ghép mới phát hiện xung đột là đã muộn.
    """
    if not opts or not opts.enabled:
        return None
    if process_mgr.is_running(TASK_MERGE):
        raise HTTPException(
            status_code=400,
            detail="Đang có tác vụ ghép chạy — không thể bật 'ghép lại khi xong'.")
    return opts.model_dump()


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

    then_translate = _chain_translate(body.auto_translate, body.translate)
    then_merge = _chain_merge(body.merge_after)

    args = body.model_dump()
    args["batch_id"] = (body.batch_id or "").strip() or new_batch_id(body.batch_name or "")
    if not pipeline.start_download(TASK_DOWNLOAD, urls, args, then_translate, then_merge):
        raise HTTPException(status_code=500, detail="Không khởi động được tiến trình tải.")
    return {"status": "success", "task_key": TASK_DOWNLOAD, "batch_id": args["batch_id"]}


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

    files, sizes = [], []
    for item in body.items:
        try:
            files.append(library.find_file(item.entry_id, item.kind or "output", item.name or ""))
        except (FileNotFoundError, ValueError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        # W/H đọc sẵn từ video.json: máy đích không có ffprobe nên đây là cách
        # rẻ nhất để biết có phải chuẩn hoá trước khi nối hay không.
        entry = library.read_entry(item.entry_id) or {}
        sizes.append((entry.get("width") or 0, entry.get("height") or 0))

    if not pipeline.start_merge(TASK_MERGE, files, body.output_name or "", sizes,
                                "auto" if body.normalize else "never"):
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
    # Task chạy bằng thread (nhập hàng loạt, ghép) không có tiến trình con để
    # giết — chỉ đặt cờ, vòng lặp của nó tự thoát sau việc đang dở.
    if process_mgr.request_stop(task_key):
        return {"status": "success",
                "message": f"Đã yêu cầu dừng '{task_key}' — sẽ dừng sau khi xong việc đang dở."}
    raise HTTPException(status_code=404, detail=f"Không có tác vụ '{task_key}' đang chạy.")


# Giao diện web (đặt CUỐI để không nuốt mất các route /api/*)
webui_dir = os.path.abspath("webui")
if os.path.exists(webui_dir):
    app.mount("/", StaticFiles(directory=webui_dir, html=True), name="webui")
