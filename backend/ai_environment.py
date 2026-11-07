"""Kiểm tra môi trường AI (.venv-ai + TripoSR + trọng số) — để UI báo rõ cho người dùng
thay vì bấm "Tạo từ ảnh" rồi mới lỗi."""
import os
from pathlib import Path

from backend.config import ROOT_DIR
from backend.gpu_info import query_nvidia_gpus


def venv_python(name: str) -> Path:
    """Python trong venv: Windows `Scripts/python.exe`, Linux `bin/python` (bản online, scripts/setup-ai-linux.sh)."""
    return ROOT_DIR / name / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


AI_PYTHON = venv_python(".venv-ai")
TRIPOSR_DIR = ROOT_DIR / "third_party" / "TripoSR"
HF_HOME = ROOT_DIR / "models" / "hf"
WORKER_IMAGE_TO_3D = ROOT_DIR / "workers" / "worker_image_to_3d.py"

# Hunyuan3D-2mini (chất lượng cao): venv + mã nguồn + trọng số RIÊNG (scripts/setup-hunyuan3d.bat).
HUNYUAN_PYTHON = venv_python(".venv-hunyuan")
HUNYUAN_DIR = ROOT_DIR / "third_party" / "Hunyuan3D-2"
HUNYUAN_MODELS = ROOT_DIR / "models" / "hy3dgen"
HUNYUAN_WEIGHTS = HUNYUAN_MODELS / "tencent" / "Hunyuan3D-2mini" / "hunyuan3d-dit-v2-mini" / "model.fp16.safetensors"
WORKER_HUNYUAN = ROOT_DIR / "workers" / "worker_hunyuan3d.py"


def _weights_downloaded(hf_home: Path) -> bool:
    snapshots = hf_home / "hub" / "models--stabilityai--TripoSR" / "snapshots"
    return snapshots.exists() and any(snapshots.glob("*/model.ckpt"))


def get_ai_status() -> dict:
    checks = {
        "python": AI_PYTHON.exists(),
        "triposr": (TRIPOSR_DIR / "tsr").exists(),
        "weights": _weights_downloaded(HF_HOME),
    }
    ready = all(checks.values())
    cuda = bool(query_nvidia_gpus())
    if not ready:
        # Chi tiết kỹ thuật nằm trong `checks`; thông báo cho người dùng chỉ nói cần làm gì.
        message = "Phần AI chưa được cài trên máy này. Hãy đóng Easy3D, chạy setup.bat rồi mở lại."
    elif not cuda:
        message = "Không có GPU NVIDIA — AI chạy bằng CPU, mỗi mô hình mất vài phút."
    else:
        message = "Sẵn sàng."
    hunyuan = all((HUNYUAN_PYTHON.exists(), (HUNYUAN_DIR / "hy3dgen").exists(), HUNYUAN_WEIGHTS.exists()))
    models = {
        "triposr": {"ready": ready, "message": message},
        "hunyuan": {"ready": hunyuan, "message": "Sẵn sàng." if hunyuan else
                    "Chưa cài Hunyuan3D — chạy scripts\setup-hunyuan3d.bat (tải ~4 GB, cần GPU NVIDIA)."},
    }
    return {"ready": ready, "cuda": cuda, "checks": checks, "message": message, "models": models}
