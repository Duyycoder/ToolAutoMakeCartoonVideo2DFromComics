"""Đóng gói dự án thành MỘT file .zip để mang sang máy khác, và mở gói đó thành dự án mới.

Gói chứa nguyên thư mục dự án (`.duan.json`, `.duan/timeline.json`…, `media/`, `phu_de/`, `long_tieng/`, `luts/`) trừ:
khoá cửa sổ (`.duan/lock`), bộ đệm dựng lại được (`.duan/cache`: proxy, thumbnail, sóng âm) và — mặc định — video đã
xuất (`xuat/`). Không nén (ZIP_STORED): video/âm thanh vốn đã nén, nén lại chỉ tốn CPU của server yếu.

Module chỉ đụng hệ thống tệp nên kiểm thử trọn vẹn (tests/test_editor_goi_du_an.py).
"""
import os
import shutil
import uuid
import zipfile
from typing import Callable, List, Optional, Tuple

from orchestrator.editor import luu_tru
from orchestrator.storage import slugify

DUOI = ".duan.zip"
KHUC = 4 * 1024 * 1024


def _bo_qua(rel: str, kem_xuat: bool) -> bool:
    p = rel.replace("\\", "/")
    if p in (f"{luu_tru.THU_MUC_EDITOR}/lock",) or p.startswith(f"{luu_tru.THU_MUC_EDITOR}/{luu_tru.CACHE}/"):
        return True
    if not kem_xuat and p.startswith(f"{luu_tru.XUAT_DIR}/"):
        return True
    return p.endswith((".tmp", ".part"))


def liet_ke(folder: str, kem_xuat: bool = False) -> List[Tuple[str, str, int]]:
    """[(đường dẫn thật, tên trong gói, kích thước)] của mọi file sẽ vào gói."""
    folder = os.path.abspath(folder)
    out = []
    for goc, _, files in os.walk(folder):
        for f in files:
            p = os.path.join(goc, f)
            rel = os.path.relpath(p, folder).replace("\\", "/")
            if not _bo_qua(rel, kem_xuat) and os.path.isfile(p):
                out.append((p, rel, os.path.getsize(p)))
    return out


def dong_goi(folder: str, dich: str, bao: Optional[Callable[[float], None]] = None, kem_xuat: bool = False) -> int:
    """Ghi gói dự án ra `dich`; `bao(0..1)` báo tiến độ. Trả kích thước gói (byte)."""
    if not os.path.isfile(luu_tru.duong_dan_duan(folder)):
        raise ValueError("Thư mục này không phải dự án.")
    ds = liet_ke(folder, kem_xuat)
    tong = sum(k for _, _, k in ds) or 1
    os.makedirs(os.path.dirname(dich), exist_ok=True)
    tam = dich + ".part"
    xong = 0
    try:
        with zipfile.ZipFile(tam, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
            for p, rel, _ in ds:
                with open(p, "rb") as f, z.open(zipfile.ZipInfo.from_file(p, rel), "w", force_zip64=True) as g:
                    while True:
                        b = f.read(KHUC)
                        if not b:
                            break
                        g.write(b)
                        xong += len(b)
                        if bao:
                            bao(min(1.0, xong / tong))
        os.replace(tam, dich)
    finally:
        if os.path.exists(tam):
            os.remove(tam)
    return os.path.getsize(dich)


def mo_goi(zip_path: str, workspace: str) -> str:
    """Giải gói vào `workspace/<tên dự án>` (trùng tên thì thêm _2, _3…), trả thư mục dự án mới.

    Dự án nhận id mới nếu id trong gói đã có ở `workspace`… — đơn giản hơn: LUÔN cấp id mới, để nhập cùng một gói hai
    lần vẫn ra hai dự án độc lập. Từ chối gói có đường dẫn thoát ra ngoài thư mục đích (zip-slip).
    """
    try:
        z = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError):
        raise ValueError("File không phải gói dự án (.zip) hợp lệ.")
    with z:
        ten = z.namelist()
        if luu_tru.MARKER not in ten:
            raise ValueError("Gói này không chứa dự án (thiếu .duan.json ở gốc).")
        for n in ten:
            chuan = os.path.normpath(n)
            if os.path.isabs(n) or chuan.startswith("..") or ":" in n or n.startswith(("/", "\\")):
                raise ValueError(f"Gói có đường dẫn không an toàn: {n}")
        import json
        try:
            da = json.loads(z.read(luu_tru.MARKER).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ValueError("File .duan.json trong gói bị hỏng.")
        slug = slugify(str(da.get("name") or "")) or "du-an-nhap"
        folder = os.path.join(workspace, slug)
        lan = 2
        while os.path.exists(folder):
            folder = os.path.join(workspace, f"{slug}_{lan}")
            lan += 1
        os.makedirs(folder)
        try:
            z.extractall(folder)
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise

    def sua(d):
        d["id"] = uuid.uuid4().hex[:8]
        d["tac_vu"] = [t for t in d.get("tac_vu", []) if t.get("trang_thai") not in ("cho", "dang_chay")]
        return True
    luu_tru.sua_duan(folder, sua)
    khoa = os.path.join(luu_tru.thu_muc_editor(folder), "lock")
    if os.path.exists(khoa):
        os.remove(khoa)
    return folder
