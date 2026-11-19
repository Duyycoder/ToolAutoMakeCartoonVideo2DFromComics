"""Xoá nền video bằng AI (U²-Net bản nhẹ, chạy CPU qua onnxruntime): sinh file mới cho đoạn [vao, ra] của video, trong đó
mọi thứ KHÔNG phải chủ thể được thay bằng MÀU KHOÁ đặc (xanh lá). Editor bật sẵn phông xanh (chroma key) cho clip dùng file
này nên nền thành trong suốt ở cả màn xem trước lẫn bản xuất.

Vì sao không xuất video có kênh alpha: trình duyệt chỉ phát alpha với WebM/VP9 mà ffmpeg lại bỏ alpha của VP9 khi giải mã
mặc định; ProRes 4444 thì trình duyệt không phát. Màu khoá đi qua được mọi khâu sẵn có (H.264, proxy, xuất trên thiết bị).

Khung hình đọc/ghi qua ống dẫn ffmpeg (rgb24) nên chỉ cần numpy + onnxruntime — server không có OpenCV.
Model: assets/models/u2netp.onnx (≈4,6 MB, bản phát hành của dự án rembg; file .onnx không nằm trong git).
"""
import os
import subprocess
from typing import Any, Callable, List, Optional

MAU_KHOA = (0, 255, 0)            # RGB của nền thay thế — khớp khoa_mau.mau = '#00ff00' mà editor bật cho clip
CANH = 320                         # cạnh ảnh đầu vào của U²-Net
CANH_DAI_TOI_DA = 1280             # file ra không lớn hơn mức này (cạnh dài) — đủ cho lớp phủ, nhẹ cho CPU
DAI_TOI_DA = 300.0                 # giây; mỗi khung là một lượt suy luận nên clip dài rất lâu
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MODEL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "models", "u2netp.onnx")


def kich_thuoc_ra(rong: int, cao: int) -> List[int]:
    """Cỡ khung làm việc: giữ tỉ lệ, cạnh dài ≤ CANH_DAI_TOI_DA, hai cạnh chẵn."""
    k = min(1.0, CANH_DAI_TOI_DA / max(rong, cao, 1))
    return [max(2, int(round(rong * k / 2)) * 2), max(2, int(round(cao * k / 2)) * 2)]


def tao_du_doan(model: str = MODEL) -> Callable[[Any], Any]:
    """Nạp model → hàm (khung RGB uint8 H×W×3) → mặt nạ float32 320×320 trong [0, 1]."""
    if not os.path.isfile(model):
        raise RuntimeError("Thiếu model xoá nền (assets/models/u2netp.onnx) trên máy này.")
    import numpy as np
    import onnxruntime as ort
    tuy = ort.SessionOptions()
    tuy.intra_op_num_threads = max(1, (os.cpu_count() or 2) - 1)
    phien = ort.InferenceSession(model, sess_options=tuy, providers=["CPUExecutionProvider"])
    ten_vao = phien.get_inputs()[0].name
    tb = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 3, 1, 1)
    lech = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 3, 1, 1)

    def du_doan(khung):
        h, w = khung.shape[:2]
        yy = (np.arange(CANH) * h // CANH).clip(0, h - 1)
        xx = (np.arange(CANH) * w // CANH).clip(0, w - 1)
        nho = khung[yy][:, xx].astype(np.float32)                   # thu nhỏ kiểu lấy mẫu gần nhất: đủ cho model
        nho /= max(1.0, float(nho.max()))
        x = (nho.transpose(2, 0, 1)[None] - tb) / lech
        d = phien.run(None, {ten_vao: x})[0][0, 0]
        lo, hi = float(d.min()), float(d.max())
        return (d - lo) / (hi - lo) if hi - lo > 1e-6 else np.zeros_like(d)
    return du_doan


def ghep_mau_khoa(khung, mat_na):
    """Khung RGB H×W×3 + mặt nạ nhỏ (0–1, cỡ bất kỳ) → khung mới: chủ thể giữ nguyên, phần còn lại là MAU_KHOA.

    Mặt nạ phóng lên cỡ khung bằng nội suy song tuyến (mép chủ thể mượt, không răng cưa khối)."""
    import numpy as np
    h, w = khung.shape[:2]
    mh, mw = mat_na.shape
    y = (np.arange(h) + 0.5) * mh / h - 0.5
    x = (np.arange(w) + 0.5) * mw / w - 0.5
    y0 = np.clip(np.floor(y).astype(int), 0, mh - 1)
    x0 = np.clip(np.floor(x).astype(int), 0, mw - 1)
    y1, x1 = np.minimum(y0 + 1, mh - 1), np.minimum(x0 + 1, mw - 1)
    fy = np.clip(y - y0, 0, 1).astype(np.float32)[:, None]
    fx = np.clip(x - x0, 0, 1).astype(np.float32)[None, :]
    m = mat_na.astype(np.float32)
    a = (m[y0][:, x0] * (1 - fx) + m[y0][:, x1] * fx) * (1 - fy) + (m[y1][:, x0] * (1 - fx) + m[y1][:, x1] * fx) * fy
    # Mép dứt khoát hơn: chroma key cần nền đúng màu khoá, vùng bán trong suốt rộng sẽ thành viền xanh.
    a = np.clip((a - 0.35) / 0.3, 0, 1)[..., None]
    nen = np.array(MAU_KHOA, dtype=np.float32)
    return (khung.astype(np.float32) * a + nen * (1 - a) + 0.5).astype(np.uint8)


def tao(ff: str, src: str, dst: str, vao: float, ra: float, rong: int, cao: int, fps: float, co_tieng: bool,
        du_doan: Optional[Callable[[Any], Any]] = None, bao: Optional[Callable[[float], None]] = None) -> int:
    """Ghi `dst` (mp4 H.264 + AAC) = đoạn [vao, ra] của `src` với nền thay bằng màu khoá. Trả số khung đã xử lý.

    `rong`×`cao` là cỡ HIỂN THỊ của video (đã tính xoay); `du_doan` để tiêm hàm giả khi kiểm thử."""
    if not 0 <= vao < ra:
        raise ValueError("Đoạn xoá nền không hợp lệ.")
    if ra - vao > DAI_TOI_DA:
        raise ValueError(f"Đoạn dài quá {int(DAI_TOI_DA / 60)} phút — cắt ngắn clip rồi xoá nền.")
    import numpy as np
    du_doan = du_doan or tao_du_doan()
    w, h = kich_thuoc_ra(int(rong) or 1280, int(cao) or 720)
    fps = float(fps) if fps and fps > 0 else 30.0
    doan = ["-ss", f"{vao:.6f}", "-t", f"{ra - vao:.6f}", "-i", src]
    doc = subprocess.Popen([ff, "-hide_banner", "-loglevel", "error", *doan, "-an", "-vf", f"scale={w}:{h},fps={fps:.6g}",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
    lenh = [ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
            "-r", f"{fps:.6g}", "-i", "-"]
    if co_tieng:
        lenh += [*doan, "-map", "0:v:0", "-map", "1:a:0?", "-c:a", "aac", "-b:a", "192k"]
    lenh += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst]
    ghi = subprocess.Popen(lenh, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                           creationflags=NO_WINDOW)
    co, so, tong = w * h * 3, 0, max(1, int(round((ra - vao) * fps)))
    try:
        while True:
            du = doc.stdout.read(co)
            if len(du) < co:
                break
            khung = np.frombuffer(du, dtype=np.uint8).reshape(h, w, 3)
            ghi.stdin.write(ghep_mau_khoa(khung, du_doan(khung)).tobytes())
            so += 1
            if bao:
                bao(min(1.0, so / tong))
        ghi.stdin.close()
        loi = ghi.stderr.read().decode("utf-8", "replace")
        if ghi.wait() != 0 or not so:
            raise RuntimeError("ffmpeg lỗi khi ghi bản xoá nền: " + (loi.strip()[-300:] or "không đọc được khung hình nào"))
    except Exception:
        for p in (doc, ghi):
            if p.poll() is None:
                p.kill()
        if os.path.exists(dst):
            try:
                os.remove(dst)
            except OSError:
                pass
        raise
    finally:
        doc.stdout.close()
        doc.wait()
    return so
