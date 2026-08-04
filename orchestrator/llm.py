"""Hạ tầng LLM dùng chung cho Pipeline và Chatbot Trợ Lý.

Hỗ trợ nghị quyết LLM, gọi API OpenAI-compatible (sync), gọi API native Ollama (async streaming),
và giải phóng VRAM (unload) khi bận.
"""
import logging
import json
from typing import AsyncGenerator, Optional, Tuple
import httpx

from .config import (
    DEFAULT_GEMINI_ONLINE_MODEL,
    DEFAULT_GEMINI_PROXY_MODEL,
    DEFAULT_OLLAMA_MODEL,
)

logger = logging.getLogger(__name__)


def resolve_llm(
    llm_engine: str,
    args: dict,
    g_config: dict,
    default_model: str,
) -> Tuple[str, str, str]:
    """Phân giải (api_key, base_url, model) dựa trên engine và cấu hình."""
    llm_api_key = args.get("llm_api_key")
    llm_offline_base_url = args.get("llm_offline_base_url")
    llm_offline_model = args.get("llm_offline_model") or default_model

    if llm_engine == "gemini":  # Gemini Online
        resolved_key = llm_api_key or g_config.get("api_keys", {}).get("gemini", "")
        if not resolved_key:
            raise ValueError(
                "Đã chọn Gemini Online nhưng chưa có API Key. "
                "Nhập key ở giao diện hoặc lưu vào Cấu Hình Chung (api_keys.gemini)."
            )
        resolved_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        resolved_model = llm_offline_model or DEFAULT_GEMINI_ONLINE_MODEL
    elif llm_engine == "ollama":  # Ollama (Local)
        resolved_key = "ollama"
        resolved_base_url = (
            llm_offline_base_url
            or g_config.get("crawler", {}).get("ollama_base_url")
            or "http://localhost:11434/v1"
        )
        resolved_model = llm_offline_model or DEFAULT_OLLAMA_MODEL
    else:  # gemini_api (Local Gemini proxy)
        resolved_key = (
            llm_api_key
            or g_config.get("crawler", {}).get("gemini_offline_key", "")
            or g_config.get("api_keys", {}).get("gemini", "")
        )
        if not resolved_key:
            raise ValueError(
                "Đã chọn Gemini Proxy nhưng chưa cấu hình key. "
                "Nhập key ở ô 'Gemini API Key' (Bước 3 hoặc Cấu Hình Chung)."
            )
        resolved_base_url = (
            llm_offline_base_url
            or g_config.get("crawler", {}).get("gemini_offline_base_url")
            or "http://localhost:7860/v1"
        )
        resolved_model = llm_offline_model or DEFAULT_GEMINI_PROXY_MODEL

    return resolved_key, resolved_base_url, resolved_model


def chat(
    base_url: str,
    model: str,
    api_key: str,
    messages: list,
    temperature: float = 0.85,
    timeout: float = 300.0,
) -> str:
    """Gọi {base_url}/chat/completions chuẩn OpenAI (sync) và trả về nội dung phản hồi."""
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": model, "messages": messages, "temperature": temperature}
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]["content"].strip()


# Model có chế độ suy luận nội bộ — phải tắt, xem chú thích ở chat_stream_ollama.
THINKING_MODEL_PREFIXES = ("qwen3", "deepseek-r1", "magistral")


async def chat_stream_ollama(
    base_url: str,
    model: str,
    messages: list,
    options: Optional[dict] = None,
    temperature: float = 0.4,
    top_p: float = 0.9,
    repeat_penalty: float = 1.05,
    num_predict: int = 512,
    num_ctx: int = 8192,
    timeout: float = 120.0,
) -> AsyncGenerator[dict, None]:
    """Gọi native Ollama /api/chat (async streaming).

    Trả về async generator các dict:
    - {"delta": "..."} với từng chunk văn bản sinh ra
    - {"done": True, "prompt_tokens": N, "truncated": bool} khi kết thúc
    """
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    url = f"{root}/api/chat"

    opts = {
        "temperature": temperature,
        "top_p": top_p,
        "repeat_penalty": repeat_penalty,
        "num_predict": num_predict,
        "num_ctx": num_ctx,
    }
    if options:
        opts.update(options)

    payload = {
        "model": model,
        "messages": messages,
        "options": opts,
        "stream": True,
    }

    # Model dòng "thinking" (qwen3...) mặc định sinh một khối suy luận nội bộ vào
    # trường `thinking` TRƯỚC khi sinh `content`. Với num_predict 512, khối đó ăn
    # sạch hạn mức và `content` trả về RỖNG — người dùng thấy trợ lý im lặng hoàn
    # toàn. Tắt chế độ nghĩ để mọi token dành cho câu trả lời thật.
    if any(model.lower().startswith(p) for p in THINKING_MODEL_PREFIXES):
        payload["think"] = False

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if "message" in data and "content" in data["message"]:
                    content = data["message"]["content"]
                    if content:
                        yield {"delta": content}

                if data.get("done", False):
                    prompt_eval_count = data.get("prompt_eval_count", 0)
                    truncated = prompt_eval_count >= int(num_ctx * 0.95)
                    yield {
                        "done": True,
                        "prompt_tokens": prompt_eval_count,
                        "truncated": truncated,
                    }
                    break


def unload_ollama(base_url: str = "", model: str = "") -> bool:
    """Yêu cầu Ollama giải phóng model khỏi VRAM (keep_alive=0)."""
    root = base_url.rstrip("/") if base_url else "http://localhost:11434"
    if root.endswith("/v1"):
        root = root[:-3]

    url = f"{root}/api/generate"
    payload = {"keep_alive": 0}
    if model:
        payload["model"] = model

    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.post(url, json=payload)
            res.raise_for_status()
            logger.info(f"[LLM] Đã yêu cầu Ollama unload model '{model or 'all'}'.")
            return True
    except Exception as e:
        logger.warning(f"[LLM] Không unload được Ollama (bỏ qua): {e}")
        return False
