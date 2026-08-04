"""Unit tests cho bước tự tải mô hình còn thiếu lúc mở ứng dụng."""
from orchestrator.model_preflight import _wanted_ollama_models


def test_chatbot_model_always_wanted_when_enabled():
    cfg = {"chatbot": {"enabled": True, "model": "qwen2.5:3b"}}
    assert _wanted_ollama_models(cfg) == ["qwen2.5:3b"]


def test_chatbot_model_skipped_when_disabled():
    cfg = {"chatbot": {"enabled": False, "model": "qwen2.5:3b"}}
    assert _wanted_ollama_models(cfg) == []


def test_only_pulls_engines_actually_selected():
    """Bước 1/3 dùng Gemini thì không được tải model Ollama của chúng."""
    cfg = {
        "chatbot": {"enabled": True, "model": "qwen2.5:3b"},
        "translate": {"default_engine": "gemini_api", "ollama_model": "hy-mt2:1.8b"},
        "video": {"default_llm_engine": "gemini_api", "default_llm_model": "gemini-3-flash"},
    }
    assert _wanted_ollama_models(cfg) == ["qwen2.5:3b"]


def test_pulls_step_models_when_ollama_selected():
    cfg = {
        "chatbot": {"enabled": True, "model": "qwen2.5:3b"},
        "translate": {"default_engine": "ollama", "ollama_model": "hy-mt2:1.8b"},
        "video": {"default_llm_engine": "ollama", "default_llm_model": "qwen2.5:7b-instruct"},
    }
    assert _wanted_ollama_models(cfg) == [
        "qwen2.5:3b", "hy-mt2:1.8b", "qwen2.5:7b-instruct",
    ]


def test_duplicate_models_pulled_once():
    cfg = {
        "chatbot": {"enabled": True, "model": "qwen2.5:3b"},
        "translate": {"default_engine": "ollama", "ollama_model": "qwen2.5:3b"},
    }
    assert _wanted_ollama_models(cfg) == ["qwen2.5:3b"]


def test_empty_config_wants_nothing():
    assert _wanted_ollama_models({}) == []
