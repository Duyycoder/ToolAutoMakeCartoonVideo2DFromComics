import os
import json
from typing import Dict, Any

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "configs", "global_config.json"))

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
                "default_site": "69shuba"
            },
            "tts": {
                "default_engine": "edge",
                "default_voice": "vi-VN-NamMinhNeural",
                "normalize": True,
                "target_lufs": -14.0,
                "speed": 1.0
            },
            "video": {
                "default_style": "anime_2d_flat",
                "use_gpu": True
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
