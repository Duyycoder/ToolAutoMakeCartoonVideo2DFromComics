"""Thư viện âm thanh: CÓ SẴN (SFX + nhạc CC0 ở assets/thu_vien_am/, dựng bằng scripts/xay_thu_vien_am.py)
+ CỦA TÔI (âm thanh người dùng tự thêm, ở <workspace>/_thu_vien_am/ — dùng chung mọi dự án).

Danh mục: {"muc": [{id, loai: sfx|nhac, nhom, ten, file, thoi_luong, tac_gia, giay_phep, nguon}]}.
Mục "của tôi" có id `toi-…` và file `rieng/<tên>` (đường dẫn ảo, trỏ vào thư mục workspace).
Thêm vào dự án = chép một bản mang tên dễ đọc ra thư mục tạm rồi nhập như media thường (media.nhap tự bỏ trùng
theo tên + cỡ, nên thêm cùng một SFX nhiều lần chỉ chép một lần).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from typing import Any, Dict, List, Optional

GOC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "thu_vien_am")
THU_MUC_RIENG = "_thu_vien_am"
TIEN_TO_RIENG = "rieng/"
_cache: Dict[str, Any] = {"mtime": None, "muc": []}
_khoa = threading.Lock()


def danh_muc() -> List[Dict[str, Any]]:
    p = os.path.join(GOC, "thu_vien.json")
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return []
    if _cache["mtime"] != mt:
        with open(p, encoding="utf-8") as f:
            _cache["muc"] = [m for m in json.load(f).get("muc", []) if os.path.isfile(os.path.join(GOC, m["file"]))]
        _cache["mtime"] = mt
    return _cache["muc"]


# ------------------------------------------------------------------ của tôi
def _goc_rieng(ws: str) -> str:
    return os.path.join(os.path.abspath(ws), THU_MUC_RIENG)


def danh_muc_rieng(ws: str) -> List[Dict[str, Any]]:
    p = os.path.join(_goc_rieng(ws), "thu_vien.json")
    try:
        with open(p, encoding="utf-8") as f:
            ds = json.load(f).get("muc", [])
    except (OSError, ValueError):
        return []
    return [m for m in ds if os.path.isfile(os.path.join(_goc_rieng(ws), m["file"][len(TIEN_TO_RIENG):]))]


def _ghi_rieng(ws: str, ds: List[Dict[str, Any]]) -> None:
    os.makedirs(_goc_rieng(ws), exist_ok=True)
    p = os.path.join(_goc_rieng(ws), "thu_vien.json")
    with open(p + ".tam", "w", encoding="utf-8") as f:
        json.dump({"muc": ds}, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tam", p)


def them_rieng(ws: str, nguon: str, ten: str, nhom: str, loai: str, ff: str, thoi_luong: float) -> Dict[str, Any]:
    """Chép (chuyển .m4a, chỉ lấy tiếng) file `nguon` vào thư viện của tôi. Trả mục mới."""
    if loai not in ("sfx", "nhac"):
        raise ValueError("Loại phải là sfx hoặc nhac.")
    ten = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", ten or "").strip()[:80] or "Âm thanh"
    nhom = re.sub(r"[\x00-\x1f]+", " ", nhom or "").strip()[:40] or "Của tôi"
    with open(nguon, "rb") as f:
        khoa = hashlib.sha1(f.read(4 * 1024 * 1024) + str(os.path.getsize(nguon)).encode()).hexdigest()[:10]
    with _khoa:
        ds = danh_muc_rieng(ws)
        cu = next((m for m in ds if m["id"] == f"toi-{khoa}"), None)
        if cu:
            cu.update(ten=ten, nhom=nhom, loai=loai)
            _ghi_rieng(ws, ds)
            return cu
        os.makedirs(_goc_rieng(ws), exist_ok=True)
        ten_file = f"{khoa}.m4a"
        dich = os.path.join(_goc_rieng(ws), ten_file)
        r = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", nguon, "-vn", "-map", "0:a:0",
                            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dich + ".tam.m4a"],
                           capture_output=True, text=True, errors="replace", timeout=900)
        if r.returncode != 0:
            raise ValueError("Không lấy được tiếng từ file này: " + (r.stderr or "").strip()[-200:])
        os.replace(dich + ".tam.m4a", dich)
        m = {"id": f"toi-{khoa}", "loai": loai, "nhom": nhom, "ten": ten, "file": TIEN_TO_RIENG + ten_file,
             "thoi_luong": round(float(thoi_luong or 0), 3), "the": ["của tôi"], "mo_ta": "",
             "tac_gia": "Bạn", "giay_phep": "Riêng", "nguon": "", "rieng": True}
        ds.append(m)
        _ghi_rieng(ws, ds)
        return m


def xoa_rieng(ws: str, mid: str) -> bool:
    with _khoa:
        ds = danh_muc_rieng(ws)
        m = next((x for x in ds if x["id"] == mid), None)
        if not m:
            return False
        p = os.path.join(_goc_rieng(ws), m["file"][len(TIEN_TO_RIENG):])
        if os.path.isfile(p):
            os.remove(p)
        _ghi_rieng(ws, [x for x in ds if x["id"] != mid])
        return True


# ------------------------------------------------------------------ dùng chung
def tim(mid: str, ws: str = "") -> Optional[Dict[str, Any]]:
    ds = danh_muc_rieng(ws) if ws and mid.startswith("toi-") else danh_muc()
    return next((m for m in ds if m["id"] == mid), None)


def duong_dan(rel: str, ws: str = "") -> Optional[str]:
    """File trong thư viện (có sẵn hoặc `rieng/…`); chặn ../ ra ngoài; None nếu không có."""
    goc = GOC
    if rel.startswith(TIEN_TO_RIENG):
        if not ws:
            return None
        goc, rel = _goc_rieng(ws), rel[len(TIEN_TO_RIENG):]
    p = os.path.abspath(os.path.join(goc, rel))
    if not p.startswith(os.path.abspath(goc) + os.sep) or not os.path.isfile(p):
        return None
    return p


def ban_sao_de_nhap(mid: str, ws: str = "") -> str:
    """Bản sao mang tên dễ đọc (tên trong thư viện) để media.nhap đặt tên media cho đẹp."""
    m = tim(mid, ws)
    nguon = m and duong_dan(m["file"], ws)
    if not nguon:
        raise ValueError(f"Không có âm thanh {mid} trong thư viện.")
    ten = re.sub(r'[\\/:*?"<>|]+', " ", m["ten"]).strip() or mid
    d = os.path.join(tempfile.gettempdir(), "editor_thu_vien_am", re.sub(r"[^A-Za-z0-9_-]", "_", mid))
    os.makedirs(d, exist_ok=True)
    dich = os.path.join(d, ten + os.path.splitext(m["file"])[1])
    if not os.path.exists(dich) or os.path.getsize(dich) != os.path.getsize(nguon):
        shutil.copyfile(nguon, dich)
    return dich
