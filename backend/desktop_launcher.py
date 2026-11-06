"""Mở Easy3D trong cửa sổ desktop (WebView2 qua pywebview), backend chạy ẩn cùng tiến trình.

Chạy:  .venv\\Scripts\\pythonw.exe -m backend.desktop_launcher   (không console, log -> logs/app.log)
       .venv\\Scripts\\python.exe  -m backend.desktop_launcher   (debug, log ra console)
Thiếu pywebview/WebView2 -> tự mở trình duyệt mặc định.
"""
import os
import socket
import sys
import threading
import time
import webbrowser

from backend.config import LOGS_DIR, load_config

WINDOW_TITLE = "Easy3D"


def _ensure_streams():
    """Dưới pythonw, stdout/stderr là None -> chuyển về logs/app.log."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_file = open(LOGS_DIR / "app.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or log_file
    sys.stderr = sys.stderr or log_file


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _start_server(host: str, port: int):
    import uvicorn
    from backend.main import app

    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="info"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):  # chờ tối đa ~10 s
        if _port_open(host, port):
            return server
        time.sleep(0.1)
    raise RuntimeError(f"Backend khong khoi dong duoc tren cong {port}")


def main() -> int:
    _ensure_streams()
    cfg = load_config()["server"]
    host, port = cfg["host"], int(cfg["port"])
    if _port_open(host, port):
        print(f"[LOI] Cong {port} dang bi chiem - co the Easy3D dang chay roi.")
        return 1
    server = _start_server(host, port)
    url = f"http://{host}:{port}/"
    try:
        import webview
        webview.create_window(WINDOW_TITLE, url, width=1400, height=900, min_size=(1000, 650))
        webview.start()
    except Exception as exc:  # thiếu pywebview / WebView2 runtime
        print(f"[CANH BAO] Khong mo duoc cua so desktop ({exc}) - mo trinh duyet.")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    server.should_exit = True
    return 0


if __name__ == "__main__":
    sys.exit(main())
