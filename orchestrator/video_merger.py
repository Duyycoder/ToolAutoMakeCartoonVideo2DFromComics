"""Nối nhiều video thành một file.

Hai đường đi:

* **Nối thẳng** (`concat` + `-c copy`): không giải mã lại, vài giây cho video
  dài — nhưng CHỈ chạy được khi mọi video cùng độ phân giải/codec.
* **Chuẩn hoá rồi nối**: ép từng video về chung một khung hình (thêm viền đen
  nếu khác tỉ lệ), 30fps, tiếng AAC 48kHz, rồi mới nối thẳng. Chậm hơn nhiều
  nhưng lô lẫn TikTok dọc với YouTube ngang vẫn ra được file.

Máy đích KHÔNG có `ffprobe` (gói `imageio_ffmpeg` chỉ ship `ffmpeg.exe`), nên
thông số video lấy từ `video.json`; thiếu thì hỏi chính `ffmpeg -i`.
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import time

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DEFAULT_SIZE = (1920, 1080)


def _select_files(mp4_files: list[str], only_files: list[str] | None) -> list[str]:
    # Filter out files that might already be the output file or other merged files
    filtered = [f for f in mp4_files if not os.path.basename(f).startswith("TongHop_")]
    if only_files:
        # CHỐNG PATH TRAVERSAL: chỉ nhận basename thuần, phải nằm trong danh sách quét được
        wanted = {name for name in only_files if os.path.basename(name) == name}
        filtered = [f for f in filtered if os.path.basename(f) in wanted]
    return filtered


def _ffmpeg_exe() -> str | None:
    try:
        # imageio_ffmpeg nằm trong venv của AIVoice (orchestrator cố ý không cài torch/ffmpeg riêng)
        sys.path.insert(0, os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "AIVoice", ".venv", "Lib", "site-packages")))
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        print("[Error] imageio_ffmpeg is not installed. Cannot find FFmpeg.")
        return None


def _run(cmd: list) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          encoding="utf-8", errors="replace", creationflags=NO_WINDOW)


def _even(value: int) -> int:
    """Ép chiều về số chẵn — `yuv420p` không nhận 1081 và ffmpeg sẽ bỏ cuộc."""
    value = int(value or 0)
    return max(2, value - value % 2)


def _target_size(sizes: list | None) -> tuple | None:
    """Khung đích: video lớn nhất theo diện tích trong lô. None nếu không biết cỡ nào."""
    known = []
    for item in sizes or []:
        try:
            width, height = int(item[0] or 0), int(item[1] or 0)
        except (TypeError, ValueError, IndexError):
            continue
        if width > 0 and height > 0:
            known.append((width, height))
    if not known:
        return None
    width, height = max(known, key=lambda s: s[0] * s[1])
    return _even(width), _even(height)


def _sizes_match(sizes: list | None, count: int) -> bool:
    """True khi biết rõ MỌI cỡ và chúng giống hệt nhau (đủ điều kiện nối thẳng)."""
    if not sizes or len(sizes) != count:
        return False
    seen = set()
    for item in sizes:
        try:
            width, height = int(item[0] or 0), int(item[1] or 0)
        except (TypeError, ValueError, IndexError):
            return False
        if width <= 0 or height <= 0:
            return False
        seen.add((width, height))
    return len(seen) == 1


def probe_media(ffmpeg_exe: str, path: str) -> dict:
    """{"width", "height", "has_audio"} hỏi thẳng ffmpeg.

    `ffmpeg -i <file>` không có output nên thoát với mã lỗi, nhưng vẫn in thông
    tin luồng ra stderr — đây là cách thay `ffprobe` trên máy đích. Gần như tức
    thì vì nó chỉ mở file chứ không giải mã.
    """
    res = _run([ffmpeg_exe, "-hide_banner", "-i", path])
    err = res.stderr or ""
    size = re.search(r"Stream #\d+:\d+.*: Video:.*?, (\d+)x(\d+)", err)
    return {
        "width": int(size.group(1)) if size else 0,
        "height": int(size.group(2)) if size else 0,
        "has_audio": bool(re.search(r"Stream #\d+:\d+.*: Audio:", err)),
    }


def probe_sizes(files: list[str]) -> list[tuple[int, int]]:
    """[(w, h), ...] song song với `files`, hỏi thẳng ffmpeg.

    Dùng khi không có sẵn kích thước trong `video.json` (vd video của dự án).
    Thiếu kích thước thì `merge_files` sẽ thử nối thẳng — với video khác cỡ,
    concat có thể "thành công" mà ra file hỏng, nên phải đo trước.
    Không tìm thấy ffmpeg thì trả [] (bên gọi coi như chưa biết cỡ).
    """
    ffmpeg_exe = _ffmpeg_exe()
    if not ffmpeg_exe:
        return []
    return [(m["width"], m["height"])
            for m in (probe_media(ffmpeg_exe, f) for f in files)]


def _concat_copy(ffmpeg_exe: str, files: list[str], output_file: str) -> bool:
    """Nối bằng concat demuxer, không mã hoá lại."""
    out_dir = os.path.dirname(os.path.abspath(output_file)) or "."
    os.makedirs(out_dir, exist_ok=True)
    list_file = os.path.join(out_dir, f"concat_list_{os.getpid()}.txt")
    try:
        with open(list_file, "w", encoding="utf-8") as fh:
            for mp4 in files:
                # FFmpeg requires forward slashes and escaped single quotes
                safe_path = os.path.abspath(mp4).replace("\\", "/")
                safe_path = safe_path.replace("'", "'\\''")
                fh.write(f"file '{safe_path}'\n")
        res = _run([ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", list_file,
                    "-c", "copy", output_file])
        if res.returncode != 0:
            print(f"[Info] Nối thẳng không thành (mã {res.returncode}).")
            return False
        return True
    finally:
        if os.path.exists(list_file):
            try:
                os.remove(list_file)
            except OSError:
                pass


def _normalize_one(ffmpeg_exe: str, src: str, dst: str, size: tuple) -> bool:
    """Ép một video về đúng khung `size`, 30fps, tiếng AAC 48kHz stereo.

    Giữ nguyên tỉ lệ gốc và chèn viền đen cho vừa khung (video dọc ghép với video
    ngang thì đứng giữa), thay vì kéo méo hình.
    """
    width, height = size
    video_filter = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1")
    encode = ["-vf", video_filter, "-r", "30",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-ar", "48000", "-ac", "2", dst]

    if probe_media(ffmpeg_exe, src).get("has_audio"):
        cmd = [ffmpeg_exe, "-y", "-i", src] + encode
    else:
        # Video câm mà nối với video có tiếng thì concat demuxer hỏng (số luồng
        # lệch nhau) -> chèn sẵn một luồng tiếng im lặng dài bằng hình.
        cmd = [ffmpeg_exe, "-y", "-i", src,
               "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
               "-map", "0:v:0", "-map", "1:a:0", "-shortest"] + encode

    res = _run(cmd)
    if res.returncode != 0:
        print(f"[Error] Chuẩn hoá thất bại: {os.path.basename(src)}")
        print((res.stderr or "")[-600:])
        return False
    return True


def _merge_normalized(ffmpeg_exe: str, files: list[str], output_file: str,
                      sizes: list | None, work_dir: str | None) -> bool:
    """Ép mọi video về chung một khung rồi mới nối."""
    target = _target_size(sizes)
    if not target:
        probed = [(m["width"], m["height"])
                  for m in (probe_media(ffmpeg_exe, f) for f in files)]
        target = _target_size(probed) or DEFAULT_SIZE

    base = work_dir or os.path.dirname(os.path.abspath(output_file)) or "."
    tmp_dir = os.path.join(base, f"merge_{os.getpid()}_{int(time.time())}")
    os.makedirs(tmp_dir, exist_ok=True)
    print(f"[Info] Các video khác cỡ nhau — chuẩn hoá về {target[0]}x{target[1]} trước khi nối.")
    try:
        parts = []
        for i, src in enumerate(files, 1):
            print(f"[Info] Chuẩn hoá ({i}/{len(files)}): {os.path.basename(src)}")
            dst = os.path.join(tmp_dir, f"{i:03d}.mp4")
            if not _normalize_one(ffmpeg_exe, src, dst, target):
                print("[SYSTEM_MSG] Không chuẩn hoá được video này — thử bỏ nó ra khỏi "
                      "danh sách rồi ghép lại.")
                return False
            parts.append(dst)
        print("[Info] Đang nối các video đã chuẩn hoá...")
        if _concat_copy(ffmpeg_exe, parts, output_file):
            print(f"[Success] Successfully merged videos to {output_file}")
            return True
        print("[Error] Nối các video đã chuẩn hoá vẫn thất bại.")
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def merge_files(files: list[str], output_file: str, sizes: list | None = None,
                normalize: str = "auto", work_dir: str | None = None) -> bool:
    """Ghép danh sách file video (đường dẫn tuyệt đối, ĐÚNG thứ tự) thành một file.

    `sizes` = [(w, h), ...] song song với `files`, lấy sẵn từ `video.json`.
    `normalize`:
      * "auto"   — cùng cỡ thì nối thẳng; khác cỡ (hoặc nối thẳng hỏng) thì
                   chuẩn hoá rồi nối.
      * "never"  — luôn nối thẳng, hỏng thì chịu (nhanh nhất).
      * "always" — luôn chuẩn hoá, kể cả khi cùng cỡ.
    """
    files = [f for f in files if f and os.path.exists(f)]
    if not files:
        print("[Warning] Không có file video hợp lệ nào để ghép.")
        return False

    ffmpeg_exe = _ffmpeg_exe()
    if not ffmpeg_exe:
        return False

    os.makedirs(os.path.dirname(os.path.abspath(output_file)) or ".", exist_ok=True)
    same_size = _sizes_match(sizes, len(files))

    if normalize != "always" and (normalize == "never" or same_size or not sizes):
        print(f"[Info] Merging {len(files)} videos into {output_file}...")
        if _concat_copy(ffmpeg_exe, files, output_file):
            print(f"[Success] Successfully merged videos to {output_file}")
            return True
        if normalize == "never":
            print("[SYSTEM_MSG] Các video khác độ phân giải/định dạng nhau — bật "
                  "'tự chuẩn hoá' ở tab Ghép rồi thử lại.")
            return False

    return _merge_normalized(ffmpeg_exe, files, output_file, sizes, work_dir)


def merge_videos(video_dir: str, output_file: str, only_files: list[str] | None = None) -> bool:
    """Ghép mọi mp4 trong một thư mục (bỏ qua các bản ghép cũ TongHop_*)."""
    mp4_files = sorted(glob.glob(os.path.join(video_dir, "*.mp4")))
    mp4_files = _select_files(mp4_files, only_files)
    if not mp4_files:
        print(f"[Warning] No MP4 files found in {video_dir} to merge.")
        return False
    return merge_files(mp4_files, output_file)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python video_merger.py <video_dir> <output_file>")
        sys.exit(1)
    merge_videos(sys.argv[1], sys.argv[2])
