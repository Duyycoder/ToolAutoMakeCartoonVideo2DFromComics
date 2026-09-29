import json
import os
import re
import time
import requests
import unicodedata
from typing import Dict, Any, List

from orchestrator.editor import hang_doi, srt, luu_tru
from orchestrator.config import load_global_config

VIETNAMESE_SYLLABLE_RE = re.compile(
    r"^(b|c|ch|d|đ|g|gh|gi|h|k|kh|l|m|n|ng|ngh|nh|p|ph|q|qu|r|s|t|th|tr|v|x)?"
    r"[aàáảãạăằắẳẵặâầấẩẫậeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵ]+"
    r"(c|ch|m|n|ng|nh|p|t)?$", re.IGNORECASE
)

def is_cjk(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7a3\u0e00-\u0e7f\u0400-\u04ff]', text))

def chu_la_trong_dich(ban_dich: str, lang_dich: str) -> list:
    """Các cụm chữ khác hệ lẫn trong bản dịch khi ngôn ngữ ĐÍCH dùng chữ Latinh (Việt/Anh/Indonesia/Tây Ban Nha…)."""
    if not is_latin_lang(lang_dich):
        return []
    return re.findall(r'[一-鿿぀-ヿ가-힣฀-๿Ѐ-ӿ]+', ban_dich or '')


def is_latin_lang(lang: str) -> bool:
    return lang.lower() in ("vietnamese", "english", "tiếng việt", "tiếng anh", "indonesian")

def is_valid_vietnamese(token: str) -> bool:
    return bool(VIETNAMESE_SYLLABLE_RE.match(token))

def is_valid_english(token: str) -> bool:
    return not bool(re.search(r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]', token, re.IGNORECASE))

def bo_dau(text: str) -> str:
    text = re.sub(r'[đĐ]', lambda m: 'd' if m.group() == 'đ' else 'D', text)
    text = unicodedata.normalize('NFD', text)
    text = re.sub(r'[\u0300-\u036f]', '', text)
    return text

def kiem_do_dai(nguon: str, ban_dich: str, lang_nguon: str, lang_dich: str) -> bool:
    def is_cjk_text_or_lang(text, lang):
        return is_cjk(text) or lang.lower() in ("chinese", "tiếng trung", "中文", "japanese", "tiếng nhật", "korean", "tiếng hàn")
        
    def count_len(text, is_cjk_flag):
        if is_cjk_flag:
            return len(re.sub(r'\s+', '', text)) * 1.6
        return len(re.findall(r'[a-zA-Zà-ỹÀ-ỸđĐ]+', text))
        
    len_nguon = count_len(nguon, is_cjk_text_or_lang(nguon, lang_nguon))
    len_dich = count_len(ban_dich, is_cjk_text_or_lang(ban_dich, lang_dich))
    
    if len_nguon == 0:
        return False
        
    return (len_dich / len_nguon) > 2.2 and (len_dich - len_nguon) >= 6

def do_lot_tu(nguon: str, ban_dich: str, lang_nguon: str, lang_dich: str, thuat_ngu: dict, tap_tu_nguon: set = None) -> dict:
    nguon_strip = nguon.strip()
    ban_dich_strip = ban_dich.strip()
    if not ban_dich_strip or (ban_dich_strip.lower() == nguon_strip.lower() and re.search(r'[a-zA-Zà-ỹÀ-ỸđĐ\u4e00-\u9fff]', nguon_strip)):
        return {"lot": ["TOÀN_BỘ"], "ti_le": 1.0}

    lot = []
    
    if is_cjk(nguon_strip) and is_latin_lang(lang_dich):
        lot = re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7a3\u0e00-\u0e7f\u0400-\u04ff]', ban_dich_strip)
        tokens_dich = list(ban_dich_strip)
        return {"lot": lot, "ti_le": len(lot)/max(1, len(tokens_dich))}
        
    matches_dich = list(re.finditer(r'[a-zA-Zà-ỹÀ-ỸđĐ]+', ban_dich_strip))
    tokens_dich = [m.group(0) for m in matches_dich]
    tokens_nguon_full = re.findall(r'[a-zA-Zà-ỹÀ-ỸđĐ]+', nguon_strip)
    tokens_nguon = [x.lower() for x in tokens_nguon_full]
    
    if tap_tu_nguon is None:
        tap_tu_nguon = set(tokens_nguon)
    
    proper_nouns = set()
    words_in_source = nguon_strip.split()
    for i, w in enumerate(words_in_source):
        clean_w = re.sub(r'^[^\w]+|[^\w]+$', '', w)
        if clean_w and clean_w[0].isupper() and i > 0:
            proper_nouns.add(clean_w.lower())
            
    keep_list = {"tiktok", "ok", "youtube", "facebook"}
    thuat_ngu_vals = [str(v).lower() for v in thuat_ngu.values()]
    
    COMMON_ENGLISH_WORDS = set()
    try:
        with open(os.path.join(os.path.dirname(__file__), "tu_tieng_anh.txt"), "r", encoding="utf-8") as f:
            COMMON_ENGLISH_WORDS = set(f.read().split())
    except:
        pass
        
    OVERLAPPING_VN_SYLLABLES = {"an", "me", "to", "ban", "hat", "he", "do", "am", "in", "on", "no", "so", "be", "we"}
    
    is_eng_target = lang_dich.lower() in ("english", "tiếng anh")
    is_vie_target = lang_dich.lower() in ("vietnamese", "tiếng việt")
    is_eng_source = lang_nguon.lower() in ("english", "tiếng anh")
    is_vie_source = lang_nguon.lower() in ("vietnamese", "tiếng việt")
    
    lot_indices = set()
    nguon_vn_bo_dau = {}
    for tk_ng in tap_tu_nguon:
        if is_valid_vietnamese(tk_ng):
            nguon_vn_bo_dau[tk_ng] = bo_dau(tk_ng)
            
    def is_in_quotes(idx):
        if idx >= len(matches_dich): return False
        m = matches_dich[idx]
        start_pos = m.start()
        end_pos = m.end()
        left_quote = False
        right_quote = False
        for i in range(start_pos - 1, -1, -1):
            c = ban_dich_strip[i]
            if c in ['"', "'", '“', '”', '‘', '’']: left_quote = True; break
            if c.isalnum(): break
        for i in range(end_pos, len(ban_dich_strip)):
            c = ban_dich_strip[i]
            if c in ['"', "'", '“', '”', '‘', '’']: right_quote = True; break
            if c.isalnum(): break
        return left_quote or right_quote

    for idx, t in enumerate(tokens_dich):
        t_lower = t.lower()
        if t_lower in keep_list or t_lower in proper_nouns:
            continue
        if t_lower in thuat_ngu_vals:
            continue
            
        if is_eng_target:
            if re.search(r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]', t_lower, re.IGNORECASE):
                lot.append(t)
                lot_indices.add(idx)
                continue
            if t_lower in tap_tu_nguon and is_valid_vietnamese(t_lower) and t_lower not in COMMON_ENGLISH_WORDS:
                lot.append(t)
                lot_indices.add(idx)
                continue
                
        elif is_vie_target:
            if t_lower in tokens_nguon:
                if is_valid_vietnamese(t_lower):
                    if is_eng_source and t_lower in COMMON_ENGLISH_WORDS and t_lower not in OVERLAPPING_VN_SYLLABLES:
                        lot.append(t)
                        lot_indices.add(idx)
                else:
                    lot.append(t)
                    lot_indices.add(idx)
        else:
            if t_lower in tokens_nguon:
                if not (is_valid_vietnamese(t_lower) or is_valid_english(t_lower)):
                    lot.append(t)
                    lot_indices.add(idx)
                    
    if not is_vie_target:
        changed = True
        while changed:
            changed = False
            for idx, t in enumerate(tokens_dich):
                if idx in lot_indices: continue
                t_lower = t.lower()
                if t_lower in keep_list or t_lower in proper_nouns: continue
                if t_lower in thuat_ngu_vals: continue
                
                in_quote = is_in_quotes(idx)
                adjacent = (idx - 1 in lot_indices) or (idx + 1 in lot_indices)
                
                is_lot_bo_dau = False
                for tk_ng, tk_ng_bo_dau in nguon_vn_bo_dau.items():
                    if tk_ng == tk_ng_bo_dau: continue # Khong co dau tieng Viet
                    
                    if t_lower == tk_ng_bo_dau:
                        if (t_lower not in COMMON_ENGLISH_WORDS) or in_quote or adjacent:
                            is_lot_bo_dau = True
                            break
                    elif len(t_lower) >= 2 and tk_ng_bo_dau.startswith(t_lower):
                        if in_quote or adjacent:
                            is_lot_bo_dau = True
                            break
                if is_lot_bo_dau:
                    lot.append(t)
                    lot_indices.add(idx)
                    changed = True

    return {"lot": lot, "ti_le": len(lot)/max(1, len(tokens_dich))}

def lam_sach_ban_dich(text: str, num_newlines: int) -> str:
    text = text.strip()
    text = re.sub(r'^(Bản dịch|Translation|Dịch):\s*', '', text, flags=re.IGNORECASE).strip()
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1].strip()
    # Giữ nguyên số dòng \n nếu có
    if num_newlines > 0:
        lines = text.split('\n')
        lines = [l.strip() for l in lines if l.strip()]
        if len(lines) > 1:
            return '\n'.join(lines)
    return text.replace('\n', ' ')

def doc_thuat_ngu(folder: str) -> dict:
    g_config = load_global_config()
    ws = g_config.get("editor", {}).get("workspace", "")
    tn = {}
    
    if ws:
        chung_path = os.path.join(ws, "_dung_chung", "thuat_ngu.json")
        if os.path.exists(chung_path):
            try:
                tn.update(json.load(open(chung_path, "r", encoding="utf-8")))
            except: pass
        
    rieng_path = os.path.join(folder, ".duan", "thuat_ngu.json")
    if os.path.exists(rieng_path):
        try:
            tn.update(json.load(open(rieng_path, "r", encoding="utf-8")))
        except: pass
        
    return tn

def ghi_thuat_ngu(folder: str, tn: dict):
    os.makedirs(os.path.join(folder, ".duan"), exist_ok=True)
    with open(os.path.join(folder, ".duan", "thuat_ngu.json"), "w", encoding="utf-8") as f:
        json.dump(tn, f, ensure_ascii=False, indent=2)

def goi_ollama(prompt: str, url: str, model: str, system: str = "", temperature: float = 0.1) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "5m",
        "options": {
            "temperature": temperature,
            "top_p": 0.6,
            "repeat_penalty": 1.05
        }
    }
    if system:
        payload["system"] = system
    try:
        resp = requests.post(url, json=payload, timeout=(10, 180))
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.exceptions.Timeout:
        raise RuntimeError("Ollama chạy quá lâu (hết thời gian chờ).")

def dich(ctx: hang_doi.NguCanh, folder: str, loai: str, m: Dict[str, Any], tham_so: Dict[str, Any]) -> Dict[str, Any]:
    g_config = load_global_config()
    tr = g_config.get("translate", {})
    ollama_base_url = tr.get("ollama_base_url", "http://localhost:11434").replace("/v1", "") + "/api/generate"
    model = tham_so.get("mt_model") or tr.get("mt_model") or "hy-mt2:1.8b"
    model_du_phong = tr.get("mt_model_du_phong") or "qwen2.5:7b-instruct"
    
    lang_nguon = tham_so.get("source_lang", "Chinese")
    lang_dich = tham_so.get("target_lang", "Vietnamese")
    
    tn_dict = doc_thuat_ngu(folder)
    if "thuat_ngu" in tham_so:
        tn_dict.update(tham_so["thuat_ngu"])
    
    cau_list = tham_so.get("cau", [])
    ids = tham_so.get("ids", [])
    if not cau_list:
        raise ValueError("Chưa có câu để dịch.")
        
    tn_keys = sorted(tn_dict.keys(), key=len, reverse=True)
    
    kq_cau = []
    tong_cau = 0
    so_cau_sua = 0
    so_lan_goi = 0
    co_dung_du_phong = False
    bao_cao_loi = []
    dung_ngu_canh = tham_so.get("ngu_canh", False)
    
    tap_tu_nguon_toan_bo = set()
    for c in cau_list:
        txt = c.get("text_goc") or c.get("text", "")
        if txt.strip():
            tap_tu_nguon_toan_bo.update([x.lower() for x in re.findall(r'[a-zA-Zà-ỹÀ-ỸđĐ]+', txt.strip())])
    
    # Dịch SONG SONG theo câu: model 1,8B chỉ dùng ~10% GPU khi gửi tuần tự (1925 câu ≈ hơn 1 giờ). Mỗi câu vẫn là MỘT yêu cầu
    # độc lập (không lọt ngữ cảnh). Bật ngữ cảnh thì câu sau cần bản dịch câu trước → chạy tuần tự.
    # Model dự phòng (7B) để lượt RIÊNG ở cuối: GPU 6 GB không giữ được cả hai model — gọi xen kẽ từng câu làm Ollama gỡ/nạp model liên tục.
    import threading
    from concurrent.futures import ThreadPoolExecutor
    khoa = threading.Lock()
    dem = {"goi": 0, "xong": 0}
    ket_qua = [None] * len(cau_list)          # bản dịch theo vị trí câu (None = giữ nguyên câu gốc)
    trang_thai = [None] * len(cau_list)       # (ban_dich, lot, ly_do, is_clean, can_sua, dung_du_phong, nguon)
    so_luong = 1 if dung_ngu_canh else max(1, int(tr.get("so_cau_song_song") or 4))

    def dich_mot_cau(i, c, cac_lan):
        text_goc = c.get("text_goc", "")
        text_hien_tai = c.get("text", "")
        
        if text_hien_tai.strip() and text_goc and text_hien_tai != text_goc and not tham_so.get("dich_lai_tat_ca"):
            return None
            
        nguon = text_hien_tai if not text_goc else text_goc
        if not nguon.strip():
            return None
            
        num_newlines = nguon.count("\n")
        
        tn_cau = {}
        for k in tn_keys:
            if k in nguon:
                tn_cau[k] = tn_dict[k]
                
        ngu_canh_text = ""
        if dung_ngu_canh and i > 0:
            truoc = []
            for j in range(max(0, i-2), i):
                truoc.append(cau_list[j].get("text_goc") or cau_list[j].get("text", ""))
            if any(truoc):
                ngu_canh_text = " ".join(truoc)
                
        lang_map = {
            "english": "英语", "japanese": "日语", "korean": "韩语", 
            "thai": "泰语", "indonesian": "印尼语", "spanish": "西班牙语", 
            "chinese": "中文", "vietnamese": "越南语"
        }
        lang_dich_zh = lang_map.get(lang_dich.lower(), lang_dich)
        
        def tao_prompt(thuat_ngu_dict):
            is_zh = lang_nguon.lower() in ("chinese", "tiếng trung", "中文") or lang_dich.lower() in ("chinese", "tiếng trung", "中文")
            p = ""
            if is_zh:
                if thuat_ngu_dict:
                    p += "参考下面的翻译：\n"
                    for k, v in thuat_ngu_dict.items():
                        p += f"{k} 翻译成 {v}\n"
                    p += "\n"
                if ngu_canh_text:
                    p += f"{ngu_canh_text}\n参考上面的信息，把下面的文本翻译成{lang_dich_zh}，不要额外解释：\n{nguon}"
                else:
                    p += f"把下面的文本翻译成{lang_dich_zh}，不要额外解释。\n\n{nguon}"
            else:
                if thuat_ngu_dict:
                    p += "Use the following terminology:\n"
                    for k, v in thuat_ngu_dict.items():
                        p += f"{k} -> {v}\n"
                    p += "\n"
                p += f"Translate the following segment into {lang_dich}, without additional explanation.\n\n{nguon}"
            return p

        ngu_canh_dich = []
        if dung_ngu_canh and i > 0:
            for j in range(max(0, i-2), i):
                ngu_canh_dich.append((ket_qua[j] or cau_list[j]).get("text", ""))

        ban_dich = ""
        lot = []
        is_clean = False
        can_sua = False
        dung_du_phong = False
        ly_do = None
        
        for lan in cac_lan:
            if ctx.viec.huy_event.is_set(): raise hang_doi.DaHuy()
            if lan > 0: can_sua = True
            if lan == 2: dung_du_phong = True
            
            cur_model = model
            temp = 0.1
            system = ""
            
            if lan == 1 and lot and is_cjk(nguon):
                for lt in lot:
                    if lt in ("DỊCH_THỪA",): continue
                    p_rieng = f"把下面的文本翻译成{lang_dich_zh}，不要额外解释。\n\n{lt}"
                    raw_lt = goi_ollama(p_rieng, ollama_base_url, cur_model, system, 0.3)
                    lt_dich = lam_sach_ban_dich(raw_lt, 0)
                    if lt_dich:
                        tn_cau[lt] = lt_dich
                        
            if lan == 0:
                prompt = tao_prompt(tn_cau)
            elif lan == 1:
                temp = 0.3
                prompt = tao_prompt(tn_cau)
            else:
                cur_model = model_du_phong
                system = "Chỉ trả về bản dịch, dịch toàn bộ văn bản. Nếu có tên riêng tiếng Trung, hãy phiên âm sang Hán-Việt."
                prompt = f"Dịch câu sau sang {lang_dich}, tuyệt đối không giữ lại từ ngôn ngữ gốc:\n{nguon}"
                if tn_cau:
                    prompt = "Dùng các thuật ngữ sau:\n" + "\n".join(f"{k} -> {v}" for k,v in tn_cau.items()) + "\n\n" + prompt

            ctx.bao(tien_do=dem["xong"] / len(cau_list) * 100,
                    thong_diep=f"Đã dịch {dem['xong']}/{len(cau_list)} câu" + (" — lượt sửa bằng model dự phòng" if lan == 2 else ""))
            with khoa:
                dem['goi'] += 1
            raw_dich = goi_ollama(prompt, ollama_base_url, cur_model, system, temp)
            ban_dich = lam_sach_ban_dich(raw_dich, num_newlines)
            
            kq_lot = do_lot_tu(nguon, ban_dich, lang_nguon, lang_dich, tn_dict, tap_tu_nguon_toan_bo)
            lot = kq_lot["lot"]
            # Chữ khác hệ (Hán/Kana/Hangul/Thái/Kirin) trong bản dịch sang ngôn ngữ chữ Latinh = model chèn chữ lạ
            # (chạy thật vi→en ra "the term \"解\""). do_lot_tu chỉ tìm từ NGUỒN nên không bắt được.
            if not lot and chu_la_trong_dich(ban_dich, lang_dich):
                lot = chu_la_trong_dich(ban_dich, lang_dich)
            
            ly_do = None
            if lot:
                ly_do = "lot_tu"
            elif kiem_do_dai(nguon, ban_dich, lang_nguon, lang_dich):
                ly_do = "dich_thua"
                lot = ["DỊCH_THỪA"]
            else:
                thieu_tn = False
                for v in tn_cau.values():
                    if v.lower() not in ban_dich.lower():
                        thieu_tn = True
                        ly_do = "thieu_thuat_ngu"
                        break
                        
                if not ly_do and dung_ngu_canh and ngu_canh_dich:
                    for ncd in ngu_canh_dich:
                        ncd_strip = ncd.strip()
                        if len(ncd_strip) >= 8 and ncd_strip in ban_dich:
                            ly_do = "lot_ngu_canh"
                            break

            if not ly_do:
                is_clean = True
                break
                
        return (ban_dich, lot, ly_do, is_clean, can_sua, dung_du_phong, nguon)

    def chay(i, cac_lan):
        if ctx.viec.huy_event.is_set():
            raise hang_doi.DaHuy()
        kq = dich_mot_cau(i, cau_list[i], cac_lan)
        with khoa:
            dem["xong"] += 1
        if kq is not None:
            trang_thai[i] = kq
            c_moi = dict(cau_list[i])
            c_moi["text"] = kq[0]
            c_moi["text_goc"] = kq[6]
            ket_qua[i] = c_moi

    # Lượt 1: model chuyên dụng, lần 1–2.
    with ThreadPoolExecutor(max_workers=so_luong) as ex:
        list(ex.map(lambda i: chay(i, (0, 1)), range(len(cau_list))))
    # Lượt 2: câu còn lỗi → model dự phòng, gom lại một lượt (một lần đổi model).
    con_loi = [i for i, t in enumerate(trang_thai) if t is not None and not t[3]]
    dem["xong"] = len(cau_list) - len(con_loi)
    with ThreadPoolExecutor(max_workers=so_luong) as ex:
        list(ex.map(lambda i: chay(i, (2,)), con_loi))
    for i in con_loi:
        t = trang_thai[i]
        trang_thai[i] = t[:4] + (True, True, t[6])        # đã sửa + đã dùng dự phòng

    kq_cau = []
    for i, c in enumerate(cau_list):
        kq_cau.append(ket_qua[i] if ket_qua[i] is not None else c)
        t = trang_thai[i]
        if t is None:
            continue
        ban_dich, lot, ly_do, is_clean, can_sua, dung_du_phong, nguon = t
        tong_cau += 1
        if can_sua: so_cau_sua += 1
        if dung_du_phong: co_dung_du_phong = True
        if not is_clean:
            bao_cao_loi.append({"id": c.get("id", str(i)), "nguon": nguon, "ban_dich": ban_dich, "lot": lot, "ly_do": ly_do})
    so_lan_goi = dem["goi"]

    bao_cao = {
        "tong_cau": tong_cau,
        "so_cau_sua": so_cau_sua,
        "so_lan_goi_model": so_lan_goi,
        "ti_le_lot_cuoi": 0.0 if not bao_cao_loi else len(bao_cao_loi)/max(1, tong_cau),
        "model": model,
        "model_du_phong_da_dung": co_dung_du_phong,
        "loi_lot": bao_cao_loi
    }
    
    ctx.viec.ket_qua = {
        "loai": loai,
        "media": m["id"],
        "cau": kq_cau,
        "ids": ids,
        "bao_cao": bao_cao
    }
    
    if len(ids) > 0 and len(kq_cau) != len(ids):
        ctx.viec.ket_qua["lech_so_cau"] = True
    
    # Dự án 1925 câu gần như chắc còn vài câu lọt — đánh LỖI cả việc (hơn nửa giờ) là bỏ phí hết bản dịch tốt.
    # Ít câu lọt → XONG + cảnh báo + danh sách câu (bảng AI bấm nhảy tới); chỉ lỗi khi lọt quá nhiều (thường sai ngôn ngữ/model).
    if bao_cao_loi:
        if bao_cao["ti_le_lot_cuoi"] > 0.2:
            raise RuntimeError(f"Còn {len(bao_cao_loi)}/{tong_cau} câu bị lọt từ hoặc thiếu thuật ngữ — kiểm tra ngôn ngữ nguồn/đích và model dịch.")
        ctx.viec.ket_qua["canh_bao"] = [f"Còn {len(bao_cao_loi)}/{tong_cau} câu bị lọt từ hoặc thiếu thuật ngữ — xem danh sách trong bảng AI để sửa tay."]
        
    return ctx.viec.ket_qua
