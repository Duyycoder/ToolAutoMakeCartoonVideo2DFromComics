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
    "game": ROOT_DIR / "output" / "game",  # mỗi nhân vật 1 thư mục: game/<Tên>/<Tên>.glb -> kéo thẳng vào Unity
    "rigs": ROOT_DIR / "library" / "rigs",  # mẫu xương tự lưu (Ghép xương)
}
ALLOWED_EXTENSIONS = {".glb", ".gltf", ".fbx", ".stl", ".obj", ".png", ".mp4", ".webm"}  # video: thanh Chuyển động
KIND_EXTENSIONS = {"game": {".glb", ".fbx", ".png", ".jpg"}, "rigs": {".json"}}  # thư mục chỉ nhận đúng loại file của nó (ảnh: texture đi kèm FBX)
LISTABLE_KINDS = {"rigs"}  # UI được liệt kê / đọc lại file
MAX_BYTES = 200 * 1024 * 1024
MAX_READ_BYTES = 2 * 1024 * 1024


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


def _subfolder(kind: str, subfolder: str | None) -> Path:
    """Thư mục con 1 cấp (tên đã làm sạch) — chỉ cho thư mục "game"."""
    folder = folder_for(kind)
    if not subfolder:
        return folder
    if kind != "game":
        raise StorageError("Thư mục này không có thư mục con")
    sub = folder / safe_filename(subfolder)
    try:
        sub.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # tên Windows dành riêng (CON, NUL...) / không ghi được
        raise StorageError("Tên thư mục không dùng được") from exc
    return sub


def save_bytes(kind: str, name: str, data: bytes, subfolder: str | None = None) -> Path:
    filename = safe_filename(name)
    if Path(filename).suffix.lower() not in KIND_EXTENSIONS.get(kind, ALLOWED_EXTENSIONS):
        raise StorageError(f"Không hỗ trợ định dạng {Path(filename).suffix or '(trống)'}")
    if not data:
        raise StorageError("File rỗng")
    if len(data) > MAX_BYTES:
        raise StorageError("File quá lớn (tối đa 200 MB)")
    folder = _subfolder(kind, subfolder)
    target = (folder / filename).resolve()
    if target.parent != folder.resolve():  # phòng thủ thêm, safe_filename đã chặn
        raise StorageError("Đường dẫn không hợp lệ")
    try:
        target.write_bytes(data)
    except OSError as exc:
        raise StorageError("Không ghi được file (tên không hợp lệ?)") from exc
    return target


def _listable(kind: str) -> Path:
    if kind not in LISTABLE_KINDS:
        raise StorageError(f"Không đọc được thư mục: {kind}")
    return folder_for(kind)


def list_files(kind: str) -> list[str]:
    folder = _listable(kind)
    allowed = KIND_EXTENSIONS.get(kind, ALLOWED_EXTENSIONS)
    return sorted(p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() in allowed)


def read_bytes(kind: str, name: str) -> bytes:
    folder = _listable(kind)
    target = (folder / safe_filename(name)).resolve()
    if target.parent != folder.resolve() or not target.is_file():
        raise StorageError("Không tìm thấy file")
    if target.stat().st_size > MAX_READ_BYTES:
        raise StorageError("File quá lớn")
    return target.read_bytes()


def open_folder(kind: str, subfolder: str | None = None) -> Path:
    folder = _subfolder(kind, subfolder)
    if os.name == "nt":
        os.startfile(folder)  # noqa: S606 — đường dẫn cố định, không từ người dùng
    else:
        subprocess.Popen(["xdg-open", str(folder)])
    return folder
