import string
import difflib
import unicodedata

def chuan_hoa_tu(tu: str) -> str:
    """Chuẩn hóa: NFC, bỏ khoảng trắng, thường hóa, bỏ dấu câu.

    Whisper trả mỗi từ kèm dấu cách ĐẦU (" Anh") — không strip thì không từ nào khớp (chạy thật 25/25 câu "không khớp").
    NFC vì chữ Việt có dấu có thể đến ở dạng tổ hợp (NFD) từ SRT nhập ngoài."""
    t = unicodedata.normalize("NFC", tu).strip().lower()
    return "".join(c for c in t if c not in string.punctuation and not c.isspace())

def can_gio_phu_de(cau_hien_tai: list[dict], words_whisper: list[dict]) -> tuple[list[dict], int]:
    """
    Căn giờ phụ đề dựa trên danh sách từ Whisper.
    Trả về (ket_qua, khong_khop).
    """
    khong_khop = 0
    ket_qua = []
    
    words_chuan = [chuan_hoa_tu(w["w"]) for w in words_whisper]
    
    t_cuoi_cau_truoc = 0.0
    
    for cau in cau_hien_tai:
        t_vao_cu = float(cau.get("t_vao", 0.0))
        t_ra_cu = float(cau.get("t_ra", t_vao_cu + 1.0))
        
        text_goc = cau.get("text_goc", "")
        if not text_goc:
            # Heuristic: khớp theo thời lượng lời gần nhất cho câu không có text_goc
            khop_start = None
            khop_end = None
            for w in words_whisper:
                if w["bd"] >= t_vao_cu - 0.5 and khop_start is None:
                    khop_start = w["bd"]
                if w["kt"] <= t_ra_cu + 0.5:
                    khop_end = w["kt"]
            
            t_vao_moi = t_vao_cu
            t_ra_moi = t_ra_cu
            if khop_start is not None and khop_end is not None and khop_start < khop_end:
                t_vao_moi = khop_start
                t_ra_moi = khop_end
            else:
                khong_khop += 1
                
            t_vao_moi = max(t_cuoi_cau_truoc, t_vao_moi)
            if t_ra_moi <= t_vao_moi:
                t_ra_moi = t_vao_moi + 0.1
                
            ket_qua.append({
                "id": cau["id"],
                "t_vao": t_vao_moi,
                "t_ra": t_ra_moi
            })
            t_cuoi_cau_truoc = t_ra_moi
            continue
            
        tu_cau = [chuan_hoa_tu(w) for w in text_goc.split() if chuan_hoa_tu(w)]
        if not tu_cau:
            khong_khop += 1
            ket_qua.append({"id": cau["id"], "t_vao": max(t_cuoi_cau_truoc, t_vao_cu), "t_ra": max(t_cuoi_cau_truoc, t_vao_cu) + (t_ra_cu - t_vao_cu)})
            t_cuoi_cau_truoc = max(t_cuoi_cau_truoc, t_vao_cu) + (t_ra_cu - t_vao_cu)
            continue
            
        # Cửa sổ trượt quanh giờ cũ ±5 s
        cua_so_tu = []
        cua_so_idx = []
        for i, w in enumerate(words_whisper):
            if t_vao_cu - 5 <= w["kt"] and w["bd"] <= t_ra_cu + 5:
                cua_so_tu.append(words_chuan[i])
                cua_so_idx.append(i)
                
        if not cua_so_tu:
            khong_khop += 1
            t_vao_moi = max(t_cuoi_cau_truoc, t_vao_cu)
            t_ra_moi = max(t_vao_moi + 0.1, t_vao_moi + (t_ra_cu - t_vao_cu))
            ket_qua.append({"id": cau["id"], "t_vao": t_vao_moi, "t_ra": t_ra_moi})
            t_cuoi_cau_truoc = t_ra_moi
            continue
            
        matcher = difflib.SequenceMatcher(None, cua_so_tu, tu_cau)
        blocks = matcher.get_matching_blocks()
        match_size = sum(b.size for b in blocks)
        
        ti_le = match_size / len(tu_cau)
        valid_blocks = [b for b in blocks if b.size > 0]
        
        if ti_le < 0.5 or not valid_blocks:
            khong_khop += 1
            t_vao_moi = max(t_cuoi_cau_truoc, t_vao_cu)
            t_ra_moi = max(t_vao_moi + 0.1, t_vao_moi + (t_ra_cu - t_vao_cu))
            ket_qua.append({"id": cau["id"], "t_vao": t_vao_moi, "t_ra": t_ra_moi})
            t_cuoi_cau_truoc = t_ra_moi
        else:
            first_match_idx = valid_blocks[0].a
            last_match_block = valid_blocks[-1]
            last_match_idx = last_match_block.a + last_match_block.size - 1
            
            idx_start = cua_so_idx[first_match_idx]
            idx_end = cua_so_idx[last_match_idx]
            
            t_vao_moi = words_whisper[idx_start]["bd"]
            t_ra_moi = words_whisper[idx_end]["kt"]
            
            t_vao_moi = max(t_cuoi_cau_truoc, t_vao_moi)
            if t_ra_moi <= t_vao_moi:
                t_ra_moi = t_vao_moi + 0.1
                
            ket_qua.append({"id": cau["id"], "t_vao": t_vao_moi, "t_ra": t_ra_moi})
            t_cuoi_cau_truoc = t_ra_moi
            
    return ket_qua, khong_khop
