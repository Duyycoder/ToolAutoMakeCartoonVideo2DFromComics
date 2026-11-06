"""FastAPI backend Easy3D. Chỉ bind 127.0.0.1. KHÔNG import torch ở đây.

Phase 01: health + gpu-info + phục vụ webui. Job queue/worker thêm ở Phase 03.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import WEBUI_DIR, load_config
from backend.gpu_info import get_gpu_info

app = FastAPI(title="Easy3D")
CONFIG = load_config()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/system/gpu-info")
def gpu_info():
    return get_gpu_info()


# Mount cuối cùng để không che các route /api.
app.mount("/", StaticFiles(directory=WEBUI_DIR, html=True), name="webui")
