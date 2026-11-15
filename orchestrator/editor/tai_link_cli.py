"""CLI tải link nhẹ cho editor chạy trên server (không cần AIVoice/.venv, không torch).

Dùng khi máy không có adapter AIVoice (vd server Linux chỉ cài venv orchestrator).
Phát cùng bộ JSON event với `adapter_download_cli.py` để `media.tai_url` đọc như cũ:
    item_start | download_progress | item_done | item_failed
Chạy: python -m orchestrator.editor.tai_link_cli --output-dir DIR --url U [--url U2] [--cookies-file F]
"""
import argparse
import json
import os
import sys


def log_json(event: str, data: dict) -> None:
    print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


def ffmpeg_exe() -> str:
    """ffmpeg đi kèm imageio-ffmpeg (server không có ffmpeg hệ thống); thiếu thì để yt-dlp tự tìm."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return ""


def tuy_chon(out_dir: str, cookies: str) -> dict:
    def tien_do(d):
        if d.get("status") != "downloading":
            return
        tong = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        if tong:
            log_json("download_progress", {"percent": round(d.get("downloaded_bytes", 0) * 100 / tong, 1)})

    opts = {
        "outtmpl": os.path.join(out_dir, "%(extractor_key)s_%(id)s.%(ext)s"),
        # Ưu tiên H.264 + AAC trong mp4 để trình duyệt điện thoại xem trước được ngay.
        "format": "bv*[vcodec^=avc1][height<=1080]+ba[ext=m4a]/b[ext=mp4][height<=1080]/bv*[height<=1080]+ba/b",
        "merge_output_format": "mp4",
        "restrictfilenames": True,
        "noprogress": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [tien_do],
    }
    ff = ffmpeg_exe()
    if ff:
        opts["ffmpeg_location"] = ff
    if cookies and os.path.isfile(cookies):
        opts["cookiefile"] = cookies
    return opts


def duong_dan_da_tai(entry: dict) -> str:
    for d in entry.get("requested_downloads") or []:
        if d.get("filepath") and os.path.isfile(d["filepath"]):
            return d["filepath"]
    path = entry.get("filepath") or entry.get("_filename") or ""
    return path if path and os.path.isfile(path) else ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--cookies-file", default="")
    ap.add_argument("--platform", default="generic")  # giữ tương thích lệnh của adapter cũ
    args = ap.parse_args(argv)
    try:
        import yt_dlp
    except ImportError:
        log_json("batch_failed", {"error": "Server chưa cài yt-dlp (pip install yt-dlp)."})
        return 1

    os.makedirs(args.output_dir, exist_ok=True)
    urls = [u.strip() for u in args.url if u.strip()]
    so_xong = 0
    with yt_dlp.YoutubeDL(tuy_chon(args.output_dir, args.cookies_file)) as ydl:
        for i, url in enumerate(urls, 1):
            log_json("item_start", {"index": i, "total": len(urls), "title": url})
            try:
                info = ydl.extract_info(url, download=True) or {}
            except Exception as e:  # yt-dlp ném DownloadError/ExtractorError với thông điệp dễ đọc
                log_json("item_failed", {"url": url, "error": f"{url}: {e}"})
                continue
            entries = info.get("entries") if info.get("_type") == "playlist" else [info]
            for entry in entries or []:
                path = duong_dan_da_tai(entry or {})
                if path:
                    so_xong += 1
                    log_json("item_done", {"path": path, "title": entry.get("title") or "", "url": url})
                else:
                    log_json("item_failed", {"url": url, "error": f"{url}: tải xong nhưng không thấy file"})
    return 0 if so_xong else 1


if __name__ == "__main__":
    sys.exit(main())
