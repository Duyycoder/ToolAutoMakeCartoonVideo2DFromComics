"""Tìm khoảng lặng trong tiếng của một media (ffmpeg silencedetect) — cho nút "Tự cắt khoảng lặng" (jump cut)."""
import re
import subprocess
from typing import List

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_DAU = re.compile(r"silence_start:\s*(-?[\d.]+)")
_CUOI = re.compile(r"silence_end:\s*(-?[\d.]+)")


def phan_tich(log: str, lech: float, het: float) -> List[List[float]]:
    """Log của silencedetect → [[bắt đầu, kết thúc], …] theo giây trong MEDIA (`lech` = điểm bắt đầu đoạn đã đo).

    Khoảng lặng kéo tới hết đoạn không có dòng silence_end → đóng tại `het`."""
    out, dau = [], None
    for dong in log.splitlines():
        m = _DAU.search(dong)
        if m:
            dau = max(0.0, float(m.group(1)))
            continue
        m = _CUOI.search(dong)
        if m and dau is not None:
            out.append([round(lech + dau, 3), round(lech + float(m.group(1)), 3)])
            dau = None
    if dau is not None and lech + dau < het - 1e-3:
        out.append([round(lech + dau, 3), round(het, 3)])
    return out


def do(ff: str, path: str, vao: float, ra: float, nguong_db: float = -35.0, toi_thieu: float = 0.6) -> List[List[float]]:
    """Các khoảng lặng (dưới `nguong_db`, dài từ `toi_thieu` giây) trong đoạn [vao, ra] của file."""
    if not 0 <= vao < ra:
        raise ValueError("Đoạn cần đo không hợp lệ.")
    res = subprocess.run([ff, "-hide_banner", "-nostats", "-ss", f"{vao:.3f}", "-t", f"{ra - vao:.3f}", "-i", path, "-vn",
                          "-af", f"silencedetect=noise={nguong_db:.1f}dB:d={toi_thieu:.3f}", "-f", "null", "-"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                         timeout=1800, creationflags=NO_WINDOW)
    if res.returncode != 0:
        raise RuntimeError("ffmpeg lỗi: " + (res.stderr or "").strip()[-300:])
    return phan_tich(res.stderr or "", vao, ra)
