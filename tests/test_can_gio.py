import pytest
from orchestrator.editor.can_gio import can_gio_phu_de

def test_can_gio_phu_de():
    # 1. Câu lệch 1.5s về đúng giờ, tiếng Việt có dấu
    cau_hien_tai = [
        {"id": "c1", "t_vao": 0.0, "t_ra": 2.0, "text_goc": "Xin chào thế giới"}
    ]
    # words_whisper lệch 1.5s
    words_whisper = [
        {"w": "Xin", "bd": 1.5, "kt": 1.8},
        {"w": "chào", "bd": 1.9, "kt": 2.2},
        {"w": "thế", "bd": 2.3, "kt": 2.7},
        {"w": "giới", "bd": 2.8, "kt": 3.5}
    ]
    ket_qua, khong_khop = can_gio_phu_de(cau_hien_tai, words_whisper)
    assert khong_khop == 0
    assert ket_qua[0]["id"] == "c1"
    assert ket_qua[0]["t_vao"] == 1.5
    assert ket_qua[0]["t_ra"] == 3.5

    # 2. Câu không khớp giữ nguyên
    cau_hien_tai_2 = [
        {"id": "c2", "t_vao": 1.0, "t_ra": 3.0, "text_goc": "Không có trong audio"}
    ]
    ket_qua_2, khong_khop_2 = can_gio_phu_de(cau_hien_tai_2, words_whisper)
    assert khong_khop_2 == 1
    assert ket_qua_2[0]["t_vao"] == 1.0
    assert ket_qua_2[0]["t_ra"] == 3.0

    # 3. Không chồng câu
    cau_hien_tai_3 = [
        {"id": "c1", "t_vao": 0.0, "t_ra": 1.0, "text_goc": "Một hai"},
        {"id": "c2", "t_vao": 1.0, "t_ra": 2.0, "text_goc": "Ba bốn"}
    ]
    words_whisper_3 = [
        {"w": "một", "bd": 0.5, "kt": 1.5},
        {"w": "hai", "bd": 1.6, "kt": 2.5},
        {"w": "ba", "bd": 2.0, "kt": 2.8}, # Note: overlapping in whisper
        {"w": "bốn", "bd": 2.9, "kt": 3.5}
    ]
    ket_qua_3, khong_khop_3 = can_gio_phu_de(cau_hien_tai_3, words_whisper_3)
    assert ket_qua_3[0]["t_ra"] == 2.5
    assert ket_qua_3[1]["t_vao"] >= 2.5 # Must not overlap with c1's t_ra



def test_tu_whisper_co_dau_cach_dau_van_khop():
    """Whisper thật trả " Anh", " đã"… (dấu cách đầu) — câu lệch +1.5 s phải được kéo về đúng giờ lời nói."""
    from orchestrator.editor.can_gio import can_gio_phu_de
    words = [{"w": " Anh", "bd": 0.0, "kt": 0.38}, {"w": " đã", "bd": 0.38, "kt": 0.46}, {"w": " xin", "bd": 0.46, "kt": 0.56},
             {"w": " nói", "bd": 0.56, "kt": 0.7}, {"w": " Cô", "bd": 2.74, "kt": 2.9}, {"w": " gái.", "bd": 2.9, "kt": 3.3}]
    cau = [{"id": "a", "t_vao": 1.5, "t_ra": 2.2, "text": "Anh đã xin nói", "text_goc": "Anh đã xin nói"},
           {"id": "b", "t_vao": 4.24, "t_ra": 4.8, "text": "Cô gái", "text_goc": "Cô gái"}]
    kq, khong_khop = can_gio_phu_de(cau, words)
    theo_id = {c["id"]: c for c in kq}
    assert khong_khop == 0
    assert abs(theo_id["a"]["t_vao"] - 0.0) < 0.01 and abs(theo_id["a"]["t_ra"] - 0.7) < 0.01
    assert abs(theo_id["b"]["t_vao"] - 2.74) < 0.01 and abs(theo_id["b"]["t_ra"] - 3.3) < 0.01
