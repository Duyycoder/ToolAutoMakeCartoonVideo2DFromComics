"""Gộp nhiều clip thành MỘT clip (compound kiểu "dựng sẵn rồi thay thế"): dựng riêng các clip được chọn — đủ lớp, biến đổi,
màu, hiệu ứng, chuyển cảnh, vùng che, tiếng — thành một file video mới; trên timeline các clip đó được thay bằng một clip
dùng file này. Không phải timeline lồng nhau: muốn sửa lại bên trong thì hoàn tác (Ctrl+Z).

Hàm ở đây chỉ dựng timeline con (thuần, kiểm thử được); chạy ffmpeg nằm ở api.py.
"""
import copy
from typing import Any, Dict, List, Tuple

from orchestrator.editor import quy_doi

GIU_LOAI = ("che_phu_de",)       # ngoài clip media được chọn, vùng che neo theo video vẫn phải vào bản gộp


def tl_con(tl: Dict[str, Any], ids: List[str]) -> Tuple[Dict[str, Any], float, bool]:
    """→ (timeline chỉ gồm các clip `ids`, dời về bắt đầu từ 0; thời điểm bắt đầu cũ; có clip trên track video không)."""
    chon = set(ids)
    loai = {t["id"]: t.get("loai") for t in tl.get("tracks") or []}
    cac = [c for c in tl.get("clips") or [] if c.get("id") in chon and not c.get("loai") and c.get("media")
           and loai.get(c.get("track")) in ("video", "audio")]
    if not cac:
        raise ValueError("Chọn ít nhất một clip video/âm thanh để gộp.")
    t0 = min(float(c.get("bat_dau") or 0) for c in cac)
    con = copy.deepcopy(tl)
    giu = {c["id"] for c in cac}
    con["clips"] = [c for c in con.get("clips") or [] if c.get("id") in giu or c.get("loai") in GIU_LOAI]
    for c in con["clips"]:
        if c.get("id") in giu:
            c["bat_dau"] = round(float(c.get("bat_dau") or 0) - t0, 6)
    con["chuyen_canh"] = [cc for cc in con.get("chuyen_canh") or [] if cc.get("truoc") in giu and cc.get("sau") in giu]
    for k in ("vung_vao", "vung_ra", "danh_dau"):
        con.pop(k, None)
    # Track ẩn / tắt tiếng vẫn giữ nguyên trạng thái: bản gộp phải giống đúng cái đang thấy và nghe.
    co_hinh = any(loai.get(c.get("track")) == "video" for c in cac)
    return con, t0, co_hinh


def thoi_luong(con: Dict[str, Any]) -> float:
    return max((quy_doi.ket_thuc(c) for c in con.get("clips") or [] if not c.get("loai")), default=0.0)
