import os
import subprocess
import glob
import sys
import datetime

def merge_videos(video_dir: str, output_file: str, only_files: list[str] | None = None) -> bool:
    """Merges all mp4 files in video_dir into output_file using FFmpeg concat stream copy."""
    try:
        # Import imageio_ffmpeg from AIVoice virtual environment
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "AIVoice", ".venv", "Lib", "site-packages")))
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        print("[Error] imageio_ffmpeg is not installed. Cannot find FFmpeg.")
        return False

    mp4_files = sorted(glob.glob(os.path.join(video_dir, "*.mp4")))
    # Filter out files that might already be the output file or other merged files
    mp4_files = [f for f in mp4_files if not os.path.basename(f).startswith("TongHop_")]
    
    if only_files:
        # CHỐNG PATH TRAVERSAL: chỉ nhận basename thuần, phải nằm trong danh sách quét được
        wanted = {name for name in only_files if os.path.basename(name) == name}
        mp4_files = [f for f in mp4_files if os.path.basename(f) in wanted]
        
    if not mp4_files:
        print(f"[Warning] No MP4 files found in {video_dir} to merge.")
        return False
        
    list_file = os.path.join(video_dir, "concat_list.txt")
    try:
        with open(list_file, "w", encoding="utf-8") as f:
            for mp4 in mp4_files:
                # FFmpeg requires forward slashes and escaped single quotes
                safe_path = os.path.abspath(mp4).replace("\\", "/")
                # In concat demuxer, single quotes in filenames must be escaped
                safe_path = safe_path.replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")
                
        print(f"[Info] Merging {len(mp4_files)} videos into {output_file}...")
        cmd = [
            ffmpeg_exe,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_file
        ]
        
        # Run ffmpeg
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"[Error] FFmpeg concat -c copy failed with exit code {result.returncode}. Attempting fallback re-encoding...")
            # Fallback re-encode đúng 1 tầng
            cmd_fallback = [
                ffmpeg_exe,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "20",
                "-c:a", "aac",
                output_file
            ]
            result_fallback = subprocess.run(cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result_fallback.returncode != 0:
                print("[Error] Fallback re-encoding also failed.")
                print(result_fallback.stderr)
                print("[SYSTEM_MSG] Các video khác độ phân giải/định dạng — hãy chọn các video cùng nguồn (cùng được tạo từ Bước 3).")
                return False
            
        print(f"[Success] Successfully merged videos to {output_file}")
        return True
            
        print(f"[Success] Successfully merged videos to {output_file}")
        return True
    except Exception as e:
        print(f"[Error] Failed to merge videos: {e}")
        return False
    finally:
        if os.path.exists(list_file):
            try:
                os.remove(list_file)
            except:
                pass

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python video_merger.py <video_dir> <output_file>")
        sys.exit(1)
    merge_videos(sys.argv[1], sys.argv[2])
