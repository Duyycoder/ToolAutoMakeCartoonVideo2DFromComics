"""Thư viện âm thanh có sẵn (SFX + nhạc nền CC0) ở assets/thu_vien_am/ — dựng bằng scripts/xay_thu_vien_am.py.

Danh mục: assets/thu_vien_am/thu_vien.json {"muc": [{id, loai: sfx|nhac, nhom, ten, file, thoi_luong, tac_gia, giay_phep, nguon}]}.
Thêm vào dự án = chép một bản mang tên dễ đọc ra thư mục tạm rồi nhập như media thường (media.nhap tự bỏ trùng
theo tên + cỡ, nên thêm cùng một SFX nhiều lần chỉ chép một lần).
"""
import json
import os
import re
import shutil
import tempfile
from typing import Any, Dict, List, Optional

GOC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "thu_vien_am")
_cache: Dict[str, Any] = {"mtime": None, "muc": []}


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


def tim(mid: str) -> Optional[Dict[str, Any]]:
    return next((m for m in danh_muc() if m["id"] == mid), None)


def duong_dan(rel: str) -> Optional[str]:
    """File trong thư viện (chặn ../ ra ngoài); None nếu không có."""
    p = os.path.abspath(os.path.join(GOC, rel))
    if not p.startswith(os.path.abspath(GOC) + os.sep) or not os.path.isfile(p):
        return None
    return p


def ban_sao_de_nhap(mid: str) -> str:
    """Bản sao mang tên dễ đọc (tên trong thư viện) để media.nhap đặt tên media cho đẹp."""
    m = tim(mid)
    if not m:
        raise ValueError(f"Không có âm thanh {mid} trong thư viện.")
    ten = re.sub(r'[\\/:*?"<>|]+', " ", m["ten"]).strip() or mid
    d = os.path.join(tempfile.gettempdir(), "editor_thu_vien_am", re.sub(r"[^A-Za-z0-9_-]", "_", mid))
    os.makedirs(d, exist_ok=True)
    dich = os.path.join(d, ten + os.path.splitext(m["file"])[1])
    nguon = os.path.join(GOC, m["file"])
    if not os.path.exists(dich) or os.path.getsize(dich) != os.path.getsize(nguon):
        shutil.copyfile(nguon, dich)
    return dich
