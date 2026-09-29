"""Đọc/ghi phụ đề: SRT/VTT/ASS → danh sách câu; câu → SRT; câu + kiểu chữ → ASS (cho ffmpeg `subtitles=`).

Đọc thử nhiều bảng mã: .srt tải trên mạng hay là UTF-16 (có BOM) hoặc cp1258/cp936 chứ
không phải lúc nào cũng UTF-8.
"""
import re
from typing import Any, Dict, List

_GIO = r"(\d+):(\d{1,2}):(\d{1,2})[,.](\d{1,3})"
_DONG_GIO = re.compile(_GIO + r"\s*-->\s*" + _GIO)
_GIO_VTT_NGAN = re.compile(r"^(\d{1,2}):(\d{2})[.](\d{3})\s*-->\s*(\d{1,2}):(\d{2})[.](\d{3})")


def doc_file(path: str) -> str:
    with open(path, "rb") as fh:
        du_lieu = fh.read()
    for ma in ("utf-8-sig", "utf-16", "cp1258", "gb18030", "latin-1"):
        try:
            text = du_lieu.decode(ma)
        except UnicodeDecodeError:
            continue
        if ma == "utf-16" and not du_lieu[:2] in (b"\xff\xfe", b"\xfe\xff"):
            continue
        return text.replace("\r\n", "\n").replace("\r", "\n")
    return du_lieu.decode("utf-8", errors="replace")


def _giay(h, m, s, ms) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def phan_tich(text: str) -> List[Dict[str, Any]]:
    """SRT/VTT/ASS → [{t_vao, t_ra, text}] theo thứ tự thời gian."""
    if "[Events]" in text and "Dialogue:" in text:
        return _phan_tich_ass(text)
    cau: List[Dict[str, Any]] = []
    khoi = re.split(r"\n\s*\n", text.strip())
    for k in khoi:
        dong = [d for d in k.split("\n") if d.strip() != ""]
        for i, d in enumerate(dong):
            m = _DONG_GIO.search(d)
            if m:
                g = m.groups()
                bd, kt = _giay(*g[:4]), _giay(*g[4:])
            else:
                n = _GIO_VTT_NGAN.search(d)
                if not n:
                    continue
                g = n.groups()
                bd, kt = _giay(0, g[0], g[1], g[2]), _giay(0, g[3], g[4], g[5])
            chu = "\n".join(dong[i + 1:]).strip()
            chu = re.sub(r"<[^>]+>", "", chu)          # thẻ <i>, <font>… của SRT/VTT
            if chu and kt > bd:
                cau.append({"t_vao": round(bd, 3), "t_ra": round(kt, 3), "text": chu})
            break
    cau.sort(key=lambda c: (c["t_vao"], c["t_ra"]))
    return cau


def _phan_tich_ass(text: str) -> List[Dict[str, Any]]:
    cau = []
    for d in text.split("\n"):
        if not d.startswith("Dialogue:"):
            continue
        phan = d.split(",", 9)
        if len(phan) < 10:
            continue
        m1 = re.match(r"(\d+):(\d+):(\d+)\.(\d+)", phan[1].strip())
        m2 = re.match(r"(\d+):(\d+):(\d+)\.(\d+)", phan[2].strip())
        if not (m1 and m2):
            continue
        chu = re.sub(r"\{[^}]*\}", "", phan[9]).replace("\\N", "\n").replace("\\n", "\n").strip()
        bd, kt = _giay(*m1.groups()), _giay(*m2.groups())
        if chu and kt > bd:
            cau.append({"t_vao": round(bd, 3), "t_ra": round(kt, 3), "text": chu})
    cau.sort(key=lambda c: (c["t_vao"], c["t_ra"]))
    return cau


def _srt_gio(t: float) -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ghi_srt(cau: List[Dict[str, Any]], khoa_bd: str = "t_vao", khoa_kt: str = "t_ra") -> str:
    out = []
    for i, c in enumerate(cau, 1):
        out.append(f"{i}\n{_srt_gio(float(c[khoa_bd]))} --> {_srt_gio(float(c[khoa_kt]))}\n{(c.get('text') or '').strip()}\n")
    return "\n".join(out)


# ------------------------------------------------------------------------ ASS
def _ass_gio(t: float) -> str:
    cs = int(round(max(0.0, t) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_mau(hex_mau: str, alpha: int = 0) -> str:
    """#RRGGBB → &HAABBGGRR (ASS để màu ngược và alpha 00 = đục)."""
    h = (hex_mau or "#ffffff").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    h = (h + "000000")[:6]
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ghi_ass(dong: List[Dict[str, Any]], kieu: Dict[str, Dict[str, Any]], rong: int, cao: int) -> str:
    """`dong`: [{bd, kt, text, kieu}] theo giờ TIMELINE. Cỡ chữ `co` tính theo khung cao 1080."""
    styles = []
    for ten, k in (kieu or {"k_mac_dinh": {}}).items():
        co = float(k.get("co") or 48) * cao / 1080.0
        vien = float(k.get("do_day_vien") or 0) * cao / 1080.0
        co_nen = (k.get("nen") or "None") not in ("None", "", None)
        vi_tri_y = float(k.get("vi_tri_y") if k.get("vi_tri_y") is not None else 0.9)
        le_duoi = max(0, int(round((1.0 - vi_tri_y) * cao)))
        styles.append(
            f"Style: {ten},{k.get('font') or 'Arial'},{co:.1f},{_ass_mau(k.get('mau') or '#ffffff')},"
            f"&H000000FF,{_ass_mau(k.get('vien') or '#000000')},"
            f"{_ass_mau(k.get('mau_nen') or '#000000', int(k.get('nen_alpha', 110)))},"
            f"0,0,0,0,100,100,0,0,{3 if co_nen else 1},{vien:.1f},0,2,20,20,{le_duoi},1")
    su_kien = []
    for d in dong:
        chu = (d.get("text") or "").replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")
        su_kien.append(f"Dialogue: 0,{_ass_gio(d['bd'])},{_ass_gio(d['kt'])},{d.get('kieu') or 'k_mac_dinh'},,0,0,0,,{chu}")
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {rong}", f"PlayResY: {cao}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        *styles, "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *su_kien, "",
    ])
