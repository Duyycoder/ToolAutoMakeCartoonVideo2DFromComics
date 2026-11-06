"""FastAPI backend Easy3D. Chỉ bind 127.0.0.1. KHÔNG import torch ở đây —
AI chạy trong subprocess .venv-ai (backend/job_runner.py)."""
from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend import routes_files, routes_jobs
from backend.config import WEBUI_DIR
from backend.gpu_info import get_gpu_info

CSRF_HEADER = "x-easy3d"

app = FastAPI(title="Easy3D")
# Chống DNS rebinding: chỉ nhận Host là localhost.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


@app.middleware("http")
async def require_custom_header_for_writes(request: Request, call_next):
    """Trang web lạ có thể POST "simple request" tới 127.0.0.1 mà không cần preflight.
    Bắt buộc header riêng -> trình duyệt phải preflight -> bị chặn vì không bật CORS."""
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(CSRF_HEADER) != "1":
        return JSONResponse({"detail": "Thiếu header X-Easy3D"}, status_code=403)
    return await call_next(request)


app.include_router(routes_jobs.router)
app.include_router(routes_files.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/system/gpu-info")
def gpu_info():
    return get_gpu_info()


# Mount cuối cùng để không che các route /api.
app.mount("/", StaticFiles(directory=WEBUI_DIR, html=True), name="webui")
