"""Cấu hình toàn cục + trạng thái form của giao diện.

Hai lớp lưu tách bạch, đừng trộn:
- `configs/global_config.json` — giá trị MẶC ĐỊNH của mọi tham số (mục "Cấu hình
  chung"). Chứa cả API key nên đã bị .gitignore loại trừ.
- `configs/ui_settings.json` — trạng thái các ô nhập trên từng tab, để mở lại app
  không phải điền lại. Không phải nguồn sự thật của tham số mặc định.
"""
import os
import json
from typing import Dict, Any

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "configs", "global_config.json"))
UI_SETTINGS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "configs", "ui_settings.json"))

DEFAULT_GEMINI_ONLINE_MODEL = "gemini-2.0-flash"
DEFAULT_GEMINI_PROXY_MODEL = "gemini-3-flash"
DEFAULT_OLLAMA_MODEL = "qwen2.5:3b-instruct"

DEFAULT_CONFIG: Dict[str, Any] = {
    "api_keys": {
        "gemini": ""
    },
    "storage_dir": "storage",
    "orchestrator_port": 8100,

    # Cào video (yt-dlp)
    "download": {
        "platform": "generic",
        "cookies_file": "",
        "max_items": 0,
        "skip_existing": True,
        "stop_on_error": False,
        "auto_translate": False
    },

    # LLM dùng để dịch phụ đề
    "translate": {
        "engine": "ollama",
        "target_lang": "Vietnamese",
        "ollama_base_url": "http://localhost:11434/v1",
        "ollama_model": DEFAULT_OLLAMA_MODEL,
        "mt_model": "hy-mt2:1.8b",
        "mt_model_du_phong": "qwen2.5:7b-instruct",
        "autostart_ollama": True,
        "gemini_offline_base_url": "http://localhost:7860/v1",
        "gemini_offline_key": "",
        # Đường dẫn start_server.bat của proxy Gemini-API nếu bạn tự cài ở nơi
        # khác — để trống thì app không tự bật proxy.
        "gemini_proxy_bat": ""
    },

    # Tạo phụ đề + lồng tiếng
    "autosub": {
        "output_dir": "",
        "source_lang": "English",
        "sub_source": "whisper",
        "burn_method": "ffmpeg",
        "clean_audio": False,
        "translate_only": False,
        "enable_voiceover": False,
        "tts_engine": "edge",
        "tts_voice": "vi-VN-NamMinhNeural",
        "auto_clone": False,
        "ducking_ratio": 90.0,
        "llm_engine": "ollama",
        "llm_model": "",
        "font_name": "",
        "font_size": 45,
        "text_color": "#ffffff",
        "stroke_color": "#000000",
        "stroke_width": 1.5,
        "bg_style": "None",
        "bg_color": "#000000",
        "bg_alpha": 140,
        "sub_position": "bottom",
        "custom_position": 70.0
    },

    "video": {
        "downloader_cookies": "",
        "ocr_use_gpu": True
    },

    # Trình edit video (xem docs/PLAN-editor.md). workspace trống = ~/CaoDichVideo (KHÔNG để trong Videos: Controlled Folder Access chặn)
    "editor": {
        "workspace": "",
        "tu_luu_giay": 1.5,
        "so_ban_lich_su": 20,
        "du_an_ngoai": []
    },

    "tts": {
        "default_engine": "edge",
        "default_voice": "vi-VN-NamMinhNeural",
        "kokoro_voice": "thuc_trinh",
        "vieneu_mode": "v3turbo",
        "vieneu_voice": "Ngọc Lan"
    }
}


def _merge_defaults(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Bổ sung khoá còn thiếu từ DEFAULT_CONFIG.

    Máy đã dùng từ trước có sẵn global_config.json nên KHÔNG đi qua nhánh tạo mặc
    định — thiếu bước này thì mỗi lần thêm tham số mới, giao diện mở ra với ô
    trống thay vì giá trị khuyến nghị.
    """
    for key, value in DEFAULT_CONFIG.items():
        if isinstance(value, dict):
            section = cfg.setdefault(key, {})
            if isinstance(section, dict):
                for sub_key, sub_value in value.items():
                    section.setdefault(sub_key, sub_value)
        else:
            cfg.setdefault(key, value)
    return cfg


def load_global_config() -> Dict[str, Any]:
    """Đọc cấu hình chung, tự tạo file mặc định nếu chưa có."""
    if not os.path.exists(CONFIG_PATH):
        default_cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        save_global_config(default_cfg)
        return default_cfg
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(DEFAULT_CONFIG))
    if not isinstance(cfg, dict):
        return json.loads(json.dumps(DEFAULT_CONFIG))
    return _merge_defaults(cfg)


def save_global_config(config: Dict[str, Any]) -> bool:
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def load_ui_settings() -> Dict[str, Any]:
    """Trạng thái toàn bộ form trên webui do người dùng bấm 'Lưu cấu hình'."""
    if not os.path.exists(UI_SETTINGS_PATH):
        return {}
    try:
        with open(UI_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_ui_settings(data: Dict[str, Any]) -> bool:
    try:
        os.makedirs(os.path.dirname(UI_SETTINGS_PATH), exist_ok=True)
        with open(UI_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False
