import os
import re

from fastapi.testclient import TestClient

from orchestrator.main import app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_phien_ban_doc_tu_file_version():
    with open(os.path.join(ROOT, "VERSION"), encoding="utf-8") as f:
        ban = f.read().strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", ban)
    assert TestClient(app).get("/api/phien-ban").json() == {"phien_ban": ban}


def test_bo_cai_lay_phien_ban_tu_file_version():
    # Hai nơi ghi số phiên bản từng lệch nhau -> bộ cài phải đọc đúng file VERSION
    with open(os.path.join(ROOT, "installer", "AutoCartoon.iss"), encoding="utf-8-sig") as f:
        iss = f.read()
    assert r'FileOpen(AddBackslash(SourcePath) + "..\VERSION")' in iss
    assert not re.search(r'#define MyAppVersion "', iss)


def test_bo_cai_khong_ghi_de_file_rieng_cua_nguoi_dung():
    with open(os.path.join(ROOT, "installer", "AutoCartoon.iss"), encoding="utf-8-sig") as f:
        iss = f.read()
    excludes = re.search(r'Excludes: "([^"]+)"', iss).group(1).split(",")
    for p in (r"\configs\global_config.json", r"\configs\ui_settings.json", "api_keys.json", "*cookies*",
              r"\AIVoice\apps\MediaComposer\config.toml", r"\storage", r"\models", ".venv"):
        assert p in excludes, p
