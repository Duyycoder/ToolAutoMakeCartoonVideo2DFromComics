"""Tìm Blender portable (scripts/setup-blender.bat tải vào tools/blender/) cho các tính năng chạy Blender ẩn."""
from pathlib import Path

from backend.config import ROOT_DIR

BLENDER_DIR = ROOT_DIR / "tools" / "blender"
BLENDER_OPS = ROOT_DIR / "blender_ops" / "run_op.py"
SETUP_HINT = "Chưa cài Blender — chạy scripts\\setup-blender.bat (tải ~383 MB) rồi mở lại Easy3D."


def find_blender() -> Path | None:
    """Bản mới nhất trong tools/blender/*/blender.exe (đặt sẵn bản khác cũng được)."""
    found = sorted(BLENDER_DIR.glob("*/blender.exe"))
    return found[-1] if found else None


def get_blender_status() -> dict:
    exe = find_blender()
    return {"ready": exe is not None, "path": str(exe) if exe else None,
            "message": "Sẵn sàng." if exe else SETUP_HINT}
