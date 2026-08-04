"""Unit tests tiêu thụ stream và kiểm tra payload Ollama options.num_ctx."""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from orchestrator.main import app, chat_mgr
from orchestrator.llm import chat_stream_ollama


_READY = {"ok": True, "server": True, "model_installed": True, "reason": ""}


@pytest.fixture
def client():
    return TestClient(app)


def test_stream_reports_when_model_cannot_be_prepared(client):
    """Ollama tắt & không pull được -> trả lời rõ ràng, không ném 500."""
    not_ready = {
        "ok": False, "server": False, "model_installed": False,
        "reason": "Không kết nối được Ollama.",
    }
    with patch("orchestrator.ollama_manager.ensure_ready", return_value=not_ready):
        res = client.post("/api/chat", json={
            "session_id": "stream-test-5",
            "message": "Bước 3 nên chọn checkpoint nào?",
            "mode": "auto"
        })
        assert res.status_code == 200
        lines = [line.strip() for line in res.text.strip().split("\n") if line.strip()]
        assert "Không kết nối được Ollama." in json.loads(lines[0])["delta"]
        last = json.loads(lines[-1])
        assert last.get("done") is True
        assert last.get("model_not_ready") is True


def test_stream_mode_lookup(client):
    res = client.post("/api/chat", json={
        "session_id": "stream-test-1",
        "message": "Bước 2 có mấy engine TTS?",
        "mode": "lookup"
    })
    assert res.status_code == 200
    lines = [line.strip() for line in res.text.strip().split("\n") if line.strip()]
    assert len(lines) >= 2
    
    first = json.loads(lines[0])
    assert "delta" in first
    assert "Edge-TTS" in first["delta"]

    last = json.loads(lines[-1])
    assert last.get("done") is True
    assert last.get("mode") == "lookup"


def test_stream_agent_l1_query(client):
    res = client.post("/api/chat", json={
        "session_id": "stream-test-2",
        "message": "Danh sách truyện",
        "mode": "auto"
    })
    assert res.status_code == 200
    lines = [line.strip() for line in res.text.strip().split("\n") if line.strip()]
    assert len(lines) >= 2
    
    last = json.loads(lines[-1])
    assert last.get("done") is True
    assert "agent_result" in last
    assert last["agent_result"]["type"] == "story_list"


def test_stream_gate_refusal(client):
    with patch.object(chat_mgr, "select_kb", return_value=([], 0.05)):
        res = client.post("/api/chat", json={
            "session_id": "stream-test-3",
            "message": "Viết giúp em đoạn code Python",
            "mode": "auto"
        })
        assert res.status_code == 200
        lines = [line.strip() for line in res.text.strip().split("\n") if line.strip()]
        last = json.loads(lines[-1])
        assert last.get("done") is True
        assert last.get("gate_refusal") is True


def test_stream_llm_main_flow(client):
    async def mock_async_stream(*args, **kwargs):
        yield {"delta": "Xin chào! "}
        yield {"delta": "Tôi là Trợ lý AI."}
        yield {"done": True, "prompt_tokens": 150, "truncated": False}

    # Ollama đã sẵn sàng -> preflight im lặng, stream không có dòng thông báo thừa.
    with patch("orchestrator.main.chat_stream_ollama", side_effect=mock_async_stream), \
         patch("orchestrator.ollama_manager.ensure_ready", return_value=_READY):
        res = client.post("/api/chat", json={
            "session_id": "stream-test-4",
            "message": "Bước 3 nên chọn checkpoint nào?",
            "mode": "auto"
        })
        assert res.status_code == 200
        lines = [line.strip() for line in res.text.strip().split("\n") if line.strip()]
        assert len(lines) == 3
        d1 = json.loads(lines[0])
        assert d1["delta"] == "Xin chào! "
        d3 = json.loads(lines[2])
        assert d3["done"] is True


@pytest.mark.anyio
async def test_ollama_payload_passes_num_ctx():
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    
    async def mock_aiter_lines():
        yield json.dumps({"message": {"content": "Test response"}, "done": False})
        yield json.dumps({"done": True, "prompt_eval_count": 100})

    mock_response.aiter_lines = mock_aiter_lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__.return_value = mock_response

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx) as mock_stream:
        chunks = []
        async for chunk in chat_stream_ollama(
            base_url="http://localhost:11434/v1",
            model="qwen2.5:3b-instruct",
            messages=[{"role": "user", "content": "Hi"}],
            num_ctx=8192
        ):
            chunks.append(chunk)

        assert len(chunks) == 2
        mock_stream.assert_called_once()
        call_kwargs = mock_stream.call_args[1]
        json_payload = call_kwargs["json"]
        assert "options" in json_payload
        assert json_payload["options"]["num_ctx"] == 8192
