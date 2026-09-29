import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from orchestrator.main import app

client = TestClient(app)

def test_cai_dat_html_co_data_cfg_quan_trong(monkeypatch, tmp_path):
    # Mock Nơi làm việc to a temp path so it doesn't touch the real system
    import orchestrator.editor.api as editor_api
    monkeypatch.setattr(editor_api, "load_global_config", lambda: {"editor": {"workspace": str(tmp_path)}})

    res = client.get("/cai_dat.html")
    assert res.status_code == 200

    html = res.content.decode("utf-8")
    soup = BeautifulSoup(html, "html.parser")
    
    # Extract data-cfg from cai_dat.html
    tags = soup.find_all(attrs={"data-cfg": True})
    keys = {tag["data-cfg"] for tag in tags}

    # Keys from old tab-settings in batch.html
    required_keys = {
        "api_keys.gemini",
        "editor.so_ban_lich_su",
        "editor.tu_luu_giay",
        "editor.workspace",
        "storage_dir",
        "translate.autostart_ollama",
        "translate.engine",
        "translate.gemini_offline_base_url",
        "translate.gemini_proxy_bat",
        "translate.ollama_base_url",
        "translate.ollama_model",
        "video.ocr_use_gpu"
    }

    missing = required_keys - keys
    assert not missing, f"cai_dat.html thiếu các data-cfg: {missing}"

    # Also make sure other important config keys are there (for AI/Batch)
    ai_keys = {
        "autosub.source_lang", "translate.target_lang", "autosub.sub_source", "autosub.tts_engine",
        "autosub.ducking_ratio"
    }
    missing_ai = ai_keys - keys
    assert not missing_ai, f"cai_dat.html thiếu các data-cfg AI: {missing_ai}"
