"""Lưu file do UI gửi lên (project, file xuất) vào thư mục cố định trong repo.

Lưu qua backend thay vì "download" của trình duyệt vì cửa sổ pywebview không có hộp thoại
tải xuống. Mọi tên file đều được làm sạch -> không thể ghi ra ngoài thư mục cho phép.
"""
import os
import re
import subprocess
from pathlib import Path

from backend.config import ROOT_DIR

FOLDERS = {
    "projects": ROOT_DIR / "projects",
    "output": ROOT_DIR / "output" / "exports",
}
ALLOWED_EXTENSIONS = {".glb", ".gltf", ".stl", ".obj", ".png", ".mp4", ".webm"}  # video: thanh Chuyển động
MAX_BYTES = 200 * 1024 * 1024


class StorageError(ValueError):
    pass


def safe_filename(name: str) -> str:
    """Giữ chữ (kể cả tiếng Việt), số, khoảng trắng, - _ . ; bỏ mọi ký tự đường dẫn."""
    base = Path(name.replace("\\", "/")).name
    base = re.sub(r"[^\w\s.\-]", "", base, flags=re.UNICODE).strip(" .")
    if not base:
        raise StorageError("Tên file không hợp lệ")
    return base[:120]


def folder_for(kind: str) -> Path:
    if kind not in FOLDERS:
        raise StorageError(f"Thư mục không hợp lệ: {kind}")
    folder = FOLDERS[kind]
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_bytes(kind: str, name: str, data: bytes) -> Path:
    filename = safe_filename(name)
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise StorageError(f"Không hỗ trợ định dạng {Path(filename).suffix or '(trống)'}")
    if not data:
        raise StorageError("File rỗng")
    if len(data) > MAX_BYTES:
        raise StorageError("File quá lớn (tối đa 200 MB)")
    folder = folder_for(kind)
    target = (folder / filename).resolve()
    if target.parent != folder.resolve():  # phòng thủ thêm, safe_filename đã chặn
        raise StorageError("Đường dẫn không hợp lệ")
    target.write_bytes(data)
    return target


def open_folder(kind: str) -> Path:
    folder = folder_for(kind)
    if os.name == "nt":
        os.startfile(folder)  # noqa: S606 — đường dẫn cố định, không từ người dùng
    else:
        subprocess.Popen(["xdg-open", str(folder)])
    return folder
