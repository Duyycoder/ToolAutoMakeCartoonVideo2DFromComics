"""Unload mọi model Ollama đang nằm trong VRAM trước job GPU.

Card 6 GB không chứa nổi cả LLM (~2.5 GB) lẫn TripoSR (~4-6 GB). Ollama giữ model 5 phút
sau lần gọi cuối -> phải chủ động gửi keep_alive=0. Ollama không chạy thì bỏ qua.
"""
import json
import urllib.request


def _request(url: str, payload: dict | None = None, timeout: float = 3.0) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — localhost cố định
        return json.loads(resp.read() or b"{}")


def unload_all_models(base_url: str) -> list[str]:
    try:
        loaded = [m["name"] for m in _request(f"{base_url}/api/ps").get("models", [])]
    except (OSError, ValueError):
        return []  # Ollama không chạy / không phản hồi
    unloaded = []
    for name in loaded:
        try:
            _request(f"{base_url}/api/generate", {"model": name, "keep_alive": 0}, timeout=10)
            unloaded.append(name)
        except (OSError, ValueError):
            pass
    return unloaded
