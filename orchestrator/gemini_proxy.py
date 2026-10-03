"""Quản lý proxy Gemini-API (toolCaoTruyen/Gemini-API) chạy cục bộ trên cổng 7860.

Proxy giả lập API OpenAI bằng phiên đăng nhập gemini.google.com, nên chỉ cần 2
cookie `__Secure-1PSID` và `__Secure-1PSIDTS`. Hai cookie lưu ở Cấu Hình Chung
(translate.gemini_psid / translate.gemini_psidts) rồi ghi ra cookies.json của
proxy mỗi lần khởi động.

Cookie hết hạn thì proxy VẪN khởi động được (thư viện chỉ cảnh báo
UNAUTHENTICATED rồi chạy chế độ khách) — nên trạng thái phải hỏi /health lấy
account_status chứ không dựa vào việc tiến trình còn sống.
"""
import json
import os
import secrets
import string
import subprocess
import tempfile
import threading
import time
import urllib.request

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGS_DIR = os.path.join(ROOT_DIR, "logs")
LOG_PATH = os.path.join(LOGS_DIR, "gemini_api.log")
MAC_DINH_THU_MUC = os.path.join(ROOT_DIR, "toolCaoTruyen", "Gemini-API")
PORT = 7860
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_proc = None
_bat_dau_luc = 0.0
_khoa = threading.Lock()


def _cfg():
    from orchestrator.config import load_global_config
    return load_global_config()


def thu_muc_proxy():
    """Thư mục proxy: theo translate.gemini_proxy_bat nếu khai báo, không thì bản đi kèm."""
    try:
        bat = ((_cfg().get("translate") or {}).get("gemini_proxy_bat") or "").strip()
    except Exception:
        bat = ""
    if bat:
        bat = bat if os.path.isabs(bat) else os.path.join(ROOT_DIR, bat)
        return os.path.dirname(bat) if bat.lower().endswith(".bat") else bat
    return MAC_DINH_THU_MUC


def _python_proxy(thu_muc):
    """Python của .venv toolCaoTruyen (cạnh thư mục proxy) — nơi đã cài gemini_webapi.
    Bản cài đặt không mang .venv nào theo (bộ cài loại trừ) -> dùng Python của app (AIVoice\\.venv),
    gemini_webapi lấy từ src/ đi kèm, thư viện phụ cài qua orchestrator/requirements.txt."""
    for p in (os.path.join(thu_muc, "..", ".venv", "Scripts", "python.exe"),
              os.path.join(thu_muc, ".venv", "Scripts", "python.exe"),
              os.path.join(ROOT_DIR, "AIVoice", ".venv", "Scripts", "python.exe")):
        if os.path.exists(p):
            return os.path.abspath(p)
    return None


def _la_python_app(py):
    return os.path.normcase(py).startswith(os.path.normcase(os.path.join(ROOT_DIR, "AIVoice")))


def doc_cookie():
    tr = _cfg().get("translate") or {}
    return (tr.get("gemini_psid") or "").strip(), (tr.get("gemini_psidts") or "").strip()


def _dong_bo_cookie(thu_muc):
    """Cấu hình -> cookies.json. Cấu hình còn trống mà cookies.json cũ có giá trị
    thì nhập ngược vào cấu hình (máy đã dùng proxy từ trước không phải điền lại)."""
    from orchestrator.config import save_global_config
    psid, psidts = doc_cookie()
    duong_dan = os.path.join(thu_muc, "cookies.json")
    if not psid:
        try:
            with open(duong_dan, "r", encoding="utf-8") as f:
                cu = json.load(f)
            if isinstance(cu, list):
                cu = {c.get("name"): c.get("value") for c in cu if isinstance(c, dict)}
            psid = (cu.get("__Secure-1PSID") or "").strip()
            psidts = (cu.get("__Secure-1PSIDTS") or "").strip()
        except (OSError, ValueError, AttributeError):
            return "", ""
        if psid and "PASTE" not in psid.upper():
            cfg = _cfg()
            cfg.setdefault("translate", {}).update(gemini_psid=psid, gemini_psidts=psidts)
            save_global_config(cfg)
        else:
            return "", ""
    with open(duong_dan, "w", encoding="utf-8") as f:
        json.dump({"__Secure-1PSID": psid, "__Secure-1PSIDTS": psidts}, f, indent=2)
    return psid, psidts


def ghi_cookie_json(psid, psidts):
    """Ghi ngay 2 cookie vào cookies.json của proxy (đúng định dạng proxy đọc:
    server/config.py::load_cookies). Trả đường dẫn đã ghi, None nếu không có proxy."""
    thu_muc = thu_muc_proxy()
    if not os.path.isdir(thu_muc):
        return None
    duong_dan = os.path.join(thu_muc, "cookies.json")
    with open(duong_dan, "w", encoding="utf-8") as f:
        json.dump({"__Secure-1PSID": psid, "__Secure-1PSIDTS": psidts}, f, indent=2)
    return duong_dan


def thu_muc_cache_cookie():
    """Nơi gemini_webapi lưu cookie đã xoay vòng (utils/rotate_1psidts.py::_get_cookie_cache_dir).
    Đặt hẳn GEMINI_COOKIE_PATH cho tiến trình proxy để hai bên chắc chắn cùng một chỗ."""
    return os.environ.get("GEMINI_COOKIE_PATH") or os.path.join(tempfile.gettempdir(), "gemini_webapi")


def xoa_cache_cookie(psid):
    """gemini_webapi thử cookie CACHE (theo __Secure-1PSID) TRƯỚC cookie truyền vào, và trang Gemini
    ở chế độ khách vẫn trả về hợp lệ -> nó coi là xong, không bao giờ thử 1PSIDTS mới. Cùng tài khoản
    thì 1PSID không đổi nên cookie vừa dán luôn bị bản cache hết hạn đè -> xoá cache khi lưu cookie mới."""
    if not psid:
        return False
    duong_dan = os.path.join(thu_muc_cache_cookie(), f".cached_cookies_{psid}.json")
    try:
        os.remove(duong_dan)
        return True
    except OSError:
        return False


def luu_cookie(psid, psidts):
    """Cookie mới từ giao diện: cấu hình chung + cookies.json, xoá cache cũ, rồi bật lại proxy."""
    from orchestrator.config import save_global_config
    cfg = _cfg()
    cfg.setdefault("translate", {}).update(gemini_psid=psid, gemini_psidts=psidts)
    if not save_global_config(cfg):
        raise OSError("Không ghi được configs/global_config.json.")
    duong_dan = ghi_cookie_json(psid, psidts)
    # Proxy cũ có thể ghi lại cache khi xoay vòng -> xoá SAU khi nó đã tắt hẳn, ngay trước lúc bật lại.
    return {"ma": khoi_dong_lai(lambda: xoa_cache_cookie(psid)), "cookies_json": duong_dan}


def _dam_bao_api_key(thu_muc):
    """Proxy đòi Bearer key có trong api_keys.json; tự tạo và ghi vào
    translate.gemini_offline_key để llm.py dùng, người dùng không phải đụng tới."""
    from orchestrator.config import save_global_config
    duong_dan = os.path.join(thu_muc, "api_keys.json")
    try:
        with open(duong_dan, "r", encoding="utf-8") as f:
            keys = json.load(f)
        if not isinstance(keys, dict):
            keys = {}
    except (OSError, ValueError):
        keys = {}
    cfg = _cfg()
    tr = cfg.setdefault("translate", {})
    hien_tai = (tr.get("gemini_offline_key") or "").strip()
    if hien_tai and hien_tai in keys:
        return hien_tai
    key = next(iter(keys), None)
    if not key:
        key = "sk-gemini-" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(40))
        keys[key] = "app"
        with open(duong_dan, "w", encoding="utf-8") as f:
            json.dump(keys, f, indent=2)
    tr["gemini_offline_key"] = key
    save_global_config(cfg)
    return key


def _port_mo():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def khoi_dong():
    """Bật proxy ẩn. Trả mã trạng thái ngắn để log; không ném lỗi."""
    global _proc, _bat_dau_luc
    with _khoa:
        thu_muc = thu_muc_proxy()
        if not os.path.isdir(os.path.join(thu_muc, "server")):
            return "khong_co_proxy"
        if _proc is not None and _proc.poll() is None:
            return "dang_chay"
        if _port_mo():
            return "dang_chay_ngoai"  # ai đó đã tự bật (vd start_server.bat)
        try:
            psid, _ = _dong_bo_cookie(thu_muc)
        except OSError as e:
            print(f"[WARN] Khong ghi duoc cookies.json cua Gemini proxy: {e}")
            return "loi"
        if not psid:
            return "chua_co_cookie"
        _dam_bao_api_key(thu_muc)
        py = _python_proxy(thu_muc)
        if not py:
            print("[WARN] Khong thay .venv cua toolCaoTruyen -> khong bat duoc Gemini proxy.")
            return "thieu_venv"
        os.makedirs(LOGS_DIR, exist_ok=True)
        # Python của app không cài gemini_webapi -> lấy bản src/ đi kèm (venv toolCaoTruyen đã có bản pip, giữ nguyên).
        duong = [thu_muc] + ([os.path.join(thu_muc, "src")] if _la_python_app(py) else [])
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(duong), PYTHONIOENCODING="utf-8",
                   GEMINI_COOKIE_PATH=thu_muc_cache_cookie())
        with open(LOG_PATH, "a", encoding="utf-8") as log:
            log.write(f"\n===== Khoi dong Gemini proxy {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
            log.flush()
            _proc = subprocess.Popen(
                [py, "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
                cwd=thu_muc, env=env, stdout=log, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
            )
        _bat_dau_luc = time.time()
        print(f"[INFO] Da khoi dong Gemini proxy (PID {_proc.pid}, log: logs/gemini_api.log).")
        return "dang_khoi_dong"


def dung():
    global _proc
    with _khoa:
        if _proc is None:
            return
        from orchestrator.process_manager import ProcessManager
        ProcessManager._kill_process_tree(_proc)
        _proc = None
        print("[INFO] Da tat Gemini proxy.")


def _diet_tien_trinh_giu_cong():
    """Proxy bật từ lần mở app trước / start_server.bat vẫn giữ cổng 7860 thì
    cookie mới không bao giờ được nạp -> tắt tiến trình đang LISTEN cổng này."""
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
                             creationflags=NO_WINDOW, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return
    for dong in out.splitlines():
        cot = dong.split()
        if len(cot) >= 5 and cot[1].endswith(f":{PORT}") and cot[3].upper() == "LISTENING":
            subprocess.run(["taskkill", "/PID", cot[4], "/T", "/F"], capture_output=True,
                           creationflags=NO_WINDOW)


def khoi_dong_lai(truoc_khi_bat=None):
    dung()
    if _port_mo():
        _diet_tien_trinh_giu_cong()
    for _ in range(20):  # chờ cổng nhả ra
        if not _port_mo():
            break
        time.sleep(0.25)
    if truoc_khi_bat:
        truoc_khi_bat()
    return khoi_dong()


def _health():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _duoi_log(n=4000):
    try:
        with open(LOG_PATH, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - n))
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


def trang_thai():
    """{ma, thong_bao}. ma: san_sang | cookie_het_han | chua_co_cookie |
    dang_khoi_dong | loi | khong_co_proxy | thieu_venv | da_tat."""
    thu_muc = thu_muc_proxy()
    if not os.path.isdir(os.path.join(thu_muc, "server")):
        return {"ma": "khong_co_proxy", "thong_bao": f"Không thấy proxy Gemini-API ở {thu_muc}."}
    if not doc_cookie()[0]:
        return {"ma": "chua_co_cookie", "thong_bao": "Chưa điền cookie Gemini."}
    h = _health()
    if h is not None:
        if not h.get("gemini_ready"):
            return {"ma": "dang_khoi_dong", "thong_bao": "Proxy đang đăng nhập Gemini..."}
        tk = h.get("account_status")
        if tk and tk != "AVAILABLE":
            return {"ma": "cookie_het_han", "thong_bao": f"Gemini báo tài khoản: {tk} — cookie đã hết hạn hoặc sai."}
        return {"ma": "san_sang", "thong_bao": "Gemini proxy sẵn sàng.", "account_status": tk}
    if _proc is not None and _proc.poll() is None:
        if time.time() - _bat_dau_luc < 90:
            return {"ma": "dang_khoi_dong", "thong_bao": "Proxy đang khởi động..."}
        return {"ma": "loi", "thong_bao": "Proxy chạy nhưng không trả lời /health.", "log": _duoi_log(1500)}
    if _proc is None:
        if not _python_proxy(thu_muc):
            return {"ma": "thieu_venv", "thong_bao": "Chưa cài môi trường Python nên không bật được proxy Gemini — "
                    "chạy \"AutoCartoon - Cai dat moi truong\" trong menu Start."}
        return {"ma": "da_tat", "thong_bao": "Proxy chưa được bật."}
    log = _duoi_log()
    log = log[log.rfind("===== Khoi dong Gemini proxy"):] if "===== Khoi dong Gemini proxy" in log else log
    if any(s in log for s in ("Failed to initialize Gemini client", "AuthError", "cookies have expired",
                              "Failed to refresh cookies", "SNlM0e")):
        return {"ma": "cookie_het_han", "thong_bao": "Không đăng nhập được Gemini — cookie đã hết hạn hoặc sai.",
                "log": log[-1500:]}
    return {"ma": "loi", "thong_bao": "Proxy Gemini đã dừng bất thường.", "log": log[-1500:]}


def ping(cau="Trả lời đúng một từ: pong", timeout=60):
    """Gửi 1 câu hỏi thật qua proxy để chắc cookie dùng được (không chỉ là tiến trình sống).

    ok=True chỉ khi tài khoản đăng nhập được (AVAILABLE) VÀ Gemini trả lời —
    chế độ khách cũng trả lời được nên không tính là chuẩn.
    """
    tt = trang_thai()
    kq = {"ok": False, "ma": tt["ma"], "thong_bao": tt["thong_bao"],
          "account_status": tt.get("account_status"), "tra_loi": "", "ms": None}
    if tt["ma"] not in ("san_sang", "cookie_het_han"):
        return kq
    tr = _cfg().get("translate") or {}
    key = tr.get("gemini_offline_key") or ""
    from orchestrator.config import DEFAULT_GEMINI_PROXY_MODEL
    body = json.dumps({"model": DEFAULT_GEMINI_PROXY_MODEL,
                       "messages": [{"role": "user", "content": cau}]}).encode("utf-8")
    rq = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", body,
                                {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        kq["tra_loi"] = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()[:200]
        kq["model"] = data.get("model")
    except Exception as e:  # HTTPError 401/502, hết giờ...
        chi_tiet = ""
        if hasattr(e, "read"):
            try:
                chi_tiet = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
        kq["thong_bao"] = f"Gửi thử thất bại: {e} {chi_tiet}".strip()
        return kq
    kq["ms"] = int((time.time() - t0) * 1000)
    if not kq["tra_loi"]:
        kq["thong_bao"] = "Gemini không trả lời gì."
    elif tt["ma"] == "cookie_het_han":
        kq["thong_bao"] = ("Gemini trả lời nhưng ở CHẾ ĐỘ KHÁCH — cookie chưa đăng nhập được, "
                           "chạy song song sẽ bị từ chối. Hãy lấy lại cookie.")
    else:
        kq["ok"] = True
        kq["thong_bao"] = f"Cookie chuẩn — Gemini trả lời sau {kq['ms'] / 1000:.1f}s."
    return kq
