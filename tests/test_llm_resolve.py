import pytest
from orchestrator.llm import resolve_llm, danh_sach_model_ollama
from orchestrator.config import DEFAULT_OLLAMA_MODEL, DEFAULT_GEMINI_ONLINE_MODEL, DEFAULT_GEMINI_PROXY_MODEL
from orchestrator.pipeline import NovelPipeline

def test_resolve_llm_ollama_fixes_gemini_name():
    g_config = {}
    key, base_url, model = resolve_llm("ollama", {"llm_offline_model": "gemini-3-flash"}, g_config, "gemini-3-flash")
    assert model == DEFAULT_OLLAMA_MODEL

def test_resolve_llm_gemini_fixes_ollama_name():
    g_config = {"api_keys": {"gemini": "test-key"}}
    key, base_url, model = resolve_llm("gemini", {"llm_offline_model": "qwen2.5:7b-instruct"}, g_config, "qwen2.5:7b-instruct")
    assert model == DEFAULT_GEMINI_ONLINE_MODEL

    key, base_url, model = resolve_llm("gemini_api", {"llm_offline_model": "llama3.1:latest"}, g_config, "llama3.1:latest")
    assert model == DEFAULT_GEMINI_PROXY_MODEL

class DummyResponse:
    def __init__(self, data=None):
        self.data = data
    def raise_for_status(self): pass
    def json(self): return self.data

class DummyClient:
    def __init__(self, data=None, error=False):
        self.data = data
        self.error = error
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def get(self, url):
        if self.error:
            raise Exception("Network error")
        return DummyResponse(self.data)

def test_danh_sach_model_ollama(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "Client", lambda timeout: DummyClient({"models": [{"name": "qwen2.5:7b-instruct"}]}))
    res = danh_sach_model_ollama("http://localhost:11434")
    assert res == ["qwen2.5:7b-instruct"]

    monkeypatch.setattr(httpx, "Client", lambda timeout: DummyClient(error=True))
    res = danh_sach_model_ollama("http://localhost:11434")
    assert res is None

def test_start_step_3_video_model_fallback(monkeypatch):
    import orchestrator.pipeline as pipe_mod
    import httpx
    monkeypatch.setattr(httpx, "Client", lambda timeout: DummyClient({"models": [{"name": "qwen2.5:7b-instruct"}]}))
    
    from test_pipeline_llm import StubStorage, StubProcess
    proc = StubProcess()
    pipeline = NovelPipeline(StubStorage(), proc)
    
    monkeypatch.setattr("orchestrator.config.load_global_config", lambda: {})
    
    pipeline.start_step_3_video("Test", {"llm_engine": "ollama", "llm_model": "unknown_model"})
    cmd = proc.captured_cmd
    
    # should fallback to DEFAULT_OLLAMA_MODEL which is qwen2.5:7b-instruct since it's in the dummy client
    idx = cmd.index("--llm-model")
    assert cmd[idx+1] == "qwen2.5:7b-instruct"
