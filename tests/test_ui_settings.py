"""Roundtrip lưu/đọc toàn bộ cấu hình UI (configs/ui_settings.json)."""
import orchestrator.config as config_mod


def test_ui_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "UI_SETTINGS_PATH", str(tmp_path / "ui_settings.json"))
    data = {
        "fields": {
            "s1Source": {"v": "local"},
            "s2Engine": {"v": "edge"},
            "s1AutoExtract": {"c": True},
            "s3Upscale": {"c": False},
        },
        "radios": {"s4VideoSource": "local"},
        "story": "Truyện Tiếng Việt có dấu",
    }
    assert config_mod.save_ui_settings(data)
    assert config_mod.load_ui_settings() == data


def test_ui_settings_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "UI_SETTINGS_PATH", str(tmp_path / "khong_ton_tai.json"))
    assert config_mod.load_ui_settings() == {}


def test_ui_settings_corrupt_file_returns_empty(tmp_path, monkeypatch):
    p = tmp_path / "ui_settings.json"
    p.write_text("{hong json", encoding="utf-8")
    monkeypatch.setattr(config_mod, "UI_SETTINGS_PATH", str(p))
    assert config_mod.load_ui_settings() == {}
