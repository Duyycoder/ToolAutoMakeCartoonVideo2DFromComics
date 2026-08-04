"""Unit tests cho tự khởi động Ollama + tự pull model còn thiếu."""
from unittest.mock import patch

from orchestrator import ollama_manager as om


def test_to_root_strips_openai_suffix():
    assert om.to_root("http://localhost:11434/v1") == "http://localhost:11434"
    assert om.to_root("http://localhost:11434/") == "http://localhost:11434"
    assert om.to_root("") == om.DEFAULT_ROOT


def test_same_tag_treats_latest_as_default():
    assert om.same_tag("qwen2.5:3b", "qwen2.5:3b")
    assert om.same_tag("qwen2.5", "qwen2.5:latest")
    assert not om.same_tag("qwen2.5:3b", "qwen2.5:7b")


def test_ensure_server_skips_start_when_already_up():
    with patch.object(om, "is_server_up", return_value=True), \
         patch.object(om, "find_ollama_exe") as find:
        assert om.ensure_server("http://localhost:11434/v1") is True
        find.assert_not_called()


def test_ensure_server_reports_when_ollama_not_installed():
    with patch.object(om, "is_server_up", return_value=False), \
         patch.object(om, "find_ollama_exe", return_value=None):
        assert om.ensure_server("http://localhost:11434") is False


def test_ensure_server_respects_autostart_off():
    with patch.object(om, "is_server_up", return_value=False), \
         patch.object(om, "find_ollama_exe") as find:
        assert om.ensure_server("http://localhost:11434", autostart=False) is False
        find.assert_not_called()


def test_ensure_ready_pulls_missing_model():
    with patch.object(om, "ensure_server", return_value=True), \
         patch.object(om, "has_model", return_value=False), \
         patch.object(om, "pull_model", return_value=True) as pull:
        res = om.ensure_ready("qwen2.5:3b", "http://localhost:11434/v1")
        assert res["ok"] is True
        assert res["model_installed"] is True
        pull.assert_called_once()


def test_ensure_ready_does_not_pull_when_model_present():
    with patch.object(om, "ensure_server", return_value=True), \
         patch.object(om, "has_model", return_value=True), \
         patch.object(om, "pull_model") as pull:
        res = om.ensure_ready("qwen2.5:3b")
        assert res["ok"] is True
        pull.assert_not_called()


def test_ensure_ready_fails_with_reason_when_pull_fails():
    with patch.object(om, "ensure_server", return_value=True), \
         patch.object(om, "has_model", return_value=False), \
         patch.object(om, "pull_model", return_value=False):
        res = om.ensure_ready("khong-ton-tai:1b")
        assert res["ok"] is False
        assert "khong-ton-tai:1b" in res["reason"]


def test_ensure_ready_fails_when_server_unavailable():
    with patch.object(om, "ensure_server", return_value=False), \
         patch.object(om, "pull_model") as pull:
        res = om.ensure_ready("qwen2.5:3b")
        assert res["ok"] is False
        assert res["server"] is False
        assert "Ollama" in res["reason"]
        pull.assert_not_called()
