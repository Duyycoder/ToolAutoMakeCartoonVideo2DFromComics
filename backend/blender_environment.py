"""Tìm Blender portable (scripts/setup-blender.bat tải vào tools/blender/) cho các tính năng chạy Blender ẩn."""
import re
from pathlib import Path

from backend.config import ROOT_DIR

BLENDER_DIR = ROOT_DIR / "tools" / "blender"
BLENDER_OPS = ROOT_DIR / "blender_ops" / "run_op.py"
SETUP_HINT = "Chưa cài Blender — chạy scripts\\setup-blender.bat (tải ~405 MB) rồi mở lại Easy3D."


def _version_key(folder: str) -> tuple:
    """blender-5.2.3-windows-x64 -> (5, 2, 3). So theo SỐ: so chuỗi thì "10.0" đứng trước "5.2"."""
    match = re.search(r"\d+(?:\.\d+)*", folder)
    return tuple(int(x) for x in match.group(0).split(".")) if match else ()


def find_blender() -> Path | None:
    """Bản mới nhất trong tools/blender/*/blender.exe (Linux: */blender). Đặt sẵn bản khác cũng được."""
    exes = [p for p in BLENDER_DIR.glob("*/blender*") if p.name in ("blender.exe", "blender") and p.is_file()]
    found = sorted(exes, key=lambda p: _version_key(p.parent.name))
    return found[-1] if found else None


def get_blender_status() -> dict:
    exe = find_blender()
    return {"ready": exe is not None, "path": str(exe) if exe else None,
            "message": "Sẵn sàng." if exe else SETUP_HINT}
