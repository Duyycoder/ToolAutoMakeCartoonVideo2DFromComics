"""P0: render_mode mặc định "auto" — MediaComposer tự chọn theo phần cứng.

"auto" không được truyền xuống CLI (adapter chỉ nhận classic/studio); chọn tay
thì luôn được truyền và thắng.
"""
from orchestrator.main import Step3Schema
from tests.test_pipeline_llm import arg_of, pipe  # noqa: F401  (fixture)


def test_schema_mac_dinh_auto():
    assert Step3Schema(story_name="x").render_mode == "auto"


def test_auto_khong_truyen_co_render_mode(pipe):  # noqa: F811
    p, proc, set_config = pipe
    set_config({"video": {"default_llm_engine": "ollama"}})
    p.start_step_3_video("Test", {"render_mode": "auto"})
    assert "--render-mode" not in proc.captured_cmd


def test_khong_chi_dinh_thi_dung_config_chung(pipe):  # noqa: F811
    p, proc, set_config = pipe
    set_config({"video": {"default_llm_engine": "ollama", "render_mode": "studio"}})
    p.start_step_3_video("Test", {})
    assert arg_of(proc.captured_cmd, "--render-mode") == "studio"


def test_user_chon_classic_thi_thang(pipe):  # noqa: F811
    p, proc, set_config = pipe
    set_config({"video": {"default_llm_engine": "ollama", "render_mode": "studio"}})
    p.start_step_3_video("Test", {"render_mode": "classic"})
    assert arg_of(proc.captured_cmd, "--render-mode") == "classic"


def test_config_mac_dinh_render_mode_auto(tmp_path, monkeypatch):
    import orchestrator.config as config_mod
    monkeypatch.setattr(config_mod, "CONFIG_PATH", str(tmp_path / "global_config.json"))
    cfg = config_mod.load_global_config()
    assert cfg["video"]["render_mode"] == "auto"
