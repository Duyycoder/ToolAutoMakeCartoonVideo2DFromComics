"""Desktop launcher: mo orchestrator trong cua so ung dung (WebView2) thay vi tab trinh duyet.

Chay:  "AIVoice\\.venv\\Scripts\\pythonw.exe" -m orchestrator.desktop   (khong console, log ra logs/app.log)
hoac:  "AIVoice\\.venv\\Scripts\\python.exe"  -m orchestrator.desktop   (debug: log ra console)

Launcher nay tu quan ly Gemini-API proxy (chay an, khong mo cua so cmd) va khi
dong cua so app se diet sach: uvicorn, proxy, va moi tien trinh AI con dang chay.
Neu may thieu pywebview/WebView2 runtime -> tu fallback ve trinh duyet.
Co `--smoke`: mo cua so, cho trang load xong roi tu dong dong sau vai giay (kiem thu).
"""
import os
import socket
import subprocess
import sys
import threading
import time

HOST = "127.0.0.1"
PORT = 8100
URL = f"http://{HOST}:{PORT}/"
GEMINI_PROXY_PORT = 7860
WINDOW_TITLE = "Cao & Dich Video"
# main.py resolve "storage"/"webui"/"AIVoice/.venv" theo CWD -> phai dung o goc repo
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGS_DIR = os.path.join(ROOT_DIR, "logs")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


LOG_MAX_BYTES = 5 * 1024 * 1024   # qua co nay thi xoay vong luc mo app
LOG_KEEP_TAIL = 1024 * 1024       # giu 1 MB cuoi de con tra loi cua lan chay truoc


def _rotate_log(path, max_bytes=LOG_MAX_BYTES, keep_tail=LOG_KEEP_TAIL):
    """app.log chi ghi noi them nen lon mai - da tung phinh toi gan 1 GB.

    Moi lan mo app: qua `max_bytes` thi cat lay `keep_tail` byte cuoi sang
    app.log.old roi bat dau file moi. Khong giu nguyen ca file cu vi nhu vay
    lan xoay dau tien van de lai nguyen mot file 1 GB tren dia.
    """
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if size <= max_bytes:
        return
    try:
        with open(path, "rb") as src:
            src.seek(max(0, size - keep_tail))
            tail = src.read()
        with open(path + ".old", "wb") as dst:
            dst.write(tail)
        os.remove(path)
    except OSError:
        pass  # file dang bi tien trinh khac giu (app cu chua tat) -> de lan sau


def _ensure_streams():
    """Duoi pythonw, sys.stdout/stderr la None -> moi print/log se lam
    logging noi tung. Chuyen het ve logs/app.log de van doc duoc khi can."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = os.path.join(LOGS_DIR, "app.log")
    _rotate_log(log_path)
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = log_file
    if sys.stderr is None:
        sys.stderr = log_file


def _port_open(port: int, host: str = HOST) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _gemini_proxy_bat():
    """Duong dan start_server.bat cua proxy Gemini-API, doc tu cau hinh.

    Nhanh nay khong kem theo proxy (no thuoc bo cao truyen). Ai tu cai o cho khac
    thi khai bao duong dan o Cau Hinh -> translate.gemini_proxy_bat; de trong thi
    app bo qua, dich bang Ollama hoac Gemini Online.
    """
    try:
        from orchestrator.config import load_global_config
        path = ((load_global_config().get("translate") or {}).get("gemini_proxy_bat") or "").strip()
    except Exception:
        return None
    if not path:
        return None
    return path if os.path.isabs(path) else os.path.join(ROOT_DIR, path)


def _start_gemini_proxy():
    """Chay Gemini-API proxy AN (khong mo cua so cmd rieng nhu run.bat cu).

    Tra ve Popen de kill khi dong app; None neu proxy da chay san / thieu file.
    """
    bat = _gemini_proxy_bat()
    if not bat or not os.path.exists(bat):
        return None
    if _port_open(GEMINI_PROXY_PORT):
        print(f"[INFO] Gemini proxy da chay san tren cong {GEMINI_PROXY_PORT}.")
        return None
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_file = open(os.path.join(LOGS_DIR, "gemini_api.log"), "a",
                    encoding="utf-8", buffering=1)
    try:
        proc = subprocess.Popen(
            ["cmd", "/c", bat],
            cwd=os.path.dirname(bat),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
        )
        print(f"[INFO] Da khoi dong Gemini proxy (PID {proc.pid}, log: logs/gemini_api.log).")
        return proc
    except Exception as e:
        print(f"[WARN] Khong khoi dong duoc Gemini proxy: {e}")
        return None
    finally:
        log_file.close()  # child da giu handle rieng


def _start_ollama():
    """Khoi dong Ollama serve an neu cong 11434 chua mo."""
    if _port_open(11434):
        print("[INFO] Ollama da chay san tren cong 11434.")
        return None
    try:
        proc = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
        )
        print(f"[INFO] Da khoi dong Ollama serve (PID {proc.pid}).")
        return proc
    except Exception as e:
        print(f"[WARN] Khong khoi dong duoc Ollama serve: {e}")
        return None


def _start_server():
    import uvicorn

    config = uvicorn.Config("orchestrator.main:app", host=HOST, port=PORT, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


def _wait_until_ready(timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(PORT):
            return True
        time.sleep(0.3)
    return False


# Luon tra Promise: evaluate_js cua pywebview CHI goi callback khi ket qua la Promise,
# gia tri thuong (vd trang chu khong co editor) thi callback khong bao gio chay.
FLUSH_JS = "Promise.resolve((window.editor && window.editor.dong) ? window.editor.dong() : true)"
FLUSH_TIMEOUT = 5.0


def _gan_flush_khi_dong(window, timeout=FLUSH_TIMEOUT):
    """Dong cua so = luu not tien do editor (timeline, ui, hoan tac) roi moi dong that.

    Su kien `closing` cua pywebview chay DONG BO tren luong giao dien: goi
    evaluate_js ngay trong do se treo (evaluate_js cung can luong giao dien).
    Nen lan dong dau tien: HUY dong, flush o luong rieng (cho Promise cua
    editor.flush() toi `timeout` giay), roi destroy() -> lan closing thu hai
    duoc cho qua (confirm_close van hoi nhu cu).
    """
    trang_thai = {"cho_phep": False}

    def _flush():
        xong = threading.Event()
        try:
            window.evaluate_js(FLUSH_JS, callback=lambda _kq: xong.set())
        except Exception as e:  # trang chua tai xong / da dong
            print(f"[WARN] Khong flush duoc editor truoc khi dong: {e}")
            return
        if not xong.wait(timeout):
            print(f"[WARN] editor.flush() qua {timeout:.0f}s chua xong - dong luon.")

    def _flush_roi_dong():
        _flush()
        trang_thai["cho_phep"] = True
        try:
            window.destroy()
        except Exception:
            pass

    def on_closing():
        if trang_thai["cho_phep"]:
            trang_thai["cho_phep"] = False
            return None
        threading.Thread(target=_flush_roi_dong, daemon=True).start()
        return False

    window.events.closing += on_closing
    return on_closing


def _shutdown(server, thread, gemini_proc):
    """Dong app = diet sach: tien trinh AI con -> Gemini proxy -> uvicorn."""
    from orchestrator.process_manager import ProcessManager

    try:
        # Cung process voi uvicorn nen day chinh la singleton dang giu cac task
        import orchestrator.main as orchestrator_main
        orchestrator_main.process_mgr.stop_all()
    except Exception as e:
        print(f"[WARN] Loi khi dung cac tien trinh con: {e}")

    if gemini_proc is not None:
        ProcessManager._kill_process_tree(gemini_proc)
        print("[INFO] Da tat Gemini proxy.")

    if server is not None:
        server.should_exit = True
        thread.join(timeout=10)
    print("[INFO] Da thoat ung dung, cac tien trinh da duoc don sach.")


def _run_browser_fallback(server, thread, gemini_proc, ly_do: str = ""):
    import webbrowser

    # Ghi ro LY DO. Truoc day chi bao "khong mo duoc cua so" nen khong the biet
    # la thieu goi pywebview hay thieu WebView2 Runtime - hai cach sua khac han.
    print("[WARN] Khong mo duoc cua so desktop -> dung trinh duyet (fallback).")
    if ly_do:
        print(f"[WARN] Ly do: {ly_do}")
    webbrowser.open(URL)
    if server is None:
        return
    try:
        thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown(server, thread, gemini_proc)


def main() -> int:
    _ensure_streams()
    os.chdir(ROOT_DIR)
    smoke = "--smoke" in sys.argv
    print(f"\n===== {WINDOW_TITLE} khoi dong luc {time.strftime('%Y-%m-%d %H:%M:%S')} =====")

    gemini_proc = _start_gemini_proxy()

    server = thread = None
    if _port_open(PORT):
        print(f"[INFO] Orchestrator da chay san tren cong {PORT} -> chi mo cua so.")
    else:
        server, thread = _start_server()
        if not _wait_until_ready():
            print(f"[ERROR] Orchestrator khong khoi dong duoc tren cong {PORT}.")
            _shutdown(server, thread, gemini_proc)
            return 1

    try:
        import webview
    except ImportError:
        _run_browser_fallback(
            server, thread, gemini_proc,
            "Thieu goi pywebview trong AIVoice/.venv. "
            "Sua bang: nhay dup CAP-NHAT.bat, hoac chay setup.bat mot lan.",
        )
        return 0

    loaded = threading.Event()
    try:
        window = webview.create_window(
            WINDOW_TITLE,
            URL,
            width=1280,
            height=840,
            min_size=(1100, 720),
            confirm_close=not smoke,
            text_select=True,
        )
        window.events.loaded += lambda: loaded.set()
        _gan_flush_khi_dong(window)

        if smoke:
            def _auto_close():
                loaded.wait(timeout=20)
                time.sleep(3)
                window.destroy()

            webview.start(_auto_close)
        else:
            webview.start()
    except Exception as e:
        # vd: thieu WebView2 runtime tren Windows 10 doi cu
        _run_browser_fallback(
            server, thread, gemini_proc,
            f"Loi khoi tao WebView2 ({e}). Thuong la may chua co WebView2 Runtime. "
            "Sua bang: nhay dup CAP-NHAT.bat, hoac chay scripts\\cai_webview2.bat.",
        )
        return 0

    _shutdown(server, thread, gemini_proc)

    if smoke and not loaded.is_set():
        print("[ERROR] Smoke test: trang chua load xong truoc khi dong cua so.")
        return 2
    if smoke:
        print("[OK] Smoke test: cua so desktop mo va load giao dien thanh cong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
