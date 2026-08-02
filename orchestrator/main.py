import os
import sys
import json
import logging
from typing import Optional
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

# Add parent directory to sys.path to resolve orchestrator package imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator.config import load_global_config, save_global_config, load_ui_settings, save_ui_settings  # noqa: E402
from orchestrator.storage import StorageManager  # noqa: E402
from orchestrator.process_manager import ProcessManager  # noqa: E402
from orchestrator.pipeline import NovelPipeline  # noqa: E402
from orchestrator.auto_run import AutoRunManager  # noqa: E402
from orchestrator.chatbot import ChatManager  # noqa: E402
from orchestrator.llm import chat_stream_ollama, unload_ollama  # noqa: E402

app = FastAPI(title="AutoCartoon Novel-to-Video Maker Orchestrator")

# Allow CORS for developmental UI/debugging
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8100", "http://localhost:8100"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize singletons
# Thư mục dữ liệu (nặng) cấu hình được: người dùng có thể trỏ sang ổ/đường dẫn khác
# qua khóa "storage_dir" trong global_config.json (mặc định: ./storage).
_cfg = load_global_config()
_storage_dir = (_cfg.get("storage_dir") or "storage").strip() or "storage"
storage_mgr = StorageManager(base_storage_dir=_storage_dir)
process_mgr = ProcessManager()
pipeline = NovelPipeline(storage_mgr, process_mgr)
auto_run_mgr = AutoRunManager(storage_mgr, process_mgr, pipeline)
chat_mgr = ChatManager(storage_mgr, process_mgr, auto_run_mgr)

def _reject_if_auto_running(slug: str):
    """Các endpoint chạy bước lẻ không được chen vào khi chuỗi tự động đang chạy."""
    if auto_run_mgr.is_chain_running(slug):
        raise HTTPException(status_code=400,
                            detail="Chuỗi tự động đang chạy cho truyện này — bấm 'Dừng chuỗi' trước.")

# Pydantic Schemas
class GlobalConfigSchema(BaseModel):
    # extra="allow" để giữ nguyên các mục cấu hình mới (translate, autosub, ...)
    # mà không cần khai báo cứng từng khóa — hợp với việc Cấu Hình Chung mirror
    # toàn bộ tham số của mọi bước.
    model_config = ConfigDict(extra="allow")
    api_keys: dict
    storage_dir: str
    crawler: dict
    tts: dict
    video: dict
    translate: Optional[dict] = None
    autosub: Optional[dict] = None
    chatbot: Optional[dict] = None
    orchestrator_port: Optional[int] = None

class ChatRequestSchema(BaseModel):
    session_id: str
    message: str
    story_name: Optional[str] = ""
    active_tab: Optional[str] = ""
    mode: Optional[str] = "auto"
    force: Optional[bool] = False

class AgentQuerySchema(BaseModel):
    action: str
    args: Optional[dict] = None

class CreateStorySchema(BaseModel):
    story_name: str

class Step1Schema(BaseModel):
    story_name: str
    source_site: str
    base_url: Optional[str] = None
    story_id: Optional[str] = None
    local_folder: Optional[str] = None
    start_chapter_id: Optional[str] = None
    max_chapters: Optional[int] = 1
    engine: Optional[str] = None
    ollama_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_offline_base_url: Optional[str] = None
    gemini_offline_model: Optional[str] = None
    genre: Optional[str] = None
    auto_extract: bool = False
    auto_translate: bool = True
    continue_download: bool = False
    topic: Optional[str] = None  # nguồn "ai_write": chủ đề/ý tưởng để LLM sáng tác
    glossary_extract_engine: Optional[str] = "gemini"
    glossary_extract_ollama_model: Optional[str] = ""

class Step2Schema(BaseModel):
    story_name: str
    preset: Optional[str] = "default"
    engine: Optional[str] = None
    voice: Optional[str] = None
    speed: Optional[float] = None
    model: Optional[str] = None
    ref_audio: Optional[str] = None
    phonemize: Optional[bool] = None
    normalize: Optional[bool] = None
    target_lufs: Optional[float] = None
    fade_in: Optional[float] = None
    fade_out: Optional[float] = None
    silence_duration: Optional[float] = None
    device: Optional[str] = "cuda"
    use_cache: Optional[bool] = None
    cache_threshold: Optional[float] = None
    vieneu_mode: Optional[str] = None
    vieneu_emotion: Optional[str] = None
    temperature: Optional[float] = None

class Step3Schema(BaseModel):
    story_name: str
    genre: Optional[str] = "tien_hiep"
    style: Optional[str] = "anime_2d_flat"
    checkpoint: Optional[str] = "anything-v5"
    bgm_path: Optional[str] = ""
    bgm_volume: Optional[float] = 0.15
    enable_upscale: Optional[bool] = True
    burn_subtitles: Optional[bool] = False
    use_semantic_split: Optional[bool] = True
    extract_characters: Optional[bool] = True
    enable_face_detailer: Optional[bool] = False
    render_mode: Optional[str] = "classic"  # "classic" | "studio" (render theo lop)
    hardware_profile: Optional[str] = "auto"
    device: Optional[str] = "cuda"
    llm_engine: Optional[str] = "gemini_api"
    llm_api_key: Optional[str] = None
    llm_offline_base_url: Optional[str] = None
    llm_offline_model: Optional[str] = None

class Step4Schema(BaseModel):
    story_name: Optional[str] = None
    video_path: Optional[str] = None
    download_url: Optional[str] = None
    platform: Optional[str] = "generic"
    source_lang: Optional[str] = "English"
    sub_source: Optional[str] = "whisper"
    crop_x: Optional[int] = -1
    crop_y: Optional[int] = -1
    crop_w: Optional[int] = -1
    crop_h: Optional[int] = -1
    burn_method: Optional[str] = "ffmpeg"
    clean_audio: Optional[bool] = False
    enable_voiceover: Optional[bool] = False
    tts_engine: Optional[str] = "edge"
    tts_voice: Optional[str] = ""
    auto_clone: Optional[bool] = False
    ducking_ratio: Optional[float] = 90.0
    llm_engine: Optional[str] = "gemini_api"
    llm_api_key: Optional[str] = None
    llm_offline_base_url: Optional[str] = None
    llm_offline_model: Optional[str] = None
    
    # Subtitle Customization Styling fields
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
    cookies_file: Optional[str] = None
    output_dir: Optional[str] = None  # thư mục đầu ra (video tải về + video đã sub)

class Step5Schema(BaseModel):
    story_name: str
    selected_files: Optional[list[str]] = None

class PrepareSchema(BaseModel):
    video_path: Optional[str] = None
    download_url: Optional[str] = None
    platform: Optional[str] = "generic"
    cookies_file: Optional[str] = None

# API Endpoints

@app.get("/api/config")
def get_config():
    return load_global_config()

@app.get("/api/stats")
def get_stats():
    """Thống kê tổng hợp từ SQLite (phục vụ trang Dashboard)."""
    from orchestrator import db
    result = db.stats(storage_mgr.db_path)
    result["stories"] = db.list_stories(storage_mgr.db_path)
    result["storage_dir"] = storage_mgr.base_dir
    return result

@app.post("/api/maintenance/cleanup-tasks")
def cleanup_tasks_api(dry_run: bool = True, days: float = 0):
    """Dọn dẹp thư mục làm việc tạm (bảo vệ contexts). dry_run=true chỉ xem trước."""
    return storage_mgr.cleanup_tasks(keep_days=days, dry_run=dry_run)

@app.post("/api/maintenance/rebuild-db")
def rebuild_db_api():
    """Đồng bộ lại SQLite từ các story.json trên đĩa."""
    n = storage_mgr.rebuild_db()
    return {"synced": n}

@app.get("/api/system/gpu-info")
def get_gpu_info():
    import subprocess
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'], capture_output=True, text=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(', ')
            return {"name": parts[0], "vram": parts[1]}
        return {"name": "No GPU found", "vram": "N/A"}
    except Exception:
        return {"name": "No nvidia-smi", "vram": "N/A"}

@app.get("/api/ollama/models")
def get_ollama_models():
    """Danh sách model Ollama: các model đã cài trên máy + các model khuyến nghị."""
    import urllib.request
    import json as _json
    curated = {
        "qwen2.5:3b-instruct": "Chat siêu nhẹ ~2-3GB VRAM — khuyến nghị cho Bước 3 trên GPU 6GB",
        "hy-mt2:1.8b": "Chuyên dịch Trung/Anh→Việt, siêu nhẹ (khuyến nghị Bước 1)",
        "translategemma:4b": "Chuyên dịch Google, 55 ngôn ngữ",
        "qwen2.5:7b-instruct": "Model chat, chất lượng cao hơn nhưng ~5GB VRAM",
        "qwen3:8b": "Model chat, đã tối ưu giảm leak"
    }
    installed = []
    online = False
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as res:
            data = _json.loads(res.read().decode("utf-8"))
            installed = [m.get("name") for m in data.get("models", []) if m.get("name")]
            online = True
    except Exception:
        pass

    models = [{"name": n, "label": curated.get(n, ""), "installed": True} for n in installed]
    for name, label in curated.items():
        if name not in installed:
            models.append({"name": name, "label": label, "installed": False})
    return {"ollama_online": online, "models": models}

@app.post("/api/config")
def update_config(config: GlobalConfigSchema):
    if save_global_config(config.dict()):
        return {"status": "success", "config": config}
    raise HTTPException(status_code=500, detail="Failed to save global configuration.")

@app.get("/api/stories")
def get_stories():
    return storage_mgr.list_stories()

@app.post("/api/stories")
def create_story(body: CreateStorySchema):
    if not body.story_name.strip():
        raise HTTPException(status_code=400, detail="Story name cannot be empty.")
    try:
        dirs = storage_mgr.init_story_workspace(body.story_name)
        meta = storage_mgr.read_story_meta(body.story_name)
        return {"status": "success", "workspace": dirs, "meta": meta}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.get("/api/stories/{story_name}")
def get_story_details(story_name: str):
    meta = storage_mgr.read_story_meta(story_name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Story '{story_name}' not found.")
    return meta

def _build_step1_args(body: Step1Schema) -> dict:
    """Build crawl/trans args cho Bước 1 — dùng chung bởi endpoint lẻ và auto-run."""
    g_config = load_global_config()
    gemini_key = body.gemini_api_key or g_config.get("api_keys", {}).get("gemini", "")
    gemini_offline_base_url = body.gemini_offline_base_url or g_config.get("crawler", {}).get("gemini_offline_base_url", "http://localhost:7860/v1")

    crawl_args = {
        "source": body.source_site,
        "base_url": body.base_url,
        "story_id": body.story_id,
        "start_chapter_id": body.start_chapter_id,
        "num_chapters": body.max_chapters,
        "local_folder": body.local_folder,
        "topic": body.topic,  # nguồn "ai_write": chủ đề để LLM sáng tác
        "continue_download": body.continue_download
    }
    trans_args = {
        "auto_translate": body.auto_translate,
        "engine": body.engine or "gemini_api",
        "ollama_model": body.ollama_model or "qwen2.5:7b-instruct",
        "gemini_api_key": gemini_key,
        "gemini_offline_base_url": gemini_offline_base_url,
        "gemini_offline_model": body.gemini_offline_model or "gemini-2.5-flash",
        "genre": body.genre or "tien_hiep",
        "auto_extract": body.auto_extract,
        "glossary_extract_engine": body.glossary_extract_engine or "gemini",
        "glossary_extract_ollama_model": body.glossary_extract_ollama_model or ""
    }
    return {"crawl_args": crawl_args, "trans_args": trans_args}

def _build_step2_args(body: Step2Schema) -> dict:
    # Filter out None values so pipeline defaults apply
    return {k: v for k, v in body.dict().items() if v is not None}

@app.post("/api/pipeline/step1")
def run_step1(body: Step1Schema):
    # Check if any step is currently running for this story
    from orchestrator.storage import slugify
    slug = slugify(body.story_name)
    task_key = f"{slug}_step1"
    _reject_if_auto_running(slug)

    if process_mgr.is_running(task_key):
        raise HTTPException(status_code=400, detail="A crawl/translate process is already active for this story.")

    # Nguồn "Sáng tác bằng AI": xác thực chủ đề sớm cho thông báo rõ ràng; việc
    # sinh truyện bằng LLM do pipeline.start_step_1_crawl_translate định tuyến
    # (dùng chung một lối với chuỗi auto-run).
    if body.source_site == "ai_write" and not (body.topic or "").strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập chủ đề/ý tưởng để AI sáng tác truyện.")

    step1_args = _build_step1_args(body)
    success = pipeline.start_step_1_crawl_translate(
        body.story_name, step1_args["crawl_args"], step1_args["trans_args"])
    if success:
        return {"status": "success", "task_key": task_key}
    raise HTTPException(status_code=500, detail="Failed to start pipeline Step 1.")

@app.post("/api/pipeline/step2")
def run_step2(body: Step2Schema):
    from orchestrator.storage import slugify
    slug = slugify(body.story_name)
    task_key = f"{slug}_step2"
    
    _reject_if_auto_running(slug)
    if process_mgr.is_running(task_key):
        raise HTTPException(status_code=400, detail="A TTS process is already active for this story.")

    success = pipeline.start_step_2_tts(body.story_name, _build_step2_args(body))
    if success:
        return {"status": "success", "task_key": task_key}
    raise HTTPException(status_code=500, detail="Failed to start pipeline Step 2.")

@app.post("/api/pipeline/step3")
def run_step3(body: Step3Schema):
    from orchestrator.storage import slugify
    slug = slugify(body.story_name)
    task_key = f"{slug}_step3"
    
    _reject_if_auto_running(slug)
    if process_mgr.is_running(task_key):
        raise HTTPException(status_code=400, detail="A video generation process is already active for this story.")

    try:
        success = pipeline.start_step_3_video(body.story_name, body.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if success:
        return {"status": "success", "task_key": task_key}
    raise HTTPException(status_code=500, detail="Failed to start pipeline Step 3.")

@app.post("/api/pipeline/stop")
def stop_pipeline(story_name: str, step: int):
    from orchestrator.storage import slugify
    slug = slugify(story_name)
    task_key = f"{slug}_step{step}"
    
    if process_mgr.stop_process(task_key):
        # Update metadata state
        meta = storage_mgr.read_story_meta(story_name)
        if meta:
            meta["status"] = "CANCELLED"
            storage_mgr.write_story_meta(story_name, meta)
        return {"status": "success", "task_key": task_key,
                "message": f"Successfully stopped task '{task_key}'."}

    raise HTTPException(status_code=404, detail=f"No active running task found for key '{task_key}'.")

@app.get("/api/pipeline/logs/{task_key}")
def stream_logs(task_key: str):
    """Real-time logs streaming using Server-Sent Events (SSE)."""
    return StreamingResponse(
        process_mgr.get_logs_generator(task_key),
        media_type="text/event-stream"
    )


@app.get("/api/pipeline/status/{task_key}")
def pipeline_task_status(task_key: str):
    """Cho frontend kiểm tra task khi EventSource tạm ngắt/kết thúc."""
    return process_mgr.get_task_status(task_key)

# ---------------------- Chuỗi chạy tự động Bước 1→4 ----------------------

class AutoRunSchema(BaseModel):
    story_name: str
    step1: Step1Schema
    step2: Step2Schema
    step3: Step3Schema

@app.post("/api/pipeline/auto-run")
def start_auto_run(body: AutoRunSchema):
    ok, msg = auto_run_mgr.start(
        body.story_name,
        _build_step1_args(body.step1),
        _build_step2_args(body.step2),
        body.step3.dict(),
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}

@app.get("/api/pipeline/auto-run/{story_name}")
def auto_run_status(story_name: str):
    return auto_run_mgr.status(story_name)

@app.post("/api/pipeline/auto-run/stop")
def stop_auto_run(story_name: str):
    if auto_run_mgr.stop(story_name):
        return {"status": "success", "message": "Đã gửi yêu cầu dừng chuỗi tự động."}
    raise HTTPException(status_code=404, detail="Không có chuỗi tự động nào đang chạy cho truyện này.")

# ---------------------- Lưu/khôi phục toàn bộ cấu hình UI ----------------------

@app.get("/api/ui-settings")
def get_ui_settings():
    return load_ui_settings()

@app.post("/api/ui-settings")
def update_ui_settings(settings: dict):
    if save_ui_settings(settings):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Không ghi được configs/ui_settings.json.")

@app.post("/api/system/clear-cache")
def clear_semantic_cache():
    import shutil
    import os
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_dir = os.path.join(repo_root, "AIVoice", "storage", "cache")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            return {"status": "success", "message": "Đã xóa toàn bộ bộ đệm Semantic Cache thành công."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {"status": "success", "message": "Không tìm thấy bộ đệm cache nào để xóa."}

@app.post("/api/pipeline/step4")
def run_step4(body: Step4Schema):
    if not body.video_path and not body.download_url:
        raise HTTPException(status_code=400, detail="Cần cung cấp video_path hoặc download_url.")
        
    from orchestrator.storage import slugify
    import uuid
    
    slug = ""
    if body.story_name:
        slug = slugify(body.story_name)
        task_key = f"{slug}_step4"
    else:
        task_id = uuid.uuid4().hex[:8]
        task_key = f"autosub_{task_id}_step4"
        
    if process_mgr.is_running(task_key):
        raise HTTPException(status_code=400, detail="Tiến trình Autosub đang chạy cho truyện/tác vụ này.")
        
    autosub_args = {k: v for k, v in body.dict().items() if v is not None}
    
    if not body.story_name:
        autosub_args["task_id"] = task_id
        
    try:
        success = pipeline.start_step_4_autosub(body.story_name, autosub_args)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    if success:
        return {"status": "success", "task_key": task_key}
    raise HTTPException(status_code=500, detail="Không khởi tạo được pipeline Bước 4.")

@app.post("/api/autosub/prepare")
def autosub_prepare(body: PrepareSchema):
    import subprocess
    import uuid
    import base64
    import json as _json
    
    if not body.video_path and not body.download_url:
        raise HTTPException(status_code=400, detail="Cần cung cấp video_path hoặc download_url.")
        
    task_id = uuid.uuid4().hex[:8]
    work_dir = os.path.join(storage_mgr.tasks_dir, f"autosub_{task_id}")
    os.makedirs(work_dir, exist_ok=True)
    
    python_exe = os.path.abspath("AIVoice/.venv/Scripts/python.exe")
    adapter = os.path.abspath("AIVoice/apps/MediaComposer/adapter_autosub_cli.py")
    
    cmd = [python_exe, adapter, "--prepare-only", "--output-dir", work_dir]
    if body.download_url:
        cmd += ["--download-url", body.download_url, "--platform", body.platform or "generic"]
    else:
        cmd += ["--video-path", body.video_path]
        
    from orchestrator.config import load_global_config
    g_config = load_global_config()
    resolved_cookies = body.cookies_file or g_config.get("video", {}).get("downloader_cookies", "")
    if resolved_cookies:
        cmd += ["--cookies-file", resolved_cookies]
        
    try:
        res = subprocess.run(cmd, cwd="AIVoice", capture_output=True, text=True, encoding="utf-8", timeout=900,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Tải/chuẩn bị video quá 15 phút — kiểm tra link hoặc mạng.")
        
    if res.returncode != 0:
        err_msg = res.stderr[-1000:] if res.stderr else (res.stdout[-1000:] if res.stdout else "No output")
        raise HTTPException(status_code=500, detail=f"Lỗi prepare_only: {err_msg}")
        
    info = None
    for line in res.stdout.splitlines():
        if line.strip():
            try:
                data = _json.loads(line)
                if data.get("event") == "prepare_done":
                    info = data
                    break
            except _json.JSONDecodeError:
                continue
                
    if not info:
        err_msg = res.stdout[-1000:] if res.stdout else "No output"
        raise HTTPException(status_code=500, detail=f"Không nhận được phản hồi prepare_done. Log: {err_msg}")
        
    preview_img_path = info.get("preview_image")
    if not preview_img_path or not os.path.exists(preview_img_path):
        raise HTTPException(status_code=500, detail="Không tạo được ảnh xem trước.")
        
    with open(preview_img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
        
    return {
        "task_id": task_id,
        "prepared_path": info.get("prepared_path"),
        "width": info.get("width"),
        "height": info.get("height"),
        "duration": info.get("duration"),
        "preview_b64": f"data:image/jpeg;base64,{img_b64}"
    }

@app.post("/api/pipeline/step5")
def run_step5(body: Step5Schema):
    from orchestrator.storage import slugify
    slug = slugify(body.story_name)
    task_key = f"{slug}_step5"
    _reject_if_auto_running(slug)

    if process_mgr.is_running(task_key):
        raise HTTPException(status_code=400, detail="Tiến trình Ghép Video đang chạy.")
        
    try:
        success = pipeline.start_step_5_merge(body.story_name, body.selected_files)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    if success:
        return {"status": "success", "task_key": task_key}
    raise HTTPException(status_code=500, detail="Không khởi tạo được pipeline Bước 5.")

@app.get("/api/stories/{story_name}/videos")
def get_story_videos(story_name: str):
    import glob

    story_dir = storage_mgr.get_story_dir(story_name)
    if not os.path.exists(story_dir):
        raise HTTPException(status_code=404, detail="Truyện không tồn tại.")
        
    video_dir = os.path.join(story_dir, "video")
    if not os.path.exists(video_dir):
        return []
        
    mp4_files = sorted(glob.glob(os.path.join(video_dir, "*.mp4")))
    
    videos = []
    for f in mp4_files:
        name = os.path.basename(f)
        size = os.path.getsize(f)
        is_merged = name.startswith("TongHop_")
        videos.append({
            "name": name,
            "size": size,
            "is_merged": is_merged
        })
    return videos

@app.post("/api/pipeline/stop-task")
def stop_task(task_key: str):
    if process_mgr.stop_process(task_key):
        try:
            parts = task_key.rsplit("_", 1)
            if len(parts) == 2 and parts[1].startswith("step"):
                slug = parts[0]
                stories = storage_mgr.list_stories()
                for s in stories:
                    if s.get("story_slug") == slug:
                        story_name = s.get("story_name")
                        meta = storage_mgr.read_story_meta(story_name)
                        if meta:
                            meta["status"] = "CANCELLED"
                            storage_mgr.write_story_meta(story_name, meta)
                        break
        except Exception:
            pass
            
        return {"status": "success", "message": f"Successfully stopped task '{task_key}'."}
        
    raise HTTPException(status_code=404, detail=f"No active running task found for key '{task_key}'.")

# ------------------------------------------------------------------ Chatbot API
@app.get("/api/chat/health")
def get_chat_health():
    cfg = load_global_config().get("chatbot", {})
    base_url = cfg.get("base_url") or _cfg.get("crawler", {}).get("ollama_base_url") or "http://localhost:11434/v1"
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]

    want_model = cfg.get("model", "qwen2.5:3b")
    ollama_online = False
    model_loaded = False   # đã nạp sẵn trong VRAM (/api/ps)
    model_installed = False  # đã pull về đĩa (/api/tags)

    def _same_tag(a: str, b: str) -> bool:
        """Ollama coi 'foo' và 'foo:latest' là một."""
        norm = lambda s: s if ":" in s else f"{s}:latest"  # noqa: E731
        return norm(a) == norm(b)

    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.get(f"{root}/api/ps")
            if r.status_code == 200:
                ollama_online = True
                names = [m.get("name", "") for m in r.json().get("models", [])]
                model_loaded = any(_same_tag(want_model, n) for n in names)

            # model_installed phải HỎI THẬT /api/tags. Trước đây giá trị này bị
            # hardcode True, nên khi model chưa pull thì badge vẫn xanh và người
            # dùng chỉ phát hiện ra khi câu hỏi đầu tiên trả về 404.
            rt = client.get(f"{root}/api/tags")
            if rt.status_code == 200:
                ollama_online = True
                installed = [m.get("name", "") for m in rt.json().get("models", [])]
                model_installed = any(_same_tag(want_model, n) for n in installed)
    except Exception:
        pass

    gpu_weight, busy_tasks = chat_mgr.get_gpu_weight()
    return {
        "ollama_online": ollama_online,
        "model": want_model,
        "model_installed": model_installed,
        "model_loaded": model_loaded,
        "busy": gpu_weight != "none",
        "busy_tasks": busy_tasks,
        "gpu_weight": gpu_weight,
        "lookup_only": gpu_weight == "heavy"
    }

@app.get("/api/system/busy")
def get_system_busy():
    gpu_weight, tasks = chat_mgr.get_gpu_weight()
    chains = auto_run_mgr.list_running_chains()
    return {
        "running": len(tasks) > 0,
        "tasks": tasks,
        "chains": chains,
        "gpu_weight": gpu_weight
    }

@app.post("/api/chat")
async def post_chat(body: ChatRequestSchema, request: Request):
    cfg = load_global_config().get("chatbot", {})
    if not cfg.get("enabled", True):
        raise HTTPException(status_code=503, detail="Trợ lý AI đang bị tắt trong Cấu Hình Chung.")

    acquired = chat_mgr.single_chat_lock.acquire(blocking=False)
    if not acquired:
        raise HTTPException(status_code=429, detail="Trợ lý đang trả lời câu trước.")

    try:
        gpu_weight, busy_tasks = chat_mgr.get_gpu_weight()
        block_when_busy = cfg.get("block_when_busy", True)

        if block_when_busy and gpu_weight == "heavy" and not body.force and body.mode != "lookup":
            chat_mgr.single_chat_lock.release()
            lookup_ans = chat_mgr.lookup_only(body.message, body.active_tab or "")
            return JSONResponse(
                status_code=409,
                content={
                    "detail": "Pipeline GPU bận",
                    "busy_tasks": busy_tasks,
                    "lookup_answer": lookup_ans
                }
            )

        action, action_args = chat_mgr.route_intent(body.message, body.story_name or "")
        if action != "chat":
            if action in ["run_step", "select_story"]:
                chat_mgr.single_chat_lock.release()

                # PHẢI trả NDJSON có newline cuối như mọi nhánh khác.
                # Trước đây nhánh này trả JSONResponse thuần (application/json,
                # không newline). Client tách stream theo "\n" rồi lop() dòng cuối
                # chưa hoàn chỉnh vào buffer, nên gói JSON duy nhất không bao giờ
                # được xử lý — widget đứng mãi ở dấu "..." khi người dùng gõ lệnh.
                async def generate_agent_action():
                    yield json.dumps({
                        "agent_action": action,
                        "args": action_args,
                        "message": f"Yêu cầu thực thi lệnh {action}",
                        "done": True,
                    }) + "\n"

                return StreamingResponse(
                    generate_agent_action(), media_type="application/x-ndjson"
                )
            elif action in ["list_stories", "story_report", "system_status"]:
                res = chat_mgr.agent_query(action, action_args)
                chat_mgr.single_chat_lock.release()
                async def generate_agent_l1():
                    yield json.dumps({"delta": "Dưới đây là thông tin bạn yêu cầu:\n"}) + "\n"
                    yield json.dumps({"agent_result": res, "done": True, "prompt_tokens": 0, "truncated": False}) + "\n"
                return StreamingResponse(generate_agent_l1(), media_type="application/x-ndjson")

        if body.mode == "lookup" or (gpu_weight == "heavy" and not body.force):
            lookup_ans = chat_mgr.lookup_only(body.message, body.active_tab or "")
            chat_mgr.single_chat_lock.release()
            async def generate_lookup():
                yield json.dumps({"delta": lookup_ans["answer"]}) + "\n"
                yield json.dumps({"done": True, "prompt_tokens": 0, "truncated": False, "mode": "lookup", "sources": lookup_ans["sources"]}) + "\n"
            return StreamingResponse(generate_lookup(), media_type="application/x-ndjson")

        session = chat_mgr.get_or_create_session(
            body.session_id,
            max_sessions=cfg.get("max_sessions", 20),
            ttl_minutes=cfg.get("session_ttl_minutes", 120)
        )

        kb_sections, max_score = chat_mgr.select_kb(
            query=body.message,
            active_tab=body.active_tab or "",
            sticky_kb=session.get("sticky_kb") if cfg.get("kb_sticky_per_session", True) else None,
            token_budget=cfg.get("kb_token_budget", 3000),
            min_score=cfg.get("kb_min_score", 0.50)
        )
        if cfg.get("kb_sticky_per_session", True) and kb_sections:
            session["sticky_kb"] = kb_sections

        min_score = cfg.get("kb_min_score", 0.50)
        if max_score < min_score and "truyện" not in body.message.lower() and "story" not in body.message.lower():
            chat_mgr.single_chat_lock.release()
            refusal_text = (
                "Tài liệu hiện có không đề cập nội dung này.\n\n"
                "📌 **Các mục bạn có thể tham khảo:**\n"
                "- `00-tong-quan.md`: Quy trình 5 bước\n"
                "- `06-cau-hinh.md`: Cấu hình chung\n"
                "- `07-su-co-thuong-gap.md`: FAQ giải quyết lỗi\n"
            )
            async def generate_gate_refusal():
                yield json.dumps({"delta": refusal_text}) + "\n"
                yield json.dumps({"done": True, "prompt_tokens": 0, "truncated": False, "gate_refusal": True}) + "\n"
            return StreamingResponse(generate_gate_refusal(), media_type="application/x-ndjson")

        story_ctx = chat_mgr.build_story_context(body.story_name or "")
        system_prompt = chat_mgr.build_system_prompt(kb_sections, story_ctx)

        messages = [{"role": "system", "content": system_prompt}]
        history = session.get("messages", [])
        max_turns = cfg.get("max_history_turns", 12)
        recent_history = history[-(max_turns * 2):]
        messages.extend(recent_history)
        messages.append({"role": "user", "content": body.message})

        base_url = cfg.get("base_url") or _cfg.get("crawler", {}).get("ollama_base_url") or "http://localhost:11434/v1"
        model = cfg.get("model", "qwen2.5:3b")
        num_ctx = cfg.get("num_ctx", 8192)

        async def generate_chat():
            full_response = ""
            try:
                async for chunk in chat_stream_ollama(
                    base_url=base_url,
                    model=model,
                    messages=messages,
                    temperature=cfg.get("temperature", 0.4),
                    top_p=cfg.get("top_p", 0.9),
                    repeat_penalty=cfg.get("repeat_penalty", 1.05),
                    num_predict=cfg.get("num_predict", 512),
                    num_ctx=num_ctx,
                ):
                    if await request.is_disconnected():
                        logger.info("[Chatbot] Client ngắt kết nối giữa stream.")
                        break

                    if "delta" in chunk:
                        full_response += chunk["delta"]
                    yield json.dumps(chunk) + "\n"

                if full_response:
                    session["messages"].append({"role": "user", "content": body.message})
                    session["messages"].append({"role": "assistant", "content": full_response})
            except Exception as ex:
                logger.error(f"[Chatbot] Lỗi stream chat: {ex}")
                yield json.dumps({"error": str(ex)}) + "\n"
            finally:
                chat_mgr.single_chat_lock.release()

        return StreamingResponse(generate_chat(), media_type="application/x-ndjson")

    except HTTPException:
        chat_mgr.single_chat_lock.release()
        raise
    except Exception as e:
        chat_mgr.single_chat_lock.release()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/unload")
def unload_chat_endpoint():
    cfg = load_global_config().get("chatbot", {})
    base_url = cfg.get("base_url") or _cfg.get("crawler", {}).get("ollama_base_url") or "http://localhost:11434/v1"
    model = cfg.get("model", "")
    ok = unload_ollama(base_url, model)
    return {"status": "success" if ok else "failed"}

@app.delete("/api/chat/sessions/{session_id}")
def delete_chat_session_endpoint(session_id: str):
    if session_id in chat_mgr.sessions:
        del chat_mgr.sessions[session_id]
        return {"status": "success"}
    return {"status": "not_found"}

@app.post("/api/chat/prewarm")
async def prewarm_chat_model():
    cfg = load_global_config().get("chatbot", {})
    if not cfg.get("prewarm_on_open", True):
        return {"status": "disabled"}

    gpu_weight, _ = chat_mgr.get_gpu_weight()
    if gpu_weight == "heavy":
        return {"status": "busy_skipped"}

    base_url = cfg.get("base_url") or _cfg.get("crawler", {}).get("ollama_base_url") or "http://localhost:11434/v1"
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    model = cfg.get("model", "qwen2.5:3b")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(f"{root}/api/generate", json={"model": model, "keep_alive": "5m"})
            return {"status": "prewarmed", "model": model}
    except Exception as e:
        logger.warning(f"[Chatbot] Prewarm failed: {e}")
        return {"status": "failed", "error": str(e)}

@app.post("/api/agent/query")
def agent_query_endpoint(body: AgentQuerySchema):
    return chat_mgr.agent_query(body.action, body.args or {})

# Serve Web UI assets directly
webui_dir = os.path.abspath("webui")
if os.path.exists(webui_dir):
    app.mount("/", StaticFiles(directory=webui_dir, html=True), name="webui")
