"""Chống rung (stabilize) một đoạn video bằng vidstab của ffmpeg: sinh file mới đã ổn định cho đoạn [vao, ra].

Hai lượt: `vidstabdetect` đo chuyển động rung → file .trf; `vidstabtransform` bù lại (làm mượt quỹ đạo máy quay), tự phóng
nhẹ cho khỏi lộ viền đen. ffmpeg không có vidstab thì dùng `deshake` (một lượt, yếu hơn).
File .trf ghi bằng TÊN TƯƠNG ĐỐI trong thư mục tạm (cwd): đường dẫn Windows có dấu ':' làm hỏng cú pháp bộ lọc.
"""
import os
import shutil
import subprocess
import tempfile
from typing import List

DAI_TOI_DA = 1800.0
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def co_vidstab(ff: str) -> bool:
    try:
        res = subprocess.run([ff, "-hide_banner", "-filters"], capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return False
    return "vidstabtransform" in (res.stdout or "")


def loc_buoc_2(manh: int, vidstab: bool) -> str:
    """Chuỗi bộ lọc của lượt dựng. `manh` 1–100: độ mượt (số khung lấy trung bình quỹ đạo)."""
    manh = max(1, min(100, int(manh)))
    if not vidstab:
        return f"deshake=rx={16 + manh // 2}:ry={16 + manh // 2}"
    return f"vidstabtransform=input=rung.trf:smoothing={5 + manh * 35 // 100}:optzoom=1:interpol=bicubic,unsharp=5:5:0.6:3:3:0.3"


def _chay(cmd: List[str], cwd: str) -> None:
    res = subprocess.run(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                         errors="replace", timeout=7200, creationflags=NO_WINDOW)
    if res.returncode != 0:
        raise RuntimeError("ffmpeg lỗi: " + (res.stderr or "").strip()[-300:])


def tao(ff: str, src: str, dst: str, vao: float, ra: float, co_tieng: bool, manh: int = 50) -> None:
    """Ghi `dst` (mp4 H.264 + AAC) = đoạn [vao, ra] của `src` đã chống rung."""
    if not 0 <= vao < ra:
        raise ValueError("Đoạn chống rung không hợp lệ.")
    if ra - vao > DAI_TOI_DA:
        raise ValueError(f"Đoạn dài quá {int(DAI_TOI_DA / 60)} phút — cắt ngắn clip rồi chống rung.")
    src, dst = os.path.abspath(src), os.path.abspath(dst)
    tam = tempfile.mkdtemp(prefix="rung_", dir=os.path.dirname(dst))
    doan = ["-ss", f"{vao:.6f}", "-t", f"{ra - vao:.6f}", "-i", src]
    chung = [ff, "-hide_banner", "-loglevel", "error", "-y"]
    vidstab = co_vidstab(ff)
    try:
        if vidstab:
            _chay(chung + doan + ["-an", "-vf", "vidstabdetect=shakiness=6:accuracy=12:result=rung.trf", "-f", "null", "-"], tam)
        tieng = ["-c:a", "aac", "-b:a", "192k"] if co_tieng else ["-an"]
        _chay(chung + doan + ["-vf", loc_buoc_2(manh, vidstab), "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
                              "-pix_fmt", "yuv420p", *tieng, "-movflags", "+faststart", dst], tam)
    except Exception:
        if os.path.exists(dst):
            os.remove(dst)
        raise
    finally:
        shutil.rmtree(tam, ignore_errors=True)
