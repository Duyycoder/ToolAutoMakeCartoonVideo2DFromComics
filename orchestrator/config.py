import os
import json
from typing import Dict, Any

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "configs", "global_config.json"))
UI_SETTINGS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "configs", "ui_settings.json"))

DEFAULT_GEMINI_ONLINE_MODEL = "gemini-2.0-flash"
DEFAULT_GEMINI_PROXY_MODEL = "gemini-3-flash"
DEFAULT_OLLAMA_MODEL = "qwen2.5:3b-instruct"

# Tham số sinh ảnh cho Bước 3 — ghi xuống [storytelling] của MediaComposer
# trước mỗi lần chạy (xem orchestrator/mediacomposer_config.py).
SD_TUNING_DEFAULTS = {
    "sd_steps": 8,
    "sd_guidance": 5.0,
    "sd_image_width": 768,
    "sd_image_height": 432,
    "sd_output_width": 1920,
    "sd_output_height": 1080,
    "sd_video_fps": 24,
    "sd_face_detailer_steps": 14,
    "sd_face_detailer_strength": 0.45,
    "sd_ip_adapter_scale": 0.6,
    "sd_studio_render_steps": 0,
    "sd_studio_render_guidance": 0.0,
}

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
            # Bước 1 — mặc định dịch/sáng tác (dùng chung cho toàn dự án)
            "translate": {
                "default_engine": "gemini_api",
                "ollama_model": "qwen2.5:7b-instruct",
                "gemini_offline_model": "gemini-2.5-flash",
                "genre": "tien_hiep",
                "auto_translate": True,
                "auto_extract": True,
                "glossary_extract_engine": "gemini",
                "glossary_extract_ollama_model": ""
            },
            "tts": {
                "default_engine": "edge",
                "default_voice": "vi-VN-NamMinhNeural",
                "kokoro_voice": "thuc_trinh",
                "vieneu_mode": "v3turbo",
                "vieneu_voice": "Ngọc Lan",
                "vieneu_emotion": "",
                "normalize": True,
                "target_lufs": -14.0,
                "speed": 1.0,
                "fade_in": 0.1,
                "fade_out": 0.1,
                "silence_duration": 0.3,
                "device": "auto",
                "use_cache": False,
                "cache_threshold": 0.95,
                "temperature": 0.3
            },
            "video": {
                "default_style": "anime_2d_flat",
                "use_gpu": True,
                "default_checkpoint": "anything-v5",
                "bgm_path": "",
                "bgm_volume": 0.15,
                "default_llm_engine": "gemini_api",
                "default_llm_model": DEFAULT_GEMINI_PROXY_MODEL,
                "downloader_cookies": "",
                "genre": "tien_hiep",
                "enable_upscale": True,
                "burn_subtitles": False,
                "use_semantic_split": True,
                "extract_characters": True,
                "enable_face_detailer": False,
                "sd_steps": 8,
                "sd_guidance": 5.0,
                "sd_image_width": 768,
                "sd_image_height": 432,
                "sd_output_width": 1920,
                "sd_output_height": 1080,
                "sd_video_fps": 24,
                "sd_face_detailer_steps": 14,
                "sd_face_detailer_strength": 0.45,
                "sd_ip_adapter_scale": 0.6,
                "sd_studio_render_steps": 0,
                "sd_studio_render_guidance": 0.0,
                "render_mode": "studio",
                "hardware_profile": "auto",
                "device": "auto"
            },
            # Bước 4 — autosub/lồng tiếng (bao gồm thư mục đầu ra tùy chọn)
            "autosub": {
                "output_dir": "",
                "source_lang": "English",
                "sub_source": "whisper",
                "burn_method": "ffmpeg",
                "clean_audio": False,
                "enable_voiceover": False,
                "tts_engine": "edge",
                "tts_voice": "vi-VN-NamMinhNeural",
                "auto_clone": False,
                "ducking_ratio": 90.0,
                "llm_engine": "gemini_api",
                "llm_model": "gemini-3-flash",
                "font_name": "",
                "font_size": 45,
                "text_color": "#ffffff",
                "stroke_color": "#000000",
                "stroke_width": 1.5,
                "bg_style": "",
                "bg_color": "#000000",
                "bg_alpha": 140,
                "sub_position": "",
                "custom_position": 70.0
            },
            "chatbot": {
                "enabled": True,
                "model": "qwen2.5:3b",
                "share_model_with_step3": False,
                "base_url": "",
                "temperature": 0.4,
                "top_p": 0.9,
                "repeat_penalty": 1.05,
                "num_predict": 512,
                "num_ctx": 8192,
                "max_history_turns": 12,
                "kb_token_budget": 3000,
                "kb_min_score": 0.75,
                "kb_sticky_per_session": True,
                "cache_repeat_questions": True,
                "reasoning_pass": True,
                "keep_alive": "5m",
                "prewarm_on_open": True,
                "idle_unload_minutes": 10,
                "auto_unload_before_pipeline": True,
                "block_when_busy": True,
                "autostart_ollama": True,
                "max_sessions": 20,
                "session_ttl_minutes": 120
            }
        }
        save_global_config(default_cfg)
        return default_cfg
        
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if "chatbot" not in cfg:
                cfg["chatbot"] = {
                    "enabled": True,
                    "model": "qwen2.5:3b",
                    "share_model_with_step3": False,
                    "base_url": "",
                    "temperature": 0.4,
                    "top_p": 0.9,
                    "repeat_penalty": 1.05,
                    "num_predict": 512,
                    "num_ctx": 8192,
                    "max_history_turns": 12,
                    "kb_token_budget": 3000,
                    "kb_min_score": 0.75,
                    "kb_sticky_per_session": True,
                "cache_repeat_questions": True,
                "reasoning_pass": True,
                    "keep_alive": "5m",
                    "prewarm_on_open": True,
                    "idle_unload_minutes": 10,
                    "auto_unload_before_pipeline": True,
                    "block_when_busy": True,
                    "autostart_ollama": True,
                    "max_sessions": 20,
                    "session_ttl_minutes": 120
                }
            # Máy đã dùng từ trước có sẵn global_config.json nên KHÔNG đi qua
            # nhánh tạo mặc định ở trên. Thiếu bước này thì các thanh trượt tham
            # số sinh ảnh mở ra trống trơn và trượt về giữa thang, không phải giá
            # trị khuyến nghị.
            video_cfg = cfg.setdefault("video", {})
            for key, value in SD_TUNING_DEFAULTS.items():
                video_cfg.setdefault(key, value)
            return cfg
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
