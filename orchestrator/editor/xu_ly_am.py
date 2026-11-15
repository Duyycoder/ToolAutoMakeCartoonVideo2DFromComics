"""Xử lý âm thanh của clip khi xuất: lọc tạp âm + EQ 3 dải (clip["xu_ly_am"]).

    {"giam_on": 0..100, "thap": dB, "trung": dB, "cao": dB}   (dB trong khoảng -12..12)

Xem trước: webui/editor/am_xu_ly.js dựng cùng các bộ lọc bằng Web Audio (EQ, lọc ù/gió); phần khử nhiễu
FFT (afftdn) chỉ nghe được ở bản xuất hoặc nút "Xem chính xác".
"""
from typing import Any, Dict, List

# Tần số giống am_xu_ly.js (BiquadFilter lowshelf / peaking / highshelf).
EQ = (("thap", "lowshelf=f=120:g={:.1f}"), ("trung", "equalizer=f=1500:t=q:w=1:g={:.1f}"),
      ("cao", "highshelf=f=6000:g={:.1f}"))


def loc_am(x: Dict[str, Any]) -> List[str]:
    x = x or {}
    loc: List[str] = []
    on = max(0.0, min(100.0, float(x.get("giam_on") or 0)))
    if on > 0:
        # Cắt tiếng ù/gió dưới 80 Hz rồi khử nhiễu nền (tự bám theo tiếng ồn thay đổi).
        loc.append("highpass=f=80")
        loc.append(f"afftdn=nr={6 + 0.34 * on:.1f}:nf=-40:tn=1")
    for k, mau in EQ:
        g = max(-12.0, min(12.0, float(x.get(k) or 0)))
        if abs(g) >= 0.1:
            loc.append(mau.format(g))
    return loc
