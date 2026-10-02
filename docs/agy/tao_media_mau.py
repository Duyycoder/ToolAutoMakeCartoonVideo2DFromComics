"""Tạo media mẫu để test editor: video ngang h264, .mov HEVC quay dọc (như iPhone), mp3, png."""
import os
import subprocess

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mau")
os.makedirs(OUT, exist_ok=True)


def chay(args, ten):
    res = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y"] + args + [os.path.join(OUT, ten)],
                         capture_output=True, text=True)
    print(ten, "OK" if res.returncode == 0 else "LOI: " + res.stderr[-400:])


chay(["-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=6",
      "-f", "lavfi", "-i", "sine=frequency=330:duration=6",
      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"], "canh ngang.mp4")
chay(["-f", "lavfi", "-i", "smptebars=size=1920x1080:rate=30:duration=5",
      "-f", "lavfi", "-i", "sine=frequency=550:duration=5",
      "-c:v", "libx265", "-tag:v", "hvc1", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"], "_hevc.mov")
# Gắn cờ xoay như iPhone quay dọc (display matrix), không mã hoá lại.
chay(["-display_rotation:v:0", "90", "-i", os.path.join(OUT, "_hevc.mov"), "-c", "copy", "-tag:v", "hvc1"], "IMG_0896.mov")
os.remove(os.path.join(OUT, "_hevc.mov"))
chay(["-f", "lavfi", "-i", "color=c=0x8b5cf6:size=512x256:duration=1", "-frames:v", "1"], "logo.png")
