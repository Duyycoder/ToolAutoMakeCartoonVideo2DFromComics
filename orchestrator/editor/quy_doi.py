"""Quy đổi thời gian media gốc ↔ timeline cho phụ đề và vùng che (docs/PLAN-editor.md mục 2.1).

Câu phụ đề sinh từ Whisper/OCR/.srt NEO theo media gốc: `tu_media` + `t_vao/t_ra` (giây trong
media). Vị trí trên timeline tính qua clip đang dùng media đó:

    bat_dau_hien = clip.bat_dau + (max(t_vao, clip.vao) - clip.vao) / clip.toc_do

nên cắt, tỉa, dời, đổi tốc độ clip thì phụ đề đi theo. Một media có nhiều clip (đã cắt đôi)
thì câu hiện ở clip chứa nó; phần nằm ngoài [vao, ra] của mọi clip thì ẩn (không xoá).
Câu tự gõ không thuộc media nào dùng `bat_dau/ket_thuc` tuyệt đối.

Bản JS tương ứng: `webui/editor/store.js › hienThiNeo`. Hai bản chạy chung ca test
`tests/js/ca_quy_doi.json`.
"""
from typing import Any, Dict, List

LOAI_NEO = ("phu_de", "che_phu_de")


def la_neo(c: Dict[str, Any]) -> bool:
    return bool(c.get("tu_media")) and c.get("t_vao") is not None and c.get("t_ra") is not None


def ket_thuc(c: Dict[str, Any]) -> float:
    if c.get("ket_thuc") is not None:
        return float(c["ket_thuc"])
    toc = float(c.get("toc_do") or 1)
    return float(c.get("bat_dau") or 0) + (float(c.get("ra") or 0) - float(c.get("vao") or 0)) / toc


def clip_chua_media(tl: Dict[str, Any], mid: str) -> List[Dict[str, Any]]:
    """Clip (track video, không có thì track âm thanh) đang dùng media `mid`."""
    loai = {t["id"]: t.get("loai") for t in tl.get("tracks") or []}
    cac = [c for c in tl.get("clips") or [] if c.get("media") == mid]
    video = [c for c in cac if loai.get(c.get("track")) == "video"]
    return video or [c for c in cac if loai.get(c.get("track")) == "audio"]


def hien_thi(tl: Dict[str, Any], c: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Các khoảng [bd, kt] trên timeline mà clip phụ đề/che `c` hiện ra (mới nhất theo bd)."""
    if not la_neo(c):
        if c.get("bat_dau") is None:
            return []
        return [{"bd": float(c["bat_dau"]), "kt": ket_thuc(c), "clip": None}]
    tv, tr = float(c["t_vao"]), float(c["t_ra"])
    out = []
    for v in clip_chua_media(tl, c["tu_media"]):
        vao, ra = float(v.get("vao") or 0), float(v.get("ra") or 0)
        lo, hi = max(tv, vao), min(tr, ra)
        if hi - lo <= 1e-6:
            continue
        toc = float(v.get("toc_do") or 1)
        bd0 = float(v.get("bat_dau") or 0)
        out.append({"bd": round(bd0 + (lo - vao) / toc, 6), "kt": round(bd0 + (hi - vao) / toc, 6),
                    "clip": v["id"]})
    out.sort(key=lambda x: x["bd"])
    return out


def phu_de_tren_timeline(tl: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Mọi câu phụ đề đang hiện (track phụ đề không ẩn), theo thời gian: [{id, bd, kt, text, kieu}]."""
    an = {t["id"] for t in tl.get("tracks") or [] if t.get("an")}
    out = []
    for c in tl.get("clips") or []:
        if c.get("loai") != "phu_de" or c.get("track") in an or not (c.get("text") or "").strip():
            continue
        for k in hien_thi(tl, c):
            out.append({"id": c["id"], "bd": k["bd"], "kt": k["kt"], "text": c.get("text") or "",
                        "kieu": c.get("kieu") or "k_mac_dinh"})
    out.sort(key=lambda x: (x["bd"], x["kt"]))
    return out
