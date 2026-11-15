"""Chuẩn hoá file tải lên từ điện thoại/máy quay để editor xem trước và dựng được.

- Ảnh HEIC/HEIF (mặc định của iPhone), AVIF, TIFF… trình duyệt không hiện → đổi sang JPG.
  HEIC iPhone là LƯỚI nhiều ô 512×512 + cờ xoay: đọc bằng pillow-heif (libheif) để ra đủ ảnh
  4032×3024 đúng hướng, giữ hồ sơ màu (Display P3). ffmpeg chỉ lấy được ô đầu → ảnh 512×512 sai khung.
- Âm thanh CAF/AMR/AC3/AIFF… trình duyệt không phát → đổi sang M4A (AAC).
- Đuôi lạ hoặc không có đuôi → hỏi ffmpeg nội dung thật: video thì đổi đuôi .mkv (luôn tạo
  proxy H.264 khi nhập), âm thanh/ảnh thì đổi như trên. ffmpeg không đọc được thì từ chối.
File gốc được thay bằng bản đã chuẩn hoá (cùng thư mục cache/tai_len).
"""
import os
import subprocess

from orchestrator.editor import media
from orchestrator.editor.tai_len import LoiTaiLen

ANH_DOI_JPG = (".heic", ".heif", ".hif", ".avif", ".tif", ".tiff", ".jfif", ".jxl")
HEIF = (".heic", ".heif", ".hif")
AM_DOI_M4A = (".caf", ".amr", ".3ga", ".ac3", ".eac3", ".dts", ".aif", ".aiff", ".aifc",
              ".wv", ".ape", ".mka", ".au")
LENH_ANH = ["-frames:v", "1", "-q:v", "2"]
LENH_AM = ["-vn", "-c:a", "aac", "-b:a", "256k"]


def nhan_duoc(ten: str) -> bool:
    """Kiểm tra sớm lúc bắt đầu tải: đuôi lạ vẫn cho tải, chỉ chặn file chắc chắn không phải media."""
    duoi = os.path.splitext(ten)[1].lower()
    return duoi not in {".exe", ".bat", ".cmd", ".sh", ".dll", ".apk", ".ipa", ".zip", ".rar", ".7z",
                        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".html", ".htm", ".js", ".py"}


def _doi(path: str, duoi_moi: str, tuy_chon: list) -> str:
    exe = media.ffmpeg_exe()
    if not exe:
        raise LoiTaiLen("Server thiếu ffmpeg nên không đổi được định dạng file này.", 500)
    dich = os.path.splitext(path)[0] + duoi_moi
    try:
        res = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-i", path, *tuy_chon, dich],
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                             encoding="utf-8", errors="replace", timeout=900, creationflags=media.NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as e:
        raise LoiTaiLen(f"Đổi định dạng {os.path.basename(path)} lỗi: {e}", 422)
    if res.returncode != 0 or not os.path.isfile(dich) or os.path.getsize(dich) == 0:
        _xoa(dich)
        loi = (res.stderr or "").strip().splitlines()[-1:] or [""]
        raise LoiTaiLen(f"Không đọc được {os.path.basename(path)} ({loi[0][:160]}). "
                        "Ảnh iPhone: Cài đặt › Camera › Định dạng › Tương thích nhất rồi chụp/tải lại.", 422)
    _xoa(path)
    return dich


def _xoa(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _doi_heif(path: str) -> str:
    """HEIC/HEIF → JPG chất lượng cao, đủ độ phân giải, đúng hướng, giữ ICC (màu P3 của iPhone)."""
    try:
        import pillow_heif
        from PIL import Image
    except ImportError:
        if _so_luong_hinh(path) > 1:
            raise LoiTaiLen("Ảnh HEIC của iPhone cần thư viện pillow-heif để ghép đủ khung — chạy CAP-NHAT.bat "
                            "(hoặc pip install pillow-heif) rồi nhập lại.", 500)
        return _doi(path, ".jpg", LENH_ANH)
    pillow_heif.register_heif_opener()
    dich = os.path.splitext(path)[0] + ".jpg"
    try:
        with Image.open(path) as im:      # pillow-heif đã áp xoay/lật (irot/imir) — KHÔNG xoay theo EXIF lần nữa
            icc = im.info.get("icc_profile")
            exif = im.getexif()
            exif[0x0112] = 1              # Orientation: ảnh đã xoay đúng, để trình duyệt/ffmpeg khỏi xoay thêm
            im.convert("RGB").save(dich, "JPEG", quality=95, icc_profile=icc, exif=exif.tobytes())
    except Exception as e:  # file hỏng/biến thể lạ: báo rõ, không để ảnh sai
        _xoa(dich)
        raise LoiTaiLen(f"Không đọc được ảnh {os.path.basename(path)}: {e}", 422)
    _xoa(path)
    return dich


def _so_luong_hinh(path: str) -> int:
    """Số luồng hình ffmpeg thấy trong file (HEIC dạng lưới: mỗi ô 512×512 là một luồng)."""
    exe = media.ffmpeg_exe()
    if not exe:
        return 0
    try:
        res = subprocess.run([exe, "-hide_banner", "-i", path], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                             text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=media.NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return 0
    return sum(1 for d in (res.stderr or "").splitlines() if "Stream #" in d and ": Video:" in d)


def chuan_hoa(path: str) -> str:
    """Trả đường dẫn file editor dùng được (có thể là file mới); không dùng được thì ném LoiTaiLen."""
    duoi = os.path.splitext(path)[1].lower()
    if duoi in HEIF:
        return _doi_heif(path)
    if duoi in ANH_DOI_JPG:
        return _doi(path, ".jpg", LENH_ANH)
    if duoi in AM_DOI_M4A:
        return _doi(path, ".m4a", LENH_AM)
    if media.loai_theo_duoi(path):
        return path

    ts = media.do_thong_so(path)
    if ts.get("co_hinh") and float(ts.get("thoi_luong") or 0) >= 0.5:
        dich = os.path.splitext(path)[0] + ".mkv"
        os.replace(path, dich)
        return dich
    if ts.get("co_am_thanh"):
        return _doi(path, ".m4a", LENH_AM)
    if ts.get("co_hinh"):
        return _doi(path, ".jpg", LENH_ANH)
    _xoa(path)
    raise LoiTaiLen(f"{os.path.basename(path)} không phải video, âm thanh hay ảnh mà server đọc được.", 415)
