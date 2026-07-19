import os
import json
from typing import Dict, Any

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "configs", "global_config.json"))
UI_SETTINGS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "configs", "ui_settings.json"))

DEFAULT_GEMINI_ONLINE_MODEL = "gemini-2.0-flash"
DEFAULT_GEMINI_PROXY_MODEL = "gemini-3-flash"
DEFAULT_OLLAMA_MODEL = "qwen2.5:3b-instruct"

def load_global_config() -> Dict[str, Any]:
    """Loads the global configuration, creating defaults if missing."""
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        default_cfg = {
            "api_keys": {
                "gemini": ""
            },
            "storage_dir": "storage",
            "orchestrator_port": 8100,
            "crawler": {
                "default_site": "local",
                "gemini_offline_base_url": "http://localhost:7860/v1",
                "gemini_offline_key": "",
                "ollama_base_url": "http://localhost:11434/v1"
            },
            "tts": {
                "default_engine": "edge",
                "default_voice": "vi-VN-NamMinhNeural",
                "kokoro_voice": "thuc_trinh",
                "vieneu_mode": "v3turbo",
                "vieneu_voice": "Ngọc Lan",
                "normalize": True,
                "target_lufs": -14.0,
                "speed": 1.0
            },
            "video": {
                "default_style": "anime_2d_flat",
                "use_gpu": True,
                "default_checkpoint": "anything-v5",
                "bgm_volume": 0.15,
                "default_llm_engine": "gemini_api",
                "default_llm_model": DEFAULT_GEMINI_PROXY_MODEL
            }
        }
        save_global_config(default_cfg)
        return default_cfg
        
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_global_config(config: Dict[str, Any]) -> bool:
    """Saves the global configuration."""
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def load_ui_settings() -> Dict[str, Any]:
    """Trạng thái toàn bộ form trên webui do người dùng bấm 'Lưu cấu hình'."""
    if not os.path.exists(UI_SETTINGS_PATH):
        return {}
    try:
        with open(UI_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_ui_settings(data: Dict[str, Any]) -> bool:
    try:
        os.makedirs(os.path.dirname(UI_SETTINGS_PATH), exist_ok=True)
        with open(UI_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
