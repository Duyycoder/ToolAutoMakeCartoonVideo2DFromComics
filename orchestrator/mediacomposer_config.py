"""Ghi tham số sinh ảnh từ Cấu Hình Chung xuống `config.toml` của MediaComposer.

Vì sao đi đường này thay vì thêm tham số dòng lệnh: `adapter_video_cli.py` nằm
trong submodule `AIVoice` và không có sẵn tham số cho steps/guidance/độ phân giải.
MediaComposer vốn đã đọc các giá trị đó từ `[storytelling]` trong `config.toml`,
nên orchestrator chỉ cần ghi vào đúng chỗ trước khi chạy Bước 3 — không phải sửa
một dòng nào trong submodule.

Sửa theo TỪNG DÒNG chứ không parse-rồi-ghi-lại: `config.toml` có nhiều chú thích
giải thích vì sao một giá trị được đặt như vậy (ví dụ vì sao guidance là 5.0 chứ
không phải 1.5). Ghi lại bằng thư viện TOML sẽ xoá sạch chúng.
"""
import logging
import os
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "AIVoice", "apps", "MediaComposer", "config.toml"
))

# Khoá trong global_config["video"] -> khoá trong [storytelling] của config.toml.
# Chỉ những tham số ảnh hưởng trực tiếp tới chất lượng/tốc độ sinh ảnh.
SD_PARAM_MAP = {
    "sd_steps": "num_inference_steps",
    "sd_guidance": "guidance_scale",
    "sd_image_width": "image_width",
    "sd_image_height": "image_height",
    "sd_output_width": "output_width",
    "sd_output_height": "output_height",
    "sd_video_fps": "video_fps",
    "sd_face_detailer_steps": "face_detailer_steps",
    "sd_face_detailer_strength": "face_detailer_strength",
    "sd_ip_adapter_scale": "ip_adapter_scale",
    "sd_studio_render_steps": "studio_render_steps",
    "sd_studio_render_guidance": "studio_render_guidance",
}

# Chặn giá trị vô lý trước khi ghi. Đặt steps = 0 hay guidance âm sẽ làm Bước 3
# chạy cả chục phút rồi mới lỗi, hoặc tệ hơn là ra ảnh rác mà không báo gì.
LIMITS = {
    "num_inference_steps": (1, 60),
    "guidance_scale": (0.0, 20.0),
    "image_width": (256, 2048),
    "image_height": (256, 2048),
    "output_width": (256, 3840),
    "output_height": (256, 2160),
    "video_fps": (1, 60),
    "face_detailer_steps": (1, 60),
    "face_detailer_strength": (0.0, 1.0),
    "ip_adapter_scale": (0.0, 1.5),
    "studio_render_steps": (0, 60),        # 0 = theo num_inference_steps chung
    "studio_render_guidance": (0.0, 20.0),  # 0 = theo guidance_scale chung
}


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:g}" if value != int(value) else f"{value:.1f}"
    return str(value)


def _clamp(key: str, value: Any) -> Any:
    lo, hi = LIMITS.get(key, (None, None))
    if lo is None:
        return value
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    num = max(lo, min(hi, num))
    return int(num) if isinstance(lo, int) else num


def apply_sd_params(video_cfg: Dict[str, Any], config_path: str = CONFIG_PATH) -> Dict[str, Any]:
    """Ghi các khoá `sd_*` vào [storytelling]. Trả về những gì đã ghi.

    Best-effort: thiếu file hoặc không ghi được thì chỉ ghi log rồi bỏ qua — không
    được chặn Bước 3 chỉ vì không tinh chỉnh được tham số.
    """
    wanted = {}
    for src, dst in SD_PARAM_MAP.items():
        if src not in video_cfg or video_cfg[src] in ("", None):
            continue
        val = _clamp(dst, video_cfg[src])
        if val is not None:
            wanted[dst] = val

    if not wanted or not os.path.exists(config_path):
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        logger.warning(f"[MediaComposer] Không đọc được config.toml: {e}")
        return {}

    in_section = False
    written = {}
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped == "[storytelling]"
            continue
        if not in_section:
            continue
        m = re.match(r"^(\s*)([A-Za-z_][\w]*)(\s*=\s*)(.*)$", line)
        if not m:
            continue
        key = m.group(2)
        if key in wanted:
            lines[i] = f"{m.group(1)}{key}{m.group(3)}{_fmt(wanted[key])}\n"
            written[key] = wanted[key]

    # Khoá chưa có trong file thì thêm vào cuối mục [storytelling].
    missing = {k: v for k, v in wanted.items() if k not in written}
    if missing:
        end = len(lines)
        seen = False
        for i, line in enumerate(lines):
            s = line.strip()
            if s == "[storytelling]":
                seen = True
                continue
            if seen and s.startswith("["):
                end = i
                break
        block = [f"{k} = {_fmt(v)}\n" for k, v in missing.items()]
        lines[end:end] = block
        written.update(missing)

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except OSError as e:
        logger.warning(f"[MediaComposer] Không ghi được config.toml: {e}")
        return {}

    logger.info(f"[MediaComposer] Đã áp tham số sinh ảnh: {written}")
    return written
