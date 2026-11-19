"""Tua ngược một đoạn video: sinh file mới phát ngược đoạn [vao, ra] của video gốc (cả tiếng).

Bộ lọc `reverse` của ffmpeg giữ MỌI khung chưa nén trong RAM (1080p ≈ 3 MB/khung) nên đảo cả đoạn dài một lượt là
hết bộ nhớ. Ở đây cắt đoạn thành từng khúc KHUC giây, đảo từng khúc, rồi nối các khúc theo thứ tự ngược lại.
Tiếng nhẹ hơn nhiều nên đảo một lượt (`areverse`).
"""
import os
import shutil
import subprocess
import tempfile
from typing import List

KHUC = 2.0            # giây mỗi khúc video
DAI_TOI_DA = 1800.0   # không nhận đoạn dài hơn 30 phút
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def cac_khuc(vao: float, ra: float, khuc: float = KHUC) -> List[List[float]]:
    """[[bắt đầu, dài], …] phủ kín [vao, ra] theo thứ tự xuôi."""
    out, a = [], vao
    while ra - a > 1e-3:
        d = min(khuc, ra - a)
        out.append([round(a, 6), round(d, 6)])
        a += d
    return out


def _chay(cmd: List[str]) -> None:
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                         errors="replace", timeout=3600, creationflags=NO_WINDOW)
    if res.returncode != 0:
        raise RuntimeError("ffmpeg lỗi: " + (res.stderr or "").strip()[-300:])


def tao(ff: str, src: str, dst: str, vao: float, ra: float, co_tieng: bool, fps: float = 0) -> None:
    """Ghi `dst` (mp4 H.264 + AAC) = đoạn [vao, ra] của `src` phát ngược."""
    if not 0 <= vao < ra:
        raise ValueError("Đoạn tua ngược không hợp lệ.")
    if ra - vao > DAI_TOI_DA:
        raise ValueError(f"Đoạn dài quá {int(DAI_TOI_DA / 60)} phút — cắt ngắn clip rồi tua ngược.")
    tam = tempfile.mkdtemp(prefix="dao_", dir=os.path.dirname(dst))
    chung = [ff, "-hide_banner", "-loglevel", "error", "-y"]
    loc = "reverse,setpts=PTS-STARTPTS" + (f",fps={fps:.6g}" if fps else "")
    try:
        ten = []
        for i, (a, d) in enumerate(cac_khuc(vao, ra)):
            p = os.path.join(tam, f"{i:05d}.mp4")
            _chay(chung + ["-ss", f"{a:.6f}", "-t", f"{d:.6f}", "-i", src, "-an", "-vf", loc, "-c:v", "libx264",
                           "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", p])
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                ten.append(p)
        if not ten:
            raise RuntimeError("Không đảo được khung hình nào.")
        ds = os.path.join(tam, "ds.txt")
        with open(ds, "w", encoding="utf-8") as f:
            f.writelines("file '" + p.replace("\\", "/").replace("'", "'\''") + "'\n" for p in reversed(ten))
        lenh = chung + ["-f", "concat", "-safe", "0", "-i", ds]
        if co_tieng:
            lenh += ["-ss", f"{vao:.6f}", "-t", f"{ra - vao:.6f}", "-i", src, "-map", "0:v:0", "-map", "1:a:0",
                     "-af", "areverse", "-c:a", "aac", "-b:a", "192k"]
        _chay(lenh + ["-c:v", "copy", "-movflags", "+faststart", dst])
    except Exception:
        if os.path.exists(dst):
            os.remove(dst)
        raise
    finally:
        shutil.rmtree(tam, ignore_errors=True)
