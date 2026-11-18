"""Tốc độ clip theo ĐỒ THỊ (speed ramp) — bản Python của webui/editor/toc_do_cong.js (chung ca test
tests/js/ca_toc_do_cong.json).

clip.toc_do_cong = [{q, v}]: q ∈ [0, 1] là vị trí trên clip đã đổi tốc (thời gian timeline, chuẩn hoá), v = tốc độ.
clip.toc_do = tốc độ trung bình của đồ thị → độ dài clip vẫn = (ra − vao) / toc_do.
Nguồn: P(q) = ∫₀^q v / ∫₀¹ v; ngoài [0, 1] (kéo dài cho chuyển cảnh) chạy tiếp bằng tốc độ ở mép.

Xuất: hình dùng setpts với biểu thức nghịch đảo (giây nguồn → giây ra), tiếng cắt thành khúc ngắn,
mỗi khúc một atempo rồi nối lại (atempo không đổi tốc theo thời gian được).
"""
import math
from typing import Any, Dict, List, Optional, Tuple

TOC_MIN, TOC_MAX = 0.1, 10.0
KHUC_AM = 0.25          # giây (đầu ra) tối đa mỗi khúc tiếng
LE_AM = 0.25            # giây nguồn lấy thừa mỗi bên khúc (render._tieng_doi_toc)
TOI_DA_KHUC = 400


def chuan(cong: Any) -> Optional[List[Dict[str, float]]]:
    if not isinstance(cong, list) or len(cong) < 2:
        return None
    d = sorted(({"q": round(min(1.0, max(0.0, float(x.get("q") or 0))), 4),
                 "v": round(min(TOC_MAX, max(TOC_MIN, float(x.get("v") or 1))), 3)} for x in cong), key=lambda x: x["q"])
    if d[0]["q"] > 0:
        d.insert(0, {"q": 0.0, "v": d[0]["v"]})
    if d[-1]["q"] < 1:
        d.append({"q": 1.0, "v": d[-1]["v"]})
    return d


def cua_clip(c: Dict[str, Any]) -> Optional[List[Dict[str, float]]]:
    return chuan(c.get("toc_do_cong"))


def toc_tai(cong, q: float) -> float:
    if q <= cong[0]["q"]:
        return cong[0]["v"]
    for a, b in zip(cong, cong[1:]):
        if q <= b["q"]:
            h = b["q"] - a["q"]
            return b["v"] if h < 1e-9 else a["v"] + (b["v"] - a["v"]) * (q - a["q"]) / h
    return cong[-1]["v"]


def _tich_luy(cong) -> List[float]:
    A = [0.0]
    for a, b in zip(cong, cong[1:]):
        A.append(A[-1] + (b["q"] - a["q"]) * (a["v"] + b["v"]) / 2)
    return A


def trung_binh(cong) -> float:
    return _tich_luy(cong)[-1]


def nguon_tai(cong, q: float) -> float:
    A = _tich_luy(cong)
    M = A[-1]
    if q <= 0:
        return q * cong[0]["v"] / M
    if q >= 1:
        return 1 + (q - 1) * cong[-1]["v"] / M
    for i in range(1, len(cong)):
        a, b = cong[i - 1], cong[i]
        if q <= b["q"]:
            x = q - a["q"]
            return (A[i - 1] + a["v"] * x + (toc_tai(cong, q) - a["v"]) * x / 2) / M
    return 1.0


def vi_tri_tai(cong, p: float) -> float:
    A = _tich_luy(cong)
    M = A[-1]
    if p <= 0:
        return p * M / cong[0]["v"]
    if p >= 1:
        return 1 + (p - 1) * M / cong[-1]["v"]
    can = p * M
    for i in range(1, len(cong)):
        if can <= A[i] + 1e-12:
            a, b = cong[i - 1], cong[i]
            h = b["q"] - a["q"]
            if h < 1e-9:
                return a["q"]
            r, k = can - A[i - 1], (b["v"] - a["v"]) / h
            return a["q"] + 2 * r / (a["v"] + math.sqrt(max(0.0, a["v"] ** 2 + 2 * k * r)))
    return 1.0


def _so(x: float) -> str:
    return f"{float(x):.6f}".rstrip("0").rstrip(".") or "0"


def bieu_thuc_pts(cong, L: float, D: float, lech: float) -> str:
    """Biểu thức setpts (giây) cho luồng nguồn bắt đầu ở vao + lech: T (giây kể từ đầu luồng) → giây ra kể từ đầu luồng.

    out(u) = D·Q(u/L), u = T + lech; trừ out(lech) để luồng ra bắt đầu từ 0. Q tuyến tính ngoài [0, L] (tốc độ mép).
    Trong đoạn i: Q = qa + 2r / (va + √(va² + 2kr)), r = u/L·M − Aa, k = (vb − va)/h.
    """
    A = _tich_luy(cong)
    M = A[-1]
    u = f"(T+{_so(lech)})" if lech >= 0 else f"(T-{_so(-lech)})"
    p = f"({u}/{_so(L)})"
    bt = f"(1+({p}-1)*{_so(M / cong[-1]['v'])})"            # sau mép phải
    for i in range(len(cong) - 1, 0, -1):
        a, b = cong[i - 1], cong[i]
        h = b["q"] - a["q"]
        if h < 1e-9:
            continue
        k = (b["v"] - a["v"]) / h
        r = f"({p}*{_so(M)}-{_so(A[i - 1])})"
        doan = f"({_so(a['q'])}+2*{r}/({_so(a['v'])}+sqrt(max(0\\,{_so(a['v'] ** 2)}+{_so(2 * k)}*{r}))))"
        bt = f"if(lt({p}\\,{_so(A[i] / M)})\\,{doan}\\,{bt})"
    bt = f"if(lt({p}\\,0)\\,{p}*{_so(M / cong[0]['v'])}\\,{bt})"
    goc = D * vi_tri_tai(cong, lech / L)
    return f"({_so(D)}*{bt}-({_so(goc)}))/TB"


def khuc_am(cong, L: float, D: float) -> List[Tuple[float, float, float]]:
    """Chia tiếng thành khúc theo thời gian ra → [(giây nguồn bắt đầu, giây nguồn kết thúc, tempo)]."""
    moc = sorted({x["q"] for x in cong})
    q_ds: List[float] = []
    for a, b in zip(moc, moc[1:]):
        n = max(1, math.ceil((b - a) * D / KHUC_AM))
        q_ds += [a + (b - a) * j / n for j in range(n)]
    q_ds.append(1.0)
    if len(q_ds) - 1 > TOI_DA_KHUC:
        q_ds = [j / TOI_DA_KHUC for j in range(TOI_DA_KHUC + 1)]
    ra = []
    for qa, qb in zip(q_ds, q_ds[1:]):
        s0, s1 = L * nguon_tai(cong, qa), L * nguon_tai(cong, qb)
        dt = (qb - qa) * D
        if dt > 1e-6 and s1 - s0 > 1e-6:
            ra.append((s0, s1, (s1 - s0) / dt))
    return ra
