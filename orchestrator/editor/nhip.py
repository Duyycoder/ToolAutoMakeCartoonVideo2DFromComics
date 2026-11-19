"""Tìm nhịp (beat) của nhạc để đặt điểm đánh dấu trên timeline — cắt cảnh theo nhạc.

Không dùng thư viện ngoài (server không có librosa): ffmpeg giải mã về PCM mono 11 kHz, rồi
    1. năng lượng từng khung 23 ms → "độ nổi" = phần năng lượng (log) tăng so với khung trước;
    2. tự tương quan độ nổi trong dải 60–180 BPM → chu kỳ nhịp;
    3. chọn pha để lưới nhịp trùng nhiều chỗ nổi nhất → danh sách thời điểm.
Giả định nhịp đều trong đoạn đo (đúng với hầu hết nhạc nền); nhạc đổi tempo giữa chừng thì nên đo từng clip.
"""
import array
import math
import subprocess
from typing import List, Tuple

SR = 11025
BUOC = 256                      # 23,2 ms mỗi khung
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def do_noi(mau: array.array) -> List[float]:
    """Độ nổi (onset strength) theo từng khung BUOC mẫu."""
    truoc, out = None, []
    for i in range(0, len(mau) - BUOC + 1, BUOC):
        e = 0.0
        for x in mau[i:i + BUOC]:
            e += x * x
        lg = math.log10(1.0 + e / BUOC)
        out.append(max(0.0, lg - truoc) if truoc is not None else 0.0)
        truoc = lg
    return out


def tim_nhip(noi: List[float], bpm_min: float = 60, bpm_max: float = 180) -> Tuple[float, List[float]]:
    """Độ nổi → (BPM, [giây của từng nhịp]). Không đủ dữ liệu / không có nhịp rõ → (0, [])."""
    fps = SR / BUOC
    n = len(noi)
    lag_a, lag_b = int(fps * 60 / bpm_max), int(fps * 60 / bpm_min)
    if n < lag_b * 3 or max(noi, default=0) <= 0:
        return 0.0, []
    tb = sum(noi) / n
    x = [v - tb for v in noi]
    tot, lag = -1e18, 0
    for L in range(max(2, lag_a), lag_b + 1):
        s = 0.0
        for i in range(n - L):
            s += x[i] * x[i + L]
        s /= (n - L)
        # Ưu tiên nhẹ tempo quanh 120 BPM để không chọn nhầm nửa/gấp đôi nhịp khi hai đỉnh ngang nhau.
        s *= math.exp(-0.5 * (math.log2((60 * fps / L) / 120) / 0.9) ** 2)
        if s > tot:
            tot, lag = s, L
    if lag <= 0 or tot <= 0:
        return 0.0, []
    # Chu kỳ thật hiếm khi tròn số khung (120 BPM = 21,53 khung): lưới theo `lag` nguyên sẽ trôi dần khỏi nhạc.
    # → dò chu kỳ lẻ quanh `lag` (bước 0,02 khung) cùng pha, lấy lưới trùng nhiều chỗ nổi nhất.
    tot_luoi, chu_ky, pha = -1.0, float(lag), 0.0
    for buoc in range(-50, 51):
        P = lag + buoc * 0.02
        so = int((n - 1) / P) + 1
        for p in range(int(P) + 1):
            s, k = 0.0, 0
            while True:
                i = int(p + k * P + 0.5)
                if i >= n:
                    break
                s += noi[i]
                k += 1
            s /= max(1, so)
            if s > tot_luoi:
                tot_luoi, chu_ky, pha = s, P, float(p)
    nhip, k = [], 0
    while pha + k * chu_ky < n:
        nhip.append(round((pha + k * chu_ky) / fps, 3))
        k += 1
    return round(60 * fps / chu_ky, 1), nhip


def do(ff: str, path: str, vao: float, ra: float) -> Tuple[float, List[float]]:
    """Nhịp trong đoạn [vao, ra] của file → (BPM, [giây trong MEDIA])."""
    if not 0 <= vao < ra:
        raise ValueError("Đoạn cần đo không hợp lệ.")
    if ra - vao > 1200:
        raise ValueError("Đoạn dài quá 20 phút — cắt ngắn clip rồi tìm nhịp.")
    res = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-ss", f"{vao:.3f}", "-t", f"{ra - vao:.3f}", "-i", path,
                          "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600, creationflags=NO_WINDOW)
    if res.returncode != 0:
        raise RuntimeError("ffmpeg lỗi: " + res.stderr.decode("utf-8", "replace").strip()[-300:])
    mau = array.array("h")
    mau.frombytes(res.stdout[:len(res.stdout) // 2 * 2])
    bpm, nhip = tim_nhip(do_noi(mau))
    return bpm, [round(vao + t, 3) for t in nhip if vao + t < ra]
