"""Kiểm tra môi trường AI (.venv-ai + TripoSR + trọng số) — để UI báo rõ cho người dùng
thay vì bấm "Tạo từ ảnh" rồi mới lỗi."""
from pathlib import Path

from backend.config import ROOT_DIR
from backend.gpu_info import query_nvidia_gpus

AI_PYTHON = ROOT_DIR / ".venv-ai" / "Scripts" / "python.exe"
TRIPOSR_DIR = ROOT_DIR / "third_party" / "TripoSR"
HF_HOME = ROOT_DIR / "models" / "hf"
WORKER_IMAGE_TO_3D = ROOT_DIR / "workers" / "worker_image_to_3d.py"


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
    return {"ready": ready, "cuda": cuda, "checks": checks, "message": message}
