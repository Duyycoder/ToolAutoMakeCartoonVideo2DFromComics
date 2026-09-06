import os
import subprocess
import glob
import sys

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


def merge_files(files: list[str], output_file: str) -> bool:
    """Ghép danh sách file video (đường dẫn tuyệt đối, đúng thứ tự) thành một file.

    Ưu tiên concat stream-copy (không giải mã lại — vài giây cho video dài); chỉ
    khi các nguồn khác codec/độ phân giải mới lùi về mã hoá lại một tầng.
    """
    files = [f for f in files if f and os.path.exists(f)]
    if not files:
        print("[Warning] Không có file video hợp lệ nào để ghép.")
        return False

    ffmpeg_exe = _ffmpeg_exe()
    if not ffmpeg_exe:
        return False

    out_dir = os.path.dirname(os.path.abspath(output_file)) or "."
    os.makedirs(out_dir, exist_ok=True)
    list_file = os.path.join(out_dir, "concat_list.txt")
    try:
        with open(list_file, "w", encoding="utf-8") as f:
            for mp4 in files:
                # FFmpeg requires forward slashes and escaped single quotes
                safe_path = os.path.abspath(mp4).replace("\\", "/")
                safe_path = safe_path.replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")

        print(f"[Info] Merging {len(files)} videos into {output_file}...")
        cmd = [ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", list_file,
               "-c", "copy", output_file]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode != 0:
            print(f"[Error] FFmpeg concat -c copy failed with exit code {result.returncode}. "
                  f"Attempting fallback re-encoding...")
            cmd_fallback = [ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", list_file,
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                            "-c:a", "aac", output_file]
            result_fallback = subprocess.run(
                cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result_fallback.returncode != 0:
                print("[Error] Fallback re-encoding also failed.")
                print(result_fallback.stderr)
                print("[SYSTEM_MSG] Các video khác độ phân giải/định dạng nhau — thử chọn các video "
                      "cùng nguồn, hoặc gắn phụ đề cho chúng bằng cùng một bộ tham số trước khi ghép.")
                return False

        print(f"[Success] Successfully merged videos to {output_file}")
        return True
    except Exception as e:
        print(f"[Error] Failed to merge videos: {e}")
        return False
    finally:
        if os.path.exists(list_file):
            try:
                os.remove(list_file)
            except OSError:
                pass


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
