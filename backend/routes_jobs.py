"""Routes ảnh -> 3D: upload ảnh (raw body), theo dõi tiến độ (SSE), huỷ, tải GLB kết quả."""
import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from backend.ai_environment import AI_PYTHON, HF_HOME, WORKER_IMAGE_TO_3D, get_ai_status
from backend.config import ROOT_DIR, load_config
from backend.job_runner import JobRunner
from backend.ollama_unload import unload_all_models

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
MAX_IMAGE_BYTES = 25 * 1024 * 1024

router = APIRouter(prefix="/api")
_config = load_config()
runner = JobRunner(
    python_exe=AI_PYTHON,
    worker_script=WORKER_IMAGE_TO_3D,
    jobs_dir=ROOT_DIR / "output" / "jobs",
    presets=_config["quality_presets"],
    env={"HF_HOME": str(HF_HOME), "U2NET_HOME": str(ROOT_DIR / "models" / "u2net")},
    before_gpu_job=lambda: unload_all_models(_config["ollama"]["url"]),
)


@router.get("/system/ai-status")
def ai_status():
    return get_ai_status()


@router.post("/image-to-3d")
async def image_to_3d(request: Request, filename: str, quality: str = "balanced"):
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(400, "Chỉ nhận ảnh PNG, JPG hoặc WEBP")
    if quality not in _config["quality_presets"]:
        raise HTTPException(400, "Mức chất lượng không hợp lệ")
    data = await request.body()
    if not data:
        raise HTTPException(400, "Ảnh rỗng")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Ảnh quá lớn (tối đa 25 MB)")
    if not get_ai_status()["ready"]:
        raise HTTPException(409, get_ai_status()["message"])
    return runner.submit_image_to_3d(data, ext, quality).public()


def _job_or_404(job_id: str):
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(404, "Không tìm thấy job")
    return job


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    return _job_or_404(job_id).public()


@router.post("/jobs/{job_id}/cancel")
def job_cancel(job_id: str):
    return {"cancelled": runner.cancel(_job_or_404(job_id).id)}


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    job = _job_or_404(job_id)

    async def stream():
        sent = 0
        while True:
            while sent < len(job.events):
                yield f"data: {json.dumps(job.events[sent], ensure_ascii=False)}\n\n"
                sent += 1
            if job.finished and sent >= len(job.events):
                return
            await asyncio.sleep(0.3)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@router.get("/jobs/{job_id}/result.glb")
def job_result(job_id: str):
    job = _job_or_404(job_id)
    path = job.work_dir / "mesh.glb"
    if job.status != "done" or not path.exists():
        raise HTTPException(404, "Chưa có kết quả")
    return FileResponse(path, media_type="model/gltf-binary")
