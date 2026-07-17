import os
import sys
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add parent directory to sys.path to resolve orchestrator package imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator.config import load_global_config, save_global_config
from orchestrator.storage import StorageManager
from orchestrator.process_manager import ProcessManager
from orchestrator.pipeline import NovelPipeline

app = FastAPI(title="AutoCartoon Novel-to-Video Maker Orchestrator")

# Allow CORS for developmental UI/debugging
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize singletons
storage_mgr = StorageManager(base_storage_dir="storage")
process_mgr = ProcessManager()
pipeline = NovelPipeline(storage_mgr, process_mgr)

# Pydantic Schemas
class GlobalConfigSchema(BaseModel):
    api_keys: dict
    storage_dir: str
    crawler: dict
    tts: dict
    video: dict

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

@app.get("/api/system/gpu-info")
def get_gpu_info():
    import subprocess
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'], capture_output=True, text=True)
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

@app.post("/api/pipeline/step1")
def run_step1(body: Step1Schema):
    # Check if any step is currently running for this story
    from orchestrator.storage import slugify
    slug = slugify(body.story_name)
    task_key = f"{slug}_step1"
    
    if process_mgr.is_running(task_key):
        raise HTTPException(status_code=400, detail="A crawl/translate process is already active for this story.")

    # Override api keys from global config if empty in body
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

    success = pipeline.start_step_1_crawl_translate(body.story_name, crawl_args, trans_args)
    if success:
        return {"status": "success", "task_key": task_key}
    raise HTTPException(status_code=500, detail="Failed to start pipeline Step 1.")

@app.post("/api/pipeline/step2")
def run_step2(body: Step2Schema):
    from orchestrator.storage import slugify
    slug = slugify(body.story_name)
    task_key = f"{slug}_step2"
    
    if process_mgr.is_running(task_key):
        raise HTTPException(status_code=400, detail="A TTS process is already active for this story.")

    # Convert schema to dict, filtering out None values so pipeline defaults apply
    tts_args = {k: v for k, v in body.dict().items() if v is not None}

    success = pipeline.start_step_2_tts(body.story_name, tts_args)
    if success:
        return {"status": "success", "task_key": task_key}
    raise HTTPException(status_code=500, detail="Failed to start pipeline Step 2.")

@app.post("/api/pipeline/step3")
def run_step3(body: Step3Schema):
    from orchestrator.storage import slugify
    slug = slugify(body.story_name)
    task_key = f"{slug}_step3"
    
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
        return {"status": "success", "message": f"Successfully stopped task '{task_key}'."}
    
    raise HTTPException(status_code=404, detail=f"No active running task found for key '{task_key}'.")

@app.get("/api/pipeline/logs/{task_key}")
def stream_logs(task_key: str):
    """Real-time logs streaming using Server-Sent Events (SSE)."""
    return StreamingResponse(
        process_mgr.get_logs_generator(task_key),
        media_type="text/event-stream"
    )

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
        res = subprocess.run(cmd, cwd="AIVoice", capture_output=True, text=True, encoding="utf-8", timeout=900)
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
            except:
                pass
                
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
    from orchestrator.storage import slugify
    import glob
    
    slug = slugify(story_name)
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

# Serve Web UI assets directly
webui_dir = os.path.abspath("webui")
if os.path.exists(webui_dir):
    app.mount("/", StaticFiles(directory=webui_dir, html=True), name="webui")
