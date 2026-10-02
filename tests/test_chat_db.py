"""Hàng rào cho trợ lý hỏi dữ liệu CSDL (orchestrator/chat_db.py).

Code phân loại câu hỏi và tự lấy/tính số liệu; model chỉ đọc. Các test này khoá
phần CODE: nhận câu hỏi dữ liệu, nhận tên truyện, bộ lọc, khối dữ liệu, và chốt
bổ sung mục bị model bỏ sót. Không gọi Ollama.
"""
import json
import sqlite3
from unittest.mock import patch

import pytest

from orchestrator import chat_db, db


def _story(slug, name, status, step, created, chapters):
    return slug, name, status, step, created, chapters


STORIES = [
    _story("hog", "Bảng học tập Hogwarts", "VIDEO_FAILED", 3, "2026-07-07T10:00:00",
           [("wav", None)] * 3),
    _story("inf", "Infinity: Chiến đấu trong thế giới điện ảnh", "VIDEO_FAILED", 1, "2026-07-12T10:00:00", []),
    _story("ntvn", "Người Trên Vạn Người", "VIDEO_FAILED", 3, "2026-07-18T10:00:00", []),
    _story("tu", "10 năm tu luyện ẩn dật", "VIDEO_GENERATED", 3, "2026-09-30T10:00:00",
           [("wav", "mp4"), (None, None), ("wav", "mp4")]),
    _story("hao", "Tiểu Thư Hào Môn Trở Về", "TRANSLATED", 2, "2026-08-07T10:00:00", [(None, None)] * 2),
    _story("chua", "Người bắt chước chúa", "TRANSLATING", 1, "2026-09-01T10:00:00", [(None, None)]),
    _story("quy", "Nếu ngươi chỉ đơn thuần có tài năng trong Đệ Nhất Thánh Quỷ Phái", "CANCELLED", 3,
           "2026-07-18T10:00:00", [("wav", None)]),
]


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "app.db")
    db.init_db(path)
    for slug, name, status, step, created, chs in STORIES:
        db.upsert_story(path, {"story_slug": slug, "story_name": name, "status": status,
                               "pipeline_step": step, "created_at": created, "updated_at": created})
        db.replace_chapters(path, slug, [
            {"idx": i + 1, "title": f"Chương {i + 1}", "wav_path": w, "mp4_path": m,
             "status": "video" if m else ("tts" if w else "text")}
            for i, (w, m) in enumerate(chs)
        ])
    return path


# ---------------------------------------------------------------- phân loại

@pytest.mark.parametrize("q", [
    "Có bao nhiêu truyện?",
    "Những truyện nào bị lỗi video?",
    "Đã render được mấy video rồi?",
    "Truyện nào cập nhật gần nhất?",
    "Có job nào thất bại không?",
    "/db hogwarts",
])
def test_data_questions_detected(q):
    assert chat_db.is_data_question(q)


@pytest.mark.parametrize("q", [
    "Chương 3 báo cáo nói gì?",
    "Khóa ngoại là gì?",
    "Stable Diffusion sinh ảnh như thế nào?",
    "Làm sao để cào truyện?",
    "Xin chào",
])
def test_non_data_questions_left_to_docs(q):
    assert not chat_db.is_data_question(q)


def test_story_named_by_foreign_word_or_phrase(db_path):
    stories = chat_db.load_stories(db_path)
    names = lambda q: [s["name"] for s in chat_db.match_stories(q, stories)]  # noqa: E731
    assert names("Truyện Hogwarts có bao nhiêu chương?") == ["Bảng học tập Hogwarts"]
    assert names("truyen 10 nam tu luyen con chuong nao") == ["10 năm tu luyện ẩn dật"]


def test_common_words_do_not_match_a_story(db_path):
    """"nhất", "chưa"/"chúa", "lồng"/"lòng" bỏ dấu trùng tên truyện — từng nhận nhầm."""
    stories = chat_db.load_stories(db_path)
    for q in ["Truyện nào có nhiều chương nhất?",
              "Truyện nào chưa có video?",
              "Liệt kê các truyện đang ở bước lồng tiếng",
              "Người dùng có bao nhiêu truyện?"]:
        assert chat_db.match_stories(q, stories) == [], q


def test_this_story_uses_current_story(db_path):
    d = chat_db.gather(db_path, "Truyện này còn chương nào chưa có video?",
                       current_story="10 năm tu luyện ẩn dật")
    assert d["truyen"] == ["10 năm tu luyện ẩn dật"]
    assert d["ro_ten"] is False


# ---------------------------------------------------------------- dữ liệu

def test_overview_has_precomputed_numbers(db_path):
    d = chat_db.gather(db_path, "Có bao nhiêu truyện?")
    ctx = d["context"]
    assert d["loai"] == ["tong_quan"]
    assert "Tổng số truyện: 7" in ctx
    assert "chương đã có video: 2" in ctx
    assert "VIDEO_FAILED (lỗi video): 3 truyện" in ctx
    assert "2026-09: 2 truyện" in ctx


def test_story_block_states_missing_chapters_in_full_sentence(db_path):
    d = chat_db.gather(db_path, "Truyện 10 năm tu luyện còn chương nào chưa có video?")
    assert d["loai"] == ["tong_quan", "truyen"]
    assert "còn 1 chương CHƯA có video: chương số 2" in d["context"]
    # Câu hỏi về một truyện chỉ kèm tổng quan ngắn — bảng mọi truyện làm 3B đọc lẫn.
    assert "Bảng các truyện" not in d["context"]

    d = chat_db.gather(db_path, "Hogwarts những chương nào chưa có video?")
    assert "Cả 3 chương đều CHƯA có video" in d["context"]


@pytest.mark.parametrize("q,expect", [
    ("Những truyện nào bị lỗi video?", {"Bảng học tập Hogwarts", "Người Trên Vạn Người",
                                        "Infinity: Chiến đấu trong thế giới điện ảnh"}),
    ("Liệt kê các truyện đang ở bước lồng tiếng", {"Tiểu Thư Hào Môn Trở Về"}),
    ("Trong tháng 9 tạo bao nhiêu truyện?", {"10 năm tu luyện ẩn dật", "Người bắt chước chúa"}),
    ("Truyện nào bị huỷ?", {"Nếu ngươi chỉ đơn thuần có tài năng trong Đệ Nhất Thánh Quỷ Phái"}),
])
def test_filters_from_question(db_path, q, expect):
    d = chat_db.gather(db_path, q)
    assert "loc" in d["loai"]
    assert set(d["hits"]) == expect
    assert d["context"].startswith("## KẾT QUẢ KHỚP CÂU HỎI")


def test_jobs_block_says_table_empty(db_path):
    d = chat_db.gather(db_path, "Có job nào thất bại không?")
    assert "job" in d["loai"]
    assert "Bảng jobs chưa có bản ghi nào" in d["context"]
    assert "loc" not in d["loai"]  # "thất bại" ở đây nói về job, không lọc truyện


def test_db_opened_read_only(db_path):
    conn = chat_db._connect_ro(db_path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM stories")
    finally:
        conn.close()


def test_completeness_note_adds_dropped_items(db_path):
    d = chat_db.gather(db_path, "Những truyện nào bị lỗi video?")
    ans = "Người Trên Vạn Người và Bảng học tập Hogwarts bị lỗi video."
    note = chat_db.completeness_note(ans, d)
    assert "Infinity" in note and "(3)" in note
    full = "Infinity: Chiến đấu trong thế giới điện ảnh, Nguoi Tren Van Nguoi, Bang hoc tap Hogwarts"
    assert chat_db.completeness_note(full, d) == ""


# ---------------------------------------------------------------- qua API

def test_api_data_question_streams_answer_with_db_context(db_path):
    from fastapi.testclient import TestClient
    from orchestrator import main

    async def fake_stream(**kw):
        sys_prompt = kw["messages"][0]["content"]
        assert "KẾT QUẢ KHỚP CÂU HỎI" in sys_prompt
        yield {"delta": "Có 3 truyện lỗi video: Bảng học tập Hogwarts, Người Trên Vạn Người."}
        yield {"done": True, "prompt_tokens": 10, "truncated": False}

    ready = {"ok": True, "server": True, "model_installed": True, "reason": ""}
    with patch.object(main.storage_mgr, "db_path", db_path), \
            patch.object(main, "_sync_db_for_chat", lambda *a, **k: None), \
            patch.object(main.ollama_manager, "ensure_ready", return_value=ready), \
            patch.object(main, "chat_stream_ollama", fake_stream), \
            patch.object(main.chat_mgr, "get_gpu_weight", return_value=("none", [])):
        res = TestClient(main.app).post("/api/chat", json={
            "session_id": "db-test", "message": "Những truyện nào bị lỗi video?", "mode": "auto"})
    assert res.status_code == 200
    lines = [json.loads(x) for x in res.text.strip().split("\n") if x.strip()]
    text = "".join(x.get("delta", "") for x in lines)
    assert "Infinity" in text  # chốt bổ sung mục model bỏ sót
    done = lines[-1]
    assert done["done"] is True and "loc" in done["db"]["loai"]
