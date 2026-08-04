"""Hàng rào cho RAG v2: chia nhỏ tri thức, cache câu lặp, lượt suy nghĩ.

Không cần GPU, không gọi Ollama — mọi thứ ở đây là logic thuần.
"""
import os
import time

from orchestrator import kb_index
from orchestrator.chatbot import ChatManager

KB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "kb"))


# ----------------------------------------------------------------- chia nhỏ
def test_moi_manh_deu_mang_duong_dan_ngu_canh():
    """Mảnh tách khỏi tiêu đề là vô nghĩa — phải nhân bản đường dẫn vào đầu.

    Không có ràng buộc này, "- `classic`: 1 ảnh/cảnh" rời khỏi "Chế độ render —
    Bước 3" thì cả người lẫn model đều không biết nó nói về cái gì.
    """
    md = "# Tài liệu\n\n## Chế độ render\n\n- `classic`: 1 ảnh mỗi cảnh\n"
    chunks = kb_index.chunk_markdown(md, "x.md")
    assert chunks
    for ch in chunks:
        assert ch["path"], "Mảnh không có đường dẫn ngữ cảnh"
        assert ch["content"].startswith("["), "Nội dung mảnh thiếu tiền tố ngữ cảnh"
        assert ch["path"] in ch["content"]


def test_doan_dai_bi_cat_theo_tran():
    long_md = "# T\n\n## Mục\n\n" + "\n".join(f"- dòng số {i} với ít nội dung" for i in range(60))
    chunks = kb_index.chunk_markdown(long_md, "y.md")
    assert len(chunks) > 1, "Đoạn dài phải bị cắt thành nhiều mảnh"
    for ch in chunks:
        # +200 cho phần tiền tố đường dẫn ngữ cảnh được nhân bản vào mỗi mảnh.
        assert len(ch["content"]) <= kb_index.MAX_CHUNK_CHARS + 200


def test_chi_muc_that_nap_duoc_va_khong_rong():
    mgr = ChatManager(None, None, None, kb_dir=KB_DIR)
    assert len(mgr.kb_sections) > 50, "Chỉ mục KB rỗng hoặc quá ít mảnh"
    assert all(s.get("content") for s in mgr.kb_sections)


# ------------------------------------------------------------------- cache
def test_cache_tra_lai_dung_cau_da_luu():
    mgr = ChatManager(None, None, None, kb_dir=KB_DIR)
    mgr.cache_put("Bước 2 có mấy engine TTS?", "m1", "Có 5 engine.")
    assert mgr.cache_get("bước 2 có   mấy engine tts?", "m1") == "Có 5 engine."


def test_cache_khong_dung_chung_giua_cac_model():
    """Đổi model mà vẫn nhận câu cũ là lỗi rất khó truy — mọi thứ khác đều đúng."""
    mgr = ChatManager(None, None, None, kb_dir=KB_DIR)
    mgr.cache_put("câu hỏi", "model-a", "trả lời A")
    assert mgr.cache_get("câu hỏi", "model-b") is None


def test_cache_het_han_theo_ttl():
    mgr = ChatManager(None, None, None, kb_dir=KB_DIR)
    mgr.CACHE_TTL_SECONDS = 0
    mgr.cache_put("câu hỏi", "m", "trả lời")
    time.sleep(0.01)
    assert mgr.cache_get("câu hỏi", "m") is None


def test_cache_khong_vuot_qua_gioi_han():
    mgr = ChatManager(None, None, None, kb_dir=KB_DIR)
    mgr.CACHE_MAX = 5
    for i in range(20):
        mgr.cache_put(f"câu {i}", "m", f"đáp {i}")
    assert len(mgr._answer_cache) <= 5


# ------------------------------------------------------- lượt suy nghĩ (R4)
def test_chi_suy_nghi_khi_manh_rai_nhieu_file():
    một_file = [{"file": "a.md"}, {"file": "a.md"}]
    hai_file = [{"file": "a.md"}, {"file": "b.md"}]
    ba_file = [{"file": "a.md"}, {"file": "b.md"}, {"file": "c.md"}]
    assert ChatManager.needs_reasoning(một_file) is False
    assert ChatManager.needs_reasoning(hai_file) is False
    assert ChatManager.needs_reasoning(ba_file) is True


def test_prompt_suy_nghi_chi_chua_tieu_de():
    """Lượt này phải rẻ: chỉ đưa tiêu đề, tuyệt đối không đưa nội dung mảnh."""
    secs = [{"path": "A › B", "header": "B", "content": "NỘI DUNG BÍ MẬT"}]
    msgs = ChatManager.build_reasoning_prompt("hỏi gì đó", secs)
    joined = " ".join(m["content"] for m in msgs)
    assert "A › B" in joined
    assert "NỘI DUNG BÍ MẬT" not in joined


def test_ap_dung_lua_chon_va_fallback_khi_hong():
    secs = [{"file": f"{i}.md", "path": str(i)} for i in range(5)]
    assert ChatManager.apply_reasoning(secs, "1, 3") == [secs[0], secs[2]]
    # Model trả rác hoặc số ngoài phạm vi -> giữ nguyên danh sách truy xuất.
    assert ChatManager.apply_reasoning(secs, "không biết") == secs
    assert ChatManager.apply_reasoning(secs, "99") == secs
    # Không bao giờ nạp quá 3 mảnh.
    assert len(ChatManager.apply_reasoning(secs, "1,2,3,4,5")) == 3
