"""Kiem tra nguon "Sang tac bang AI" (ai_write) di dung mot loi qua
start_step_1_crawl_translate — de ca nut Buoc 1 le lan chuoi auto-run deu chay.

Khong goi LLM that: story_writer.generate_story duoc thay bang stub.
"""
import time

import orchestrator.config as config_mod
import orchestrator.story_writer as story_writer
from orchestrator.pipeline import NovelPipeline, _resolve_ai_write_args
from tests.test_pipeline_llm import StubProcess


class _TmpStorage:
    def __init__(self, root):
        self.root = root
        self.meta = {"story_slug": "test-story", "status": "READY"}

    def read_story_meta(self, _name):
        return dict(self.meta)

    def get_story_dir(self, _name):
        return str(self.root)

    def write_story_meta(self, _name, meta):
        self.meta = dict(meta)


def _wait_completed(proc, task_key, timeout=5.0):
    deadline = time.time() + timeout
    while proc.completed_exit_codes.get(task_key) is None and time.time() < deadline:
        time.sleep(0.02)
    return proc.completed_exit_codes.get(task_key)


def test_ai_write_routes_through_step1(monkeypatch, tmp_path):
    proc = StubProcess()
    storage = _TmpStorage(tmp_path)
    pipeline = NovelPipeline(storage, proc)
    monkeypatch.setattr(config_mod, "load_global_config", lambda: {})

    captured = {}

    def fake_generate_story(**kwargs):
        captured.update(kwargs)
        return 3

    monkeypatch.setattr(story_writer, "generate_story", fake_generate_story)

    ok = pipeline.start_step_1_crawl_translate(
        "Test",
        {"source": "ai_write", "topic": "  y tuong  ", "num_chapters": 3},
        {"engine": "gemini_api",
         "gemini_offline_base_url": "http://proxy/v1",
         "gemini_offline_model": "gemini-x",
         "gemini_api_key": "KEY", "genre": "tien_hiep"},
    )

    assert ok is True
    assert proc.captured_cmd is None  # KHONG dung lenh crawl cho ai_write
    assert _wait_completed(proc, "test-story_step1") == 0

    # Tham so LLM resolve dung tu trans_args, topic da duoc trim
    assert captured["topic"] == "y tuong"
    assert captured["num_chapters"] == 3
    assert captured["base_url"] == "http://proxy/v1"
    assert captured["model"] == "gemini-x"
    assert captured["api_key"] == "KEY"
    assert captured["genre"] == "tien_hiep"

    # Sinh xong -> danh dau TRANSLATED de buoc TTS chay tiep (bo qua dich)
    assert storage.meta["status"] == "TRANSLATED"
    assert storage.meta["pipeline_step"] == 2


def test_ai_write_ollama_resolution(monkeypatch):
    monkeypatch.setattr(
        config_mod, "load_global_config",
        lambda: {"crawler": {"ollama_base_url": "http://oll/v1"}})
    args = _resolve_ai_write_args(
        {"topic": " t ", "num_chapters": 5},
        {"engine": "ollama", "ollama_model": "qwen3:8b", "genre": "kiem_hiep"})
    assert args["base_url"] == "http://oll/v1"
    assert args["model"] == "qwen3:8b"
    assert args["api_key"] == ""
    assert args["topic"] == "t"
    assert args["num_chapters"] == 5
    assert args["genre"] == "kiem_hiep"


def test_ai_write_gemini_defaults(monkeypatch):
    monkeypatch.setattr(config_mod, "load_global_config", lambda: {})
    args = _resolve_ai_write_args(
        {"topic": "x", "num_chapters": 1},
        {"engine": "gemini_api"})
    assert args["base_url"] == "http://localhost:7860/v1"
    assert args["model"] == "gemini-2.5-flash"
