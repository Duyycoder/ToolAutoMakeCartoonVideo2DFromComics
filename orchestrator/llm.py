"""Phân giải tham số LLM dùng để dịch phụ đề + tiện ích nhả VRAM của Ollama."""
import logging
from typing import Tuple

import httpx

from .config import (
    DEFAULT_GEMINI_ONLINE_MODEL,
    DEFAULT_GEMINI_PROXY_MODEL,
    DEFAULT_OLLAMA_MODEL,
)

logger = logging.getLogger(__name__)


def resolve_llm(llm_engine: str, args: dict, g_config: dict, default_model: str = "") -> Tuple[str, str, str]:
    """Trả (api_key, base_url, model) cho engine dịch đã chọn.

    Ưu tiên giá trị người dùng gửi từ form, sau đó tới Cấu Hình Chung, cuối cùng
    là mặc định của từng engine. Adapter dịch phụ đề nói chuyện với cả ba engine
    qua cùng một giao thức OpenAI-compatible nên chỉ khác nhau ở bộ ba này.
    """
    trans = g_config.get("translate") or {}
    llm_api_key = args.get("llm_api_key")
    llm_base_url = args.get("llm_offline_base_url") or args.get("llm_base_url")
    llm_model = args.get("llm_offline_model") or args.get("llm_model") or default_model

    if llm_engine == "gemini":  # Gemini Online (cần API key trả phí/miễn phí của Google)
        resolved_key = llm_api_key or g_config.get("api_keys", {}).get("gemini", "")
        if not resolved_key:
            raise ValueError(
                "Đã chọn Gemini Online nhưng chưa có API Key. "
                "Nhập key ở form dịch hoặc lưu vào Cấu Hình Chung (api_keys.gemini)."
            )
        resolved_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        resolved_model = llm_model or DEFAULT_GEMINI_ONLINE_MODEL
    elif llm_engine == "gemini_api":  # proxy Gemini-API chạy cục bộ
        resolved_key = (llm_api_key
                        or trans.get("gemini_offline_key", "")
                        or g_config.get("api_keys", {}).get("gemini", "")
                        or "local")
        resolved_base_url = (llm_base_url
                             or trans.get("gemini_offline_base_url")
                             or "http://localhost:7860/v1")
        resolved_model = llm_model or DEFAULT_GEMINI_PROXY_MODEL
    else:  # ollama (mặc định của nhánh này: chạy hẳn trên máy, không cần key)
        resolved_key = "ollama"
        resolved_base_url = (llm_base_url
                             or trans.get("ollama_base_url")
                             or "http://localhost:11434/v1")
        resolved_model = llm_model or trans.get("ollama_model") or DEFAULT_OLLAMA_MODEL

    return resolved_key, resolved_base_url, resolved_model


def unload_ollama(base_url: str = "", model: str = "") -> bool:
    """Yêu cầu Ollama nhả model khỏi VRAM (keep_alive=0) trước bước nặng GPU."""
    root = base_url.rstrip("/") if base_url else "http://localhost:11434"
    if root.endswith("/v1"):
        root = root[:-3]

    payload = {"keep_alive": 0}
    if model:
        payload["model"] = model
    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.post(f"{root}/api/generate", json=payload)
            res.raise_for_status()
        logger.info(f"[LLM] Đã yêu cầu Ollama unload model '{model or 'all'}'.")
        return True
    except Exception as e:
        logger.warning(f"[LLM] Không unload được Ollama (bỏ qua): {e}")
        return False
