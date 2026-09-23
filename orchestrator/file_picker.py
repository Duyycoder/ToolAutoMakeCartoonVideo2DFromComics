"""Hộp thoại chọn file/thư mục của hệ điều hành — chạy như một TIẾN TRÌNH RIÊNG.

Vì sao không dùng `<input type="file">`: trình duyệt lẫn WebView2 chỉ cho biết
TÊN file chứ không cho đường dẫn thật, mà video hàng GB thì không thể upload lên
để lấy nội dung. Công cụ chạy ngay trên máy người dùng nên cách đúng là mở hộp
thoại ở phía máy chủ rồi trả về đường dẫn.

Vì sao là tiến trình riêng: tkinter đòi chạy ở luồng chính, gọi thẳng trong luồng
xử lý request của uvicorn là treo cả app.

    python -m orchestrator.file_picker --mode files
    {"paths": ["D:\\phim\\tap1.mp4"], "cancelled": false}

Luôn in ĐÚNG MỘT dòng JSON ra stdout, kể cả khi lỗi, để bên gọi chỉ việc đọc
dòng cuối.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator.storage import VIDEO_EXTS  # noqa: E402


def pick(mode: str, title: str = "") -> dict:
    """Mở hộp thoại và trả {"paths": [...], "cancelled": bool}."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    # Thiếu dòng này thì hộp thoại hiện ra SAU cửa sổ ứng dụng và người dùng
    # tưởng app treo — lỗi này hay gặp nhất khi chạy trong WebView2.
    root.attributes("-topmost", True)
    try:
        if mode == "folder":
            chosen = filedialog.askdirectory(
                parent=root, title=title or "Chọn thư mục chứa video")
            paths = [chosen] if chosen else []
        else:
            patterns = " ".join("*" + ext for ext in VIDEO_EXTS)
            chosen = filedialog.askopenfilenames(
                parent=root, title=title or "Chọn video (giữ Ctrl/Shift để chọn nhiều)",
                filetypes=[("Video", patterns), ("Tất cả các file", "*.*")])
            paths = list(chosen or ())
    finally:
        root.destroy()
    return {"paths": [os.path.abspath(p) for p in paths], "cancelled": not paths}


def main():
    parser = argparse.ArgumentParser(description="Hộp thoại chọn video của hệ điều hành")
    parser.add_argument("--mode", default="files", choices=("files", "folder"))
    parser.add_argument("--title", default="")
    args = parser.parse_args()

    # Đường dẫn tiếng Việt sẽ thành dấu hỏi nếu stdout không phải UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    try:
        result = pick(args.mode, args.title)
    except Exception as e:  # thiếu tkinter, không có màn hình, người dùng tắt ngang...
        result = {"paths": [], "cancelled": True, "error": str(e)}
    print(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
