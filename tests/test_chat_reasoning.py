"""Hàng rào cho quy trình suy luận nhiều lượt của trợ lý (orchestrator/chat_reasoning.py).

Không gọi Ollama: model được thay bằng hàm giả trả JSON dựng sẵn, để khoá lại
LUẬT ĐIỀU PHỐI — khi nào hiểu lại câu hỏi, khi nào tách ý, xử lý "không đoạn nào".
"""
import asyncio
import json
import os

from orchestrator import chat_reasoning as cr
from orchestrator import kb_index
from orchestrator.chatbot import ChatManager

KB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "kb"))
_MGR = None


def _mgr():
    global _MGR
    if _MGR is None:
        _MGR = ChatManager(None, None, None, kb_dir=KB_DIR)
    return _MGR


def _run_plan(question, replies, cfg=None, history=None, mgr=None):
    """Chạy plan_answer với model giả trả lần lượt các chuỗi trong `replies`."""
    calls = []

    async def fake_llm(messages, **kw):
        calls.append({"messages": messages, **kw})
        return replies.pop(0) if replies else "{}"

    async def go():
        events = []
        async for ev in cr.plan_answer(chat_mgr=mgr or _mgr(), llm=fake_llm, question=question,
                                       history=history or [], active_tab="", cfg=cfg or {}):
            events.append(ev)
        return events

    events = asyncio.run(go())
    return events[-1]["plan"], [e for e in events if "stage" in e], calls


# ------------------------------------------------------------ đọc JSON của model
def test_doc_ket_qua_hieu_cau_hoi_ca_khi_co_loi_dan():
    raw = 'Đây: {"cau_hoi": "LoRA là gì?", "loai": "do_an", "tu_khoa": "LoRA, hạng thấp", "y_nho": []}'
    a = cr.parse_analysis(raw, "lora?")
    assert a["cau_hoi"] == "LoRA là gì?"
    assert a["loai"] == "do_an"
    assert a["tu_khoa"] == ["LoRA", "hạng thấp"]
    assert cr.parse_analysis("không phải json", "q") is None
    # Nhãn lạ bị bỏ, không được lọt vào luật điều phối.
    assert cr.parse_analysis('{"loai": "abc"}', "q")["loai"] == ""


def test_doc_lua_chon_doan():
    assert cr.parse_rerank('{"chon": [2, 1]}', 5) == [1, 0]
    assert cr.parse_rerank('{"chon": [9, 2, 2]}', 5) == [1]          # ngoài phạm vi, trùng
    assert cr.parse_rerank('{"chon": []}', 5) == []
    assert cr.parse_rerank("{}", 5) == []                              # JSON rỗng = không đoạn nào
    assert cr.parse_rerank("chọn đoạn 3", 5) == [2]
    assert cr.parse_rerank("không biết", 5) is None                    # đọc không được
    assert len(cr.parse_rerank('{"chon": [1,2,3,4,5]}', 5)) == 3


# ------------------------------------------------------------------ câu nối tiếp
def test_nhan_ra_cau_noi_tiep():
    hist = [{"role": "user", "content": "LoRA là gì?"}, {"role": "assistant", "content": "..."}]
    assert cr.looks_followup("thế còn IP-Adapter?", hist)
    assert cr.looks_followup("vì sao vậy", hist)
    assert not cr.looks_followup("thế còn IP-Adapter?", [])
    assert not cr.looks_followup(
        "Stable Diffusion sinh ảnh như thế nào trong đồ án của em", hist)


# -------------------------------------------------------------------- tách ý
def test_chi_tach_khi_cau_that_su_nhieu_y():
    assert cr.worth_splitting("LoRA là gì và khác IP-Adapter thế nào?",
                              ["LoRA là gì?", "LoRA khác IP-Adapter thế nào?"])
    # Model 3B đôi khi tách cả câu một ý — mỗi ý thêm tốn ~5 giây, phải chặn.
    assert not cr.worth_splitting("LoRA là gì?", ["LoRA là gì?", "Định nghĩa LoRA?"])
    assert not cr.worth_splitting("SSE và WebSocket?", ["SSE?"])
    assert not cr.worth_splitting("A và B?", ["A?", "A?"])


def test_cau_nhieu_y_moi_y_tra_tai_lieu_rieng():
    analysis = json.dumps({
        "cau_hoi": "LoRA là gì và khác IP-Adapter thế nào?", "loai": "do_an",
        "tu_khoa": ["LoRA", "IP-Adapter"],
        "y_nho": ["LoRA là gì?", "LoRA khác IP-Adapter thế nào?"],
    })
    plan, stages, calls = _run_plan(
        "LoRA là gì và nó khác IP-Adapter thế nào?",
        [analysis, '{"chon": [1]}', '{"chon": [1]}'],
        cfg={"reasoning": "deep"},
    )
    assert [p["question"] for p in plan["parts"]] == ["LoRA là gì?", "LoRA khác IP-Adapter thế nào?"]
    assert all(p["sections"] for p in plan["parts"]), "Ý nào cũng phải có tài liệu riêng"
    # Lượt chọn đoạn của ý 2 phải hỏi bằng câu của ý 2, không phải cả câu gốc.
    rerank_users = [c["messages"][1]["content"] for c in calls if c.get("num_predict") == 40]
    assert any("LoRA khác IP-Adapter" in u for u in rerank_users)
    assert any(s["stage"] == "phan_tich" for s in stages)


# ---------------------------------------------------------- "không đoạn nào"
def test_model_bao_khong_doan_nao_va_cau_ngoai_pham_vi_thi_khong_nap_tai_lieu():
    plan, _stages, _calls = _run_plan(
        "Viết giúp em một bài thơ tình",
        ['{"cau_hoi": "Viết một bài thơ tình", "loai": "ngoai", "tu_khoa": ["thơ"], "y_nho": []}',
         '{"chon": []}'],
        cfg={"reasoning": "deep"},
    )
    assert plan["sections"] == []


def test_che_do_nhanh_khong_goi_model():
    plan, stages, calls = _run_plan("LoRA là gì?", [], cfg={"reasoning": "fast"})
    assert calls == [] and stages == []
    assert plan["sections"], "Chế độ nhanh vẫn phải trả tài liệu từ IDF"


def test_model_hong_thi_van_co_tai_lieu():
    """Lượt phụ trả rác -> rơi về IDF, không bao giờ chặn câu trả lời."""
    plan, _s, _c = _run_plan("Vì sao dùng SSE mà không dùng WebSocket?",
                             ["xin lỗi tôi không hiểu", "???"], cfg={"reasoning": "deep"})
    assert plan["sections"]


# ------------------------------------------------------------- soát chi tiết
def test_soat_so_lieu_va_ten_tep_khong_co_trong_tai_lieu():
    ctx = "VRAM đỉnh ≈ 4,0 GB. Sửa trong `orchestrator/desktop.py`. 173 passed."
    ans = "VRAM đỉnh 4.0 GB, đã có 173 test, sửa ở desktop.py; còn 12,5 GB ở `config_x.py`."
    issues = cr.grounding_issues(ans, ctx)
    assert "12,5 GB" in issues or "12,5" in " ".join(issues)
    assert "config_x.py" in " ".join(issues)
    assert not any("173" in x or "4.0" in x for x in issues)


# ------------------------------------------------------------- prompt trả lời
def test_prompt_on_tap_co_khuon_va_bo_tien_to_duong_dan():
    sec = {"file": "datn/a.md", "path": "Chương 7 › CFG", "content": "[Chương 7 › CFG]\nCFG = 5.0"}
    p = cr.build_study_prompt([sec])
    assert "--- Chương 7 › CFG ---\nCFG = 5.0" in p
    assert "Nguồn:" in p and "<tailieu>" in p


def test_prompt_tong_hop_chi_dung_cau_tra_loi_tung_y():
    parts = [{"question": "LoRA là gì?", "answer": "ΔW = BA.", "sections": [{"file": "x", "path": "LoRA"}]}]
    p = cr.build_synthesis_prompt(parts)
    assert "Ý 1: LoRA là gì?" in p and "ΔW = BA." in p and "KHÔNG thêm chi tiết mới" in p


# ------------------------------------------------------------- chỉ mục nhiều bộ
def test_chia_manh_nhan_tieu_de_cap_4_va_bo_qua_dau_thang_trong_ma():
    md = "# Chương\n\n## Mục\n\n#### Câu 1 LoRA là gì?\n\nTrả lời.\n\n```\n# không phải tiêu đề\n```\n"
    chunks = kb_index.chunk_markdown(md, "datn/x.md", 800)
    assert chunks[0]["path"] == "Chương › Mục › Câu 1 LoRA là gì?"
    assert "# không phải tiêu đề" in chunks[0]["content"]


def test_thu_muc_con_la_bo_tri_thuc_rieng(tmp_path):
    (tmp_path / "a.md").write_text("# A\n\nhướng dẫn bấm nút\n", encoding="utf-8")
    (tmp_path / "datn").mkdir()
    (tmp_path / "datn" / "b.md").write_text("# B\n\nlý thuyết LoRA\n", encoding="utf-8")
    db = str(tmp_path / "idx.db")
    assert kb_index.build_index(str(tmp_path), db) == 2
    cols = {c["file"]: c["collection"] for c in kb_index.load_chunks(db)}
    assert cols == {"a.md": "huong_dan", "datn/b.md": "datn"}


def test_chi_muc_cu_thieu_cot_collection_bi_dung_lai(tmp_path):
    import sqlite3
    db = str(tmp_path / "old.db")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE kb_chunks (id INTEGER PRIMARY KEY, file TEXT, path TEXT,"
                 " header TEXT, content TEXT, mtime REAL)")
    conn.execute("INSERT INTO kb_chunks VALUES (1,'a.md','p','h','c', 9e12)")
    conn.commit()
    conn.close()
    assert kb_index.index_is_stale(str(tmp_path), db)


def test_idf_bo_huong_dan_khong_bi_bo_do_an_lam_lech():
    """Thêm tài liệu đồ án không được đổi điểm của bộ hướng dẫn (ngưỡng đã chỉnh)."""
    mgr = _mgr()
    only_guide = ChatManager.__new__(ChatManager)
    only_guide.kb_sections = [s for s in mgr.kb_sections if s["collection"] == "huong_dan"]
    only_guide._build_idf()
    q = "Bước 2 có mấy engine TTS?"
    assert mgr.score_sections(q)[1] == only_guide.score_sections(q)[1]


# ------------------------------------------------------------------- router
def test_cau_hoi_ly_thuyet_khong_bi_hieu_thanh_lenh():
    mgr = _mgr()
    assert mgr.route_intent("Stable Diffusion sinh ảnh như thế nào?")[0] == "chat"
    assert mgr.route_intent("Hệ thống chạy trên phần cứng nào?")[0] == "chat"
    assert mgr.route_intent("Cấu hình SD mặc định là gì?")[0] == "chat"
    # Mệnh lệnh thật vẫn giữ nguyên.
    assert mgr.route_intent("Gen hình ảnh cho truyện")[0] == "run_step"
    assert mgr.route_intent("Xem trạng thái hệ thống GPU")[0] == "system_status"
