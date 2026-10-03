"""Đề xuất engine dịch theo số câu + những gì máy đang có (cookie, API key, Ollama).

Tốc độ lấy từ số đo thật trên máy này, không phải con số quảng cáo:
- Ollama hy-mt2 1.8B Q8, 8 luồng lô 12 câu: ~0,24 s/câu (29/09/2026, RTX 3060 6 GB).
- Gemini cookie, lô 100 câu ≈ 14 s, 2 luồng; sau ~30 lô liên tiếp Google bắt đầu hạn chế
  tài khoản (02/10/2026) → quá ~3.000 câu phần dư sẽ rơi về Ollama.
- Gemini API key: CHƯA đo, ước theo 8 luồng lô 100 câu ~12 s.
"""
import math
from typing import Any, Dict

from orchestrator.config import load_global_config

CAU_S_OLLAMA = 4.0
CAU_S_COOKIE = 7.0
CAU_S_KEY = 60.0
NGUONG_COOKIE = 3000


def _co_key(g: Dict[str, Any]) -> bool:
    k = ((g.get("api_keys") or {}).get("gemini") or "").strip()
    return bool(k) and "DIEN_" not in k and "YOUR_" not in k


def _ollama(g: Dict[str, Any]) -> Dict[str, Any]:
    from orchestrator import ollama_manager
    base = (g.get("translate") or {}).get("ollama_base_url", "")
    if ollama_manager.is_server_up(ollama_manager.to_root(base), timeout=1.0):
        return {"san_sang": True, "trang_thai": "Ollama đang chạy"}
    if ollama_manager.find_ollama_exe():
        return {"san_sang": True, "trang_thai": "Ollama đã cài, app tự bật khi dịch"}
    return {"san_sang": False, "trang_thai": "Chưa cài Ollama"}


def _so(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _thoi_gian(giay: float) -> str:
    giay = max(1, int(math.ceil(giay)))
    if giay < 60:
        return f"~{giay} giây"
    phut = giay / 60
    return f"~{phut:.0f} phút" if phut < 90 else f"~{phut / 60:.1f} giờ"


def de_xuat(so_cau: int) -> Dict[str, Any]:
    from orchestrator import gemini_proxy
    g = load_global_config()
    n = max(0, int(so_cau or 0))
    tt = gemini_proxy.trang_thai()
    cookie_ok = tt["ma"] in ("san_sang", "dang_khoi_dong", "da_tat") and bool(gemini_proxy.doc_cookie()[0])
    key_ok = _co_key(g)
    ol = _ollama(g)

    if n <= NGUONG_COOKIE:
        giay_cookie = n / CAU_S_COOKIE
    else:
        giay_cookie = NGUONG_COOKIE / CAU_S_COOKIE + (n - NGUONG_COOKIE) / CAU_S_OLLAMA

    engines = [
        {"id": "gemini_api", "ten": "Gemini (cookie đăng nhập)", "san_sang": cookie_ok,
         "trang_thai": tt["thong_bao"] if not cookie_ok else ("Đã kết nối" if tt["ma"] == "san_sang" else tt["thong_bao"]),
         "uoc_tinh": _thoi_gian(giay_cookie), "chi_phi": "Miễn phí",
         "uu": "Dịch hay nhất: hiểu ngữ cảnh 100 câu liền nhau nên xưng hô, thành ngữ tự nhiên; không tốn GPU.",
         "nhuoc": f"Cần mạng + cookie còn hạn. Quá ~{_so(NGUONG_COOKIE)} câu một lúc Google hay tạm chặn — phần dư tự chuyển Ollama."},
        {"id": "gemini", "ten": "Gemini API key (trả phí)", "san_sang": key_ok,
         "trang_thai": "Đã có API key" if key_ok else "Chưa nhập API key ở ⚙ Cấu hình",
         "uoc_tinh": _thoi_gian(n / CAU_S_KEY) + " (ước tính)", "chi_phi": "Vài nghìn đồng / 10.000 câu",
         "uu": "Nhanh nhất, chạy song song nhiều luồng không bị chặn; chất lượng như Gemini cookie.",
         "nhuoc": "Tốn phí theo lượng chữ; cần mạng."},
        {"id": "ollama", "ten": "Ollama trên máy (offline)", "san_sang": ol["san_sang"], "trang_thai": ol["trang_thai"],
         "uoc_tinh": _thoi_gian(n / CAU_S_OLLAMA), "chi_phi": "Miễn phí",
         "uu": "Không cần mạng, không giới hạn số câu, dữ liệu không rời máy.",
         "nhuoc": "Model nhỏ 1,8B nên dịch sát chữ hơn, xưng hô kém nhất quán; chiếm GPU (không chạy song song được với tạo ảnh/lồng tiếng)."},
    ]

    if key_ok and (n > NGUONG_COOKIE or not cookie_ok):
        chon, ly_do = "gemini", (f"{_so(n)} câu là nhiều — API key dịch nhanh nhất ({_thoi_gian(n / CAU_S_KEY)}) và không lo bị chặn."
                                if n > NGUONG_COOKIE else "Đã có API key: nhanh và ổn định nhất.")
    elif cookie_ok:
        chon = "gemini_api"
        ly_do = ("Miễn phí và dịch hay nhất; số câu vừa sức một tài khoản."
                 if n <= NGUONG_COOKIE else
                 f"Miễn phí và dịch hay nhất, nhưng {_so(n)} câu vượt mức an toàn ~{_so(NGUONG_COOKIE)} câu: phần sau có thể bị Google chặn "
                 "và tự chuyển Ollama. Muốn nhanh và đều chất lượng hãy nhập Gemini API key.")
    elif ol["san_sang"]:
        chon, ly_do = "ollama", ("Chưa có cookie Gemini hay API key nên dùng Ollama offline. "
                                 "Dán cookie Gemini ở ⚙ Cấu hình để dịch hay hơn, miễn phí.")
    else:
        chon, ly_do = "gemini_api", "Chưa có engine nào sẵn sàng: dán cookie Gemini ở ⚙ Cấu hình (miễn phí) hoặc cài Ollama."
    return {"so_cau": n, "de_xuat": chon, "giai_thich": ly_do, "engines": engines}
