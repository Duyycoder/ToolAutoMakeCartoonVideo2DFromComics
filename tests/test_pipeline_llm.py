"""Unit tests cho logic resolve tham so LLM (Buoc 3) va fallback TTS (Buoc 2)
trong orchestrator/pipeline.py.

Khong can GPU, khong can model, khong spawn tien trinh that:
- StorageManager/ProcessManager duoc thay bang stub.
- load_global_config duoc monkeypatch de test khong phu thuoc config that tren may.
"""
import pytest

import orchestrator.config as config_mod
from orchestrator.pipeline import NovelPipeline


class StubStorage:
    tasks_dir = "storage/tasks"

    def read_story_meta(self, name):
        return {"story_slug": "test-story", "status": "READY"}

    def get_story_dir(self, name):
        return "storage/truyen/test-story"

    def write_story_meta(self, name, meta):
        pass


class StubProcess:
    def __init__(self):
        self.captured_cmd = None
        self.log_queues = {}

    def start_process(self, task_key, cmd, cwd, env_override=None, on_completed=None, **kw):
        self.captured_cmd = cmd
        return True


def arg_of(cmd, flag):
    """Lay gia tri ngay sau mot co CLI trong lenh da bat duoc."""
    return cmd[cmd.index(flag) + 1]


@pytest.fixture
def pipe(monkeypatch):
    """Tra ve (pipeline, stub_process, set_config) voi config kiem soat duoc."""
    proc = StubProcess()
    pipeline = NovelPipeline(StubStorage(), proc)

    state = {"config": {}}
    monkeypatch.setattr(config_mod, "load_global_config", lambda: state["config"])

    def set_config(cfg):
        state["config"] = cfg

    return pipeline, proc, set_config


# ---------------------------------------------------------------------------
# Buoc 3: resolve LLM engine
# ---------------------------------------------------------------------------

def test_step3_gemini_api_offline_mac_dinh(pipe):
    p, proc, set_config = pipe
    set_config({"crawler": {"gemini_offline_base_url": "http://localhost:7860/v1"}})
    p.start_step_3_video("Test", {"llm_engine": "gemini_api"})
    cmd = proc.captured_cmd
    assert arg_of(cmd, "--llm-base-url") == "http://localhost:7860/v1"
    assert arg_of(cmd, "--llm-model") == "gemini-3-flash"
    assert arg_of(cmd, "--llm-api-key").startswith("sk-gemini-")


def test_step3_ollama_doc_base_url_tu_cau_hinh_chung(pipe):
    p, proc, set_config = pipe
    set_config({"crawler": {"ollama_base_url": "http://192.168.1.9:11434/v1"}})
    p.start_step_3_video("Test", {"llm_engine": "ollama"})
    cmd = proc.captured_cmd
    assert arg_of(cmd, "--llm-base-url") == "http://192.168.1.9:11434/v1"
    assert arg_of(cmd, "--llm-api-key") == "ollama"
    assert arg_of(cmd, "--llm-model") == "qwen2.5:3b-instruct"


def test_step3_ollama_fallback_11434_khi_config_trong(pipe):
    p, proc, set_config = pipe
    set_config({})
    p.start_step_3_video("Test", {"llm_engine": "ollama"})
    assert arg_of(proc.captured_cmd, "--llm-base-url") == "http://localhost:11434/v1"


def test_step3_gemini_online_lay_key_tu_request(pipe):
    p, proc, set_config = pipe
    set_config({})
    p.start_step_3_video("Test", {"llm_engine": "gemini", "llm_api_key": "AIza-test"})
    cmd = proc.captured_cmd
    assert "generativelanguage.googleapis.com" in arg_of(cmd, "--llm-base-url")
    assert arg_of(cmd, "--llm-api-key") == "AIza-test"
    assert arg_of(cmd, "--llm-model") == "gemini-2.0-flash"


def test_step3_gemini_online_thieu_key_phai_bao_loi_som(pipe):
    p, proc, set_config = pipe
    set_config({"api_keys": {"gemini": ""}})
    with pytest.raises(ValueError):
        p.start_step_3_video("Test", {"llm_engine": "gemini"})
    # Chua duoc phep spawn tien trinh khi cau hinh sai
    assert proc.captured_cmd is None


def test_step3_request_ghi_de_moi_fallback(pipe):
    p, proc, set_config = pipe
    set_config({"crawler": {"ollama_base_url": "http://localhost:11434/v1"}})
    p.start_step_3_video("Test", {
        "llm_engine": "ollama",
        "llm_offline_base_url": "http://10.0.0.2:11434/v1",
        "llm_offline_model": "qwen3:8b",
    })
    cmd = proc.captured_cmd
    assert arg_of(cmd, "--llm-base-url") == "http://10.0.0.2:11434/v1"
    assert arg_of(cmd, "--llm-model") == "qwen3:8b"


def test_step3_dung_mac_dinh_video_tu_cau_hinh_chung(pipe):
    p, proc, set_config = pipe
    set_config({"video": {
        "default_llm_engine": "ollama",
        "default_llm_model": "qwen3:8b",
        "default_style": "anime_2d_flat",
        "default_checkpoint": "meinamix",
        "bgm_volume": 0.25,
    }})
    p.start_step_3_video("Test", {})
    cmd = proc.captured_cmd
    assert arg_of(cmd, "--llm-api-key") == "ollama"
    assert arg_of(cmd, "--llm-model") == "qwen3:8b"
    assert arg_of(cmd, "--style") == "anime_2d_flat"
    assert arg_of(cmd, "--checkpoint") == "meinamix"
    assert arg_of(cmd, "--bgm-volume") == "0.25"


# ---------------------------------------------------------------------------
# Buoc 2: fallback TTS tu cau hinh chung
# ---------------------------------------------------------------------------

def test_step2_kokoro_dung_voice_rieng(pipe):
    p, proc, set_config = pipe
    set_config({"tts": {"kokoro_voice": "thuc_trinh", "default_voice": "vi-VN-NamMinhNeural"}})
    p.start_step_2_tts("Test", {"engine": "kokoro"})
    assert arg_of(proc.captured_cmd, "--voice") == "thuc_trinh"


def test_step2_vieneu_dung_voice_rieng_khong_dinh_voice_edge(pipe):
    p, proc, set_config = pipe
    set_config({"tts": {"vieneu_voice": "Ngọc Lan", "default_voice": "vi-VN-NamMinhNeural"}})
    p.start_step_2_tts("Test", {"engine": "vieneu"})
    assert arg_of(proc.captured_cmd, "--voice") == "Ngọc Lan"


def test_step2_engine_fallback_tu_cau_hinh_chung(pipe):
    p, proc, set_config = pipe
    set_config({"tts": {"default_engine": "kokoro", "kokoro_voice": "thuc_trinh"}})
    p.start_step_2_tts("Test", {})
    cmd = proc.captured_cmd
    assert arg_of(cmd, "--engine") == "kokoro"
    assert arg_of(cmd, "--voice") == "thuc_trinh"


def test_step2_voice_tu_request_thang_fallback(pipe):
    p, proc, set_config = pipe
    set_config({"tts": {"kokoro_voice": "thuc_trinh"}})
    p.start_step_2_tts("Test", {"engine": "kokoro", "voice": "giong_khac"})
    assert arg_of(proc.captured_cmd, "--voice") == "giong_khac"
