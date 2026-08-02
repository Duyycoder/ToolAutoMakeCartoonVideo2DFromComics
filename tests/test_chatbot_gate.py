"""Hàng rào cho cổng ngưỡng chống bịa đặt (kb_min_score) trong select_kb.

Các test ở đây khoá lại ba khiếm khuyết đã từng xảy ra:
  1. Cờ header_matched vô hiệu hoá guard tỷ lệ khớp -> câu ngoài phạm vi lọt cổng.
  2. Một từ trùng ngẫu nhiên đủ để nhận cả đoạn KB.
  3. Danh sách stopword bị nhồi từ nội dung của chính bộ eval (overfit phép đo).
"""
import os

from orchestrator.chatbot import ChatManager, VIETNAMESE_STOPWORDS

KB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "kb"))
MIN_SCORE = 0.65


def _mgr():
    return ChatManager(None, None, None, kb_dir=KB_DIR)


def test_cau_hoi_ngoai_pham_vi_bi_chan():
    """Câu hoàn toàn ngoài phạm vi phải bị cổng ngưỡng chặn, không gọi tới LLM."""
    mgr = _mgr()
    for q in [
        "Giá vàng hôm nay bao nhiêu?",
        "Công thức nấu phở bò gia truyền?",
        "Làm sao để sửa xe máy bị đứt xích?",
        "Dự báo thời tiết hôm nay thế nào?",
    ]:
        sections, score = mgr.select_kb(q, min_score=MIN_SCORE)
        assert sections == [], f"Không được nhận tài liệu cho: {q}"
        assert score < MIN_SCORE, f"score={score:.3f} vượt ngưỡng cho: {q}"


def test_cau_hoi_hop_le_van_qua_cong():
    """Siết cổng không được chặn nhầm câu hỏi vận hành thông thường."""
    mgr = _mgr()
    for q in [
        "Bước 2 có mấy engine TTS?",
        "GPU 6GB nên chọn model Ollama nào cho Bước 3?",
        "Cổng mặc định của Ollama là bao nhiêu?",
    ]:
        sections, score = mgr.select_kb(q, min_score=MIN_SCORE)
        assert sections, f"Bị chặn oan: {q}"
        assert score >= MIN_SCORE


def test_khop_header_khong_duoc_bo_qua_guard_ty_le():
    """Trùng một từ ở tiêu đề KHÔNG còn là đường thoát khỏi guard match_ratio.

    Câu dưới đây có đúng một từ ('video') trùng tiêu đề đoạn KB, phần còn lại
    không liên quan. Trước khi sửa, cờ header_matched cho nó đi thẳng qua cổng.
    """
    mgr = _mgr()
    sections, score = mgr.select_kb(
        "video cua toi bi mat trom ngoai duong hom qua", min_score=MIN_SCORE
    )
    assert sections == []
    assert score < MIN_SCORE


def test_stopwords_khong_chua_tu_noi_dung_cua_bo_eval():
    """Chốt chặn overfit: stopword chỉ được chứa hư từ, không phải từ khoá bộ đo."""
    cam = {
        "thoi", "tiet", "pho", "bo", "nau", "nop", "tien", "dien", "thoai",
        "sua", "xe", "cach", "viet", "cong", "thuc", "du",
    }
    trung = cam & VIETNAMESE_STOPWORDS
    assert not trung, (
        f"Stopword chứa từ nội dung của bộ eval: {sorted(trung)}. "
        "Thêm từ khoá câu hỏi vào stopword là overfit phép đo, không phải cải thiện thật."
    )


def test_health_khong_duoc_hardcode_model_installed():
    """model_installed phải hỏi thật /api/tags, không được trả True vô điều kiện.

    Bản trước hardcode True: model chưa pull mà badge vẫn xanh, người dùng chỉ
    biết khi câu hỏi đầu tiên trả về 404.
    """
    import inspect

    from orchestrator import main as main_mod

    src = inspect.getsource(main_mod.get_chat_health)
    assert '"model_installed": True' not in src
    assert "/api/tags" in src, "Phải truy vấn /api/tags để biết model đã pull chưa"


def test_cong_nguong_dung_chung_nguong_voi_cau_hinh():
    """Mặc định trong code phải khớp giá trị đã hiệu chỉnh bằng bộ eval."""
    import inspect

    sig = inspect.signature(ChatManager.select_kb)
    assert sig.parameters["min_score"].default == MIN_SCORE
