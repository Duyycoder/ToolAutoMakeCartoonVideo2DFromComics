import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from orchestrator.main import app, chat_mgr, process_mgr, auto_run_mgr
from orchestrator.llm import resolve_llm, unload_ollama
from orchestrator.chatbot import remove_vietnamese_diacritics


@pytest.fixture
def client():
    return TestClient(app)


def test_remove_vietnamese_diacritics():
    assert remove_vietnamese_diacritics("Bước 3 nên chọn checkpoint nào?") == "buoc 3 nen chon checkpoint nao?"
    assert remove_vietnamese_diacritics("Hoả Vân Lộ") == "hoa van lo"


def test_resolve_llm_ollama():
    key, url, model = resolve_llm("ollama", {}, {"crawler": {"ollama_base_url": "http://localhost:11434/v1"}}, "qwen2.5:3b-instruct")
    assert key == "ollama"
    assert url == "http://localhost:11434/v1"
    assert model == "qwen2.5:3b-instruct"


def test_select_kb_scoring_and_budget():
    sections, max_score = chat_mgr.select_kb("bước 2 engine tts", active_tab="step2", token_budget=3000)
    assert len(sections) > 0
    assert max_score > 0.25
    # Tự tăng điểm cho file tab step2
    assert any("02-buoc2-tts.md" in s["file"] for s in sections)


def test_build_system_prompt():
    sec = [{"file": "02-buoc2-tts.md", "content": "Nội dung TTS"}]
    prompt = chat_mgr.build_system_prompt(sec, "Ngữ cảnh truyện test")
    assert "<tailieu>" in prompt
    assert "<noidungtruyen>" in prompt
    assert "QUY TẮC BẮT BUỘC CHỐNG BỊA ĐẶT" in prompt


def test_lookup_only():
    res = chat_mgr.lookup_only("bước 3 checkpoint", active_tab="step3")
    assert res["found"] is True
    assert "Trích tài liệu" in res["answer"]
    assert len(res["sources"]) > 0


def test_session_lifecycle():
    sid = "test-session-1"
    sess = chat_mgr.get_or_create_session(sid, max_sessions=2, ttl_minutes=120)
    assert sess is not None

    # Tạo thêm 2 session để kích hoạt prune max_sessions
    chat_mgr.get_or_create_session("test-session-2", max_sessions=2, ttl_minutes=120)
    chat_mgr.get_or_create_session("test-session-3", max_sessions=2, ttl_minutes=120)
    assert len(chat_mgr.sessions) <= 2


def test_gpu_weight_resolution():
    with patch.object(process_mgr, "list_running", return_value=["hvl_step3"]):
        weight, tasks = chat_mgr.get_gpu_weight()
        assert weight == "heavy"
        assert "hvl_step3" in tasks

    with patch.object(process_mgr, "list_running", return_value=["hvl_step1"]):
        weight, tasks = chat_mgr.get_gpu_weight()
        assert weight == "medium"

    with patch.object(process_mgr, "list_running", return_value=[]):
        with patch.object(auto_run_mgr, "list_running_chains", return_value=[]):
            weight, tasks = chat_mgr.get_gpu_weight()
            assert weight == "none"


def test_api_chat_health(client):
    res = client.get("/api/chat/health")
    assert res.status_code == 200
    data = res.json()
    assert "ollama_online" in data
    assert "gpu_weight" in data


def test_api_system_busy(client):
    res = client.get("/api/system/busy")
    assert res.status_code == 200
    data = res.json()
    assert "running" in data
    assert "tasks" in data


def test_api_chat_409_conflict(client):
    with patch.object(chat_mgr, "get_gpu_weight", return_value=("heavy", ["hvl_step3"])):
        payload = {
            "session_id": "s-test",
            "message": "Bước 3 chọn checkpoint nào?",
            "force": False
        }
        res = client.post("/api/chat", json=payload)
        assert res.status_code == 409
        data = res.json()
        assert "lookup_answer" in data


def test_api_agent_query(client):
    res = client.post("/api/agent/query", json={"action": "system_status"})
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "system_status"


def test_unload_ollama_mock():
    with patch("httpx.Client.post") as mock_post:
        mock_res = MagicMock()
        mock_res.raise_for_status.return_value = None
        mock_post.return_value = mock_res

        ok = unload_ollama("http://localhost:11434/v1", "qwen2.5:3b-instruct")
        assert ok is True
        mock_post.assert_called_once()


def test_api_chat_prewarm(client):
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_post.return_value = mock_res

        res = client.post("/api/chat/prewarm")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["prewarmed", "busy_skipped", "disabled"]
