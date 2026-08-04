import pytest
from orchestrator.pipeline import NovelPipeline
from tests.test_pipeline_llm import StubStorage, StubProcess, arg_of

@pytest.fixture
def pipe(monkeypatch):
    import orchestrator.config as config_mod
    proc = StubProcess()
    pipeline = NovelPipeline(StubStorage(), proc)
    state = {"config": {}}
    monkeypatch.setattr(config_mod, "load_global_config", lambda: state["config"])
    def set_config(cfg):
        state["config"] = cfg
    return pipeline, proc, set_config

def test_step1_crawl_cmd_source_not_local(pipe):
    p, proc, set_config = pipe
    p.start_step_1_crawl_translate("Test", {"source": "69shuba", "story_id": "123", "base_url": "http://test", "continue_download": True}, {})
    cmd = proc.captured_cmd
    assert cmd is not None
    assert "crawl" in cmd
    assert arg_of(cmd, "--source") == "69shuba"
    assert arg_of(cmd, "--story-id") == "123"
    assert arg_of(cmd, "--base-url") == "http://test"
    assert "--continue-download" in cmd

def test_step1_crawl_cmd_source_local(pipe):
    p, proc, set_config = pipe
    p.start_step_1_crawl_translate("Test", {"source": "local", "local_folder": "some/folder"}, {})
    # Should not trigger crawl_cmd, but spawns a thread. proc.captured_cmd should be None.
    assert proc.captured_cmd is None

def test_step4_crop_args(pipe):
    p, proc, set_config = pipe
    set_config({"crawler": {"gemini_offline_key": "dummy"}})
    # Missing one crop arg -> no crop flags
    p.start_step_4_autosub("Test", {"crop_x": 10, "crop_y": 10, "crop_w": 100})
    cmd = proc.captured_cmd
    assert "--crop-x" not in cmd
    
    # All valid crop args -> present
    p.start_step_4_autosub("Test", {"crop_x": 10, "crop_y": 10, "crop_w": 100, "crop_h": 100})
    cmd = proc.captured_cmd
    assert arg_of(cmd, "--crop-x") == "10"
    assert arg_of(cmd, "--crop-h") == "100"

def test_step4_styling_and_cookies(pipe):
    p, proc, set_config = pipe
    set_config({"video": {"downloader_cookies": "test_cookie"}, "crawler": {"gemini_offline_key": "dummy"}})
    p.start_step_4_autosub("Test", {"font_name": "Arial", "bg_alpha": 0.5})
    cmd = proc.captured_cmd
    assert arg_of(cmd, "--font-name") == "Arial"
    assert arg_of(cmd, "--bg-alpha") == "0.5"
    assert arg_of(cmd, "--cookies-file") == "test_cookie"

def test_step5_merge(pipe):
    p, proc, set_config = pipe
    # start_step_5_merge creates a thread instead of using start_process, so we just check queue creation.
    p.start_step_5_merge("test-story", {})
    assert "test-story_step5" in p.process_mgr.log_queues


def test_step4_output_dir_override(pipe, tmp_path):
    """Thư mục đầu ra do người dùng chỉ định (autosub_args) được ưu tiên."""
    p, proc, set_config = pipe
    set_config({"crawler": {"gemini_offline_key": "dummy"}})
    out = str(tmp_path / "myout")
    p.start_step_4_autosub("Test", {"output_dir": out, "video_path": "x.mp4"})
    assert arg_of(proc.captured_cmd, "--output-dir") == out


def test_step4_output_dir_from_config(pipe, tmp_path):
    """Không có trong request thì lấy autosub.output_dir từ Cấu Hình Chung."""
    p, proc, set_config = pipe
    cfgout = str(tmp_path / "cfgout")
    set_config({"crawler": {"gemini_offline_key": "dummy"}, "autosub": {"output_dir": cfgout}})
    p.start_step_4_autosub("Test", {"video_path": "x.mp4"})
    assert arg_of(proc.captured_cmd, "--output-dir") == cfgout


def test_step4_output_dir_default_when_unset(pipe):
    """Cả request lẫn cấu hình đều trống -> dùng mặc định theo truyện (…/video)."""
    p, proc, set_config = pipe
    set_config({"crawler": {"gemini_offline_key": "dummy"}})
    p.start_step_4_autosub("Test", {"video_path": "x.mp4"})
    out = arg_of(proc.captured_cmd, "--output-dir")
    assert out.replace("\\", "/").endswith("test-story/video")
