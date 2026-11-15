"""Chỉnh màu nâng cao: bộ lọc màu có sẵn (preset), LUT .cube, đường cong (curves), HSL từng vùng màu,
làm nét, khử nhiễu.

Bộ lọc, LUT, đường cong và HSL được GỘP thành MỘT LUT 3D 33³ cho mỗi clip → ffmpeg `lut3d` lúc xuất.
`webui/editor/mau_nang_cao.js` tính đúng cùng công thức để xem trước bằng WebGL — đổi công thức ở đây
thì đổi cả bên đó (tests/test_editor_mau_nang_cao.py so khớp hai bên).

Thứ tự áp: LUT file → preset → đường cong → HSL. Đường cong lưu điểm [x, y] thang 0..255.
"""
import hashlib
import json
import math
import os
import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

N_LUT = 33
N_BANG = 1024
VUNG_HSL = (("do", 0.0), ("cam", 30.0), ("vang", 60.0), ("luc", 120.0), ("xanh_ngoc", 180.0),
            ("lam", 240.0), ("tim", 270.0), ("hong", 300.0))
KENH = ("tong", "do", "luc", "lam")

_PRESET_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "webui", "editor", "preset_mau.json")
try:
    with open(_PRESET_PATH, encoding="utf-8") as _f:
        PRESET: Dict[str, Any] = json.load(_f)
except (OSError, ValueError):
    PRESET = {}

RGB = Tuple[float, float, float]


def _kep(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


# ------------------------------------------------------------------ đường cong
def bang_duong_cong(diem: Sequence[Sequence[float]]) -> Optional[List[float]]:
    """Spline đơn điệu (Fritsch–Carlson) qua các điểm → bảng N_BANG+1 giá trị; None nếu là đường thẳng."""
    d = sorted({round(float(x)): float(y) for x, y in diem or []}.items())
    if len(d) < 2 or all(abs(x - y) < 1e-9 for x, y in d) and d[0][0] == 0 and d[-1][0] == 255:
        return None
    xs = [x / 255 for x, _ in d]
    ys = [_kep(y / 255) for _, y in d]
    n = len(xs)
    dk = [(ys[k + 1] - ys[k]) / (xs[k + 1] - xs[k]) for k in range(n - 1)]
    m = [dk[0]] + [0.0 if dk[k - 1] * dk[k] <= 0 else (dk[k - 1] + dk[k]) / 2 for k in range(1, n - 1)] + [dk[-1]]
    for k in range(n - 1):
        if dk[k] == 0:
            m[k] = m[k + 1] = 0.0
            continue
        a, b = m[k] / dk[k], m[k + 1] / dk[k]
        s = a * a + b * b
        if s > 9:
            t = 3 / math.sqrt(s)
            m[k], m[k + 1] = t * a * dk[k], t * b * dk[k]
    bang, k = [], 0
    for i in range(N_BANG + 1):
        x = i / N_BANG
        if x <= xs[0]:
            bang.append(ys[0])
            continue
        if x >= xs[-1]:
            bang.append(ys[-1])
            continue
        while x > xs[k + 1]:
            k += 1
        h = xs[k + 1] - xs[k]
        t = (x - xs[k]) / h
        t2, t3 = t * t, t * t * t
        y = ((2 * t3 - 3 * t2 + 1) * ys[k] + (t3 - 2 * t2 + t) * h * m[k]
             + (-2 * t3 + 3 * t2) * ys[k + 1] + (t3 - t2) * h * m[k + 1])
        bang.append(_kep(y))
    return bang


def _tra(bang: Optional[List[float]], x: float) -> float:
    if bang is None:
        return x
    p = _kep(x) * N_BANG
    i = min(int(p), N_BANG - 1)
    return bang[i] + (bang[i + 1] - bang[i]) * (p - i)


def _cac_bang(cong: Dict[str, Any]) -> Optional[Dict[str, Optional[List[float]]]]:
    b = {k: bang_duong_cong((cong or {}).get(k) or []) for k in KENH}
    return b if any(v is not None for v in b.values()) else None


def _ap_cong(c: RGB, b: Dict[str, Optional[List[float]]]) -> RGB:
    t = b["tong"]
    return (_tra(b["do"], _tra(t, c[0])), _tra(b["luc"], _tra(t, c[1])), _tra(b["lam"], _tra(t, c[2])))


# ------------------------------------------------------------- bão hoà, HSL
def _bao_hoa(c: RGB, bh: float) -> RGB:
    if not bh:
        return c
    k = 1 + bh / 100
    y = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    return (_kep(y + (c[0] - y) * k), _kep(y + (c[1] - y) * k), _kep(y + (c[2] - y) * k))


def _hsl_hop_le(hsl: Dict[str, Any]) -> Optional[List[List[float]]]:
    ds = [[float(v) for v in ((hsl or {}).get(ten) or [0, 0, 0])[:3]] for ten, _ in VUNG_HSL]
    return ds if any(any(x) for x in ds) else None


def _ap_hsl(c: RGB, ds: List[List[float]]) -> RGB:
    r, g, b = c
    mx, mn = max(c), min(c)
    d = mx - mn
    if d < 1e-6:
        return c
    l = (mx + mn) / 2
    s = d / (1 - abs(2 * l - 1)) if abs(2 * l - 1) < 1 else 0.0
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    h *= 60
    i = 0
    while i < len(VUNG_HSL) - 1 and h >= VUNG_HSL[i + 1][1]:
        i += 1
    j = (i + 1) % len(VUNG_HSL)
    c0, c1 = VUNG_HSL[i][1], VUNG_HSL[j][1] if j else 360.0
    t = (h - c0) / (c1 - c0)
    dh, ds_, dl = ((1 - t) * ds[i][k] + t * ds[j][k] for k in range(3))
    h = (h + dh * 0.3) % 360
    s = _kep(s * (1 + ds_ / 100))
    l = _kep(l * (1 + 0.5 * dl / 100 * s))
    cc = (1 - abs(2 * l - 1)) * s
    x = cc * (1 - abs((h / 60) % 2 - 1))
    m = l - cc / 2
    sec = int(h // 60) % 6
    r1, g1, b1 = ((cc, x, 0), (x, cc, 0), (0, cc, x), (0, x, cc), (x, 0, cc), (cc, 0, x))[sec]
    return (_kep(r1 + m), _kep(g1 + m), _kep(b1 + m))


# ------------------------------------------------------------------ LUT file
def doc_cube(noi_dung: str) -> Tuple[int, List[RGB]]:
    """Đọc LUT 3D .cube (Resolve/Premiere/CapCut). Ném ValueError nếu hỏng."""
    n, du = 0, []
    for dong in noi_dung.splitlines():
        dong = dong.strip()
        if not dong or dong.startswith("#"):
            continue
        if dong.upper().startswith("LUT_3D_SIZE"):
            n = int(dong.split()[1])
        elif dong.upper().startswith("LUT_1D_SIZE"):
            raise ValueError("Chỉ hỗ trợ LUT 3D (.cube có LUT_3D_SIZE).")
        elif re.match(r"^[-+0-9.eE]", dong):
            p = dong.split()
            if len(p) >= 3:
                du.append((_kep(float(p[0])), _kep(float(p[1])), _kep(float(p[2]))))
    if not 2 <= n <= 129 or len(du) != n ** 3:
        raise ValueError(f"File .cube hỏng: LUT_3D_SIZE {n}, có {len(du)} dòng màu.")
    return n, du


def _mau_lut(lut: Tuple[int, List[RGB]], c: RGB) -> RGB:
    n, du = lut
    p = [x * (n - 1) for x in c]
    i = [min(int(x), n - 2) for x in p]
    f = [p[k] - i[k] for k in range(3)]
    out = [0.0, 0.0, 0.0]
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                w = (f[0] if dx else 1 - f[0]) * (f[1] if dy else 1 - f[1]) * (f[2] if dz else 1 - f[2])
                if w:
                    v = du[(i[0] + dx) + (i[1] + dy) * n + (i[2] + dz) * n * n]
                    for k in range(3):
                        out[k] += w * v[k]
    return (out[0], out[1], out[2])


def _tron(a: RGB, b: RGB, m: float) -> RGB:
    return (a[0] + (b[0] - a[0]) * m, a[1] + (b[1] - a[1]) * m, a[2] + (b[2] - a[2]) * m)


# ------------------------------------------------------------------ gộp
def ham_mau(mau: Dict[str, Any], lut: Optional[Tuple[int, List[RGB]]] = None) -> Optional[Callable[[RGB], RGB]]:
    """Hàm rgb→rgb của clip; None nếu clip không chỉnh gì cần LUT."""
    mau = mau or {}
    pr = PRESET.get(mau.get("preset") or "")
    pm = float(mau.get("preset_manh", 100)) / 100 if pr else 0
    pr_cong = _cac_bang(pr.get("cong")) if pr else None
    pr_hsl = _hsl_hop_le(pr.get("hsl")) if pr else None
    lm = float(mau.get("lut_manh", 100)) / 100 if lut else 0
    cong = _cac_bang(mau.get("cong"))
    hsl = _hsl_hop_le(mau.get("hsl"))
    if not (pm or lm or cong or hsl):
        return None

    def f(c: RGB) -> RGB:
        if lm:
            c = _tron(c, _mau_lut(lut, c), lm)
        if pm:
            v = _ap_cong(c, pr_cong) if pr_cong else c
            v = _bao_hoa(v, float(pr.get("bao_hoa") or 0))
            v = _ap_hsl(v, pr_hsl) if pr_hsl else v
            c = _tron(c, v, pm)
        if cong:
            c = _ap_cong(c, cong)
        if hsl:
            c = _ap_hsl(c, hsl)
        return c
    return f


def viet_cube(f: Callable[[RGB], RGB], n: int = N_LUT) -> str:
    dong = [f"LUT_3D_SIZE {n}"]
    for b in range(n):
        for g in range(n):
            for r in range(n):
                v = f((r / (n - 1), g / (n - 1), b / (n - 1)))
                dong.append(f"{v[0]:.5f} {v[1]:.5f} {v[2]:.5f}")
    return "\n".join(dong) + "\n"


def loc_clip(mau: Dict[str, Any], doc_lut: Callable[[str], str]) -> Tuple[List[str], Dict[str, str]]:
    """Filter ffmpeg cho clip (khử nhiễu → làm nét → LUT gộp) + file .cube cần ghi cạnh loc.txt.

    `doc_lut(ten)` trả nội dung file LUT của dự án; tên file .cube trong filter là tên ASCII tương đối.
    """
    mau = mau or {}
    loc: List[str] = []
    tep: Dict[str, str] = {}
    kn = float(mau.get("khu_nhieu") or 0)
    if kn > 0:
        s = kn / 100
        loc.append(f"hqdn3d={6 * s:.2f}:{4.5 * s:.2f}:{8 * s:.2f}:{6 * s:.2f}")
    ln = float(mau.get("lam_net") or 0)
    if ln > 0:
        loc.append(f"unsharp=5:5:{1.5 * ln / 100:.3f}:5:5:0")
    lut = None
    if mau.get("lut"):
        try:
            lut = doc_cube(doc_lut(mau["lut"]))
        except (OSError, ValueError):
            lut = None       # LUT đã xoá/hỏng: bỏ qua, vẫn xuất được
    f = ham_mau(mau, lut)
    if f:
        khoa = json.dumps({k: mau.get(k) for k in ("preset", "preset_manh", "lut", "lut_manh", "cong", "hsl")},
                          sort_keys=True) + (str(len(lut[1])) if lut else "")
        ten = f"lut_{hashlib.md5(khoa.encode()).hexdigest()[:10]}.cube"
        tep[ten] = viet_cube(f)
        loc.append(f"lut3d=file={ten}:interp=tetrahedral")
    return loc, tep
