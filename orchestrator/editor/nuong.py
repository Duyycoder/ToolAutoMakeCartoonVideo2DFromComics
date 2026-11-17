"""Server "nướng sẵn" phần xuất trên thiết bị máy không tự làm được (plan xuất trên thiết bị, phase 3).

- Lớp chữ: chữ / hình vẽ / phụ đề = MỘT file .ass (chu_hinh.tao_ass) như bản xuất server → libass vẽ ra ảnh PNG trong
  suốt đúng khung xuất. libass của ffmpeg không ghi kênh alpha → vẽ hai lần trên nền đen và nền trắng rồi suy ra alpha
  (alpha = 1 − (trắng − đen), màu = đen / alpha). Khung không có hiệu ứng động: một ảnh cho cả đoạn chữ đứng yên;
  đoạn có \\fad/\\move: mỗi khung một ảnh. Máy chồng ảnh lên khung đã ghép → chữ y hệt bản server.
- Đoạn nướng: các khúc [a, b) (chỉ số khung trên lưới fps xuất) mà máy không ghép được (chỉnh màu nâng cao, chuyển cảnh
  không có bản vẽ trên máy, nguồn máy không giải mã được) → render.py dựng đúng như bản server, chỉ giữ các khung đó,
  nối liền thành một file H.264 chất lượng rất cao, không chữ (máy chồng lớp chữ sau).
Hàm dựng kế hoạch/lệnh là hàm thuần (pytest); `chay` là thân việc trong hàng đợi GPU.
"""
import os
import re
import shutil
from typing import Any, Callable, Dict, List, Tuple

from orchestrator.editor import chu_hinh, hang_doi, luu_tru, render

_DONG = re.compile(r"^Dialogue:\s*\d+,\s*(\d+):(\d+):(\d+(?:\.\d+)?),\s*(\d+):(\d+):(\d+(?:\.\d+)?),")
_DONG_DONG = ("\\fad", "\\move", "\\t(", "\\k")      # thẻ ASS làm chữ đổi theo từng khung
TEN_FILE = re.compile(r"^[a-z0-9_]{1,40}(\.[a-z0-9]{1,5})?$")   # id việc / tên file nướng — không "..", không "/"
TOI_DA_ANH = 4000                                       # chặn kế hoạch quá lớn (video dài đầy hiệu ứng động)


def khung_ms(n: int, fps: float) -> int:
    """Mốc ms libass nhận cho khung n (vf_subtitles đổi pts sang ms, làm tròn)."""
    return int(round(n * 1000.0 / fps))


def su_kien_ass(ass: str) -> List[Tuple[int, int, bool]]:
    """Dialogue → [(bắt đầu ms, kết thúc ms, có động)]."""
    ra = []
    for dong in ass.splitlines():
        m = _DONG.match(dong)
        if not m:
            continue
        g = m.groups()
        bd = int(round((int(g[0]) * 3600 + int(g[1]) * 60 + float(g[2])) * 1000))
        kt = int(round((int(g[3]) * 3600 + int(g[4]) * 60 + float(g[5])) * 1000))
        if kt > bd:
            ra.append((bd, kt, any(t in dong for t in _DONG_DONG)))
    return ra


def _khung_dau(ms: int, fps: float) -> int:
    """Khung nhỏ nhất có khung_ms ≥ ms."""
    n = max(0, int(ms * fps / 1000.0) - 1)
    while khung_ms(n, fps) < ms:
        n += 1
    return n


def ke_hoach_lop_chu(ass: str, n0: int, n1: int, fps: float) -> List[Dict[str, int]]:
    """Khung [n0, n1) → [{tu, den, khung}]: ảnh vẽ ở `khung` dùng cho mọi khung [tu, den). Khung không có chữ thì bỏ."""
    ev = []
    for bd, kt, dong in su_kien_ass(ass):
        a, b = max(n0, _khung_dau(bd, fps)), min(n1, _khung_dau(kt, fps))
        if a < b:
            ev.append((a, b, dong))
    moc = sorted({n0, n1, *(x for a, b, _ in ev for x in (a, b))})
    ra: List[Dict[str, int]] = []
    for a, b in zip(moc, moc[1:]):
        dang = [d for x, y, d in ev if x <= a and y >= b]
        if not dang:
            continue
        if any(dang):
            ra += [{"tu": n, "den": n + 1, "khung": n} for n in range(a, b)]
        else:
            ra.append({"tu": a, "den": b, "khung": a})
    return ra


def _chuoi_chon(khung: List[int]) -> str:
    """Danh sách khung tăng dần → biểu thức select gộp các dãy liền nhau."""
    day, ra = [], []
    for n in khung:
        if day and n == day[-1][1] + 1:
            day[-1][1] = n
        else:
            day.append([n, n])
    for a, b in day:
        ra.append(f"eq(n,{a})" if a == b else f"between(n,{a},{b})")
    return "+".join(ra)


def loc_lop_chu(W: int, H: int, fps: float, khung: List[int]) -> str:
    """Filter vẽ sub.ass tại các khung (chỉ số tuyệt đối trên lưới fps) → [o] RGBA."""
    chon = _chuoi_chon(khung)
    d = (max(khung) + 2) / fps
    nguon = lambda mau: (f"color=c={mau}:s={W}x{H}:r={render._so(fps)}:d={render._so(d)},format=gbrp,"
                         f"select='{chon}',subtitles=sub.ass")
    return ";\n".join([
        nguon("black") + ",split[b1][b2]",
        nguon("white") + "[w]",
        "[w][b1]blend=all_mode=difference,negate,extractplanes=g[a]",
        "[b2][a]alphamerge,unpremultiply=inplace=1,format=rgba[o]",
    ])


def lenh_lop_chu(ff: str) -> List[str]:
    return [ff, "-hide_banner", "-y", "-nostats", "-progress", "pipe:1"] + render.tham_so_file_loc(ff, "loc_chu.txt") + [
        "-map", "[o]", "-fps_mode", "passthrough", "-compression_level", "3", "chu_%05d.png"]


def thu_muc(folder: str, vid: str) -> str:
    return luu_tru._p(folder, luu_tru.CACHE, "nuong", vid)


def don_cu(folder: str, giu_giay: float = 86400) -> None:
    """Xoá việc nướng cũ (máy bị tắt giữa chừng không kịp xoá)."""
    import time
    goc = luu_tru._p(folder, luu_tru.CACHE, "nuong")
    if not os.path.isdir(goc):
        return
    for ten in os.listdir(goc):
        p = os.path.join(goc, ten)
        if os.path.isdir(p) and time.time() - os.path.getmtime(p) > giu_giay:
            shutil.rmtree(p, ignore_errors=True)


def _chay_ff(ctx: hang_doi.NguCanh, cmd: List[str], cwd: str, log: str, bao: Callable[[float], None]) -> None:
    cuoi: List[str] = []

    def dong(line: str) -> None:
        if line.startswith("frame="):
            try:
                bao(int(line.split("=", 1)[1]))
            except ValueError:
                pass
        elif "=" not in line or " " in line.split("=", 1)[0]:
            cuoi.append(line)
            del cuoi[:-8]
    code = ctx.chay_doc_dong(cmd, cwd, dong, log=os.path.join(cwd, log))
    if code != 0:
        raise RuntimeError("ffmpeg lỗi: " + " | ".join(x for x in cuoi[-4:] if x.strip())[-500:])


def chay(ctx: hang_doi.NguCanh, folder: str, du_an: Dict[str, Any], tl: Dict[str, Any], tc: Dict[str, Any],
         n0: int, n1: int, lop_chu: bool, doan: List[List[int]], ff: str, tm: str) -> Dict[str, Any]:
    os.makedirs(tm, exist_ok=True)
    W, H = render.kich_thuoc_xuat(du_an.get("thong_so") or {}, tc.get("do_phan_giai") or "")
    fps = float(tc.get("fps") or (du_an.get("thong_so") or {}).get("fps") or 30)
    kq: Dict[str, Any] = {"kich_thuoc": [W, H], "fps": fps, "lop_chu": [], "doan": None}
    tong_buoc = (1 if lop_chu else 0) + (1 if doan else 0)
    buoc = 0
    if lop_chu:
        ass = chu_hinh.tao_ass(tl, W, H)
        kh = ke_hoach_lop_chu(ass, n0, n1, fps)
        khung = sorted({x["khung"] for x in kh})
        if len(khung) > TOI_DA_ANH:
            raise RuntimeError(f"Chữ/phụ đề động quá nhiều ({len(khung)} khung) — hãy xuất bằng Server.")
        if khung:
            with open(os.path.join(tm, "sub.ass"), "w", encoding="utf-8") as fh:
                fh.write(ass)
            with open(os.path.join(tm, "loc_chu.txt"), "w", encoding="utf-8") as fh:
                fh.write(loc_lop_chu(W, H, fps, khung))
            ctx.bao(0, f"Server vẽ chữ/phụ đề ({len(khung)} ảnh)…")
            _chay_ff(ctx, lenh_lop_chu(ff), tm, "log_chu.txt",
                     lambda k: ctx.bao(min(99.0, k * 100 / len(khung) / tong_buoc)))
            anh = {n: f"chu_{i + 1:05d}.png" for i, n in enumerate(khung)}
            if not all(os.path.isfile(os.path.join(tm, f)) for f in anh.values()):
                raise RuntimeError("Server vẽ thiếu ảnh chữ/phụ đề.")
            kq["lop_chu"] = [{**x, "file": anh[x["khung"]]} for x in kh]
        buoc = 1
    if doan:
        lenh = render.dung_lenh_xuat(folder, du_an, tl, {**tc, "doan_nuong": doan, "giu_hdr": False},
                                     os.path.join(tm, "doan.mp4"), ff, co_ass=False)
        with open(os.path.join(tm, "loc.txt"), "w", encoding="utf-8") as fh:
            fh.write(lenh["loc"])
        for ten, noi in (lenh.get("tep") or {}).items():
            with open(os.path.join(tm, ten), "w", encoding="utf-8") as fh:
                fh.write(noi)
        so = lenh["so_khung"]
        ctx.bao(buoc * 100 / tong_buoc, f"Server dựng {so} khung máy không ghép được…")
        _chay_ff(ctx, lenh["cmd"], tm, "log_doan.txt",
                 lambda k: ctx.bao(min(99.0, (buoc + k / max(1, so)) * 100 / tong_buoc)))
        kq["doan"] = {"file": "doan.mp4", "khuc": doan, "so_khung": so}
    return kq
