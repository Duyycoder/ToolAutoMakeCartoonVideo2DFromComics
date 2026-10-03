"""Dịch phụ đề theo LÔ JSON qua API kiểu OpenAI (Gemini cookie qua proxy 7860, hoặc Gemini API key).

Mỗi lô gửi {"1": câu, "2": câu, ...} và đòi lại JSON cùng khoá. Số đo thật 02/10/2026
(gemini-3-flash qua cookie): lô 100 câu ≈ 14 s, lô ≥ 150 câu bị từ chối ("Tôi chỉ là mô
hình ngôn ngữ..."); chạy 4–8 luồng thì khoảng nửa số lô bị từ chối, và sau ~30 lô lớn
liên tiếp tài khoản bị Google hạn chế. Nên:
- lô bị từ chối / JSON hỏng thì chia đôi rồi gửi lại (lô nhỏ ít bị từ chối hơn);
- nhiều lô liên tiếp hỏng = tài khoản đang bị hạn chế → DỪNG, trả phần đã dịch để
  dich.py chuyển phần còn lại sang Ollama, thay vì nện tiếp làm tài khoản bị khoá lâu hơn.
"""
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional

import requests

LO_NHO_NHAT = 12          # chia đôi tới mức này mà vẫn hỏng thì bỏ lô cho Ollama
NGUONG_HAN_CHE = 5        # số lô hỏng LIÊN TIẾP coi như tài khoản bị hạn chế
NGHI_SAU_TU_CHOI = 4.0    # giây; lùi lại một chút trước khi gửi lô chia nhỏ


class BiHanChe(Exception):
    """Google từ chối liên tục — dừng phần Gemini."""


def boc_json(txt: str) -> Optional[dict]:
    """Lấy object JSON ĐẦU TIÊN trong câu trả lời (model hay kèm ```json và ghi chú phía sau)."""
    if not txt:
        return None
    txt = txt.replace("\\_", "_").replace("\\[", "[").replace("\\]", "]")
    a = txt.find("{")
    if a < 0:
        return None
    try:
        kq = json.JSONDecoder().raw_decode(txt[a:])[0]
        return kq if isinstance(kq, dict) else None
    except ValueError:
        pass
    b = txt.rfind("}")
    try:
        kq = json.loads(txt[a:b + 1])
        return kq if isinstance(kq, dict) else None
    except ValueError:
        # Cứu từng cặp "khoá": "giá trị" khi chỉ hỏng một chỗ (thường là dấu " lọt trong câu).
        kq = {}
        # Giá trị phải kết thúc ngay trước , hoặc } — cặp có " lọt giữa câu thì bỏ, đừng cắt cụt.
        for k, v in re.findall(r'"(\d+)"\s*:\s*"((?:[^"\\]|\\.)*)"(?=\s*[,}])', txt[a:]):
            try:
                kq[k] = json.loads(f'"{v}"')
            except ValueError:
                kq[k] = v
        return kq or None


def tao_prompt(cau: Dict[str, str], lang_nguon: str, lang_dich: str, thuat_ngu: Dict[str, str]) -> str:
    p = (f"Bạn là dịch giả phụ đề phim. Dịch từng câu phụ đề {lang_nguon} trong JSON dưới đây sang {lang_dich}. "
         "Các câu nối tiếp nhau trong cùng một cảnh: giữ xưng hô nhất quán theo quan hệ nhân vật, câu ngắn gọn tự nhiên "
         "như lời thoại. Tên riêng tiếng Trung phiên âm Hán-Việt.\n")
    if thuat_ngu:
        p += "Bắt buộc dùng đúng các thuật ngữ sau:\n" + "".join(f"- {k} → {v}\n" for k, v in thuat_ngu.items())
    p += ("Trả về DUY NHẤT một JSON object có đúng các khoá như đầu vào, giá trị là bản dịch của câu tương ứng; "
          "không gộp câu, không bỏ câu, không giải thích, không markdown.\n\n")
    return p + json.dumps(cau, ensure_ascii=False)


def goi_chat(prompt: str, base_url: str, api_key: str, model: str, timeout: float = 240) -> str:
    r = requests.post(base_url.rstrip("/") + "/chat/completions",
                      headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                      json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2},
                      timeout=(10, timeout))
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    return (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()


def dich_lo_json(nguon: Dict[int, str], *, lang_nguon: str, lang_dich: str, thuat_ngu: Dict[str, str],
                 base_url: str, api_key: str, model: str, so_moi_lo: int = 100, so_luong: int = 2,
                 kiem_cau: Callable[[str, str], bool] = lambda n, d: bool(d.strip()),
                 huy: Optional[threading.Event] = None,
                 bao: Callable[[int, str], None] = lambda xong, msg: None) -> dict:
    """nguon: {vị trí câu: văn bản}. Trả {"ban_dich": {vị trí: bản dịch đạt}, "so_lo", "so_tu_choi", "bi_han_che", "loi"}.

    Câu không có trong ban_dich (bị từ chối, sót, không qua kiem_cau) để bên gọi dịch cách khác.
    """
    tn_keys = sorted(thuat_ngu, key=len, reverse=True)
    vi_tri = list(nguon)
    ket_qua: Dict[int, str] = {}
    tk = {"so_lo": 0, "so_tu_choi": 0, "lien_tiep": 0, "loi": ""}
    khoa = threading.Lock()
    dung = threading.Event()

    def gui(ds: List[int]) -> None:
        if dung.is_set() or (huy is not None and huy.is_set()):
            return
        cau = {str(k + 1): nguon[i].strip() for k, i in enumerate(ds)}
        tn = {k: thuat_ngu[k] for k in tn_keys if any(k in c for c in cau.values())}
        try:
            d = boc_json(goi_chat(tao_prompt(cau, lang_nguon, lang_dich, tn), base_url, api_key, model))
        except Exception as e:  # mạng/HTTP: coi như một lô hỏng
            d = None
            with khoa:
                tk["loi"] = str(e)[:200]
        dat = {}
        if d:
            for k, i in enumerate(ds):
                v = d.get(str(k + 1))
                if isinstance(v, str) and v.strip() and kiem_cau(nguon[i], v.strip()):
                    dat[i] = v.strip()
        with khoa:
            tk["so_lo"] += 1
            ket_qua.update(dat)
            hong = not d or len(dat) < len(ds) * 0.5
            if hong:
                tk["so_tu_choi"] += 1
                tk["lien_tiep"] += 1
                if tk["lien_tiep"] >= NGUONG_HAN_CHE:
                    dung.set()
            else:
                tk["lien_tiep"] = 0
            xong = len(ket_qua)
        bao(xong, f"Gemini đã dịch {xong}/{len(vi_tri)} câu" + (" — đang chia nhỏ lô bị từ chối" if hong else ""))
        if hong and not dung.is_set() and len(ds) > LO_NHO_NHAT:
            con = [i for i in ds if i not in dat]
            giua = (len(con) + 1) // 2
            time.sleep(NGHI_SAU_TU_CHOI)
            gui(con[:giua])
            gui(con[giua:])

    cac_lo = [vi_tri[j:j + so_moi_lo] for j in range(0, len(vi_tri), so_moi_lo)]
    with ThreadPoolExecutor(max_workers=max(1, so_luong)) as ex:
        list(ex.map(gui, cac_lo))
    return {"ban_dich": ket_qua, "so_lo": tk["so_lo"], "so_tu_choi": tk["so_tu_choi"],
            "bi_han_che": dung.is_set(), "loi": tk["loi"]}
