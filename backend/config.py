"""Đọc cấu hình: configs/config.json (cá nhân, không commit) ghi đè lên config.example.json."""
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "configs"
WEBUI_DIR = ROOT_DIR / "webui"
LOGS_DIR = ROOT_DIR / "logs"


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict:
    config = json.loads((CONFIG_DIR / "config.example.json").read_text(encoding="utf-8"))
    user_file = CONFIG_DIR / "config.json"
    if user_file.exists():
        try:
            config = _deep_merge(config, json.loads(user_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            # File cá nhân hỏng không được làm sập app -> dùng mặc định, báo log.
            print(f"[CANH BAO] configs/config.json loi JSON ({exc}) - dung cau hinh mac dinh.")
    return config
